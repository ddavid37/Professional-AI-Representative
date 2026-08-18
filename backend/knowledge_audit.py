"""
Knowledge directory audit: content hashes, versioning, and append-only events.

Runs on agent startup when knowledge is loaded. Does not log secrets or full file bodies.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from custom.knowledge_loader import (
    ALL_EXTENSIONS,
    KNOWLEDGE_DIR_NAME,
    PDF_EXTENSIONS,
    _read_pdf,
    get_project_dir,
)


AUDIT_DIR_NAME = ".audit"
EVENTS_FILE = "events.jsonl"
STATE_FILE = "state.json"
VERSIONS_DIR_NAME = "versions"

SKIP_NAMES = {"README.MD"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_now() -> str:
    return utc_now()


def hash_normalized_text(text: str) -> str:
    digest = hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def append_audit_event(knowledge_dir: Path, event_type: str, payload: Dict[str, Any]) -> None:
    _append_event(knowledge_dir, event_type, payload)


def patch_source_metadata(knowledge_dir: Path, identity: str, extra: Dict[str, Any]) -> None:
    state = _load_state(knowledge_dir)
    sources = dict(state.get("sources") or {})
    current = dict(sources.get(identity) or {})
    current.update(extra)
    sources[identity] = current
    state["sources"] = sources
    _save_state(knowledge_dir, state)


def _audit_root(knowledge_dir: Path) -> Path:
    return knowledge_dir / AUDIT_DIR_NAME


def _events_path(knowledge_dir: Path) -> Path:
    return _audit_root(knowledge_dir) / EVENTS_FILE


def _state_path(knowledge_dir: Path) -> Path:
    return _audit_root(knowledge_dir) / STATE_FILE


def _versions_dir(knowledge_dir: Path) -> Path:
    return _audit_root(knowledge_dir) / VERSIONS_DIR_NAME


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def _read_source_text(path: Path) -> str:
    if path.suffix.lower() in PDF_EXTENSIONS:
        return _read_pdf(path).strip()
    return path.read_text(encoding="utf-8", errors="replace")


def _content_hash(path: Path) -> str:
    if path.suffix.lower() in PDF_EXTENSIONS:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        normalized = _normalize_text(_read_source_text(path))
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _git_head(project_dir: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        sha = result.stdout.strip()
        return sha or None
    except (OSError, subprocess.SubprocessError):
        return None


def _git_log_field(project_dir: Path, rel_path: str, revision: str, field: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "log", revision, "-1", f"--format={field}", "--", rel_path],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        value = result.stdout.strip()
        return value or None
    except (OSError, subprocess.SubprocessError):
        return None


def _file_provenance(path: Path, project_dir: Path, knowledge_dir: Path) -> Dict[str, Any]:
    rel_path = path.relative_to(project_dir).as_posix()
    file_modified_at: Optional[str] = None
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        file_modified_at = mtime.isoformat()
    except OSError:
        pass

    git_added_at = _git_log_field(project_dir, rel_path, "--diff-filter=A", "%aI")
    git_last_committed_at = _git_log_field(project_dir, rel_path, "-1", "%aI")
    git_last_commit = _git_log_field(project_dir, rel_path, "-1", "%H")

    return {
        "file_modified_at": file_modified_at,
        "git_added_at": git_added_at,
        "git_last_committed_at": git_last_committed_at,
        "git_last_commit": git_last_commit,
    }


def _enrich_source_record(record: Dict[str, Any], path: Path, project_dir: Path, knowledge_dir: Path) -> Dict[str, Any]:
    return {**record, **_file_provenance(path, project_dir, knowledge_dir)}


def _load_state(knowledge_dir: Path) -> Dict[str, Any]:
    path = _state_path(knowledge_dir)
    if not path.is_file():
        return {"sources": {}, "last_sync": None, "git_commit": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sources": {}, "last_sync": None, "git_commit": None}


def _try_mkdir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def _save_state(knowledge_dir: Path, state: Dict[str, Any]) -> None:
    root = _audit_root(knowledge_dir)
    if not _try_mkdir(root):
        return
    try:
        _state_path(knowledge_dir).write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _append_event(knowledge_dir: Path, event_type: str, payload: Dict[str, Any]) -> None:
    root = _audit_root(knowledge_dir)
    if not _try_mkdir(root):
        return
    record = {
        "type": event_type,
        "timestamp": _utc_now(),
        **payload,
    }
    try:
        with _events_path(knowledge_dir).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        return


def _version_snapshot_path(knowledge_dir: Path, identity: str, version: int, suffix: str) -> Path:
    safe_name = identity.replace("/", "_")
    return _versions_dir(knowledge_dir) / f"{safe_name}.v{version}{suffix}"


def _write_version_snapshot(knowledge_dir: Path, identity: str, version: int, path: Path) -> None:
    versions = _versions_dir(knowledge_dir)
    if not _try_mkdir(versions):
        return
    dest = _version_snapshot_path(knowledge_dir, identity, version, path.suffix.lower() or ".bin")
    try:
        dest.write_bytes(path.read_bytes())
    except OSError:
        return


def _iter_knowledge_files(knowledge_dir: Path) -> List[Path]:
    if not knowledge_dir.is_dir():
        return []
    files: List[Path] = []
    for path in sorted(knowledge_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.name.upper() in SKIP_NAMES:
            continue
        if path.suffix.lower() not in ALL_EXTENSIONS:
            continue
        files.append(path)
    return files


def sync_knowledge_audit(knowledge_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Compare knowledge files to persisted state, archive prior versions on change,
    append audit events, and update state. Safe to call on every agent startup.
    """
    if knowledge_dir is None:
        knowledge_dir = get_project_dir() / KNOWLEDGE_DIR_NAME

    project_dir = knowledge_dir.parent
    git_commit = _git_head(project_dir)
    state = _load_state(knowledge_dir)
    prev_sources: Dict[str, Any] = dict(state.get("sources") or {})

    current_files = _iter_knowledge_files(knowledge_dir)
    current_identities = {p.name for p in current_files}
    summary: Dict[str, Any] = {
        "discovered": [],
        "updated": [],
        "stale": [],
        "unchanged": [],
    }

    new_sources: Dict[str, Any] = {}

    for path in current_files:
        identity = path.name
        content_hash = _content_hash(path)
        prev = prev_sources.get(identity)
        byte_size = path.stat().st_size

        if prev is None:
            version = 1
            new_sources[identity] = _enrich_source_record(
                {
                    "identity": identity,
                    "content_hash": content_hash,
                    "version": version,
                    "audited_at": _utc_now(),
                    "byte_size": byte_size,
                    "status": "current",
                },
                path,
                project_dir,
                knowledge_dir,
            )
            summary["discovered"].append(identity)
            _append_event(
                knowledge_dir,
                "knowledge_discovered",
                {
                    "identity": identity,
                    "content_hash": content_hash,
                    "version": version,
                    "byte_size": byte_size,
                    "git_commit": git_commit,
                },
            )
            _write_version_snapshot(knowledge_dir, identity, version, path)
            continue

        if prev.get("content_hash") == content_hash:
            record = {**prev, "status": "current", "byte_size": byte_size}
            if "audited_at" not in record and record.get("updated_at"):
                record["audited_at"] = record["updated_at"]
            new_sources[identity] = _enrich_source_record(record, path, project_dir, knowledge_dir)
            summary["unchanged"].append(identity)
            version = int(prev.get("version") or 1)
            snap = _version_snapshot_path(
                knowledge_dir, identity, version, path.suffix.lower() or ".bin"
            )
            if not snap.is_file():
                _write_version_snapshot(knowledge_dir, identity, version, path)
            continue

        old_version = int(prev.get("version") or 1)
        old_snapshot = _version_snapshot_path(
            knowledge_dir, identity, old_version, path.suffix.lower() or ".bin"
        )
        archive_available = old_snapshot.is_file()

        version = old_version + 1
        new_sources[identity] = _enrich_source_record(
            {
                "identity": identity,
                "content_hash": content_hash,
                "version": version,
                "audited_at": _utc_now(),
                "byte_size": byte_size,
                "status": "current",
                "previous_hash": prev.get("content_hash"),
            },
            path,
            project_dir,
            knowledge_dir,
        )
        summary["updated"].append(identity)
        _append_event(
            knowledge_dir,
            "knowledge_version_created",
            {
                "identity": identity,
                "content_hash": content_hash,
                "previous_hash": prev.get("content_hash"),
                "version": version,
                "previous_version": old_version,
                "byte_size": byte_size,
                "previous_snapshot_available": archive_available,
                "git_commit": git_commit,
            },
        )
        _append_event(
            knowledge_dir,
            "knowledge_updated",
            {
                "identity": identity,
                "content_hash": content_hash,
                "version": version,
                "git_commit": git_commit,
            },
        )
        _write_version_snapshot(knowledge_dir, identity, version, path)
        continue

    for identity, prev in prev_sources.items():
        if identity not in current_identities and prev.get("status") != "stale":
            stale_record = {**prev, "status": "stale", "stale_at": _utc_now()}
            new_sources[identity] = stale_record
            summary["stale"].append(identity)
            _append_event(
                knowledge_dir,
                "knowledge_stale",
                {
                    "identity": identity,
                    "last_hash": prev.get("content_hash"),
                    "last_version": prev.get("version"),
                    "git_commit": git_commit,
                },
            )

    state["sources"] = new_sources
    state["last_sync"] = _utc_now()
    state["git_commit"] = git_commit
    _save_state(knowledge_dir, state)

    _append_event(
        knowledge_dir,
        "knowledge_loaded",
        {
            "file_count": len(current_files),
            "identities": [p.name for p in current_files],
            "discovered": summary["discovered"],
            "updated": summary["updated"],
            "stale": summary["stale"],
            "git_commit": git_commit,
        },
    )

    return summary


def reload_knowledge_audit(knowledge_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Re-run audit sync and record an explicit reload event."""
    if knowledge_dir is None:
        knowledge_dir = get_project_dir() / KNOWLEDGE_DIR_NAME
    summary = sync_knowledge_audit(knowledge_dir)
    _append_event(
        knowledge_dir,
        "knowledge_reload",
        {"git_commit": _git_head(knowledge_dir.parent), "summary": summary},
    )
    return summary


def read_recent_events(knowledge_dir: Optional[Path] = None, limit: int = 20) -> List[Dict[str, Any]]:
    events = read_all_events(knowledge_dir)
    if limit <= 0:
        return events
    return events[-limit:]


def read_all_events(knowledge_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    if knowledge_dir is None:
        knowledge_dir = get_project_dir() / KNOWLEDGE_DIR_NAME
    path = _events_path(knowledge_dir)
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
