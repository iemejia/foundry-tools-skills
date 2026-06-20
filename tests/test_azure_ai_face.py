#!/usr/bin/env python3
"""Unit tests for skills/azure-ai-face/scripts/detect.py."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-face",
    "scripts", "detect.py",
)
_spec = importlib.util.spec_from_file_location("face_detect", _SCRIPT)
face = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(face)
sys.modules["face_detect"] = face

_ENV = {
    "AZURE_AI_FACE_ENDPOINT": "https://x.cognitiveservices.azure.com",
    "AZURE_AI_FACE_API_KEY": "k",
}

_ONE_FACE = [
    {
        "faceId": "abc-123",
        "faceRectangle": {"top": 10, "left": 20, "width": 100, "height": 100},
        "faceAttributes": {"headPose": {"roll": 0, "yaw": 0, "pitch": 0}},
    }
]

_TWO_FACES = [
    {
        "faceRectangle": {"top": 10, "left": 20, "width": 100, "height": 100},
    },
    {
        "faceRectangle": {"top": 50, "left": 60, "width": 80, "height": 80},
    },
]


class TestBuildUrl(unittest.TestCase):
    def test_basic(self):
        url = face.build_url(
            "https://x.cognitiveservices.azure.com", "v1.0",
            False, False, None, "detection_01", "recognition_04",
        )
        self.assertIn("/face/v1.0/detect", url)
        self.assertIn("returnFaceId=false", url)
        self.assertIn("detectionModel=detection_01", url)
        self.assertNotIn("returnFaceAttributes", url)

    def test_with_attributes(self):
        url = face.build_url(
            "https://x.cognitiveservices.azure.com", "v1.0",
            True, True, ["headPose", "blur"], "detection_03", "recognition_04",
        )
        self.assertIn("returnFaceId=true", url)
        self.assertIn("returnFaceLandmarks=true", url)
        self.assertIn("returnFaceAttributes=headPose,blur", url)
        self.assertIn("detectionModel=detection_03", url)

    def test_trailing_slash(self):
        url = face.build_url(
            "https://x.cognitiveservices.azure.com/", "v1.0",
            False, False, None, "detection_01", "recognition_04",
        )
        self.assertNotIn("//face", url)


class TestParseArgs(unittest.TestCase):
    def test_file(self):
        args = face.parse_args(["--file", "photo.jpg"])
        self.assertEqual(args.file_path, "photo.jpg")
        self.assertEqual(args.detection_model, "detection_01")
        self.assertFalse(args.face_id)
        self.assertFalse(args.landmarks)

    def test_url(self):
        args = face.parse_args(["--url", "https://example.com/img.jpg"])
        self.assertEqual(args.image_url, "https://example.com/img.jpg")

    def test_attributes(self):
        args = face.parse_args([
            "--file", "x.jpg", "--attributes", "headPose", "blur",
        ])
        self.assertEqual(args.attributes, ["headPose", "blur"])

    def test_attributes_all(self):
        args = face.parse_args(["--file", "x.jpg", "--attributes", "all"])
        self.assertEqual(args.attributes, ["all"])

    def test_face_id_and_landmarks(self):
        args = face.parse_args([
            "--file", "x.jpg", "--face-id", "--landmarks",
        ])
        self.assertTrue(args.face_id)
        self.assertTrue(args.landmarks)


class TestMainMissingEndpoint(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_endpoint(self):
        rc = face.main(["--file", "x.jpg"])
        self.assertEqual(rc, 1)


class TestMainMissingKey(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"AZURE_AI_FACE_ENDPOINT": "https://x.cognitiveservices.azure.com"},
        clear=True,
    )
    def test_no_key(self):
        rc = face.main(["--file", "x.jpg"])
        self.assertEqual(rc, 1)


class TestMainFileNotFound(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    def test_missing(self):
        rc = face.main(["--file", "/nonexistent/photo.jpg"])
        self.assertEqual(rc, 1)


class TestMainOneFace(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("face_detect._do_request")
    def test_basic_detection(self, mock_req):
        mock_req.return_value = _ONE_FACE
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff\xe0" * 10)
            tmpfile = f.name
        try:
            rc = face.main(["--file", tmpfile])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(tmpfile)


class TestMainTwoFaces(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("face_detect._do_request")
    def test_count(self, mock_req):
        mock_req.return_value = _TWO_FACES
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff\xe0" * 10)
            tmpfile = f.name
        try:
            rc = face.main(["--file", tmpfile])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(tmpfile)


class TestMainUrl(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("face_detect._do_request")
    def test_url_input(self, mock_req):
        mock_req.return_value = _ONE_FACE
        rc = face.main(["--url", "https://example.com/photo.jpg"])
        self.assertEqual(rc, 0)
        call_body = mock_req.call_args[0][2]
        self.assertIn(b"url", call_body if isinstance(call_body, bytes)
                      else call_body.encode())


class TestMainRaw(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("face_detect._do_request")
    def test_raw_output(self, mock_req):
        mock_req.return_value = _ONE_FACE
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff\xe0" * 10)
            tmpfile = f.name
        try:
            rc = face.main(["--file", tmpfile, "--raw"])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(tmpfile)


class TestMainAllAttrs(unittest.TestCase):
    @patch.dict(os.environ, _ENV, clear=True)
    @patch("face_detect._do_request")
    def test_all_attrs_detection_03(self, mock_req):
        mock_req.return_value = []
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff\xe0" * 10)
            tmpfile = f.name
        try:
            rc = face.main([
                "--file", tmpfile, "--attributes", "all",
                "--detection-model", "detection_03",
            ])
            self.assertEqual(rc, 0)
            # Should use detection_03 attrs
            call_url = mock_req.call_args[0][0]
            self.assertIn("headPose", call_url)
            self.assertIn("mask", call_url)
        finally:
            os.unlink(tmpfile)


class TestHintForHttpError(unittest.TestCase):
    def test_401(self):
        hint = face._hint_for_http_error(401, "")
        self.assertIn("AZURE_AI_FACE_API_KEY", hint)

    def test_403(self):
        hint = face._hint_for_http_error(403, "")
        self.assertIn("Limited Access", hint)

    def test_400_invalid_image(self):
        hint = face._hint_for_http_error(400, "InvalidImage blah")
        self.assertIn("too large", hint)

    def test_400_invalid_attrs(self):
        hint = face._hint_for_http_error(400, "InvalidFaceAttributes blah")
        self.assertIn("detection_03", hint)

    def test_429(self):
        hint = face._hint_for_http_error(429, "")
        self.assertIn("Rate limited", hint)


if __name__ == "__main__":
    unittest.main()
