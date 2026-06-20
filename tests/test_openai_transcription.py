#!/usr/bin/env python3
"""Unit tests for skills/openai-transcription/scripts/transcribe.py."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-transcription",
    "scripts", "transcribe.py"
)
_spec = importlib.util.spec_from_file_location("transcribe", _SCRIPT)
transcribe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transcribe)
sys.modules["transcribe"] = transcribe


class TestDetectProvider(unittest.TestCase):
    def test_azure(self):
        self.assertEqual(
            transcribe.detect_provider("https://x.openai.azure.com"), "azure"
        )

    def test_openai(self):
        self.assertEqual(
            transcribe.detect_provider("https://api.openai.com"), "openai"
        )


class TestBuildUrl(unittest.TestCase):
    def test_azure_url(self):
        url = transcribe.build_url(
            "https://x.openai.azure.com", "whisper-1", "2024-10-21", "azure"
        )
        self.assertIn("/openai/deployments/whisper-1/audio/transcriptions", url)

    def test_openai_url(self):
        url = transcribe.build_url(
            "https://api.openai.com", "whisper-1", "2024-10-21", "openai"
        )
        self.assertEqual(
            url, "https://api.openai.com/v1/audio/transcriptions"
        )


class TestBuildMultipart(unittest.TestCase):
    def test_produces_valid_multipart(self):
        fields = {"model": "whisper-1", "language": "en"}
        files = {"file": ("test.mp3", b"\xff\xfb\x90\x00", "audio/mpeg")}
        body, content_type = transcribe._build_multipart(fields, files)
        self.assertIn(b"whisper-1", body)
        self.assertIn(b"test.mp3", body)
        self.assertIn(b"\xff\xfb\x90\x00", body)
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))

    def test_boundary_in_content_type(self):
        body, ct = transcribe._build_multipart({"model": "x"}, {})
        boundary = ct.split("boundary=")[1]
        self.assertIn(boundary.encode(), body)


class TestGuessMime(unittest.TestCase):
    def test_mp3(self):
        self.assertEqual(transcribe._guess_mime("file.mp3"), "audio/mpeg")

    def test_wav(self):
        self.assertEqual(transcribe._guess_mime("file.wav"), "audio/wav")

    def test_unknown(self):
        self.assertEqual(
            transcribe._guess_mime("file.xyz"), "application/octet-stream"
        )


class TestParseArgs(unittest.TestCase):
    def test_minimal(self):
        args = transcribe.parse_args([
            "--model", "whisper-1", "--file", "audio.mp3"
        ])
        self.assertEqual(args.model, "whisper-1")
        self.assertEqual(args.audio_file, "audio.mp3")
        self.assertEqual(args.response_format, "json")

    def test_all_args(self):
        args = transcribe.parse_args([
            "--model", "gpt-4o-transcribe", "--file", "meeting.wav",
            "--language", "en", "--prompt", "context",
            "--response-format", "srt", "--temperature", "0.2",
        ])
        self.assertEqual(args.language, "en")
        self.assertEqual(args.response_format, "srt")
        self.assertAlmostEqual(args.temperature, 0.2)


class TestMainMissingKey(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key(self):
        rc = transcribe.main(["--model", "whisper-1", "--file", "x.mp3"])
        self.assertEqual(rc, 1)


class TestMainFileNotFound(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    def test_missing_file(self):
        rc = transcribe.main([
            "--model", "whisper-1", "--file", "/nonexistent/audio.mp3"
        ])
        self.assertEqual(rc, 1)


class TestMainSuccess(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    @patch("transcribe._do_request")
    def test_outputs_transcription(self, mock_req):
        mock_req.return_value = '{"text": "Hello world"}'
        # Create a temp audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\xff\xfb\x90\x00" * 10)
            tmpfile = f.name
        try:
            rc = transcribe.main([
                "--model", "whisper-1", "--file", tmpfile
            ])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(tmpfile)


if __name__ == "__main__":
    unittest.main()
