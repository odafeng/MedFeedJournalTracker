"""Tests for the webhook security helpers: signature verification + rate limit."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

import pytest

from agents import webhook


@pytest.fixture(autouse=True)
def _reset_rate_state():
    webhook._user_hits.clear()
    yield
    webhook._user_hits.clear()


def _sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_signature_valid(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "s3cr3t")
    body = b'{"events":[]}'
    assert webhook._verify_signature(body, _sign("s3cr3t", body)) is True


def test_signature_invalid(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "s3cr3t")
    body = b'{"events":[]}'
    assert webhook._verify_signature(body, _sign("wrong", body)) is False
    assert webhook._verify_signature(body, None) is False


def test_signature_disabled_when_no_secret(monkeypatch):
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
    # No secret configured -> allow (so existing deploys keep working).
    assert webhook._verify_signature(b"anything", None) is True


def test_rate_limit_min_interval():
    ok, _ = webhook._rate_limit_ok("U1")
    assert ok is True
    # Immediate second hit is too fast.
    ok, msg = webhook._rate_limit_ok("U1")
    assert ok is False and msg


def test_rate_limit_window_cap(monkeypatch):
    monkeypatch.setattr(webhook, "_RATE_MIN_INTERVAL_SEC", 0)
    for _ in range(webhook._RATE_MAX_PER_WINDOW):
        ok, _ = webhook._rate_limit_ok("U2")
        assert ok is True
    ok, msg = webhook._rate_limit_ok("U2")
    assert ok is False and msg


def test_rate_limit_is_per_user(monkeypatch):
    monkeypatch.setattr(webhook, "_RATE_MIN_INTERVAL_SEC", 0)
    assert webhook._rate_limit_ok("A")[0] is True
    assert webhook._rate_limit_ok("B")[0] is True
