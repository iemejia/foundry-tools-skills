#!/usr/bin/env python3
"""Integration tests for azure-ai-language skill (require live credentials).

Run:
    python3 tests/test_integration_azure_ai_language.py -v

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
from conftest import skip_reason_language  # noqa: E402

_SKIP_REASON = skip_reason_language()

# Import analyze.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-language",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("language_integ", _SCRIPT)
language = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(language)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
class TestLanguageIntegration(unittest.TestCase):
    """End-to-end tests against a live Azure AI Language resource."""

    def test_sentiment(self):
        """Verify sentiment analysis returns a valid result."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = language.main([
                "--task", "sentiment",
                "--text", "I absolutely love this product!",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue().strip())
        self.assertIn(data["sentiment"], ["positive", "neutral", "negative"])
        self.assertIn("scores", data)

    def test_entities(self):
        """Verify NER returns entities."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = language.main([
                "--task", "entities",
                "--text", "Microsoft was founded by Bill Gates.",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue().strip())
        names = [e["text"] for e in data.get("entities", [])]
        self.assertTrue(
            any("Microsoft" in n for n in names),
            "Expected Microsoft in entities: {}".format(names),
        )

    def test_key_phrases(self):
        """Verify key phrase extraction."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = language.main([
                "--task", "key-phrases",
                "--text", "The food quality was excellent and service was fast.",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue().strip())
        self.assertIn("keyPhrases", data)
        self.assertGreater(len(data["keyPhrases"]), 0)

    def test_language_detection(self):
        """Verify language detection on French text."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = language.main([
                "--task", "language-detection",
                "--text", "Bonjour le monde, comment allez-vous?",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue().strip())
        self.assertEqual(data["language"], "fr")

    def test_raw_output(self):
        """Verify --raw returns the full API response."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = language.main([
                "--task", "sentiment",
                "--text", "Hello",
                "--raw",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("kind", data)
        self.assertIn("results", data)


if __name__ == "__main__":
    unittest.main()
