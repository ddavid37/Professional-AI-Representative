"""Public questions must trigger Tavily; Daniel-personal questions must not."""

from __future__ import annotations

import unittest

from backend.search import format_search_context, should_search_web


class ShouldSearchWeb(unittest.TestCase):
    def test_world_cup_mvp_searches(self):
        self.assertTrue(should_search_web("who won the last mvp of the world cup?"))
        self.assertTrue(should_search_web("what is the weather in ny this week?"))

    def test_daniel_personal_does_not_search(self):
        self.assertFalse(should_search_web("how many siblings Daniel has?"))
        self.assertFalse(should_search_web("yoni gross ygross@gmail.com"))

    def test_failed_search_forbids_memory_answers(self):
        text = format_search_context({"status": "error", "message": "bad key"})
        self.assertIn("live web search failed", text)
        self.assertIn("Do NOT answer this question from memory", text)


if __name__ == "__main__":
    unittest.main()
