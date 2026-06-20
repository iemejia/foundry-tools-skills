#!/usr/bin/env python3
"""Integration tests for openai-transcription skill (require live credentials).

Run:
    python3 tests/test_integration_openai_transcription.py -v

Requires AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT (or OPENAI_API_KEY for OpenAI
direct) and a test audio file. A small WAV is generated synthetically.
Tests are skipped gracefully when no credentials or deployment are available.
"""

import importlib.util
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import skip_reason_openai  # noqa: E402

_SKIP_REASON = skip_reason_openai()
_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
_TRANSCRIPTION_DEPLOYMENT = os.environ.get("AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT")

# Import transcribe.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-transcription",
    "scripts", "transcribe.py"
)
_spec = importlib.util.spec_from_file_location("transcribe_integ", _SCRIPT)
transcribe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transcribe)


def _make_silent_wav(path, duration_s=1, sample_rate=16000):
    """Create a minimal silent WAV file for testing."""
    num_samples = sample_rate * duration_s
    data_size = num_samples * 2  # 16-bit mono
    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))       # chunk size
        f.write(struct.pack("<H", 1))        # PCM
        f.write(struct.pack("<H", 1))        # mono
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * 2))  # byte rate
        f.write(struct.pack("<H", 2))        # block align
        f.write(struct.pack("<H", 16))       # bits per sample
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
@unittest.skipUnless(
    _TRANSCRIPTION_DEPLOYMENT,
    "No AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT set"
)
class TestTranscriptionIntegration(unittest.TestCase):
    """End-to-end tests against a live Azure OpenAI transcription deployment."""

    def test_transcribe_silent_audio(self):
        """Transcribe a silent WAV — should return empty or minimal text."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wavpath = f.name
        _make_silent_wav(wavpath)
        try:
            rc = transcribe.main([
                "--endpoint", _ENDPOINT,
                "--model", _TRANSCRIPTION_DEPLOYMENT,
                "--file", wavpath,
            ])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(wavpath)

    def test_text_format(self):
        """Verify --response-format text returns plain text."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wavpath = f.name
        _make_silent_wav(wavpath)
        try:
            rc = transcribe.main([
                "--endpoint", _ENDPOINT,
                "--model", _TRANSCRIPTION_DEPLOYMENT,
                "--file", wavpath,
                "--response-format", "text",
            ])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(wavpath)

    def test_invalid_deployment_gives_error(self):
        """Verify structured error for a non-existent deployment."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wavpath = f.name
        _make_silent_wav(wavpath)
        try:
            rc = transcribe.main([
                "--endpoint", _ENDPOINT,
                "--model", "nonexistent-transcribe-xyz",
                "--file", wavpath,
                "--retries", "0",
            ])
            self.assertNotEqual(rc, 0)
        finally:
            os.unlink(wavpath)


if __name__ == "__main__":
    unittest.main()
