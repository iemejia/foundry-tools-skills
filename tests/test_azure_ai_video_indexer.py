#!/usr/bin/env python3
"""Unit tests for skills/azure-ai-video-indexer/scripts/analyze.py."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-video-indexer",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("vi_analyze", _SCRIPT)
vi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vi)
sys.modules["vi_analyze"] = vi

_ENV = {
    "AZURE_VIDEO_INDEXER_ACCOUNT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_VIDEO_INDEXER_LOCATION": "trial",
    "AZURE_VIDEO_INDEXER_ACCESS_TOKEN": "test-token",
}

_LIST_RESPONSE = {
    "results": [
        {"id": "vid1", "name": "Video 1", "state": "Processed",
         "durationInSeconds": 120, "created": "2026-01-01T00:00:00Z"},
        {"id": "vid2", "name": "Video 2", "state": "Processing",
         "durationInSeconds": 60, "created": "2026-01-02T00:00:00Z"},
    ]
}

_INDEX_RESPONSE = {
    "name": "Test Video",
    "state": "Processed",
    "durationInSeconds": 120,
    "videos": [{
        "insights": {
            "transcript": [
                {"text": "Hello world", "timeOffset": "0:00:00",
                 "endTimeOffset": "0:00:02"},
            ],
            "topics": [
                {"name": "Technology", "confidence": 0.95},
            ],
            "keywords": [
                {"text": "hello", "confidence": 0.9},
            ],
            "labels": [
                {"name": "person", "confidence": 0.88},
            ],
            "sentiments": [
                {"sentimentType": "Positive", "averageScore": 0.8},
            ],
            "faces": [
                {"id": 1, "name": "Unknown #1", "confidence": 0.7},
            ],
        }
    }],
}

_UPLOAD_RESPONSE = {
    "id": "new-video-id",
    "name": "My Video",
    "state": "Uploaded",
}


class TestGuessContentType(unittest.TestCase):
    def test_mp4(self):
        self.assertEqual(vi._guess_content_type("video.mp4"), "video/mp4")

    def test_avi(self):
        self.assertEqual(vi._guess_content_type("clip.avi"), "video/x-msvideo")

    def test_unknown(self):
        self.assertEqual(vi._guess_content_type("file.xyz"), "video/mp4")


class TestApiUrl(unittest.TestCase):
    def test_basic(self):
        url = vi._api_url("trial", "acct-id", "/Videos")
        self.assertEqual(
            url,
            "https://api.videoindexer.ai/trial/Accounts/acct-id/Videos",
        )

    def test_with_params(self):
        url = vi._api_url("eastus2", "acct-id", "/Videos", {"name": "test"})
        self.assertIn("name=test", url)

    def test_path_with_id(self):
        url = vi._api_url("trial", "acct", "/Videos/vid1/Index")
        self.assertIn("/Videos/vid1/Index", url)


class TestBuildMultipart(unittest.TestCase):
    def test_produces_valid_multipart(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"\x00" * 100)
            tmpfile = f.name
        try:
            body, ct = vi._build_multipart(tmpfile)
            self.assertIn("multipart/form-data; boundary=", ct)
            self.assertIn(b"Content-Disposition: form-data", body)
            self.assertIn(b"video/mp4", body)
        finally:
            os.unlink(tmpfile)


class TestParseArgs(unittest.TestCase):
    def test_upload(self):
        args = vi.parse_args(["--upload", "video.mp4"])
        self.assertEqual(args.upload_path, "video.mp4")
        self.assertTrue(args.wait)

    def test_video_url(self):
        args = vi.parse_args(["--video-url", "https://example.com/vid.mp4"])
        self.assertEqual(args.video_url, "https://example.com/vid.mp4")

    def test_video_id(self):
        args = vi.parse_args(["--video-id", "abc123"])
        self.assertEqual(args.video_id, "abc123")

    def test_list(self):
        args = vi.parse_args(["--list"])
        self.assertTrue(args.list_videos)

    def test_no_wait(self):
        args = vi.parse_args(["--upload", "v.mp4", "--no-wait"])
        self.assertFalse(args.wait)

    def test_name(self):
        args = vi.parse_args(["--upload", "v.mp4", "--name", "My Video"])
        self.assertEqual(args.name, "My Video")


class TestMainMissingAccountId(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_account_id(self):
        rc = vi.main(["--list"])
        self.assertEqual(rc, 1)


class TestMainMissingLocation(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"AZURE_VIDEO_INDEXER_ACCOUNT_ID": "acct"},
        clear=True,
    )
    def test_no_location(self):
        rc = vi.main(["--list"])
        self.assertEqual(rc, 1)


class TestMainMissingToken(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"AZURE_VIDEO_INDEXER_ACCOUNT_ID": "acct",
         "AZURE_VIDEO_INDEXER_LOCATION": "trial"},
        clear=True,
    )
    @patch("vi_analyze._generate_token_via_az")
    def test_no_token_no_az(self, mock_gen):
        mock_gen.side_effect = RuntimeError("no az")
        rc = vi.main(["--list"])
        self.assertEqual(rc, 1)


class TestMainList(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("vi_analyze._api_get")
    def test_list_videos(self, mock_get):
        mock_get.return_value = _LIST_RESPONSE
        rc = vi.main(["--list"])
        self.assertEqual(rc, 0)


class TestMainInsights(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("vi_analyze._api_get")
    def test_get_insights(self, mock_get):
        mock_get.return_value = _INDEX_RESPONSE
        rc = vi.main(["--video-id", "vid1"])
        self.assertEqual(rc, 0)


class TestMainInsightsRaw(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("vi_analyze._api_get")
    def test_raw(self, mock_get):
        mock_get.return_value = _INDEX_RESPONSE
        rc = vi.main(["--video-id", "vid1", "--raw"])
        self.assertEqual(rc, 0)


class TestMainUploadFileNotFound(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    def test_missing_file(self):
        rc = vi.main(["--upload", "/nonexistent/video.mp4"])
        self.assertEqual(rc, 1)


class TestMainUploadNoWait(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("vi_analyze._api_post")
    def test_upload_no_wait(self, mock_post):
        mock_post.return_value = _UPLOAD_RESPONSE
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"\x00" * 100)
            tmpfile = f.name
        try:
            rc = vi.main(["--upload", tmpfile, "--no-wait"])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(tmpfile)


class TestMainVideoUrl(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("vi_analyze._api_post")
    def test_url_no_wait(self, mock_post):
        mock_post.return_value = _UPLOAD_RESPONSE
        rc = vi.main([
            "--video-url", "https://example.com/vid.mp4", "--no-wait",
        ])
        self.assertEqual(rc, 0)


class TestHintForHttpError(unittest.TestCase):
    def test_401(self):
        hint = vi._hint_for_http_error(401, "")
        self.assertIn("expired", hint)

    def test_404(self):
        hint = vi._hint_for_http_error(404, "")
        self.assertIn("AZURE_VIDEO_INDEXER_ACCOUNT_ID", hint)

    def test_409(self):
        hint = vi._hint_for_http_error(409, "")
        self.assertIn("Conflict", hint)

    def test_429(self):
        hint = vi._hint_for_http_error(429, "")
        self.assertIn("Rate limited", hint)


class TestPrintInsights(unittest.TestCase):
    def test_simplified(self):
        rc = vi._print_insights(_INDEX_RESPONSE, False)
        self.assertEqual(rc, 0)

    def test_raw(self):
        rc = vi._print_insights(_INDEX_RESPONSE, True)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
