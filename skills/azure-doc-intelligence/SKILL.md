---
name: azure-doc-intelligence
description: >
  Extract text, tables, key-value pairs, and structured fields from documents
  using Azure Document Intelligence with a single, dependency-free Python
  script. Supports prebuilt models for layouts, invoices, receipts, and IDs.
  Use when the user wants to: (1) extract text or tables from PDFs,
  (2) parse invoices or receipts, (3) OCR images or scanned documents,
  (4) analyze document structure without installing SDKs.
  Triggers: "document intelligence", "form recognizer", "extract text from pdf",
  "ocr", "parse invoice", "parse receipt", "extract tables", "analyze document",
  "pdf extraction"
---

# azure-doc-intelligence — Document Analysis via a zero-dependency script

This skill calls the **Azure Document Intelligence** (formerly Form Recognizer)
REST API. It submits a document, polls for results, and outputs extracted
content.

## Supported models

| Model | Use case |
|-------|----------|
| `prebuilt-read` | OCR — extract text from images and PDFs |
| `prebuilt-layout` | Text + tables + structure (default) |
| `prebuilt-invoice` | Invoice field extraction |
| `prebuilt-receipt` | Receipt field extraction |
| `prebuilt-idDocument` | ID document (passport, driver's license) |
| `prebuilt-businessCard` | Business card fields |
| Custom model ID | Your own trained model |

## How it works

1. **Submit** — POST the document (local file or URL) to the analyze endpoint.
2. **Poll** — GET the operation status until `succeeded` or `failed`.
3. **Output** — Print extracted content (text, tables, key-value pairs, fields).

## Prerequisites

- An Azure Document Intelligence resource.
- Python ≥ 3.8.

## Required environment variables

| Variable | Description |
|----------|-------------|
| `AZURE_DOCUMENT_INTELLIGENCE_API_KEY` | API key from your resource. |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | Endpoint URL (e.g. `https://<resource>.cognitiveservices.azure.com`). |

## Scripts

### `scripts/analyze.py`

**Extract text and tables from a PDF:**

```sh
export AZURE_DOCUMENT_INTELLIGENCE_API_KEY="..."
export AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://<resource>.cognitiveservices.azure.com"

python3 skills/azure-doc-intelligence/scripts/analyze.py \
  --model prebuilt-layout \
  --file document.pdf
```

**OCR an image:**

```sh
python3 skills/azure-doc-intelligence/scripts/analyze.py \
  --model prebuilt-read \
  --file scan.png
```

**Parse an invoice:**

```sh
python3 skills/azure-doc-intelligence/scripts/analyze.py \
  --model prebuilt-invoice \
  --file invoice.pdf
```

**Analyze a document from a URL:**

```sh
python3 skills/azure-doc-intelligence/scripts/analyze.py \
  --model prebuilt-layout \
  --url "https://example.com/report.pdf"
```

**Markdown output (tables as Markdown):**

```sh
python3 skills/azure-doc-intelligence/scripts/analyze.py \
  --model prebuilt-layout \
  --file report.pdf \
  --output-format markdown
```

**Select specific pages:**

```sh
python3 skills/azure-doc-intelligence/scripts/analyze.py \
  --model prebuilt-layout \
  --file large-doc.pdf \
  --pages "1-3,5"
```

**Full API response:**

```sh
python3 skills/azure-doc-intelligence/scripts/analyze.py \
  --model prebuilt-read \
  --file scan.png \
  --raw
```

See all options:

```sh
python3 skills/azure-doc-intelligence/scripts/analyze.py --help
```
