#!/usr/bin/env python3
"""Integration tests for openai-tts skill (require live credentials).

Run:
    python3 tests/test_integration_openai_tts.py -v

Requires AZURE_OPENAI_TTS_DEPLOYMENT (or OPENAI_API_KEY for OpenAI direct).
Tests are skipped gracefully when no credentials or TTS deployment are
available.
"""

import importlib.util
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import skip_reason_openai  # noqa: E402

_SKIP_REASON = skip_reason_openai()
_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
_TTS_DEPLOYMENT = os.environ.get("AZURE_OPENAI_TTS_DEPLOYMENT")

# Import tts.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-tts", "scripts", "tts.py"
)
_spec = importlib.util.spec_from_file_location("tts_integ", _SCRIPT)
tts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tts)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
@unittest.skipUnless(_TTS_DEPLOYMENT, "No AZURE_OPENAI_TTS_DEPLOYMENT set")
class TestTTSIntegration(unittest.TestCase):
    """End-to-end tests against a live Azure OpenAI TTS deployment."""

    def test_generate_speech(self):
        """Generate audio and verify it saves a non-empty file."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            outpath = f.name
        try:
            rc = tts.main([
                "--endpoint", _ENDPOINT,
                "--model", _TTS_DEPLOYMENT,
                "--voice", "alloy",
                "--input", "Integration test: hello world.",
                "--output", outpath,
            ])
            self.assertEqual(rc, 0)
            self.assertGreater(os.path.getsize(outpath), 100)
        finally:
            if os.path.exists(outpath):
                os.unlink(outpath)

    def test_different_voice(self):
        """Verify different voices work."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            outpath = f.name
        try:
            rc = tts.main([
                "--endpoint", _ENDPOINT,
                "--model", _TTS_DEPLOYMENT,
                "--voice", "nova",
                "--input", "Testing nova voice.",
                "--output", outpath,
            ])
            self.assertEqual(rc, 0)
            self.assertGreater(os.path.getsize(outpath), 100)
        finally:
            if os.path.exists(outpath):
                os.unlink(outpath)

    def test_invalid_deployment_gives_error(self):
        """Verify structured error for a non-existent deployment."""
        rc = tts.main([
            "--endpoint", _ENDPOINT,
            "--model", "nonexistent-tts-xyz",
            "--voice", "alloy",
            "--input", "test",
            "--retries", "0",
        ])
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
