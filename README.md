# NexusAgent

[![CI](https://github.com/stephanos8926-lgtm/NexusAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/stephanos8926-lgtm/NexusAgent/actions/workflows/ci.yml)

**AI Coding Agent — terminal-native, privacy-first, built for real work.**

## What It Is

NexusAgent is a local AI coding agent that runs in your terminal. It connects to LLM providers (Gemini, OpenRouter, and more), gives them tools to read/write files, run shell commands, search the web, and manage tasks — and lets you orchestrate it all from a beautiful TUI.

No cloud dependency. No data leaving your machine. Your keys, your code, your control.

## Features

- **Rich TUI** — Markdown rendering, collapsible tool output, 7 themes, responsive layout, braille spinners
- **Multi-provider LLM** — Gemini, OpenRouter, local models via unified provider bridge
- **Tool system** — Shell, file ops, code review, web search, subagent spawning, todo tracking, git, and more
- **Skills** — Load custom skills from `~/.hermes/skills/` with YAML frontmatter
- **Hooks** — Event-driven automation (session-init, post-tool, error hooks)
- **Session management** — Undo/redo, session snapshots, compaction for long conversations
- **Web UI** — Optional browser-based interface alongside the TUI
- **Headless mode** — JSON output for scripting and CI/CD integration
- **NATS bus** — Scalable message passing for multi-agent deployments

## Quick Start

```bash
# Install
git clone https://github.com/stephanos8926-lgtm/NexusAgent.git
cd NexusAgent
pip install -e ".[dev]"

# Run the TUI
python -m nexusagent

# Or run headless
python -m nexusagent run "Fix the auth bug in server.py" -d /project
```

## Documentation

- [Setup](docs/getting-started.md) — Installation and configuration
- [Usage](docs/quickstart.md) — Common workflows
- [Architecture](docs/architecture/overview.md) — System design
- [ADRs](docs/adrs/index.md) — Architecture decision records
- [Roadmap](docs/plans/2026-07-12-assessment-and-roadmap.md) — Current status and next steps
- [Codebase Map](docs/CODEBASE_MAP.md) — Annotated source map
- [Research](docs/research/) — Feature parity and design research

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. All contributions welcome — bug fixes, features, docs, tests.

## License

MIT
