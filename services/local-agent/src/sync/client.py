"""
Supabase client for the sync layer. Uses the SERVICE ROLE key — this bypasses
RLS by design, which is exactly why this client must only ever run in this
trusted, local, non-browser process, never be embedded in apps/web.
"""

from __future__ import annotations

from supabase import Client, create_client

from src.config import AgentConfig


def get_service_client(config: AgentConfig) -> Client:
    if not config.supabase_url or not config.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in .env")
    return create_client(config.supabase_url, config.supabase_service_role_key)
