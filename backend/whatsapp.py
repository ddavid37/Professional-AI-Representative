"""
Twilio WhatsApp notifications for captured leads.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from twilio.rest import Client


def _whatsapp_from() -> str:
    raw = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    return raw if raw.startswith("whatsapp:") else f"whatsapp:{raw}"


def _whatsapp_to() -> str:
    raw = os.getenv("TWILIO_WHATSAPP_TO", "whatsapp:+972544483282")
    return raw if raw.startswith("whatsapp:") else f"whatsapp:{raw}"


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

    body = (
        "New inquiry for Daniel David\n\n"
        f"Question: {question}\n\n"
        f"From: {name}\n"
        f"Email: {email}"
    )

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body,
            from_=_whatsapp_from(),
            to=_whatsapp_to(),
        )
        return {"status": "sent", "sid": message.sid}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def send_test_message() -> Dict[str, Any]:
    """Send a short test message to verify Twilio WhatsApp sandbox setup."""
    return send_lead_notification(
        name="Test User",
        email="test@example.com",
        question="This is a test — your WhatsApp integration is working.",
    )
