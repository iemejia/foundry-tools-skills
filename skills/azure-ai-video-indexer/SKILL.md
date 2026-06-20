---
name: azure-ai-video-indexer
description: >
  Upload, index, and extract insights from video using Azure Video
  Indexer with a single, dependency-free Python script. Extracts
  transcripts, topics, keywords, faces, labels, and sentiments.
  Use when the user wants to: (1) upload and analyze a video,
  (2) extract transcripts from video, (3) get video insights
  (topics, keywords, faces, labels), (4) list indexed videos.
  Triggers: "video indexer", "video analysis", "video insights",
  "video transcript", "index video", "analyze video",
  "video keywords", "video topics"
---

# azure-ai-video-indexer — Video Analysis via a zero-dependency script

This skill calls the **Azure Video Indexer API** to upload videos,
wait for indexing, and retrieve rich insights including transcripts,
topics, keywords, detected faces, labels, and sentiment analysis.

## Authentication

Video Indexer uses **access tokens** (not API keys). The script
supports two approaches:

1. **Direct token** — set `AZURE_VIDEO_INDEXER_ACCESS_TOKEN`
2. **Auto-generate via az CLI** — the script discovers your VI
   account and generates a token via the ARM API

### Generating a token manually

```sh
# 1. Get ARM token
ARM_TOKEN=$(az account get-access-token \
  --resource https://management.azure.com \
  --query accessToken -o tsv)

# 2. Generate VI access token
curl -s -X POST \
  "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.VideoIndexer/accounts/{name}/generateAccessToken?api-version=2024-01-01" \
  -H "Authorization: Bearer $ARM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"permissionType":"Contributor","scope":"Account"}' \
  | jq -r .accessToken
```

## Prerequisites

- An Azure Video Indexer account.
- Python ≥ 3.8.
- Either an access token or `az` CLI logged in with access to the
  Video Indexer account.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_VIDEO_INDEXER_ACCOUNT_ID` | Video Indexer account ID (GUID). |
| `AZURE_VIDEO_INDEXER_LOCATION` | Account location (e.g. `eastus2`, `trial`). |
| `AZURE_VIDEO_INDEXER_ACCESS_TOKEN` | *(Optional)* Pre-generated access token. Auto-generated via az CLI if not set. |

## Scripts

### `scripts/analyze.py`

**Upload and analyze a video:**

```sh
export AZURE_VIDEO_INDEXER_ACCOUNT_ID="<guid>"
export AZURE_VIDEO_INDEXER_LOCATION="eastus2"

python3 skills/azure-ai-video-indexer/scripts/analyze.py \
  --upload video.mp4 --name "My Video"
```

**Index from URL:**

```sh
python3 skills/azure-ai-video-indexer/scripts/analyze.py \
  --video-url "https://example.com/video.mp4" \
  --name "Remote Video"
```

**Get insights for existing video:**

```sh
python3 skills/azure-ai-video-indexer/scripts/analyze.py \
  --video-id "abc123def456"
```

**List indexed videos:**

```sh
python3 skills/azure-ai-video-indexer/scripts/analyze.py --list
```

**Upload without waiting (returns immediately):**

```sh
python3 skills/azure-ai-video-indexer/scripts/analyze.py \
  --upload video.mp4 --no-wait
```

**Full API response:**

```sh
python3 skills/azure-ai-video-indexer/scripts/analyze.py \
  --video-id "abc123" --raw
```

See all options:

```sh
python3 skills/azure-ai-video-indexer/scripts/analyze.py --help
```

## Extracted insights

The script extracts and summarizes:

| Insight | Description |
|---------|-------------|
| **transcript** | Timestamped text of spoken content |
| **topics** | Auto-detected topics with confidence |
| **keywords** | Key phrases with confidence |
| **labels** | Visual labels (objects, scenes) |
| **sentiments** | Sentiment analysis (positive/neutral/negative) |
| **faces** | Detected and identified faces |
