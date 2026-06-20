#!/usr/bin/env python3
"""OpenAI / Azure OpenAI — Chat Completions (single prompt).

Service: OpenAI API / Azure OpenAI / Azure AI Foundry
Task:    Send one chat prompt to a model and print the response.

Works with both the real OpenAI API and Azure OpenAI deployments.
Provider is auto-detected from the endpoint URL or can be forced with
--provider.

Required environment variables (one of):
    OPENAI_API_KEY          API key for the OpenAI platform.
    AZURE_OPENAI_API_KEY    API key for an Azure OpenAI resource.

Example (OpenAI):
    export OPENAI_API_KEY="sk-..."
    python3 chat.py --model gpt-4o-mini --prompt "Hello!"

Example (Azure OpenAI):
    export AZURE_OPENAI_API_KEY="<your-key>"
    python3 chat.py \\
        --endpoint "https://<resource>.openai.azure.com" \\
        --model "gpt-4o-mini" \\
        --prompt "List three Azure AI services."
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
            + "/chat/completions?api-version="
            + api_version
        )
    return base + "/v1/chat/completions"


# ---------------------------------------------------------------------------
# HTTP call with retries on transient errors
# ---------------------------------------------------------------------------

def call_chat(url, api_key, payload, timeout, provider, max_retries=3):
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
                # Retry with exponential backoff on transient errors
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

    # Should not reach here, but satisfy type checkers
    raise RuntimeError("max retries exhausted")


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    # type: (Optional[list]) -> argparse.Namespace
    parser = argparse.ArgumentParser(
        description="Call the OpenAI or Azure OpenAI Chat Completions API "
        "(zero dependencies).",
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
        help="Model (or Azure deployment) name, e.g. gpt-4o-mini.",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help='User prompt to send. Use "-" to read from stdin.',
    )
    parser.add_argument(
        "--system",
        default=None,
        help="Optional system message.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "azure"],
        default=None,
        help="Force provider instead of auto-detecting from the endpoint URL.",
    )
    parser.add_argument(
        "--api-version",
        default=DEFAULT_API_VERSION,
        help="Azure OpenAI API version; ignored for OpenAI (default: %(default)s).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional max completion tokens.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Optional sampling temperature.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
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
        help="Print the full JSON response instead of just the message text.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    # type: (Optional[list]) -> int
    args = parse_args(argv)

    provider = args.provider or detect_provider(args.endpoint)

    # Resolve API key: prefer provider-specific var, fall back to the other
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
                "find your key in the Azure Portal under your OpenAI resource > "
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

    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": prompt})

    payload = {"messages": messages, "model": args.model}
    if args.max_tokens is not None:
        payload["max_completion_tokens"] = args.max_tokens
    if args.temperature is not None:
        payload["temperature"] = args.temperature

    url = build_url(args.endpoint, args.model, args.api_version, provider)

    try:
        result = call_chat(url, api_key, payload, args.timeout, provider, args.retries)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace") if exc.fp else ""
        hint = _hint_for_http_error(exc.code, provider, args.model, detail)
        _emit_error(
            "HTTP {0} {1}".format(exc.code, exc.reason),
            hint,
        )
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

    if args.raw:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        _emit_error(
            "Unexpected response shape — no choices[0].message.content found.",
            "Run with --raw to inspect the full API response. "
            "The model may have returned a refusal or an empty completion.",
        )
        json.dump(result, sys.stderr, indent=2)
        sys.stderr.write("\n")
        return 1

    print(content)
    return 0


def _hint_for_http_error(code, provider, model, detail):
    # type: (int, str, str, str) -> str
    """Return an actionable hint string based on the HTTP status code."""
    if code == 401 or code == 403:
        if provider == "azure":
            return (
                "Authentication failed. Verify AZURE_OPENAI_API_KEY is correct "
                "and not expired. Find your key in Azure Portal > your OpenAI "
                "resource > Keys and Endpoint."
            )
        return (
            "Authentication failed. Verify OPENAI_API_KEY is valid and has not "
            "been revoked. Generate a new key at "
            "https://platform.openai.com/api-keys"
        )
    if code == 404:
        if provider == "azure":
            return (
                "Deployment '{0}' not found. Verify the deployment exists in "
                "your Azure OpenAI resource (Portal > Model deployments) and "
                "that --endpoint points to the correct resource.".format(model)
            )
        return (
            "Model '{0}' not found. Check the model name is valid "
            "(e.g. gpt-4o-mini, gpt-4o). See "
            "https://platform.openai.com/docs/models".format(model)
        )
    if code == 429:
        return (
            "Rate limited. Wait before retrying, reduce request frequency, "
            "or check your usage tier / quota."
        )
    if code == 400:
        if "context_length" in detail or "max_tokens" in detail:
            return (
                "Request exceeds the model's context window. Shorten the prompt "
                "or reduce --max-tokens."
            )
        return (
            "Bad request — the API rejected the payload. Check --model, "
            "--prompt, and --max-tokens values. Run with --raw for details."
        )
    if code >= 500:
        return (
            "Server error on the provider side. This is usually transient — "
            "retry in a few seconds. If persistent, check "
            "https://status.openai.com or Azure Service Health."
        )
    return "Unexpected HTTP {0}. Inspect the response body above for details.".format(
        code
    )


if __name__ == "__main__":
    sys.exit(main())
