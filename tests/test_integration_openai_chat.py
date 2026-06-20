#!/usr/bin/env python3
"""Integration tests for openai-chat skill (require live credentials).

Run:
    python3 tests/test_integration_openai_chat.py -v

Credentials are auto-discovered via az CLI if env vars are not set.
Tests are skipped gracefully when no credentials are available.
"""

import importlib.util
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(__file__))
from conftest import skip_reason_openai  # noqa: E402

_SKIP_REASON = skip_reason_openai()
_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")

# Import chat.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-chat", "scripts", "chat.py"
)
_spec = importlib.util.spec_from_file_location("chat_integ", _SCRIPT)
chat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chat)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
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


if __name__ == "__main__":
    unittest.main()
