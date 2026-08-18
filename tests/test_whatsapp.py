"""Sandbox WhatsApp sends must use the template that actually delivers."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from backend.whatsapp import DEFAULT_SANDBOX_CONTENT_SID, send_lead_notification


def _ok_message() -> MagicMock:
    msg = MagicMock()
    msg.sid = "SMtest"
    msg.error_code = None
    msg.error_message = None
    return msg


class WhatsAppSend(unittest.TestCase):
    @patch("backend.whatsapp.append_lead_record")
    @patch("backend.whatsapp.Client")
    def test_sandbox_uses_content_template_with_question(
        self, client_cls: MagicMock, _append: MagicMock
    ):
        client_cls.return_value.messages.create.return_value = _ok_message()
        env = {
            "TWILIO_ACCOUNT_SID": "ACtest",
            "TWILIO_AUTH_TOKEN": "token",
            "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
            "TWILIO_WHATSAPP_TO": "whatsapp:+15555555555",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TWILIO_CONTENT_SID", None)
            result = send_lead_notification(
                "yoni gross",
                "ygross@gmail.com",
                "how many siblings Daniel has?",
            )

        self.assertEqual(result["status"], "sent")
        kwargs = client_cls.return_value.messages.create.call_args.kwargs
        self.assertEqual(kwargs["content_sid"], DEFAULT_SANDBOX_CONTENT_SID)
        self.assertNotIn("body", kwargs)
        variables = json.loads(kwargs["content_variables"])
        self.assertEqual(variables["1"], "how many siblings Daniel has?")
        self.assertIn("yoni gross", variables["2"])
        self.assertIn("ygross@gmail.com", variables["2"])

    @patch("backend.whatsapp.append_lead_record")
    @patch("backend.whatsapp.Client")
    def test_non_sandbox_sender_uses_freeform_body(
        self, client_cls: MagicMock, _append: MagicMock
    ):
        client_cls.return_value.messages.create.return_value = _ok_message()
        env = {
            "TWILIO_ACCOUNT_SID": "ACtest",
            "TWILIO_AUTH_TOKEN": "token",
            "TWILIO_WHATSAPP_FROM": "whatsapp:+15551234567",
            "TWILIO_WHATSAPP_TO": "whatsapp:+15555555555",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TWILIO_CONTENT_SID", None)
            result = send_lead_notification("Ada", "ada@example.com", "hello")

        self.assertEqual(result["status"], "sent")
        kwargs = client_cls.return_value.messages.create.call_args.kwargs
        self.assertNotIn("content_sid", kwargs)
        self.assertIn("New inquiry for Daniel David", kwargs["body"])
        self.assertIn("hello", kwargs["body"])


if __name__ == "__main__":
    unittest.main()
