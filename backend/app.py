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
from typing import Any, AsyncGenerator, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from .agent import GRAPH, AgentState, initial_state_from_user_message


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


class ChatRequest(BaseModel):
    """Request body for chat endpoints."""

    message: str
    user_id: str | None = None


class ChatResponse(BaseModel):
    """Non-streaming chat response (for convenience / testing)."""

    response: str
    leads: list[Dict[str, Any]] = []


@app.get("/healthz", tags=["meta"])
async def healthz() -> Dict[str, str]:
    """Simple health check for HF Spaces / uptime monitors."""
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Non-streaming chat endpoint.

    Useful for quick testing or environments where SSE is inconvenient.
    """
    state: AgentState = initial_state_from_user_message(request.message)
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
    """
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
    """
    state: AgentState = initial_state_from_user_message(request.message)
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

