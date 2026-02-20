"""
LangGraph-based agent core for the Professional AI Representative.

This module:
- Defines the typed AgentState with LangGraph reducers.
- Wires Azure OpenAI (Foundry) as the chat model using .env credentials.
- Injects persona + knowledge from the existing knowledge_loader.
- Enforces an "I don't know" protocol that asks for contact info instead of hallucinating.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, TypedDict

from typing_extensions import Annotated

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, START, CompiledGraph, StateGraph
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
    # Simple "append" semantics: keep all historical leads.
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


_MODEL: AzureChatOpenAI | None = None


def _get_azure_chat_model() -> AzureChatOpenAI:
    """
    Construct (or reuse) an AzureChatOpenAI model using Foundry-style env vars.

    Expected env vars (already documented in README):
      - AZURE_OPENAI_API_KEY
      - AZURE_OPENAI_ENDPOINT          e.g. https://<resource>.services.ai.azure.com
      - AZURE_OPENAI_API_VERSION       e.g. 2024-10-21
      - AZURE_OPENAI_DEPLOYMENT_NAME   e.g. gpt-4o-mini
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    missing = [name for name, value in [
        ("AZURE_OPENAI_API_KEY", api_key),
        ("AZURE_OPENAI_ENDPOINT", endpoint),
        ("AZURE_OPENAI_API_VERSION", api_version),
        ("AZURE_OPENAI_DEPLOYMENT_NAME", deployment),
    ] if not value]
    if missing:
        raise ValueError(
            "Missing Azure OpenAI configuration for LangGraph agent. "
            f"Set in .env: {', '.join(missing)}"
        )

    # Normalize endpoint (Foundry uses *.services.ai.azure.com)
    endpoint = endpoint.rstrip("/")

    _MODEL = AzureChatOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
        azure_deployment=deployment,
    )
    return _MODEL


_DEFAULT_BIO = """
Daniel David is a CS student at Columbia University (class of 2026) and an ML Engineer at Rhino HealthTech.
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
    - Sends the message history to Azure OpenAI.
    - Appends the assistant reply to `messages`.
    """
    model = _get_azure_chat_model()
    messages = _ensure_system_message(state["messages"])
    response: AIMessage = model.invoke(messages)
    return {"messages": [response]}


def build_agent_graph() -> CompiledGraph:
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
GRAPH: CompiledGraph = build_agent_graph()


def initial_state_from_user_message(content: str) -> AgentState:
    """
    Helper to build an initial AgentState from a single user message.
    """
    return {
        "messages": [HumanMessage(content=content)],
        "leads": [],
    }

