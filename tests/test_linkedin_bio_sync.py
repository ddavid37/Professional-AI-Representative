"""Tests for LinkedIn About/Bio sync — same service for manual and scheduled triggers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.dev_panel import sync_credentials_allowed
from backend.knowledge_audit import read_all_events, sync_knowledge_audit
from backend.linkedin_bio_provider import (
    LinkedInBioProviderError,
    MockLinkedInBioProvider,
    UrlLinkedInBioProvider,
    build_linkedin_bio_provider,
)
from backend.linkedin_bio_sync import (
    LINKEDIN_BIO_IDENTITY,
    normalize_bio,
    sync_linkedin_bio,
)


ABOUT = """My technical journey has evolved from the foundations of Machine Learning.

Today, I'm focused on finding my next full-time opportunity."""

LOCAL = """<!-- local-only: career preferences not present on LinkedIn About. -->
Daniel is looking for FDE-style roles that mix technical work with customer-facing and business context."""

CHANGED_ABOUT = """My technical journey has evolved from the foundations of Machine Learning.

Today, I'm focused on finding my next full-time opportunity in agentic AI systems."""


def _seed_knowledge(root: Path, about: str = ABOUT) -> Path:
    knowledge = root / "knowledge"
    knowledge.mkdir()
    (knowledge / LINKEDIN_BIO_IDENTITY).write_text(
        f"<!-- linkedin-about:start -->\n{about}\n<!-- linkedin-about:end -->\n\n{LOCAL}\n",
        encoding="utf-8",
    )
    (knowledge / "other.md").write_text("other knowledge\n", encoding="utf-8")
    sync_knowledge_audit(knowledge)
    return knowledge


def _event_types(knowledge: Path) -> list[str]:
    return [e.get("type") for e in read_all_events(knowledge)]


def _source(knowledge: Path) -> dict:
    state = json.loads((knowledge / ".audit" / "state.json").read_text(encoding="utf-8"))
    return (state.get("sources") or {}).get(LINKEDIN_BIO_IDENTITY) or {}


class NormalizeBioTests(unittest.TestCase):
    def test_whitespace_and_line_endings_are_equivalent(self):
        a = "AI Engineer\n\nBuilding agentic systems"
        b = "AI Engineer\r\n\r\nBuilding agentic systems  "
        c = "AI Engineer\n\n\nBuilding   agentic systems"
        self.assertEqual(normalize_bio(a), normalize_bio(b))
        self.assertEqual(normalize_bio(a), normalize_bio(c))


class ProviderTests(unittest.TestCase):
    def test_refuses_linkedin_hosts(self):
        provider = UrlLinkedInBioProvider("https://www.linkedin.com/in/ddavid37/")
        with self.assertRaises(LinkedInBioProviderError) as ctx:
            provider.get_bio()
        self.assertEqual(ctx.exception.category, "linkedin_host_blocked")

    def test_build_requires_source(self):
        with self.assertRaises(LinkedInBioProviderError) as ctx:
            build_linkedin_bio_provider(source="")
        self.assertEqual(ctx.exception.category, "provider_not_configured")


class LinkedInBioSyncTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.knowledge = _seed_knowledge(self.root)
        self.reloads = {"count": 0}

        def reload_fn():
            self.reloads["count"] += 1
            return {"status": "ok"}

        self.reload_fn = reload_fn
        self.initial_version = _source(self.knowledge).get("version")
        self.initial_text = (self.knowledge / LINKEDIN_BIO_IDENTITY).read_text(encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _sync(self, bio: str, trigger: str = "manual"):
        return sync_linkedin_bio(
            self.knowledge,
            trigger=trigger,
            provider=MockLinkedInBioProvider(bio),
            reload_fn=self.reload_fn,
            project_root=self.root,
        )

    def test_no_change(self):
        result = self._sync(ABOUT)
        self.assertTrue(result.ok)
        self.assertEqual(result.result, "unchanged")
        self.assertEqual(_source(self.knowledge).get("version"), self.initial_version)
        self.assertEqual((self.knowledge / LINKEDIN_BIO_IDENTITY).read_text(encoding="utf-8"), self.initial_text)
        self.assertEqual(self.reloads["count"], 0)
        types = _event_types(self.knowledge)
        self.assertIn("linkedin_bio_sync_unchanged", types)
        self.assertIn("linkedin_bio_sync_completed", types)
        self.assertNotIn("linkedin_bio_changed", types)

    def test_meaningful_change(self):
        result = self._sync(CHANGED_ABOUT)
        self.assertTrue(result.ok)
        self.assertEqual(result.result, "updated")
        self.assertEqual(result.previous_version, self.initial_version)
        self.assertEqual(result.new_version, self.initial_version + 1)
        self.assertTrue(result.change_summary)
        self.assertEqual(self.reloads["count"], 1)
        self.assertIn("FDE-style roles", (self.knowledge / LINKEDIN_BIO_IDENTITY).read_text(encoding="utf-8"))
        self.assertIn("agentic AI systems", (self.knowledge / LINKEDIN_BIO_IDENTITY).read_text(encoding="utf-8"))
        types = _event_types(self.knowledge)
        self.assertIn("linkedin_bio_changed", types)
        self.assertIn("knowledge_updated", types)
        self.assertIn("knowledge_reload_completed", types)
        self.assertEqual(_source(self.knowledge).get("version"), self.initial_version + 1)

    def test_formatting_only_change(self):
        noisy = ABOUT.replace("\n\n", "\n\n\n") + "  "
        result = self._sync(noisy)
        self.assertTrue(result.ok)
        self.assertEqual(result.result, "unchanged")
        self.assertEqual(_source(self.knowledge).get("version"), self.initial_version)
        self.assertEqual(self.reloads["count"], 0)

    def test_fetch_failure_keeps_knowledge(self):
        class Boom:
            def get_bio(self):
                raise LinkedInBioProviderError("export_http_error", "Authorized export URL request failed.")

        result = sync_linkedin_bio(
            self.knowledge,
            trigger="scheduled",
            provider=Boom(),
            reload_fn=self.reload_fn,
            project_root=self.root,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_category, "export_http_error")
        self.assertEqual((self.knowledge / LINKEDIN_BIO_IDENTITY).read_text(encoding="utf-8"), self.initial_text)
        self.assertEqual(_source(self.knowledge).get("version"), self.initial_version)
        self.assertEqual(self.reloads["count"], 0)
        self.assertIn("linkedin_bio_sync_failed", _event_types(self.knowledge))

    def test_empty_bio_rejected(self):
        result = self._sync("   \n\n  ")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_category, "empty_bio")
        self.assertEqual((self.knowledge / LINKEDIN_BIO_IDENTITY).read_text(encoding="utf-8"), self.initial_text)
        self.assertEqual(self.reloads["count"], 0)

    def test_duplicate_execution_does_not_version(self):
        first = self._sync(CHANGED_ABOUT, trigger="scheduled")
        second = self._sync(CHANGED_ABOUT, trigger="manual")
        third = self._sync(CHANGED_ABOUT, trigger="scheduled")
        self.assertEqual(first.result, "updated")
        self.assertEqual(second.result, "unchanged")
        self.assertEqual(third.result, "unchanged")
        self.assertEqual(_source(self.knowledge).get("version"), self.initial_version + 1)
        self.assertEqual(self.reloads["count"], 1)

    def test_manual_and_scheduled_use_same_service(self):
        manual = self._sync(ABOUT, trigger="manual")
        scheduled = self._sync(ABOUT, trigger="scheduled")
        self.assertEqual(manual.result, scheduled.result)
        self.assertEqual(manual.result, "unchanged")
        events = read_all_events(self.knowledge)
        triggers = [e.get("trigger") for e in events if e.get("type") == "linkedin_bio_sync_started"]
        self.assertIn("manual", triggers)
        self.assertIn("scheduled", triggers)


class SyncAuthTests(unittest.TestCase):
    def test_accepts_panel_secret(self):
        self.assertTrue(
            sync_credentials_allowed("panel-secret", None, panel_secret="panel-secret", cron_secret="cron")
        )

    def test_accepts_cron_bearer(self):
        self.assertTrue(
            sync_credentials_allowed(None, "Bearer cron-token", panel_secret="panel", cron_secret="cron-token")
        )

    def test_rejects_wrong_secret(self):
        self.assertFalse(
            sync_credentials_allowed("nope", "Bearer nope", panel_secret="panel", cron_secret="cron")
        )

    def test_vercel_requires_secret(self):
        self.assertFalse(sync_credentials_allowed(None, None, panel_secret="", cron_secret="", vercel=True))
        self.assertTrue(sync_credentials_allowed(None, None, panel_secret="", cron_secret="", vercel=False))


if __name__ == "__main__":
    unittest.main()
