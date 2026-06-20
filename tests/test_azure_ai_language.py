#!/usr/bin/env python3
"""Unit tests for skills/azure-ai-language/scripts/analyze.py."""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-language",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("language_analyze", _SCRIPT)
language = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(language)
sys.modules["language_analyze"] = language


class TestBuildUrl(unittest.TestCase):
    def test_basic(self):
        url = language.build_url(
            "https://x.cognitiveservices.azure.com", "2023-04-01"
        )
        self.assertIn("/language/:analyze-text?", url)
        self.assertIn("api-version=2023-04-01", url)

    def test_trailing_slash(self):
        url = language.build_url(
            "https://x.cognitiveservices.azure.com/", "2023-04-01"
        )
        self.assertNotIn("//language", url)


class TestBuildRequestBody(unittest.TestCase):
    def test_sentiment(self):
        body = language.build_request_body(
            "sentiment", ["I love this!"], language="en"
        )
        self.assertEqual(body["kind"], "SentimentAnalysis")
        self.assertEqual(len(body["analysisInput"]["documents"]), 1)
        self.assertEqual(
            body["analysisInput"]["documents"][0]["language"], "en"
        )

    def test_language_detection_no_lang(self):
        body = language.build_request_body(
            "language-detection", ["Bonjour"], language="en"
        )
        self.assertEqual(body["kind"], "LanguageDetection")
        # language-detection should not include a language hint
        self.assertNotIn(
            "language", body["analysisInput"]["documents"][0]
        )

    def test_batch(self):
        body = language.build_request_body(
            "entities", ["text1", "text2", "text3"]
        )
        self.assertEqual(len(body["analysisInput"]["documents"]), 3)
        self.assertEqual(
            body["analysisInput"]["documents"][0]["id"], "1"
        )
        self.assertEqual(
            body["analysisInput"]["documents"][2]["id"], "3"
        )

    def test_pii(self):
        body = language.build_request_body("pii", ["My SSN is 123-45-6789"])
        self.assertEqual(body["kind"], "PiiEntityRecognition")


class TestFormatResult(unittest.TestCase):
    def test_sentiment(self):
        result = {
            "results": {
                "documents": [
                    {
                        "id": "1",
                        "sentiment": "positive",
                        "confidenceScores": {
                            "positive": 0.99, "neutral": 0.01, "negative": 0.0
                        },
                        "sentences": [
                            {
                                "text": "I love this!",
                                "sentiment": "positive",
                                "confidenceScores": {
                                    "positive": 0.99,
                                    "neutral": 0.01,
                                    "negative": 0.0,
                                },
                            }
                        ],
                    }
                ]
            }
        }
        out = language._format_result("sentiment", result)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["sentiment"], "positive")
        self.assertIn("sentences", out[0])

    def test_entities(self):
        result = {
            "results": {
                "documents": [
                    {
                        "id": "1",
                        "entities": [
                            {
                                "text": "Microsoft",
                                "category": "Organization",
                                "subcategory": "",
                                "confidenceScore": 0.95,
                            }
                        ],
                    }
                ]
            }
        }
        out = language._format_result("entities", result)
        self.assertEqual(out[0]["entities"][0]["text"], "Microsoft")
        self.assertEqual(out[0]["entities"][0]["category"], "Organization")

    def test_key_phrases(self):
        result = {
            "results": {
                "documents": [
                    {"id": "1", "keyPhrases": ["great product", "fast delivery"]}
                ]
            }
        }
        out = language._format_result("key-phrases", result)
        self.assertEqual(out[0]["keyPhrases"], ["great product", "fast delivery"])

    def test_pii(self):
        result = {
            "results": {
                "documents": [
                    {
                        "id": "1",
                        "redactedText": "My SSN is ***********",
                        "entities": [
                            {
                                "text": "123-45-6789",
                                "category": "USSocialSecurityNumber",
                                "subcategory": "",
                                "confidenceScore": 0.99,
                            }
                        ],
                    }
                ]
            }
        }
        out = language._format_result("pii", result)
        self.assertIn("***", out[0]["redactedText"])

    def test_language_detection(self):
        result = {
            "results": {
                "documents": [
                    {
                        "id": "1",
                        "detectedLanguage": {
                            "name": "French",
                            "iso6391Name": "fr",
                            "confidenceScore": 1.0,
                        },
                    }
                ]
            }
        }
        out = language._format_result("language-detection", result)
        self.assertEqual(out[0]["language"], "fr")
        self.assertEqual(out[0]["name"], "French")

    def test_empty(self):
        result = {"results": {"documents": []}}
        out = language._format_result("sentiment", result)
        self.assertEqual(out, [])


class TestParseArgs(unittest.TestCase):
    def test_minimal(self):
        args = language.parse_args([
            "--task", "sentiment", "--text", "hello"
        ])
        self.assertEqual(args.task, "sentiment")
        self.assertEqual(args.texts, ["hello"])

    def test_all_args(self):
        args = language.parse_args([
            "--task", "entities",
            "--text", "t1", "--text", "t2",
            "--language", "en",
            "--retries", "5",
            "--raw",
        ])
        self.assertEqual(len(args.texts), 2)
        self.assertEqual(args.language, "en")
        self.assertTrue(args.raw)


class TestMainMissingEndpoint(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_endpoint(self):
        rc = language.main(["--task", "sentiment", "--text", "hi"])
        self.assertEqual(rc, 1)


class TestMainMissingKey(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"AZURE_AI_LANGUAGE_ENDPOINT": "https://x.cognitiveservices.azure.com"},
        clear=True,
    )
    def test_no_key(self):
        rc = language.main(["--task", "sentiment", "--text", "hi"])
        self.assertEqual(rc, 1)


class TestMainSuccess(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "AZURE_AI_LANGUAGE_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_AI_LANGUAGE_API_KEY": "k",
        },
        clear=True,
    )
    @patch("language_analyze._do_request")
    def test_sentiment(self, mock_req):
        mock_req.return_value = {
            "kind": "SentimentAnalysisResults",
            "results": {
                "documents": [
                    {
                        "id": "1",
                        "sentiment": "positive",
                        "confidenceScores": {
                            "positive": 0.99, "neutral": 0.01, "negative": 0.0
                        },
                        "sentences": [],
                    }
                ],
                "errors": [],
            },
        }
        rc = language.main(["--task", "sentiment", "--text", "Great!"])
        self.assertEqual(rc, 0)

    @patch.dict(
        os.environ,
        {
            "AZURE_AI_LANGUAGE_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_AI_LANGUAGE_API_KEY": "k",
        },
        clear=True,
    )
    @patch("language_analyze._do_request")
    def test_raw_output(self, mock_req):
        mock_req.return_value = {"kind": "test", "results": {"documents": []}}
        rc = language.main([
            "--task", "entities", "--text", "test", "--raw"
        ])
        self.assertEqual(rc, 0)


class TestHintForHttpError(unittest.TestCase):
    def test_401(self):
        hint = language._hint_for_http_error(401, "")
        self.assertIn("AZURE_AI_LANGUAGE_API_KEY", hint)

    def test_429(self):
        hint = language._hint_for_http_error(429, "")
        self.assertIn("Rate limited", hint)


if __name__ == "__main__":
    unittest.main()
