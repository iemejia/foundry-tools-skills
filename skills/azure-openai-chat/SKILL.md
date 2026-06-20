---
name: azure-openai-chat
description: >
  Call the Azure OpenAI Chat Completions API exposed through Azure AI Foundry
  using a single, dependency-free Python script.
  Use when the user wants to: (1) send a prompt to an Azure OpenAI chat
  deployment, (2) script LLM calls without installing the openai SDK,
  (3) get JSON-parseable completions from a terminal or CI job.
  Triggers: "azure openai chat", "call gpt deployment", "chat completion",
  "foundry chat", "openai without sdk"
---

# azure-openai-chat — Azure OpenAI Chat Completions via a zero-dependency script

This skill calls the **Azure OpenAI Chat Completions** endpoint
(`/openai/deployments/{deployment}/chat/completions`) using only the Python
standard library.

## Prerequisites

- An Azure OpenAI resource (or Azure AI Foundry project) with a deployed chat
  model (e.g. `gpt-4o-mini`).
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_API_KEY` | API key for the Azure OpenAI resource. |

The endpoint, deployment name, and API version are passed as CLI flags (the
endpoint may also be supplied via `AZURE_OPENAI_ENDPOINT`).

## Scripts

### `scripts/chat.py`

Send a single prompt (optionally with a system message) to a chat deployment
and print the response.

```sh
export AZURE_OPENAI_API_KEY="<your-key>"

python3 skills/azure-openai-chat/scripts/chat.py \
  --endpoint "https://<resource>.openai.azure.com" \
  --deployment "gpt-4o-mini" \
  --system "You are a terse assistant." \
  --prompt "List three Azure AI services."
```

Print the full JSON response instead of just the message text:

```sh
python3 skills/azure-openai-chat/scripts/chat.py \
  --endpoint "$AZURE_OPENAI_ENDPOINT" \
  --deployment "gpt-4o-mini" \
  --prompt "Say hi" \
  --raw
```

See all options:

```sh
python3 skills/azure-openai-chat/scripts/chat.py --help
```
