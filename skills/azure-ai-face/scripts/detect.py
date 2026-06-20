#!/usr/bin/env python3
"""Detect faces in images using Azure AI Face.

Service: Azure AI Face
Task:    Face detection with optional attributes and landmarks
Env:     AZURE_AI_FACE_API_KEY  (required)
         AZURE_AI_FACE_ENDPOINT (required)

Example:
    export AZURE_AI_FACE_API_KEY="..."
    export AZURE_AI_FACE_ENDPOINT="https://<resource>.cognitiveservices.azure.com"
    python3 detect.py --file photo.jpg
    python3 detect.py --url "https://example.com/photo.jpg" --attributes headPose blur

# Requires: Python >= 3.8, standard library only
"""

from __future__ import print_function

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_API_VERSION = "v1.0"

# Attributes available per detection model.
# Note: age, gender, emotion, smile, facialHair, hair, makeup were
# retired/restricted by Microsoft in late 2023.  They require Limited
# Access approval — see https://aka.ms/facerecognition.
_DETECTION_01_ATTRS = [
    "accessories", "blur", "exposure", "glasses", "headPose",
    "noise", "occlusion", "qualityForRecognition",
]
_DETECTION_03_ATTRS = [
    "blur", "exposure", "headPose", "mask", "noise",
    "qualityForRecognition",
]
_RESTRICTED_ATTRS = [
    "age", "emotion", "facialHair", "gender", "hair",
    "makeup", "smile",
]
_ALL_ATTRS = sorted(set(_DETECTION_01_ATTRS + _DETECTION_03_ATTRS))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured JSON error to *stderr* for agent consumption."""
    msg = json.dumps({"error": str(what), "hint": hint})
    sys.stderr.write(msg + "\n")


def build_url(endpoint, api_version, return_face_id, return_landmarks,
              attributes, detection_model, recognition_model):
    # type: (str, str, bool, bool, list, str, str) -> str
    """Build the Face detect URL."""
    endpoint = endpoint.rstrip("/")
    parts = [
        "returnFaceId={}".format("true" if return_face_id else "false"),
        "returnFaceLandmarks={}".format("true" if return_landmarks else "false"),
        "detectionModel={}".format(detection_model),
        "recognitionModel={}".format(recognition_model),
    ]
    if attributes:
        parts.append("returnFaceAttributes={}".format(",".join(attributes)))
    return "{}/face/{}/detect?{}".format(endpoint, api_version, "&".join(parts))


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _do_request(url, api_key, body, content_type, timeout, max_retries):
    # type: (str, str, bytes, str, int, int) -> list
    """POST image and return parsed JSON; retry on transient errors."""
    if isinstance(body, str):
        data = body.encode("utf-8")
    else:
        data = body
    for attempt in range(max_retries + 1):
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": content_type,
        }
        req = urllib.request.Request(
            url, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                retry_after = exc.headers.get("Retry-After")
                wait = (
                    int(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 2 ** attempt
                )
                sys.stderr.write(
                    "HTTP {} \u2014 retrying in {}s (attempt {}/{})\n".format(
                        exc.code, wait, attempt + 1, max_retries
                    )
                )
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("max retries exhausted")


# ---------------------------------------------------------------------------
# Error hints
# ---------------------------------------------------------------------------


def _hint_for_http_error(code, detail):
    # type: (int, str) -> str
    """Return an actionable hint for the HTTP status code."""
    if code == 401:
        return (
            "Check AZURE_AI_FACE_API_KEY. Find keys at "
            "portal.azure.com > Face resource > Keys and Endpoint."
        )
    if code == 403:
        return (
            "Access denied. Some face attributes (age, gender, emotion) "
            "require Limited Access approval. Apply at "
            "https://aka.ms/facerecognition"
        )
    if code == 400:
        hint = "Bad request."
        if "InvalidImage" in detail:
            hint += (
                " Image may be invalid, too large (>6MB), or too small. "
                "Supported: JPEG, PNG, BMP, GIF."
            )
        elif "InvalidFaceAttributes" in detail:
            hint += (
                " Some attributes are not supported with the chosen "
                "detection model. detection_03 supports: "
                + ", ".join(_DETECTION_03_ATTRS)
                + ". detection_01 supports: "
                + ", ".join(_DETECTION_01_ATTRS) + "."
            )
        elif detail:
            hint += " " + detail[:300]
        return hint
    if code == 404:
        return "Endpoint not found. Verify AZURE_AI_FACE_ENDPOINT."
    if code == 429:
        return "Rate limited. Wait and retry, or upgrade pricing tier."
    if code >= 500:
        return "Server error ({}). Retry later.".format(code)
    return "HTTP {}: {}".format(code, detail[:200] if detail else "unknown")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    # type: (list) -> argparse.Namespace
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description=(
            "Detect faces in images using Azure AI Face. "
            "Returns face rectangles and optional attributes."
        ),
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--file", dest="file_path",
        help="Image file to analyze (JPEG, PNG, BMP, GIF; max 6MB).",
    )
    source.add_argument(
        "--url", dest="image_url",
        help="Publicly accessible image URL to analyze.",
    )
    p.add_argument(
        "--attributes", nargs="*", default=None,
        help=(
            "Face attributes to return (space-separated). "
            "Available: " + ", ".join(_ALL_ATTRS) + ". "
            "Restricted (need approval): " + ", ".join(_RESTRICTED_ATTRS)
            + ". Use 'all' for all standard attributes."
        ),
    )
    p.add_argument(
        "--face-id", action="store_true", default=False,
        help="Return faceId for each face.",
    )
    p.add_argument(
        "--landmarks", action="store_true", default=False,
        help="Return detailed face landmarks (27 points).",
    )
    p.add_argument(
        "--detection-model",
        default="detection_01",
        choices=["detection_01", "detection_03"],
        help=(
            "Detection model (default: %(default)s). "
            "detection_03 is more accurate but supports fewer attributes."
        ),
    )
    p.add_argument(
        "--recognition-model",
        default="recognition_04",
        help="Recognition model (default: %(default)s).",
    )
    p.add_argument(
        "--endpoint", default=None,
        help="Face endpoint URL (overrides env var).",
    )
    p.add_argument(
        "--api-version",
        default=_DEFAULT_API_VERSION,
        help="API version (default: %(default)s).",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds (default: %(default)s).",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max retries on transient HTTP errors (default: %(default)s).",
    )
    p.add_argument(
        "--raw",
        action="store_true",
        help="Print the full API JSON response.",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv=None):
    # type: (list) -> int
    """Entry point. Returns 0 on success, 1 on failure."""
    args = parse_args(argv)

    # ---- Resolve endpoint ----
    endpoint = (
        args.endpoint or os.environ.get("AZURE_AI_FACE_ENDPOINT")
    )
    if not endpoint:
        _emit_error(
            "No endpoint specified.",
            "Set AZURE_AI_FACE_ENDPOINT or pass --endpoint. "
            "Find it at portal.azure.com > Face resource > "
            "Keys and Endpoint.",
        )
        return 1

    # ---- Resolve API key ----
    api_key = os.environ.get("AZURE_AI_FACE_API_KEY")
    if not api_key:
        _emit_error(
            "AZURE_AI_FACE_API_KEY is not set.",
            "Run: export AZURE_AI_FACE_API_KEY='...' \u2014 find your "
            "key at portal.azure.com > Face resource > Keys and Endpoint.",
        )
        return 1

    # ---- Resolve attributes ----
    attributes = args.attributes
    if attributes:
        if "all" in attributes:
            if args.detection_model == "detection_03":
                attributes = _DETECTION_03_ATTRS
            else:
                attributes = _DETECTION_01_ATTRS

    # ---- Build URL ----
    url = build_url(
        endpoint, args.api_version, args.face_id, args.landmarks,
        attributes, args.detection_model, args.recognition_model,
    )

    # ---- Build body ----
    if args.file_path:
        if not os.path.isfile(args.file_path):
            _emit_error(
                "File not found: '{}'.".format(args.file_path),
                "Check the path and ensure the file exists.",
            )
            return 1
        with open(args.file_path, "rb") as f:
            body = f.read()
        content_type = "application/octet-stream"
    else:
        body = json.dumps({"url": args.image_url})
        content_type = "application/json"

    # ---- Call API ----
    try:
        result = _do_request(
            url, api_key, body, content_type,
            args.timeout, args.retries,
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_error(
            "HTTP {} from Face API.".format(exc.code),
            _hint_for_http_error(exc.code, detail),
        )
        return 1
    except urllib.error.URLError as exc:
        _emit_error(
            "Connection failed: {}".format(exc.reason),
            "Check network and endpoint URL ({}).".format(endpoint),
        )
        return 1
    except Exception as exc:
        _emit_error(str(exc), "Unexpected error during face detection.")
        return 1

    # ---- Output ----
    if args.raw:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    # Simplified output
    faces = []
    for face_data in result:
        entry = {"faceRectangle": face_data.get("faceRectangle", {})}
        if face_data.get("faceId"):
            entry["faceId"] = face_data["faceId"]
        if face_data.get("faceAttributes"):
            entry["attributes"] = face_data["faceAttributes"]
        if face_data.get("faceLandmarks"):
            entry["landmarks"] = face_data["faceLandmarks"]
        faces.append(entry)

    output = {"faceCount": len(faces), "faces": faces}
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
