---
name: azure-ai-vision
description: >
  Analyze images using Azure AI Vision (Image Analysis 4.0) with a single,
  dependency-free Python script. Supports captioning, OCR, tagging, object
  detection, people detection, and smart cropping.
  Use when the user wants to: (1) caption or describe an image,
  (2) extract text from images (OCR), (3) detect objects or people,
  (4) tag image content, (5) get smart crop suggestions.
  Triggers: "analyze image", "image caption", "OCR image", "detect objects",
  "computer vision", "image tags", "azure vision", "describe image",
  "read text from image"
---

# azure-ai-vision — Image Analysis via a zero-dependency script

This skill calls the **Azure AI Vision Image Analysis 4.0** API to extract
captions, text (OCR), tags, objects, people, and smart crops from images.

## Features

| Feature | Description |
|---------|-------------|
| `caption` | Natural language description of the image |
| `denseCaptions` | Captions for regions within the image |
| `read` | OCR — extract printed/handwritten text |
| `tags` | Content tags with confidence scores |
| `objects` | Object detection with bounding boxes |
| `people` | People detection with bounding boxes |
| `smartCrops` | Suggested crop regions for given aspect ratios |

Default features: `caption`, `read`, `tags`.

## Supported image formats

JPEG, PNG, GIF, BMP, TIFF, WebP

## Prerequisites

- An Azure Computer Vision resource (Image Analysis 4.0 requires S1 tier or
  higher in [supported regions](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-image-analysis)).
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_AI_VISION_API_KEY` | API key from your Computer Vision resource. |
| `AZURE_AI_VISION_ENDPOINT` | Endpoint URL (e.g. `https://<resource>.cognitiveservices.azure.com`). |

## Scripts

### `scripts/analyze.py`

**Caption + OCR + tags (default):**

```sh
export AZURE_AI_VISION_API_KEY="..."
export AZURE_AI_VISION_ENDPOINT="https://<resource>.cognitiveservices.azure.com"

python3 skills/azure-ai-vision/scripts/analyze.py \
  --file photo.jpg
```

**Object detection:**

```sh
python3 skills/azure-ai-vision/scripts/analyze.py \
  --file photo.jpg \
  --features objects people
```

**Analyze image from URL:**

```sh
python3 skills/azure-ai-vision/scripts/analyze.py \
  --url "https://example.com/photo.jpg" \
  --features caption tags
```

**All features:**

```sh
python3 skills/azure-ai-vision/scripts/analyze.py \
  --file photo.jpg \
  --features caption denseCaptions read tags objects people smartCrops
```

**Full API response:**

```sh
python3 skills/azure-ai-vision/scripts/analyze.py \
  --file photo.jpg --raw
```

See all options:

```sh
python3 skills/azure-ai-vision/scripts/analyze.py --help
```
