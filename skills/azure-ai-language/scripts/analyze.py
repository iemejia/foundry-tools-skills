#!/usr/bin/env python3
"""Analyze text with Azure AI Language.

Service: Azure AI Language
Task:    Sentiment analysis, NER, key phrases, PII detection, language
         detection
Env:     AZURE_AI_LANGUAGE_API_KEY  (required)
         AZURE_AI_LANGUAGE_ENDPOINT (required)

Example:
    export AZURE_AI_LANGUAGE_API_KEY="..."
    export AZURE_AI_LANGUAGE_ENDPOINT="https://<resource>.cognitiveservices.azure.com"
    python3 analyze.py --task sentiment --text "I love this product!"

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

_DEFAULT_API_VERSION = "2023-04-01"

_TASK_MAP = {
    "sentiment": "SentimentAnalysis",
    "entities": "EntityRecognition",
    "key-phrases": "KeyPhraseExtraction",
    "pii": "PiiEntityRecognition",
    "language-detection": "LanguageDetection",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured JSON error to *stderr* for agent consumption."""
    msg = json.dumps({"error": str(what), "hint": hint})
    sys.stderr.write(msg + "\n")


def build_url(endpoint, api_version):
    # type: (str, str) -> str
    """Build the /language/:analyze-text URL."""
    endpoint = endpoint.rstrip("/")
    return "{}/language/:analyze-text?api-version={}".format(
        endpoint, api_version
    )


def build_request_body(task, texts, language=None):
    # type: (str, list, str) -> dict
    """Build the API request body for the given task and input texts."""
    kind = _TASK_MAP[task]
    documents = []
    for i, text in enumerate(texts):
        doc = {"id": str(i + 1), "text": text}
        # Language detection doesn't accept a language hint
        if language and task != "language-detection":
            doc["language"] = language
        documents.append(doc)

    return {
        "kind": kind,
        "analysisInput": {"documents": documents},
    }


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
            "Check AZURE_AI_LANGUAGE_API_KEY. Find keys at "
            "portal.azure.com > Language resource > Keys and Endpoint."
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
        return "Endpoint not found. Verify AZURE_AI_LANGUAGE_ENDPOINT."
    if code == 429:
        return "Rate limited. Wait and retry, or upgrade pricing tier."
    if code >= 500:
        return "Server error ({}). Retry later.".format(code)
    return "HTTP {}: {}".format(code, detail[:200] if detail else "unknown")


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


def _format_result(task, result):
    # type: (str, dict) -> list
    """Extract key information based on the task type."""
    results = result.get("results", {})
    documents = results.get("documents", [])
    formatted = []

    for doc in documents:
        out = {"id": doc.get("id", "")}

        if task == "sentiment":
            out["sentiment"] = doc.get("sentiment", "")
            out["scores"] = doc.get("confidenceScores", {})
            sentences = doc.get("sentences", [])
            if sentences:
                out["sentences"] = [
                    {
                        "text": s.get("text", ""),
                        "sentiment": s.get("sentiment", ""),
                        "scores": s.get("confidenceScores", {}),
                    }
                    for s in sentences
                ]

        elif task == "entities":
            out["entities"] = [
                {
                    "text": e.get("text", ""),
                    "category": e.get("category", ""),
                    "subcategory": e.get("subcategory", ""),
                    "confidence": round(e.get("confidenceScore", 0), 3),
                }
                for e in doc.get("entities", [])
            ]

        elif task == "key-phrases":
            out["keyPhrases"] = doc.get("keyPhrases", [])

        elif task == "pii":
            out["redactedText"] = doc.get("redactedText", "")
            out["entities"] = [
                {
                    "text": e.get("text", ""),
                    "category": e.get("category", ""),
                    "subcategory": e.get("subcategory", ""),
                    "confidence": round(e.get("confidenceScore", 0), 3),
                }
                for e in doc.get("entities", [])
            ]

        elif task == "language-detection":
            lang = doc.get("detectedLanguage", {})
            out["language"] = lang.get("iso6391Name", "")
            out["name"] = lang.get("name", "")
            out["confidence"] = round(lang.get("confidenceScore", 0), 3)

        formatted.append(out)

    return formatted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    # type: (list) -> argparse.Namespace
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description="Analyze text via the Azure AI Language API."
    )
    p.add_argument(
        "--task",
        required=True,
        choices=sorted(_TASK_MAP.keys()),
        help="Analysis task to perform.",
    )
    p.add_argument(
        "--text",
        dest="texts",
        action="append",
        required=True,
        help="Text to analyze. Use '-' for stdin. Repeat for batch.",
    )
    p.add_argument(
        "--language",
        default=None,
        help="Document language hint (ISO 639-1, e.g. 'en').",
    )
    p.add_argument(
        "--endpoint", default=None, help="Language endpoint URL."
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
    endpoint = args.endpoint or os.environ.get("AZURE_AI_LANGUAGE_ENDPOINT")
    if not endpoint:
        _emit_error(
            "No endpoint specified.",
            "Set AZURE_AI_LANGUAGE_ENDPOINT or pass --endpoint. "
            "Find it at portal.azure.com > Language resource > "
            "Keys and Endpoint.",
        )
        return 1

    # ---- Resolve API key ----
    api_key = os.environ.get("AZURE_AI_LANGUAGE_API_KEY")
    if not api_key:
        _emit_error(
            "AZURE_AI_LANGUAGE_API_KEY is not set.",
            "Run: export AZURE_AI_LANGUAGE_API_KEY='...' \u2014 find your key "
            "at portal.azure.com > Language resource > Keys and Endpoint.",
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
            "Pass --text 'some text' or --text - for stdin.",
        )
        return 1

    # ---- Build request ----
    url = build_url(endpoint, args.api_version)
    body = build_request_body(args.task, texts, language=args.language)

    # ---- Call API ----
    try:
        result = _do_request(url, api_key, body, args.timeout, args.retries)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_error(
            "HTTP {} from Language API.".format(exc.code),
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
        _emit_error(str(exc), "Unexpected error during text analysis.")
        return 1

    # ---- Check for document-level errors ----
    doc_errors = result.get("results", {}).get("errors", [])
    if doc_errors:
        for err in doc_errors:
            _emit_error(
                "Document {}: {}".format(
                    err.get("id", "?"),
                    err.get("error", {}).get("message", "unknown"),
                ),
                "Check input text and --language parameter.",
            )

    # ---- Output ----
    if args.raw:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    formatted = _format_result(args.task, result)
    for item in formatted:
        json.dump(item, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
