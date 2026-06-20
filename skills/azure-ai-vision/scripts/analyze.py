#!/usr/bin/env python3
"""Analyze images with Azure AI Vision (Image Analysis 4.0).

Service: Azure AI Vision (Computer Vision)
Task:    Caption, OCR, tagging, object detection, people detection
Env:     AZURE_AI_VISION_API_KEY  (required)
         AZURE_AI_VISION_ENDPOINT (required)

Example:
    export AZURE_AI_VISION_API_KEY="..."
    export AZURE_AI_VISION_ENDPOINT="https://<resource>.cognitiveservices.azure.com"
    python3 analyze.py --file photo.jpg --features caption read tags

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

_DEFAULT_API_VERSION = "2024-02-01"
_ALL_FEATURES = [
    "caption", "denseCaptions", "read", "tags",
    "objects", "people", "smartCrops",
]
_DEFAULT_FEATURES = ["caption", "read", "tags"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured JSON error to *stderr* for agent consumption."""
    msg = json.dumps({"error": str(what), "hint": hint})
    sys.stderr.write(msg + "\n")


def build_url(endpoint, api_version, features, language=None):
    # type: (str, str, list, str) -> str
    """Build the Image Analysis URL with query parameters."""
    endpoint = endpoint.rstrip("/")
    url = (
        "{}/computervision/imageanalysis:analyze"
        "?api-version={}&features={}".format(
            endpoint, api_version, ",".join(features)
        )
    )
    if language:
        url += "&language=" + urllib.parse.quote(language)
    return url


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _do_request(url, api_key, data, content_type, timeout, max_retries):
    # type: (str, str, bytes, str, int, int) -> dict
    """POST image data and return parsed JSON; retry on transient errors."""
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
            "Check AZURE_AI_VISION_API_KEY. Find keys at "
            "portal.azure.com > Computer Vision > Keys and Endpoint."
        )
    if code == 403:
        return (
            "Access denied. The key may lack permissions or the resource "
            "may be disabled. Check Azure portal."
        )
    if code == 400:
        hint = "Bad request."
        if detail:
            hint += " " + detail[:300]
        return hint
    if code == 404:
        return "Endpoint not found. Verify AZURE_AI_VISION_ENDPOINT."
    if code == 415:
        return (
            "Unsupported media type. Supported formats: "
            "JPEG, PNG, GIF, BMP, TIFF, WebP."
        )
    if code == 429:
        return "Rate limited. Wait and retry, or upgrade pricing tier."
    if code >= 500:
        return "Server error ({}). Retry later.".format(code)
    return "HTTP {}: {}".format(code, detail[:200] if detail else "unknown")


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


def _format_result(result, features):
    # type: (dict, list) -> dict
    """Extract key information from the API response."""
    output = {}  # type: dict

    if "caption" in features:
        cap = result.get("captionResult", {})
        if cap:
            output["caption"] = cap.get("text", "")
            output["captionConfidence"] = round(cap.get("confidence", 0), 3)

    if "denseCaptions" in features:
        dc = result.get("denseCaptionsResult", {})
        if dc.get("values"):
            output["denseCaptions"] = [
                {
                    "text": v.get("text", ""),
                    "confidence": round(v.get("confidence", 0), 3),
                }
                for v in dc["values"]
            ]

    if "read" in features:
        read_res = result.get("readResult", {})
        lines = []
        for block in read_res.get("blocks", []):
            for line in block.get("lines", []):
                lines.append(line.get("text", ""))
        if lines:
            output["text"] = lines

    if "tags" in features:
        tags = result.get("tagsResult", {})
        if tags.get("values"):
            output["tags"] = [
                {
                    "name": v.get("name", ""),
                    "confidence": round(v.get("confidence", 0), 3),
                }
                for v in tags["values"]
            ]

    if "objects" in features:
        objs = result.get("objectsResult", {})
        if objs.get("values"):
            items = []
            for v in objs["values"]:
                tag = v.get("tags", [{}])[0] if v.get("tags") else {}
                items.append(
                    {
                        "name": tag.get("name", ""),
                        "confidence": round(tag.get("confidence", 0), 3),
                        "boundingBox": v.get("boundingBox", {}),
                    }
                )
            output["objects"] = items

    if "people" in features:
        ppl = result.get("peopleResult", {})
        if ppl.get("values"):
            output["people"] = [
                {
                    "confidence": round(v.get("confidence", 0), 3),
                    "boundingBox": v.get("boundingBox", {}),
                }
                for v in ppl["values"]
            ]

    if "smartCrops" in features:
        sc = result.get("smartCropsResult", {})
        if sc.get("values"):
            output["smartCrops"] = [
                {
                    "aspectRatio": v.get("aspectRatio", 0),
                    "boundingBox": v.get("boundingBox", {}),
                }
                for v in sc["values"]
            ]

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    # type: (list) -> argparse.Namespace
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description="Analyze images via Azure AI Vision (Image Analysis 4.0)."
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--file", dest="file_path", help="Local image file to analyze."
    )
    source.add_argument(
        "--url", dest="image_url", help="Public URL of the image."
    )
    p.add_argument(
        "--features",
        nargs="+",
        default=_DEFAULT_FEATURES,
        choices=_ALL_FEATURES,
        help="Features to extract (default: caption read tags).",
    )
    p.add_argument(
        "--endpoint", default=None, help="Vision endpoint URL."
    )
    p.add_argument(
        "--language", default=None,
        help="Caption language (e.g. 'en'). Default: server decides.",
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
    endpoint = args.endpoint or os.environ.get("AZURE_AI_VISION_ENDPOINT")
    if not endpoint:
        _emit_error(
            "No endpoint specified.",
            "Set AZURE_AI_VISION_ENDPOINT or pass --endpoint. "
            "Find it at portal.azure.com > Computer Vision > "
            "Keys and Endpoint.",
        )
        return 1

    # ---- Resolve API key ----
    api_key = os.environ.get("AZURE_AI_VISION_API_KEY")
    if not api_key:
        _emit_error(
            "AZURE_AI_VISION_API_KEY is not set.",
            "Run: export AZURE_AI_VISION_API_KEY='...' \u2014 find your key "
            "at portal.azure.com > Computer Vision > Keys and Endpoint.",
        )
        return 1

    # ---- Validate file ----
    if args.file_path and not os.path.isfile(args.file_path):
        _emit_error(
            "File not found: '{}'.".format(args.file_path),
            "Check the path and ensure the file exists.",
        )
        return 1

    # ---- Build URL ----
    url = build_url(
        endpoint, args.api_version, args.features, language=args.language,
    )

    # ---- Prepare body ----
    if args.image_url:
        data = json.dumps({"url": args.image_url}).encode("utf-8")
        content_type = "application/json"
    else:
        with open(args.file_path, "rb") as f:
            data = f.read()
        content_type = "application/octet-stream"

    # ---- Call API ----
    try:
        result = _do_request(
            url, api_key, data, content_type, args.timeout, args.retries,
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_error(
            "HTTP {} from Vision API.".format(exc.code),
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
        _emit_error(str(exc), "Unexpected error during image analysis.")
        return 1

    # ---- Output ----
    if args.raw:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    output = _format_result(result, args.features)
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
