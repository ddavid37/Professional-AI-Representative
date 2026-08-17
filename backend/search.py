"""
Tavily web search for public / current facts the agent cannot answer from knowledge/.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)


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
