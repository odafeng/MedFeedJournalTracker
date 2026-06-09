"""Tests for the /webhook route: signature gate, rate limit, event dispatch."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from agents import webhook


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    webhook._user_hits.clear()
    webhook._conversations.clear()
    yield
    webhook._user_hits.clear()
    webhook._conversations.clear()


@pytest.fixture
def client():
    webhook.app.config["TESTING"] = True
    return webhook.app.test_client()


def _post(client, payload, secret=None):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if secret:
        sig = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()
        headers["X-Line-Signature"] = sig
    return client.post("/webhook", data=body, headers=headers)


def _msg_event(user_id="U1", text="hi"):
    return {"events": [{"type": "message", "source": {"userId": user_id},
                        "message": {"type": "text", "text": text}}]}


def test_health_ok(client):
    assert client.get("/health").get_json() == {"status": "healthy"}


def test_invalid_signature_rejected(client, monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "secret")
    body = json.dumps(_msg_event()).encode()
    r = client.post("/webhook", data=body,
                    headers={"X-Line-Signature": "wrong", "Content-Type": "application/json"})
    assert r.status_code == 403


def test_valid_signature_dispatches(client, monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "secret")
    calls = []
    # Run the "background" handler synchronously so we can assert on it.
    monkeypatch.setattr(webhook, "_handle_message", lambda uid, text: calls.append((uid, text)))

    class _SyncThread:
        def __init__(self, target, args, daemon=None):
            self._target, self._args = target, args
        def start(self):
            self._target(*self._args)
    monkeypatch.setattr(webhook.threading, "Thread", _SyncThread)

    r = _post(client, _msg_event("Uabc", "你好"), secret="secret")
    assert r.status_code == 200
    assert calls == [("Uabc", "你好")]


def test_rate_limit_blocks_rapid_second_message(client, monkeypatch):
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)  # signature disabled
    pushed = []
    monkeypatch.setattr(webhook, "_push_message", lambda uid, text: pushed.append((uid, text)))
    monkeypatch.setattr(webhook, "_handle_message", lambda uid, text: None)

    class _SyncThread:
        def __init__(self, target, args, daemon=None):
            self._target, self._args = target, args
        def start(self):
            self._target(*self._args)
    monkeypatch.setattr(webhook.threading, "Thread", _SyncThread)

    _post(client, _msg_event("Uxyz", "q1"))
    _post(client, _msg_event("Uxyz", "q2"))  # immediate second -> rate limited
    # The rate-limit rejection is delivered via _push_message
    assert any("太快" in text for _, text in pushed)
