#!/usr/bin/env python3
"""Integration tests for azure-ai-speech scripts (synthesize.py + recognize.py).

Requires AZURE_AI_SPEECH_API_KEY and AZURE_AI_SPEECH_REGION
(auto-discovered via az CLI if available).
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest

# -- Credential discovery --
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from conftest import skip_reason_speech  # noqa: E402

_skip = skip_reason_speech()

# -- Load scripts --
_SYN_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-speech",
    "scripts", "synthesize.py",
)
_syn_spec = importlib.util.spec_from_file_location("synthesize_int", _SYN_SCRIPT)
synthesize = importlib.util.module_from_spec(_syn_spec)
_syn_spec.loader.exec_module(synthesize)
sys.modules["synthesize_int"] = synthesize

_REC_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-speech",
    "scripts", "recognize.py",
)
_rec_spec = importlib.util.spec_from_file_location("recognize_int", _REC_SCRIPT)
recognize = importlib.util.module_from_spec(_rec_spec)
_rec_spec.loader.exec_module(recognize)
sys.modules["recognize_int"] = recognize


@unittest.skipIf(_skip, _skip or "")
class TestSynthesizeIntegration(unittest.TestCase):
    """Live integration tests for Speech synthesize.py."""

    def test_basic_tts_mp3(self):
        """Synthesize a short phrase to MP3."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            outpath = f.name
        try:
            rc = synthesize.main([
                "--text", "Hello, this is a test.",
                "--voice", "en-US-JennyNeural",
                "-o", outpath,
            ])
            self.assertEqual(rc, 0)
            self.assertGreater(os.path.getsize(outpath), 100)
        finally:
            if os.path.exists(outpath):
                os.unlink(outpath)

    def test_tts_wav_format(self):
        """Synthesize to WAV format."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            outpath = f.name
        try:
            rc = synthesize.main([
                "--text", "Testing WAV output.",
                "--voice", "en-US-GuyNeural",
                "--output-format", "wav",
                "-o", outpath,
            ])
            self.assertEqual(rc, 0)
            self.assertGreater(os.path.getsize(outpath), 100)
        finally:
            if os.path.exists(outpath):
                os.unlink(outpath)

    def test_list_voices(self):
        """List voices should succeed."""
        rc = synthesize.main(["--list-voices"])
        self.assertEqual(rc, 0)

    def test_prosody_rate_pitch(self):
        """Synthesize with rate and pitch control."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            outpath = f.name
        try:
            rc = synthesize.main([
                "--text", "Testing prosody controls.",
                "--voice", "en-US-JennyNeural",
                "--rate", "fast",
                "--pitch", "high",
                "-o", outpath,
            ])
            self.assertEqual(rc, 0)
            self.assertGreater(os.path.getsize(outpath), 100)
        finally:
            if os.path.exists(outpath):
                os.unlink(outpath)


@unittest.skipIf(_skip, _skip or "")
class TestSynthThenRecognize(unittest.TestCase):
    """Round-trip: synthesize speech then recognize it."""

    def test_round_trip(self):
        """Synthesize WAV then recognize it — recognized text should exist."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            rc = synthesize.main([
                "--text", "Hello world",
                "--voice", "en-US-JennyNeural",
                "--output-format", "wav",
                "-o", wav_path,
            ])
            self.assertEqual(rc, 0, "TTS failed")
            self.assertGreater(os.path.getsize(wav_path), 100)

            rc = recognize.main([
                "--file", wav_path,
                "--language", "en-US",
            ])
            self.assertEqual(rc, 0, "STT failed")
        finally:
            if os.path.exists(wav_path):
                os.unlink(wav_path)


@unittest.skipIf(_skip, _skip or "")
class TestRecognizeIntegration(unittest.TestCase):
    """Live integration tests for Speech recognize.py."""

    def test_detailed_format(self):
        """Synthesize then recognize with detailed format."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            rc = synthesize.main([
                "--text", "This is a test of detailed recognition.",
                "--voice", "en-US-JennyNeural",
                "--output-format", "wav",
                "-o", wav_path,
            ])
            self.assertEqual(rc, 0, "TTS failed")

            rc = recognize.main([
                "--file", wav_path,
                "--language", "en-US",
                "--format", "detailed",
            ])
            self.assertEqual(rc, 0, "STT detailed failed")
        finally:
            if os.path.exists(wav_path):
                os.unlink(wav_path)


if __name__ == "__main__":
    unittest.main()
