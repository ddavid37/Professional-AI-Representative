"""
Entry point for the Professional Representative Agent chatbot.
Uses Azure OpenAI via azure_utils and the OpenAI Agents SDK.
"""
import asyncio
import sys
from pathlib import Path

from agents import Runner, RunConfig
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, NotFoundError

from agent_config import create_agent
from azure_utils import setup_azure_for_agents
from knowledge_loader import KNOWLEDGE_DIR_NAME, get_project_dir

_PROJECT_DIR = get_project_dir()


def _connection_error_help():
    return """
Connection error talking to Azure OpenAI (this app uses Azure, not the direct OpenAI API). Check:
  • .env uses Azure vars: AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT (not OPENAI_API_KEY)
  • AZURE_OPENAI_ENDPOINT looks like https://YOUR-RESOURCE.openai.azure.com
  • AZURE_OPENAI_API_KEY is the key from Azure portal for that resource
  • Network can reach Azure (no VPN/firewall blocking)
  • AZURE_OPENAI_DEPLOYMENT_NAME matches a deployment in your Azure resource (e.g. gpt-4o-mini)
"""


# Many errors from the SDK/library mention platform.openai.com; we use Azure, so steer users to Azure.
AZURE_PORTAL_NOTE = (
    "\n(This app uses Azure OpenAI. Use https://portal.azure.com → your OpenAI resource for keys, "
    "deployments, and logs — not platform.openai.com.)"
)


def _maybe_add_azure_note(err: Exception) -> str:
    """If the error message points to OpenAI's platform, append a note that we use Azure."""
    msg = str(err)
    if "platform.openai" in msg.lower() or "openai.com" in msg.lower():
        return msg + AZURE_PORTAL_NOTE
    return msg


def _deployment_not_found_help():
    return """
DeploymentNotFound (404): AZURE_OPENAI_DEPLOYMENT_NAME in .env doesn't match any deployment in your Azure resource.
  • Open https://portal.azure.com → your OpenAI resource (e.g. "daniel-ai-agents-resource") → "Model deployments" or "Deployments".
  • Copy the exact deployment NAME (the one you gave when you created it — e.g. "gpt-4o" or "gpt-4o-mini").
  • Set AZURE_OPENAI_DEPLOYMENT_NAME in .env to that exact name and run again.
"""


async def run_chat():
    """Initialize Azure, create agent, and run a simple async chat loop."""
    load_dotenv(_PROJECT_DIR / ".env", override=True)

    knowledge_dir = _PROJECT_DIR / KNOWLEDGE_DIR_NAME
    knowledge_dir.mkdir(exist_ok=True)

    try:
        deployment_name = setup_azure_for_agents()
        agent = create_agent(model_name=deployment_name, knowledge_dir=knowledge_dir)
    except ValueError as e:
        print("Config error:", e, file=sys.stderr)
        print("Make sure .env uses Azure vars: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT (not OPENAI_API_KEY).", file=sys.stderr)
        sys.exit(1)
    except (APIConnectionError, APITimeoutError, OSError) as e:
        print("Startup failed:", _maybe_add_azure_note(e), file=sys.stderr)
        print(_connection_error_help(), file=sys.stderr)
        sys.exit(1)

    print("Professional Representative Agent (Daniel David)")
    print("Ask about Daniel's background, ML/Federated Learning, or leave a lead.")
    if knowledge_dir.exists() and any(knowledge_dir.iterdir()):
        print(f"(Using context from {KNOWLEDGE_DIR_NAME}/)")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "bye"):
                print("Goodbye.")
                break
            result = await Runner.run(agent, user_input, run_config=RunConfig(tracing_disabled=True))
            print(f"\nRep: {result.final_output}\n")
        except KeyboardInterrupt:
            print("\nGoodbye.")
            break
        except NotFoundError as e:
            print(f"Error: {_maybe_add_azure_note(e)}")
            if "DeploymentNotFound" in str(e) or "deployment" in str(e).lower():
                print(_deployment_not_found_help())
            else:
                print(_connection_error_help())
        except (APIConnectionError, APITimeoutError) as e:
            print(f"Connection error: {_maybe_add_azure_note(e)}")
            print(_connection_error_help())
        except Exception as e:
            print(f"Error: {_maybe_add_azure_note(e)}")
            if "DeploymentNotFound" in str(e) or "404" in str(e):
                print(_deployment_not_found_help())
            print()


if __name__ == "__main__":
    asyncio.run(run_chat())
