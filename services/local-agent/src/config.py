"""Loads services/local-agent/.env. Never logs or prints the loaded values."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class AgentConfig:
    supabase_url: str
    supabase_service_role_key: str
    gmail_oauth_client_id: str
    gmail_oauth_client_secret: str
    gemini_api_key: str
    ai_categorization_enabled: bool
    ai_confidence_threshold: float
    local_agent_port: int


def load_config() -> AgentConfig:
    load_dotenv(_ENV_PATH)
    return AgentConfig(
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        gmail_oauth_client_id=os.environ.get("GMAIL_OAUTH_CLIENT_ID", ""),
        gmail_oauth_client_secret=os.environ.get("GMAIL_OAUTH_CLIENT_SECRET", ""),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        ai_categorization_enabled=os.environ.get("AI_CATEGORIZATION_ENABLED", "true").lower() == "true",
        ai_confidence_threshold=float(os.environ.get("AI_CONFIDENCE_THRESHOLD", "80")),
        local_agent_port=int(os.environ.get("LOCAL_AGENT_PORT", "8765")),
    )
