---
name: azure-ai-translator
description: >
  Translate text across 100+ languages using the Azure AI Translator API
  with a single, dependency-free Python script. Supports auto-detection of
  source language, multiple target languages, and batch translation.
  Use when the user wants to: (1) translate text from the terminal,
  (2) batch-translate content in CI/CD or agent workflows,
  (3) auto-detect the source language before translating.
  Triggers: "translate", "translator", "azure translator", "text translation",
  "language translation", "translate to french", "detect language"
---

# azure-ai-translator — Text Translation via a zero-dependency script

This skill calls the **Azure AI Translator Text API v3.0** using either the
global endpoint or a custom-domain resource endpoint.

## Features

- **100+ languages** — translate between any supported language pair
- **Auto-detect source** — omit `--from` to let the API detect the language
- **Multiple targets** — repeat `--to` for simultaneous translations
- **Batch input** — repeat `--text` for multiple texts in one call
- **stdin support** — use `--text -` to read from a pipe

## Prerequisites

- An Azure AI Translator resource (or multi-service Cognitive Services resource).
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_TRANSLATOR_API_KEY` | API key from your Translator resource. |
| `AZURE_TRANSLATOR_REGION` | Region (e.g. `eastus`). Required with the global endpoint. |
| `AZURE_TRANSLATOR_ENDPOINT` | *(Optional)* Custom-domain endpoint URL. If omitted, the global endpoint is used. |

## Scripts

### `scripts/translate.py`

**Simple translation (global endpoint):**

```sh
export AZURE_TRANSLATOR_API_KEY="..."
export AZURE_TRANSLATOR_REGION="eastus"

python3 skills/azure-ai-translator/scripts/translate.py \
  --to fr \
  --text "Hello, world!"
```

**Multiple target languages:**

```sh
python3 skills/azure-ai-translator/scripts/translate.py \
  --to fr --to de --to ja \
  --text "Good morning"
```

**Custom-domain endpoint (no region needed):**

```sh
export AZURE_TRANSLATOR_API_KEY="..."
export AZURE_TRANSLATOR_ENDPOINT="https://my-translator.cognitiveservices.azure.com"

python3 skills/azure-ai-translator/scripts/translate.py \
  --to es \
  --text "Hello"
```

**Batch translation:**

```sh
python3 skills/azure-ai-translator/scripts/translate.py \
  --to pt \
  --text "Hello" --text "Goodbye" --text "Thank you"
```

**Read from stdin:**

```sh
echo "Translate this paragraph" | \
  python3 skills/azure-ai-translator/scripts/translate.py \
  --to zh-Hans --text -
```

**Full API response:**

```sh
python3 skills/azure-ai-translator/scripts/translate.py \
  --to fr --text "Hello" --raw
```

See all options:

```sh
python3 skills/azure-ai-translator/scripts/translate.py --help
```
