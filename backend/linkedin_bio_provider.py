"""
LinkedIn About/Bio provider.

Responsibility: obtain the current About/Bio text from an authorized source.

Does not scrape linkedin.com. LinkedIn has no public, authorized About API for
this project, so production must plug in an export you control (file or URL).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol
from urllib.parse import urlparse

import httpx


BLOCKED_LINKEDIN_HOST_SUFFIXES = (
    "linkedin.com",
    "linkedin.cn",
    "lnkd.in",
)


class LinkedInBioProviderError(Exception):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category
        self.message = message


@dataclass(frozen=True)
class LinkedInBioFetch:
    bio: str
    source: str
    fetched_at: str


class LinkedInBioProvider(Protocol):
    def get_bio(self) -> LinkedInBioFetch:
        ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_blocked_linkedin_host(host: Optional[str]) -> bool:
    if not host:
        return False
    host = host.lower().rstrip(".")
    return any(host == suffix or host.endswith("." + suffix) for suffix in BLOCKED_LINKEDIN_HOST_SUFFIXES)


class MockLinkedInBioProvider:
    def __init__(self, bio: str, source: str = "mock"):
        self._bio = bio
        self._source = source

    def get_bio(self) -> LinkedInBioFetch:
        return LinkedInBioFetch(bio=self._bio, source=self._source, fetched_at=_utc_now())


class FileLinkedInBioProvider:
    """Read About/Bio text from a local export file you control."""

    def __init__(self, path: Path):
        self._path = path

    def get_bio(self) -> LinkedInBioFetch:
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            raise LinkedInBioProviderError("file_unreadable", f"Could not read bio export file: {exc}") from exc
        return LinkedInBioFetch(bio=text, source=f"file:{self._path.name}", fetched_at=_utc_now())


class UrlLinkedInBioProvider:
    """
    Fetch About/Bio from a URL you control (plain text or JSON {\"bio\": \"...\"}).

    Refuses LinkedIn hosts — we do not scrape LinkedIn pages.
    """

    def __init__(self, url: str, timeout: float = 15.0):
        self._url = url.strip()
        self._timeout = timeout

    def get_bio(self) -> LinkedInBioFetch:
        parsed = urlparse(self._url)
        if parsed.scheme not in {"http", "https"}:
            raise LinkedInBioProviderError("invalid_url", "Export URL must be http or https.")
        if _is_blocked_linkedin_host(parsed.hostname):
            raise LinkedInBioProviderError(
                "linkedin_host_blocked",
                "Refusing to fetch LinkedIn pages. Use an authorized export URL you control.",
            )
        try:
            response = httpx.get(self._url, timeout=self._timeout, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LinkedInBioProviderError("export_http_error", "Authorized export URL request failed.") from exc

        content_type = (response.headers.get("content-type") or "").lower()
        bio = ""
        if "json" in content_type:
            try:
                payload = response.json()
            except ValueError as exc:
                raise LinkedInBioProviderError("malformed_export", "Export JSON was not valid.") from exc
            if not isinstance(payload, dict) or "bio" not in payload:
                raise LinkedInBioProviderError("malformed_export", "Export JSON must contain a bio field.")
            bio = str(payload.get("bio") or "")
        else:
            bio = response.text

        return LinkedInBioFetch(bio=bio, source="authorized_export_url", fetched_at=_utc_now())


def build_linkedin_bio_provider(
    *,
    source: Optional[str] = None,
    file_path: Optional[str] = None,
    export_url: Optional[str] = None,
    mock_bio: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> LinkedInBioProvider:
    mode = (source or os.getenv("LINKEDIN_BIO_SOURCE") or "").strip().lower()
    if not mode:
        raise LinkedInBioProviderError(
            "provider_not_configured",
            "LINKEDIN_BIO_SOURCE is not set. Use file, url, or mock — LinkedIn pages are not scraped.",
        )

    if mode == "mock":
        bio = mock_bio if mock_bio is not None else os.getenv("LINKEDIN_BIO_MOCK", "")
        return MockLinkedInBioProvider(bio=bio, source="mock")

    if mode == "file":
        raw_path = file_path or os.getenv("LINKEDIN_BIO_FILE") or ""
        if not raw_path.strip():
            raise LinkedInBioProviderError("provider_not_configured", "LINKEDIN_BIO_FILE is required when source=file.")
        path = Path(raw_path)
        if not path.is_absolute() and project_root is not None:
            path = project_root / path
        return FileLinkedInBioProvider(path)

    if mode == "url":
        url = export_url or os.getenv("LINKEDIN_BIO_EXPORT_URL") or ""
        if not url.strip():
            raise LinkedInBioProviderError(
                "provider_not_configured",
                "LINKEDIN_BIO_EXPORT_URL is required when source=url.",
            )
        return UrlLinkedInBioProvider(url)

    raise LinkedInBioProviderError(
        "provider_not_configured",
        "LINKEDIN_BIO_SOURCE must be file, url, or mock.",
    )
