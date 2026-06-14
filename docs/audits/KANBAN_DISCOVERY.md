# Kanban Phase 2 — Discovery Report

> **Date:** 2026-07-19
> **Searcher:** OWL (Lucien) — inline execution
> **Sources:** tokrepo (3 assets), web search (10+ results), Hermes docs

---

## 1. Kanban + AI Agent Integration Patterns

### AgentFlow (UrRhb/agentflow) — 7-Stage Pipeline
**URL:** https://github.com/UrRhb/agentflow

The most relevant pattern. AgentFlow treats the Kanban board as a **distributed state machine**:

```
Backlog → Research → Build → Review → Test → Integrate → Done
```

Key concepts applicable to our workflow:
- **Stateless orchestrator** — crontab-driven sweep, no daemon, crash-proof
- **Transitive priority dispatch** — tasks that unblock the most work get built first (automatic critical path)
- **Conflict-aware scheduling** — parallel tasks touching same files are serialized
- **Deterministic gates before AI** — `tsc + eslint + tests` catch ~60% of issues before AI review
- **Adversarial AI review** — reviewers must "list 3 things wrong before deciding to pass"
- **Per-task cost tracking** with stage cost ceilings
- **Spec drift detection** — SHA-256 hash comparison catches requirement changes mid-sprint

### Vibe-Kanban — Rust-Powered Agent Kanban
**URL:** https://tokrepo.com/en/workflows/asset-b8e74112

TUI-based kanban for AI coding agents. Key features:
- Column-based workflow (Todo → In Progress → Review → Done)
- Priority and tag system
- Agent assignment per card

### Agent Kanban (saltbo/agent-kanban) — Agent-First Task Board
**URL:** https://github.com/saltbo/agent-kanban

The most sophisticated pattern found. Key concepts:
- **Cryptographic agent identity** — Ed25519 keys for each agent
- **Role-based task routing** — agents have roles (architect, frontend, backend, reviewer)
- **Atomic claims** — race-condition-free task claiming via D1 batch operations
- **Stale detection** — agents inactive for 2h auto-marked offline
- **Multi-runtime** — supports Claude Code, Codex CLI, Gemini CLI, ACP-compliant agents
- **Task dependencies** — `depends_on` with cycle detection
- **Self-organization** — lead agents create subtasks and assign to teammates

### Hermes Native Kanban
**URL:** https://github.com/NousResearch/hermes-agent

Hermes already has a built-in Kanban system:
- SQLite-backed (`~/.hermes/kanban.db`)
- 7 `kanban_*` tools (`kanban_show`, `kanban_list`, `kanban_complete`, `kanban_block`, `kanban_heartbeat`, `kanban_comment`, `kanban_create`, `kanban_link`)
- Dispatcher daemon with crash detection and circuit breaker
- Auto-decomposition of triage tasks
- Dependency graph with parent→child links
- Multi-profile collaboration (workers, orchestrators, reviewers)

**Key insight:** We're NOT building a Kanban system from scratch. We're designing a **review workflow** that validates and populates the existing Hermes Kanban board.

---

## 2. Existing Kanban Tools with API Support

| Tool | Type | API | Self-Hosted | Notes |
|------|------|-----|-------------|-------|
| **Hermes Kanban** | Built-in | `kanban_*` tools + CLI | ✅ | Already installed, SQLite-backed |
| **Focalboard** | Open source | REST API | ✅ | Mattermost-built, Trello alternative |
| **Vikunja** | Open source | REST API | ✅ | Go-based, kanban + Gantt |
| **Linear** | SaaS | GraphQL API | ❌ | Best-in-class for software teams |
| **GitHub Projects** | SaaS | GraphQL API | ❌ | Already have GitHub integration |

**Recommendation:** Use the native Hermes Kanban. It's already installed, has tool-level integration, and supports multi-profile collaboration. No external tool needed.

---

## 3. Workflow Patterns for Kanban-Driven Development

### The "Kanban Review Workflow" Pattern (Novel)

Based on the research, no existing tool specifically addresses the problem of **validating a Kanban board's readiness for agent-driven execution**. This is a new workflow type that combines:

1. **Board Health Check** — stale tasks, blocked tasks, failure loops
2. **Task Decomposition Quality** — are tasks small enough for sub-agents (2-5 min)?
3. **Dependency Ordering** — can parallel tasks actually run in parallel?
4. **Conflict Detection** — do any tasks touch the same files?
5. **Go/No-Go Decision** — is the board ready for dispatch?

This is the **novel workflow** we're designing.

---

## 4. MCP Servers for Kanban/Project Management

**tokrepo search found no dedicated Kanban MCP servers.** The native Hermes Kanban tools are the best integration point.

---

## 5. Key Patterns to Incorporate

| Pattern | Source | Application |
|---------|--------|-------------|
| **7-stage pipeline** | AgentFlow | Our 6 issues map to: Triage → Research → Build → Review → Test → Integrate → Done |
| **Conflict-aware scheduling** | AgentFlow | Check if Kanban tasks touch same files |
| **Adversarial review** | AgentFlow | Reviewer must find 3 things wrong before passing |
| **Atomic claims** | Agent Kanban | Hermes Kanban already has this via dispatcher |
| **Stale detection** | Agent Kanban | Flag tasks inactive >2h |
| **Cost tracking** | AgentFlow | Track tokens per Kanban task |
| **Spec drift detection** | AgentFlow | Hash task descriptions, detect changes mid-sprint |
| **Auto-decomposition** | Hermes Native | Already supported via `auto_decompose` config |
| **Dependency graph** | Hermes Native | Already supported via `kanban_link` |
