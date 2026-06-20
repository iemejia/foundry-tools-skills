#!/usr/bin/env python3
"""Unit tests for skills/openai-tts/scripts/tts.py."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-tts", "scripts", "tts.py"
)
_spec = importlib.util.spec_from_file_location("tts", _SCRIPT)
tts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tts)
sys.modules["tts"] = tts


class TestDetectProvider(unittest.TestCase):
    def test_azure(self):
        self.assertEqual(tts.detect_provider("https://x.openai.azure.com"), "azure")

    def test_openai(self):
        self.assertEqual(tts.detect_provider("https://api.openai.com"), "openai")


class TestBuildUrl(unittest.TestCase):
    def test_azure_url(self):
        url = tts.build_url("https://x.openai.azure.com", "tts-1", "2024-10-21", "azure")
        self.assertIn("/openai/deployments/tts-1/audio/speech", url)

    def test_openai_url(self):
        url = tts.build_url("https://api.openai.com", "tts-1", "2024-10-21", "openai")
        self.assertEqual(url, "https://api.openai.com/v1/audio/speech")


class TestParseArgs(unittest.TestCase):
    def test_minimal(self):
        args = tts.parse_args(["--model", "tts-1", "--voice", "nova", "--input", "hi"])
        self.assertEqual(args.model, "tts-1")
        self.assertEqual(args.voice, "nova")
        self.assertEqual(args.input_text, "hi")
        self.assertEqual(args.response_format, "mp3")

    def test_all_args(self):
        args = tts.parse_args([
            "--model", "tts-1-hd", "--voice", "echo", "--input", "test",
            "--response-format", "opus", "--speed", "1.5",
            "--output", "out.opus", "--provider", "azure",
        ])
        self.assertEqual(args.response_format, "opus")
        self.assertAlmostEqual(args.speed, 1.5)
        self.assertEqual(args.output, "out.opus")


class TestMainMissingKey(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key(self):
        rc = tts.main(["--model", "tts-1", "--voice", "nova", "--input", "hi"])
        self.assertEqual(rc, 1)


class TestMainSuccess(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    @patch("tts._do_request")
    def test_saves_audio(self, mock_req):
        mock_req.return_value = b"\xff\xfb\x90\x00" * 100  # fake mp3 bytes
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            outpath = f.name
        try:
            rc = tts.main([
                "--model", "tts-1", "--voice", "nova",
                "--input", "hello", "--output", outpath,
            ])
            self.assertEqual(rc, 0)
            self.assertGreater(os.path.getsize(outpath), 0)
        finally:
            os.unlink(outpath)


if __name__ == "__main__":
    unittest.main()
