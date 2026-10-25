"""
LangGraph agent for Daniel's AI representative.

Simple design:
- Answer from knowledge/ when confident about Daniel.
- Search the public web with Tavily for current / general facts.
- Otherwise collect name + email and call notify_daniel_on_whatsapp.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Set

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
from .handoff import EMAIL_RE
from .knowledge_audit import sync_knowledge_audit
from .search import search_web as tavily_search
from .search import format_search_context
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
def search_web(query: str) -> str:
    """
    Search the public internet for current events, companies, sports, news, or
    other general facts that are not about Daniel's private life.
    Call this for public/current questions. Never answer those from memory.
    If search fails, tell the visitor search is unavailable — do not guess.
    """
    result = tavily_search(query)
    return format_search_context(result)


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


def _load_knowledge_text() -> str:
    knowledge_dir = get_project_dir() / KNOWLEDGE_DIR_NAME
    try:
        sync_knowledge_audit(knowledge_dir)
    except OSError:
        # Vercel (and other read-only deploys) cannot persist audit snapshots.
        pass
    return load_knowledge_dir(knowledge_dir).strip()


def _build_system_prompt(knowledge_text: str) -> str:
    persona_section = knowledge_text if knowledge_text else _DEFAULT_BIO

    return f"""You are the professional representative for Daniel David.

## Knowledge about Daniel (answer from this when you are sure)
{persona_section}

## Tone
- Professional but **slightly playful** — warm, witty, and human. Not a stiff FAQ bot.
- Match the user's energy when appropriate; a little personality is fine if it stays accurate and respectful.

## Your rules
1. If you KNOW the answer from the knowledge above (Daniel's bio, skills, career preferences), answer directly. Do not search the web for facts already in knowledge.
2. If the question is about **public / current information** (news, companies, sports, weather, scores, people who are not Daniel):
   - You MUST use live search results (already attached as an internal message, or by calling `search_web`).
   - NEVER answer those from training memory (do not say Messi won in 2022 unless the live results say so).
   - If search failed or returned nothing, say you could not retrieve live results. Do not guess.
3. If you are NOT sure about **Daniel personally** (family, salary, private info, unconfirmed job offers, etc.), do NOT guess and do NOT search the web for that.
   - Ask for their full name and email.
   - Once you have name, email, AND their question, call `notify_daniel_on_whatsapp`.
4. Read the **entire conversation**. The question may have been asked in an earlier message.
   - If the user sends something like "John Doe john@email.com", that is contact info — use their earlier question for the tool.
   - Never ask for name, email, or the question again if you already have all three.
5. After calling the WhatsApp tool, confirm Daniel was notified on WhatsApp.
6. **Career search:** Daniel does **not** have a named dream company. He has an entrepreneurship mindset and also fully values stable, established companies. If asked where he wants to work or what he is looking for, describe the two tracks in knowledge: (1) early-stage / founding-adjacent, versatile, technical + customer-facing + business-oriented; (2) Series A–B, especially Forward Deployed Engineer (FDE) roles with the same mix. Do not invent a target company.
7. Do not volunteer career-search detail unprompted unless the chat is about jobs or career goals.
8. **Contact details:** NEVER invent an email address, phone number, or link for Daniel. Only share contact details that appear word-for-word in the knowledge above. If someone wants to reach Daniel, point them to the Contact page or offer to collect their name and email and notify him on WhatsApp.
9. **Do not repeat yourself:** offer the WhatsApp handoff at most once unless the visitor asks again. Never end several messages in a row with the same closing line or sign-off; vary it or skip it.
10. **Recruiters:** if the visitor is a recruiter, from a company, or mentions a role, answer their question and then ask, in the same reply, about the specifics you are missing: the role title, seniority, location (and on-site / hybrid / remote), and the team or company. Ask at most two of these per reply, skip any they already told you, and stop asking once you have them. Include what they shared when you call `notify_daniel_on_whatsapp`.
11. **Language and gender:** reply in the visitor's language. Daniel is male, so refer to him in masculine forms. Do NOT assume the visitor's gender. In Hebrew, unless the visitor has written about themselves in a gendered form (e.g. "אני מגייסת" → feminine, "אני מגייס" → masculine), address them in plural / neutral forms: write "אם תרצו", "תוכלו להשאיר פרטים", "אשמח לשמוע מכם" — never "אם תרצה", "תוכל", "אתה" by default. When speaking about yourself in Hebrew, prefer neutral phrasing ("קשה לי לומר בוודאות", "אשמח") over gendered adjectives.
""".strip()


# Emails the agent may repeat (from knowledge/). Anything else is scrubbed.
VERIFIED_EMAILS: Set[str] = set()


def build_agent_graph():
    global VERIFIED_EMAILS
    knowledge_text = _load_knowledge_text()
    VERIFIED_EMAILS = set(EMAIL_RE.findall(knowledge_text))
    return create_react_agent(
        _get_chat_model(),
        [search_web, notify_daniel_on_whatsapp],
        prompt=_build_system_prompt(knowledge_text),
    )


GRAPH = build_agent_graph()


def reload_agent_graph() -> Dict[str, Any]:
    """Rebuild the in-process graph so it picks up knowledge/ changes."""
    global GRAPH
    GRAPH = build_agent_graph()
    return {"status": "ok"}


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
