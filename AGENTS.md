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

- `<service-name>` is a lowercase, hyphenated slug (e.g. `openai-chat`,
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

### Agent-friendly error output

Scripts are primarily invoked by coding agents (AI assistants, CI bots,
orchestrators). Every error message MUST include:

1. **What failed** — the specific operation or check that went wrong.
2. **Why it likely failed** — interpret HTTP status codes, missing env vars,
   malformed input, etc. into a probable root cause.
3. **How to fix it** — a concrete remediation step: the exact env var to set,
   the flag to pass, the URL to visit, or the command to run.
4. **Structured format** — emit errors as a single-line JSON object to
   `stderr` so agents can parse them programmatically:
   `{"error": "<what>", "hint": "<how to fix>"}`.

Common patterns:
- `401/403` → "Authentication failed. Verify OPENAI_API_KEY is valid.
  Generate a new key at https://platform.openai.com/api-keys"
- `404` → "Model or deployment not found. Check --model value. For Azure,
  verify the deployment exists in your resource."
- `429` → "Rate limited. Wait and retry, or reduce request frequency."
- Missing env var → Tell the agent exactly which variable to `export` and
  where to obtain the value.
- Network error → Suggest checking the --endpoint URL and connectivity.

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
4. Write unit tests in `tests/test_<skill_name>.py`.
5. Add integration test cases in `tests/test_integration.py`.
6. Verify: `python3 run_tests.py -v` (all tests pass).
7. List the new skill in `README.md`.

## Verification

There is no build system. Before committing a script, at minimum run:

```sh
python3 -m py_compile skills/<service-name>/scripts/<task>.py
python3 skills/<service-name>/scripts/<task>.py --help
```

## Testing

Run the full test suite (stdlib `unittest` only, zero dependencies):

```sh
python3 run_tests.py        # all tests
python3 run_tests.py -v     # verbose
```

### Test requirement

Every new skill MUST include both:

1. **Unit tests** — test all logic without network access.
2. **Integration tests** — test against live APIs with real credentials.

A skill is not considered complete until both test types exist and pass.

### Test layers

1. **Skill validation** (`tests/test_skill_validation.py`) — auto-discovers all
   skills and checks: directory structure, SKILL.md frontmatter, script
   compilation (`py_compile`), and `--help` exits 0. Runs with no credentials.

2. **Unit tests** (`tests/test_<skill_name>.py`) — import each script as a
   module via `importlib.util` and test pure logic: URL building, payload
   construction, provider detection, argument parsing, error messages. Mock
   `urllib.request.urlopen` (via `unittest.mock`) for HTTP-level tests (retry
   behavior, error code handling, successful responses). No network access.

3. **Integration tests** (`tests/test_integration.py`) — make real API calls
   against live Azure OpenAI (or OpenAI) endpoints. Credentials are resolved
   in this order:
   - Environment variables: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`,
     `AZURE_OPENAI_CHAT_DEPLOYMENT`, etc.
   - Auto-discovery via `az CLI`: the test harness runs
     `az cognitiveservices account list` and
     `az cognitiveservices account keys list` to find resources and keys
     automatically when env vars are not set. This works out of the box on
     any machine where `az login` has been run.
   - Tests are **skipped gracefully** (not failed) if no credentials are
     available — safe for CI environments without secrets configured.

### Writing tests for a new skill

1. Create `tests/test_<skill_name>.py` (replace hyphens with underscores).
2. Import the script as a module:
   ```python
   import importlib.util, sys
   _spec = importlib.util.spec_from_file_location("myscript", "<path>")
   myscript = importlib.util.module_from_spec(_spec)
   _spec.loader.exec_module(myscript)
   sys.modules["myscript"] = myscript  # enables @patch("myscript.func")
   ```
3. Test public functions directly (URL builders, payload constructors).
4. Use `@patch("myscript.<http_function>")` to mock HTTP and test `main()`.
5. Add integration test cases in `tests/test_integration.py` under a new
   `TestCase` class for your skill. Use `@unittest.skipIf` / `skipUnless` to
   gate on the required credentials or deployments.
6. Verify `run_tests.py -v` passes before committing.

## Commit conventions

- Imperative subject line ≤ 50 chars; body explaining the why when useful.
- For AI-assisted commits, add the kernel-style trailer, e.g.:
  `Assisted-by: GitHub Copilot:claude-opus-4.8`
- Do not use `Co-authored-by:` for AI assistance.
