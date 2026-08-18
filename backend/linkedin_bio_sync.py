"""
LinkedIn About/Bio sync service.

Fetches bio via LinkedInBioProvider, compares against knowledge/LinkedIn_Bio.md
(About section only), and on meaningful change updates the file through the
existing knowledge audit + agent reload path.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .knowledge_audit import (
    append_audit_event,
    hash_normalized_text,
    patch_source_metadata,
    reload_knowledge_audit,
    utc_now,
)
from .linkedin_bio_provider import (
    LinkedInBioFetch,
    LinkedInBioProvider,
    LinkedInBioProviderError,
    build_linkedin_bio_provider,
)


LINKEDIN_BIO_IDENTITY = "LinkedIn_Bio.md"
ABOUT_START = "<!-- linkedin-about:start -->"
ABOUT_END = "<!-- linkedin-about:end -->"
LOCAL_MARKER = "<!-- local-only:"


@dataclass
class LinkedInBioSyncResult:
    ok: bool
    result: str
    trigger: str
    source: str = "linkedin"
    identity: str = LINKEDIN_BIO_IDENTITY
    previous_version: Optional[int] = None
    new_version: Optional[int] = None
    previous_hash: Optional[str] = None
    new_hash: Optional[str] = None
    change_summary: Optional[str] = None
    error_category: Optional[str] = None
    message: str = ""
    agent_reloaded: bool = False
    last_synced_at: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "result": self.result,
            "trigger": self.trigger,
            "source": self.source,
            "identity": self.identity,
            "previous_version": self.previous_version,
            "new_version": self.new_version,
            "previous_hash": self.previous_hash,
            "new_hash": self.new_hash,
            "change_summary": self.change_summary,
            "error_category": self.error_category,
            "message": self.message,
            "agent_reloaded": self.agent_reloaded,
            "last_synced_at": self.last_synced_at,
        }


def normalize_bio(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    collapsed: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank:
                collapsed.append("")
            blank = True
        else:
            collapsed.append(line)
            blank = False
    return "\n".join(collapsed).strip()


def split_linkedin_bio_file(text: str) -> tuple[str, str]:
    """Return (about_section, local_only_suffix)."""
    if ABOUT_START in text and ABOUT_END in text:
        _, rest = text.split(ABOUT_START, 1)
        about, after = rest.split(ABOUT_END, 1)
        return about.strip(), after.strip()
    if LOCAL_MARKER in text:
        about, after = text.split(LOCAL_MARKER, 1)
        return about.strip(), (LOCAL_MARKER + after).strip()
    return text.strip(), ""


def render_linkedin_bio_file(about: str, local_suffix: str) -> str:
    about = about.strip() + "\n"
    local = local_suffix.strip()
    parts = [ABOUT_START, about.rstrip(), ABOUT_END]
    if local:
        parts.extend(["", local])
    return "\n".join(parts) + "\n"


def change_summary(previous: str, current: str) -> str:
    old_words = normalize_bio(previous).split()
    new_words = normalize_bio(current).split()
    matcher = difflib.SequenceMatcher(a=old_words, b=new_words)
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert" and j2 > j1:
            snippet = " ".join(new_words[j1 : min(j2, j1 + 10)])
            parts.append(f"Added {snippet!r}" if snippet else "Added text")
        elif tag == "delete" and i2 > i1:
            snippet = " ".join(old_words[i1 : min(i2, i1 + 10)])
            parts.append(f"Removed {snippet!r}" if snippet else "Removed text")
        elif tag == "replace":
            parts.append("Updated professional summary")
    if not parts:
        return "Updated professional summary"
    return "; ".join(parts[:3])[:240]


def _bio_hash(text: str) -> str:
    return hash_normalized_text(normalize_bio(text))


def _fail(
    knowledge_dir: Path,
    trigger: str,
    category: str,
    message: str,
    source: str = "linkedin",
) -> LinkedInBioSyncResult:
    timestamp = utc_now()
    append_audit_event(
        knowledge_dir,
        "linkedin_bio_sync_failed",
        {
            "source": source,
            "trigger": trigger,
            "error_category": category,
            "message": message,
            "identity": LINKEDIN_BIO_IDENTITY,
        },
    )
    return LinkedInBioSyncResult(
        ok=False,
        result="failed",
        trigger=trigger,
        source=source,
        error_category=category,
        message=message,
        last_synced_at=timestamp,
    )


def sync_linkedin_bio(
    knowledge_dir: Path,
    *,
    trigger: str = "manual",
    provider: Optional[LinkedInBioProvider] = None,
    reload_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    project_root: Optional[Path] = None,
) -> LinkedInBioSyncResult:
    """
    Single sync implementation used by the developer panel and the weekly job.
    Never writes on fetch failure, empty bio, or formatting-only differences.
    """
    source = "linkedin"
    append_audit_event(
        knowledge_dir,
        "linkedin_bio_sync_started",
        {"source": source, "trigger": trigger, "identity": LINKEDIN_BIO_IDENTITY},
    )

    path = knowledge_dir / LINKEDIN_BIO_IDENTITY
    if not path.is_file():
        return _fail(knowledge_dir, trigger, "knowledge_missing", "LinkedIn_Bio.md is not present.")

    try:
        current_text = path.read_text(encoding="utf-8")
    except OSError:
        return _fail(knowledge_dir, trigger, "knowledge_unreadable", "Could not read LinkedIn_Bio.md.")

    about, local_suffix = split_linkedin_bio_file(current_text)
    previous_hash = _bio_hash(about)

    try:
        if provider is None:
            provider = build_linkedin_bio_provider(project_root=project_root or knowledge_dir.parent)
        fetch: LinkedInBioFetch = provider.get_bio()
    except LinkedInBioProviderError as exc:
        return _fail(knowledge_dir, trigger, exc.category, exc.message)
    except Exception:
        return _fail(knowledge_dir, trigger, "provider_error", "Bio provider failed unexpectedly.")

    fetched_normalized = normalize_bio(fetch.bio)
    fetched_hash = _bio_hash(fetch.bio)
    append_audit_event(
        knowledge_dir,
        "linkedin_bio_fetched",
        {
            "source": fetch.source,
            "trigger": trigger,
            "success": True,
            "content_hash": fetched_hash,
            "identity": LINKEDIN_BIO_IDENTITY,
        },
    )

    if not fetched_normalized:
        return _fail(knowledge_dir, trigger, "empty_bio", "Fetched About/Bio was empty; kept current knowledge.")

    current_normalized = normalize_bio(about)
    timestamp = utc_now()

    if fetched_normalized == current_normalized:
        patch_source_metadata(
            knowledge_dir,
            LINKEDIN_BIO_IDENTITY,
            {
                "id": "linkedin_bio",
                "type": "linkedin",
                "path": f"knowledge/{LINKEDIN_BIO_IDENTITY}",
                "last_synced_at": timestamp,
            },
        )
        append_audit_event(
            knowledge_dir,
            "linkedin_bio_sync_unchanged",
            {
                "source": source,
                "trigger": trigger,
                "result": "unchanged",
                "content_hash": previous_hash,
                "identity": LINKEDIN_BIO_IDENTITY,
            },
        )
        append_audit_event(
            knowledge_dir,
            "linkedin_bio_sync_completed",
            {
                "source": source,
                "trigger": trigger,
                "result": "unchanged",
                "identity": LINKEDIN_BIO_IDENTITY,
            },
        )
        state_version = _current_version(knowledge_dir)
        return LinkedInBioSyncResult(
            ok=True,
            result="unchanged",
            trigger=trigger,
            previous_version=state_version,
            new_version=state_version,
            previous_hash=previous_hash,
            new_hash=previous_hash,
            message="No changes detected.",
            last_synced_at=timestamp,
        )

    rendered = render_linkedin_bio_file(fetch.bio.strip(), local_suffix)
    try:
        path.write_text(rendered, encoding="utf-8")
    except OSError:
        return _fail(
            knowledge_dir,
            trigger,
            "knowledge_not_writable",
            "Could not write LinkedIn_Bio.md (filesystem may be read-only). Current knowledge kept.",
        )

    summary = change_summary(about, fetch.bio)
    previous_version = _current_version(knowledge_dir) or 1

    try:
        audit_summary = reload_knowledge_audit(knowledge_dir)
    except Exception:
        append_audit_event(
            knowledge_dir,
            "linkedin_bio_sync_failed",
            {
                "source": source,
                "trigger": trigger,
                "error_category": "audit_failed",
                "message": "Bio file was written but knowledge audit failed.",
                "identity": LINKEDIN_BIO_IDENTITY,
            },
        )
        return LinkedInBioSyncResult(
            ok=False,
            result="failed",
            trigger=trigger,
            previous_version=previous_version,
            error_category="audit_failed",
            message="Bio file was written but knowledge audit failed.",
        )

    new_version = _current_version(knowledge_dir) or (previous_version + 1)
    new_file_hash = "sha256:" + hashlib.sha256(
        normalize_bio(path.read_text(encoding="utf-8")).encode("utf-8")
    ).hexdigest()

    append_audit_event(
        knowledge_dir,
        "linkedin_bio_changed",
        {
            "source": source,
            "trigger": trigger,
            "previous_hash": previous_hash,
            "new_hash": fetched_hash,
            "previous_version": previous_version,
            "new_version": new_version,
            "change_summary": summary,
            "identity": LINKEDIN_BIO_IDENTITY,
        },
    )
    append_audit_event(
        knowledge_dir,
        "knowledge_updated",
        {
            "source": "linkedin_bio",
            "identity": LINKEDIN_BIO_IDENTITY,
            "previous_version": previous_version,
            "new_version": new_version,
            "change_summary": summary,
            "content_hash": fetched_hash,
        },
    )

    agent_reloaded = False
    reload_status = "skipped"
    if reload_fn is not None:
        try:
            reload_result = reload_fn() or {}
            reload_status = reload_result.get("status", "ok")
            agent_reloaded = reload_status in {"ok", "reloaded"}
        except Exception:
            append_audit_event(
                knowledge_dir,
                "linkedin_bio_sync_failed",
                {
                    "source": source,
                    "trigger": trigger,
                    "error_category": "agent_reload_failed",
                    "message": "Knowledge updated but agent reload failed.",
                    "identity": LINKEDIN_BIO_IDENTITY,
                    "new_version": new_version,
                },
            )
            return LinkedInBioSyncResult(
                ok=False,
                result="updated_reload_failed",
                trigger=trigger,
                previous_version=previous_version,
                new_version=new_version,
                previous_hash=previous_hash,
                new_hash=fetched_hash,
                change_summary=summary,
                error_category="agent_reload_failed",
                message="Knowledge updated but agent reload failed.",
                agent_reloaded=False,
                last_synced_at=timestamp,
            )

    if agent_reloaded or reload_fn is None:
        append_audit_event(
            knowledge_dir,
            "knowledge_reload_completed",
            {
                "identity": LINKEDIN_BIO_IDENTITY,
                "version": new_version,
                "reload_status": reload_status if reload_fn is not None else "audit_only",
                "source": source,
            },
        )

    patch_source_metadata(
        knowledge_dir,
        LINKEDIN_BIO_IDENTITY,
        {
            "id": "linkedin_bio",
            "type": "linkedin",
            "path": f"knowledge/{LINKEDIN_BIO_IDENTITY}",
            "last_synced_at": timestamp,
            "last_changed_at": timestamp,
        },
    )
    append_audit_event(
        knowledge_dir,
        "linkedin_bio_sync_completed",
        {
            "source": source,
            "trigger": trigger,
            "result": "updated",
            "new_version": new_version,
            "identity": LINKEDIN_BIO_IDENTITY,
            "audit_summary": {
                "updated": (audit_summary or {}).get("updated"),
            },
        },
    )
    return LinkedInBioSyncResult(
        ok=True,
        result="updated",
        trigger=trigger,
        previous_version=previous_version,
        new_version=new_version,
        previous_hash=previous_hash,
        new_hash=fetched_hash,
        change_summary=summary,
        message="Bio updated.",
        agent_reloaded=agent_reloaded,
        last_synced_at=timestamp,
        extra={"file_hash": new_file_hash},
    )


def _current_version(knowledge_dir: Path) -> Optional[int]:
    state_path = knowledge_dir / ".audit" / "state.json"
    if not state_path.is_file():
        return None
    try:
        import json

        state = json.loads(state_path.read_text(encoding="utf-8"))
        source = (state.get("sources") or {}).get(LINKEDIN_BIO_IDENTITY) or {}
        version = source.get("version")
        return int(version) if version is not None else None
    except (OSError, ValueError, TypeError):
        return None


def linkedin_bio_status(knowledge_dir: Path) -> Dict[str, Any]:
    import json

    path = knowledge_dir / LINKEDIN_BIO_IDENTITY
    state_path = knowledge_dir / ".audit" / "state.json"
    source: Dict[str, Any] = {}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            source = (state.get("sources") or {}).get(LINKEDIN_BIO_IDENTITY) or {}
        except (OSError, json.JSONDecodeError):
            source = {}

    about = ""
    if path.is_file():
        try:
            about, _ = split_linkedin_bio_file(path.read_text(encoding="utf-8"))
        except OSError:
            about = ""

    return {
        "id": "linkedin_bio",
        "type": "linkedin",
        "path": f"knowledge/{LINKEDIN_BIO_IDENTITY}",
        "identity": LINKEDIN_BIO_IDENTITY,
        "status": source.get("status") or ("current" if path.is_file() else "missing"),
        "version": source.get("version"),
        "content_hash": source.get("content_hash") or (_bio_hash(about) if about else None),
        "last_synced_at": source.get("last_synced_at"),
        "last_changed_at": source.get("last_changed_at") or source.get("audited_at") or source.get("updated_at"),
        "profile_url": (os.getenv("LINKEDIN_PROFILE_URL") or "").strip() or None,
        "source_mode": (os.getenv("LINKEDIN_BIO_SOURCE") or "").strip() or None,
    }
