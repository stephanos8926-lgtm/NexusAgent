# Feature Parity Research — CLI Architecture (Technical Perspective)

> Generated: 2026-07-19
> Perspective: Internal design, agent loops, tool execution, memory systems, performance
> Scope: Claude Code CLI, Gemini CLI, Qwen Code CLI, OpenAI Codex CLI, Aider, Continue

---

## 1. Claude Code CLI — Architecture

### Agent Loop

Claude Code uses an **iterative tool-use loop** pattern:

1. User message → model call with system prompt + context
2. Model returns text + tool_use blocks
3. Tool calls executed in parallel (where safe)
4. Results fed back to model as tool_result
5. Loop continues until model returns only text (no tool_use)
6. PostToolUse hooks fire after each edit

**Subagent delegation**: Large reads delegated to separate context windows to avoid bloating main context. Subagents have their own isolated conversation context.

**Background tasks**: Bash commands can be backgrounded (Ctrl+B, or double-press for tmux). Long-running processes don't block the main interaction.

**Conversation threading**: Conversations can be forked, resumed, and renamed. The `/clear [name]` command labels the previous conversation.

### Tool Execution Model

- **Parallel tool calls**: Multiple tool calls in a single model response execute concurrently
- **Safety gating**: PreToolUse hooks can deny/execute tool calls
- **PostToolUse hooks**: Fire after each edit for linting, testing, etc.
- **MCP servers**: Per-session, support stdio and HTTP transports
- **MCP tool namespacing**: MCP tools appear as `mcp__<server>__<tool>`
- **24 hook events**: BeforeAgent, AfterAgent, BeforeModel, BeforeTool, AfterTool, PreCompact, PostToolUse, etc.

### Memory & Context Management

**Startup context loading:**
1. System prompt (immutable rules)
2. CLAUDE.md hierarchy (user home → project root → subdirectories)
3. Auto memory files (MEMORY.md, 200 lines/25KB limit)
4. MCP tool names + skill descriptions
5. Active conversation history

**Post-compaction reload:**
- Session system prompt reloads
- CLAUDE.md files re-injected (project-root persists)
- Auto memory files re-injected
- Skills re-injected (large skills truncated)
- Path-scoped rules reload on next file read

**Context window visualization** (`/context`):
- Colored grid showing tokens by category
- Optimization suggestions for context-heavy tools
- Fullscreen mode collapses per-item breakdown
- Per-tool token usage reporting

### Streaming Implementation

- WebSocket-based (for desktop app) or stdio-based (CLI)
- Events: `thinking`, `response_chunk`, `response`, `tool_call`, `tool_result`, `error`
- Token-by-token display for response_chunks
- Retry with exponential backoff on stream failures
- Model fallback on repeated failures

### Hook System Architecture

```json
{
  "hooks": {
    "PreToolUse": [{"type": "command", "command": "eslint --fix"}],
    "PostToolUse": [{"type": "command", "command": "git diff --stat"}],
    "BeforeAgent": [{"type": "command", "command": "echo 'Starting task'"}],
    "AfterAgent": [{"type": "command", "command": "echo 'Task complete'"}],
    "PreCompact": [{"type": "prompt", "prompt": "Save important state"}]
  }
}
```

- Hook input: JSON via stdin with session_id, cwd, transcript_path
- Hook output: JSON via stdout with decision/block reason
- Exit codes: 0 (pass), 2+ (block with message)
- Managed hooks via settings.json, user hooks in ~/.claude/settings.json

---

## 2. Gemini CLI — Architecture

**Repository**: google-gemini/gemini-cli (open source)

### Agent Loop (Three-Layer Architecture)

```
Layer 1: GeminiChat (lowest)
  ├── Wrapper around @google/genai SDK
  ├── Maintains conversation history
  ├── Mid-stream retry with exponential backoff
  └── Model fallback on repeated failures

Layer 2: Turn (middle)
  ├── Represents a single agentic loop turn
  ├── Instantiated fresh per sendMessageStream call
  ├── Accumulates pendingToolCalls during stream
  └── Caller dispatches tools after stream ends

Layer 3: GeminiClient (top)
  ├── Manages multi-turn agentic loop
  ├── Session limits monitoring
  ├── Chat compression triggering
  ├── Loop detection service
  └── Hook fire orchestration
```

### Streaming Architecture

Four-layer event pipeline:

```
Network Stream → GeminiChat → Turn → GeminiClient → useGeminiStream (React hook) → UI
```

**Event types** (discriminated union):
- `content` (text response)
- `toolCall` (function call)
- `toolResult` (execution result)
- `loopDetected` (abort event)
- `reconnect` (retry event)

**useGeminiStream** React hook bridges streaming engine to UI:
- Iterates AsyncIterable from GeminiClient.sendMessageStream()
- Manages connection lifecycle (connect, reconnect, disconnect)
- AbortController for cancellation
- Event buffering during disconnection

### Context Management (ContextManager + Sidecar)

**NEW architecture** (commit #24752):

```
ContextManager
  ├── WorkingBuffer (episodic context graph)
  │   ├── ConcreteNodes (messages, tool results)
  │   ├── PristineGraph (raw history)
  │   └── PipelineOrchestrator (GC pipeline)
  ├── ContextProfile (sidecar: config/budget)
  ├── ContextEnvironment (eventBus, graphMapper)
  └── ContextTracer (debug logging)
```

**Context pipeline stages:**
1. **Ingestion**: New messages added to working buffer
2. **Evaluation**: Check budget thresholds, fire consolidation events
3. **GC Backstop**: Enforce token budget before LLM call
4. **Rendering**: Map episodic graph → Gemini Content[] array

**Unified context management** (commit #24157):
- Progressive Message Normalization: full fidelity in "grace zone", proportional compression
- Tool Output Distillation: Large outputs → disk, LLM-generated summaries
- Intelligent Truncation: Token-budget-based with agent continuity summaries
- Configurable via `contextManagement` schema in settings

### Hook System (7 events)

| Event | Source | Purpose |
|-------|--------|---------|
| BeforeAgent | client.ts | Inject workspace context |
| BeforeModel | geminiChat.ts | Modify LLM request or skip reasoning |
| BeforeTool | scheduler.ts | Confirm destructive commands |
| AfterTool | scheduler.ts | Force follow-up tool executions |
| AfterAgent | client.ts | Signal for context clearing/distillation |

**Hook control flow decisions:**
- `deny`/`block`: Hard stop with policy violation
- `stop`: Mission complete, shut down agent loop
- `ask`: Confirmation dialog (Proceed Once / Proceed Always / Cancel)

### Security Architecture

- **Trusted Folders**: Three-tier trust model
- **6 Seatbelt profiles**: permissive-open → restrictive-closed
- **Conseca dynamic security**: Behind feature flag, runtime analysis
- **PolicyEngine**: Shell command pattern matching for dangerous commands

---

## 3. Qwen Code CLI — Architecture

**Repository**: QwenLM/qwen-code (open source, forked from Gemini CLI)

### Architecture Evolution

Qwen Code started as a fork of Gemini CLI and has gradually diverged:

- **Inherited**: Core agent loop, streaming, theming, keybindings
- **Added**: Daemon mode, multi-protocol support, SDK ecosystem
- **Diverged**: Provider abstraction layer, approval mode system, session management

### Daemon Mode (`qwen serve`) — Unique Architecture

**HTTP Bridge Architecture:**

```
[qwen serve] HTTP Server (Express 5)
  ├── POST /session              → Create/list sessions
  ├── POST /session/:id/prompt   → Submit prompt (FIFO queue)
  ├── POST /session/:id/cancel   → Cancel running prompt
  ├── GET  /session/:id/events   → SSE stream (Last-Event-ID reconnect)
  ├── POST /session/:id/permission/:id → Vote on approval
  ├── GET  /session/:id/context  → Get session context
  ├── POST /session/:id/model    → Change model
  └── GET  /health               → Health check
```

**Per-session architecture:**
- 1 daemon = 1 workspace × N sessions
- Each session: 1 `qwen --acp` subprocess
- EventBus per session: fan-out via HTTP/SSE
- Ring-backed replay buffer for event history
- Bounded subscriber queues with client_evicted overflow

**Client-side (DaemonClient):**
- TypeScript SDK with HttpTransport adapter
- Translates ACP ↔ stream-json
- Same query() flow works in both daemon and process modes
- EventSource for SSE with automatic reconnect

### Multi-Protocol Provider Layer

```
Unified Config
  ├── modelProviders
  │   ├── openai: { baseURL, model, api_key }
  │   ├── anthropic: { baseURL, model, api_key }
  │   ├── gemini: { baseURL, model, api_key }
  │   ├── vertex-ai: { project, location }
  │   └── alibabanCodingPlan: { baseURL, model }
  ├── defaultProvider: "openai" (startup protocol)
  └── Per-session provider switching via /model
```

### Configuration System

**Three-tier config** (new organized format):
1. `~/.qwen/settings.json` — user (global)
2. `.qwen/settings.json` — project (overrides user)
3. Environment variables — process-level overrides

**Key config sections:**
- `modelProviders`: Define available models per protocol
- `tools.approvalMode`: plan/default/auto-edit/yolo
- `context.includePaths`: Additional directories for context
- `context.excludePaths`: Paths to exclude

---

## 4. OpenAI Codex CLI — Architecture

**Repository**: openai/codex (Rust, 67K+ GitHub stars)

### Multi-Runtime Agent Architecture

```
codex-rs/core/src/codex.rs (central orchestration)
  ├── ToolOrchestrator
  │   ├── Approval check
  │   ├── Sandbox selection
  │   ├── Execution attempt
  │   └── Retry-with-escalation-on-denial
  ├── AgentState machine
  │   ├── Waiting
  │   ├── Running
  │   └── Error
  ├── Memory pipeline
  │   ├── memory_summary.md (5K token cap)
  │   └── Session state (SQLite)
  └── Config system
      ├── config.toml (user defaults)
      ├── requirements.toml (managed, admin-enforced)
      └── .codex/rules/ (workspace rules)
```

### Security Architecture (Most Advanced)

**Three independent safety layers:**

1. **Network isolation**: Default off, configurable per-sandbox
2. **OS sandbox**: Bubblewrap (Linux), Seatbelt (macOS), Windows native
3. **Approval policy**: Rule-based with auto-review subagent

**Exec policy DSL:**
```
# ~/.codex/rules/*.rules
allow read *, write src/**, deny rm -rf /
allow git *, deny git push *
```

**Auto-review reviewer:**
- Automatically approves low-risk sandbox escalations
- Escalates high-risk or novel actions to user
- Integrates with approval policy

### Memory Pipeline

- **memory_summary.md**: Capped at 5K tokens, injected at session start
- **SQLite database**: Job ownership leases (1-hour expiry), retry delays
- **Persistent state**: Survives process crashes
- **Session transcripts**: Local storage for resume

### JSON-RPC App-Server Interface

- MCP server support (Codex itself as MCP server)
- Desktop app communication bridge
- WebSocket transport for remote TUI

---

## 5. Aider — Architecture

**Repository**: paul-gauthier/aider (Python)

### Four Edit Modes

| Mode | Model Strategy | Use Case |
|------|---------------|----------|
| `diff` | Single model, diff format | Routine edits (default) |
| `whole` | Single model, whole-file | Small focused changes |
| `udiff` | Single model, unified diff | Surgical precision |
| `architect` | Two-model (planner + editor) | Multi-step refactoring |

### Repo-Map System (Killer Feature)

```
Full Repo Scan (tree-sitter)
  └── Symbol Index (files + key symbols)
       └── Dependency Graph (who calls what)
            └── PageRank Algorithm (relevance scoring)
                 └── Dynamic Budget Fitting (1K tokens default)
                      └── Chat-Optimized Selection (context-aware)
```

**Optimization features:**
- Binary search fitting within token budget
- mtime-based cache invalidation
- 8x expansion when no files in chat
- Auto-suggest files based on chat context
- Chat-history-aware relevance tuning

### Git-Native Architecture

- Every agent turn → automatic git commit with LLM-generated message
- Feature branch by default
- `/undo` → trivial rollback (git reset --soft)
- Dirty commits for uncommitted changes
- `--attribute-author`, `--attribute-committer` for git blame

### Voice Architecture

```
Microphone → sounddevice → Whisper API → Text → Agent Loop
                                                    ↕
User Speech → Voice Activity Detection → Transcription → Review → Execute
```

- Whisper API for transcription
- Chat history as prompt context for better recognition
- --voice-language for language constraint
- --voice-input-device for device selection

---

## 6. Continue — Architecture (VS Code Extension)

**Repository**: continuedev/continue.dev

While not a CLI tool, Continue provides relevant patterns:

- **IDE-native**: Full VS Code extension, not terminal-based
- **Tab-completion**: Inline code completion (GitHub Copilot-style)
- **Chat sidebar**: Persistent chat panel in IDE
- **Context providers**: @file, @folder, @web, @codebase
- **Model switching**: Multiple providers (OpenAI, Anthropic, Ollama, local)
- **RAG**: Built-in codebase indexing for context retrieval

### Relevant Patterns for NexusAgent

- Context provider abstraction (pluggable context sources)
- Inline diff display (side-by-side in editor)
- Tab-completion model for chat suggestions
- Persistent sidebar chat model

---

## Technical Comparison Matrix

| Architecture Aspect | Claude Code | Gemini CLI | Qwen Code | OpenAI Codex | Aider |
|---------------------|-------------|------------|-----------|--------------|-------|
| Language | TypeScript | TypeScript | TypeScript | Rust | Python |
| Agent Loop | Iterative tool-use | Three-layer (Chat→Turn→Client) | Same as Gemini + daemon | Orchestrator + state machine | Four-mode (diff/whole/udiff/architect) |
| Context Mgmt | CLAUDE.md + auto-compact | Episodic Context Graph | Inherited + daemon | Rule-based + memory_summary | Repo-map + PageRank |
| Streaming | WebSocket + stdio | AsyncIterable + React hook | Same + SSE | JSON-RPC | Direct |
| Security | 5 permission modes + sandbox | 6 Seatbelt profiles | 4 approval modes | Triple-gated (network + sandbox + approval) | Git-based undo |
| Memory | CLAUDE.md + MEMORY.md | GEMINI.md + checkpoint | QWEN.md + AGENTS.md | memory_summary.md + SQLite | MMAP.md + git |
| Hooks | 24 events | 7 events | Inherited | Rule-based | ❌ |
| Extension | MCP + skills | MCP + skills + extensions | MCP + skills | MCP + plugins | ❌ |
| Multi-agent | Subagents + teams | Agents | Agents | Reviewer agent | Architect mode |
| Unique | CLAUDE.md hierarchy | Context Graph + Distillation | Daemon mode | Bubblewrap + auto-review | Voice + repo-map |

### Key Architectural Patterns to Adopt

1. **Episodic Context Graph** (Gemini) — Graph-based context with pipeline GC
2. **Tool Output Distillation** (Gemini) — Large outputs → disk + LLM summary
3. **Rule-based Exec Policy** (Codex) — DSL for command safety
4. **Repo-map with PageRank** (Aider) — Smart context selection
5. **Multi-model provider layer** (Qwen) — Unified provider abstraction
6. **Progressive Message Normalization** (Gemini) — Age-based compression
7. **Auto-review subagent** (Codex) — Automatic approval for low-risk actions
