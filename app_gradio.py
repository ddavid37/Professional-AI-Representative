"""
Gradio UI for the Professional Representative Agent chatbot.
Run: python app_gradio.py
Then open the URL shown (e.g. http://127.0.0.1:7860).
"""
import sys
from pathlib import Path

import gradio as gr
from agents import Runner, RunConfig
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, NotFoundError

from agent_config import create_agent
from azure_utils import setup_azure_for_agents
from knowledge_loader import KNOWLEDGE_DIR_NAME, get_project_dir

_PROJECT_DIR = get_project_dir()

# Initialize agent once at startup (shared across chat turns)
agent = None


def _init_agent():
    """Load env, set up Azure, create agent. Call once at startup."""
    global agent
    load_dotenv(_PROJECT_DIR / ".env", override=True)
    knowledge_dir = _PROJECT_DIR / KNOWLEDGE_DIR_NAME
    knowledge_dir.mkdir(exist_ok=True)
    deployment_name = setup_azure_for_agents()
    agent = create_agent(model_name=deployment_name, knowledge_dir=knowledge_dir)
    return agent


async def chat(message: str, history: list) -> str:
    """
    Gradio chat handler: takes user message and history, returns the assistant reply string.
    """
    global agent
    if not message or not message.strip():
        return ""
    try:
        result = await Runner.run(
            agent, message.strip(), run_config=RunConfig(tracing_disabled=True)
        )
        return result.final_output or ""
    except (NotFoundError, APIConnectionError, APITimeoutError) as e:
        err_msg = str(e)
        if "DeploymentNotFound" in err_msg or "deployment" in err_msg.lower():
            err_msg += "\n\nCheck AZURE_OPENAI_DEPLOYMENT_NAME in .env (Azure Portal → Model deployments)."
        return f"Sorry, an error occurred: {err_msg}"
    except Exception as e:
        return f"Sorry, an error occurred: {str(e)}"


def main():
    global agent
    try:
        _init_agent()
    except ValueError as e:
        print("Config error:", e, file=sys.stderr)
        print(
            "Ensure .env has: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT.",
            file=sys.stderr,
        )
        sys.exit(1)
    except (APIConnectionError, APITimeoutError, OSError) as e:
        print("Startup failed:", e, file=sys.stderr)
        sys.exit(1)

    # Gradio ChatInterface: simple chat UI with title and placeholder
    demo = gr.ChatInterface(
        fn=chat,
        title="Professional Representative Agent — Daniel David",
        description="Ask about Daniel's background, ML/Federated Learning, or leave a lead. Say **exit** or **quit** to stop.",
        type="messages",
        examples=[
            "What is Daniel's background?",
            "Tell me about Federated Learning.",
            "I'd like to leave a lead.",
        ],
    )

    # 0.0.0.0 = listen on all interfaces (other devices can use your PC's IP:7860).
    # In your browser, use 127.0.0.1 or localhost — do not open http://0.0.0.0:7860.
    print("\n  Open in your browser: http://127.0.0.1:7860  (or http://localhost:7860)\n")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
    )


if __name__ == "__main__":
    main()
