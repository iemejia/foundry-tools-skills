---
name: azure-openai-chat
description: >
  Call the OpenAI or Azure OpenAI Chat Completions API using a single,
  dependency-free Python script. Auto-detects the provider from the endpoint.
  Use when the user wants to: (1) send a prompt to an OpenAI or Azure OpenAI
  chat model, (2) script LLM calls without installing the openai SDK,
  (3) get JSON-parseable completions from a terminal or CI job.
  Triggers: "azure openai chat", "openai chat", "call gpt deployment",
  "chat completion", "foundry chat", "openai without sdk"
---

# azure-openai-chat — Chat Completions via a zero-dependency script

This skill calls the **Chat Completions** endpoint on either:

- **OpenAI** (`https://api.openai.com/v1/chat/completions`)
- **Azure OpenAI** (`/openai/deployments/{deployment}/chat/completions`)

Provider is auto-detected from the endpoint URL or can be forced with
`--provider`.

## Prerequisites

- For OpenAI: an API key from [platform.openai.com](https://platform.openai.com).
- For Azure OpenAI: a resource (or Azure AI Foundry project) with a deployed
  chat model (e.g. `gpt-4o-mini`).
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for the OpenAI platform. |
| `AZURE_OPENAI_API_KEY` | API key for an Azure OpenAI resource. |

Set one (or both). The script picks the right one based on the provider.
The endpoint may also be supplied via `AZURE_OPENAI_ENDPOINT`.

## Scripts

### `scripts/chat.py`

Send a single prompt (optionally with a system message) and print the response.

**OpenAI:**

```sh
export OPENAI_API_KEY="sk-..."

python3 skills/azure-openai-chat/scripts/chat.py \
  --model "gpt-4o-mini" \
  --prompt "Hello, world!"
```

**Azure OpenAI:**

```sh
export AZURE_OPENAI_API_KEY="<your-key>"

python3 skills/azure-openai-chat/scripts/chat.py \
  --endpoint "https://<resource>.openai.azure.com" \
  --model "gpt-4o-mini" \
  --system "You are a terse assistant." \
  --prompt "List three Azure AI services."
```

Print the full JSON response instead of just the message text:

```sh
python3 skills/azure-openai-chat/scripts/chat.py \
  --model "gpt-4o-mini" \
  --prompt "Say hi" \
  --raw
```

See all options:

```sh
python3 skills/azure-openai-chat/scripts/chat.py --help
```
