#!/usr/bin/env python3
"""Recognize speech from audio with Azure AI Speech (STT).

Service: Azure AI Speech
Task:    Speech-to-text for short audio (up to 60 seconds)
Env:     AZURE_AI_SPEECH_API_KEY  (required)
         AZURE_AI_SPEECH_REGION   (required unless --endpoint is used)
         AZURE_AI_SPEECH_ENDPOINT (optional; overrides region)

Example:
    export AZURE_AI_SPEECH_API_KEY="..."
    export AZURE_AI_SPEECH_REGION="eastus"
    python3 recognize.py --file recording.wav --language en-US

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

_AUDIO_CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".webm": "audio/webm",
    ".wma": "audio/x-ms-wma",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured JSON error to *stderr* for agent consumption."""
    msg = json.dumps({"error": str(what), "hint": hint})
    sys.stderr.write(msg + "\n")


def build_stt_url(endpoint=None, region=None, language="en-US",
                   output_format="simple", profanity="masked"):
    # type: (str, str, str, str, str) -> str
    """Build the STT recognition URL."""
    if endpoint:
        base = endpoint.rstrip("/")
    elif region:
        base = "https://{}.stt.speech.microsoft.com".format(region)
    else:
        raise ValueError("Either endpoint or region must be provided")

    params = urllib.parse.urlencode({
        "language": language,
        "format": output_format,
        "profanity": profanity,
    })
    return (
        "{}/speech/recognition/conversation/cognitiveservices/v1?{}".format(
            base, params
        )
    )


def _guess_content_type(filepath):
    # type: (str) -> str
    """Guess audio content type from file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    return _AUDIO_CONTENT_TYPES.get(ext, "audio/wav")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _do_request(url, api_key, audio_data, content_type, timeout, max_retries):
    # type: (str, str, bytes, str, int, int) -> dict
    """POST audio and return parsed JSON; retry on transient errors."""
    for attempt in range(max_retries + 1):
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": content_type,
            "Accept": "application/json",
        }
        req = urllib.request.Request(
            url, data=audio_data, headers=headers, method="POST"
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
            "Check AZURE_AI_SPEECH_API_KEY. Find keys at "
            "portal.azure.com > Speech resource > Keys and Endpoint."
        )
    if code == 403:
        return "Access denied. Check resource permissions in Azure portal."
    if code == 400:
        hint = "Bad request. Check audio format and --language."
        if detail:
            hint += " Detail: " + detail[:200]
        return hint
    if code == 404:
        return (
            "Endpoint not found. Verify --region or --endpoint. "
            "STT uses https://{region}.stt.speech.microsoft.com"
        )
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
            "Recognize speech from audio via Azure AI Speech. "
            "Supports short audio up to 60 seconds."
        ),
    )
    p.add_argument(
        "--file",
        dest="file_path",
        required=True,
        help="Audio file to recognize (WAV, MP3, OGG, FLAC, etc.).",
    )
    p.add_argument(
        "--language",
        default="en-US",
        help="Recognition language (default: %(default)s).",
    )
    p.add_argument(
        "--format",
        dest="output_format",
        choices=["simple", "detailed"],
        default="simple",
        help="Output detail level (default: %(default)s).",
    )
    p.add_argument(
        "--profanity",
        choices=["masked", "removed", "raw"],
        default="masked",
        help="Profanity handling (default: %(default)s).",
    )
    p.add_argument(
        "--endpoint", default=None,
        help="Speech endpoint URL (overrides --region).",
    )
    p.add_argument(
        "--region", default=None,
        help="Azure region (e.g. 'eastus').",
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

    # ---- Resolve connection ----
    endpoint = args.endpoint or os.environ.get("AZURE_AI_SPEECH_ENDPOINT")
    region = args.region or os.environ.get("AZURE_AI_SPEECH_REGION")

    if not endpoint and not region:
        _emit_error(
            "No region or endpoint specified.",
            "Set AZURE_AI_SPEECH_REGION (e.g. 'eastus') or "
            "AZURE_AI_SPEECH_ENDPOINT, or pass --region / --endpoint.",
        )
        return 1

    api_key = os.environ.get("AZURE_AI_SPEECH_API_KEY")
    if not api_key:
        _emit_error(
            "AZURE_AI_SPEECH_API_KEY is not set.",
            "Run: export AZURE_AI_SPEECH_API_KEY='...' \u2014 find your key "
            "at portal.azure.com > Speech resource > Keys and Endpoint.",
        )
        return 1

    # ---- Validate file ----
    if not os.path.isfile(args.file_path):
        _emit_error(
            "File not found: '{}'.".format(args.file_path),
            "Check the path and ensure the file exists.",
        )
        return 1

    # ---- Build URL ----
    url = build_stt_url(
        endpoint=endpoint, region=region,
        language=args.language,
        output_format=args.output_format,
        profanity=args.profanity,
    )

    # ---- Read audio ----
    with open(args.file_path, "rb") as f:
        audio_data = f.read()

    content_type = _guess_content_type(args.file_path)

    # ---- Call API ----
    try:
        result = _do_request(
            url, api_key, audio_data, content_type,
            args.timeout, args.retries,
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_error(
            "HTTP {} from Speech STT.".format(exc.code),
            _hint_for_http_error(exc.code, detail),
        )
        return 1
    except urllib.error.URLError as exc:
        _emit_error(
            "Connection failed: {}".format(exc.reason),
            "Check network, region, or endpoint.",
        )
        return 1
    except Exception as exc:
        _emit_error(str(exc), "Unexpected error during recognition.")
        return 1

    # ---- Check recognition status ----
    status = result.get("RecognitionStatus", "")
    if status != "Success":
        _emit_error(
            "Recognition status: {}".format(status),
            _recognition_hint(status),
        )
        return 1

    # ---- Output ----
    if args.raw:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if args.output_format == "detailed":
        nbest = result.get("NBest", [])
        output = {
            "status": status,
            "results": [
                {
                    "text": n.get("Display", ""),
                    "confidence": round(n.get("Confidence", 0), 3),
                    "lexical": n.get("Lexical", ""),
                }
                for n in nbest
            ],
        }
    else:
        output = {
            "status": status,
            "text": result.get("DisplayText", ""),
        }

    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _recognition_hint(status):
    # type: (str) -> str
    """Hint for non-Success recognition statuses."""
    hints = {
        "NoMatch": (
            "No speech detected. Check the audio file contains speech "
            "and --language matches the spoken language."
        ),
        "InitialSilenceTimeout": (
            "Audio started with silence. Ensure audio contains speech "
            "near the beginning."
        ),
        "BabbleTimeout": (
            "Audio contains too much background noise. Use cleaner audio."
        ),
        "Error": (
            "Recognition error. Check audio format (WAV, MP3, OGG, FLAC) "
            "and ensure the file is under 60 seconds."
        ),
    }
    return hints.get(status, "Unexpected status: {}".format(status))


if __name__ == "__main__":
    sys.exit(main())
