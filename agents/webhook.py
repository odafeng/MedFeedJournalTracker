"""LINE Webhook — receives messages and replies via QueryAgent.

Deployment: Render web service (24/7), separate from the daily cron job.

    gunicorn agents.webhook:app --bind 0.0.0.0:$PORT

Required env vars:
    LINE_CHANNEL_ACCESS_TOKEN
    ANTHROPIC_API_KEY
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE (or SUPABASE_KEY / SUPABASE_API_KEY)
"""

from __future__ import annotations

import logging
import os

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
logger = logging.getLogger("journal_tracker")

# --- Lazy-init singletons ----------------------------------------------------
_query_agent = None


def _get_agent():
    global _query_agent
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


def _reply(reply_token: str, text: str) -> bool:
    """Reply to a LINE message using the Reply API."""
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        return False

    if len(text) > 5000:
        text = text[:4950] + "\n\n... (回覆過長，已截斷)"

    try:
        r = requests.post(
            "https://api.line.me/v2/bot/message/reply",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            json={
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": text}],
            },
            timeout=30,
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Reply failed: {e}")
        return False


# --- Routes ------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}

    for event in data.get("events", []):
        event_type = event.get("type")
        reply_token = event.get("replyToken")

        if event_type == "message" and reply_token:
            text = event.get("message", {}).get("text", "").strip()
            if not text:
                continue

            agent = _get_agent()
            if not agent:
                _reply(reply_token, "系統尚未就緒，請稍後再試。")
                continue

            try:
                answer = agent.ask(text)
                _reply(reply_token, answer)
            except Exception as e:
                logger.error(f"Agent error: {e}", exc_info=True)
                _reply(reply_token, f"查詢時發生錯誤：{str(e)[:200]}")

    return jsonify({"status": "ok"})


@app.route("/", methods=["GET"])
def index():
    return "MedFeed Query Agent is running."


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})
