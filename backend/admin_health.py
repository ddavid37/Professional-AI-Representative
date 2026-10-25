"""
Admin connectivity checks: OpenAI, Tavily, Twilio, and lead storage.

Each check is cheap, runs with a timeout, and never returns secret values —
only configured / not configured, ok / error, latency, and a short redacted error.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import Header, HTTPException

from .leads import leads_file_path
from .search import search_web as tavily_search
from .smoke_test import _configured, _mask_whatsapp, _safe_error
from .whatsapp import TWILIO_SANDBOX_FROM, _content_sid, _whatsapp_from

CHECK_TIMEOUT_S = 8.0
_SECRET_ENV = ("OPENAI_API_KEY", "TAVILY_API_KEY", "TWILIO_AUTH_TOKEN", "ADMIN_TOKEN")


def require_admin_token(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> None:
    """Fail closed: without ADMIN_TOKEN set on the API, the admin endpoints are disabled."""
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin page disabled: set ADMIN_TOKEN on the API.")
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


def _redact(text: str) -> str:
    """Strip any secret env value that leaked into an error message."""
    for name in _SECRET_ENV:
        value = os.getenv(name, "").strip()
        if len(value) >= 6:
            text = text.replace(value, "***")
    return _safe_error(Exception(text))


def _result(status: str, detail: str = "", **extra: Any) -> Dict[str, Any]:
    return {"status": status, "detail": detail, **extra}


def check_openai() -> Dict[str, Any]:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    if not _configured("OPENAI_API_KEY"):
        return _result("not_configured", "OPENAI_API_KEY is not set.", model=model)
    from openai import OpenAI

    client = OpenAI(timeout=CHECK_TIMEOUT_S, max_retries=0)
    client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
    )
    return _result("ok", f"A 1-token call to {model} succeeded.", model=model)


def check_tavily() -> Dict[str, Any]:
    if not _configured("TAVILY_API_KEY"):
        return _result("not_configured", "TAVILY_API_KEY is not set.")
    result = tavily_search("OpenAI", max_results=1)
    if result.get("status") != "ok":
        return _result("error", _redact(str(result.get("message") or "unknown error")))
    if not (result.get("results") or result.get("answer")):
        return _result("error", "Search succeeded but returned no results.")
    return _result("ok", "Search returned results.")


def check_twilio() -> Dict[str, Any]:
    sender = _whatsapp_from()
    config = {
        "sandbox": sender == TWILIO_SANDBOX_FROM,
        "content_sid_set": _configured("TWILIO_CONTENT_SID"),
        "whatsapp_to": _mask_whatsapp(os.getenv("TWILIO_WHATSAPP_TO", "")) if _configured("TWILIO_WHATSAPP_TO") else "not set",
    }
    if not (_configured("TWILIO_ACCOUNT_SID") and _configured("TWILIO_AUTH_TOKEN")):
        return _result("not_configured", "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN are not set.", **config)
    from twilio.http.http_client import TwilioHttpClient
    from twilio.rest import Client

    client = Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN"),
        http_client=TwilioHttpClient(timeout=CHECK_TIMEOUT_S),
    )
    account = client.api.accounts(os.getenv("TWILIO_ACCOUNT_SID")).fetch()
    if account.status != "active":
        return _result("error", f"Twilio account status is {account.status}.", **config)

    # The template sent with each lead must exist on this account (error 21655 otherwise).
    content_sid = _content_sid()
    if content_sid:
        try:
            client.content.v1.contents(content_sid).fetch()
            config["template"] = "found"
        except Exception:
            config["template"] = "not found on this account"
            return _result(
                "error",
                "Credentials are valid, but the WhatsApp template SID is not on this account. "
                "Leads fall back to plain text.",
                **config,
            )
    return _result("ok", "Credentials are valid and the account is active.", **config)


def check_storage() -> Dict[str, Any]:
    """
    Chat history lives in the visitor's browser (localStorage); the backend is stateless.
    The only server-side store is the lead log, so probe that it can be written and read.
    """
    path = leads_file_path()
    probe = path.parent / f".health-{uuid.uuid4().hex}"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        ok = probe.read_text(encoding="utf-8") == "ok"
    except OSError as exc:
        return _result(
            "error",
            f"Lead log is not writable ({exc.__class__.__name__}); leads are only delivered over WhatsApp.",
            store="leads/leads.txt",
        )
    finally:
        try:
            probe.unlink()
        except OSError:
            pass
    if not ok:
        return _result("error", "Lead log probe read back the wrong value.", store="leads/leads.txt")
    return _result("ok", "Lead log can be written and read.", store="leads/leads.txt")


CHECKS: Dict[str, Callable[[], Dict[str, Any]]] = {
    "openai": check_openai,
    "tavily": check_tavily,
    "twilio": check_twilio,
    "storage": check_storage,
}


async def _timed(check: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await asyncio.wait_for(asyncio.to_thread(check), timeout=CHECK_TIMEOUT_S + 2)
    except asyncio.TimeoutError:
        result = _result("error", f"Timed out after {CHECK_TIMEOUT_S + 2:.0f}s.")
    except Exception as exc:
        result = _result("error", _redact(str(exc) or exc.__class__.__name__))
    result["latency_ms"] = round((time.perf_counter() - started) * 1000)
    return result


async def run_admin_health(checks: Optional[Dict[str, Callable[[], Dict[str, Any]]]] = None) -> Dict[str, Any]:
    selected = checks or CHECKS
    results = await asyncio.gather(*(_timed(fn) for fn in selected.values()))
    by_name = dict(zip(selected.keys(), results))
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ok": all(r["status"] == "ok" for r in by_name.values()),
        "checks": by_name,
    }
