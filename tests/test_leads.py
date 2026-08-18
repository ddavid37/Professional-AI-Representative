"""Local lead log appends to leads/leads.txt."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.leads import append_lead_record, recent_leads


class AppendLeadRecord(unittest.TestCase):
    def test_appends_pipe_separated_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "leads" / "leads.txt"
            with patch("backend.leads.leads_file_path", return_value=path):
                append_lead_record(
                    "yoni gross",
                    "ygross@gmail.com",
                    "how many siblings Daniel has?",
                    "sent",
                )

            text = path.read_text(encoding="utf-8")
            self.assertIn("name=yoni gross", text)
            self.assertIn("email=ygross@gmail.com", text)
            self.assertIn("question=how many siblings Daniel has?", text)
            self.assertIn("whatsapp=sent", text)

    def test_recent_leads_keeps_only_last_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "leads.txt"
            path.write_text(
                "\n".join(
                    [
                        "2026-06-05T02:35:31.711031+00:00 | name=old | email=old@example.com | question=old q | whatsapp=error",
                        "2026-08-17T16:00:00+00:00 | name=yoni gross | email=ygross@gmail.com | question=how many siblings? | whatsapp=sent",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            now = datetime(2026, 8, 18, 16, 50, tzinfo=timezone.utc)
            with patch("backend.leads.leads_file_path", return_value=path):
                items = recent_leads(now=now, days=7)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["email"], "ygross@gmail.com")
            self.assertEqual(items[0]["whatsapp"], "sent")


if __name__ == "__main__":
    unittest.main()
