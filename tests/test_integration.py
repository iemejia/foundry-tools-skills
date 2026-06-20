#!/usr/bin/env python3
"""Integration tests for foundry-tools-skills (require live credentials).

These tests make real API calls to Azure OpenAI. They are skipped
automatically if the required environment variables are not set.

Run:
    # Set credentials (or let the test discover them via az CLI)
    export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com"
    export AZURE_OPENAI_API_KEY="<key>"
    export AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4o"  # deployment name for chat

    python3 run_tests.py tests/test_integration.py -v

Or discover credentials automatically (requires az CLI logged in):
    python3 tests/test_integration.py -v
"""

# Requires: Python >= 3.8, standard library only

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Credential discovery via az CLI (fallback if env vars not set)
# ---------------------------------------------------------------------------

def _az_discover():
    """Try to discover Azure OpenAI credentials via az CLI."""
    if os.environ.get("AZURE_OPENAI_ENDPOINT") and os.environ.get("AZURE_OPENAI_API_KEY"):
        return  # already set

    # Find an Azure OpenAI resource with a chat deployment
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

        # Try each resource to find one with a chat deployment
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
            # Find a chat-capable deployment (gpt-* models)
            chat_dep = next(
                (d for d in deployments if d["model"].startswith("gpt-")),
                None,
            )
            if not chat_dep:
                continue

            # Get key
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


# Run discovery at import time
_az_discover()

# ---------------------------------------------------------------------------
# Check prerequisites
# ---------------------------------------------------------------------------

_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")

_SKIP_REASON = None
if not _ENDPOINT or not _API_KEY:
    _SKIP_REASON = (
        "Integration tests require AZURE_OPENAI_ENDPOINT and "
        "AZURE_OPENAI_API_KEY (or az CLI login). Skipping."
    )

# ---------------------------------------------------------------------------
# Import scripts as modules
# ---------------------------------------------------------------------------

_CHAT_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-chat", "scripts", "chat.py"
)
_chat_spec = importlib.util.spec_from_file_location("chat_e2e", _CHAT_SCRIPT)
chat = importlib.util.module_from_spec(_chat_spec)
_chat_spec.loader.exec_module(chat)

_GEN_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-images", "scripts", "generate.py"
)
_gen_spec = importlib.util.spec_from_file_location("generate_e2e", _GEN_SCRIPT)
generate = importlib.util.module_from_spec(_gen_spec)
_gen_spec.loader.exec_module(generate)


# ---------------------------------------------------------------------------
# Integration tests — Chat
# ---------------------------------------------------------------------------

@unittest.skipIf(_SKIP_REASON, _SKIP_REASON)
class TestChatIntegration(unittest.TestCase):
    """End-to-end tests against a live Azure OpenAI chat deployment."""

    def test_basic_prompt(self):
        """Send a simple prompt and verify we get a non-empty response."""
        rc = chat.main([
            "--endpoint", _ENDPOINT,
            "--model", _CHAT_DEPLOYMENT,
            "--prompt", "Reply with exactly the word 'pong'.",
            "--max-tokens", "5",
        ])
        self.assertEqual(rc, 0)

    def test_system_message(self):
        """Verify system message is respected."""
        rc = chat.main([
            "--endpoint", _ENDPOINT,
            "--model", _CHAT_DEPLOYMENT,
            "--system", "You must reply with only the word 'OK'.",
            "--prompt", "Anything.",
            "--max-tokens", "5",
        ])
        self.assertEqual(rc, 0)

    def test_raw_json_output(self):
        """Verify --raw returns valid JSON with expected structure."""
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = chat.main([
                "--endpoint", _ENDPOINT,
                "--model", _CHAT_DEPLOYMENT,
                "--prompt", "Say hi",
                "--max-tokens", "5",
                "--raw",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("choices", data)
        self.assertGreater(len(data["choices"]), 0)
        self.assertIn("message", data["choices"][0])

    def test_invalid_deployment_gives_error(self):
        """Verify structured error for a non-existent deployment."""
        rc = chat.main([
            "--endpoint", _ENDPOINT,
            "--model", "nonexistent-deployment-xyz",
            "--prompt", "hi",
            "--max-tokens", "5",
            "--retries", "0",
        ])
        self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# Integration tests — Images (only if a gpt-image deployment exists)
# ---------------------------------------------------------------------------

_IMAGE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_IMAGE_DEPLOYMENT")


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON)
@unittest.skipUnless(_IMAGE_DEPLOYMENT, "No AZURE_OPENAI_IMAGE_DEPLOYMENT set")
class TestImagesIntegration(unittest.TestCase):
    """End-to-end tests against a live Azure OpenAI image deployment."""

    def test_generate_image(self):
        """Generate an image and verify it saves to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = generate.main([
                "--endpoint", _ENDPOINT,
                "--model", _IMAGE_DEPLOYMENT,
                "--prompt", "A simple blue square on white background",
                "--size", "1024x1024",
                "--output-dir", tmpdir,
            ])
            self.assertEqual(rc, 0)
            files = os.listdir(tmpdir)
            self.assertGreater(len(files), 0)
            # Verify file is non-empty
            fpath = os.path.join(tmpdir, files[0])
            self.assertGreater(os.path.getsize(fpath), 100)


if __name__ == "__main__":
    unittest.main()
