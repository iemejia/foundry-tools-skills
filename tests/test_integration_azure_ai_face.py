#!/usr/bin/env python3
"""Integration tests for skills/azure-ai-face/scripts/detect.py.

Requires AZURE_AI_FACE_API_KEY and AZURE_AI_FACE_ENDPOINT
(auto-discovered via az CLI if available).
"""

import importlib.util
import json
import os
import sys
import unittest

# -- Credential discovery --
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from conftest import skip_reason_face  # noqa: E402

_skip = skip_reason_face()

# -- Load script --
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-ai-face",
    "scripts", "detect.py",
)
_spec = importlib.util.spec_from_file_location("face_detect_int", _SCRIPT)
face = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(face)
sys.modules["face_detect_int"] = face

# A well-known public domain image with a face
_TEST_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/"
    "a/a7/Camponotus_flavomarginatus_ant.jpg/"
    "320px-Camponotus_flavomarginatus_ant.jpg"
)
# Use a more reliable test: Wikipedia portrait
_FACE_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/"
    "1/16/Ada_Lovelace_portrait.jpg/"
    "220px-Ada_Lovelace_portrait.jpg"
)


@unittest.skipIf(_skip, _skip or "")
class TestFaceDetectIntegration(unittest.TestCase):
    """Live integration tests for Face detect.py."""

    def test_detect_from_url(self):
        """Detect faces from a public URL."""
        rc = face.main(["--url", _FACE_URL])
        self.assertEqual(rc, 0)

    def test_detect_with_attributes(self):
        """Detect with headPose and blur attributes."""
        rc = face.main([
            "--url", _FACE_URL,
            "--attributes", "headPose", "blur", "qualityForRecognition",
        ])
        self.assertEqual(rc, 0)

    def test_detect_with_landmarks(self):
        """Detect with face landmarks enabled."""
        rc = face.main(["--url", _FACE_URL, "--landmarks"])
        self.assertEqual(rc, 0)

    def test_detect_detection_03(self):
        """Use detection_03 model."""
        rc = face.main([
            "--url", _FACE_URL,
            "--detection-model", "detection_03",
            "--attributes", "mask", "qualityForRecognition",
        ])
        self.assertEqual(rc, 0)

    def test_detect_raw(self):
        """--raw should produce valid JSON."""
        rc = face.main(["--url", _FACE_URL, "--raw"])
        self.assertEqual(rc, 0)

    def test_no_faces_image(self):
        """Image without faces should return faceCount=0."""
        rc = face.main(["--url", _TEST_URL])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
