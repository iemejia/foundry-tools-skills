#!/usr/bin/env python3
"""OpenAI / Azure OpenAI — Text-to-Speech.

Service: OpenAI API / Azure OpenAI / Azure AI Foundry
Task:    Synthesize speech from text using tts-1 or tts-1-hd.

Works with both the real OpenAI API and Azure OpenAI deployments.
Provider is auto-detected from the endpoint URL or can be forced with
--provider.

Supported models:
    tts-1       Standard quality, low latency
    tts-1-hd    Higher quality audio

Voices: alloy, echo, fable, onyx, nova, shimmer

Required environment variables (one of):
    OPENAI_API_KEY          API key for the OpenAI platform.
    AZURE_OPENAI_API_KEY    API key for an Azure OpenAI resource.

Example (OpenAI):
    export OPENAI_API_KEY="sk-..."
    python3 tts.py --model tts-1-hd --voice nova --input "Hello, world!"

Example (Azure OpenAI):
    export AZURE_OPENAI_API_KEY="<your-key>"
    python3 tts.py \\
        --endpoint "https://<resource>.openai.azure.com" \\
        --model tts-1 \\
        --voice alloy \\
        --input "Hello from Azure!"
"""

# Requires: Python >= 3.8, standard library only

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Optional

# Ensure UTF-8 output on Windows (where stdout defaults to system code page)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_API_VERSION = "2024-10-21"
OPENAI_DEFAULT_ENDPOINT = "https://api.openai.com"
VOICES = ("alloy", "echo", "fable", "onyx", "nova", "shimmer")


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
            + "/audio/speech?api-version="
            + api_version
        )
    return base + "/v1/audio/speech"


# ---------------------------------------------------------------------------
# HTTP call with retries
# ---------------------------------------------------------------------------

def _do_request(url, api_key, payload, timeout, provider, max_retries):
    # type: (str, str, dict, float, str, int) -> bytes
    """Send TTS request and return raw audio bytes."""
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")
        if provider == "azure":
            request.add_header("api-key", api_key)
        else:
            request.add_header("Authorization", "Bearer " + api_key)

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
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
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    # type: (Optional[list]) -> argparse.Namespace
    parser = argparse.ArgumentParser(
        description="Synthesize speech with the OpenAI or Azure OpenAI TTS API "
        "(zero dependencies). Supports tts-1 and tts-1-hd.",
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
        help="Model or Azure deployment name: tts-1 or tts-1-hd.",
    )
    parser.add_argument(
        "--input",
        required=True,
        dest="input_text",
        help='Text to synthesize. Use "-" to read from stdin.',
    )
    parser.add_argument(
        "--voice",
        required=True,
        choices=VOICES,
        help="Voice to use: alloy, echo, fable, onyx, nova, or shimmer.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "azure"],
        default=None,
        help="Force provider instead of auto-detecting from the endpoint URL.",
    )
    parser.add_argument(
        "--response-format",
        choices=["mp3", "opus", "aac", "flac", "wav", "pcm"],
        default="mp3",
        help="Audio output format (default: mp3).",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=None,
        help="Speech speed: 0.25 to 4.0 (default: 1.0).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path. Defaults to 'speech.<format>' in current directory.",
    )
    parser.add_argument(
        "--api-version",
        default=DEFAULT_API_VERSION,
        help="Azure OpenAI API version; ignored for OpenAI (default: %(default)s).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
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
                "Deployment '{0}' not found. Verify the TTS deployment exists "
                "in your Azure OpenAI resource.".format(model)
            )
        return (
            "Model '{0}' not found. Valid TTS models: tts-1, tts-1-hd. "
            "See https://platform.openai.com/docs/models".format(model)
        )
    if code == 400:
        return (
            "Bad request. Check --model, --voice, --speed, and --input values. "
            "Max input length is ~4096 characters."
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

    # Read input from stdin if "-"
    text = args.input_text
    if text == "-":
        text = sys.stdin.read()
        if not text.strip():
            _emit_error(
                "Empty input read from stdin.",
                "Pipe text into the command or pass --input 'text' directly.",
            )
            return 1

    # Build payload
    payload = {"model": args.model, "input": text, "voice": args.voice}
    if args.response_format != "mp3":
        payload["response_format"] = args.response_format
    if args.speed is not None:
        payload["speed"] = args.speed

    url = build_url(args.endpoint, args.model, args.api_version, provider)

    # Make request
    try:
        audio_bytes = _do_request(
            url, api_key, payload, args.timeout, provider, args.retries
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

    # Write output
    output_path = args.output or "speech.{0}".format(args.response_format)
    try:
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
    except OSError as exc:
        _emit_error(
            "Cannot write to '{0}': {1}".format(output_path, exc),
            "Check that the path is writable or choose a different --output.",
        )
        return 1

    result = {"saved": output_path, "bytes": len(audio_bytes)}
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
