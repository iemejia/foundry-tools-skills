# AGENTS.md

Guidance for AI agents and contributors working in **foundry-tools-skills**.

## What this repository is

A collection of [agent skills](https://agentskills.io/) for driving
**Microsoft Foundry Tools** — Azure AI / Cognitive Services and the OpenAI
APIs exposed through Azure AI Foundry. Each skill bundles instructions
(`SKILL.md`) and one or more **self-contained Python scripts** that perform a
concrete task against a single Foundry service.

The guiding principle: **one Python script per service task**, runnable with a
bare Python interpreter and nothing else.

## Repository layout

```
foundry-tools-skills/
├── AGENTS.md                 # this file
├── LICENSE                   # MIT
├── README.md
├── skills/
│   └── <service-name>/       # one directory per service/skill
│       ├── SKILL.md          # skill instructions + frontmatter
│       └── scripts/
│           └── <task>.py     # self-contained, zero-dependency script
└── ...
```

- `<service-name>` is a lowercase, hyphenated slug (e.g. `azure-openai-chat`,
  `ai-speech-tts`, `document-intelligence`, `content-safety`).
- Each script under `scripts/` solves **one** task and is executable on its own.

## Hard constraints for Python scripts

These are non-negotiable. Any script added MUST satisfy all of them:

1. **Zero third-party dependencies.** Standard library only. No `requests`,
   no `azure-*` SDKs, no `openai` package. Use `urllib.request`,
   `urllib.parse`, `json`, `http.client`, `base64`, `hmac`, `hashlib`, etc.
2. **Python ≥ 3.8 compatible.** Do not use syntax/features newer than 3.8
   (no `match` statements, no `tomllib`, no `str.removeprefix`, no PEP 604
   `X | Y` type unions at runtime, no positional-only enforced APIs that
   require >3.8). Prefer `typing.Optional`/`typing.Union` over `|`.
3. **Single file, self-contained.** No imports from sibling files in the repo.
   A user must be able to copy one `.py` file and run it.
4. **Configuration via environment variables and CLI flags only.** Never
   hard-code endpoints, keys, deployment names, or regions. Read secrets from
   the environment (e.g. `AZURE_OPENAI_API_KEY`); accept everything else via
   `argparse`.
5. **No secrets in the repo.** Never commit keys, tokens, endpoints with
   embedded credentials, or `.env` files.
6. **Cross-platform.** Must run on macOS and Linux without modification.
7. **OpenAI API compatibility.** Scripts that target OpenAI-compatible
   services (chat completions, embeddings, image generation, etc.) MUST work
   against both the Azure OpenAI endpoint **and** the real OpenAI API
   (`https://api.openai.com`). This means: support `Authorization: Bearer`
   auth (OpenAI) in addition to `api-key` header (Azure); accept the standard
   `OPENAI_API_KEY` env var alongside `AZURE_OPENAI_API_KEY`; include the
   `model` field in the request body; and handle the differing URL structures
   (Azure: `/openai/deployments/{name}/...?api-version=`, OpenAI:
   `/v1/chat/completions`). A `--provider` flag or auto-detection from the
   endpoint URL is the recommended approach.

## Script conventions

- Start with a `#!/usr/bin/env python3` shebang and a module docstring that
  states the service, the task, required env vars, and an example invocation.
- Use `argparse` for arguments; provide sensible `--help` output.
- Use `urllib.request` for HTTP. Set explicit timeouts. Handle
  `urllib.error.HTTPError` / `URLError` and print actionable messages to
  `stderr`.
- Exit non-zero on failure (`sys.exit(1)`); exit `0` on success.
- Print machine-readable output (JSON) to `stdout` when it makes sense; keep
  human/log messages on `stderr`.
- Keep the API version configurable via a flag with a documented default.
- Add a brief `# Requires: Python >= 3.8, standard library only` comment near
  the top.

## SKILL.md conventions

Each skill begins with YAML frontmatter:

```yaml
---
name: <service-name>
description: >
  One-paragraph summary of what the skill does and when to use it.
  Use when the user wants to: (1) ..., (2) ..., (3) ...
  Triggers: "...", "...", "..."
---
```

Then document: prerequisites, required environment variables, the available
scripts under `scripts/`, and copy-pasteable example invocations.

## Adding a new service skill

1. Create `skills/<service-name>/SKILL.md` with frontmatter.
2. Add one or more scripts under `skills/<service-name>/scripts/`.
3. Verify each script: `python3 skills/<service-name>/scripts/<task>.py --help`.
4. List the new skill in `README.md`.

## Verification

There is no build system. Before committing a script, at minimum run:

```sh
python3 -m py_compile skills/<service-name>/scripts/<task>.py
python3 skills/<service-name>/scripts/<task>.py --help
```

## Commit conventions

- Imperative subject line ≤ 50 chars; body explaining the why when useful.
- For AI-assisted commits, add the kernel-style trailer, e.g.:
  `Assisted-by: GitHub Copilot:claude-opus-4.8`
- Do not use `Co-authored-by:` for AI assistance.
