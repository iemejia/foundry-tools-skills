#!/usr/bin/env python3
"""Synthesize speech with Azure AI Speech (TTS).

Service: Azure AI Speech
Task:    Text-to-speech with 400+ neural voices and SSML support
Env:     AZURE_AI_SPEECH_API_KEY  (required)
         AZURE_AI_SPEECH_REGION   (required unless --endpoint is used)
         AZURE_AI_SPEECH_ENDPOINT (optional; overrides region)

Example:
    export AZURE_AI_SPEECH_API_KEY="..."
    export AZURE_AI_SPEECH_REGION="eastus"
    python3 synthesize.py --voice en-US-JennyNeural --text "Hello!" -o hello.mp3

# Requires: Python >= 3.8, standard library only
"""

from __future__ import print_function

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from xml.sax.saxutils import escape as xml_escape

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OUTPUT_FORMATS = {
    "mp3": "audio-24khz-160kbitrate-mono-mp3",
    "mp3-16k": "audio-16khz-128kbitrate-mono-mp3",
    "mp3-48k": "audio-48khz-192kbitrate-mono-mp3",
    "wav": "riff-24khz-16bit-mono-pcm",
    "wav-16k": "riff-16khz-16bit-mono-pcm",
    "opus": "ogg-24khz-16bit-mono-opus",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured JSON error to *stderr* for agent consumption."""
    msg = json.dumps({"error": str(what), "hint": hint})
    sys.stderr.write(msg + "\n")


def build_tts_url(endpoint=None, region=None):
    # type: (str, str) -> str
    """Build the TTS endpoint URL."""
    if endpoint:
        return endpoint.rstrip("/") + "/cognitiveservices/v1"
    if region:
        return "https://{}.tts.speech.microsoft.com/cognitiveservices/v1".format(
            region
        )
    raise ValueError("Either endpoint or region must be provided")


def build_voices_url(endpoint=None, region=None):
    # type: (str, str) -> str
    """Build the voice list endpoint URL."""
    if endpoint:
        return endpoint.rstrip("/") + "/cognitiveservices/voices/list"
    if region:
        return "https://{}.tts.speech.microsoft.com/cognitiveservices/voices/list".format(
            region
        )
    raise ValueError("Either endpoint or region must be provided")


def build_ssml(text, voice, rate=None, pitch=None):
    # type: (str, str, str, str) -> str
    """Build SSML from text and voice parameters."""
    # Extract language from voice name (e.g. en-US-JennyNeural -> en-US)
    parts = voice.split("-")
    lang = "-".join(parts[:2]) if len(parts) >= 2 else "en-US"

    escaped = xml_escape(text)

    if rate or pitch:
        attrs = ""
        if rate:
            attrs += " rate='{}'".format(xml_escape(rate))
        if pitch:
            attrs += " pitch='{}'".format(xml_escape(pitch))
        inner = "<prosody{}>{}</prosody>".format(attrs, escaped)
    else:
        inner = escaped

    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
        "xml:lang='{lang}'>"
        "<voice name='{voice}'>{inner}</voice>"
        "</speak>"
    ).format(lang=lang, voice=voice, inner=inner)


def resolve_output_format(fmt):
    # type: (str) -> str
    """Resolve a short alias to the full output format string."""
    return _OUTPUT_FORMATS.get(fmt, fmt)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _do_request(url, api_key, ssml, output_format, timeout, max_retries):
    # type: (str, str, str, str, int, int) -> bytes
    """POST SSML and return audio bytes; retry on transient errors."""
    data = ssml.encode("utf-8")
    for attempt in range(max_retries + 1):
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": output_format,
            "User-Agent": "foundry-tools-skills",
        }
        req = urllib.request.Request(
            url, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
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


def _list_voices(url, api_key, timeout):
    # type: (str, str, int) -> list
    """Fetch the list of available voices."""
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


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
        hint = "Bad request. Check SSML syntax and voice name."
        if detail:
            hint += " Detail: " + detail[:200]
        return hint
    if code == 404:
        return (
            "Endpoint not found. Verify --region or --endpoint. "
            "TTS uses https://{region}.tts.speech.microsoft.com"
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
            "Synthesize speech via Azure AI Speech. "
            "Supports 400+ neural voices, SSML, and multiple audio formats."
        ),
    )
    p.add_argument(
        "--text",
        help="Text to synthesize. Use '-' for stdin.",
    )
    p.add_argument(
        "--ssml-file",
        help="SSML file to synthesize (overrides --text and --voice).",
    )
    p.add_argument(
        "--voice",
        default="en-US-JennyNeural",
        help="Voice name (default: %(default)s). Use --list-voices to browse.",
    )
    p.add_argument(
        "--output-format",
        default="mp3",
        help=(
            "Audio format. Short aliases: mp3, mp3-16k, mp3-48k, wav, "
            "wav-16k, opus. Or full format string (default: %(default)s)."
        ),
    )
    p.add_argument(
        "--output", "-o",
        help="Output file path. Defaults to speech.<ext>.",
    )
    p.add_argument(
        "--rate",
        default=None,
        help="Speech rate: x-slow, slow, medium, fast, x-fast, or percentage.",
    )
    p.add_argument(
        "--pitch",
        default=None,
        help="Voice pitch: x-low, low, medium, high, x-high, or Hz offset.",
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
        "--list-voices",
        action="store_true",
        help="List available voices and exit.",
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

    # ---- List voices mode ----
    if args.list_voices:
        try:
            voices_url = build_voices_url(endpoint=endpoint, region=region)
            voices = _list_voices(voices_url, api_key, args.timeout)
            # Print compact summary
            for v in voices:
                out = {
                    "name": v.get("ShortName", ""),
                    "locale": v.get("Locale", ""),
                    "gender": v.get("Gender", ""),
                    "localName": v.get("LocalName", ""),
                }
                json.dump(out, sys.stdout, ensure_ascii=False)
                sys.stdout.write("\n")
            return 0
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            _emit_error(
                "HTTP {} listing voices.".format(exc.code),
                _hint_for_http_error(exc.code, detail),
            )
            return 1
        except Exception as exc:
            _emit_error(str(exc), "Failed to list voices.")
            return 1

    # ---- Build SSML ----
    if args.ssml_file:
        if not os.path.isfile(args.ssml_file):
            _emit_error(
                "SSML file not found: '{}'.".format(args.ssml_file),
                "Check the path and ensure the file exists.",
            )
            return 1
        with open(args.ssml_file, "r") as f:
            ssml = f.read()
    elif args.text:
        text = sys.stdin.read().strip() if args.text == "-" else args.text
        if not text:
            _emit_error("No text provided.", "Pass --text 'Hello' or --text - for stdin.")
            return 1
        ssml = build_ssml(text, args.voice, rate=args.rate, pitch=args.pitch)
    else:
        _emit_error(
            "No input provided.",
            "Pass --text 'Hello', --ssml-file speech.xml, or --list-voices.",
        )
        return 1

    # ---- Resolve output format and file ----
    output_format = resolve_output_format(args.output_format)
    if args.output:
        output_path = args.output
    else:
        ext_map = {"mp3": ".mp3", "wav": ".wav", "opus": ".opus"}
        ext = ext_map.get(args.output_format, ".mp3")
        if args.output_format.startswith("riff"):
            ext = ".wav"
        elif "opus" in args.output_format:
            ext = ".opus"
        elif "mp3" in args.output_format:
            ext = ".mp3"
        output_path = "speech" + ext

    # ---- Call TTS API ----
    try:
        tts_url = build_tts_url(endpoint=endpoint, region=region)
        audio = _do_request(
            tts_url, api_key, ssml, output_format,
            args.timeout, args.retries,
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        _emit_error(
            "HTTP {} from Speech TTS.".format(exc.code),
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
        _emit_error(str(exc), "Unexpected error during speech synthesis.")
        return 1

    # ---- Save audio ----
    with open(output_path, "wb") as f:
        f.write(audio)

    result = {"saved": output_path, "bytes": len(audio), "format": output_format}
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
