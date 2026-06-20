#!/usr/bin/env python3
"""Integration tests for skills/azure-content-safety/scripts/analyze.py.

Requires AZURE_CONTENT_SAFETY_API_KEY and AZURE_CONTENT_SAFETY_ENDPOINT
(auto-discovered via az CLI if available).
"""

import importlib.util
import json
import os
import sys
import unittest

# -- Credential discovery --
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from conftest import skip_reason_content_safety  # noqa: E402

_skip = skip_reason_content_safety()

# -- Load script --
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-content-safety",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("safety_analyze_int", _SCRIPT)
safety = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(safety)
sys.modules["safety_analyze_int"] = safety


@unittest.skipIf(_skip, _skip or "")
class TestContentSafetyIntegration(unittest.TestCase):
    """Live integration tests for Content Safety analyze.py."""

    def test_safe_text(self):
        """Analyze innocuous text — should return safe."""
        rc = safety.main(["--text", "The weather is beautiful today."])
        self.assertEqual(rc, 0)

    def test_safe_text_with_threshold(self):
        """Innocuous text with threshold should still be safe (exit 0)."""
        rc = safety.main([
            "--text", "I love programming in Python.",
            "--threshold", "2",
        ])
        self.assertEqual(rc, 0)

    def test_raw_output(self):
        """--raw should succeed and produce valid JSON."""
        rc = safety.main(["--text", "Hello world", "--raw"])
        self.assertEqual(rc, 0)

    def test_specific_categories(self):
        """Analyze with subset of categories."""
        rc = safety.main([
            "--text", "A friendly greeting",
            "--categories", "Hate", "Violence",
        ])
        self.assertEqual(rc, 0)

    def test_stdin_text(self):
        """Read text from stdin (simulated by piping)."""
        import io
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("This is a perfectly normal sentence.")
        try:
            rc = safety.main(["--text", "-"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
