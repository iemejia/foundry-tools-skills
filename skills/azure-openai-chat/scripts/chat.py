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
import urllib.error
import urllib.request
from typing import Optional

DEFAULT_API_VERSION = "2024-10-21"
OPENAI_DEFAULT_ENDPOINT = "https://api.openai.com"


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
    # OpenAI-compatible endpoint
    return base + "/v1/chat/completions"


def call_chat(url, api_key, payload, timeout, provider):
    # type: (str, str, dict, float, str) -> dict
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if provider == "azure":
        request.add_header("api-key", api_key)
    else:
        request.add_header("Authorization", "Bearer " + api_key)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


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
        help="User prompt to send.",
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
        "--raw",
        action="store_true",
        help="Print the full JSON response instead of just the message text.",
    )
    return parser.parse_args(argv)


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
        print(
            "error: set OPENAI_API_KEY or AZURE_OPENAI_API_KEY",
            file=sys.stderr,
        )
        return 1

    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})

    payload = {"messages": messages, "model": args.model}
    if args.max_tokens is not None:
        payload["max_tokens"] = args.max_tokens
    if args.temperature is not None:
        payload["temperature"] = args.temperature

    url = build_url(args.endpoint, args.model, args.api_version, provider)

    try:
        result = call_chat(url, api_key, payload, args.timeout, provider)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace") if exc.fp else ""
        print(
            "error: HTTP {0} {1}\n{2}".format(exc.code, exc.reason, detail),
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as exc:
        print("error: request failed: {0}".format(exc.reason), file=sys.stderr)
        return 1
    except (ValueError, OSError) as exc:
        print("error: {0}".format(exc), file=sys.stderr)
        return 1

    if args.raw:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print("error: unexpected response shape:", file=sys.stderr)
        json.dump(result, sys.stderr, indent=2)
        sys.stderr.write("\n")
        return 1

    print(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
