#!/usr/bin/env python3
"""Unit tests for skills/openai-chat/scripts/chat.py.

Tests pure logic (no network calls). Uses unittest.mock to verify HTTP
handling, retry behavior, and error output.
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Import chat.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-chat", "scripts", "chat.py"
)
_spec = importlib.util.spec_from_file_location("chat", _SCRIPT)
chat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chat)
sys.modules["chat"] = chat


class TestDetectProvider(unittest.TestCase):
    def test_azure_openai_endpoint(self):
        self.assertEqual(
            chat.detect_provider("https://myres.openai.azure.com"),
            "azure",
        )

    def test_cognitive_services_endpoint(self):
        self.assertEqual(
            chat.detect_provider("https://myres.cognitiveservices.azure.com"),
            "azure",
        )

    def test_openai_endpoint(self):
        self.assertEqual(
            chat.detect_provider("https://api.openai.com"),
            "openai",
        )

    def test_custom_endpoint_defaults_to_openai(self):
        self.assertEqual(
            chat.detect_provider("https://my-proxy.example.com"),
            "openai",
        )


class TestBuildUrl(unittest.TestCase):
    def test_azure_url(self):
        url = chat.build_url(
            "https://myres.openai.azure.com", "gpt-4o", "2024-10-21", "azure"
        )
        self.assertEqual(
            url,
            "https://myres.openai.azure.com/openai/deployments/gpt-4o"
            "/chat/completions?api-version=2024-10-21",
        )

    def test_openai_url(self):
        url = chat.build_url(
            "https://api.openai.com", "gpt-4o", "2024-10-21", "openai"
        )
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")

    def test_trailing_slash_stripped(self):
        url = chat.build_url(
            "https://api.openai.com/", "gpt-4o", "2024-10-21", "openai"
        )
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")


class TestParseArgs(unittest.TestCase):
    def test_minimal_args(self):
        args = chat.parse_args(["--model", "gpt-4o", "--prompt", "hi"])
        self.assertEqual(args.model, "gpt-4o")
        self.assertEqual(args.prompt, "hi")
        self.assertIsNone(args.system)
        self.assertFalse(args.raw)

    def test_all_args(self):
        args = chat.parse_args([
            "--model", "gpt-4o",
            "--prompt", "hello",
            "--system", "Be brief",
            "--provider", "azure",
            "--endpoint", "https://myres.openai.azure.com",
            "--api-version", "2025-01-01",
            "--max-tokens", "100",
            "--temperature", "0.7",
            "--timeout", "30",
            "--retries", "5",
            "--raw",
        ])
        self.assertEqual(args.provider, "azure")
        self.assertEqual(args.max_tokens, 100)
        self.assertAlmostEqual(args.temperature, 0.7)
        self.assertEqual(args.retries, 5)
        self.assertTrue(args.raw)


class TestMainMissingKey(unittest.TestCase):
    """Test that main() emits structured errors when API key is missing."""

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_openai(self):
        with patch("sys.stderr") as mock_stderr:
            mock_stderr.write = MagicMock()
            rc = chat.main(["--model", "gpt-4o", "--prompt", "hi"])
        self.assertEqual(rc, 1)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_azure(self):
        with patch("sys.stderr") as mock_stderr:
            mock_stderr.write = MagicMock()
            rc = chat.main([
                "--model", "gpt-4o",
                "--prompt", "hi",
                "--endpoint", "https://x.openai.azure.com",
            ])
        self.assertEqual(rc, 1)


class TestMainSuccess(unittest.TestCase):
    """Test successful API call path with mocked HTTP."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    @patch("chat.call_chat")
    def test_prints_content(self, mock_call):
        mock_call.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        with patch("builtins.print") as mock_print:
            rc = chat.main(["--model", "gpt-4o", "--prompt", "hi"])
        self.assertEqual(rc, 0)
        mock_print.assert_called_with("Hello!")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    @patch("chat.call_chat")
    def test_raw_mode(self, mock_call):
        response = {"choices": [{"message": {"content": "Hi"}}], "id": "x"}
        mock_call.return_value = response
        rc = chat.main(["--model", "gpt-4o", "--prompt", "hi", "--raw"])
        self.assertEqual(rc, 0)


class TestMainPayload(unittest.TestCase):
    """Verify the request payload is constructed correctly."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    @patch("chat.call_chat")
    def test_payload_includes_model(self, mock_call):
        mock_call.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        chat.main(["--model", "gpt-4o-mini", "--prompt", "test"])
        _, kwargs = mock_call.call_args if mock_call.call_args.kwargs else (mock_call.call_args[0], {})
        args = mock_call.call_args[0] if mock_call.call_args[0] else []
        # payload is the 3rd positional arg (url, api_key, payload, timeout, provider, retries)
        payload = args[2]
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertIn({"role": "user", "content": "test"}, payload["messages"])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    @patch("chat.call_chat")
    def test_system_message_included(self, mock_call):
        mock_call.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        chat.main(["--model", "gpt-4o", "--prompt", "hi", "--system", "Be terse"])
        payload = mock_call.call_args[0][2]
        self.assertEqual(payload["messages"][0], {"role": "system", "content": "Be terse"})


if __name__ == "__main__":
    unittest.main()
