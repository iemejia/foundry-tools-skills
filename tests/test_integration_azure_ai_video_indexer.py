#!/usr/bin/env python3
"""Integration tests for skills/azure-ai-video-indexer/scripts/analyze.py.

Requires AZURE_VIDEO_INDEXER_ACCOUNT_ID, AZURE_VIDEO_INDEXER_LOCATION,
and AZURE_VIDEO_INDEXER_ACCESS_TOKEN (auto-discovered via az CLI if available).

Note: Video upload/indexing tests are skipped by default because they are
slow (minutes) and consume Video Indexer quota.  Set VI_RUN_UPLOAD_TESTS=1
to enable them.
"""

import importlib.util
import os
import sys
import unittest

# -- Credential discovery --
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from conftest import skip_reason_video_indexer  # noqa: E402

_skip = skip_reason_video_indexer()
_skip_upload = (
    not os.environ.get("VI_RUN_UPLOAD_TESTS")
    and "Upload tests disabled (set VI_RUN_UPLOAD_TESTS=1 to enable)"
)

# -- Load script --
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-video-indexer",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("vi_analyze_int", _SCRIPT)
vi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vi)
sys.modules["vi_analyze_int"] = vi


@unittest.skipIf(_skip, _skip or "")
class TestVideoIndexerListIntegration(unittest.TestCase):
    """Live integration test: list videos."""

    def test_list_videos(self):
        """List indexed videos — should succeed even if no videos exist."""
        rc = vi.main(["--list"])
        self.assertEqual(rc, 0)


@unittest.skipIf(_skip, _skip or "")
class TestVideoIndexerListRaw(unittest.TestCase):
    def test_list_raw(self):
        """List with --raw should succeed."""
        rc = vi.main(["--list", "--raw"])
        self.assertEqual(rc, 0)


@unittest.skipIf(_skip or _skip_upload, _skip or _skip_upload or "")
class TestVideoIndexerUploadUrl(unittest.TestCase):
    """Live upload test (disabled by default due to quota/time)."""

    def test_upload_from_url_no_wait(self):
        """Submit a public video URL without waiting for processing."""
        rc = vi.main([
            "--video-url",
            "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
            "--name", "integration-test-video",
            "--no-wait",
        ])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
