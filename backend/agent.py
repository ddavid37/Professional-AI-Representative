"""
LangGraph agent for Daniel's AI representative.

Simple design:
- Answer from knowledge/ when confident.
- Otherwise collect name + email and call notify_daniel_on_whatsapp.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from custom.knowledge_loader import (
    KNOWLEDGE_DIR_NAME,
    get_project_dir,
    load_knowledge_dir,
)
from .whatsapp import send_lead_notification


def _get_chat_model() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY.")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(api_key=api_key, model=model_name)


_DEFAULT_BIO = """
Daniel David is a Columbia University graduate (B.A. Computer Science, May 2026) and former ML Engineer at Rhino Federated Computing.
His work focuses on ML Security, Federated Learning, and NVFlare. He is currently open to full-time ML/AI roles.
He is professional, approachable, and witty.
""".strip()


@tool
def notify_daniel_on_whatsapp(name: str, email: str, question: str) -> str:
    """
    Notify Daniel on WhatsApp about a question you cannot answer from verified knowledge.
    Call this once you have the visitor's full name, email, and their question.
    """
    result = send_lead_notification(name=name, email=email, question=question)
    if result.get("status") == "sent":
        return "Daniel was notified on WhatsApp."
    return f"Could not reach Daniel on WhatsApp: {result.get('message', 'unknown error')}"


def _build_system_prompt() -> str:
    project_dir = get_project_dir()
    knowledge_dir = project_dir / KNOWLEDGE_DIR_NAME
    knowledge_text = load_knowledge_dir(knowledge_dir).strip()
    persona_section = knowledge_text if knowledge_text else _DEFAULT_BIO

    return f"""You are the professional representative for Daniel David.

## Knowledge about Daniel (answer from this when you are sure)
{persona_section}

## Tone
- Professional but **slightly playful** — warm, witty, and human. Not a stiff FAQ bot.
- Match the user's energy when appropriate; a little personality is fine if it stays accurate and respectful.

## Your rules
1. If you KNOW the answer from the knowledge above, answer directly.
2. If you are NOT sure (family/personal details, siblings, salary, private info, job offers you cannot confirm, etc.), do NOT guess.
   - Ask for their full name and email.
   - Once you have name, email, AND their question, call `notify_daniel_on_whatsapp`.
3. Read the **entire conversation**. The question may have been asked in an earlier message.
   - If the user sends something like "John Doe john@email.com", that is contact info — use their earlier question for the tool.
   - Never ask for name, email, or the question again if you already have all three.
4. After calling the tool, confirm Daniel was notified on WhatsApp.
5. **Dream company (Starbridge) — two chunks:**
   - If asked Daniel's dream/top-choice company (without asking why): answer in **one short sentence** only, e.g. "Daniel's dream company is Starbridge." Do not explain why unless asked.
   - If asked why (including "Why?" as a follow-up): give the reason — product vision, CEO Justin Wenig, unapologetic vision and execution. Do not repeat the one-liner unless helpful.
6. Do not mention Starbridge unprompted unless the chat is about careers or job search.
""".strip()


def build_agent_graph():
    return create_react_agent(
        _get_chat_model(),
        [notify_daniel_on_whatsapp],
        prompt=_build_system_prompt(),
    )


GRAPH = build_agent_graph()


def initial_state_from_user_message(content: str) -> Dict[str, List[AnyMessage]]:
    return {"messages": [HumanMessage(content=content)]}


def state_from_chat_history(history: List[Dict[str, Any]]) -> Dict[str, List[AnyMessage]]:
    messages: List[AnyMessage] = []
    for item in history:
        role = item.get("role")
        content = item.get("content", "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return {"messages": messages}
