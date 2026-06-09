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
"""

from __future__ import annotations

import logging
import os
import threading

import requests as http_requests
from flask import Flask, jsonify, request

app = Flask(__name__)
logger = logging.getLogger("journal_tracker")
logging.basicConfig(level=logging.INFO)

# --- Lazy-init singletons ----------------------------------------------------
_query_agent = None
_init_lock = threading.Lock()


def _get_agent():
    global _query_agent
    if _query_agent is not None:
        return _query_agent

    with _init_lock:
        if _query_agent is not None:
            return _query_agent

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
            return None

        from database.supabase_client import SupabaseClient
        from agents.query_agent import QueryAgent

        db = SupabaseClient(supabase_url, supabase_key)
        _query_agent = QueryAgent(anthropic_key, db)
        logger.info("QueryAgent initialized")
        return _query_agent


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

    agent = _get_agent()
    if not agent:
        _push_message(user_id, "⚠️ 系統尚未就緒，請稍後再試。")
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
    data = request.json or {}

    for event in data.get("events", []):
        event_type = event.get("type")
        user_id = event.get("source", {}).get("userId")

        if event_type == "message" and user_id:
            text = event.get("message", {}).get("text", "").strip()
            if not text:
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
