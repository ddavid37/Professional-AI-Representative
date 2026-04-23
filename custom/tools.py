"""
Tools for the Professional Representative Agent: SendGrid email and Lead Capture.
Uses Pydantic for LeadCapture schema and @function_tool for the Agents SDK.
"""
import os
from typing import Dict

import sendgrid
from pydantic import BaseModel, Field
from sendgrid.helpers.mail import Content, Email, Mail, To

from agents import function_tool


# ----- Pydantic schema for lead capture -----
class LeadCapture(BaseModel):
    """Schema for capturing a lead when the agent cannot answer a question."""

    name: str = Field(description="Full name of the person making the inquiry.")
    email: str = Field(description="Email address where they can be reached.")
    question: str = Field(description="The specific question or topic they asked that could not be answered.")


def send_html_email(subject: str, html_body: str) -> Dict[str, str]:
    """
    Send an HTML email via SendGrid. Used to notify Daniel of captured leads.
    Expects SENDGRID_API_KEY, EMAIL_FROM (verified sender), EMAIL_TO (Daniel) in env.
    """
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        return {"status": "error", "message": "SENDGRID_API_KEY not set"}

    from_email = os.environ.get("EMAIL_FROM", "noreply@example.com")
    to_email = os.environ.get("EMAIL_TO", "daniel@example.com")

    try:
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        mail = Mail(
            from_email=Email(from_email),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_body),
        )
        response = sg.client.mail.send.post(request_body=mail.get())
        if response.status_code in (200, 202):
            return {"status": "sent", "message": "Email delivered"}
        return {"status": "error", "message": f"SendGrid returned {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@function_tool
def lead_capture(name: str, email: str, question: str) -> Dict[str, str]:
    """
    Use this when you cannot answer the user's question (e.g. salary, private project details,
    or anything not in Daniel's public bio). Captures their name, email, and question, then
    notifies Daniel via email so he can follow up. Tell the user you've recorded their
    inquiry and Daniel will get back to them.
    """
    # Validate with Pydantic (optional but keeps schema consistent)
    payload = LeadCapture(name=name, email=email, question=question)

    subject = f"[Lead] {payload.name} – {payload.question[:50]}..."
    html_body = f"""
    <h2>New lead from Professional Rep Bot</h2>
    <p><strong>Name:</strong> {payload.name}</p>
    <p><strong>Email:</strong> {payload.email}</p>
    <p><strong>Question / topic:</strong></p>
    <blockquote>{payload.question}</blockquote>
    """
    result = send_html_email(subject=subject, html_body=html_body)
    if result.get("status") == "sent":
        return {"status": "ok", "message": "Inquiry recorded; Daniel will be notified."}
    return {"status": "error", "message": result.get("message", "Failed to send notification.")}
