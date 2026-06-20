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

            # Also discover TTS and transcription deployments if present
            tts_dep = next(
                (d for d in deployments if d["model"].startswith("tts-")),
                None,
            )
            if tts_dep:
                os.environ.setdefault("AZURE_OPENAI_TTS_DEPLOYMENT", tts_dep["name"])

            transcribe_dep = next(
                (d for d in deployments
                 if "transcribe" in d["model"] or d["model"] == "whisper-1"),
                None,
            )
            if transcribe_dep:
                os.environ.setdefault("AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT", transcribe_dep["name"])

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


# ---------------------------------------------------------------------------
# Azure AI Translator
# ---------------------------------------------------------------------------


def _az_get_key(name, rg):
    """Retrieve key1 for a Cognitive Services resource."""
    key_result = subprocess.run(
        ["az", "cognitiveservices", "account", "keys", "list",
         "--name", name, "--resource-group", rg,
         "--query", "key1", "-o", "tsv"],
        capture_output=True, text=True, timeout=30,
    )
    if key_result.returncode == 0 and key_result.stdout.strip():
        return key_result.stdout.strip()
    return None


def az_discover_translator():
    """Discover Azure Translator credentials via az CLI."""
    if (os.environ.get("AZURE_TRANSLATOR_API_KEY")
            and os.environ.get("AZURE_TRANSLATOR_REGION")):
        return
    try:
        result = subprocess.run(
            ["az", "cognitiveservices", "account", "list",
             "--query",
             "[?kind=='TextTranslation'].{name:name, rg:resourceGroup, "
             "location:location, endpoint:properties.endpoint}",
             "-o", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return
        resources = json.loads(result.stdout)
        if not resources:
            return
        res = resources[0]
        key = _az_get_key(res["name"], res["rg"])
        if not key:
            return
        os.environ.setdefault("AZURE_TRANSLATOR_API_KEY", key)
        os.environ.setdefault("AZURE_TRANSLATOR_REGION", res["location"])
        if res.get("endpoint"):
            os.environ.setdefault("AZURE_TRANSLATOR_ENDPOINT", res["endpoint"])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass


def skip_reason_translator():
    """Return a skip reason if Translator credentials are unavailable."""
    az_discover_translator()
    if not os.environ.get("AZURE_TRANSLATOR_API_KEY"):
        return (
            "Integration tests require AZURE_TRANSLATOR_API_KEY "
            "(or az CLI login with a TextTranslation resource). Skipping."
        )
    if not os.environ.get("AZURE_TRANSLATOR_REGION"):
        return (
            "Integration tests require AZURE_TRANSLATOR_REGION. Skipping."
        )
    return None


# ---------------------------------------------------------------------------
# Azure Document Intelligence
# ---------------------------------------------------------------------------


def az_discover_doc_intelligence():
    """Discover Azure Document Intelligence credentials via az CLI."""
    if (os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_API_KEY")
            and os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")):
        return
    try:
        result = subprocess.run(
            ["az", "cognitiveservices", "account", "list",
             "--query",
             "[?kind=='FormRecognizer'].{name:name, rg:resourceGroup, "
             "endpoint:properties.endpoint}",
             "-o", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return
        resources = json.loads(result.stdout)
        if not resources:
            return
        res = resources[0]
        key = _az_get_key(res["name"], res["rg"])
        if not key:
            return
        os.environ.setdefault("AZURE_DOCUMENT_INTELLIGENCE_API_KEY", key)
        if res.get("endpoint"):
            os.environ.setdefault(
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", res["endpoint"]
            )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass


def skip_reason_doc_intelligence():
    """Return a skip reason if Doc Intelligence credentials are unavailable."""
    az_discover_doc_intelligence()
    if not os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_API_KEY"):
        return (
            "Integration tests require AZURE_DOCUMENT_INTELLIGENCE_API_KEY "
            "(or az CLI login with a FormRecognizer resource). Skipping."
        )
    if not os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"):
        return (
            "Integration tests require AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT. "
            "Skipping."
        )
    return None


# ---------------------------------------------------------------------------
# Azure AI Vision
# ---------------------------------------------------------------------------


def az_discover_vision():
    """Discover Azure Computer Vision credentials via az CLI."""
    if (os.environ.get("AZURE_AI_VISION_API_KEY")
            and os.environ.get("AZURE_AI_VISION_ENDPOINT")):
        return
    try:
        result = subprocess.run(
            ["az", "cognitiveservices", "account", "list",
             "--query",
             "[?kind=='ComputerVision'].{name:name, rg:resourceGroup, "
             "endpoint:properties.endpoint}",
             "-o", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return
        resources = json.loads(result.stdout)
        if not resources:
            return
        res = resources[0]
        key = _az_get_key(res["name"], res["rg"])
        if not key:
            return
        os.environ.setdefault("AZURE_AI_VISION_API_KEY", key)
        if res.get("endpoint"):
            os.environ.setdefault("AZURE_AI_VISION_ENDPOINT", res["endpoint"])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass


def skip_reason_vision():
    """Return a skip reason if Vision credentials are unavailable."""
    az_discover_vision()
    if not os.environ.get("AZURE_AI_VISION_API_KEY"):
        return (
            "Integration tests require AZURE_AI_VISION_API_KEY "
            "(or az CLI login with a ComputerVision resource). Skipping."
        )
    if not os.environ.get("AZURE_AI_VISION_ENDPOINT"):
        return (
            "Integration tests require AZURE_AI_VISION_ENDPOINT. Skipping."
        )
    return None


# ---------------------------------------------------------------------------
# Azure AI Language
# ---------------------------------------------------------------------------


def az_discover_language():
    """Discover Azure Language credentials via az CLI."""
    if (os.environ.get("AZURE_AI_LANGUAGE_API_KEY")
            and os.environ.get("AZURE_AI_LANGUAGE_ENDPOINT")):
        return
    try:
        result = subprocess.run(
            ["az", "cognitiveservices", "account", "list",
             "--query",
             "[?kind=='TextAnalytics'].{name:name, rg:resourceGroup, "
             "endpoint:properties.endpoint}",
             "-o", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return
        resources = json.loads(result.stdout)
        if not resources:
            return
        res = resources[0]
        key = _az_get_key(res["name"], res["rg"])
        if not key:
            return
        os.environ.setdefault("AZURE_AI_LANGUAGE_API_KEY", key)
        if res.get("endpoint"):
            os.environ.setdefault("AZURE_AI_LANGUAGE_ENDPOINT", res["endpoint"])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass


def skip_reason_language():
    """Return a skip reason if Language credentials are unavailable."""
    az_discover_language()
    if not os.environ.get("AZURE_AI_LANGUAGE_API_KEY"):
        return (
            "Integration tests require AZURE_AI_LANGUAGE_API_KEY "
            "(or az CLI login with a TextAnalytics resource). Skipping."
        )
    if not os.environ.get("AZURE_AI_LANGUAGE_ENDPOINT"):
        return (
            "Integration tests require AZURE_AI_LANGUAGE_ENDPOINT. Skipping."
        )
    return None
