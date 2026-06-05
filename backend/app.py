"""
FastAPI backend for the Professional AI Representative.

Responsibilities:
- Expose a health check endpoint.
- Expose a streaming chat endpoint (SSE) backed by the LangGraph agent.
- (Later) Serve the compiled Next.js frontend as static files for HF Spaces.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, SystemMessage
from pydantic import BaseModel

from .agent import (
    GRAPH,
    AgentState,
    initial_state_from_user_message,
    state_from_chat_history,
)  # noqa: E402
from .leads import conversation_context_note, resolve_lead_turn
from .whatsapp import send_test_message


logger = logging.getLogger(__name__)


# ----- Environment bootstrap -----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)


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


def _conversation_messages(request: ChatRequest) -> List[ChatMessage]:
    if request.messages:
        return request.messages
    if request.message:
        return [ChatMessage(role="user", content=request.message)]
    return []


def _apply_context_note(state: AgentState, messages: List[ChatMessage]) -> AgentState:
    """Fallback context injection when we still need the LLM (non-lead turns)."""
    note = conversation_context_note(messages)
    if note is None:
        return state
    return {**state, "messages": [*state["messages"], SystemMessage(content=note)]}


async def _sse_direct_reply(text: str) -> AsyncGenerator[str, None]:
    """Emit a full reply as one SSE payload (no LLM call)."""
    payload = {"type": "token", "delta": text}
    yield f"data: {json.dumps(payload)}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


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

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.get("/healthz", tags=["meta"])
async def healthz() -> Dict[str, str]:
    """Simple health check for HF Spaces / uptime monitors."""
    return {"status": "ok"}


@app.post("/api/test/whatsapp", tags=["meta"])
async def test_whatsapp() -> Dict[str, Any]:
    """
    Send a test WhatsApp message to verify Twilio sandbox configuration.
    Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and sandbox join on your phone.
    """
    result = send_test_message()
    if result.get("status") != "sent":
        raise HTTPException(status_code=502, detail=result.get("message", "WhatsApp send failed"))
    return result


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Non-streaming chat endpoint.

    Useful for quick testing or environments where SSE is inconvenient.
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

    messages = _conversation_messages(request)
    try:
        direct_reply, _ = resolve_lead_turn(messages)
    except Exception:
        logger.exception("Lead capture failed")
        direct_reply = None

    if direct_reply:
        return ChatResponse(response=direct_reply, leads=[])

    state = _apply_context_note(state, messages)
    final_state: AgentState = GRAPH.invoke(state)

    ai_messages = [m for m in final_state["messages"] if isinstance(m, AIMessage)]
    if not ai_messages:
        raise HTTPException(status_code=500, detail="Agent did not return any response.")

    return ChatResponse(
        response=ai_messages[-1].content,
        leads=final_state.get("leads", []),
    )


@app.post("/api/chat/stream", tags=["chat"])
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    Streaming chat endpoint (SSE).

    Lead capture turns return a fixed confirmation without calling the LLM,
    so the agent cannot ignore instructions or loop on contact collection.
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

    messages = _conversation_messages(request)
    try:
        direct_reply, _ = resolve_lead_turn(messages)
    except Exception:
        logger.exception("Lead capture failed")
        direct_reply = None

    if direct_reply:
        return StreamingResponse(
            _sse_direct_reply(direct_reply),
            media_type="text/event-stream",
        )

    state = _apply_context_note(state, messages)
    return StreamingResponse(
        _sse_event_stream(state),
        media_type="text/event-stream",
    )


# ----- Static frontend (Next.js build) -----
FRONTEND_BUILD_DIR = PROJECT_ROOT / "frontend" / "out"
if FRONTEND_BUILD_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_BUILD_DIR, html=True),
        name="frontend",
    )
