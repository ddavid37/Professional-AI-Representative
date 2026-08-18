"""Append-only local lead log. Not the WhatsApp delivery path."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RECENT_LEAD_DAYS = 7


def leads_file_path() -> Path:
    return Path(__file__).resolve().parents[1] / "leads" / "leads.txt"


def _field(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def append_lead_record(name: str, email: str, question: str, whatsapp_status: str) -> None:
    """
    Append one line to leads/leads.txt. Fail-soft on read-only filesystems (Vercel).
    """
    path = leads_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        line = (
            f"{timestamp} | name={_field(name)} | email={_field(email)} | "
            f"question={_field(question)} | whatsapp={whatsapp_status}\n"
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        return


def _parse_timestamp(raw: str) -> Optional[datetime]:
    text = raw.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_lead_line(line: str) -> Optional[Dict[str, str]]:
    parts = [part.strip() for part in line.split("|")]
    if len(parts) < 2:
        return None
    fields: Dict[str, str] = {"timestamp": parts[0]}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        fields[key.strip().lower()] = value.strip()
    if not fields.get("email") and not fields.get("question"):
        return None
    return fields


def recent_leads(*, now: Optional[datetime] = None, days: int = RECENT_LEAD_DAYS) -> List[Dict[str, Any]]:
    """Return leads from the last `days` days, newest first."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = moment - timedelta(days=days)
    path = leads_file_path()
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    items: List[Dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        record = parse_lead_line(line)
        if not record:
            continue
        stamp = _parse_timestamp(record.get("timestamp", ""))
        if stamp is None or stamp < cutoff:
            continue
        items.append(
            {
                "timestamp": stamp.isoformat(),
                "name": record.get("name") or "Guest",
                "email": record.get("email") or "",
                "question": record.get("question") or "",
                "whatsapp": record.get("whatsapp") or "",
            }
        )
    items.sort(key=lambda item: item["timestamp"], reverse=True)
    return items
