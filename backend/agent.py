"""
LangGraph-based agent core for the Professional AI Representative.

This module:
- Defines the typed AgentState with LangGraph reducers.
- Wires standard OpenAI (gpt-4o-mini) as the chat model via OPENAI_API_KEY.
- Injects persona + knowledge from the existing knowledge_loader.
- Enforces an "I don't know" protocol that asks for contact info instead of hallucinating.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, TypedDict

from typing_extensions import Annotated

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from knowledge_loader import KNOWLEDGE_DIR_NAME, get_project_dir, load_knowledge_dir


def _append_leads(
    existing: List[Dict[str, Any]] | None, new: List[Dict[str, Any]] | None
) -> List[Dict[str, Any]]:
    """
    Custom reducer for the `leads` key in the AgentState.

    LangGraph will call this with the previous and new values whenever a node
    returns a partial state update for `leads`.
    """
    if not existing:
        existing = []
    if not new:
        new = []
    return [*existing, *new]


class AgentState(TypedDict):
    """
    Global state for the LangGraph workflow.

    - messages: running chat history (system + user + assistant).
      Uses `add_messages` so nodes can append without clobbering history.
    - leads: structured list of captured leads; updated via `_append_leads`.
    """

    messages: Annotated[List[AnyMessage], add_messages]
    leads: Annotated[List[Dict[str, Any]], _append_leads]


_MODEL: ChatOpenAI | None = None


def _get_chat_model() -> ChatOpenAI:
    """
    Construct (or reuse) a ChatOpenAI model using the standard OpenAI API.

    Required env var:
      - OPENAI_API_KEY

    Optional env var (defaults to gpt-4o-mini):
      - OPENAI_MODEL   e.g. gpt-4o, gpt-4o-mini
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "Missing OPENAI_API_KEY. Set it in .env or as a Railway environment variable."
        )

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    _MODEL = ChatOpenAI(api_key=api_key, model=model_name)
    return _MODEL


_DEFAULT_BIO = """
Daniel David is a CS student at Columbia University (class of 2026) and an ML Engineer at Rhino Federated Computing.
His work focuses on ML Security, Federated Learning, and NVFlare. He is professional, approachable, and witty.
""".strip()


def _build_system_prompt() -> str:
    """
    Build the system prompt from the knowledge directory plus a safety policy.

    Mirrors the behavior of the existing agent_config.py but tailored for LangGraph.
    """
    project_dir = get_project_dir()
    knowledge_dir = project_dir / KNOWLEDGE_DIR_NAME
    knowledge_text = load_knowledge_dir(knowledge_dir).strip()

    persona_section = knowledge_text if knowledge_text else _DEFAULT_BIO

    return f"""You are the professional representative and gatekeeper for Daniel David.

You must be:
- Professional and clear.
- Approachable and a bit witty when appropriate.
- Grounded in factual information only.

## Persona and knowledge about Daniel
{persona_section}

## Grounding and safety
- Answer only from the information above or general, widely known public knowledge.
- NEVER invent specific private details (salaries, confidential projects, internal company data).
- If you are not confident you know the answer, you MUST avoid hallucinating.

## When you don't know
If you cannot answer with high confidence (because the question is too private, too specific,
or not covered by your knowledge), follow this protocol:
1. Politely say that you may not have enough verified information to answer with confidence.
2. Ask the user to share their full name and email so Daniel can follow up personally.
3. Briefly restate their question so they feel heard.

Do NOT just say "I don't know" and stop. Always invite them to leave contact details so
Daniel can respond directly when needed.
""".strip()


def _ensure_system_message(messages: List[AnyMessage]) -> List[AnyMessage]:
    """Ensure the first message is our system prompt."""
    if any(isinstance(m, SystemMessage) for m in messages):
        return messages
    system = SystemMessage(content=_build_system_prompt())
    return [system, *messages]


def agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Single-node "brain" for now:
    - Injects system prompt if missing.
    - Sends the message history to OpenAI.
    - Appends the assistant reply to `messages`.
    """
    model = _get_chat_model()
    messages = _ensure_system_message(state["messages"])
    response: AIMessage = model.invoke(messages)
    return {"messages": [response]}


def build_agent_graph():
    """
    Construct the LangGraph workflow for this agent.

    For now this is a simple single-node graph:
      START -> agent_node -> END

    The state still includes `leads` with a custom reducer so we can
    later plug in a LeadCapture tool node that appends to `leads`.
    """
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    return builder.compile()


# Pre-compiled graph for reuse by the FastAPI app.
GRAPH = build_agent_graph()


def initial_state_from_user_message(content: str) -> AgentState:
    """
    Helper to build an initial AgentState from a single user message.
    """
    return {
        "messages": [HumanMessage(content=content)],
        "leads": [],
    }

