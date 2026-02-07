"""
Agent configuration for the Professional Representative Agent.
Defines system instructions and agent initialization using the OpenAI Agents SDK.
Uses the knowledge/ directory for drop-in context about Daniel.
"""
import os
from pathlib import Path
from typing import Optional

from agents import Agent

from knowledge_loader import load_knowledge_dir
from tools import lead_capture

# ----- Base persona (used if no knowledge files) -----
DEFAULT_BIO = """
Daniel David is a CS student at Columbia University (class of 2026) and an ML Engineer at Rhino HealthTech.
His work focuses on ML Security, Federated Learning, and NVFlare. He is professional, approachable, and witty.
"""


def _build_instructions(knowledge_dir: Optional[Path] = None) -> str:
    """Build system instructions, merging in content from the knowledge directory."""
    knowledge_text = load_knowledge_dir(knowledge_dir)
    if knowledge_text.strip():
        persona_section = knowledge_text.strip()
    else:
        persona_section = DEFAULT_BIO.strip()

    return f"""You are the professional representative and gatekeeper for Daniel David.

## Persona and knowledge about Daniel
{persona_section}
Be professional, witty, and grounded. Represent Daniel in a way that feels human and helpful.
Answer only from the information above or from general, public knowledge. Do not invent details.

## What you must NOT do
- Do NOT make up salary, compensation, or confidential project details.
- Do NOT invent specific internal Rhino HealthTech or Columbia details you are unsure about.
- Do NOT guess or hallucinate. If you are not confident, use the lead_capture tool.

## When you cannot answer
If the user asks for something you cannot answer from the given context (e.g. specific salary requirements,
private project details, confidential info, or anything you are not authorized to share):
1. Do NOT say "I don't know" and leave it there.
2. Use the lead_capture tool: ask for their Name and Email, and record their specific question.
3. Tell them you have recorded their inquiry and that Daniel will get back to them.
4. Be warm and professional so they feel heard.
"""


def create_agent(
    model_name: Optional[str] = None,
    knowledge_dir: Optional[Path] = None,
) -> Agent:
    """Create the Professional Representative Agent with LeadCapture tool and Azure model."""
    model = model_name or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
    instructions = _build_instructions(knowledge_dir)
    return Agent(
        name="DanielsRep",
        instructions=instructions,
        tools=[lead_capture],
        model=model,
    )
