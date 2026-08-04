# NexusAgent Operations Manual & Final Architectural Handoff

Welcome to the production-ready **NexusAgent** runtime platform. All 12 transition phases have been successfully delivered, integrated, audited, and verified.

---

## 🚀 Runtime Operating Instructions

### 1. Starting the Control Plane Server
To start the central FastAPI Control Plane server, run:
```bash
python3 -m nexusagent.server
```
The server will boot by default on port `8000` with:
- Structured logging enabled (if configured)
- Automatic NATS Bus connectivity
- Embedded SQLite Task & Session Store initialization
- Live WebSocket and REST routes for dynamic interaction and administrative capability management

### 2. Launching the Terminal User Interface (TUI)
To launch the interactive Textual TUI client, run:
```bash
nexus-client tui
```
**Interactive Features:**
- **Themes**: Switch themes instantly using the `/theme <name>` command (e.g., `/theme tokyo night`) or cycle via `Ctrl+T`. Use `/theme-preview` to inspect visual color blocks.
- **Git Tracking**: The status bar dynamically reflects repository branch, staged, dirty, or untracked changes asynchronously in the background.
- **Accessibility**: Navigate through collapsible tools seamlessly using `Tab` focus, visual `:focus` highlights, and `Space` or `Enter` keys.

---

## 🔒 Production Security & Hardening Controls

### 1. Configuration Immutability
To protect against runtime configuration pollution, all loaded configuration settings (exposed via the `settings` singleton in `src/nexusagent/infrastructure/config.py`) are fully **frozen** in Pydantic. Attempting to mutate configuration attributes at runtime will raise a `ValidationError`.

### 2. Environment Validation
When the system is run with `NEXUS_ENV=production`, strict production-grade security defaults are automatically validated and enforced on boot:
- The WebSocket client API key `client.api_key` must be configured and non-empty.
- SSL/TLS `server.tls_enabled` must be enabled (`True`).
- Localhost-only NATS URLs are blocked.

### 3. Secrets Redaction (Data Protection)
All interactive memories written through `HybridMemoryManager.remember` and all system events serialized through `SystemEvent.to_dict()` are scanned and sanitized.
- Regex pattern filters redact Google/Gemini, OpenAI, OpenRouter, and HuggingFace API keys.
- Decrypted keys from the AuthManager keystore and environment variables are dynamically matched and replaced with `[REDACTED]` before writing to disk, NATS, or the EventStore.

### 4. Audited Shell Sandboxing
The shell execution tool (`src/nexusagent/tools/shell.py`) includes argument-level auditing:
- Prohibits dangerous system binaries (e.g., `sudo`, `su`, `chmod`, `chown`).
- Restricts recursive `rm` calls on root, home, or system directories.
- Denies command arguments referencing sensitive paths outside the workspace root (e.g., `/etc/passwd`, `/etc/shadow`, `id_rsa`, AWS credentials).

---

## 🛠️ Testing, Verification & Diagnostics

To run the complete suite of tests verifying all 12 architectural phases:
```bash
PYTHONPATH=src:. python3 -m pytest tests/ -q --timeout=30 \
  --ignore=tests/api_e2e_project \
  --ignore=tests/test_e2e_production.py \
  --ignore=tests/test_graph_nodes.py \
  --ignore=tests/test_bus.py
```

### Subsystem Health Diagnostics
The FastAPI Control Plane exposes:
- `/health`: Detailed health of database connections, NATS bus connection, POL, and active sessions.
- `/metrics`: Live Prometheus-compatible metrics collector.

---

## 🏁 Architectural Transition Completion Status

| Phase | Milestone | Scope / Deliverable | Status |
|---|---|---|---|
| **Phase 1** | Runtime Foundation | Lifecycle, context, runtime, sessions, DI container | ✅ DELIVERED |
| **Phase 2** | Durable Task Execution | Task state machine, persistent TaskStore, recovery loop | ✅ DELIVERED |
| **Phase 3** | Event-Driven Core | SystemEvent, NATS integration, SQLite EventStore | ✅ DELIVERED |
| **Phase 4** | LangGraph Worker Runtime | LangGraph worker graph, checkpointers, state persistence | ✅ DELIVERED |
| **Phase 5** | Planner & Orchestrator | Planner decomposition, WorkerPool concurrent execution | ✅ DELIVERED |
| **Phase 6** | DAG Execution Engine | DAG topological execution, recovery, failure escalation | ✅ DELIVERED |
| **Phase 7** | POL Control Plane | AI Governance, subscriber, dynamic intervention protocol | ✅ DELIVERED |
| **Phase 8** | Capability Security Model | Capability registry, PolicyEngine, sync/async audit trail | ✅ DELIVERED |
| **Phase 9** | Memory Evolution (4-layer) | Working, Episodic, Semantic, Procedural trust layers | ✅ DELIVERED |
| **Phase 10** | Observability & Reliability | Structured logging, tracing IDs, Prometheus `/metrics` | ✅ DELIVERED |
| **Phase 11** | Production Readiness | Secrets redaction, immutability, sandboxing, ops tests | ✅ DELIVERED |
| **Phase 12** | Master Finish | Version 0.6.0 editable install, handoff manuals | ✅ DELIVERED |

*Congratulations! The NexusAgent platform is now ready for fully autonomous, secure, and resilient operations.* 🚀
