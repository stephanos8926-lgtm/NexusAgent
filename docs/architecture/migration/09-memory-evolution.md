# Phase 8 — Memory Evolution

## Objective

Separate memory into distinct layers with clear trust boundaries.

## Memory Layers

```
┌─────────────────────────────────────┐
│        Working Memory               │
│  Current execution context          │
│  Ephemeral — lost on completion     │
├─────────────────────────────────────┤
│        Episodic Memory              │
│  Historical events and sessions     │
│  Append-only — preserved forever    │
├─────────────────────────────────────┤
│        Semantic Memory              │
│  Stable facts about the world       │
│  Curated — verified before写入      │
├─────────────────────────────────────┤
│        Procedural Memory            │
│  Skills and reusable procedures     │
│  Evolved — updated through use      │
└─────────────────────────────────────┘
```

## Layer Responsibilities

| Layer | Data | Duration | Trust |
|-------|------|----------|-------|
| **Working** | Current objective, tool results, intermediate state | Session lifetime | High (system-owned) |
| **Episodic** | Session transcripts, events, decisions | Permanent (append-only) | Medium (auto-extracted) |
| **Semantic** | User facts, project knowledge, architecture decisions | Permanent (curated) | High (verified) |
| **Procedural** | Skills, workflows, automation scripts | Persistent (evolved) | Medium (agent-generated) |

## Requirements

Every memory item requires:

- **source** — which agent/session created it
- **confidence** — how reliable it is (0.0–1.0)
- **authority** — what trust level the source had
- **timestamp** — when it was observed

## Implementation Steps

### Step 1 — Layer separation

Refactor the current `HybridMemoryManager` into four distinct storage backends, each with its own schema and retention policy.

### Step 2 — Trust-aware ingestion

Memory extraction must respect the `TrustLevel` of the content being extracted. Low-trust content cannot create high-trust memories.

### Step 3 — Source provenance

Every memory item is tagged with its source identity and authority level. Memories from external/MCP tools have lower default authority.

### Step 4 — Confidence scoring

Auto-extracted memories start with a configurable minimum confidence. Memories can be promoted to higher confidence through confirmation or repeated observation.

## Completion Criteria

- [ ] Memory cannot be poisoned silently (low-trust content cannot create high-trust memories)
- [ ] Each memory layer is independently queryable
- [ ] Source provenance is preserved for every memory item
- [ ] Confidence scoring prevents untrusted information from polluting semantic knowledge