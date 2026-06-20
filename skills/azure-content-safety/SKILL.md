---
name: azure-content-safety
description: >
  Analyze text and images for harmful content using Azure Content Safety
  with a single, dependency-free Python script. Detects Hate, SelfHarm,
  Sexual, and Violence with four severity levels.
  Use when the user wants to: (1) moderate user-generated content,
  (2) gate CI/CD pipelines on content safety,
  (3) classify content severity before publishing.
  Triggers: "content safety", "content moderation", "harmful content",
  "text moderation", "image moderation", "safety check", "hate detection",
  "violence detection"
---

# azure-content-safety — Content Moderation via a zero-dependency script

This skill calls the **Azure Content Safety** API to analyze text or images
for harmful content across four categories: **Hate**, **SelfHarm**,
**Sexual**, and **Violence**.

## Severity levels

| Level | Meaning |
|-------|---------|
| 0 | Safe |
| 2 | Low severity |
| 4 | Medium severity |
| 6 | High severity |

## Supports

- **Text analysis** — pass `--text` with content to check
- **Image analysis** — pass `--file` (base64-encoded) or `--url` (blob URL)
- **CI/CD gating** — use `--threshold` to exit with code 2 if severity
  meets or exceeds the value

## Prerequisites

- An Azure Content Safety resource.
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_CONTENT_SAFETY_API_KEY` | API key from your Content Safety resource. |
| `AZURE_CONTENT_SAFETY_ENDPOINT` | Endpoint URL (e.g. `https://<resource>.cognitiveservices.azure.com`). |

## Scripts

### `scripts/analyze.py`

**Check text:**

```sh
export AZURE_CONTENT_SAFETY_API_KEY="..."
export AZURE_CONTENT_SAFETY_ENDPOINT="https://<resource>.cognitiveservices.azure.com"

python3 skills/azure-content-safety/scripts/analyze.py \
  --text "Some content to check"
```

**Check image file:**

```sh
python3 skills/azure-content-safety/scripts/analyze.py \
  --file photo.jpg
```

**CI/CD gating (exit code 2 if severity >= 2):**

```sh
python3 skills/azure-content-safety/scripts/analyze.py \
  --text "Content to gate" --threshold 2
echo "Exit code: $?"  # 0 = safe, 2 = flagged
```

**Read from stdin:**

```sh
echo "Check this content" | python3 skills/azure-content-safety/scripts/analyze.py --text -
```

**Full API response:**

```sh
python3 skills/azure-content-safety/scripts/analyze.py \
  --text "Hello" --raw
```

See all options:

```sh
python3 skills/azure-content-safety/scripts/analyze.py --help
```
