---
name: azure-ai-face
description: >
  Detect faces in images using Azure AI Face with a single,
  dependency-free Python script. Returns face rectangles, optional
  attributes (blur, exposure, glasses, headPose, etc.), and landmarks.
  Use when the user wants to: (1) detect faces in photos or images,
  (2) get face attributes like glasses, head pose, blur,
  (3) count faces in an image, (4) get face landmark coordinates.
  Triggers: "face detection", "detect faces", "face analysis",
  "face attributes", "face landmarks", "count faces", "face rectangle"
---

# azure-ai-face — Face Detection via a zero-dependency script

This skill calls the **Azure AI Face API** to detect human faces in
images and optionally return attributes, landmarks, and face IDs.

## Access restrictions

Microsoft has restricted some face attributes since late 2023:

| Access level | Attributes |
|-------------|------------|
| **Open** | accessories, blur, exposure, glasses, headPose, mask, noise, occlusion, qualityForRecognition |
| **Limited Access** (requires approval) | age, emotion, facialHair, gender, hair, makeup, smile |

Apply for Limited Access at: https://aka.ms/facerecognition

## Detection models

| Model | Best for | Attributes |
|-------|----------|------------|
| `detection_01` | General (default) | All open attributes except `mask` |
| `detection_03` | Improved accuracy | blur, exposure, headPose, mask, noise, qualityForRecognition |

## Prerequisites

- An Azure Face resource.
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_AI_FACE_API_KEY` | API key from your Face resource. |
| `AZURE_AI_FACE_ENDPOINT` | Endpoint URL (e.g. `https://<resource>.cognitiveservices.azure.com`). |

## Scripts

### `scripts/detect.py`

**Basic face detection (rectangles only):**

```sh
export AZURE_AI_FACE_API_KEY="..."
export AZURE_AI_FACE_ENDPOINT="https://<resource>.cognitiveservices.azure.com"

python3 skills/azure-ai-face/scripts/detect.py --file photo.jpg
```

**With attributes:**

```sh
python3 skills/azure-ai-face/scripts/detect.py \
  --file photo.jpg \
  --attributes headPose glasses blur qualityForRecognition
```

**All standard attributes:**

```sh
python3 skills/azure-ai-face/scripts/detect.py \
  --file photo.jpg --attributes all
```

**From URL with landmarks:**

```sh
python3 skills/azure-ai-face/scripts/detect.py \
  --url "https://example.com/photo.jpg" \
  --landmarks --attributes headPose
```

**Higher accuracy model:**

```sh
python3 skills/azure-ai-face/scripts/detect.py \
  --file photo.jpg \
  --detection-model detection_03 \
  --attributes blur mask qualityForRecognition
```

**Full API response:**

```sh
python3 skills/azure-ai-face/scripts/detect.py --file photo.jpg --raw
```

See all options:

```sh
python3 skills/azure-ai-face/scripts/detect.py --help
```
