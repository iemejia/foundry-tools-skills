#!/usr/bin/env python3
"""Unit tests for azure-ai-speech scripts (synthesize.py + recognize.py)."""

import importlib.util
import json
import os
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

# -- Load synthesize.py --
_SYN_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-speech",
    "scripts", "synthesize.py",
)
_syn_spec = importlib.util.spec_from_file_location("synthesize", _SYN_SCRIPT)
synthesize = importlib.util.module_from_spec(_syn_spec)
_syn_spec.loader.exec_module(synthesize)
sys.modules["synthesize"] = synthesize

# -- Load recognize.py --
_REC_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-speech",
    "scripts", "recognize.py",
)
_rec_spec = importlib.util.spec_from_file_location("recognize", _REC_SCRIPT)
recognize = importlib.util.module_from_spec(_rec_spec)
_rec_spec.loader.exec_module(recognize)
sys.modules["recognize"] = recognize

_ENV = {
    "AZURE_AI_SPEECH_API_KEY": "k",
    "AZURE_AI_SPEECH_REGION": "eastus",
}


# ===== synthesize.py tests =====


class TestBuildTtsUrl(unittest.TestCase):
    def test_region(self):
        url = synthesize.build_tts_url(region="eastus")
        self.assertEqual(
            url, "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1"
        )

    def test_endpoint(self):
        url = synthesize.build_tts_url(
            endpoint="https://my-speech.cognitiveservices.azure.com"
        )
        self.assertIn("my-speech.cognitiveservices.azure.com/cognitiveservices/v1", url)

    def test_trailing_slash(self):
        url = synthesize.build_tts_url(
            endpoint="https://my-speech.cognitiveservices.azure.com/"
        )
        self.assertNotIn("//cognitiveservices", url)


class TestBuildSsml(unittest.TestCase):
    def test_basic(self):
        ssml = synthesize.build_ssml("Hello", "en-US-JennyNeural")
        self.assertIn("xml:lang='en-US'", ssml)
        self.assertIn("name='en-US-JennyNeural'", ssml)
        self.assertIn("Hello", ssml)

    def test_xml_escape(self):
        ssml = synthesize.build_ssml("A & B < C", "en-US-JennyNeural")
        self.assertIn("A &amp; B &lt; C", ssml)

    def test_prosody(self):
        ssml = synthesize.build_ssml(
            "Hi", "en-US-JennyNeural", rate="slow", pitch="high"
        )
        self.assertIn("<prosody", ssml)
        self.assertIn("rate='slow'", ssml)
        self.assertIn("pitch='high'", ssml)

    def test_lang_extraction(self):
        ssml = synthesize.build_ssml("Bonjour", "fr-FR-DeniseNeural")
        self.assertIn("xml:lang='fr-FR'", ssml)


class TestResolveOutputFormat(unittest.TestCase):
    def test_alias(self):
        self.assertEqual(
            synthesize.resolve_output_format("mp3"),
            "audio-24khz-160kbitrate-mono-mp3",
        )

    def test_full_string(self):
        full = "audio-48khz-192kbitrate-mono-mp3"
        self.assertEqual(synthesize.resolve_output_format(full), full)


class TestSynthParseArgs(unittest.TestCase):
    def test_minimal(self):
        args = synthesize.parse_args(["--text", "Hello"])
        self.assertEqual(args.text, "Hello")
        self.assertEqual(args.voice, "en-US-JennyNeural")
        self.assertEqual(args.output_format, "mp3")

    def test_all_args(self):
        args = synthesize.parse_args([
            "--text", "Hi", "--voice", "en-US-GuyNeural",
            "--output-format", "wav", "-o", "out.wav",
            "--rate", "fast", "--pitch", "high",
            "--region", "westus",
        ])
        self.assertEqual(args.voice, "en-US-GuyNeural")
        self.assertEqual(args.output_format, "wav")
        self.assertEqual(args.rate, "fast")


class TestSynthMissingRegion(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_region_or_endpoint(self):
        rc = synthesize.main(["--text", "hi"])
        self.assertEqual(rc, 1)


class TestSynthMissingKey(unittest.TestCase):
    @patch.dict(os.environ, {"AZURE_AI_SPEECH_REGION": "eastus"}, clear=True)
    def test_no_key(self):
        rc = synthesize.main(["--text", "hi"])
        self.assertEqual(rc, 1)


class TestSynthSuccess(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("synthesize._do_request")
    def test_saves_audio(self, mock_req):
        mock_req.return_value = b"\xff\xfb\x90\x00" * 100
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            outpath = f.name
        try:
            rc = synthesize.main(["--text", "Hello", "-o", outpath])
            self.assertEqual(rc, 0)
            self.assertGreater(os.path.getsize(outpath), 0)
        finally:
            os.unlink(outpath)


class TestSynthListVoices(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("synthesize._list_voices")
    def test_list_voices(self, mock_list):
        mock_list.return_value = [
            {"ShortName": "en-US-JennyNeural", "Locale": "en-US",
             "Gender": "Female", "LocalName": "Jenny"},
        ]
        rc = synthesize.main(["--list-voices"])
        self.assertEqual(rc, 0)


# ===== recognize.py tests =====


class TestBuildSttUrl(unittest.TestCase):
    def test_region(self):
        url = recognize.build_stt_url(region="eastus", language="en-US")
        self.assertIn("eastus.stt.speech.microsoft.com", url)
        self.assertIn("language=en-US", url)

    def test_endpoint(self):
        url = recognize.build_stt_url(
            endpoint="https://my-speech.cognitiveservices.azure.com",
            language="fr-FR",
        )
        self.assertIn("language=fr-FR", url)


class TestGuessContentType(unittest.TestCase):
    def test_wav(self):
        self.assertEqual(recognize._guess_content_type("file.wav"), "audio/wav")

    def test_mp3(self):
        self.assertEqual(recognize._guess_content_type("file.mp3"), "audio/mpeg")

    def test_unknown(self):
        self.assertEqual(recognize._guess_content_type("file.xyz"), "audio/wav")


class TestRecParseArgs(unittest.TestCase):
    def test_minimal(self):
        args = recognize.parse_args(["--file", "audio.wav"])
        self.assertEqual(args.file_path, "audio.wav")
        self.assertEqual(args.language, "en-US")
        self.assertEqual(args.output_format, "simple")

    def test_all_args(self):
        args = recognize.parse_args([
            "--file", "a.mp3", "--language", "fr-FR",
            "--format", "detailed", "--profanity", "raw",
        ])
        self.assertEqual(args.language, "fr-FR")
        self.assertEqual(args.output_format, "detailed")
        self.assertEqual(args.profanity, "raw")


class TestRecMissingRegion(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_region(self):
        rc = recognize.main(["--file", "a.wav"])
        self.assertEqual(rc, 1)


class TestRecMissingKey(unittest.TestCase):
    @patch.dict(os.environ, {"AZURE_AI_SPEECH_REGION": "eastus"}, clear=True)
    def test_no_key(self):
        rc = recognize.main(["--file", "a.wav"])
        self.assertEqual(rc, 1)


class TestRecFileNotFound(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    def test_missing(self):
        rc = recognize.main(["--file", "/nonexistent/audio.wav"])
        self.assertEqual(rc, 1)


class TestRecSuccess(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("recognize._do_request")
    def test_simple(self, mock_req):
        mock_req.return_value = {
            "RecognitionStatus": "Success",
            "DisplayText": "Hello world.",
        }
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"\x00" * 100)
            tmpfile = f.name
        try:
            rc = recognize.main(["--file", tmpfile])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(tmpfile)

    @patch.dict(os.environ, _ENV, clear=True)
    @patch("recognize._do_request")
    def test_no_match(self, mock_req):
        mock_req.return_value = {"RecognitionStatus": "NoMatch"}
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"\x00" * 100)
            tmpfile = f.name
        try:
            rc = recognize.main(["--file", tmpfile])
            self.assertEqual(rc, 1)
        finally:
            os.unlink(tmpfile)


class TestRecognitionHint(unittest.TestCase):
    def test_no_match(self):
        hint = recognize._recognition_hint("NoMatch")
        self.assertIn("No speech detected", hint)

    def test_error(self):
        hint = recognize._recognition_hint("Error")
        self.assertIn("format", hint)


if __name__ == "__main__":
    unittest.main()
