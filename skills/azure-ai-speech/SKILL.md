---
name: azure-ai-speech
description: >
  Synthesize speech (TTS) and recognize speech (STT) using Azure AI Speech
  with zero-dependency Python scripts. TTS supports 400+ neural voices,
  SSML, and multiple audio formats. STT supports short audio recognition.
  Use when the user wants to: (1) synthesize speech with Azure neural voices,
  (2) use SSML for fine-grained speech control, (3) transcribe short audio,
  (4) list available voices, (5) use Azure-specific TTS features.
  Triggers: "azure speech", "azure tts", "azure stt", "neural voice",
  "ssml", "synthesize speech", "speech recognition", "azure transcribe",
  "list voices", "text to speech azure"
---

# azure-ai-speech — TTS and STT via zero-dependency scripts

This skill provides two scripts for the **Azure AI Speech** service:

- **synthesize.py** — Text-to-speech with 400+ neural voices and SSML
- **recognize.py** — Speech-to-text for short audio (up to 60 seconds)

## Prerequisites

- An Azure Speech resource.
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_AI_SPEECH_API_KEY` | API key from your Speech resource. |
| `AZURE_AI_SPEECH_REGION` | Azure region (e.g. `eastus`). Required unless using `--endpoint`. |
| `AZURE_AI_SPEECH_ENDPOINT` | *(Optional)* Custom-domain endpoint URL. Overrides region. |

## Scripts

### `scripts/synthesize.py` — Text-to-Speech

**Basic synthesis:**

```sh
export AZURE_AI_SPEECH_API_KEY="..."
export AZURE_AI_SPEECH_REGION="eastus"

python3 skills/azure-ai-speech/scripts/synthesize.py \
  --voice en-US-JennyNeural \
  --text "Hello, world!" \
  -o hello.mp3
```

**Different voice and format:**

```sh
python3 skills/azure-ai-speech/scripts/synthesize.py \
  --voice fr-FR-DeniseNeural \
  --text "Bonjour le monde" \
  --output-format wav \
  -o bonjour.wav
```

**Prosody control (rate and pitch):**

```sh
python3 skills/azure-ai-speech/scripts/synthesize.py \
  --voice en-US-GuyNeural \
  --text "Speaking slowly and low" \
  --rate slow --pitch low
```

**Custom SSML:**

```sh
python3 skills/azure-ai-speech/scripts/synthesize.py \
  --ssml-file speech.xml -o output.mp3
```

**List available voices:**

```sh
python3 skills/azure-ai-speech/scripts/synthesize.py --list-voices
```

**Output formats:**

| Alias | Full format |
|-------|-------------|
| `mp3` | audio-24khz-160kbitrate-mono-mp3 |
| `mp3-48k` | audio-48khz-192kbitrate-mono-mp3 |
| `wav` | riff-24khz-16bit-mono-pcm |
| `opus` | ogg-24khz-16bit-mono-opus |

### `scripts/recognize.py` — Speech-to-Text

**Recognize speech from WAV:**

```sh
python3 skills/azure-ai-speech/scripts/recognize.py \
  --file recording.wav \
  --language en-US
```

**Detailed output with confidence scores:**

```sh
python3 skills/azure-ai-speech/scripts/recognize.py \
  --file audio.mp3 \
  --language en-US \
  --format detailed
```

**Different language:**

```sh
python3 skills/azure-ai-speech/scripts/recognize.py \
  --file audio.wav \
  --language fr-FR
```

**Full API response:**

```sh
python3 skills/azure-ai-speech/scripts/recognize.py \
  --file audio.wav --raw
```

> **Note:** The simple recognition endpoint supports audio up to 60 seconds.
> For longer audio, use the batch transcription API or the
> `openai-transcription` skill.

See all options:

```sh
python3 skills/azure-ai-speech/scripts/synthesize.py --help
python3 skills/azure-ai-speech/scripts/recognize.py --help
```
