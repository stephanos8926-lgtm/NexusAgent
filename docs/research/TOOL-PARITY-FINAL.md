# Tool Parity — Final Synthesis Report

> Synthesized from: tool-parity-workflow.md, tool-parity-architecture.md
> Date: 2026-06-11

---

## 1. Executive Summary

Comprehensive comparison of NexusAgent against Claude Code CLI, Gemini CLI, Qwen Code CLI, and DeepAgents across 20+ dimensions. NexusAgent has unique strengths (LangGraph research workflows, hybrid memory, 3-tier policy system) but gaps in extensibility, session management, and built-in tooling.

## 2. Feature Parity Matrix

### 2.1 Already at Parity (✅)

| Feature | NexusAgent | Claude Code | Gemini CLI | Qwen Code | DeepAgents |
|---------|-----------|-------------|------------|-----------|------------|
| ReAct agent loop | ✅ | ✅ | ✅ | ✅ | ✅ |
| Streaming responses | ✅ | ✅ | ✅ | ✅ | ✅ |
| Tool registration | ✅ | ✅ | ✅ | ✅ | ✅ |
| Policy/permissions | ✅ 3-tier | ✅ auto/ask/plan | ✅ | ✅ multi-layer | ✅ |
| Git integration | ✅ 10 tools | ✅ | ✅ | ✅ | ✅ |
| File operations | ✅ 7 tools | ✅ | ✅ | ✅ | ✅ |
| Shell execution | ✅ | ✅ | ✅ | ✅ | ✅ |
| Web search | ✅ | ✅ | ✅ | ✅ | ✅ |
| Sub-agents | ✅ | ✅ | ✅ | ✅ | ✅ |
| Memory system | ✅ hybrid | ❌ | ❌ | ❌ | ✅ |
| Research workflows | ✅ LangGraph | ❌ | ❌ | ❌ | ❌ |

### 2.2 Gaps Filled in This Sprint (🆕)

| Feature | Status | Priority |
|---------|--------|----------|
| Hooks system | ✅ Implemented | HIGH |
| Code review tool | ✅ Implemented | HIGH |
| Todo management | ✅ Implemented | MEDIUM |
| System prompt | ✅ FORGE.md integration | HIGH |
| TUI aesthetics | ✅ Complete overhaul | HIGH |
| Responsive design | ✅ Implemented | MEDIUM |
| Accessibility | ✅ NO_COLOR + keyboard | MEDIUM |

### 2.3 Remaining Gaps (📋)

| Feature | Priority | Effort | Notes |
|---------|----------|--------|-------|
| Session management TUI | HIGH | Medium | Browse/resume/fork sessions |
| Skills system | HIGH | Medium | Extensible skill loading |
| LSP integration | MEDIUM | Low | Experimental in Qwen |
| Scheduled tasks | MEDIUM | Low | Cron-like |
| Extensions/plugins | LOW | High | Plugin marketplace |
| Headless/CI mode | MEDIUM | Medium | Non-interactive execution |
| Sidechain transcripts | LOW | Low | For sub-agent debugging |
| Concurrent tool execution | MEDIUM | Medium | Claude Code pattern |
| Custom agent definitions | LOW | Medium | Like Qwen extensions |

## 3. Competitive Analysis

### 3.1 Claude Code CLI — The Gold Standard

**Strengths:**
- 9-step pipeline with pre-model shapers
- 27 hook events for automation
- Plugin marketplace (Claude Code Marketplace)
- Sidechain transcripts for sub-agent debugging
- Concurrent tool execution
- Sophisticated permission system

**What we should adopt:**
- Pre-model hook execution (we now have hooks ✅)
- Plugin/extension system (skills system planned)
- Concurrent tool execution pattern

### 3.2 Gemini CLI — The Balanced Choice

**Strengths:**
- Clean DeclarativeTool/ToolInvocation split
- Extensions gallery
- Multi-modal capabilities
- Simple but effective permission model

**What we should adopt:**
- Declarative tool pattern (our registry is similar)
- Extension system

### 3.3 Qwen Code CLI — The Feature-Rich Option

**Strengths:**
- 14 hook events
- Channels (Telegram, WeChat, DingTalk)
- LSP integration
- Code review built-in
- Scheduled tasks
- Sandboxing support
- Multi-layer permissions

**What we should adopt:**
- Channels (we have Telegram via Hermes ✅)
- Code review (now implemented ✅)
- Hooks (now implemented ✅)
- LSP (planned)

### 3.4 DeepAgents — The Foundation

**Strengths:**
- Async sub-agents
- Virtual filesystem backend
- Context compression
- Memory middleware
- Pluggable architecture

**What we should adopt:**
- Async sub-agents (our WorkerPool is synchronous-wait)
- Context compression (we have compaction ✅)

## 4. NexusAgent Unique Differentiators

These are things NexusAgent does that competitors don't:

1. **LangGraph Research Workflows** — Durable, resumable, checkpointed multi-step research
2. **Hybrid Memory** — File-based + SQLite FTS5 + sqlite-vec with tiered embeddings
3. **3-Tier Policy System** — Permissive/restricted/strict with thread-local context
4. **NATS JetStream Task Orchestration** — Distributed task processing with circuit breakers
5. **Multi-Provider LLM** — Gemini + OpenRouter with automatic failover
6. **Textual TUI** — Modern Python TUI with 7 themes and responsive design

## 5. Priority Roadmap

### P0 — Critical (Do Now)
- ✅ Hooks system
- ✅ Code review tool
- ✅ TUI aesthetics overhaul
- ✅ System prompt enhancement

### P1 — High (Next Sprint)
- Session management TUI
- Skills system
- fetch_url, ask_user tools (already exist)
- Concurrent tool execution

### P2 — Medium (This Quarter)
- LSP integration
- Scheduled tasks
- Custom agent definitions
- Sidechain transcripts

### P3 — Low (Future)
- Plugin marketplace
- Headless/CI mode
- Sandboxing support
- Multi-modal capabilities

## 6. Recommendations

1. **Session management TUI** — Browse, resume, fork sessions (like Claude Code's /threads)
2. **Skills system** — Extensible skill loading from ~/.nexusagent/skills/
3. **Concurrent tool execution** — Start concurrency-safe tools before model finishes
4. **Plugin manifest** — Allow third-party extensions via declarative manifests
5. **Better error recovery** — Claude Code's 9-step pipeline is more resilient

---

*Sprint completed: 2026-06-11*
