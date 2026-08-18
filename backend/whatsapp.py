"""
Twilio WhatsApp notifications for captured leads.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from twilio.rest import Client

TWILIO_SANDBOX_FROM = "whatsapp:+14155238886"
# Public Twilio sandbox sample: "Your appointment is coming up on {{1}} at {{2}}"
# Free-form `body` is accepted by the API but often never delivered to
# international sandbox numbers; this template is what actually arrives.
DEFAULT_SANDBOX_CONTENT_SID = "HXb5b62575e6e4ff6129ad7c8efe1f983e"
_MAX_TEMPLATE_VAR = 200


def _whatsapp_from() -> str:
    raw = os.getenv("TWILIO_WHATSAPP_FROM", TWILIO_SANDBOX_FROM)
    return raw if raw.startswith("whatsapp:") else f"whatsapp:{raw}"


def _whatsapp_to() -> str:
    raw = os.getenv("TWILIO_WHATSAPP_TO", "whatsapp:+972544483282")
    return raw if raw.startswith("whatsapp:") else f"whatsapp:{raw}"


def _content_sid() -> str:
    explicit = os.getenv("TWILIO_CONTENT_SID", "").strip()
    if explicit:
        return explicit
    if _whatsapp_from() == TWILIO_SANDBOX_FROM:
        return DEFAULT_SANDBOX_CONTENT_SID
    return ""


def _template_variables(name: str, email: str, question: str) -> str:
    question_text = " ".join(question.split())
    if len(question_text) > _MAX_TEMPLATE_VAR:
        question_text = question_text[: _MAX_TEMPLATE_VAR - 1] + "…"
    who = f"{name} / {email}"
    if len(who) > _MAX_TEMPLATE_VAR:
        who = who[: _MAX_TEMPLATE_VAR - 1] + "…"
    return json.dumps({"1": question_text, "2": who})


def _lead_body(name: str, email: str, question: str) -> str:
    return (
        "New inquiry for Daniel David\n\n"
        f"Question: {question}\n\n"
        f"From: {name}\n"
        f"Email: {email}"
    )


def send_lead_notification(name: str, email: str, question: str) -> Dict[str, Any]:
    """
    Send a WhatsApp message to Daniel when a visitor leaves contact details
    for a question the agent could not answer.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        return {
            "status": "error",
            "message": "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set (local .env or Vercel env vars on the API project).",
        }

    body = _lead_body(name, email, question)
    content_sid = _content_sid()

    try:
        client = Client(account_sid, auth_token)
        if content_sid:
            message = client.messages.create(
                content_sid=content_sid,
                content_variables=_template_variables(name, email, question),
                from_=_whatsapp_from(),
                to=_whatsapp_to(),
            )
        else:
            message = client.messages.create(
                body=body,
                from_=_whatsapp_from(),
                to=_whatsapp_to(),
            )
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    error_code = getattr(message, "error_code", None)
    if error_code:
        return {
            "status": "error",
            "sid": getattr(message, "sid", None),
            "message": getattr(message, "error_message", None) or str(error_code),
        }
    return {"status": "sent", "sid": message.sid}


def send_test_message() -> Dict[str, Any]:
    """Send a short test message to verify Twilio WhatsApp sandbox setup."""
    return send_lead_notification(
        name="Test User",
        email="test@example.com",
        question="This is a test — your WhatsApp integration is working.",
    )
