#!/usr/bin/env python3
"""OpenAI / Azure OpenAI — Image Generation.

Service: OpenAI API / Azure OpenAI / Azure AI Foundry
Task:    Generate images from a text prompt using gpt-image-1 or gpt-image-2.

Works with both the real OpenAI API and Azure OpenAI deployments.
Provider is auto-detected from the endpoint URL or can be forced with
--provider.

Supported models:
    gpt-image-1   1024x1024, 1536x1024, 1024x1536, auto; quality low/med/high
    gpt-image-2   1024x1024, 1536x1024, 1024x1536, 2048x2048, auto;
                  quality low/medium/high; up to n=4; 2K/4K resolution

Required environment variables (one of):
    OPENAI_API_KEY          API key for the OpenAI platform.
    AZURE_OPENAI_API_KEY    API key for an Azure OpenAI resource.

Example (OpenAI):
    export OPENAI_API_KEY="sk-..."
    python3 generate.py --model gpt-image-2 --prompt "A cat in space"

Example (Azure OpenAI):
    export AZURE_OPENAI_API_KEY="<your-key>"
    python3 generate.py \\
        --endpoint "https://<resource>.openai.azure.com" \\
        --model gpt-image-2 \\
        --prompt "A cat in space"
"""

# Requires: Python >= 3.8, standard library only

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Optional

DEFAULT_API_VERSION = "2024-10-21"
OPENAI_DEFAULT_ENDPOINT = "https://api.openai.com"


# ---------------------------------------------------------------------------
# Error reporting (structured JSON to stderr for agent consumption)
# ---------------------------------------------------------------------------

def _emit_error(what, hint):
    # type: (str, str) -> None
    """Print a structured error to stderr that coding agents can parse."""
    obj = {"error": what, "hint": hint}
    print(json.dumps(obj), file=sys.stderr)


# ---------------------------------------------------------------------------
# Provider detection and URL building
# ---------------------------------------------------------------------------

def detect_provider(endpoint):
    # type: (str) -> str
    """Return 'azure' or 'openai' based on the endpoint URL."""
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
            + "/images/generations?api-version="
            + api_version
        )
    return base + "/v1/images/generations"


# ---------------------------------------------------------------------------
# HTTP call with retries on transient errors
# ---------------------------------------------------------------------------

def _do_request(url, api_key, payload, timeout, provider, max_retries):
    # type: (str, str, dict, float, str, int) -> dict
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
                body = response.read().decode("utf-8")
            return json.loads(body)
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
# Image saving
# ---------------------------------------------------------------------------

def _save_image(image_data, index, output_dir, output_format):
    # type: (dict, int, str, str) -> str
    """Save a single image (from URL or b64) to disk. Returns file path."""
    ext = output_format if output_format in ("png", "jpeg", "webp") else "png"
    filename = "image_{0:03d}.{1}".format(index, ext)
    filepath = os.path.join(output_dir, filename)

    if "b64_json" in image_data:
        raw = base64.b64decode(image_data["b64_json"])
        with open(filepath, "wb") as f:
            f.write(raw)
    elif "url" in image_data:
        req = urllib.request.Request(image_data["url"])
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(filepath, "wb") as f:
                f.write(resp.read())
    else:
        _emit_error(
            "Image data has neither 'b64_json' nor 'url' field.",
            "Run with --raw to inspect the full API response.",
        )
        return ""

    return filepath


# ---------------------------------------------------------------------------
# Payload building (model-aware)
# ---------------------------------------------------------------------------

def build_payload(args, provider):
    # type: (argparse.Namespace, str) -> dict
    """Build the request payload, adapting parameters to the model."""
    model = args.model
    payload = {"prompt": args.prompt, "model": model}

    # Number of images
    if args.n is not None:
        if model == "gpt-image-2" and args.n > 4:
            _emit_error(
                "gpt-image-2 supports at most n=4 images per request.",
                "Set --n to 4 or fewer.",
            )
            sys.exit(1)
        payload["n"] = args.n
    else:
        payload["n"] = 1

    # Size
    if args.size:
        payload["size"] = args.size

    # Quality
    if args.quality:
        payload["quality"] = args.quality

    # Output format (gpt-image-* models use output_format, return b64 inline)
    if args.output_format:
        payload["output_format"] = args.output_format

    # Background
    if args.background:
        payload["background"] = args.background

    return payload


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    # type: (Optional[list]) -> argparse.Namespace
    parser = argparse.ArgumentParser(
        description="Generate images with the OpenAI or Azure OpenAI Images API "
        "(zero dependencies). Supports gpt-image-1 and gpt-image-2.",
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
        help="Model or Azure deployment name: gpt-image-1 or gpt-image-2.",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help='Text prompt describing the image. Use "-" to read from stdin.',
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "azure"],
        default=None,
        help="Force provider instead of auto-detecting from the endpoint URL.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=None,
        help="Number of images to generate (gpt-image-2 supports up to 4).",
    )
    parser.add_argument(
        "--size",
        default=None,
        help="Image size, e.g. 1024x1024, 1536x1024, 1024x1536, 2048x2048, "
        "or 'auto'.",
    )
    parser.add_argument(
        "--quality",
        default=None,
        help="Quality level: low, medium, or high.",
    )
    parser.add_argument(
        "--background",
        choices=["transparent", "opaque", "auto"],
        default=None,
        help="Background type.",
    )
    parser.add_argument(
        "--output-format",
        choices=["png", "jpeg", "webp"],
        default=None,
        help="Output image format (default: png).",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to save generated images (default: current directory).",
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
        help="Max retries on transient HTTP errors (429/5xx) (default: %(default)s).",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the full JSON response to stdout and do not save files.",
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
                "OpenAI resource (supported regions: East US 2, West US 3, "
                "Sweden Central) and that --endpoint is correct.".format(model)
            )
        return (
            "Model '{0}' not found or not available for your account. "
            "Valid models: gpt-image-1, gpt-image-2. "
            "See https://platform.openai.com/docs/models".format(model)
        )
    if code == 400:
        if "size" in detail:
            return (
                "Invalid size for model '{0}'. Supported sizes: "
                "gpt-image-1: 1024x1024/1536x1024/1024x1536/auto, "
                "gpt-image-2: 1024x1024/1536x1024/1024x1536/2048x2048/auto."
                .format(model)
            )
        if "content_policy" in detail or "safety" in detail:
            return (
                "Content policy violation. The prompt was rejected by the "
                "safety system. Revise the prompt to comply with usage policies."
            )
        return (
            "Bad request. Check --model, --size, --quality, --n values. "
            "Run with --raw for the full error response."
        )
    if code == 429:
        return (
            "Rate limited. Wait before retrying, reduce request frequency, "
            "or check your usage tier / quota."
        )
    if code >= 500:
        return (
            "Server error (transient). Retry in a few seconds. If persistent, "
            "check https://status.openai.com or Azure Service Health."
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

    # Read prompt from stdin if "-"
    prompt = args.prompt
    if prompt == "-":
        prompt = sys.stdin.read()
        if not prompt.strip():
            _emit_error(
                "Empty prompt read from stdin.",
                "Pipe content into the command or pass --prompt 'text' directly.",
            )
            return 1
    args.prompt = prompt

    # Build payload
    payload = build_payload(args, provider)
    url = build_url(args.endpoint, args.model, args.api_version, provider)

    # Make the request
    try:
        result = _do_request(url, api_key, payload, args.timeout, provider, args.retries)
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
            "Check that --endpoint '{0}' is correct and reachable. "
            "Verify network/proxy settings.".format(args.endpoint),
        )
        return 1
    except (ValueError, OSError) as exc:
        _emit_error(str(exc), "Check endpoint URL and network connectivity.")
        return 1

    # --raw: dump JSON and exit
    if args.raw:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    # Save images
    images = result.get("data", [])
    if not images:
        _emit_error(
            "No images returned in the response.",
            "Run with --raw to inspect the full API response.",
        )
        return 1

    # Ensure output directory exists
    if not os.path.isdir(args.output_dir):
        try:
            os.makedirs(args.output_dir)
        except OSError as exc:
            _emit_error(
                "Cannot create output directory '{0}': {1}".format(
                    args.output_dir, exc
                ),
                "Check that the path is writable or choose a different --output-dir.",
            )
            return 1

    fmt = args.output_format or "png"
    saved = []
    for i, img in enumerate(images):
        path = _save_image(img, i, args.output_dir, fmt)
        if path:
            saved.append(path)

    if not saved:
        _emit_error(
            "Failed to save any images.",
            "Run with --raw to inspect the API response format.",
        )
        return 1

    # Output saved file paths as JSON (machine-readable for agents)
    output = {"saved": saved, "count": len(saved)}
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())