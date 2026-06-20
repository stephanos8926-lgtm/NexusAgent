# NexusAgent

[![CI](https://github.com/stephanos8926-lgtm/NexusAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/stephanos8926-lgtm/NexusAgent/actions/workflows/ci.yml)

**AI Coding Agent — terminal-native, privacy-first, built for real work.**

## What It Is

NexusAgent is a local AI coding agent platform that runs in your terminal. It connects to LLM providers (Gemini, OpenRouter, and more), gives them tools to read/write files, run shell commands, search the web, and manage tasks — all orchestrated through a beautiful TUI, a CLI, or a WebSocket API.

No cloud dependency. No data leaving your machine. Your keys, your code, your control.

## Features

- **Rich TUI** — Markdown rendering, collapsible tool output, 7 themes, responsive layout, streaming
- **Multi-provider LLM** — Gemini, OpenRouter, local models via unified provider bridge
- **Tool system** — 30+ tools: shell, filesystem, code review, web search, subagent spawning, git, AST search, memory
- **Skills** — Load custom skills from `~/.hermes/skills/` with YAML frontmatter
- **Hooks** — Event-driven automation (session-init, post-tool, error hooks)
- **Session management** — Fork/rename/delete, compaction with DAG-based hierarchical summarization
- **Memory v2** — Hybrid file+vector memory with auto-extraction, dream cycle consolidation, bi-temporal search, TTL, Git-backed
- **Workspace scoping** — Per-session path jail, thread-local memory isolation, NEXUS.md per workspace
- **NATS bus** — Scalable JetStream messaging for multi-agent deployments
- **Policy enforcement** — Per-role tool access (permissive/restricted/strict) with auto-unlock
- **Version handshake** — Client/server version preflight with compatibility warnings
- **Web UI** — Optional browser-based interface alongside the TUI
- **SDK** — Python SDK for programmatic task submission and orchestration

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

# Check version compatibility
python -m nexusagent --check-server
```

## Documentation

- [Installation](docs/installation.md) — Detailed install guide
- [Quick Start](docs/quickstart.md) — Common workflows
- [Getting Started](docs/getting_started.md) — First-setup walkthrough
- [Local Development](docs/local_development.md) — Contributor workflow
- [Codebase Map](docs/CODEBASE_MAP.md) — Annotated source map with module inventory
- [Semantic Index](docs/SEMANTIC_INDEX.md) — Data flows, state management, extension points
- [Roadmap](docs/ROADMAP/index.html) — Interactive audit dashboard & roadmap
- [ADRs](docs/adrs/index.md) — Architecture decision records (0001-0008)
- [Research](docs/research/) — Feature parity and design research

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NexusAgent System                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   CLI    │  │   TUI    │  │  Web UI  │  │ REST/WS  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       └──────────────┴──────────────┴──────────────┘        │
│                          │                                  │
│                   ┌──────┴──────┐                           │
│                   │ Agent (Core)│                           │
│                   └──────┬──────┘                           │
│                          │                                  │
│       ┌──────────────────┼──────────────────┐              │
│       │                  │                  │              │
│  ┌────┴────┐      ┌─────┴─────┐     ┌─────┴─────┐        │
│  │  Tools  │      │   NATS    │     │  Memory   │        │
│  │Registry │      │   Bus     │     │  v2       │        │
│  └─────────┘      └───────────┘     └───────────┘        │
│                                           │                │
│                                    ┌──────┴──────┐         │
│                                    │ SQLite DB   │         │
│                                    └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Memory System v2

The memory system is a hybrid file+vector architecture with background consolidation:

- **FileMemory** — Canonical markdown files with YAML frontmatter, Git-backed auto-commits
- **HybridMemoryIndex** — FTS5 + sqlite-vec hybrid search with RRF fusion
- **Auto-Extraction** — Regex-based fact extraction after every agent turn
- **Dream Cycle** — 4-phase background consolidation (scan → patterns → consolidate → trim)
- **LLM Refinement** — Optional LLM synthesis layer for higher-level insights
- **Bi-temporal Search** — `valid_from`/`valid_until` for time-based queries
- **TTL** — Automatic expiration and pruning of stale memories
- **Provenance** — `source_session_id` and `derived_from` linking
- **Rate Limiting** — Token-bucket protection against flooding

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. All contributions welcome — bug fixes, features, docs, tests.

## License

MIT
