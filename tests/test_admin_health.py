"""Admin health: token guard, secret redaction, and aggregation (no live APIs)."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend import admin_health
from backend.admin_health import check_storage, require_admin_token, run_admin_health


class AdminTokenGuard(unittest.TestCase):
    def test_disabled_without_admin_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as ctx:
                require_admin_token("anything")
        self.assertEqual(ctx.exception.status_code, 503)

    def test_rejects_wrong_token_and_accepts_right_one(self):
        with patch.dict(os.environ, {"ADMIN_TOKEN": "s3cret-token"}, clear=True):
            with self.assertRaises(HTTPException) as ctx:
                require_admin_token("wrong")
            self.assertEqual(ctx.exception.status_code, 401)
            self.assertIsNone(require_admin_token("s3cret-token"))


class AdminHealthRun(unittest.TestCase):
    def test_aggregates_and_redacts_secret_in_errors(self):
        def leaky():
            raise RuntimeError("bad key tvly-abc123SECRET for request")

        env = {"TAVILY_API_KEY": "tvly-abc123SECRET"}
        with patch.dict(os.environ, env, clear=True):
            result = asyncio.run(
                run_admin_health({"ok": lambda: {"status": "ok", "detail": "fine"}, "tavily": leaky})
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["checks"]["ok"]["status"], "ok")
        self.assertIn("latency_ms", result["checks"]["ok"])
        self.assertEqual(result["checks"]["tavily"]["status"], "error")
        self.assertNotIn("abc123SECRET", result["checks"]["tavily"]["detail"])

    def test_slow_check_times_out(self):
        with patch.object(admin_health, "CHECK_TIMEOUT_S", -1.9):
            result = asyncio.run(run_admin_health({"slow": lambda: time.sleep(0.5) or {"status": "ok"}}))
        self.assertEqual(result["checks"]["slow"]["status"], "error")
        self.assertIn("Timed out", result["checks"]["slow"]["detail"])

    def test_unconfigured_services_report_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(admin_health.check_openai()["status"], "not_configured")
            self.assertEqual(admin_health.check_tavily()["status"], "not_configured")
            self.assertEqual(admin_health.check_twilio()["status"], "not_configured")


class StorageProbe(unittest.TestCase):
    def test_writable_dir_is_ok_and_leaves_no_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            leads = Path(tmp) / "leads" / "leads.txt"
            with patch.object(admin_health, "leads_file_path", return_value=leads):
                self.assertEqual(check_storage()["status"], "ok")
            self.assertEqual(list(leads.parent.iterdir()), [])

    def test_read_only_dir_is_an_error(self):
        with patch.object(admin_health, "leads_file_path", return_value=Path("/proc/nope/leads.txt")):
            self.assertEqual(check_storage()["status"], "error")


if __name__ == "__main__":
    unittest.main()
