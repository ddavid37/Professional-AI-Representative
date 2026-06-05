"""
FastAPI backend for the Professional AI Representative.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from .agent import (
    GRAPH,
    initial_state_from_user_message,
    state_from_chat_history,
)
from .whatsapp import send_test_message


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

app = FastAPI(title="Professional AI Representative Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str | None = None
    messages: List[ChatMessage] | None = None
    user_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    leads: list[Dict[str, Any]] = []


def _last_ai_text(messages: List[Any]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


async def _sse_event_stream(initial_state: Dict[str, Any]) -> AsyncGenerator[str, None]:
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
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.get("/healthz", tags=["meta"])
async def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/test/whatsapp", tags=["meta"])
async def test_whatsapp() -> Dict[str, Any]:
    result = send_test_message()
    if result.get("status") != "sent":
        raise HTTPException(status_code=502, detail=result.get("message", "WhatsApp send failed"))
    return result


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    if request.messages:
        state = state_from_chat_history([m.model_dump() for m in request.messages])
    elif request.message:
        state = initial_state_from_user_message(request.message)
    else:
        raise HTTPException(status_code=400, detail="Either `message` or `messages` is required.")

    final_state = GRAPH.invoke(state)
    response = _last_ai_text(final_state["messages"])
    if not response:
        raise HTTPException(status_code=500, detail="Agent did not return a response.")
    return ChatResponse(response=response)


@app.post("/api/chat/stream", tags=["chat"])
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    if request.messages:
        state = state_from_chat_history([m.model_dump() for m in request.messages])
    elif request.message:
        state = initial_state_from_user_message(request.message)
    else:
        raise HTTPException(status_code=400, detail="Either `message` or `messages` is required.")

    return StreamingResponse(_sse_event_stream(state), media_type="text/event-stream")


FRONTEND_BUILD_DIR = PROJECT_ROOT / "frontend" / "out"
if FRONTEND_BUILD_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_BUILD_DIR, html=True), name="frontend")
