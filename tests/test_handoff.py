"""Handoff should forward the original question, not a consent reply."""

from __future__ import annotations

import unittest

from backend.handoff import select_handoff_question


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


if __name__ == "__main__":
    unittest.main()
