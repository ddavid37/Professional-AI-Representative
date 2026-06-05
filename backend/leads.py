"""
Lead extraction from chat conversations and local persistence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class ChatLike(Protocol):
    role: str
    content: str


@dataclass
class LeadInfo:
    name: str
    email: str
    question: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def leads_file_path() -> Path:
    return _project_root() / "leads" / "leads.txt"


def ensure_leads_dir() -> None:
    leads_file_path().parent.mkdir(parents=True, exist_ok=True)


def _is_contact_reply(text: str) -> bool:
    """True when the message looks like someone sharing contact details."""
    return EMAIL_RE.search(text) is not None


def _extract_name_from_contact_message(text: str, email: str) -> str:
    """Best-effort name parse from a contact-details message."""
    for pattern in (
        r"(?:name|i(?:'m| am))\s*[:\s]+(.+?)(?:,|\n|$)",
        r"^(.+?)\s*,\s*" + re.escape(email),
    ):
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            candidate = match.group(1).strip()
            if candidate and "@" not in candidate:
                return candidate

    for line in text.splitlines():
        stripped = line.strip()
        if stripped and email not in stripped and "@" not in stripped:
            return stripped

    return "unknown"


def _find_original_question(messages: List[ChatLike]) -> str:
    """
    Walk backward through user turns and pick the most recent message that is
    not the contact-details reply (the one containing an email).
    """
    user_messages = [m.content.strip() for m in messages if m.role == "user" and m.content.strip()]
    if not user_messages:
        return "No question captured"

    if len(user_messages) == 1:
        return user_messages[0]

    # Latest user message is usually the contact reply; question is the prior turn.
    for content in reversed(user_messages[:-1]):
        if not _is_contact_reply(content):
            return content

    return user_messages[0]


def extract_lead_from_messages(messages: List[ChatLike]) -> Optional[LeadInfo]:
    """
    When the latest user message includes an email, treat the conversation as
    a completed lead capture and return structured lead info.
    """
    if not messages:
        return None

    latest_user: Optional[str] = None
    for msg in reversed(messages):
        if msg.role == "user" and msg.content.strip():
            latest_user = msg.content.strip()
            break

    if not latest_user:
        return None

    email_match = EMAIL_RE.search(latest_user)
    if not email_match:
        return None

    email = email_match.group(0)
    name = _extract_name_from_contact_message(latest_user, email)
    question = _find_original_question(messages)

    return LeadInfo(name=name, email=email, question=question)


def _lead_key(lead: LeadInfo) -> str:
    return f"{lead.email.lower()}|{lead.question.strip().lower()}"


def lead_already_logged(lead: LeadInfo) -> bool:
    """Avoid duplicate WhatsApp notifications for the same inquiry."""
    path = leads_file_path()
    if not path.is_file():
        return False

    key = _lead_key(lead)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False

    return f"email={lead.email.lower()}" in text.lower() and lead.question.strip().lower() in text.lower()


def append_lead_record(lead: LeadInfo, whatsapp_status: str) -> str:
    """Append a lead line to leads/leads.txt and return the formatted line."""
    ensure_leads_dir()
    timestamp = datetime.now(timezone.utc).isoformat()
    line = (
        f"{timestamp} | name={lead.name} | email={lead.email} | "
        f"question={lead.question} | whatsapp={whatsapp_status}"
    )
    with leads_file_path().open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip() + "\n")
    return line


def process_lead_capture(messages: List[ChatLike]) -> Optional[Dict[str, Any]]:
    """
    Extract a lead from the conversation, log it, and return metadata for the caller.
    Returns None when no new lead is detected.
    """
    lead = extract_lead_from_messages(messages)
    if lead is None:
        return None

    if lead_already_logged(lead):
        return {"lead": lead, "skipped": True, "reason": "already_logged"}

    return {"lead": lead, "skipped": False}
