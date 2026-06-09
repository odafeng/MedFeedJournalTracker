"""LINE Webhook — receives messages and replies via QueryAgent.

Uses Push API (not Reply API) because the agent takes 5-15 seconds
to respond, and Reply tokens expire in ~30 seconds which is too tight
when combined with Render free-tier cold starts.

Deployment: Render web service (24/7), separate from the daily cron job.

    gunicorn agents.webhook:app --bind 0.0.0.0:$PORT --timeout 120 --preload

Required env vars:
    LINE_CHANNEL_ACCESS_TOKEN
    ANTHROPIC_API_KEY
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE (or SUPABASE_KEY / SUPABASE_API_KEY)

Recommended (security):
    LINE_CHANNEL_SECRET          enables X-Line-Signature verification so only
                                 LINE's servers can trigger the agent (blocks
                                 anonymous POSTs that would burn Anthropic quota)
Optional:
    LINE_RESTRICT_TO_SUBSCRIBERS="true"  only answer users in the subscribers table
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import threading
import time
from collections import defaultdict, deque

import requests as http_requests
from flask import Flask, jsonify, request

app = Flask(__name__)
logger = logging.getLogger("journal_tracker")
logging.basicConfig(level=logging.INFO)

# --- Lazy-init singletons ----------------------------------------------------
_query_agent = None
_db_client = None
_init_lock = threading.Lock()

# --- Rate limiting (in-memory; single gunicorn worker shares this) -----------
_RATE_WINDOW_SEC = 3600          # rolling window
_RATE_MAX_PER_WINDOW = 30        # max queries per user per window
_RATE_MIN_INTERVAL_SEC = 3       # min seconds between consecutive queries
_rate_lock = threading.Lock()
_user_hits: dict[str, deque] = defaultdict(deque)


def _init_clients():
    """Lazily build the Supabase client + QueryAgent (shared singletons)."""
    global _query_agent, _db_client
    if _query_agent is not None:
        return _query_agent, _db_client

    with _init_lock:
        if _query_agent is not None:
            return _query_agent, _db_client

        from dotenv import load_dotenv
        load_dotenv(override=False)

        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_API_KEY")
        )

        if not all([anthropic_key, supabase_url, supabase_key]):
            logger.error("Missing env vars for QueryAgent")
            return None, None

        from database.supabase_client import SupabaseClient
        from agents.query_agent import QueryAgent

        _db_client = SupabaseClient(supabase_url, supabase_key)
        _query_agent = QueryAgent(anthropic_key, _db_client)
        logger.info("QueryAgent initialized")
        return _query_agent, _db_client


# --- Security helpers ---------------------------------------------------------

def _verify_signature(body: bytes, signature: str | None) -> bool:
    """Validate LINE's X-Line-Signature (HMAC-SHA256 of the raw body).

    If LINE_CHANNEL_SECRET is not configured we allow the request but warn,
    so existing deploys keep working until the secret is added. Once set,
    invalid signatures are rejected — this is what blocks anonymous abuse.
    """
    secret = os.getenv("LINE_CHANNEL_SECRET")
    if not secret:
        logger.warning("LINE_CHANNEL_SECRET not set — signature verification disabled")
        return True
    if not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def _rate_limit_ok(user_id: str) -> tuple[bool, str]:
    """Per-user rolling-window rate limit. Returns (ok, message_if_blocked)."""
    now = time.time()
    with _rate_lock:
        dq = _user_hits[user_id]
        while dq and dq[0] < now - _RATE_WINDOW_SEC:
            dq.popleft()
        if dq and now - dq[-1] < _RATE_MIN_INTERVAL_SEC:
            return False, "⏳ 您送出的速度太快了，請稍候幾秒再試。"
        if len(dq) >= _RATE_MAX_PER_WINDOW:
            return False, "⚠️ 您這個時段的查詢次數已達上限，請稍後再試。"
        dq.append(now)
        return True, ""


def _is_allowed_user(db, user_id: str) -> bool:
    """When LINE_RESTRICT_TO_SUBSCRIBERS is on, only answer known subscribers."""
    if os.getenv("LINE_RESTRICT_TO_SUBSCRIBERS", "").lower() not in ("1", "true", "yes"):
        return True
    allowlist = {
        u.strip() for u in os.getenv("LINE_ALLOWED_USER_IDS", "").split(",") if u.strip()
    }
    if user_id in allowlist:
        return True
    try:
        return bool(db and db.is_active_subscriber(user_id))
    except Exception as e:
        logger.error(f"Subscriber check failed: {e}")
        return False


# --- LINE push ----------------------------------------------------------------

def _push_message(user_id: str, text: str) -> bool:
    """Send a message via LINE Push API (no token expiry issue)."""
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        logger.error("LINE_CHANNEL_ACCESS_TOKEN not set")
        return False

    if len(text) > 5000:
        text = text[:4950] + "\n\n... (回覆過長，已截斷)"

    try:
        r = http_requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            json={
                "to": user_id,
                "messages": [{"type": "text", "text": text}],
            },
            timeout=30,
        )
        if r.status_code == 200:
            logger.info(f"Push message sent to {user_id[:8]}...")
            return True
        logger.error(f"Push failed ({r.status_code}): {r.text[:300]}")
        return False
    except Exception as e:
        logger.error(f"Push failed: {e}")
        return False


def _handle_message(user_id: str, text: str) -> None:
    """Process message in a background thread (non-blocking)."""
    # Immediate acknowledgement so the user knows the query was received.
    # The agent itself takes 5-15s; without this the chat looks dead and the
    # user can't tell whether the message went through.
    _push_message(user_id, "🔍 收到您的問題，搜尋中，請稍候…")

    agent, db = _init_clients()
    if not agent:
        _push_message(user_id, "⚠️ 系統尚未就緒，請稍後再試。")
        return

    if not _is_allowed_user(db, user_id):
        _push_message(user_id, "ℹ️ 您尚未訂閱本服務，目前無法使用查詢功能。")
        return

    try:
        answer = agent.ask(text)
        _push_message(user_id, answer)
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        _push_message(user_id, f"⚠️ 查詢時發生錯誤，請稍後再試。\n（{str(e)[:150]}）")


# --- Routes ------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data()
    signature = request.headers.get("X-Line-Signature")
    if not _verify_signature(body, signature):
        logger.warning("Rejected webhook with invalid signature")
        return jsonify({"status": "invalid signature"}), 403

    data = request.get_json(silent=True) or {}

    for event in data.get("events", []):
        event_type = event.get("type")
        user_id = event.get("source", {}).get("userId")

        if event_type == "message" and user_id:
            text = event.get("message", {}).get("text", "").strip()
            if not text:
                continue

            ok, block_msg = _rate_limit_ok(user_id)
            if not ok:
                _push_message(user_id, block_msg)
                continue

            # Process in background thread so we return 200 immediately
            # (LINE expects a response within a few seconds)
            thread = threading.Thread(
                target=_handle_message, args=(user_id, text), daemon=True
            )
            thread.start()

    return jsonify({"status": "ok"})


@app.route("/", methods=["GET"])
def index():
    return "MedFeed Query Agent is running."


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})
