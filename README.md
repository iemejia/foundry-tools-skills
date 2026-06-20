# foundry-tools-skills

A collection of [agent skills](https://agentskills.io/) for driving
**Microsoft Foundry Tools** — Azure AI / Cognitive Services and the OpenAI
APIs exposed through [Azure AI Foundry](https://ai.azure.com/).

Each skill bundles natural-language instructions (`SKILL.md`) and one or more
**self-contained Python scripts** that perform a concrete task against a single
Foundry service. The scripts are designed to be copied and run with nothing but
a Python interpreter.

## Design principles

- **One Python script per service task.** Small, focused, composable.
- **Zero third-party dependencies.** Standard library only — no SDKs, no
  `requests`, no `openai` package.
- **Python ≥ 3.8 compatible.** Runs on the interpreter shipped with most
  systems.
- **Self-contained.** Copy a single `.py` file and run it.
- **Config via env vars + CLI flags.** No hard-coded endpoints, keys, or
  regions; no secrets in the repo.
- **Cross-platform.** Works on macOS and Linux unchanged.

## Repository layout

```
skills/
└── <service-name>/       # one directory per service/skill
    ├── SKILL.md          # skill instructions + frontmatter
    └── scripts/
        └── <task>.py     # self-contained, zero-dependency script
```

## Available skills

| Skill | Service | Status |
|-------|---------|--------|
| [`openai-chat`](skills/openai-chat/) | OpenAI / Azure OpenAI — Chat Completions | example stub |
| [`openai-images`](skills/openai-images/) | OpenAI / Azure OpenAI — Image Generation (gpt-image-1/2) | new |

More service skills (Speech, Vision, Language, Translator, Document
Intelligence, Content Safety, ...) will be added over time — one script per
task.

## Usage

Each script is standalone. Set the required environment variables (documented
in the corresponding `SKILL.md` and the script's `--help`) and run it:

```sh
# OpenAI
export OPENAI_API_KEY="sk-..."
python3 skills/openai-chat/scripts/chat.py \
  --model "gpt-4o-mini" \
  --prompt "Hello, Foundry!"

# Azure OpenAI
export AZURE_OPENAI_API_KEY="<your-key>"
python3 skills/openai-chat/scripts/chat.py \
  --endpoint "https://<resource>.openai.azure.com" \
  --model "gpt-4o-mini" \
  --prompt "Hello, Foundry!"
```

Run any script with `--help` to see its options:

```sh
python3 skills/openai-chat/scripts/chat.py --help
```

## Contributing

See [AGENTS.md](AGENTS.md) for the hard constraints, script/skill conventions,
and the checklist for adding a new service skill.

Before committing a script:

```sh
python3 -m py_compile skills/<service-name>/scripts/<task>.py
python3 skills/<service-name>/scripts/<task>.py --help
```

## License

[MIT](LICENSE)
