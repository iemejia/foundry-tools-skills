#!/usr/bin/env python3
"""Azure OpenAI — Chat Completions (single prompt).

Service: Azure OpenAI / Azure AI Foundry
Task:    Send one chat prompt to a deployment and print the response.

Required environment variables:
    AZURE_OPENAI_API_KEY    API key for the Azure OpenAI resource.

The endpoint may be passed with --endpoint or via AZURE_OPENAI_ENDPOINT.

Example:
    export AZURE_OPENAI_API_KEY="<your-key>"
    python3 chat.py \\
        --endpoint "https://<resource>.openai.azure.com" \\
        --deployment "gpt-4o-mini" \\
        --system "You are a terse assistant." \\
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


def build_url(endpoint, deployment, api_version):
    # type: (str, str, str) -> str
    base = endpoint.rstrip("/")
    return (
        base
        + "/openai/deployments/"
        + deployment
        + "/chat/completions?api-version="
        + api_version
    )


def call_chat(url, api_key, payload, timeout):
    # type: (str, str, dict, float) -> dict
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("api-key", api_key)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def parse_args(argv=None):
    # type: (Optional[list]) -> argparse.Namespace
    parser = argparse.ArgumentParser(
        description="Call the Azure OpenAI Chat Completions API (zero dependencies).",
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        help="Resource endpoint, e.g. https://<resource>.openai.azure.com "
        "(or set AZURE_OPENAI_ENDPOINT).",
    )
    parser.add_argument(
        "--deployment",
        required=True,
        help="Deployment (model) name, e.g. gpt-4o-mini.",
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
        "--api-version",
        default=DEFAULT_API_VERSION,
        help="Azure OpenAI API version (default: %(default)s).",
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

    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        print("error: AZURE_OPENAI_API_KEY is not set", file=sys.stderr)
        return 1
    if not args.endpoint:
        print(
            "error: endpoint missing; pass --endpoint or set AZURE_OPENAI_ENDPOINT",
            file=sys.stderr,
        )
        return 1

    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})

    payload = {"messages": messages}
    if args.max_tokens is not None:
        payload["max_tokens"] = args.max_tokens
    if args.temperature is not None:
        payload["temperature"] = args.temperature

    url = build_url(args.endpoint, args.deployment, args.api_version)

    try:
        result = call_chat(url, api_key, payload, args.timeout)
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
