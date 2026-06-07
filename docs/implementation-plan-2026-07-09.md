# NexusAgent — Implementation Plan: Dev Agent, Tiered Prompts, Multi-Agent Parallelism

> **Date**: July 9, 2026
> **Author**: OWL (Lucien) for Steven Page
> **Based on**: Competitive analysis (2026-06-06), SWE-Bench Pro research, AgentSpawn paper (arXiv:2602.07072), Claude Code prompt architecture leak, promptloom library patterns

---

## Executive Summary

Three workstreams, prioritized by dependency order:

1. **Real Software Dev Capability** (Weeks 1-3) — Agent needs proper tooling, execution environment, and scaffolding to write/test/debug real code
2. **Tiered Prompt System** (Weeks 2-4) — Modular prompt architecture: base → user → sub-agent, with cache-aware composition
3. **Multi-Agent Parallelism** (Weeks 4-7) — Dynamic sub-agent spawning with memory slicing, coherence protocols, and NATS-based coordination

Workstreams 1 and 2 can run in parallel. Workstream 3 depends on both.

---

## Workstream 1: Real Software Development Capability

### 1.1 What "Real Dev Capability" Means in 2026

Based on SWE-Bench Pro research, the gap between "demo agent" and "real dev agent" is **not the model — it's the harness**. Key findings:

- Frontier models score ~80% on SWE-Bench Verified (single-file, simple) but crater to 23% on SWE-Bench Pro (multi-file, cross-file dependencies)
- The #1 failure mode is **planning**: agents edit file A without checking consumers in file B
- The #2 failure mode is **context overflow**: agents forget what they read 10 tool calls ago
- The #3 failure mode is **compounding errors**: bad edit in A breaks test in B, agent "fixes" B by mutating assertions
- **Scaffolding patterns that recover 30-40% of the gap**: pre-edit consumer mapping, dual-agent judge, context compaction, state snapshot + rollback

### 1.2 Required Tool Upgrades

Current tools (`fs`, `shell`, `patch`, `research`) have been upgraded. Status:

| Tool | Status | Notes |
|---|---|---|
| `read_file` | ✅ Done | Line-range support (`offset`+`limit`), session read tracking |
| `write_file` | ✅ Done | Read-before-write safety for existing files |
| `edit_file` | ✅ New | Surgical line-range edit with old_text validation |
| `list_directory` | ✅ Done | Recursive + max_depth + glob pattern + exclude filters |
| `run_shell` | ✅ Done | Timeout, workdir, env vars |
| `run_shell_streaming` | ✅ New | Line-by-line streaming for long commands |
| `git_*` | ✅ New | status, diff, log, branch, show, stash, commit, checkout |
| `run_tests` | ✅ New | Auto-detects pytest/jest/maven/gradle/go/cargo |
| `search_code` | ✅ New | ripgrep-based with context lines |
| `find_symbol` | ✅ New | Multi-language symbol definition search |
| `find_references` | ✅ New | Find all references to a symbol |
| `apply_patch` | ⚠️ Exists | Uses patch-ng, could use line-range validation |

Still needed:

| Tool | Purpose | Priority |
|---|---|---|
| **`lsp_client`** | LSP-based code navigation (go-to-def, find-references, hover) | 🟡 High |
| **`debugger`** | pdb/node-debug integration | 🟡 High |
| **`docker`** | Containerized execution environments | 🟡 High |
| **`dependency_analyzer`** | Map imports, call graphs, type dependencies | 🟢 Nice |

### 1.3 Scaffolding Patterns to Implement

Based on SWE-Bench Pro analysis and AgentSpawn research:

**Pattern 1: Pre-Edit Planning (Consumer Mapping)**
Before any edit, the agent must:
1. Locate the symbol being changed
2. List every consumer (imports, call sites, tests)
3. Write a one-paragraph plan naming every file it will touch
4. Only then begin editing

This alone adds 4-8 points on SWE-Bench Pro.

**Pattern 2: Dual-Agent Judge**
- One model proposes the patch
- A second model (can be smaller/cheaper) judges it against the plan and tests before shipping
- This is responsible for most of the gap between Claude Code (55.4%) and Cursor (50.2%) on the same underlying model

**Pattern 3: Context Compaction**
Every 8-10 tool calls:
1. Summarize older tool output into compressed form
2. Keep last 2-3 raw
3. Re-inject the original task description
4. Without this, effective working memory degrades to the most recent 30K tokens

**Pattern 4: State Snapshot + Rollback**
Before any multi-file edit:
1. Snapshot current state (git stash or full diff)
2. If downstream tests break, roll back to snapshot
3. Try a different decomposition
4. Worth 5-15 points on Pro-difficulty tasks

### 1.4 Execution Environment

For real dev tasks, the agent needs an **isolated, containerized environment**:

```
┌─────────────────────────────────────────┐
│  Agent (NexusWorker)                    │
│  ┌───────────────────────────────────┐  │
│  │  Docker Container per Task         │  │
│  │  - Full repo checkout              │  │
│  │  - Language runtime + deps         │  │
│  │  - Test suite pre-installed        │  │
│  │  - Terminal + file system access   │  │
│  │  - Network for package installs    │  │
│  └───────────────────────────────────┘  │
│  - Agent edits files in container       │
│  - Runs tests in container              │
│  - Iterates until tests pass            │
│  - Returns final diff + test results    │
└─────────────────────────────────────────┘
```

This is the architecture used by SWE-Master (61.4% on SWE-Bench Verified) and OpenHands.

### 1.5 Implementation Steps

1. **Add `git` tool** — wrap git CLI with structured output
2. **Add `test_runner` tool** — detect test framework from repo, run with JSON output parsing
3. **Add `lsp_client` tool** — use python-lsp-server or typescript-language-server via stdio
4. **Implement pre-edit planning** — add to agent's system prompt as mandatory workflow step
5. **Implement dual-agent judge** — use smaller model (e.g., llama-3.1-8b) as judge
6. **Implement context compaction** — middleware in the agent loop that summarizes old tool output
7. **Implement state snapshot/rollback** — git-based snapshot before multi-file edits
8. **Add Docker execution environment** — container per task, managed by worker

---

## Workstream 2: Tiered Prompt System

### 2.1 Architecture

Based on Claude Code's leaked 7-layer architecture, promptloom patterns, and dynamic composition research:

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEM PROMPT (compiled)                  │
├─────────────────────────────────────────────────────────────┤
│  [CACHE BOUNDARY — everything above is globally cached]     │
│                                                             │
│  Layer 1: BASE (immutable, shipped with NexusAgent)         │
│  - Agent identity and role                                  │
│  - Core behavioral rules                                    │
│  - Tool definitions and usage patterns                      │
│  - Ecosystem overview (NATS, bus, worker, SDK)              │
│  - Security constraints and guardrails                      │
│                                                             │
│  Layer 2: USER (customizable, loaded from file)             │
│  - User's CLAUDE.md / NEXUS.md equivalent                   │
│  - Project-specific instructions                            │
│  - Coding style preferences                                 │
│  - Domain knowledge                                         │
│                                                             │
│  [CACHE BOUNDARY — everything below is session-specific]     │
│                                                             │
│  Layer 3: SUB-AGENT (role-specific, composed at spawn time) │
│  - Role definition (e.g., "test-writer", "code-reviewer")   │
│  - Task-specific instructions                               │
│  - Inherited skills from parent                             │
│  - Scope constraints (what this sub-agent can/cannot do)    │
│                                                             │
│  Layer 4: DYNAMIC (assembled per request)                   │
│  - Current date/time                                        │
│  - Git status                                               │
│  - Active session context                                   │
│  - Memory injection                                         │
│  - Previous error recovery context                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 File Structure

```
~/.nexusagent/
├── prompts/
│   ├── base.md              # Layer 1: shipped with NexusAgent
│   ├── user.md              # Layer 2: user's customizations (gitignored)
│   ├── user.md.example      # Layer 2: template
│   └── subagents/
│       ├── coder.md         # Sub-agent: general coding
│       ├── reviewer.md      # Sub-agent: code review
│       ├── tester.md        # Sub-agent: test writing
│       ├── debugger.md      # Sub-agent: debugging
│       └── researcher.md    # Sub-agent: research
└── memory/
    └── session_*.json       # Session memory (for dynamic layer)
```

### 2.3 Prompt Compiler

Implement a `PromptCompiler` class (inspired by promptloom):

```python
class PromptCompiler:
    def __init__(self):
        self.sections: list[PromptSection] = []
        self.cache_boundaries: list[int] = []
    
    def add_base(self, content: str):
        """Layer 1: immutable, globally cached"""
        self.sections.append(PromptSection(
            priority=10, content=content, cache_scope="global"
        ))
    
    def add_user(self, content: str):
        """Layer 2: user customizations, org-cached"""
        self.sections.append(PromptSection(
            priority=20, content=content, cache_scope="org"
        ))
    
    def add_subagent(self, role: str, content: str):
        """Layer 3: role-specific, session-specific"""
        self.sections.append(PromptSection(
            priority=30, content=content, cache_scope="session",
            role=role
        ))
    
    def add_dynamic(self, content: str):
        """Layer 4: per-request, never cached"""
        self.sections.append(PromptSection(
            priority=40, content=content, cache_scope=None
        ))
    
    def compile(self, context: dict) -> CompiledPrompt:
        """Assemble final prompt with cache boundaries"""
        # Sort by priority
        # Insert cache boundary markers
        # Apply token budget (drop lowest priority if over)
        # Return compiled prompt with cache annotations
        ...
```

### 2.4 User Prompt File Format (NEXUS.md)

```markdown
# NEXUS.md — User Customizations

## Coding Style
- Follow PEP 8 for Python
- Use type annotations everywhere
- Write docstrings for all public functions
- Prefer composition over inheritance

## Project Context
- This is a multi-agent orchestration framework
- NATS is the message bus (port 4222)
- SQLite is the persistence layer
- FastAPI serves the REST API

## Behavioral Preferences
- Be concise in responses
- Always run tests before declaring completion
- Ask before deleting files
- Use git branches for experimental changes

## Custom Tools
- `deploy`: Deploy to staging environment
- `benchmark`: Run performance benchmarks
```

### 2.5 Sub-Agent Prompt Templates

Each sub-agent role gets a focused prompt:

```markdown
# subagents/coder.md

You are a **coding specialist** sub-agent of NexusAgent.

## Your Role
- Write, modify, and refactor code
- Follow the pre-edit planning protocol (always map consumers before editing)
- Run tests after every change
- Keep changes minimal and focused

## Constraints
- You can ONLY modify files in the assigned working directory
- You MUST run tests before returning
- You MUST return a structured diff of all changes
- You CANNOT spawn further sub-agents (leaf agent)

## Output Format
Return a JSON object with:
- `status`: "success" | "partial" | "failed"
- `files_modified`: list of file paths
- `diff`: unified diff of all changes
- `test_results`: {passed: N, failed: N, output: string}
- `summary`: one-paragraph description of what was done
```

### 2.6 Implementation Steps

1. **Create `PromptCompiler` class** in `src/nexusagent/prompt_compiler.py`
2. **Write base prompt** (`prompts/base.md`) — identity, tools, ecosystem, security
3. **Create user prompt loader** — load `~/.nexusagent/prompts/user.md` or `./NEXUS.md`
4. **Create sub-agent prompt templates** — coder, reviewer, tester, debugger, researcher
5. **Integrate into agent loop** — compile prompt at session start, recompile dynamic layer each turn
6. **Add cache boundary markers** — for API-level prompt caching (Anthropic, OpenAI)
7. **Add token budget tracking** — drop lowest-priority sections if over budget

---

## Workstream 3: Multi-Agent Parallelism

### 3.1 Architecture

Based on AgentSpawn (arXiv:2602.07072) — the state of the art in dynamic multi-agent collaboration:

```
┌─────────────────────────────────────────────────────────────┐
│  Parent Agent (NexusWorker)                                 │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Spawn Controller                                    │    │
│  │  - Monitors runtime complexity metrics               │    │
│  │  - Decides WHEN to spawn (threshold δ=0.7)           │    │
│  │  - Decides WHAT specialist to spawn                  │    │
│  │  - Limits: max depth 3, max concurrent 4             │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                  │
│              ┌───────────┼───────────┐                      │
│              ▼           ▼           ▼                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ Child Agent 1│ │ Child Agent 2│ │ Child Agent 3│       │
│  │ (Coder)      │ │ (Tester)     │ │ (Reviewer)   │       │
│  │              │ │              │ │              │       │
│  │ NATS subject:│ │ NATS subject:│ │ NATS subject:│       │
│  │ nexus.sub.1  │ │ nexus.sub.2  │ │ nexus.sub.3  │       │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘       │
│         │                │                │                │
│         └────────────────┼────────────────┘                │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Resume Coordinator                                  │    │
│  │  - Collects results from all children                │    │
│  │  - Merges code changes (3-tier merge)                │    │
│  │  - Summarizes execution traces                       │    │
│  │  - Promotes successful skills to parent              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Coherence Manager                                   │    │
│  │  - Lock-free optimistic concurrency                  │    │
│  │  - Conflict detection (overlapping file edits)       │    │
│  │  - 3-tier resolution:                                │    │
│  │    1. Automatic merge (non-overlapping)              │    │
│  │    2. Semantic merge via LLM (intent-compatible)     │    │
│  │    3. Parent escalation (contradictory)              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 NATS Integration

Leverage existing NATS infrastructure:

```
Streams:
- nexus.tasks        → parent consumes, produces subtasks
- nexus.sub.{id}     → child-specific task stream
- nexus.results      → children publish results here
- nexus.coherence    → conflict detection/resolution messages

KV Stores:
- nexus.spawn.{id}   → spawn package (memory slice, skills, context)
- nexus.resume.{id}  → resume package (output, diffs, metrics)
```

### 3.3 Adaptive Spawning Policy

Monitor 5 runtime complexity metrics (from AgentSpawn):

| Metric | Weight | Description |
|---|---|---|
| **File Interdependency (If)** | 0.30 | How many files reference the symbol being modified |
| **Cyclomatic Complexity (Cc)** | 0.20 | Complexity of the code being modified |
| **Test Failure Cascade (Fc)** | 0.25 | Number of tests failing after edit |
| **Context Saturation (Oc)** | 0.15 | How full the context window is |
| **Model Uncertainty (Uc)** | 0.10 | Agent's self-reported uncertainty |

Spawn score = weighted sum. When score > δ (0.7), spawn a child specialist.

### 3.4 Memory Slicing

When spawning, transfer only relevant context (not everything):

```python
def compute_memory_slice(parent_memory, subtask) -> MemorySlice:
    """Select relevant episodic, semantic, and working memory items"""
    
    # Score each memory item by relevance to subtask
    for item in parent_memory.all_items():
        score = (
            0.3 * keyword_match(item, subtask) +
            0.3 * dependency_score(item, subtask) +
            0.2 * temporal_recency(item) +
            0.2 * semantic_similarity(item, subtask)
        )
        item.relevance = score
    
    # Keep items above threshold (target ~50% of parent memory)
    threshold = compute_threshold(parent_memory, target_ratio=0.5)
    slice = [item for item in parent_memory if item.relevance > threshold]
    
    return MemorySlice(
        episodic=slice.episodic,
        semantic=slice.semantic,
        working=slice.working,
        execution_context=parent_memory.current_context
    )
```

This reduces memory overhead by ~42% (from AgentSpawn results).

### 3.5 Spawn-Resume Protocol

```python
@dataclass
class SpawnPackage:
    """Parent → Child"""
    memory_slice: MemorySlice
    skills: list[Skill]
    execution_context: dict  # repo path, current file, pending changes
    task_spec: str
    complexity_metrics: dict
    timeout: int = 600  # 10 minutes

@dataclass
class ResumePackage:
    """Child → Parent"""
    status: str  # "success" | "partial" | "failed"
    task_output: str
    files_modified: list[str]
    diff: str
    test_results: dict
    execution_trace: list[dict]  # key decisions
    learned_skills: list[Skill]
    performance_metrics: dict
```

### 3.6 User-Facing API

Users should be able to spawn parallel agents via:

**CLI:**
```bash
# Spawn 3 parallel agents for different tasks
nexus spawn --count 3 --role coder --tasks "task1.md,task2.md,task3.md"

# Spawn with custom prompt
nexus spawn --role coder --prompt ./my-coder-prompt.md --task "Implement auth module"
```

**SDK:**
```python
from nexusagent import NexusSDK

sdk = NexusSDK()

# Spawn parallel agents
agents = sdk.spawn_parallel([
    {"role": "coder", "task": "Implement user authentication"},
    {"role": "tester", "task": "Write tests for auth module"},
    {"role": "reviewer", "task": "Review auth implementation"},
])

# Wait for all to complete
results = sdk.wait_for_all(agents)

# Or wait for any
result = sdk.wait_for_any(agents)
```

**REST API:**
```http
POST /api/v1/agents/spawn
{
  "role": "coder",
  "task": "Implement user authentication",
  "prompt_override": "...",
  "timeout": 600
}

GET /api/v1/agents/{agent_id}/status
GET /api/v1/agents/{agent_id}/results
DELETE /api/v1/agents/{agent_id}  # cancel
```

### 3.7 Implementation Steps

1. **Implement SpawnController** — complexity monitoring, spawn decisions
2. **Implement MemorySlicer** — relevance-scored memory transfer
3. **Implement ResumeCoordinator** — collect results, merge, summarize
4. **Implement CoherenceManager** — 3-tier conflict resolution
5. **Add NATS streams for sub-agents** — `nexus.sub.{id}`, `nexus.results`
6. **Implement Spawn-Resume protocol** — SpawnPackage/ResumePackage serialization
7. **Add user-facing spawn API** — CLI, SDK, REST endpoints
8. **Add sub-agent prompt templates** — integrate with Workstream 2
9. **Test with SWE-Bench tasks** — validate 34% improvement target

---

## Dependency Graph

```
Workstream 1 (Dev Capability) ──────┐
                                     ├──→ Workstream 3 (Multi-Agent)
Workstream 2 (Tiered Prompts) ──────┘
```

- WS1 and WS2 can run in parallel (different code areas)
- WS3 depends on both (needs tools + prompt system)
- WS1 items 1-3 (git, test_runner, lsp) are prerequisites for WS3
- WS2 items 1-4 (compiler, base, user, subagent templates) are prerequisites for WS3

---

## File Manifest

### New Files

| File | Purpose |
|---|---|
| `src/nexusagent/prompt_compiler.py` | Tiered prompt composition engine |
| `src/nexusagent/spawn_controller.py` | Adaptive spawning policy |
| `src/nexusagent/memory_slicer.py` | Relevance-scored memory transfer |
| `src/nexusagent/resume_coordinator.py` | Result collection + merge |
| `src/nexusagent/coherence_manager.py` | Conflict detection + resolution |
| `src/nexusagent/tools/git.py` | Git operations tool |
| `src/nexusagent/tools/test_runner.py` | Test execution tool |
| `src/nexusagent/tools/lsp_client.py` | LSP-based code navigation |
| `src/nexusagent/tools/code_search.py` | AST-aware code search |
| `src/nexusagent/tools/debugger.py` | Debugger integration |
| `src/nexusagent/tools/docker.py` | Container management |
| `src/nexusagent/subagent.py` | Sub-agent base class |
| `prompts/base.md` | Base system prompt (Layer 1) |
| `prompts/user.md.example` | User prompt template (Layer 2) |
| `prompts/subagents/coder.md` | Coder sub-agent prompt |
| `prompts/subagents/reviewer.md` | Reviewer sub-agent prompt |
| `prompts/subagents/tester.md` | Tester sub-agent prompt |
| `prompts/subagents/debugger.md` | Debugger sub-agent prompt |
| `prompts/subagents/researcher.md` | Researcher sub-agent prompt |

### Modified Files

| File | Changes |
|---|---|
| `src/nexusagent/agent.py` | Integrate prompt compiler, add planning patterns |
| `src/nexusagent/worker.py` | Add spawn/resume logic, sub-agent management |
| `src/nexusagent/orchestration.py` | Add multi-agent orchestration |
| `src/nexusagent/server.py` | Add spawn API endpoints |
| `src/nexusagent/cli.py` | Add `nexus spawn` command |
| `src/nexusagent/sdk.py` | Add `spawn_parallel()` methods |
| `src/nexusagent/models.py` | Add SpawnPackage/ResumePackage models |
| `src/nexusagent/config.py` | Add spawn/prompt configuration |

---

## Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| SWE-Bench Verified | > 40% resolve rate | Run evaluation suite |
| SWE-Bench Pro | > 15% resolve rate | Run evaluation suite |
| Multi-file task completion | 30%+ improvement over single-agent | Internal benchmark |
| Sub-agent spawn latency | < 5 seconds | Time from decision to child active |
| Memory overhead reduction | 40%+ vs full context transfer | Token count comparison |
| Conflict resolution rate | 70%+ auto-resolved | Coherence manager metrics |
| Prompt compilation time | < 100ms | Benchmark |
