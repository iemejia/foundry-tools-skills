"""Shared helpers for integration tests.

Provides credential auto-discovery via az CLI and common skip logic.
"""

import json
import os
import subprocess


def az_discover_openai():
    """Discover Azure OpenAI credentials via az CLI if env vars are not set.

    Sets AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and
    AZURE_OPENAI_CHAT_DEPLOYMENT in os.environ as a side effect.
    """
    if os.environ.get("AZURE_OPENAI_ENDPOINT") and os.environ.get("AZURE_OPENAI_API_KEY"):
        return

    try:
        result = subprocess.run(
            ["az", "cognitiveservices", "account", "list",
             "--query", "[?kind=='OpenAI'].{name:name, rg:resourceGroup, endpoint:properties.endpoint}",
             "-o", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return
        resources = json.loads(result.stdout)
        if not resources:
            return

        for res in resources:
            dep_result = subprocess.run(
                ["az", "cognitiveservices", "account", "deployment", "list",
                 "--name", res["name"], "--resource-group", res["rg"],
                 "--query", "[].{name:name, model:properties.model.name}",
                 "-o", "json"],
                capture_output=True, text=True, timeout=30,
            )
            if dep_result.returncode != 0:
                continue
            deployments = json.loads(dep_result.stdout)
            chat_dep = next(
                (d for d in deployments if d["model"].startswith("gpt-")),
                None,
            )
            if not chat_dep:
                continue

            key_result = subprocess.run(
                ["az", "cognitiveservices", "account", "keys", "list",
                 "--name", res["name"], "--resource-group", res["rg"],
                 "--query", "key1", "-o", "tsv"],
                capture_output=True, text=True, timeout=30,
            )
            if key_result.returncode != 0 or not key_result.stdout.strip():
                continue

            os.environ.setdefault("AZURE_OPENAI_ENDPOINT", res["endpoint"])
            os.environ.setdefault("AZURE_OPENAI_API_KEY", key_result.stdout.strip())
            os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT", chat_dep["name"])
            return
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass


def openai_credentials():
    """Return (endpoint, api_key) or (None, None) after attempting discovery."""
    az_discover_openai()
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    return endpoint, api_key


def skip_reason_openai():
    """Return a skip reason string if OpenAI credentials are unavailable."""
    endpoint, api_key = openai_credentials()
    if not endpoint or not api_key:
        return (
            "Integration tests require AZURE_OPENAI_ENDPOINT and "
            "AZURE_OPENAI_API_KEY (or az CLI login). Skipping."
        )
    return None
