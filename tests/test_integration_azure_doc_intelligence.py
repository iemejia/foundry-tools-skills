#!/usr/bin/env python3
"""Integration tests for azure-doc-intelligence skill (require live credentials).

Run:
    python3 tests/test_integration_azure_doc_intelligence.py -v

Credentials are auto-discovered via az CLI if env vars are not set.
Tests are skipped gracefully when no credentials are available.
A minimal BMP image is generated synthetically for testing.
"""

import importlib.util
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(__file__))
from conftest import skip_reason_doc_intelligence  # noqa: E402

_SKIP_REASON = skip_reason_doc_intelligence()

# Import analyze.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-doc-intelligence",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("analyze_integ", _SCRIPT)
analyze = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analyze)


def _make_white_bmp(path, width=100, height=100):
    """Create a minimal white BMP image for testing."""
    row_size = (width * 3 + 3) & ~3  # rows padded to 4-byte boundary
    data_size = row_size * height
    file_size = 54 + data_size

    with open(path, "wb") as f:
        # File header (14 bytes)
        f.write(b"BM")
        f.write(struct.pack("<I", file_size))
        f.write(struct.pack("<HH", 0, 0))
        f.write(struct.pack("<I", 54))
        # Info header (40 bytes)
        f.write(struct.pack("<I", 40))
        f.write(struct.pack("<i", width))
        f.write(struct.pack("<i", height))
        f.write(struct.pack("<HH", 1, 24))
        f.write(struct.pack("<I", 0))  # no compression
        f.write(struct.pack("<I", data_size))
        f.write(struct.pack("<ii", 2835, 2835))  # pixels per meter
        f.write(struct.pack("<II", 0, 0))
        # Pixel data (all white)
        row = b"\xff" * (width * 3)
        padding = b"\x00" * (row_size - width * 3)
        for _ in range(height):
            f.write(row + padding)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
class TestDocIntelligenceIntegration(unittest.TestCase):
    """End-to-end tests against a live Document Intelligence resource."""

    def test_analyze_image(self):
        """Analyze a blank BMP with prebuilt-read (OCR)."""
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            bmppath = f.name
        _make_white_bmp(bmppath)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = analyze.main([
                    "--model", "prebuilt-read",
                    "--file", bmppath,
                ])
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertIn("content", data)
            self.assertIn("pages", data)
        finally:
            os.unlink(bmppath)

    def test_analyze_raw_output(self):
        """Verify --raw returns the full API response."""
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            bmppath = f.name
        _make_white_bmp(bmppath)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = analyze.main([
                    "--model", "prebuilt-read",
                    "--file", bmppath,
                    "--raw",
                ])
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertIn("status", data)
            self.assertEqual(data["status"], "succeeded")
            self.assertIn("analyzeResult", data)
        finally:
            os.unlink(bmppath)

    def test_invalid_model_gives_error(self):
        """Verify structured error for a non-existent model."""
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            bmppath = f.name
        _make_white_bmp(bmppath)
        try:
            rc = analyze.main([
                "--model", "nonexistent-model-xyz",
                "--file", bmppath,
            ])
            self.assertNotEqual(rc, 0)
        finally:
            os.unlink(bmppath)


if __name__ == "__main__":
    unittest.main()
