"""
Azure OpenAI client setup for the OpenAI Agents SDK.
Uses Azure-only env vars (not OPENAI_API_KEY). Same pattern as the main agents repo.
The Agents SDK requires AsyncAzureOpenAI and chat_completions API mode for Azure.
"""
import os
from openai import AsyncAzureOpenAI
from agents import set_default_openai_client, set_default_openai_api, set_tracing_export_api_key


def setup_azure_for_agents() -> str:
    """
    Create AsyncAzureOpenAI client and set it as the default for the Agents SDK.
    Caller must load .env first (e.g. main.py loads from project dir).
    Azure supports Chat Completions only (not the Responses API).
    Returns the deployment name for use as the model parameter.
    """
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "o4-mini")

    if not api_key or not endpoint:
        missing = [k for k, v in [
            ("AZURE_OPENAI_API_KEY", api_key),
            ("AZURE_OPENAI_ENDPOINT", endpoint),
        ] if not v]
        raise ValueError(
            f"Missing in .env: {', '.join(missing)}. "
            "Use your Azure OpenAI key and endpoint (not the direct OpenAI API key)."
        )

    # Some clients expect endpoint without trailing slash
    endpoint = endpoint.rstrip("/")
    if not api_version:
        # Match your deployment (cognitiveservices.azure.com); portal often uses 2024-12-01-preview
        api_version = "2024-12-01-preview"

    client = AsyncAzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=endpoint,
    )
    # LLM calls use Azure. Tracing uploads to platform.openai.com and needs a direct OpenAI key.
    set_default_openai_client(client, use_for_tracing=False)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        set_tracing_export_api_key(openai_key)  # so traces appear at https://platform.openai.com/traces
    set_default_openai_api("chat_completions")
    return deployment_name
