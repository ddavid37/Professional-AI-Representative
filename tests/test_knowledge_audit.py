"""Knowledge audit should not crash the API on a read-only filesystem (Vercel)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.knowledge_audit import sync_knowledge_audit


class KnowledgeAuditReadOnly(unittest.TestCase):
    def test_sync_skips_writes_when_mkdir_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge = Path(tmp) / "knowledge"
            knowledge.mkdir()
            (knowledge / "bio.md").write_text("Daniel is an ML engineer.\n", encoding="utf-8")

            real_mkdir = Path.mkdir

            def mkdir_readonly(self, *args, **kwargs):
                if self.name == "versions" or self.name == ".audit":
                    raise OSError(30, "Read-only file system")
                return real_mkdir(self, *args, **kwargs)

            with patch.object(Path, "mkdir", mkdir_readonly):
                summary = sync_knowledge_audit(knowledge)

            self.assertIn("bio.md", summary["discovered"] + summary["unchanged"] + summary["updated"])


if __name__ == "__main__":
    unittest.main()
