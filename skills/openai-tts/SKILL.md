---
name: openai-tts
description: >
  Synthesize speech from text using the OpenAI or Azure OpenAI TTS API with
  a single, dependency-free Python script. Supports tts-1 and tts-1-hd models
  with six voices and multiple audio formats.
  Use when the user wants to: (1) convert text to speech from the terminal,
  (2) generate audio files without installing the openai SDK,
  (3) batch-produce narration in CI/CD or agent workflows.
  Triggers: "text to speech", "tts", "openai tts", "synthesize speech",
  "generate audio", "azure tts", "read aloud"
---

# openai-tts — Text-to-Speech via a zero-dependency script

This skill calls the **Audio Speech** endpoint on either:

- **OpenAI** (`https://api.openai.com/v1/audio/speech`)
- **Azure OpenAI** (`/openai/deployments/{deployment}/audio/speech`)

Provider is auto-detected from the endpoint URL or can be forced with
`--provider`.

## Supported models

| Model | Quality | Latency |
|-------|---------|---------|
| `tts-1` | Standard | Low |
| `tts-1-hd` | High | Higher |

## Voices

`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

## Output formats

`mp3` (default), `opus`, `aac`, `flac`, `wav`, `pcm`

## Prerequisites

- For OpenAI: an API key from [platform.openai.com](https://platform.openai.com).
- For Azure OpenAI: a resource with a deployed TTS model.
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for the OpenAI platform. |
| `AZURE_OPENAI_API_KEY` | API key for an Azure OpenAI resource. |

## Scripts

### `scripts/tts.py`

**OpenAI:**

```sh
export OPENAI_API_KEY="sk-..."

python3 skills/openai-tts/scripts/tts.py \
  --model tts-1-hd \
  --voice nova \
  --input "Hello, world!" \
  --output hello.mp3
```

**Azure OpenAI:**

```sh
export AZURE_OPENAI_API_KEY="<your-key>"

python3 skills/openai-tts/scripts/tts.py \
  --endpoint "https://<resource>.openai.azure.com" \
  --model tts-1 \
  --voice alloy \
  --input "Hello from Azure!"
```

**Read from stdin:**

```sh
echo "Long text to synthesize" | python3 skills/openai-tts/scripts/tts.py \
  --model tts-1 --voice shimmer --input - --output narration.mp3
```

**Different formats:**

```sh
python3 skills/openai-tts/scripts/tts.py \
  --model tts-1-hd --voice echo \
  --input "High quality opus" \
  --response-format opus --output speech.opus
```

See all options:

```sh
python3 skills/openai-tts/scripts/tts.py --help
```
