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
QUESTION_HINTS = (
    "how",
    "what",
    "when",
    "where",
    "why",
    "who",
    "does",
    "do ",
    "is ",
    "are ",
    "can ",
    "could ",
    "would ",
    "daniel",
    "sibling",
    "salary",
    "family",
)


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


def _user_contents(messages: List[ChatLike]) -> List[str]:
    return [m.content.strip() for m in messages if m.role == "user" and m.content.strip()]


def _find_email_in_history(user_contents: List[str]) -> Optional[str]:
    for content in reversed(user_contents):
        match = EMAIL_RE.search(content)
        if match:
            return match.group(0)
    return None


def _looks_like_name(text: str) -> bool:
    text = text.strip()
    if not text or "@" in text or "?" in text:
        return False
    lower = text.lower()
    if any(hint in lower for hint in QUESTION_HINTS):
        return False
    words = text.split()
    return 1 <= len(words) <= 6 and len(text) < 80


def _line_is_question(line: str) -> bool:
    line = line.strip()
    if not line or EMAIL_RE.search(line) or _looks_like_name(line):
        return False
    if "?" in line:
        return True
    lower = line.lower()
    return any(hint in lower for hint in QUESTION_HINTS)


def _question_from_message(text: str) -> Optional[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        for line in reversed(lines):
            if _line_is_question(line):
                return line
        return None
    if _line_is_question(text):
        return text.strip()
    return None


def _extract_question(user_contents: List[str]) -> Optional[str]:
    for content in reversed(user_contents):
        question = _question_from_message(content)
        if question:
            return question
    return None


def _extract_name_from_contact_message(text: str, email: str) -> str:
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
        if stripped and email not in stripped and "@" not in stripped and _looks_like_name(stripped):
            return stripped

    return "unknown"


def _find_name_in_history(user_contents: List[str], email: str) -> str:
    for index, content in enumerate(user_contents):
        if email not in content and not EMAIL_RE.search(content):
            continue
        name = _extract_name_from_contact_message(content, email)
        if name != "unknown":
            return name
        if index > 0 and _looks_like_name(user_contents[index - 1]):
            return user_contents[index - 1].strip()

    for content in user_contents:
        if _looks_like_name(content):
            return content.strip()

    return "unknown"


def conversation_has_contact_info(messages: List[ChatLike]) -> bool:
    """True when the visitor has shared an email anywhere in the thread."""
    return _find_email_in_history(_user_contents(messages)) is not None


def extract_lead_from_messages(messages: List[ChatLike]) -> Optional[LeadInfo]:
    """
    Build a lead when the conversation contains both an email and a substantive
    question, even if the user sent them in separate messages.
    """
    user_contents = _user_contents(messages)
    if not user_contents:
        return None

    email = _find_email_in_history(user_contents)
    if not email:
        return None

    question = _extract_question(user_contents)
    if not question:
        return None

    name = _find_name_in_history(user_contents, email)
    return LeadInfo(name=name, email=email, question=question)


def lead_confirmation_note(lead: LeadInfo) -> str:
    """System note injected so the agent confirms capture instead of re-asking."""
    return (
        "[Internal — inquiry recorded]\n"
        "Daniel was notified on WhatsApp about this visitor inquiry.\n"
        f"- Name: {lead.name}\n"
        f"- Email: {lead.email}\n"
        f"- Question: {lead.question}\n\n"
        "Respond warmly: confirm the inquiry was recorded, restate their question, "
        "and say Daniel will follow up personally. Do NOT ask for name or email again."
    )


def _lead_key(lead: LeadInfo) -> str:
    return f"{lead.email.lower()}|{lead.question.strip().lower()}"


def lead_already_logged(lead: LeadInfo) -> bool:
    """Avoid duplicate WhatsApp notifications for the same inquiry."""
    path = leads_file_path()
    if not path.is_file():
        return False

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False

    return (
        f"email={lead.email.lower()}" in text.lower()
        and lead.question.strip().lower() in text.lower()
    )


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
    Extract a lead from the conversation and return metadata for the caller.
    Returns None when email + question are not both present yet.
    """
    lead = extract_lead_from_messages(messages)
    if lead is None:
        return None

    if lead_already_logged(lead):
        return {"lead": lead, "skipped": True, "reason": "already_logged"}

    return {"lead": lead, "skipped": False}
