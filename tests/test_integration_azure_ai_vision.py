#!/usr/bin/env python3
"""Integration tests for azure-ai-vision skill (require live credentials).

Run:
    python3 tests/test_integration_azure_ai_vision.py -v

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
from conftest import skip_reason_vision  # noqa: E402

_SKIP_REASON = skip_reason_vision()

# Import analyze.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-vision",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("vision_integ", _SCRIPT)
vision = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vision)


def _make_white_bmp(path, width=100, height=100):
    """Create a minimal white BMP image for testing."""
    row_size = (width * 3 + 3) & ~3
    data_size = row_size * height
    file_size = 54 + data_size
    with open(path, "wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<I", file_size))
        f.write(struct.pack("<HH", 0, 0))
        f.write(struct.pack("<I", 54))
        f.write(struct.pack("<I", 40))
        f.write(struct.pack("<i", width))
        f.write(struct.pack("<i", height))
        f.write(struct.pack("<HH", 1, 24))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", data_size))
        f.write(struct.pack("<ii", 2835, 2835))
        f.write(struct.pack("<II", 0, 0))
        row = b"\xff" * (width * 3)
        padding = b"\x00" * (row_size - width * 3)
        for _ in range(height):
            f.write(row + padding)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON or "")
class TestVisionIntegration(unittest.TestCase):
    """End-to-end tests against a live Azure Computer Vision resource."""

    def test_caption_and_tags(self):
        """Analyze a blank BMP with caption and tags."""
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            bmppath = f.name
        _make_white_bmp(bmppath)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = vision.main([
                    "--file", bmppath,
                    "--features", "caption", "tags",
                ])
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            # Caption should be present (even for blank image)
            self.assertIn("caption", data)
        finally:
            os.unlink(bmppath)

    def test_read_ocr(self):
        """Verify OCR feature runs without error."""
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            bmppath = f.name
        _make_white_bmp(bmppath)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = vision.main([
                    "--file", bmppath,
                    "--features", "read",
                ])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(bmppath)

    def test_raw_output(self):
        """Verify --raw returns the full API response."""
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            bmppath = f.name
        _make_white_bmp(bmppath)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = vision.main([
                    "--file", bmppath,
                    "--features", "caption",
                    "--raw",
                ])
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertIn("captionResult", data)
        finally:
            os.unlink(bmppath)


if __name__ == "__main__":
    unittest.main()
