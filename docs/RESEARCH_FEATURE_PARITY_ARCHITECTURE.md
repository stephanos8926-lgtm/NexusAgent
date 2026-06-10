# AI Coding Agent Architecture: Feature Parity Research

**Date:** 2026-06-10  
**Scope:** Claude Code, Gemini CLI, Qwen Code CLI, Aider  
**Dimensions:** Session Management, Context/Window Management, Memory Systems, Tool Dispatch, Agent Loop, Extensibility, Collaboration

---

## 1. Architecture Summaries

### Claude Code

- **Architecture:** Monolithic CLI (TypeScript/Node) with a compiled binary. Two-layer: CLI frontend + agent_core backend. Communicates with Claude API (Anthropic-first, supports others via adapters).
- **Agent Loop:** Turn-based. Model → tool call(s) → results → next turn. Supports sequential and concurrent tool execution (read-only tools run in parallel; write tools are serialized). Built-in loop detection.
- **Subagents:** First-class `Task` tool. Subagents get **fresh context** (no parent history), only the task description + project-level CLAUDE.md. Parent only sees the final summary.
- **Compaction:** Multi-layered context management: (1) per-message tool-result budgeting, (2) history snip, (3) microcompact, (4) context-collapse projection, (5) proactive auto-compact, (6) reactive compact/retry recovery, (7) token-target budgeting. Server-side compaction API (`compact_20260112`). Manual `/compact` with optional steering instructions.
- **Session Storage:** JSONL files in `~/.claude/projects/`. Compaction boundaries stored as `compact_boundary` records with metadata (trigger type, pre-token count). Cross-file continuation via UUID chain — new session file's first record points to parent session's last UUID.
- **Memory:** `/memory` tool (file-backed, scoped). `CLAUDE.md` / `CLAUDE.project.md` loaded hierarchically (cwd → project root → home). Explicit `/remember` and implicit memory writes.
- **MCP:** Native tool search (deferred/on-demand loading of MCP tool schemas, reducing context 95%). Supports stdio, SSE, Streamable HTTP, and remote MCP with OAuth. MCP `list_changed` triggers auto-refresh. Scoping: local/user/project.
- **Extensibility:** Hooks system (PreToolUse, PostToolUse, PreCompact, SubagentStart/Stop, etc.), Skills (prompt packages), custom slash commands, plugins (extensions).

### Gemini CLI

- **Architecture:** Two-package monorepo (`packages/cli` frontend + `packages/core` backend). Open source (Apache 2.0). Config-driven via singleton `Config` class (service locator pattern). Event-driven (`coreEvents`/`appEvents`).
- **Agent Loop:** `LocalAgentExecutor` class runs a loop calling tools until `complete_task` is called. Supports concurrent tool calls. Loop detection via `LoopDetectionService`. `ChatCompressionService` manages context. Hooks: BeforeAgent, AfterAgent.
- **Subagents:** `LocalAgentExecutor` supports subagent spawning. Subagents preserve parent session ID via `parentSessionId`.
- **Compaction:** `ChatCompressionService` handles automatic summarization. Failed compression is tracked (`hasFailedCompressionAttempt`). Compression triggered by token threshold.
- **Session Storage:** JSONL files in `~/.gemini/tmp/<project_hash>/chats/`. Auto-save enabled by default. Retention: 30 days default (configurable via `maxAge`, `maxCount`, `minRetention`). Resume via `--resume` flag. Project-scoped (directory-based hash).
- **Memory:** Hierarchical `GEMINI.md` system: global (`~/.gemini/GEMINI.md`) → project root → intermediate directories → current directory. Automatic loading into every prompt. **Auto Memory** (experimental): background agent mines past session transcripts, proposes memory diffs and skill drafts to a review inbox. Never auto-applies — requires user approval.
- **MCP:** `ToolRegistry` manages built-in, extension, and MCP-discovered tools. MCP lifecycle: `McpClient` → `discoverInto()` → `DiscoveredMCPTool` wrapper. MessageBus for policy coordination. Command-discovered tools via `toolDiscoveryCommand`. Supports stdio, SSE, Streamable HTTP.
- **Extensibility:** Extensions plugin system, Hook system, custom commands, MCP servers, command-discovered tools.

### Qwen Code CLI

- **Architecture:** Fork/variant of Gemini CLI architecture (acknowledged). Two-package (`packages/cli` + `packages/core`). Same event-driven, config-driven patterns. Adds daemon mode, ACP protocol support, multi-provider model routing (OpenAI/Anthropic/Gemini/Alibaba Cloud).
- **Agent Loop:** Based on Gemini CLI's loop. Adds: scheduled tasks (`/loop` with cron), session-scoped cron scheduler. Subagent support via `LocalAgentExecutor`. Daemon mode runs one `qwen --acp` child per workspace, multiplexing N sessions.
- **Daemon Mode (`qwen serve`):** HTTP/SSE daemon exposing ACP. Per-session FIFO prompt queue, EventBus with ring replay and `Last-Event-ID` reconnect. Permission voting via HTTP route. Stage 1 architecture: 1 daemon = 1 workspace × N sessions.
- **Compaction:** Inherited from Gemini CLI base (`ChatCompressionService`). Session-memory compact tried before full summary compact; preserves a tail of recent messages.
- **Session Storage:** JSONL files in `~/.qwen/tmp/<project_id>/chats/`. `SessionService` class handles listing (cursor-based pagination by mtime), loading (tree-structured records for resumption), and removal. `--resume <session-id>` support.
- **Memory:** Two mechanisms: (1) `QWEN.md` (manual, hierarchical: global `~/.qwen/QWEN.md` → project root → intermediate dirs → cwd). Supports `@import` for file inclusion. (2) **Auto-memory** (experimental): background agent saves preferences/facts to `~/.qwen/projects/<hash>/memory/`. All branches of same repo share memory. Periodic dedup via `/dream` command. Auto-memory considers sessions idle for 3+ hours.
- **MCP:** Same lifecycle as Gemini CLI (discovery → DiscoveredMCPTool wrapper → registry). Three transports: stdio, SSE, Streamable HTTP. **Progressive discovery** (UI appears immediately; MCP status pill shows `N/M ready`). Configurable `discoveryTimeoutMs` per server. Legacy blocking mode via `QWEN_CODE_LEGACY_MCP_BLOCKING=1`.
- **Extensibility:** Extensions, Skills, MCP servers, ACP protocol for external clients, Python/TypeScript/Java SDKs, scheduled tasks.

### Aider

- **Architecture:** Single-process Python application. `Coder` class (in `aider/coders/base_coder.py`) is the central orchestrator. Layered: `main.py` (entry) → `Commands` (slash commands) → `Coder` (orchestration) → `Model` (litellm) + `RepoMap` (code understanding) + `GitRepo` + `InputOutput`. Uses `litellm` as universal LLM adapter (100+ providers). No daemon, no build step.
- **Agent Loop:** User prompt → construct layered message (system + repo map + chat history + current + files) → `litellm.completion()` → parse edit instructions from response → apply changes → lint → auto-commit to git. Strict alternation of user/assistant roles enforced.
- **Subagents:** Not natively supported (no subagent architecture). Single-agent only. Work is sequential within oneCoder instance.
- **Compaction:** `ChatSummary` class manages history summarization. Triggered when `done_messages` exceeds `max_chat_history_tokens` (default: `min(max_input_tokens/16, 1024), 8192)`). Runs on a background thread (non-blocking). Splits history into head/tail at assistant boundary; summarizes head recursively. Uses a configurable weak model. Configurable via `--max-chat-history-tokens`.
- **Session Storage:** No built-in session persistence until recent PRs (still in progress as of 2026-01). Chat history stored in markdown file (`.aider.chat.history.md`). Input history in `.aider.input.history`. Session save/load via `/session save|load|list|view|delete` (PR #4343, not yet merged to mainline). Sessions stored as JSON in `.aider/sessions/`.
- **Memory:** `.aider.conf.yml` for persistent config. No hierarchical memory file system. Project context via `RepoMap` (dynamic, computed per-request). Chat history + done messages are the primary "memory."
- **Tool Dispatch:** No MCP support. Built-in tools are hardcoded: file read/write/edit, shell commands, grep (via `grep_ast`/tree-sitter), git operations. No plugin system. Tools are not dynamically discovered.
- **Extensibility:** Custom edit formats (subclasses of `Coder`). Custom prompts via config. LLM provider flexibility via `litellm`. No hooks, no plugins, no MCP. Community fork with "context branches" (git-branch-like session management).

---

##2. Feature Comparison Matrix

### Legend
- 🟢 **Nice to have** — Differentiating, not essential for basic functionality
- 🟡 **Mandatory** — Expected in any production-grade AI coding agent
- 🔴 **CRITICAL** — Must-have for usability without it, the agent is fundamentally broken

| Feature | Claude Code | Gemini CLI | Qwen Code CLI | Aider | Tier |
|---|---|---|---|---|---:|
| **SESSION MANAGEMENT** ||||||
| Persistent session storage (JSONL/native) | ✅ `~/.claude/projects/` | ✅ `~/.gemini/tmp/<hash>/chats/` | ✅ `~/.qwen/tmp/<id>/chats/` | ⚠️ Markdown file; session save/load via PR (not mainline) | 🔴 CRITICAL |
| Session resume / continuation | ✅ `/resume`, `--continue`, compaction boundaries | ✅ `--resume` flag, interactive browser | ✅ `--resume <session-id>` | ✅ `restore-chat-history` config flag; `/restore-session N` (PR) | 🔴 CRITICAL |
| Session listing & management UI | ✅ `/sessions`, esc-esc rewind, `/clear` | ✅ Interactive TUI browser | ✅ Via `SessionService` + TUI | ✅ `/session list` (PR) | 🟡 Mandatory |
| Cross-session continuation chain | ✅ UUID chain across files (logicalParentUuid) | ⚠️ Session-resume (single-level) | ⚠️ Session-resume (single-level) | ❌ | 🟢 Nice to have |
| Session retention policies | ❌ Manual cleanup | ✅ 30-day default, configurable `maxAge`/`maxCount`/`minRetention` | ⚠️ Project-scoped (implied cleanup) | ❌ | 🟢 Nice to have |
| /clear (new session in same window) | ✅ | ✅ | ✅ | ✅ | 🔴 CRITICAL |
| /rewind (undo to checkpoint) | ✅ esc-esc | ❌ | ❌ | ❌ | 🟢 Nice to have |
| **CONTEXT / WINDOW MANAGEMENT** ||||||
| Compaction (auto + manual) | ✅ 7-layer: tool-result budget, history snip, microcompact, context-collapse, auto-compact, reactive, token-target | ✅ `ChatCompressionService` + API-side compression | ✅ Inherited from Gemini CLI | ✅ `ChatSummary` (head/tail recursive) | 🔴 CRITICAL |
| Compaction with steering instructions | ✅ `/compact focus on X` | ⚠️ Configurable instructions | ⚠️ Configurable | ❌ | 🟡 Mandatory |
| Proactive/partial compaction (microcompact) | ✅ Separate from full compact | ❌ | ✅ (session-memory compact) | ❌ | 🟢 Nice to have |
| Tool-result budget management | ✅ Per-message enforcement | ❌ | ❌ | ❌ | 🟢 Nice to have |
| Token budget allocation for repo map | ✅ (dynamic, 1 - files - map = remaining) | N/A (no repo map) | N/A (no repo map) | ✅ Default 1024 tokens, configurable `map_tokens`, `map_mul_no_files` | 🟡 Mandatory |
| 1M+ context window support | ✅ (Claude Opus/Sonnet 1M) | ✅ (Gemini 1M+) | ✅ (model-dependent) | ⚠️ Model-dependent | 🟡 Mandatory |
| Context rot awareness / mitigation | ✅ Explicit in docs, multi-layer defense | ⚠️ Implicit via compression | ⚠️ Implicit via compression | ⚠️ Implicit via summarization | 🟡 Mandatory |
| **MEMORY SYSTEMS** ||||||
| Hierarchical memory files (project global → subdir) | ✅ `CLAUDE.md` / `CLAUDE.project.md` (cwd → root → home) | ✅ `GEMINI.md` (cwd → workspace → home) + JIT discovery | ✅ `QWEN.md` (cwd → root → home) + `@import` | ❌ No hierarchical files | 🔴 CRITICAL |
| Auto-memory (implicit fact extraction) | ✅ `/memory` tool (model-triggered writes) | ✅ Auto Memory (background agent, review inbox, diffs + skills) | ✅ Auto-memory (background, idle 3h+, `/dream` cleanup) | ❌ | 🟡 Mandatory |
| Explicit remember command | ✅ `/remember "fact"` | ✅ "Remember that..." (natural language → file edit) | ✅ `/remember "fact"` | ❌ | 🟡 Mandatory |
| Memory review/inbox workflow | ❌ (direct write) | ✅ Review inbox with diffs; approve/discard | ⚠️ `/memory` panel, `/dream` cleanup | ❌ | 🟢 Nice to have |
| Cross-project (global) memory | ✅ `~/.claude/CLAUDE.md` | ✅ `~/.gemini/GEMINI.md` | ✅ `~/.qwen/QWEN.md` | ❌ | 🟡 Mandatory |
| Memory import/include system | ⚠️ (CLAUDE.md is flat) | ❌ | ✅ `@import path/to/file.md` in QWEN.md | ❌ | 🟢 Nice to have |
| Branch-scoped memory sharing | ❌ | ❌ | ✅ All branches share same memory folder | ❌ | 🟢 Nice to have |
| **TOOL DISPATCH** ||||||
| Concurrent tool execution | ✅ Read-only parallel; writes serialized | ✅ | ✅ (inherited) | ❌ Sequential only | 🔴 CRITICAL |
| Tool confirmation / approval flow | ✅ Auto-approve / per-tool / per-session modes | ✅ `ApprovalMode` variants, MessageBus policy | ✅ Trust settings + confirmation logic | ⚠️ Shell commands only (y/n) | 🟡 Mandatory |
| Loop detection | ✅ Built-in | ✅ `LoopDetectionService` | ✅ Inherited | ❌ | 🟡 Mandatory |
| Tool output truncation/budgeting | ✅ Per-message tool-result budget enforcement | ⚠️ `ToolOutputMaskingService` | ✅ Inherited | ❌ | 🟢 Nice to have |
| **AGENT LOOP** ||||||
| Agent loop pattern | Turn-based: model → tool(s) → results → repeat | `LocalAgentExecutor`: loop until `complete_task` | Based on Gemini CLI + cron scheduler | Single turn: prompt → response → edit → commit | 🔴 CRITICAL |
| Subagent spawning (clean context) | ✅ `Task` tool — fresh context, summary returned | ✅ `LocalAgentExecutor` with `parentSessionId` preservation | ✅ Inherited | ❌ No subagent support | 🟡 Mandatory |
| Subagent permission scoping | ✅ Subagent only sees task + CLAUDE.md | ✅ Per-subagent tool registry | ✅ Per-session Config/ToolRegistry/McpClientManager | N/A | 🟢 Nice to have |
| Multi-agent orchestration | ✅ Via SDK (subagents as tools) | ✅ Via SDK | ✅ Via SDK + ACP daemon | ❌ | 🟢 Nice to have |
| Scheduled/recurring tasks | ❌ | ❌ | ✅ `/loop` with cron, session-scoped scheduler | ❌ | 🟢 Nice to have |
| **EXTENSIBILITY** ||||||
| MCP (Model Context Protocol) support | ✅ Full: stdio, SSE, Streamable HTTP, remote + OAuth. Tool search (deferred loading, -95% context) | ✅ Full: stdio, SSE, Streamable HTTP. `ToolRegistry` + `McpClient` lifecycle | ✅ Full: stdio, SSE, Streamable HTTP. Progressive discovery | ❌ No MCP support | 🔴 CRITICAL |
| MCP tool search / deferred loading | ✅ Default on (reduces context 95%) | ❌ All tools loaded upfront | ❌ All tools loaded upfront | N/A | 🟡 Mandatory |
| MCP scoping (local/user/project) | ✅ `--scope local|user|project` | ⚠️ Config-based | ⚠️ Config-based | N/A | 🟡 Mandatory |
| Plugin / extension system | ✅ Extensions, Skills (prompt packages), custom slash commands | ✅ Extensions, custom commands | ✅ Extensions, Skills | ❌ No plugin system | 🟡 Mandatory |
| Hooks system (PreToolUse, PostToolUse, etc.) | ✅ Full hooks: PreToolUse, PostToolUse, PreCompact, SubagentStart/Stop, UserPromptSubmit, Stop | ✅ BeforeAgent, AfterAgent hooks | ✅ Inherited from Gemini CLI | ❌ No hooks | 🟡 Mandatory |
| SDK (programmatic agent building) | ✅ Agent SDK (TypeScript) + Python SDK | ✅ SDK available | ✅ TypeScript, Python, Java SDKs | ❌ No SDK (library use only via Python import) | 🟡 Mandatory |
| IDE integration | ✅ VS Code, JetBrains, desktop app, web | ✅ VS Code extension | ✅ VS Code, Zed, JetBrains | ❌ Terminal only | 🟡 Mandatory |
| **COLLABORATION** ||||||
| Multi-client session sharing | ❌ Single user per session | ❌ Single user per session | ✅ Daemon mode: 1 workspace × N sessions, EventBus fan-out, any-client permission voting | ❌ | 🟢 Nice to have |
| ACP (Agent Client Protocol) support | ❌ | ❌ | ✅ `qwen --acp` + `qwen serve` HTTP/SSE bridge | ❌ | 🟢 Nice to have |
| Live collaboration (multiple users, same session) | ❌ | ❌ | ✅ `sessionScope: single` for cross-client live collaboration | ❌ | 🟢 Nice to have |
| Git integration (auto-commit, attribution) | ⚠️ Via MCP/tools | ⚠️ Via tools | ⚠️ Via tools | ✅ **Core feature**: auto-commit with AI attribution, `/commit`, `/diff`, `/undo` | 🟡 Mandatory |
| Repo map / code understanding | ⚠️ Via tools (Grep, Glob, Read) | ⚠️ Via tools | ⚠️ Via tools | ✅ **Core feature**: tree-sitter + PageRank repo map, dynamic token-bounded context selection | 🟡 Mandatory |

---

## 3. Key Architectural Patterns

### 3.1 Context Management Spectrum

| Approach | Agent | Description |
|---|---|---|
| Multi-layer defense | Claude Code | 7 distinct layers from per-message budgeting to full compaction |
| Service-based compression | Gemini CLI / Qwen Code | `ChatSummary`/`ChatCompressionService` with background threading |
| Head/tail recursive summarization | Aider | Splits at assistant boundary, summarizes head recursively, preserves tail verbatim |

**Takeaway:** Claude Code has the most sophisticated context management. Aider's approach is simplest but effective for its single-agent, single-session model. Gemini CLI and Qwen Code sit in the middle.

### 3.2 Memory Architecture Patterns

| Pattern | Agents | Description |
|---|---|---|
| Hierarchical markdown files | Claude Code, Gemini CLI, Qwen Code | Project-root → subdirectory → global. Loaded at session start. |
| Auto-extraction from transcripts | Gemini CLI, Qwen Code | Background agent mines past sessions, proposes diffs to review inbox. |
| File-backed scoped memory tool | Claude Code | Model calls `save_memory` tool; client implements CRUD on files. |
| None (chat history only) | Aider | No persistent memory files; relies on chat history + repo map. |

**Takeaway:** All agents except Aider have converged on hierarchical markdown files as the primary memory mechanism. Auto-extraction (Gemini CLI, Qwen Code) is a differentiator for long-term personalization.

### 3.3 MCP Integration Patterns

| Pattern | Agents | Description |
|---|---|---|
| Deferred tool search (on-demand) | Claude Code | Tool schemas loaded only when needed; -95% context usage. |
| Upfront loading with registry | Gemini CLI, Qwen Code | All MCP tools discovered at startup, registered in `ToolRegistry`. |
| Progressive discovery | Qwen Code | UI appears immediately; MCP status pill updates as servers connect. |
| No MCP | Aider | No MCP support; built-in tools only. |

**Takeaway:** Claude Code's deferred MCP tool search is a significant architectural advantage for agents with many MCP servers. Qwen Code's progressive discovery is a UX improvement for startup latency.

### 3.4 Session Persistence Patterns

| Pattern | Agents | Description |
|---|---|---|
| JSONL with compaction boundaries | Claude Code | Rich metadata (trigger type, pre-tokens, UUID chain for cross-file continuation). |
| JSONL with retention policies | Gemini CLI | Configurable `maxAge`/`maxCount`/`minRetention`. Project-scoped by directory hash. |
| JSONL + daemon multiplexing | Qwen Code | Same as Gemini CLI + daemon mode for multi-client session sharing. |
| Markdown + PR for JSON save/load | Aider | Chat history in markdown; session save/load via community PR (not mainline). |

**Takeaway:** Claude Code has the most robust session persistence with compaction boundary tracking. Gemini CLI adds retention policies. Qwen Code adds multi-client sharing. Aider lags behind.

### 3.5 Agent Loop Patterns

| Pattern | Agents | Description |
|---|---|---|
| Turn-based with subagent trees | Claude Code | Main agent → Task tool → subagent (clean context) → summary returned. |
| Executor loop until completion | Gemini CLI / Qwen Code | `LocalAgentExecutor` runs until `complete_task` tool is called. |
| Single-turn edit-commit loop | Aider | Prompt → response → parse edits → apply → lint → commit. No subagents. |

**Takeaway:** Claude Code and Gemini CLI/Qwen Code support hierarchical agent composition. Aider is flat — one agent, one context, sequential edits.

---

## 4. Critical Findings for NexusAgent

### 🔴 CRITICAL Features (Must Have)

1. **Persistent session storage with resume** — All production agents have this. JSONL is the de facto standard. Without it, users lose work on crash/disconnect.
2. **Compaction (auto + manual)** — Non-negotiable for long sessions. Must handle context approaching window limits gracefully.
3. **Hierarchical memory files** — CLAUDE.md/GEMINI.md/QWEN.md pattern is universal. Users expect project-level and global instructions to persist.
4. **Concurrent tool execution** — Sequential-only tool dispatch is a major performance bottleneck. Read-only tools must run in parallel.
5. **MCP support** — The ecosystem has standardized on MCP. Without it, the agent cannot integrate with the growing tool ecosystem.
6. **Session /clear** — Users must be able to start fresh without restarting the process.

### 🟡 Mandatory Features (Expected in Production)

1. **Session listing and management UI** — Users need to browse, resume, and delete past sessions.
2. **Compaction with steering** — Let users guide what to keep during compaction.
3. **Auto-memory / implicit fact extraction** — Reduces repetitive prompting; major UX improvement.
4. **Explicit `/remember` command** — Users expect to be able to save facts on demand.
5. **Global (cross-project) memory** — User preferences should apply everywhere.
6. **Subagent spawning** — Clean-context subtask delegation is essential for complex multi-step work.
7. **Tool confirmation/approval flow** — Safety requirement for destructive operations.
8. **Loop detection** — Prevents infinite tool-call loops.
9. **MCP scoping (local/user/project)** — Different tools for different contexts.
10. **Plugin/extension system** — Community extensibility is table stakes.
11. **Hooks system** — Pre/post tool execution hooks for logging, safety, customization.
12. **SDK** — Programmatic access for building on top of the agent.
13. **IDE integration** — Terminal-only is insufficient for most developers.
14. **Git integration** — Auto-commit with attribution is a core workflow for AI coding agents.
15. **Repo map / code understanding** — Intelligent context selection beats dumping entire files.
16. **1M+ context window support** — Users work on large codebases; small context windows are a dealbreaker.

### 🟢 Nice-to-Have Features (Differentiators)

1. **Cross-session continuation chains** (Claude Code's UUID chain) — Elegant but complex.
2. **Memory review inbox** (Gemini CLI's diff-based approval) — Safety vs. convenience tradeoff.
3. **Memory import/include system** (QWEN.md `@import`) — Useful for large projects.
4. **Branch-scoped memory sharing** (Qwen Code) — Nice for multi-branch workflows.
5. **MCP deferred tool search** (Claude Code) — Major context savings but complex to implement.
6. **Daemon mode / multi-client** (Qwen Code) — Enables IDE + CLI sharing same session.
7. **ACP protocol support** (Qwen Code) — Emerging standard for agent-client communication.
8. **Scheduled/recurring tasks** (Qwen Code `/loop`) — Useful for monitoring/cron workflows.
9. **/rewind checkpoint** (Claude Code esc-esc) — Undo to arbitrary point in conversation.
10. **Proactive micro-compaction** (Claude Code) — Prevents context rot before it happens.
11. **Tool-result budget management** (Claude Code) — Fine-grained context control.
12. **Session retention policies** (Gemini CLI) — Automatic cleanup of old sessions.

---

## 5. Architectural Recommendations for NexusAgent

Based on this research, the recommended architecture for NexusAgent should:

1. **Adopt JSONL session storage** with compaction boundary metadata (follow Claude Code's model — it's the most robust).
2. **Implement hierarchical memory files** (markdown, project-root → global) with an auto-memory background agent for fact extraction.
3. **Support MCP with deferred tool search** — this is the single biggest context efficiency win. At minimum, support stdio and Streamable HTTP transports.
4. **Build a turn-based agent loop** with subagent support (clean context per subagent, summary returned to parent).
5. **Implement multi-layer compaction**: at minimum, auto-compact at threshold + manual `/compact` with steering instructions.
6. **Support concurrent tool execution** for read-only operations.
7. **Include a hooks system** (PreToolUse, PostToolUse, PreCompact, SubagentStart/Stop) for extensibility.
8. **Provide an SDK** (TypeScript and/or Python) for programmatic use.
9. **Integrate git** with auto-commit and attribution (follow Aider's lead — it's the gold standard for git integration).
10. **Build a repo map** using tree-sitter + relevance ranking (Aider's PageRank approach is proven and effective).

---

## 6. Sources

- Claude Code Docs: Session management, compaction, MCP, agent loop, subagents
- Gemini CLI Architecture.md, client.ts, session-management.md, GEMINI.md docs, Auto Memory docs
- Qwen Code Docs: Memory, MCP, session service, daemon mode (PR #3803), architecture overview
- Aider DeepWiki: Core architecture, repo map, message formatting, chat history; Aider docs: config, session PRs
- Anthropic Engineering: Code execution with MCP, context engineering cookbook
- Community analysis: Claude Code session continuation (blog.fsck.com), Aider architecture deep-dive (simranchawl.com, ggprompts.com)
