"""Centralized, typed configuration loader.

All environment variable access happens here. The rest of the app imports
`Settings` and reads typed attributes — not `os.getenv` — so missing config
surfaces as a clear error at startup, not a `None`-related crash mid-run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _load_env_files() -> None:
    """Load .env files in priority order. Later files do NOT override earlier ones."""
    for filename in (".env.local", ".env", ".env.production"):
        path = Path(filename)
        if path.exists():
            load_dotenv(path, override=False)


@dataclass(frozen=True)
class Settings:
    """Typed settings object. All required fields validated at construction time."""

    # Supabase
    supabase_url: str
    supabase_key: str

    # Telegram
    telegram_token: str
    telegram_chat_id: str

    # Anthropic / LLM
    anthropic_api_key: str
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_daily_budget: int = 50

    # PubMed (optional)
    pubmed_api_key: Optional[str] = None

    # Notion (optional)
    notion_token: Optional[str] = None
    notion_database_id: Optional[str] = None

    # LINE (optional — parallel raw-alert channel for subscribers).
    # Subscribers live in Supabase (authoritative); the JSON file is an
    # optional local seed that gets upserted into the DB when present.
    line_channel_access_token: Optional[str] = None
    line_subscribers_file: Path = Path("config/subscribers.json")

    # Runtime
    log_level: str = "INFO"
    days_back: int = 7

    # Feature flags
    llm_enabled: bool = True
    telegram_enabled: bool = True
    notion_sync_enabled: bool = field(init=False)
    line_enabled: bool = field(init=False)

    def __post_init__(self) -> None:
        # Notion sync is enabled only if both token and DB id are present
        object.__setattr__(
            self, "notion_sync_enabled",
            bool(self.notion_token and self.notion_database_id),
        )
        # LINE is enabled whenever a token is set — subscribers come from DB,
        # not from a file, so the presence of subscribers.json is irrelevant.
        object.__setattr__(
            self, "line_enabled",
            bool(self.line_channel_access_token),
        )

    @classmethod
    def from_env(cls) -> "Settings":
        _load_env_files()

        def req(name: str) -> str:
            val = os.getenv(name)
            if not val:
                raise RuntimeError(
                    f"Missing required environment variable: {name}. "
                    f"Check your .env.local or Render environment settings."
                )
            return val

        # Accept multiple historical names for Supabase key
        supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_API_KEY")
        )
        if not supabase_key:
            raise RuntimeError(
                "Missing Supabase key: set SUPABASE_SERVICE_ROLE (preferred), "
                "SUPABASE_KEY, or SUPABASE_API_KEY."
            )

        return cls(
            supabase_url=req("SUPABASE_URL"),
            supabase_key=supabase_key,
            telegram_token=req("TELEGRAM_TOKEN"),
            telegram_chat_id=req("TELEGRAM_CHAT_ID"),
            anthropic_api_key=req("ANTHROPIC_API_KEY"),
            llm_model=os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929"),
            llm_daily_budget=int(os.getenv("LLM_DAILY_BUDGET", "50")),
            pubmed_api_key=os.getenv("PUBMED_API_KEY"),
            notion_token=os.getenv("NOTION_TOKEN"),
            notion_database_id=os.getenv("NOTION_DATABASE_ID"),
            line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            days_back=int(os.getenv("DAYS_BACK", "7")),
        )
