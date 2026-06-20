---
name: openai-images
description: >
  Generate images using the OpenAI or Azure OpenAI Images API with a single,
  dependency-free Python script. Supports all model generations (dall-e-2,
  dall-e-3, gpt-image-1). Auto-detects provider from the endpoint URL.
  Use when the user wants to: (1) generate images from text prompts,
  (2) script image generation without installing the openai SDK,
  (3) produce images in CI/CD or agent workflows.
  Triggers: "openai image", "generate image", "dall-e", "gpt-image",
  "image generation", "text to image", "azure image generation"
---

# openai-images — Image Generation via a zero-dependency script

This skill calls the **Images Generation** endpoint on either:

- **OpenAI** (`https://api.openai.com/v1/images/generations`)
- **Azure OpenAI** (`/openai/deployments/{deployment}/images/generations`)

Provider is auto-detected from the endpoint URL or can be forced with
`--provider`.

## Supported models

| Model | Sizes | Quality | Notes |
|-------|-------|---------|-------|
| `dall-e-2` | 256x256, 512x512, 1024x1024 | — | Up to 10 images per request |
| `dall-e-3` | 1024x1024, 1792x1024, 1024x1792 | standard, hd | 1 image per request; supports style |
| `gpt-image-1` | 1024x1024, 1536x1024, 1024x1536, auto | low, medium, high | Multiple images; transparent backgrounds |

## Prerequisites

- For OpenAI: an API key from [platform.openai.com](https://platform.openai.com).
- For Azure OpenAI: a resource with a deployed image model.
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for the OpenAI platform. |
| `AZURE_OPENAI_API_KEY` | API key for an Azure OpenAI resource. |

Set one (or both). The script picks the right one based on the provider.
The endpoint may also be supplied via `AZURE_OPENAI_ENDPOINT`.

## Scripts

### `scripts/generate.py`

Generate one or more images from a text prompt.

**OpenAI (DALL-E 3):**

```sh
export OPENAI_API_KEY="sk-..."

python3 skills/openai-images/scripts/generate.py \
  --model dall-e-3 \
  --prompt "A futuristic city skyline at sunset, digital art" \
  --size 1792x1024 \
  --quality hd
```

**OpenAI (gpt-image-1):**

```sh
python3 skills/openai-images/scripts/generate.py \
  --model gpt-image-1 \
  --prompt "A cute robot gardening in a greenhouse" \
  --size 1536x1024 \
  --quality high \
  --output-format png \
  --output-dir ./generated
```

**Azure OpenAI:**

```sh
export AZURE_OPENAI_API_KEY="<your-key>"

python3 skills/openai-images/scripts/generate.py \
  --endpoint "https://<resource>.openai.azure.com" \
  --model dall-e-3 \
  --prompt "Mountain landscape in watercolor style" \
  --size 1024x1024
```

**Save to a specific directory:**

```sh
python3 skills/openai-images/scripts/generate.py \
  --model dall-e-2 \
  --prompt "Abstract geometric pattern" \
  --n 4 \
  --output-dir ./images
```

See all options:

```sh
python3 skills/openai-images/scripts/generate.py --help
```
