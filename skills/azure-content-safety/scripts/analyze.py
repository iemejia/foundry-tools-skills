#!/usr/bin/env python3
"""Analyze content for safety using Azure Content Safety.

Service: Azure Content Safety
Task:    Text and image moderation with severity levels
Env:     AZURE_CONTENT_SAFETY_API_KEY  (required)
         AZURE_CONTENT_SAFETY_ENDPOINT (required)

Example:
    export AZURE_CONTENT_SAFETY_API_KEY="..."
    export AZURE_CONTENT_SAFETY_ENDPOINT="https://<resource>.cognitiveservices.azure.com"
    python3 analyze.py --text "Some content to check"

# Requires: Python >= 3.8, standard library only
"""

from __future__ import print_function

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Ensure UTF-8 output on Windows (where stdout defaults to system code page)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_API_VERSION = "2024-09-01"
_ALL_CATEGORIES = ["Hate", "SelfHarm", "Sexual", "Violence"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured JSON error to *stderr* for agent consumption."""
    msg = json.dumps({"error": str(what), "hint": hint})
    sys.stderr.write(msg + "\n")


def build_url(endpoint, api_version, content_type):
    # type: (str, str, str) -> str
    """Build the analyze URL. *content_type* is 'text' or 'image'."""
    endpoint = endpoint.rstrip("/")
    return "{}/contentsafety/{}:analyze?api-version={}".format(
        endpoint, content_type, api_version
    )


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _do_request(url, api_key, body, timeout, max_retries):
    # type: (str, str, dict, int, int) -> dict
    """POST JSON and return parsed response; retry on transient errors."""
    data = json.dumps(body).encode("utf-8")
    for attempt in range(max_retries + 1):
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/json",
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
            "Check AZURE_CONTENT_SAFETY_API_KEY. Find keys at "
            "portal.azure.com > Content Safety > Keys and Endpoint."
        )
    if code == 403:
        return "Access denied. Check resource permissions in Azure portal."
    if code == 400:
        hint = "Bad request."
        if detail:
            hint += " " + detail[:300]
        return hint
    if code == 404:
        return "Endpoint not found. Verify AZURE_CONTENT_SAFETY_ENDPOINT."
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
            "Analyze text or images for safety using Azure Content Safety. "
            "Provide --text for text analysis, or --file / --url for images."
        ),
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--text",
        help="Text content to analyze. Use '-' to read from stdin.",
    )
    source.add_argument(
        "--file", dest="file_path",
        help="Image file to analyze.",
    )
    source.add_argument(
        "--url", dest="image_url",
        help="Image blob URL to analyze.",
    )
    p.add_argument(
        "--categories",
        nargs="+",
        default=_ALL_CATEGORIES,
        choices=_ALL_CATEGORIES,
        help="Categories to check (default: all).",
    )
    p.add_argument(
        "--threshold",
        type=int,
        default=None,
        choices=[0, 2, 4, 6],
        help=(
            "Severity threshold. Exit code 2 if any category meets or "
            "exceeds this value. Useful for CI/CD gating."
        ),
    )
    p.add_argument(
        "--endpoint", default=None,
        help="Content Safety endpoint URL.",
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
    """Entry point. Returns 0 (safe), 1 (error), or 2 (flagged by threshold)."""
    args = parse_args(argv)

    # ---- Resolve endpoint ----
    endpoint = (
        args.endpoint or os.environ.get("AZURE_CONTENT_SAFETY_ENDPOINT")
    )
    if not endpoint:
        _emit_error(
            "No endpoint specified.",
            "Set AZURE_CONTENT_SAFETY_ENDPOINT or pass --endpoint. "
            "Find it at portal.azure.com > Content Safety > "
            "Keys and Endpoint.",
        )
        return 1

    # ---- Resolve API key ----
    api_key = os.environ.get("AZURE_CONTENT_SAFETY_API_KEY")
    if not api_key:
        _emit_error(
            "AZURE_CONTENT_SAFETY_API_KEY is not set.",
            "Run: export AZURE_CONTENT_SAFETY_API_KEY='...' \u2014 find your "
            "key at portal.azure.com > Content Safety > Keys and Endpoint.",
        )
        return 1

    # ---- Determine content type and build body ----
    if args.text is not None:
        # Text analysis
        text = sys.stdin.read().strip() if args.text == "-" else args.text
        if not text:
            _emit_error(
                "No text provided.",
                "Pass --text 'content' or --text - for stdin.",
            )
            return 1
        content_type = "text"
        body = {
            "text": text,
            "categories": args.categories,
            "outputType": "FourSeverityLevels",
        }
    elif args.file_path:
        # Image from file
        if not os.path.isfile(args.file_path):
            _emit_error(
                "File not found: '{}'.".format(args.file_path),
                "Check the path and ensure the file exists.",
            )
            return 1
        with open(args.file_path, "rb") as f:
            image_bytes = f.read()
        content_type = "image"
        body = {
            "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
            "categories": args.categories,
            "outputType": "FourSeverityLevels",
        }
    else:
        # Image from URL
        content_type = "image"
        body = {
            "image": {"blobUrl": args.image_url},
            "categories": args.categories,
            "outputType": "FourSeverityLevels",
        }

    # ---- Call API ----
    url = build_url(endpoint, args.api_version, content_type)

    try:
        result = _do_request(url, api_key, body, args.timeout, args.retries)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_error(
            "HTTP {} from Content Safety API.".format(exc.code),
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
        _emit_error(str(exc), "Unexpected error during content analysis.")
        return 1

    # ---- Output ----
    if args.raw:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        categories = {}
        max_severity = 0
        for item in result.get("categoriesAnalysis", []):
            cat = item.get("category", "")
            sev = item.get("severity", 0)
            categories[cat] = sev
            if sev > max_severity:
                max_severity = sev

        threshold = args.threshold
        if threshold is not None:
            safe = max_severity < threshold
        else:
            safe = max_severity == 0

        output = {
            "safe": safe,
            "maxSeverity": max_severity,
            "categories": categories,
        }
        json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")

    # ---- Threshold check ----
    if args.threshold is not None:
        max_sev = max(
            (item.get("severity", 0)
             for item in result.get("categoriesAnalysis", [])),
            default=0,
        )
        if max_sev >= args.threshold:
            sys.stderr.write(
                "Content flagged: max severity {} >= threshold {}\n".format(
                    max_sev, args.threshold
                )
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
