---
name: openai-transcription
description: >
  Transcribe audio files to text using the OpenAI or Azure OpenAI
  Transcriptions API with a single, dependency-free Python script. Supports
  whisper-1 and gpt-4o-transcribe models.
  Use when the user wants to: (1) transcribe audio or video files,
  (2) convert speech to text without installing the openai SDK,
  (3) generate subtitles (SRT/VTT) from audio.
  Triggers: "transcribe", "speech to text", "whisper", "audio to text",
  "transcription", "srt subtitles", "openai transcribe", "azure transcribe"
---

# openai-transcription — Audio Transcription via a zero-dependency script

This skill calls the **Audio Transcriptions** endpoint on either:

- **OpenAI** (`https://api.openai.com/v1/audio/transcriptions`)
- **Azure OpenAI** (`/openai/deployments/{deployment}/audio/transcriptions`)

Provider is auto-detected from the endpoint URL or can be forced with
`--provider`.

## Supported models

| Model | Notes |
|-------|-------|
| `whisper-1` | Original Whisper model |
| `gpt-4o-transcribe` | Higher accuracy, word-level timestamps |
| `gpt-4o-mini-transcribe` | Faster, lower cost |

## Supported audio formats

mp3, mp4, mpeg, mpga, m4a, wav, webm (max ~25 MB)

## Output formats

`json` (default), `text`, `srt`, `verbose_json`, `vtt`

## Prerequisites

- For OpenAI: an API key from [platform.openai.com](https://platform.openai.com).
- For Azure OpenAI: a resource with a deployed transcription model.
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for the OpenAI platform. |
| `AZURE_OPENAI_API_KEY` | API key for an Azure OpenAI resource. |

## Scripts

### `scripts/transcribe.py`

**OpenAI:**

```sh
export OPENAI_API_KEY="sk-..."

python3 skills/openai-transcription/scripts/transcribe.py \
  --model whisper-1 \
  --file recording.mp3
```

**Azure OpenAI:**

```sh
export AZURE_OPENAI_API_KEY="<your-key>"

python3 skills/openai-transcription/scripts/transcribe.py \
  --endpoint "https://<resource>.openai.azure.com" \
  --model gpt-4o-transcribe \
  --file meeting.wav \
  --language en
```

**Generate subtitles:**

```sh
python3 skills/openai-transcription/scripts/transcribe.py \
  --model whisper-1 \
  --file video.mp4 \
  --response-format srt > subtitles.srt
```

**Verbose JSON with timestamps:**

```sh
python3 skills/openai-transcription/scripts/transcribe.py \
  --model gpt-4o-transcribe \
  --file interview.mp3 \
  --response-format verbose_json
```

See all options:

```sh
python3 skills/openai-transcription/scripts/transcribe.py --help
```
