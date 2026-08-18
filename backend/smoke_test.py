"""
Configuration smoke test for the Professional AI Representative.

Checks env presence and live connectivity for OpenAI, Tavily, Twilio WhatsApp,
and knowledge/agent. Never returns secret values.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from custom.knowledge_loader import KNOWLEDGE_DIR_NAME, get_project_dir, load_knowledge_dir
from .search import search_web as tavily_search
from .whatsapp import send_test_message


REQUIRED_ENV = (
    ("OPENAI_API_KEY", "OpenAI", "LLM calls"),
    ("TWILIO_ACCOUNT_SID", "Twilio", "WhatsApp lead notifications"),
    ("TWILIO_AUTH_TOKEN", "Twilio", "WhatsApp lead notifications"),
    ("TWILIO_WHATSAPP_FROM", "Twilio", "WhatsApp sender"),
    ("TWILIO_WHATSAPP_TO", "Twilio", "Daniel's WhatsApp number"),
    ("TAVILY_API_KEY", "Tavily", "Public web search"),
)

OPTIONAL_ENV = (
    ("NEXT_PUBLIC_API_URL", "Frontend", "Usually set on the frontend project"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _configured(name: str) -> bool:
    value = os.getenv(name)
    return bool(value and value.strip())


def _mask_whatsapp(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) < 4:
        return "configured"
    return f"…{digits[-4:]}"


def _safe_error(exc: BaseException) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-***", text)
    text = re.sub(r"tvly-[A-Za-z0-9_-]+", "tvly-***", text)
    return text[:240]


def _check(
    check_id: str,
    name: str,
    group: str,
    status: str,
    *,
    required: bool = True,
    detail: str = "",
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "name": name,
        "group": group,
        "status": status,
        "required": required,
        "detail": detail,
    }


def _env_check(name: str, group: str, purpose: str, *, required: bool) -> Dict[str, Any]:
    present = _configured(name)
    if present:
        extra = ""
        if name in {"TWILIO_WHATSAPP_FROM", "TWILIO_WHATSAPP_TO"}:
            extra = f" {_mask_whatsapp(os.getenv(name, ''))}."
        elif name == "NEXT_PUBLIC_API_URL":
            extra = " Present in this API process."
        return _check(
            f"env_{name.lower()}",
            name,
            group,
            "pass",
            required=required,
            detail=f"{purpose}.{extra}".strip(),
        )
    if required:
        return _check(
            f"env_{name.lower()}",
            name,
            group,
            "fail",
            required=True,
            detail=f"Missing. {purpose}.",
        )
    return _check(
        f"env_{name.lower()}",
        name,
        group,
        "skip",
        required=False,
        detail=f"Not set. {purpose}.",
    )


def _ping_openai() -> Dict[str, Any]:
    if not _configured("OPENAI_API_KEY"):
        return _check(
            "openai_live",
            "OpenAI API",
            "OpenAI",
            "skip",
            required=True,
            detail="Skipped because OPENAI_API_KEY is missing.",
        )
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    try:
        from openai import OpenAI

        client = OpenAI()
        client.models.retrieve(model)
        return _check(
            "openai_live",
            "OpenAI API",
            "OpenAI",
            "pass",
            detail=f"Reached OpenAI; model {model} is available.",
        )
    except Exception as exc:
        return _check(
            "openai_live",
            "OpenAI API",
            "OpenAI",
            "fail",
            detail=_safe_error(exc),
        )


def _ping_tavily() -> Dict[str, Any]:
    if not _configured("TAVILY_API_KEY"):
        return _check(
            "tavily_live",
            "Tavily search",
            "Tavily",
            "skip",
            required=True,
            detail="Skipped because TAVILY_API_KEY is missing.",
        )
    result = tavily_search("OpenAI", max_results=1)
    if result.get("status") == "ok" and (result.get("results") or result.get("answer")):
        return _check(
            "tavily_live",
            "Tavily search",
            "Tavily",
            "pass",
            detail="Search returned at least one result.",
        )
    return _check(
        "tavily_live",
        "Tavily search",
        "Tavily",
        "fail",
        detail=str(result.get("message") or "Search returned no results."),
    )


def _ping_whatsapp(*, send: bool) -> Dict[str, Any]:
    twilio_ready = all(
        _configured(name)
        for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "TWILIO_WHATSAPP_TO")
    )
    if not send:
        return _check(
            "whatsapp_live",
            "Twilio WhatsApp send",
            "Twilio",
            "skip",
            required=True,
            detail="Send skipped by request.",
        )
    if not twilio_ready:
        return _check(
            "whatsapp_live",
            "Twilio WhatsApp send",
            "Twilio",
            "skip",
            required=True,
            detail="Skipped because one or more TWILIO_* vars are missing.",
        )
    result = send_test_message()
    dest = _mask_whatsapp(os.getenv("TWILIO_WHATSAPP_TO", ""))
    if result.get("status") == "sent":
        return _check(
            "whatsapp_live",
            "Twilio WhatsApp send",
            "Twilio",
            "pass",
            detail=f"Test message sent to {dest}. This app does not send email.",
        )
    return _check(
        "whatsapp_live",
        "Twilio WhatsApp send",
        "Twilio",
        "fail",
        detail=str(result.get("message") or "WhatsApp send failed."),
    )


def _check_knowledge(knowledge_dir: Optional[Path] = None) -> Dict[str, Any]:
    root = knowledge_dir or (get_project_dir() / KNOWLEDGE_DIR_NAME)
    if not root.is_dir():
        return _check(
            "knowledge",
            "Knowledge directory",
            "Knowledge",
            "fail",
            detail="knowledge/ is missing.",
        )
    text = load_knowledge_dir(root)
    files = [
        p.name
        for p in sorted(root.iterdir())
        if p.is_file() and p.suffix.lower() in {".txt", ".md", ".markdown", ".pdf"} and p.name.upper() != "README.MD"
    ]
    if not text.strip() or not files:
        return _check(
            "knowledge",
            "Knowledge directory",
            "Knowledge",
            "fail",
            detail="No readable knowledge files loaded.",
        )
    return _check(
        "knowledge",
        "Knowledge directory",
        "Knowledge",
        "pass",
        detail=f"Loaded {len(files)} file(s): {', '.join(files[:8])}.",
    )


def _check_agent(graph_ok: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
    try:
        if graph_ok is None:
            from . import agent as agent_module

            ok = agent_module.GRAPH is not None
        else:
            ok = graph_ok()
        if ok:
            return _check("agent", "LangGraph agent", "Agent", "pass", detail="Agent graph is loaded.")
        return _check("agent", "LangGraph agent", "Agent", "fail", detail="Agent graph is not loaded.")
    except Exception as exc:
        return _check("agent", "LangGraph agent", "Agent", "fail", detail=_safe_error(exc))


def run_config_smoke_test(
    *,
    send_whatsapp: bool = True,
    knowledge_dir: Optional[Path] = None,
    graph_ok: Optional[Callable[[], bool]] = None,
    ping_openai: Optional[Callable[[], Dict[str, Any]]] = None,
    ping_tavily: Optional[Callable[[], Dict[str, Any]]] = None,
    ping_whatsapp: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    for name, group, purpose in REQUIRED_ENV:
        checks.append(_env_check(name, group, purpose, required=True))
    for name, group, purpose in OPTIONAL_ENV:
        checks.append(_env_check(name, group, purpose, required=False))

    checks.append((ping_openai or _ping_openai)())
    checks.append((ping_tavily or _ping_tavily)())
    if ping_whatsapp is not None:
        checks.append(ping_whatsapp(send=send_whatsapp))
    else:
        checks.append(_ping_whatsapp(send=send_whatsapp))
    checks.append(_check_knowledge(knowledge_dir))
    checks.append(_check_agent(graph_ok))
    checks.append(
        _check(
            "email_channel",
            "Email / SendGrid",
            "Notifications",
            "skip",
            required=False,
            detail="Not used in production. Leads are WhatsApp-only (legacy SendGrid lives in custom/).",
        )
    )

    required_failed = [c for c in checks if c["required"] and c["status"] == "fail"]
    ok = len(required_failed) == 0
    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    skipped = sum(1 for c in checks if c["status"] == "skip")

    return {
        "ok": ok,
        "ran_at": _utc_now(),
        "summary": {"passed": passed, "failed": failed, "skipped": skipped, "total": len(checks)},
        "checks": checks,
        "notes": [
            "Leads are delivered on WhatsApp only. This app does not send email.",
            "The WhatsApp live check sends a real test message to TWILIO_WHATSAPP_TO.",
            "Secret values are never returned.",
        ],
    }
