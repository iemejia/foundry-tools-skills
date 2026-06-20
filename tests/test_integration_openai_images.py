#!/usr/bin/env python3
"""Integration tests for openai-images skill (require live credentials).

Run:
    python3 tests/test_integration_openai_images.py -v

Requires AZURE_OPENAI_IMAGE_DEPLOYMENT (or OPENAI_API_KEY for OpenAI direct).
Tests are skipped gracefully when no credentials or image deployment are
available.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(__file__))
from conftest import skip_reason_openai  # noqa: E402

_SKIP_REASON = skip_reason_openai()
_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
_IMAGE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_IMAGE_DEPLOYMENT")

# Import generate.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-images", "scripts", "generate.py"
)
_spec = importlib.util.spec_from_file_location("generate_integ", _SCRIPT)
generate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
@unittest.skipUnless(_IMAGE_DEPLOYMENT, "No AZURE_OPENAI_IMAGE_DEPLOYMENT set")
class TestImagesIntegration(unittest.TestCase):
    """End-to-end tests against a live Azure OpenAI image deployment."""

    def test_generate_image(self):
        """Generate an image and verify it saves to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = generate.main([
                "--endpoint", _ENDPOINT,
                "--model", _IMAGE_DEPLOYMENT,
                "--prompt", "A simple blue square on white background",
                "--size", "1024x1024",
                "--output-dir", tmpdir,
            ])
            self.assertEqual(rc, 0)
            files = os.listdir(tmpdir)
            self.assertGreater(len(files), 0)
            fpath = os.path.join(tmpdir, files[0])
            self.assertGreater(os.path.getsize(fpath), 100)

    def test_raw_json_output(self):
        """Verify --raw returns valid JSON with image data."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = generate.main([
                "--endpoint", _ENDPOINT,
                "--model", _IMAGE_DEPLOYMENT,
                "--prompt", "A red circle",
                "--size", "1024x1024",
                "--raw",
            ])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("data", data)
        self.assertGreater(len(data["data"]), 0)

    def test_invalid_deployment_gives_error(self):
        """Verify structured error for a non-existent deployment."""
        rc = generate.main([
            "--endpoint", _ENDPOINT,
            "--model", "nonexistent-image-model-xyz",
            "--prompt", "test",
            "--retries", "0",
        ])
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
