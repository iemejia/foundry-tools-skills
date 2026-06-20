#!/usr/bin/env python3
"""Unit tests for skills/azure-ai-vision/scripts/analyze.py."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-vision",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("vision_analyze", _SCRIPT)
vision = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vision)
sys.modules["vision_analyze"] = vision


class TestBuildUrl(unittest.TestCase):
    def test_default_features(self):
        url = vision.build_url(
            "https://x.cognitiveservices.azure.com",
            "2024-02-01",
            ["caption", "read", "tags"],
        )
        self.assertIn("/computervision/imageanalysis:analyze?", url)
        self.assertIn("api-version=2024-02-01", url)
        self.assertIn("features=caption,read,tags", url)

    def test_single_feature(self):
        url = vision.build_url(
            "https://x.cognitiveservices.azure.com", "2024-02-01", ["read"]
        )
        self.assertIn("features=read", url)

    def test_language(self):
        url = vision.build_url(
            "https://x.cognitiveservices.azure.com", "2024-02-01",
            ["caption"], language="en",
        )
        self.assertIn("language=en", url)

    def test_trailing_slash(self):
        url = vision.build_url(
            "https://x.cognitiveservices.azure.com/", "2024-02-01",
            ["caption"],
        )
        self.assertNotIn("//computervision", url)


class TestFormatResult(unittest.TestCase):
    def test_caption(self):
        result = {
            "captionResult": {"text": "a cat on a mat", "confidence": 0.95},
        }
        out = vision._format_result(result, ["caption"])
        self.assertEqual(out["caption"], "a cat on a mat")
        self.assertAlmostEqual(out["captionConfidence"], 0.95, places=2)

    def test_read_ocr(self):
        result = {
            "readResult": {
                "blocks": [
                    {"lines": [
                        {"text": "Hello"},
                        {"text": "World"},
                    ]}
                ]
            }
        }
        out = vision._format_result(result, ["read"])
        self.assertEqual(out["text"], ["Hello", "World"])

    def test_tags(self):
        result = {
            "tagsResult": {
                "values": [
                    {"name": "outdoor", "confidence": 0.99},
                    {"name": "sky", "confidence": 0.95},
                ]
            }
        }
        out = vision._format_result(result, ["tags"])
        self.assertEqual(len(out["tags"]), 2)
        self.assertEqual(out["tags"][0]["name"], "outdoor")

    def test_objects(self):
        result = {
            "objectsResult": {
                "values": [
                    {
                        "tags": [{"name": "car", "confidence": 0.9}],
                        "boundingBox": {"x": 0, "y": 0, "w": 100, "h": 50},
                    }
                ]
            }
        }
        out = vision._format_result(result, ["objects"])
        self.assertEqual(out["objects"][0]["name"], "car")

    def test_empty_result(self):
        out = vision._format_result({}, ["caption", "read", "tags"])
        self.assertEqual(out, {})


class TestParseArgs(unittest.TestCase):
    def test_file_input(self):
        args = vision.parse_args(["--file", "photo.jpg"])
        self.assertEqual(args.file_path, "photo.jpg")
        self.assertEqual(args.features, ["caption", "read", "tags"])

    def test_url_input(self):
        args = vision.parse_args(["--url", "https://example.com/img.jpg"])
        self.assertEqual(args.image_url, "https://example.com/img.jpg")

    def test_custom_features(self):
        args = vision.parse_args([
            "--file", "x.jpg", "--features", "objects", "people",
        ])
        self.assertEqual(args.features, ["objects", "people"])


class TestMainMissingEndpoint(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_endpoint(self):
        rc = vision.main(["--file", "x.jpg"])
        self.assertEqual(rc, 1)


class TestMainMissingKey(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"AZURE_AI_VISION_ENDPOINT": "https://x.cognitiveservices.azure.com"},
        clear=True,
    )
    def test_no_key(self):
        rc = vision.main(["--file", "x.jpg"])
        self.assertEqual(rc, 1)


class TestMainFileNotFound(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "AZURE_AI_VISION_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_AI_VISION_API_KEY": "k",
        },
        clear=True,
    )
    def test_missing_file(self):
        rc = vision.main(["--file", "/nonexistent/photo.jpg"])
        self.assertEqual(rc, 1)


class TestMainSuccess(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "AZURE_AI_VISION_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_AI_VISION_API_KEY": "k",
        },
        clear=True,
    )
    @patch("vision_analyze._do_request")
    def test_analyze_file(self, mock_req):
        mock_req.return_value = {
            "captionResult": {"text": "a photo", "confidence": 0.9},
            "tagsResult": {"values": [{"name": "test", "confidence": 0.8}]},
        }
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff\xe0" * 10)
            tmpfile = f.name
        try:
            rc = vision.main(["--file", tmpfile])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(tmpfile)

    @patch.dict(
        os.environ,
        {
            "AZURE_AI_VISION_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_AI_VISION_API_KEY": "k",
        },
        clear=True,
    )
    @patch("vision_analyze._do_request")
    def test_analyze_url(self, mock_req):
        mock_req.return_value = {
            "captionResult": {"text": "a url photo", "confidence": 0.85},
        }
        rc = vision.main(["--url", "https://example.com/img.jpg"])
        self.assertEqual(rc, 0)
        # Verify JSON body was sent (not binary)
        call_args = mock_req.call_args
        self.assertEqual(call_args[0][3], "application/json")

    @patch.dict(
        os.environ,
        {
            "AZURE_AI_VISION_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_AI_VISION_API_KEY": "k",
        },
        clear=True,
    )
    @patch("vision_analyze._do_request")
    def test_raw_output(self, mock_req):
        mock_req.return_value = {"captionResult": {"text": "raw"}}
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff\xe0")
            tmpfile = f.name
        try:
            rc = vision.main(["--file", tmpfile, "--raw"])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(tmpfile)


class TestHintForHttpError(unittest.TestCase):
    def test_401(self):
        hint = vision._hint_for_http_error(401, "")
        self.assertIn("AZURE_AI_VISION_API_KEY", hint)

    def test_415(self):
        hint = vision._hint_for_http_error(415, "")
        self.assertIn("Unsupported", hint)


if __name__ == "__main__":
    unittest.main()
