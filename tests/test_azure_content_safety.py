#!/usr/bin/env python3
"""Unit tests for skills/azure-content-safety/scripts/analyze.py."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-content-safety",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("safety_analyze", _SCRIPT)
safety = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(safety)
sys.modules["safety_analyze"] = safety

_ENV = {
    "AZURE_CONTENT_SAFETY_ENDPOINT": "https://x.cognitiveservices.azure.com",
    "AZURE_CONTENT_SAFETY_API_KEY": "k",
}

_SAFE_RESPONSE = {
    "categoriesAnalysis": [
        {"category": "Hate", "severity": 0},
        {"category": "SelfHarm", "severity": 0},
        {"category": "Sexual", "severity": 0},
        {"category": "Violence", "severity": 0},
    ]
}

_FLAGGED_RESPONSE = {
    "categoriesAnalysis": [
        {"category": "Hate", "severity": 4},
        {"category": "SelfHarm", "severity": 0},
        {"category": "Sexual", "severity": 0},
        {"category": "Violence", "severity": 2},
    ]
}


class TestBuildUrl(unittest.TestCase):
    def test_text(self):
        url = safety.build_url(
            "https://x.cognitiveservices.azure.com", "2024-09-01", "text"
        )
        self.assertIn("/contentsafety/text:analyze", url)
        self.assertIn("api-version=2024-09-01", url)

    def test_image(self):
        url = safety.build_url(
            "https://x.cognitiveservices.azure.com", "2024-09-01", "image"
        )
        self.assertIn("/contentsafety/image:analyze", url)

    def test_trailing_slash(self):
        url = safety.build_url(
            "https://x.cognitiveservices.azure.com/", "2024-09-01", "text"
        )
        self.assertNotIn("//contentsafety", url)


class TestParseArgs(unittest.TestCase):
    def test_text(self):
        args = safety.parse_args(["--text", "hello"])
        self.assertEqual(args.text, "hello")
        self.assertIsNone(args.threshold)

    def test_file(self):
        args = safety.parse_args(["--file", "img.jpg"])
        self.assertEqual(args.file_path, "img.jpg")

    def test_url(self):
        args = safety.parse_args(["--url", "https://blob/img.jpg"])
        self.assertEqual(args.image_url, "https://blob/img.jpg")

    def test_threshold(self):
        args = safety.parse_args(["--text", "x", "--threshold", "2"])
        self.assertEqual(args.threshold, 2)


class TestMainMissingEndpoint(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_endpoint(self):
        rc = safety.main(["--text", "hi"])
        self.assertEqual(rc, 1)


class TestMainMissingKey(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"AZURE_CONTENT_SAFETY_ENDPOINT": "https://x.cognitiveservices.azure.com"},
        clear=True,
    )
    def test_no_key(self):
        rc = safety.main(["--text", "hi"])
        self.assertEqual(rc, 1)


class TestMainTextSafe(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("safety_analyze._do_request")
    def test_safe_content(self, mock_req):
        mock_req.return_value = _SAFE_RESPONSE
        rc = safety.main(["--text", "Hello world"])
        self.assertEqual(rc, 0)


class TestMainTextFlagged(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("safety_analyze._do_request")
    def test_threshold_exceeded(self, mock_req):
        mock_req.return_value = _FLAGGED_RESPONSE
        rc = safety.main(["--text", "bad content", "--threshold", "2"])
        self.assertEqual(rc, 2)

    @patch.dict(os.environ, _ENV, clear=True)
    @patch("safety_analyze._do_request")
    def test_threshold_not_exceeded(self, mock_req):
        mock_req.return_value = _SAFE_RESPONSE
        rc = safety.main(["--text", "good content", "--threshold", "2"])
        self.assertEqual(rc, 0)


class TestMainImageFile(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("safety_analyze._do_request")
    def test_image_file(self, mock_req):
        mock_req.return_value = _SAFE_RESPONSE
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff\xe0" * 10)
            tmpfile = f.name
        try:
            rc = safety.main(["--file", tmpfile])
            self.assertEqual(rc, 0)
            # Verify base64 was sent
            call_body = mock_req.call_args[0][2]
            self.assertIn("image", call_body)
            self.assertIn("content", call_body["image"])
        finally:
            os.unlink(tmpfile)


class TestMainRaw(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("safety_analyze._do_request")
    def test_raw_output(self, mock_req):
        mock_req.return_value = _SAFE_RESPONSE
        rc = safety.main(["--text", "hello", "--raw"])
        self.assertEqual(rc, 0)


class TestHintForHttpError(unittest.TestCase):
    def test_401(self):
        hint = safety._hint_for_http_error(401, "")
        self.assertIn("AZURE_CONTENT_SAFETY_API_KEY", hint)

    def test_429(self):
        hint = safety._hint_for_http_error(429, "")
        self.assertIn("Rate limited", hint)


if __name__ == "__main__":
    unittest.main()
