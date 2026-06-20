# NexusAgent

**Multi-agent orchestration framework with NATS messaging.**

NexusAgent is a lightweight, self-hosted agent platform that runs anywhere. It features:

- **NATS-native**: Async messaging without Kafka's operational weight
- **Multi-interface**: CLI, TUI, Web UI, and API out of the box
- **Policy-aware tool system**: Progressive discovery with per-agent access control
- **Multi-agent parallelism**: Dynamic sub-agent spawning with memory slicing
- **Memory v2**: Hybrid file+vector memory with dream cycle consolidation
- **Production-grade**: Circuit breakers, encrypted credentials, version handshake

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run tests
pytest tests/ -q

# Start dev server
nats-server -js &
python -m nexusagent
```

## Documentation

### Getting Started
- [Installation](installation.md) — Install NexusAgent
- [Quick Start](quickstart.md) — Get up and running fast
- [Getting Started Guide](getting_started.md) — Detailed first-setup walkthrough
- [Local Development](local_development.md) — Contributor workflow guide

### Architecture
- [Codebase Map](CODEBASE_MAP.md) — Complete source inventory, coupling analysis, extraction candidates
- [Semantic Index](SEMANTIC_INDEX.md) — Data flows, state management, extension points, tech debt
- [Refactoring Plan](REFACTORING_PLAN.md) — Prioritized refactoring roadmap with completion status

### Codebase
- [State](STATE.md) — Module-by-module inventory with data flow and key classes
- [Code Review](CODE_REVIEW_COMPREHENSIVE.md) — Comprehensive multi-audit findings
- [Assessment](assessment/2026-07-18-independent-codebase-assessment.md) — Independent architecture assessment

### ADRs (Architecture Decision Records)
- [ADRs Index](adrs/index.md)
- [ADR 0001: Telemetry System](adrs/0001-telemetry-system-design.md)
- [ADR 0002: Project Structure](adrs/0002-project-structure-build-modes.md)
- [ADR 0003: Branding & Config](adrs/0003-project-branding-config.md)
- [ADR 0004: Documentation Standards](adrs/0004-documentation-standards.md)
- [ADR 0005: TUI Refactoring](adrs/0005-tui-refactoring.md)
- [ADR 0006: Memory Session Integration](adrs/0006-memory-session-integration.md)
- [ADR 0007: Context Compression](adrs/0007-context-compression.md)
- [ADR 0008: Cross-Session Memory](adrs/0008-cross-session-memory.md)

### Plans
- [Assessment & Roadmap](plans/2026-07-12-assessment-and-roadmap.md) — Strategic roadmap
- [Memory System v2](plans/2026-07-22-memory-system-v2.md) — Research-backed implementation plan
- [Memory System Audit](plans/2026-07-22-memory-system-audit-synthesis.md) — Audit synthesis
- [Memory System Overhaul](plans/2026-07-22-memory-system-overhaul.md) — Overhaul plan
- [Security Hardening](plans/phase-1-security-hardening.md) — Phase 1 security fixes
- [Version Handshake](plans/version-handshake-v1.md) — Version system spec

### Research
- [Tool Parity](research/TOOL-PARITY-FINAL.md)
- [TUI Aesthetics](research/TUI-AESTHETICS-FINAL.md)
- [Feature Parity CLI](research/FEATURE_PARITY_CLI_USER.md)
- [Feature Parity Arch](research/FEATURE_PARITY_CLI_ARCH.md)

### Reports
- [Comprehensive Code Review](CODE_REVIEW_COMPREHENSIVE.md)
- [Memory System Analysis](MEMORY_SYSTEM_ANALYSIS.md)
- [Memory System Comprehensive](MEMORY_SYSTEM_COMPREHENSIVE_ANALYSIS.md)
- [TUI Audit](TUI_AUDIT.md)
- [Runbook](RUNBOOK.md) — Operations guide

### Roadmap
- [Interactive Dashboard](ROADMAP/index.html) — Audit results, roadmap, competitor matrix, growth tracking

### Contributing
- [Contributing Guide](CONTRIBUTING.md)
