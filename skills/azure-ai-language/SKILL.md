---
name: azure-ai-language
description: >
  Analyze text using the Azure AI Language API with a single, dependency-free
  Python script. Supports sentiment analysis, named entity recognition (NER),
  key phrase extraction, PII detection, and language detection.
  Use when the user wants to: (1) detect sentiment in text,
  (2) extract named entities, (3) find key phrases,
  (4) detect and redact PII, (5) detect the language of text.
  Triggers: "sentiment", "NER", "named entities", "key phrases",
  "PII detection", "detect language", "text analysis", "azure language",
  "sentiment analysis", "entity recognition"
---

# azure-ai-language — Text Analysis via a zero-dependency script

This skill calls the **Azure AI Language** unified `/language/:analyze-text`
endpoint for five pre-built text analysis tasks.

## Supported tasks

| Task | CLI name | Description |
|------|----------|-------------|
| Sentiment Analysis | `sentiment` | Positive/neutral/negative with per-sentence scores |
| Named Entity Recognition | `entities` | People, places, organizations, dates, etc. |
| Key Phrase Extraction | `key-phrases` | Key concepts and topics |
| PII Detection | `pii` | Detect and redact personal information |
| Language Detection | `language-detection` | Identify text language (120+ languages) |

## Prerequisites

- An Azure AI Language resource.
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_AI_LANGUAGE_API_KEY` | API key from your Language resource. |
| `AZURE_AI_LANGUAGE_ENDPOINT` | Endpoint URL (e.g. `https://<resource>.cognitiveservices.azure.com`). |

## Scripts

### `scripts/analyze.py`

**Sentiment analysis:**

```sh
export AZURE_AI_LANGUAGE_API_KEY="..."
export AZURE_AI_LANGUAGE_ENDPOINT="https://<resource>.cognitiveservices.azure.com"

python3 skills/azure-ai-language/scripts/analyze.py \
  --task sentiment \
  --text "I love this product! The quality is amazing."
```

**Named entity recognition:**

```sh
python3 skills/azure-ai-language/scripts/analyze.py \
  --task entities \
  --text "Microsoft was founded by Bill Gates in 1975 in Albuquerque."
```

**Key phrase extraction:**

```sh
python3 skills/azure-ai-language/scripts/analyze.py \
  --task key-phrases \
  --text "The food was great and the service was excellent."
```

**PII detection:**

```sh
python3 skills/azure-ai-language/scripts/analyze.py \
  --task pii \
  --text "My phone number is 555-123-4567 and my email is john@example.com"
```

**Language detection:**

```sh
python3 skills/azure-ai-language/scripts/analyze.py \
  --task language-detection \
  --text "Bonjour le monde"
```

**Batch analysis:**

```sh
python3 skills/azure-ai-language/scripts/analyze.py \
  --task sentiment \
  --text "Great product!" \
  --text "Terrible experience." \
  --text "It was okay."
```

**Read from stdin:**

```sh
echo "Analyze this text" | python3 skills/azure-ai-language/scripts/analyze.py \
  --task key-phrases --text -
```

**Full API response:**

```sh
python3 skills/azure-ai-language/scripts/analyze.py \
  --task sentiment --text "Hello" --raw
```

See all options:

```sh
python3 skills/azure-ai-language/scripts/analyze.py --help
```
