#!/usr/bin/env python3
"""OpenAI / Azure OpenAI — Audio Transcription (Speech-to-Text).

Service: OpenAI API / Azure OpenAI / Azure AI Foundry
Task:    Transcribe an audio file to text using whisper-1 or gpt-4o-transcribe.

Works with both the real OpenAI API and Azure OpenAI deployments.
Provider is auto-detected from the endpoint URL or can be forced with
--provider.

Supported models:
    whisper-1              Original Whisper model
    gpt-4o-transcribe      Higher accuracy, word-level timestamps
    gpt-4o-mini-transcribe Faster, lower cost variant

Supported audio formats: mp3, mp4, mpeg, mpga, m4a, wav, webm

Required environment variables (one of):
    OPENAI_API_KEY          API key for the OpenAI platform.
    AZURE_OPENAI_API_KEY    API key for an Azure OpenAI resource.

Example (OpenAI):
    export OPENAI_API_KEY="sk-..."
    python3 transcribe.py --model whisper-1 --file recording.mp3

Example (Azure OpenAI):
    export AZURE_OPENAI_API_KEY="<your-key>"
    python3 transcribe.py \\
        --endpoint "https://<resource>.openai.azure.com" \\
        --model gpt-4o-transcribe \\
        --file meeting.wav --language en
"""

# Requires: Python >= 3.8, standard library only

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Optional

DEFAULT_API_VERSION = "2024-10-21"
OPENAI_DEFAULT_ENDPOINT = "https://api.openai.com"


# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------

def _emit_error(what, hint):
    # type: (str, str) -> None
    obj = {"error": what, "hint": hint}
    print(json.dumps(obj), file=sys.stderr)


# ---------------------------------------------------------------------------
# Provider detection and URL building
# ---------------------------------------------------------------------------

def detect_provider(endpoint):
    # type: (str) -> str
    if "openai.azure.com" in endpoint or "cognitiveservices.azure.com" in endpoint:
        return "azure"
    return "openai"


def build_url(endpoint, model, api_version, provider):
    # type: (str, str, str, str) -> str
    base = endpoint.rstrip("/")
    if provider == "azure":
        return (
            base
            + "/openai/deployments/"
            + model
            + "/audio/transcriptions?api-version="
            + api_version
        )
    return base + "/v1/audio/transcriptions"


# ---------------------------------------------------------------------------
# Multipart form-data builder (stdlib only, no requests)
# ---------------------------------------------------------------------------

def _build_multipart(fields, files):
    # type: (dict, dict) -> tuple
    """Build a multipart/form-data body from fields and files.

    Args:
        fields: dict of {name: value} for text fields
        files: dict of {name: (filename, data, content_type)} for file fields

    Returns:
        (body_bytes, content_type_header)
    """
    boundary = "----FormBoundary" + uuid.uuid4().hex[:16]
    parts = []

    for name, value in fields.items():
        parts.append(
            "--{0}\r\nContent-Disposition: form-data; name=\"{1}\"\r\n\r\n{2}\r\n"
            .format(boundary, name, value)
        )

    for name, (filename, data, content_type) in files.items():
        parts.append(
            "--{0}\r\nContent-Disposition: form-data; name=\"{1}\"; "
            "filename=\"{2}\"\r\nContent-Type: {3}\r\n\r\n".format(
                boundary, name, filename, content_type
            )
        )
        # We need to handle binary data separately
        parts.append(data)
        parts.append("\r\n")

    parts.append("--{0}--\r\n".format(boundary))

    # Combine text and binary parts
    body = b""
    for part in parts:
        if isinstance(part, bytes):
            body += part
        else:
            body += part.encode("utf-8")

    content_type = "multipart/form-data; boundary={0}".format(boundary)
    return body, content_type


# ---------------------------------------------------------------------------
# HTTP call with retries
# ---------------------------------------------------------------------------

def _do_request(url, api_key, body, content_type, timeout, provider, max_retries):
    # type: (str, str, bytes, str, float, str, int) -> str
    """Send transcription request and return response body as string."""
    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", content_type)
        if provider == "azure":
            request.add_header("api-key", api_key)
        else:
            request.add_header("Authorization", "Bearer " + api_key)

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait = 2 ** attempt
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if retry_after and retry_after.isdigit():
                    wait = max(wait, int(retry_after))
                print(
                    json.dumps({
                        "error": "HTTP {0}, retrying in {1}s (attempt {2}/{3})".format(
                            exc.code, wait, attempt + 1, max_retries
                        ),
                        "hint": "Transient error; retrying automatically."
                    }),
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            raise

    raise RuntimeError("max retries exhausted")


# ---------------------------------------------------------------------------
# MIME type mapping
# ---------------------------------------------------------------------------

_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}


def _guess_mime(filepath):
    # type: (str) -> str
    ext = os.path.splitext(filepath)[1].lower()
    return _MIME_TYPES.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    # type: (Optional[list]) -> argparse.Namespace
    parser = argparse.ArgumentParser(
        description="Transcribe audio with the OpenAI or Azure OpenAI API "
        "(zero dependencies). Supports whisper-1 and gpt-4o-transcribe.",
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT", OPENAI_DEFAULT_ENDPOINT),
        help="API endpoint URL. Defaults to AZURE_OPENAI_ENDPOINT env var, "
        "or https://api.openai.com if unset.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model or Azure deployment name: whisper-1, gpt-4o-transcribe, "
        "or gpt-4o-mini-transcribe.",
    )
    parser.add_argument(
        "--file",
        required=True,
        dest="audio_file",
        help="Path to the audio file to transcribe.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "azure"],
        default=None,
        help="Force provider instead of auto-detecting from the endpoint URL.",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="ISO 639-1 language code (e.g. en, de, fr). Default: auto-detect.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Optional text to guide the model's style or provide context.",
    )
    parser.add_argument(
        "--response-format",
        choices=["json", "text", "srt", "verbose_json", "vtt"],
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature, 0 to 1 (default: 0).",
    )
    parser.add_argument(
        "--api-version",
        default=DEFAULT_API_VERSION,
        help="Azure OpenAI API version; ignored for OpenAI (default: %(default)s).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="HTTP timeout in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max retries on transient HTTP errors (default: %(default)s).",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# HTTP error hints
# ---------------------------------------------------------------------------

def _hint_for_http_error(code, provider, model, detail):
    # type: (int, str, str, str) -> str
    if code == 401 or code == 403:
        if provider == "azure":
            return (
                "Authentication failed. Verify AZURE_OPENAI_API_KEY is correct. "
                "Find your key in Azure Portal > OpenAI resource > Keys and Endpoint."
            )
        return (
            "Authentication failed. Verify OPENAI_API_KEY is valid. "
            "Generate a new key at https://platform.openai.com/api-keys"
        )
    if code == 404:
        if provider == "azure":
            return (
                "Deployment '{0}' not found. Verify it exists in your Azure "
                "OpenAI resource.".format(model)
            )
        return (
            "Model '{0}' not found. Valid models: whisper-1, gpt-4o-transcribe, "
            "gpt-4o-mini-transcribe. "
            "See https://platform.openai.com/docs/models".format(model)
        )
    if code == 400:
        if "format" in detail or "file" in detail:
            return (
                "Unsupported audio format or file issue. Supported formats: "
                "mp3, mp4, mpeg, mpga, m4a, wav, webm. Max file size ~25MB."
            )
        return (
            "Bad request. Check --model, --file, and --language values."
        )
    if code == 413:
        return (
            "File too large. The audio file exceeds the maximum size (~25MB). "
            "Compress or split the audio before uploading."
        )
    if code == 429:
        return (
            "Rate limited. Wait before retrying or reduce request frequency."
        )
    if code >= 500:
        return (
            "Server error (transient). Retry in a few seconds. "
            "Check https://status.openai.com or Azure Service Health."
        )
    return "Unexpected HTTP {0}. Inspect the response body for details.".format(code)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    # type: (Optional[list]) -> int
    args = parse_args(argv)

    provider = args.provider or detect_provider(args.endpoint)

    # Resolve API key
    if provider == "azure":
        api_key = os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get(
            "OPENAI_API_KEY"
        )
    else:
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get(
            "AZURE_OPENAI_API_KEY"
        )

    if not api_key:
        if provider == "azure":
            _emit_error(
                "AZURE_OPENAI_API_KEY is not set.",
                "Run: export AZURE_OPENAI_API_KEY='<key>' — "
                "find your key in Azure Portal > OpenAI resource > "
                "Keys and Endpoint.",
            )
        else:
            _emit_error(
                "OPENAI_API_KEY is not set.",
                "Run: export OPENAI_API_KEY='sk-...' — "
                "generate a key at https://platform.openai.com/api-keys",
            )
        return 1

    # Read audio file
    if not os.path.isfile(args.audio_file):
        _emit_error(
            "File not found: '{0}'.".format(args.audio_file),
            "Check the path and ensure the file exists.",
        )
        return 1

    try:
        with open(args.audio_file, "rb") as f:
            audio_data = f.read()
    except OSError as exc:
        _emit_error(
            "Cannot read '{0}': {1}".format(args.audio_file, exc),
            "Check file permissions.",
        )
        return 1

    # Build multipart form data
    fields = {"model": args.model}
    if args.language:
        fields["language"] = args.language
    if args.prompt:
        fields["prompt"] = args.prompt
    if args.response_format != "json":
        fields["response_format"] = args.response_format
    if args.temperature is not None:
        fields["temperature"] = str(args.temperature)

    filename = os.path.basename(args.audio_file)
    mime_type = _guess_mime(args.audio_file)
    files = {"file": (filename, audio_data, mime_type)}

    body, content_type = _build_multipart(fields, files)
    url = build_url(args.endpoint, args.model, args.api_version, provider)

    # Make request
    try:
        response_text = _do_request(
            url, api_key, body, content_type, args.timeout, provider, args.retries
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace") if exc.fp else ""
        hint = _hint_for_http_error(exc.code, provider, args.model, detail)
        _emit_error("HTTP {0} {1}".format(exc.code, exc.reason), hint)
        if detail:
            print(detail, file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        _emit_error(
            "Request failed: {0}".format(exc.reason),
            "Check that --endpoint '{0}' is correct and reachable.".format(
                args.endpoint
            ),
        )
        return 1
    except (ValueError, OSError) as exc:
        _emit_error(str(exc), "Check endpoint URL and network connectivity.")
        return 1

    # Output the transcription
    print(response_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
