#!/usr/bin/env python3
"""Analyze documents with Azure Document Intelligence.

Service: Azure Document Intelligence (formerly Form Recognizer)
Task:    Extract text, tables, key-value pairs, and structured fields
Env:     AZURE_DOCUMENT_INTELLIGENCE_API_KEY  (required)
         AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT (required)

Example:
    export AZURE_DOCUMENT_INTELLIGENCE_API_KEY="..."
    export AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://<resource>.cognitiveservices.azure.com"
    python3 analyze.py --model prebuilt-layout --file invoice.pdf

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

_DEFAULT_API_VERSION = "2024-11-30"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured JSON error to *stderr* for agent consumption."""
    msg = json.dumps({"error": str(what), "hint": hint})
    sys.stderr.write(msg + "\n")


def build_analyze_url(endpoint, model, api_version, output_format=None, pages=None):
    # type: (str, str, str, str, str) -> str
    """Build the analyze URL with query parameters."""
    endpoint = endpoint.rstrip("/")
    url = (
        "{}/documentintelligence/documentModels/{}:analyze"
        "?api-version={}".format(
            endpoint, urllib.parse.quote(model, safe=""), api_version
        )
    )
    if output_format:
        url += "&outputContentFormat=" + urllib.parse.quote(output_format)
    if pages:
        url += "&pages=" + urllib.parse.quote(pages)
    return url


# ---------------------------------------------------------------------------
# HTTP — submit + poll
# ---------------------------------------------------------------------------


def _submit_analysis(url, api_key, file_path=None, source_url=None, timeout=60):
    # type: (str, str, str, str, int) -> str
    """Submit a document for analysis; return the Operation-Location URL."""
    headers = {"Ocp-Apim-Subscription-Key": api_key}

    if source_url:
        headers["Content-Type"] = "application/json"
        data = json.dumps({"urlSource": source_url}).encode("utf-8")
    elif file_path:
        headers["Content-Type"] = "application/octet-stream"
        with open(file_path, "rb") as f:
            data = f.read()
    else:
        raise ValueError("Either file_path or source_url is required")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        op_url = resp.headers.get("Operation-Location")
        if not op_url:
            raise RuntimeError(
                "No Operation-Location header in the 202 response. "
                "The endpoint may not support the requested model."
            )
        return op_url


def _poll_result(operation_url, api_key, poll_interval, max_wait, timeout):
    # type: (str, str, int, int, int) -> dict
    """Poll until analysis succeeds, fails, or times out."""
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    elapsed = 0

    while elapsed < max_wait:
        req = urllib.request.Request(
            operation_url, headers=headers, method="GET"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        status = result.get("status", "")
        if status == "succeeded":
            return result
        if status in ("failed", "canceled"):
            error = result.get("error", {})
            raise RuntimeError(
                "Analysis {}: {} \u2014 {}".format(
                    status,
                    error.get("code", "unknown"),
                    error.get("message", "no details"),
                )
            )

        sys.stderr.write(
            "Status: {} \u2014 polling in {}s (elapsed: {}s)\n".format(
                status, poll_interval, elapsed
            )
        )
        time.sleep(poll_interval)
        elapsed += poll_interval

    raise RuntimeError(
        "Analysis timed out after {}s. The operation may still be running. "
        "Poll manually: GET {}".format(max_wait, operation_url)
    )


# ---------------------------------------------------------------------------
# Error hints
# ---------------------------------------------------------------------------


def _hint_for_http_error(code, detail):
    # type: (int, str) -> str
    """Return an actionable hint for the HTTP status code."""
    if code == 401:
        return (
            "Check AZURE_DOCUMENT_INTELLIGENCE_API_KEY. Find keys at "
            "portal.azure.com > Document Intelligence > Keys and Endpoint."
        )
    if code == 403:
        return (
            "Access denied. Check permissions on the Document Intelligence "
            "resource in the Azure portal."
        )
    if code == 404:
        hint = "Not found. Verify --endpoint and --model."
        if detail and ("model" in detail.lower() or "not found" in detail.lower()):
            hint += (
                " Valid prebuilt models: prebuilt-read, prebuilt-layout, "
                "prebuilt-invoice, prebuilt-receipt, prebuilt-idDocument."
            )
        return hint
    if code == 400:
        hint = "Bad request."
        if detail:
            hint += " Detail: " + detail[:300]
        return hint
    if code == 413:
        return (
            "File too large. Max size is 500 MB (paid tier) or 4 MB (free tier)."
        )
    if code == 429:
        return "Rate limited. Wait and retry, or upgrade your pricing tier."
    if code >= 500:
        return "Server error ({}). Retry later.".format(code)
    return "HTTP {}: {}".format(code, detail[:200] if detail else "unknown")


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


def _format_tables(tables):
    # type: (list) -> list
    """Convert table cells into a row-oriented grid."""
    formatted = []
    for ti, table in enumerate(tables):
        rows = {}  # type: dict
        for cell in table.get("cells", []):
            r = cell.get("rowIndex", 0)
            c = cell.get("columnIndex", 0)
            rows.setdefault(r, {})[c] = cell.get("content", "")
        if not rows:
            formatted.append({"table_index": ti, "rows": []})
            continue
        max_col = max(max(cols.keys()) for cols in rows.values())
        grid = []
        for r in sorted(rows.keys()):
            row = [rows[r].get(c, "") for c in range(max_col + 1)]
            grid.append(row)
        formatted.append({"table_index": ti, "rows": grid})
    return formatted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    # type: (list) -> argparse.Namespace
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description="Analyze documents via Azure Document Intelligence."
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--file", dest="file_path", help="Local file to analyze."
    )
    source.add_argument(
        "--url", dest="source_url", help="Public URL of the document."
    )
    p.add_argument(
        "--model",
        default="prebuilt-layout",
        help=(
            "Model ID (default: %(default)s). Examples: prebuilt-read, "
            "prebuilt-layout, prebuilt-invoice, prebuilt-receipt, "
            "prebuilt-idDocument."
        ),
    )
    p.add_argument(
        "--endpoint", default=None, help="Document Intelligence endpoint URL."
    )
    p.add_argument(
        "--output-format",
        choices=["text", "markdown"],
        default=None,
        help="Content format: 'text' (default) or 'markdown' (tables as MD).",
    )
    p.add_argument(
        "--pages",
        default=None,
        help="Pages to analyze (e.g. '1-3,5'). Default: all.",
    )
    p.add_argument(
        "--api-version",
        default=_DEFAULT_API_VERSION,
        help="API version (default: %(default)s).",
    )
    p.add_argument(
        "--poll-interval",
        type=int,
        default=2,
        help="Seconds between status polls (default: %(default)s).",
    )
    p.add_argument(
        "--max-wait",
        type=int,
        default=120,
        help="Max seconds to wait for analysis (default: %(default)s).",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout per request in seconds (default: %(default)s).",
    )
    p.add_argument(
        "--raw",
        action="store_true",
        help="Print the full analysis result JSON.",
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
        args.endpoint or os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    )
    if not endpoint:
        _emit_error(
            "No endpoint specified.",
            "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or pass --endpoint. "
            "Find it at portal.azure.com > Document Intelligence > "
            "Keys and Endpoint.",
        )
        return 1

    # ---- Resolve API key ----
    api_key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_API_KEY")
    if not api_key:
        _emit_error(
            "AZURE_DOCUMENT_INTELLIGENCE_API_KEY is not set.",
            "Run: export AZURE_DOCUMENT_INTELLIGENCE_API_KEY='...' \u2014 "
            "find your key at portal.azure.com > Document Intelligence > "
            "Keys and Endpoint.",
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
    url = build_analyze_url(
        endpoint, args.model, args.api_version,
        output_format=args.output_format, pages=args.pages,
    )

    # ---- Submit ----
    try:
        operation_url = _submit_analysis(
            url, api_key,
            file_path=args.file_path,
            source_url=args.source_url,
            timeout=args.timeout,
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_error(
            "HTTP {} submitting document.".format(exc.code),
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
        _emit_error(str(exc), "Failed to submit document for analysis.")
        return 1

    sys.stderr.write("Submitted. Polling for results...\n")

    # ---- Poll ----
    try:
        result = _poll_result(
            operation_url, api_key,
            args.poll_interval, args.max_wait, args.timeout,
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_error(
            "HTTP {} polling results.".format(exc.code),
            _hint_for_http_error(exc.code, detail),
        )
        return 1
    except RuntimeError as exc:
        _emit_error(str(exc), "Analysis did not complete successfully.")
        return 1
    except Exception as exc:
        _emit_error(str(exc), "Unexpected error polling results.")
        return 1

    # ---- Output ----
    if args.raw:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    analyze = result.get("analyzeResult", {})
    output = {
        "model": args.model,
        "content": analyze.get("content", ""),
        "pages": len(analyze.get("pages", [])),
    }

    tables = analyze.get("tables", [])
    if tables:
        output["tables"] = _format_tables(tables)

    kv_pairs = analyze.get("keyValuePairs", [])
    if kv_pairs:
        output["keyValuePairs"] = [
            {
                "key": p.get("key", {}).get("content", ""),
                "value": p.get("value", {}).get("content", ""),
            }
            for p in kv_pairs
        ]

    documents = analyze.get("documents", [])
    if documents:
        output["documents"] = []
        for doc in documents:
            fields = {}
            for fname, fval in doc.get("fields", {}).items():
                fields[fname] = fval.get("content", "")
            output["documents"].append(
                {
                    "docType": doc.get("docType", ""),
                    "confidence": doc.get("confidence", 0),
                    "fields": fields,
                }
            )

    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
