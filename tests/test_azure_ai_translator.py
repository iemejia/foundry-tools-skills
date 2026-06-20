#!/usr/bin/env python3
"""Unit tests for skills/azure-ai-translator/scripts/translate.py."""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-translator",
    "scripts", "translate.py",
)
_spec = importlib.util.spec_from_file_location("translate", _SCRIPT)
translate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(translate)
sys.modules["translate"] = translate


class TestDetectEndpointType(unittest.TestCase):
    def test_global(self):
        self.assertEqual(
            translate.detect_endpoint_type(
                "https://api.cognitive.microsofttranslator.com"
            ),
            "global",
        )

    def test_custom(self):
        self.assertEqual(
            translate.detect_endpoint_type(
                "https://my-res.cognitiveservices.azure.com"
            ),
            "custom",
        )


class TestBuildUrl(unittest.TestCase):
    def test_global_single_target(self):
        url = translate.build_url(
            "https://api.cognitive.microsofttranslator.com", "3.0", ["fr"]
        )
        self.assertIn("/translate?", url)
        self.assertIn("to=fr", url)
        self.assertIn("api-version=3.0", url)
        self.assertNotIn("/translator/text/", url)

    def test_custom_endpoint(self):
        url = translate.build_url(
            "https://my-res.cognitiveservices.azure.com", "3.0", ["de"]
        )
        self.assertIn("/translator/text/v3.0/translate?", url)
        self.assertIn("to=de", url)

    def test_multiple_targets(self):
        url = translate.build_url(
            "https://api.cognitive.microsofttranslator.com", "3.0",
            ["fr", "de", "ja"],
        )
        self.assertIn("to=fr", url)
        self.assertIn("to=de", url)
        self.assertIn("to=ja", url)

    def test_from_lang(self):
        url = translate.build_url(
            "https://api.cognitive.microsofttranslator.com", "3.0",
            ["fr"], from_lang="en",
        )
        self.assertIn("from=en", url)

    def test_trailing_slash_stripped(self):
        url = translate.build_url(
            "https://api.cognitive.microsofttranslator.com/", "3.0", ["fr"]
        )
        self.assertNotIn("//translate", url)


class TestParseArgs(unittest.TestCase):
    def test_minimal(self):
        args = translate.parse_args(["--text", "hello", "--to", "fr"])
        self.assertEqual(args.texts, ["hello"])
        self.assertEqual(args.to_langs, ["fr"])
        self.assertIsNone(args.from_lang)
        self.assertFalse(args.raw)

    def test_all_args(self):
        args = translate.parse_args([
            "--text", "hi", "--text", "bye",
            "--to", "fr", "--to", "de",
            "--from", "en",
            "--endpoint", "https://my-res.cognitiveservices.azure.com",
            "--region", "eastus",
            "--retries", "5",
            "--raw",
        ])
        self.assertEqual(len(args.texts), 2)
        self.assertEqual(len(args.to_langs), 2)
        self.assertEqual(args.from_lang, "en")
        self.assertEqual(args.retries, 5)
        self.assertTrue(args.raw)


class TestMainMissingKey(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key(self):
        rc = translate.main(["--text", "hi", "--to", "fr"])
        self.assertEqual(rc, 1)


class TestMainMissingRegionGlobal(unittest.TestCase):
    @patch.dict(os.environ, {"AZURE_TRANSLATOR_API_KEY": "k"}, clear=True)
    def test_global_no_region(self):
        rc = translate.main(["--text", "hi", "--to", "fr"])
        self.assertEqual(rc, 1)


class TestMainCustomEndpointNoRegion(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"AZURE_TRANSLATOR_API_KEY": "k"},
        clear=True,
    )
    @patch("translate._do_request")
    def test_custom_endpoint_ok(self, mock_req):
        mock_req.return_value = [
            {"translations": [{"text": "Bonjour", "to": "fr"}]}
        ]
        rc = translate.main([
            "--text", "Hello",
            "--to", "fr",
            "--endpoint", "https://my-res.cognitiveservices.azure.com",
        ])
        self.assertEqual(rc, 0)


class TestMainSuccess(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"AZURE_TRANSLATOR_API_KEY": "k", "AZURE_TRANSLATOR_REGION": "eastus"},
        clear=True,
    )
    @patch("translate._do_request")
    def test_single_translation(self, mock_req):
        mock_req.return_value = [
            {
                "detectedLanguage": {"language": "en", "score": 1.0},
                "translations": [{"text": "Bonjour", "to": "fr"}],
            }
        ]
        rc = translate.main(["--text", "Hello", "--to", "fr"])
        self.assertEqual(rc, 0)

    @patch.dict(
        os.environ,
        {"AZURE_TRANSLATOR_API_KEY": "k", "AZURE_TRANSLATOR_REGION": "eastus"},
        clear=True,
    )
    @patch("translate._do_request")
    def test_raw_output(self, mock_req):
        mock_req.return_value = [
            {"translations": [{"text": "Hola", "to": "es"}]}
        ]
        rc = translate.main(["--text", "Hello", "--to", "es", "--raw"])
        self.assertEqual(rc, 0)


class TestHintForHttpError(unittest.TestCase):
    def test_401(self):
        hint = translate._hint_for_http_error(401, "")
        self.assertIn("AZURE_TRANSLATOR_API_KEY", hint)

    def test_400(self):
        hint = translate._hint_for_http_error(400, "invalid language")
        self.assertIn("Bad request", hint)

    def test_429(self):
        hint = translate._hint_for_http_error(429, "")
        self.assertIn("Rate limited", hint)


if __name__ == "__main__":
    unittest.main()
