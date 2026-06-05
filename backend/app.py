"""
FastAPI backend for the Professional AI Representative.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

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
from .whatsapp import send_lead_notification, send_test_message


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

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
    """Return the last assistant message that has visible text content."""
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = msg.content
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("text")]
            joined = "".join(parts).strip()
            if joined:
                return joined
    return ""


def _user_turns(messages: List[ChatMessage]) -> List[str]:
    return [m.content.strip() for m in messages if m.role == "user" and m.content.strip()]


def _maybe_whatsapp_reply(messages: List[ChatMessage]) -> Optional[str]:
    """
    Simple rule: if the latest user message has an email and an earlier user
    message has their question, send WhatsApp immediately. The LLM handles
    everything else; this only covers the reliable handoff case.
    """
    turns = _user_turns(messages)
    if len(turns) < 2:
        return None

    latest = turns[-1]
    email_match = EMAIL_RE.search(latest)
    if not email_match:
        return None

    email = email_match.group(0)
    name = latest[: email_match.start()].strip(" ,.-") or "Guest"

    question: Optional[str] = None
    for turn in reversed(turns[:-1]):
        if EMAIL_RE.search(turn):
            continue
        if len(turn) > 10:
            question = turn
            break
    if not question:
        return None

    result = send_lead_notification(name=name, email=email, question=question)
    if result.get("status") == "sent":
        return (
            f"Thank you, {name}! Daniel was notified on WhatsApp.\n\n"
            f'I passed along your question: "{question}"\n'
            f"He'll follow up at {email}."
        )
    return (
        f"Thank you, {name}. I have your question on file: \"{question}\". "
        f"WhatsApp could not be sent ({result.get('message', 'unknown error')})."
    )


async def _sse_direct_reply(text: str) -> AsyncGenerator[str, None]:
    yield f"data: {json.dumps({'type': 'token', 'delta': text})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def _sse_event_stream(initial_state: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """Run the full agent (including tool calls), then send the final reply."""
    try:
        final_state = await GRAPH.ainvoke(initial_state)
        text = _last_ai_text(final_state["messages"])
        if text:
            payload = {"type": "token", "delta": text}
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
        direct = _maybe_whatsapp_reply(request.messages)
    elif request.message:
        state = initial_state_from_user_message(request.message)
        direct = None
    else:
        raise HTTPException(status_code=400, detail="Either `message` or `messages` is required.")

    if direct:
        return ChatResponse(response=direct)

    final_state = GRAPH.invoke(state)
    response = _last_ai_text(final_state["messages"])
    if not response:
        raise HTTPException(status_code=500, detail="Agent did not return a response.")
    return ChatResponse(response=response)


@app.post("/api/chat/stream", tags=["chat"])
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    if request.messages:
        state = state_from_chat_history([m.model_dump() for m in request.messages])
        direct = _maybe_whatsapp_reply(request.messages)
    elif request.message:
        state = initial_state_from_user_message(request.message)
        direct = None
    else:
        raise HTTPException(status_code=400, detail="Either `message` or `messages` is required.")

    if direct:
        return StreamingResponse(_sse_direct_reply(direct), media_type="text/event-stream")

    return StreamingResponse(_sse_event_stream(state), media_type="text/event-stream")


FRONTEND_BUILD_DIR = PROJECT_ROOT / "frontend" / "out"
if FRONTEND_BUILD_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_BUILD_DIR, html=True), name="frontend")
