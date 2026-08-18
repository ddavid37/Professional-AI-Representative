"""
Tavily web search for public / current facts the agent cannot answer from knowledge/.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from .handoff import EMAIL_RE

# Do not search Daniel's private / unknown personal facts.
_PERSONAL_SKIP = re.compile(
    r"\b(sibling|salary|family|mom|mother|dad|father|girlfriend|wife|"
    r"private|phone|address|offer)\b",
    re.IGNORECASE,
)

# Public / current topics the model must not answer from training memory.
_WEB_HINTS = re.compile(
    r"\b("
    r"weather|forecast|stock|nasdaq|news|"
    r"score|won|winner|mvp|world\s*cup|worldcup|super\s*bowl|"
    r"election|president|prime\s+minister|"
    r"current|latest|today|tonight|this\s+week|this\s+year|"
    r"who\s+won|who\s+is\s+the|price\s+of"
    r")\b",
    re.IGNORECASE,
)


def should_search_web(text: str) -> bool:
    """True when this user turn is a public/current question, not a Daniel-personal one."""
    compact = " ".join(text.split())
    if not compact or EMAIL_RE.search(compact):
        return False
    if _PERSONAL_SKIP.search(compact):
        return False
    return bool(_WEB_HINTS.search(compact))


def format_search_context(result: Dict[str, Any]) -> str:
    """Turn a Tavily payload into text the agent must answer from."""
    if result.get("status") != "ok":
        message = result.get("message") or "unknown error"
        return (
            "[Internal — live web search failed]\n"
            f"{message}\n"
            "Do NOT answer this question from memory or training data. "
            "Tell the visitor you could not retrieve live results."
        )

    lines: List[str] = [
        "[Internal — live Tavily results for this turn]",
        "Answer ONLY from these results. Cite source URLs. "
        "Do not use training memory for current events, sports, weather, or news.",
    ]
    answer = (result.get("answer") or "").strip()
    if answer:
        lines.append(f"Summary: {answer}")
    for item in result.get("results") or []:
        title = item.get("title") or "Source"
        url = item.get("url") or ""
        content = item.get("content") or ""
        lines.append(f"- {title} ({url}): {content}")
    if len(lines) <= 2:
        lines.append("No web results found. Do not guess.")
    return "\n".join(lines)


def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Run a Tavily search and return a compact payload the LLM can cite.
    """
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return {
            "status": "error",
            "message": "TAVILY_API_KEY is not set (local .env or Vercel env vars on the API project).",
        }

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=True,
        )
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    results: List[Dict[str, str]] = []
    for item in response.get("results") or []:
        results.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "content": (item.get("content") or "")[:500],
            }
        )

    return {
        "status": "ok",
        "answer": response.get("answer") or "",
        "results": results,
    }
