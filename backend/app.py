"""
FastAPI backend for the Professional AI Representative.

Responsibilities:
- Expose a health check endpoint.
- Expose a streaming chat endpoint (SSE) backed by the LangGraph agent.
- (Later) Serve the compiled Next.js frontend as static files for HF Spaces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import re
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from .agent import (
    GRAPH,
    AgentState,
    initial_state_from_user_message,
    state_from_chat_history,
)  # noqa: E402


# ----- Environment bootstrap -----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)


# ----- Leads file (simple text log) -----
LEADS_DIR = PROJECT_ROOT / "leads"
LEADS_FILE = LEADS_DIR / "leads.txt"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


# ----- FastAPI app -----
app = FastAPI(title="Professional AI Representative Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    """Single message in a chat history passed from the frontend."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """
    Request body for chat endpoints.

    For backward compatibility:
      - Either `message` (single-turn) OR `messages` (multi-turn history) may be provided.
      - If both are provided, `messages` wins.
    """

    message: str | None = None
    messages: List[ChatMessage] | None = None
    user_id: str | None = None


class ChatResponse(BaseModel):
    """Non-streaming chat response (for convenience / testing)."""

    response: str
    leads: list[Dict[str, Any]] = []


def _ensure_leads_dir() -> None:
    """Create the leads directory if it does not exist."""
    LEADS_DIR.mkdir(parents=True, exist_ok=True)


def _maybe_extract_lead_from_request(request: ChatRequest) -> Optional[str]:
    """
    Heuristically extract a lead line (name + email) from the latest
    user-facing message in the request, if any.

    We intentionally keep this simple:
      - Look at the last `role == "user"` message (from `messages` if present,
        otherwise from `message`).
      - If it contains an email address, treat that as the lead's email.
      - Use the first non-empty line as a "name" guess.
    """

    content: Optional[str] = None

    if request.messages:
        # Find the last user message in the history.
        for m in reversed(request.messages):
            if m.role == "user" and m.content:
                content = m.content
                break
    elif request.message:
        content = request.message

    if not content:
        return None

    email_match = EMAIL_RE.search(content)
    if not email_match:
        return None

    email = email_match.group(0)
    # Use the first non-empty line as a crude "name" field.
    name = ""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and email not in stripped:
            name = stripped
            break

    timestamp = datetime.now(timezone.utc).isoformat()
    return f"{timestamp} | name={name or 'unknown'} | email={email}"


def _append_lead_line(line: str) -> None:
    """Append a single lead line to leads/leads.txt."""
    _ensure_leads_dir()
    with LEADS_FILE.open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


@app.get("/healthz", tags=["meta"])
async def healthz() -> Dict[str, str]:
    """Simple health check for HF Spaces / uptime monitors."""
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Non-streaming chat endpoint.

    Useful for quick testing or environments where SSE is inconvenient.

    If `messages` is provided, we treat it as the full chat history (including
    the latest user turn). Otherwise we fall back to a single-turn `message`.
    """
    if request.messages:
        history_payload = [m.model_dump() for m in request.messages]
        state: AgentState = state_from_chat_history(history_payload)
    elif request.message:
        state = initial_state_from_user_message(request.message)
    else:
        raise HTTPException(
            status_code=400,
            detail="Either `message` or `messages` must be provided.",
        )

    # Best-effort lead capture; failures here should not break chat.
    try:
        lead_line = _maybe_extract_lead_from_request(request)
        if lead_line:
            _append_lead_line(lead_line)
    except Exception:
        pass
    final_state: AgentState = GRAPH.invoke(state)

    ai_messages = [m for m in final_state["messages"] if isinstance(m, AIMessage)]
    if not ai_messages:
        raise HTTPException(status_code=500, detail="Agent did not return any response.")

    return ChatResponse(
        response=ai_messages[-1].content,
        leads=final_state.get("leads", []),
    )


async def _sse_event_stream(initial_state: AgentState) -> AsyncGenerator[str, None]:
    """
    Stream LangGraph events as Server-Sent Events (SSE).

    We focus on `on_chat_model_stream` events to emit token deltas.
    Errors are caught and forwarded as {"type": "error"} events so the
    frontend can display them instead of silently showing an empty bubble.
    """
    try:
        async for event in GRAPH.astream_events(initial_state, version="v2"):
            if event.get("event") == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if not chunk:
                    continue
                delta = chunk.content
                if not delta:
                    continue
                payload = {"type": "token", "delta": delta}
                yield f"data: {json.dumps(payload)}\n\n"
    except Exception as exc:
        error_payload = {"type": "error", "message": str(exc)}
        yield f"data: {json.dumps(error_payload)}\n\n"

    # Signal completion to the client
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/api/chat/stream", tags=["chat"])
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Streaming chat endpoint (SSE).

    The frontend should connect with EventSource or fetch/ReadableStream:
      - URL: POST /api/chat/stream
      - Response: text/event-stream
      - Events: {"type": "token", "delta": "..."} and a final {"type": "done"}.

    If `messages` is provided, we treat it as the full chat history (including
    the latest user turn). Otherwise we fall back to a single-turn `message`.
    """
    if request.messages:
        history_payload = [m.model_dump() for m in request.messages]
        state: AgentState = state_from_chat_history(history_payload)
    elif request.message:
        state = initial_state_from_user_message(request.message)
    else:
        raise HTTPException(
            status_code=400,
            detail="Either `message` or `messages` must be provided.",
        )

    # Best-effort lead capture when the user shares contact details.
    try:
        lead_line = _maybe_extract_lead_from_request(request)
        if lead_line:
            _append_lead_line(lead_line)
    except Exception:
        pass
    return StreamingResponse(
        _sse_event_stream(state),
        media_type="text/event-stream",
    )


# ----- Static frontend (Next.js build) -----
# For HF Spaces, we'll serve the compiled Next.js app (when present) as static files.
# This assumes a future build step that outputs to `frontend/out` (next export)
# or a similar directory. We guard on existence so local dev doesn't break.
FRONTEND_BUILD_DIR = PROJECT_ROOT / "frontend" / "out"
if FRONTEND_BUILD_DIR.is_dir():
    # Serve the static frontend at the root path.
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_BUILD_DIR, html=True),
        name="frontend",
    )

