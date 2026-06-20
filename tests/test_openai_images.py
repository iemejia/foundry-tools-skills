#!/usr/bin/env python3
"""Unit tests for skills/openai-images/scripts/generate.py.

Tests pure logic (no network calls). Uses unittest.mock to verify payload
construction, model validation, and error output.
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Import generate.py as a module
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "openai-images", "scripts", "generate.py"
)
_spec = importlib.util.spec_from_file_location("generate", _SCRIPT)
generate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate)
sys.modules["generate"] = generate


class TestDetectProvider(unittest.TestCase):
    def test_azure(self):
        self.assertEqual(
            generate.detect_provider("https://myres.openai.azure.com"), "azure"
        )

    def test_openai(self):
        self.assertEqual(
            generate.detect_provider("https://api.openai.com"), "openai"
        )


class TestBuildUrl(unittest.TestCase):
    def test_azure_url(self):
        url = generate.build_url(
            "https://myres.openai.azure.com", "gpt-image-2", "2024-10-21", "azure"
        )
        self.assertIn("/openai/deployments/gpt-image-2/images/generations", url)
        self.assertIn("api-version=2024-10-21", url)

    def test_openai_url(self):
        url = generate.build_url(
            "https://api.openai.com", "gpt-image-2", "2024-10-21", "openai"
        )
        self.assertEqual(url, "https://api.openai.com/v1/images/generations")


class TestBuildPayload(unittest.TestCase):
    def _make_args(self, **kwargs):
        """Create a minimal args namespace."""
        defaults = {
            "model": "gpt-image-2",
            "prompt": "a test image",
            "n": None,
            "size": None,
            "quality": None,
            "background": None,
            "output_format": None,
        }
        defaults.update(kwargs)
        return type("Args", (), defaults)()

    def test_minimal_payload(self):
        args = self._make_args()
        payload = generate.build_payload(args, "openai")
        self.assertEqual(payload["model"], "gpt-image-2")
        self.assertEqual(payload["prompt"], "a test image")
        self.assertEqual(payload["n"], 1)
        self.assertNotIn("size", payload)
        self.assertNotIn("quality", payload)

    def test_all_options(self):
        args = self._make_args(
            n=3, size="1536x1024", quality="high",
            background="transparent", output_format="webp",
        )
        payload = generate.build_payload(args, "openai")
        self.assertEqual(payload["n"], 3)
        self.assertEqual(payload["size"], "1536x1024")
        self.assertEqual(payload["quality"], "high")
        self.assertEqual(payload["background"], "transparent")
        self.assertEqual(payload["output_format"], "webp")

    def test_gpt_image_2_n_limit(self):
        args = self._make_args(n=5)
        with self.assertRaises(SystemExit):
            generate.build_payload(args, "openai")

    def test_gpt_image_1_no_n_limit(self):
        args = self._make_args(model="gpt-image-1", n=8)
        payload = generate.build_payload(args, "openai")
        self.assertEqual(payload["n"], 8)


class TestMainMissingKey(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_exits_1(self):
        rc = generate.main([
            "--model", "gpt-image-2", "--prompt", "test"
        ])
        self.assertEqual(rc, 1)


class TestMainSuccess(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    @patch("generate._do_request")
    def test_raw_mode(self, mock_req):
        response = {"data": [{"b64_json": "aGVsbG8="}]}
        mock_req.return_value = response
        rc = generate.main([
            "--model", "gpt-image-2", "--prompt", "test", "--raw"
        ])
        self.assertEqual(rc, 0)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"})
    @patch("generate._do_request")
    @patch("generate._save_image")
    def test_saves_images(self, mock_save, mock_req):
        mock_req.return_value = {
            "data": [{"b64_json": "aGVsbG8="}, {"b64_json": "d29ybGQ="}]
        }
        mock_save.side_effect = ["./img_0.png", "./img_1.png"]
        rc = generate.main([
            "--model", "gpt-image-2", "--prompt", "test", "--n", "2"
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(mock_save.call_count, 2)


if __name__ == "__main__":
    unittest.main()
