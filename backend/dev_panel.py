"""
Developer panel helpers: env var presence (names only, never values).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import Header, HTTPException

from .knowledge_audit import read_all_events


# Snapshot of the Vercel API project env vars (names/dates only — update when Vercel changes).
VERCEL_API_ENV_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "OPENAI_API_KEY",
        "group": "OpenAI",
        "sensitive": True,
        "environments": ["Production", "Preview"],
        "last_action": "Updated",
        "last_updated": "2026-05-05",
    },
    {
        "name": "NEXT_PUBLIC_API_URL",
        "group": "Frontend",
        "sensitive": True,
        "environments": ["Production"],
        "last_action": "Added",
        "last_updated": "2026-06-04",
        "note": "Set on API project today; belongs on the frontend Vercel project.",
    },
    {
        "name": "TWILIO_ACCOUNT_SID",
        "group": "Twilio",
        "sensitive": True,
        "environments": ["Production"],
        "last_action": "Added",
        "last_updated": "2026-06-05",
    },
    {
        "name": "TWILIO_AUTH_TOKEN",
        "group": "Twilio",
        "sensitive": True,
        "environments": ["Production"],
        "last_action": "Added",
        "last_updated": "2026-06-05",
    },
    {
        "name": "TWILIO_WHATSAPP_FROM",
        "group": "Twilio",
        "sensitive": False,
        "environments": ["Production"],
        "last_action": "Added",
        "last_updated": "2026-06-05",
    },
    {
        "name": "TWILIO_WHATSAPP_TO",
        "group": "Twilio",
        "sensitive": False,
        "environments": ["Production"],
        "last_action": "Added",
        "last_updated": "2026-06-05",
    },
    {
        "name": "TAVILY_API_KEY",
        "group": "Tavily",
        "sensitive": True,
        "environments": ["Production", "Preview"],
        "last_action": "Added",
        "last_updated": "2026-08-12",
    },
]

LOCAL_ONLY_ENV_VARS: List[Dict[str, Any]] = [
    {"name": "OPENAI_MODEL", "required": False, "group": "OpenAI"},
    {"name": "DEV_PANEL_SECRET", "required": False, "group": "Dev panel"},
]


def _is_configured(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip())


def api_env_status() -> Dict[str, Any]:
    vercel_vars: List[Dict[str, Any]] = []
    for spec in VERCEL_API_ENV_CATALOG:
        vercel_vars.append(
            {
                **spec,
                "scope": "vercel-api",
                "configured_local": _is_configured(spec["name"]),
            }
        )

    local_only: List[Dict[str, Any]] = []
    for spec in LOCAL_ONLY_ENV_VARS:
        local_only.append(
            {
                "name": spec["name"],
                "scope": "local-only",
                "group": spec["group"],
                "required": spec["required"],
                "configured_local": _is_configured(spec["name"]),
                "on_vercel_api": False,
            }
        )

    return {
        "vercel_api": vercel_vars,
        "local_only": local_only,
        "vercel_catalog_updated": "2026-08-17",
    }


def require_dev_panel_secret(
    x_dev_panel_secret: Optional[str] = Header(None, alias="X-Dev-Panel-Secret"),
) -> None:
    expected = os.getenv("DEV_PANEL_SECRET")
    if not expected:
        return
    if x_dev_panel_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing dev panel secret")


def dev_panel_payload(knowledge_dir) -> Dict[str, Any]:
    from pathlib import Path

    if not isinstance(knowledge_dir, Path):
        knowledge_dir = Path(knowledge_dir)

    state_path = knowledge_dir / ".audit" / "state.json"
    state: Dict[str, Any] = {}
    if state_path.is_file():
        import json

        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}

    sources = state.get("sources") or {}
    current = [s for s in sources.values() if s.get("status") == "current"]
    stale = [s for s in sources.values() if s.get("status") == "stale"]

    return {
        "env_vars": api_env_status(),
        "knowledge": {
            "state": state,
            "sources_current": sorted(current, key=lambda s: s.get("identity", "")),
            "sources_stale": sorted(stale, key=lambda s: s.get("identity", "")),
            "events": read_all_events(knowledge_dir),
        },
        "dev_panel_secret_required": bool(os.getenv("DEV_PANEL_SECRET")),
    }
