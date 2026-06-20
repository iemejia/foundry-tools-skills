#!/usr/bin/env python3
"""Translate text using the Azure AI Translator API.

Service: Azure AI Translator
Task:    Text translation (100+ languages, auto-detect source)
Env:     AZURE_TRANSLATOR_API_KEY  (required)
         AZURE_TRANSLATOR_ENDPOINT (optional; defaults to global endpoint)
         AZURE_TRANSLATOR_REGION   (required when using the global endpoint)

Example:
    export AZURE_TRANSLATOR_API_KEY="..."
    export AZURE_TRANSLATOR_REGION="eastus"
    python3 translate.py --to fr --text "Hello, world!"

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

# Ensure UTF-8 output on Windows (where stdout defaults to system code page)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GLOBAL_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
_DEFAULT_API_VERSION = "3.0"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured JSON error to *stderr* for agent consumption."""
    msg = json.dumps({"error": str(what), "hint": hint})
    sys.stderr.write(msg + "\n")


def detect_endpoint_type(endpoint):
    # type: (str) -> str
    """Return 'global' or 'custom' depending on the endpoint URL."""
    if "cognitive.microsofttranslator.com" in endpoint:
        return "global"
    return "custom"


def build_url(endpoint, api_version, to_langs, from_lang=None):
    # type: (str, str, list, str) -> str
    """Build the /translate URL with query parameters."""
    endpoint = endpoint.rstrip("/")
    ep_type = detect_endpoint_type(endpoint)
    if ep_type == "global":
        base = endpoint + "/translate"
    else:
        base = endpoint + "/translator/text/v" + api_version + "/translate"

    params = [("api-version", api_version)]
    for lang in to_langs:
        params.append(("to", lang))
    if from_lang:
        params.append(("from", from_lang))

    return base + "?" + urllib.parse.urlencode(params)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _do_request(url, headers, body, timeout, max_retries):
    # type: (str, dict, list, int, int) -> list
    """POST JSON and return parsed response; retry on transient errors."""
    data = json.dumps(body).encode("utf-8")
    for attempt in range(max_retries + 1):
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
    """Return an actionable hint for a given HTTP status code."""
    if code == 401:
        return (
            "Check AZURE_TRANSLATOR_API_KEY. Ensure the key is valid and "
            "matches the endpoint/region. Find keys at "
            "portal.azure.com > Translator > Keys and Endpoint."
        )
    if code == 403:
        return (
            "Access denied. The key may lack permissions or the resource "
            "may be disabled. Check Azure portal > Translator resource."
        )
    if code == 404:
        return (
            "Endpoint not found. Verify --endpoint URL. The global endpoint "
            "is https://api.cognitive.microsofttranslator.com"
        )
    if code == 400:
        hint = "Bad request. Check --to language codes are valid (ISO 639-1)."
        if detail:
            hint += " Detail: " + detail[:200]
        return hint
    if code == 429:
        return "Rate limited. Wait and retry, or upgrade your pricing tier."
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
        description="Translate text via the Azure AI Translator API."
    )
    p.add_argument(
        "--text",
        dest="texts",
        action="append",
        required=True,
        help="Text to translate. Use '-' for stdin. Repeat for batch.",
    )
    p.add_argument(
        "--to",
        dest="to_langs",
        action="append",
        required=True,
        help="Target language code (ISO 639-1, e.g. 'fr'). Repeat for multiple.",
    )
    p.add_argument(
        "--from",
        dest="from_lang",
        default=None,
        help="Source language code. Omit to auto-detect.",
    )
    p.add_argument(
        "--endpoint",
        default=None,
        help="Translator endpoint URL (default: global endpoint).",
    )
    p.add_argument(
        "--region",
        default=None,
        help="Azure region (required with the global endpoint).",
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
        args.endpoint
        or os.environ.get("AZURE_TRANSLATOR_ENDPOINT")
        or _GLOBAL_ENDPOINT
    )

    # ---- Resolve API key ----
    api_key = os.environ.get("AZURE_TRANSLATOR_API_KEY")
    if not api_key:
        _emit_error(
            "AZURE_TRANSLATOR_API_KEY is not set.",
            "Run: export AZURE_TRANSLATOR_API_KEY='...' \u2014 find your key "
            "at portal.azure.com > Translator > Keys and Endpoint.",
        )
        return 1

    # ---- Region check for global endpoint ----
    is_global = detect_endpoint_type(endpoint) == "global"
    region = args.region or os.environ.get("AZURE_TRANSLATOR_REGION")
    if is_global and not region:
        _emit_error(
            "Region required when using the global endpoint.",
            "Run: export AZURE_TRANSLATOR_REGION='eastus' or pass --region. "
            "Alternatively, use --endpoint with a custom-domain resource.",
        )
        return 1

    # ---- Read input texts ----
    texts = []
    for t in args.texts:
        if t == "-":
            texts.append(sys.stdin.read().strip())
        else:
            texts.append(t)

    if not any(texts):
        _emit_error(
            "No text provided.",
            "Pass --text 'Hello' or --text - for stdin.",
        )
        return 1

    # ---- Build request ----
    url = build_url(endpoint, args.api_version, args.to_langs, args.from_lang)
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json",
    }
    if is_global and region:
        headers["Ocp-Apim-Subscription-Region"] = region

    body = [{"Text": t} for t in texts]

    # ---- Call API ----
    try:
        result = _do_request(url, headers, body, args.timeout, args.retries)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_error(
            "HTTP {} from Translator API.".format(exc.code),
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
        _emit_error(str(exc), "Unexpected error during translation.")
        return 1

    # ---- Output ----
    if args.raw:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    # Structured output: one JSON line per source text per target language
    for i, item in enumerate(result):
        detected = item.get("detectedLanguage", {})
        if detected:
            sys.stderr.write(
                "Detected: {} ({:.0%})\n".format(
                    detected.get("language", "?"),
                    detected.get("score", 0),
                )
            )
        for tr in item.get("translations", []):
            out = {"to": tr["to"], "text": tr["text"]}
            if len(texts) > 1:
                out["index"] = i
            json.dump(out, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
