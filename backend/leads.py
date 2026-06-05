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
    "sibli",  # common typo
    "salary",
    "family",
    "ask daniel",
)
AFFIRMATIVE_HINTS = ("yes", "ok", "okay", "sure", "please", "go ahead", "do it", "ask daniel")


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


def _text_has_question_shape(text: str) -> bool:
    lower = text.lower().strip()
    if "?" in lower:
        return True
    return any(hint in lower for hint in QUESTION_HINTS)


def _looks_like_name(text: str) -> bool:
    text = text.strip()
    if not text or "@" in text or "?" in text:
        return False
    lower = text.lower()
    if _text_has_question_shape(text):
        return False
    words = text.split()
    return 1 <= len(words) <= 6 and len(text) < 80


def _line_is_question(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if EMAIL_RE.search(line):
        return _question_fragment_from_mixed_line(line) is not None
    if _looks_like_name(line):
        return False
    return _text_has_question_shape(line)


def _question_fragment_from_mixed_line(text: str) -> Optional[str]:
    """Pull the question portion out of a single line that also has name + email."""
    match = EMAIL_RE.search(text)
    if not match:
        return None

    after = text[match.end() :].strip(" ,.-")
    if after and _text_has_question_shape(after):
        return after

    before = text[: match.start()].strip(" ,.-")
    if before and _text_has_question_shape(before):
        return before

    return None


def _question_from_message(text: str) -> Optional[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        for line in reversed(lines):
            if _line_is_question(line):
                fragment = _question_fragment_from_mixed_line(line)
                return fragment or line
        return None

    if _line_is_question(text):
        return _question_fragment_from_mixed_line(text) or text.strip()
    return None


def _extract_question(user_contents: List[str]) -> Optional[str]:
    for content in reversed(user_contents):
        question = _question_from_message(content)
        if question:
            return question
    return None


def _name_from_mixed_line(text: str, email: str) -> Optional[str]:
    match = EMAIL_RE.search(text)
    if not match:
        return None
    before = text[: match.start()].strip(" ,.-")
    if before and _looks_like_name(before):
        return before
    return None


def _extract_name_from_contact_message(text: str, email: str) -> str:
    mixed = _name_from_mixed_line(text, email)
    if mixed:
        return mixed

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
    return _find_email_in_history(_user_contents(messages)) is not None


def _latest_user_message(messages: List[ChatLike]) -> Optional[str]:
    for msg in reversed(messages):
        if msg.role == "user" and msg.content.strip():
            return msg.content.strip()
    return None


def _is_affirmative_follow_up(text: str) -> bool:
    lower = text.lower().strip()
    return any(hint in lower for hint in AFFIRMATIVE_HINTS) and "@" not in lower


def extract_lead_from_messages(messages: List[ChatLike]) -> Optional[LeadInfo]:
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
    return (
        "[Internal — inquiry recorded]\n"
        "Daniel was notified on WhatsApp about this visitor inquiry.\n"
        f"- Name: {lead.name}\n"
        f"- Email: {lead.email}\n"
        f"- Question: {lead.question}\n\n"
        "Respond warmly: confirm the inquiry was recorded, restate their question, "
        "and say Daniel will follow up personally. Do NOT ask for name or email again. "
        "Do NOT offer to collect details by email — they are already on file."
    )


def contact_info_reminder_note(messages: List[ChatLike]) -> Optional[str]:
    """
    When the visitor already shared an email but the latest message is just
    'yes' / 'ask daniel', remind the model not to re-collect contact info.
    """
    if not conversation_has_contact_info(messages):
        return None

    latest = _latest_user_message(messages)
    if not latest:
        return None

    question = _extract_question(_user_contents(messages))
    email = _find_email_in_history(_user_contents(messages)) or "on file"

    if question:
        return (
            "[Internal — contact info already provided]\n"
            f"The visitor's email ({email}) and question are already in this thread: "
            f"\"{question}\".\n"
            "Confirm Daniel will follow up. Do NOT ask for name, email, or permission again."
        )

    if _is_affirmative_follow_up(latest):
        return (
            "[Internal — waiting for question]\n"
            f"The visitor already agreed to follow-up and shared email ({email}).\n"
            "Ask them to restate the specific question for Daniel, or confirm the last "
            "topic they asked about. Do NOT restart the contact-collection flow."
        )

    return None


def collect_contact_prompt_note(messages: List[ChatLike]) -> Optional[str]:
    """
    When the visitor says 'yes' to follow-up but has not shared email yet,
    steer the model to ask for name + email instead of a generic reset.
    """
    if conversation_has_contact_info(messages):
        return None

    latest = _latest_user_message(messages)
    if not latest or not _is_affirmative_follow_up(latest):
        return None

    question = _extract_question(_user_contents(messages))
    if question:
        return (
            "[Internal — user agreed to follow-up]\n"
            f"The visitor agreed to forward this question to Daniel: \"{question}\".\n"
            "In your reply, ask for their **full name** and **email address** so Daniel can "
            "follow up. Do NOT give a generic greeting like \"how can I assist you today\". "
            "Do NOT ask if they want to proceed again — they already said yes."
        )

    return (
        "[Internal — user agreed to follow-up]\n"
        "The visitor agreed to have Daniel follow up. Ask for their **full name** and "
        "**email address** in your next reply. Do NOT reset with a generic greeting."
    )


def conversation_context_note(messages: List[ChatLike]) -> Optional[str]:
    """Pick the right injected note for the current conversation state."""
    return contact_info_reminder_note(messages) or collect_contact_prompt_note(messages)


def _lead_key(lead: LeadInfo) -> str:
    return f"{lead.email.lower()}|{lead.question.strip().lower()}"


def lead_already_logged(lead: LeadInfo) -> bool:
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
    lead = extract_lead_from_messages(messages)
    if lead is None:
        return None

    if lead_already_logged(lead):
        return {"lead": lead, "skipped": True, "reason": "already_logged"}

    return {"lead": lead, "skipped": False}
