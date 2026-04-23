"""
Load text from a designated directory (e.g. knowledge/) for the agent's context.
Supports .txt, .md, and .pdf files; their contents are merged into the system prompt.
"""
from pathlib import Path
from typing import Optional

from pypdf import PdfReader


# Default folder name relative to the project root
KNOWLEDGE_DIR_NAME = "knowledge"

# File extensions we support
TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
PDF_EXTENSIONS = {".pdf"}
ALL_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS


def get_project_dir() -> Path:
    """Project root (directory containing main.py)."""
    return Path(__file__).resolve().parent


def _read_pdf(path: Path) -> str:
    """Extract text from a PDF file."""
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts) if parts else ""


def load_knowledge_dir(knowledge_dir: Optional[Path] = None) -> str:
    """
    Read all .txt, .md, and .pdf files in the given directory and return their
    contents concatenated. If the directory doesn't exist or is empty, returns "".
    """
    if knowledge_dir is None:
        knowledge_dir = get_project_dir() / KNOWLEDGE_DIR_NAME

    if not knowledge_dir.is_dir():
        return ""

    result_parts = []
    for path in sorted(knowledge_dir.iterdir()):
        if not path.is_file():
            continue
        suf = path.suffix.lower()
        if suf not in ALL_EXTENSIONS:
            continue
        if path.name.upper() == "README.MD":
            continue
        try:
            if suf in PDF_EXTENSIONS:
                text = _read_pdf(path).strip()
            else:
                text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                result_parts.append(f"--- From {path.name} ---\n{text}")
        except OSError:
            continue
        except Exception:
            continue

    if not result_parts:
        return ""
    return "\n\n".join(result_parts)
