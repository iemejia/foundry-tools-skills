#!/usr/bin/env python3
"""Integration tests for azure-ai-translator skill (require live credentials).

Run:
    python3 tests/test_integration_azure_ai_translator.py -v

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
from conftest import skip_reason_translator  # noqa: E402

_SKIP_REASON = skip_reason_translator()

# Import translate.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-translator",
    "scripts", "translate.py",
)
_spec = importlib.util.spec_from_file_location("translate_integ", _SCRIPT)
translate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(translate)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
class TestTranslatorIntegration(unittest.TestCase):
    """End-to-end tests against a live Azure Translator resource."""

    def test_simple_translation(self):
        """Translate 'Hello' to French."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = translate.main(["--text", "Hello", "--to", "fr"])
        self.assertEqual(rc, 0)
        output = buf.getvalue().strip()
        data = json.loads(output)
        self.assertEqual(data["to"], "fr")
        self.assertTrue(len(data["text"]) > 0)

    def test_multiple_targets(self):
        """Translate to multiple languages at once."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = translate.main([
                "--text", "Good morning", "--to", "es", "--to", "de",
            ])
        self.assertEqual(rc, 0)
        lines = buf.getvalue().strip().split("\n")
        self.assertEqual(len(lines), 2)
        langs = {json.loads(line)["to"] for line in lines}
        self.assertEqual(langs, {"es", "de"})

    def test_raw_output(self):
        """Verify --raw returns valid full API JSON."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = translate.main([
                "--text", "Hello", "--to", "ja", "--raw",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIn("translations", data[0])

    def test_auto_detect(self):
        """Verify auto-detection works (no --from)."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = translate.main([
                "--text", "Bonjour le monde", "--to", "en", "--raw",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        detected = data[0].get("detectedLanguage", {})
        self.assertEqual(detected.get("language"), "fr")


if __name__ == "__main__":
    unittest.main()
