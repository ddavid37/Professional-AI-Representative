"""Handoff should forward the original question, not a consent reply."""

from __future__ import annotations

import unittest

from backend.handoff import scrub_unverified_emails, select_handoff_question


class SelectHandoffQuestion(unittest.TestCase):
    def test_skips_ack_and_uses_original_question(self):
        turns = [
            "how many siblings Daniel has?",
            "ok let's do that",
            "yoni gross ygross@gmail.com",
        ]
        self.assertEqual(
            select_handoff_question(turns),
            "how many siblings Daniel has?",
        )

    def test_skips_short_yes_and_email_turns(self):
        turns = [
            "What is Daniel's dream?",
            "yes",
            "lebron james lebron@gmail.com",
        ]
        self.assertEqual(select_handoff_question(turns), "What is Daniel's dream?")

    def test_returns_none_without_a_prior_question(self):
        self.assertIsNone(select_handoff_question(["yoni ygross@gmail.com"]))
        self.assertIsNone(
            select_handoff_question(["ok let's do that", "yoni ygross@gmail.com"])
        )


class ScrubUnverifiedEmails(unittest.TestCase):
    def test_removes_invented_email(self):
        text = "Reach Daniel at daniel.david@gmail.com anytime."
        out = scrub_unverified_emails(text, ["daniel.david@columbia.edu"])
        self.assertNotIn("@gmail.com", out)
        self.assertIn("Contact page", out)

    def test_keeps_verified_and_visitor_emails(self):
        text = "Daniel: Daniel.David@columbia.edu. He'll reply to ygross@gmail.com."
        out = scrub_unverified_emails(
            text, ["daniel.david@columbia.edu", "ygross@gmail.com"]
        )
        self.assertEqual(out, text)


if __name__ == "__main__":
    unittest.main()
