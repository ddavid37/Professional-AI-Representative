"""Unit tests for configuration smoke test aggregation (no live APIs)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.smoke_test import run_config_smoke_test


def _pass(check_id: str, name: str, group: str, detail: str = "ok"):
    return {
        "id": check_id,
        "name": name,
        "group": group,
        "status": "pass",
        "required": True,
        "detail": detail,
    }


class SmokeTestAggregation(unittest.TestCase):
    def test_missing_required_env_fails_without_live_sends(self):
        env = {"OPENAI_MODEL": "gpt-4o-mini"}
        with patch.dict(os.environ, env, clear=True):
            with tempfile.TemporaryDirectory() as tmp:
                knowledge = Path(tmp) / "knowledge"
                knowledge.mkdir()
                (knowledge / "bio.md").write_text("Daniel is an ML engineer.\n", encoding="utf-8")
                result = run_config_smoke_test(
                    send_whatsapp=False,
                    knowledge_dir=knowledge,
                    graph_ok=lambda: True,
                    ping_openai=lambda: _pass("openai_live", "OpenAI API", "OpenAI"),
                    ping_tavily=lambda: _pass("tavily_live", "Tavily search", "Tavily"),
                    ping_whatsapp=lambda send: _pass("whatsapp_live", "Twilio WhatsApp send", "Twilio"),
                )
        self.assertFalse(result["ok"])
        ids = {c["id"]: c for c in result["checks"]}
        self.assertEqual(ids["env_openai_api_key"]["status"], "fail")
        self.assertEqual(ids["email_channel"]["status"], "skip")
        self.assertNotIn("sk-", str(result))

    def test_all_required_env_and_live_pass(self):
        env = {
            "OPENAI_API_KEY": "sk-test",
            "TWILIO_ACCOUNT_SID": "sid",
            "TWILIO_AUTH_TOKEN": "secret-auth-xyz",
            "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
            "TWILIO_WHATSAPP_TO": "whatsapp:+972544483282",
            "TAVILY_API_KEY": "tvly-test",
        }
        with patch.dict(os.environ, env, clear=True):
            with tempfile.TemporaryDirectory() as tmp:
                knowledge = Path(tmp) / "knowledge"
                knowledge.mkdir()
                (knowledge / "bio.md").write_text("Daniel is an ML engineer.\n", encoding="utf-8")
                result = run_config_smoke_test(
                    send_whatsapp=True,
                    knowledge_dir=knowledge,
                    graph_ok=lambda: True,
                    ping_openai=lambda: _pass("openai_live", "OpenAI API", "OpenAI"),
                    ping_tavily=lambda: _pass("tavily_live", "Tavily search", "Tavily"),
                    ping_whatsapp=lambda send: _pass("whatsapp_live", "Twilio WhatsApp send", "Twilio"),
                )
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["summary"]["passed"], 8)
        self.assertNotIn("sk-test", str(result))
        self.assertNotIn("tvly-test", str(result))
        self.assertNotIn("secret-auth-xyz", str(result))


if __name__ == "__main__":
    unittest.main()
