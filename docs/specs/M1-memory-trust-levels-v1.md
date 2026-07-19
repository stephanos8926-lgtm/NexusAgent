# M1 — Memory Trust Levels

**Goal:** Every memory item caries structured trust metadata: source, authority, confidence, expiration.
**Current state:** MemoryItem has `metadata: dict` (freeform). FileMemory frontmatter has optional `confidence`, `quality_score`, `ttl_hours/expires_at`, `source_session_id`, `derived_from`. None are first-class or enforced.

---

## Changes to MemoryItem (memory_item.py)

```python
from enum import StrEnum
from datetime import datetime
from pydantic import BaseModel, Field

class MemorySource(StrEnum):
    """Origin of a memory entry."""
    USER_DIRECT = "user_direct"           # User explicitly told the agent
    USER_INFERRED = "user_inferred"       # Agent inferred from user behavior
    WORKSPACE_FILE = "workspace_file"     # README, code, docs
    TOOL_OUTPUT = "tool_output"           # read_file, search, etc.
    MEMORY_INFERENCE = "memory_inference" # Dream cycle / extraction
    SYSTEM = "system"                     # Built-in / code defaults
    EXTERNAL = "external"                 # MCP tool, web search


class MemoryItem(BaseModel):
    id: str
    content: str
    metadata: dict = Field(default_factory=dict)

    # ── Trust fields (first-class) ──
    source: MemorySource = MemorySource.SYSTEM
    authority: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    expires_at: datetime | None = None

    created_at: str
    embedding: list[float] = Field(default_factory=list)
```

| Field | Meaning | Range | Set by |
|-------|---------|-------|--------|
| `source` | Where this fact came from | Enum | Registrar (calling code) |
| `authority` | Source's trustworthiness | 0.0-1.0 | Registrar — USER_DIRECT=0.9, WORKSPACE_FILE=0.7, TOOL_OUTPUT=0.6, MEMORY_INFERENCE=0.3 |
| `confidence` | Agent's certainty in correctness | 0.0-1.0 | Extractor / dream cycle / user correction signal |
| `expires_at` | When this entry becomes stale | ISO datetime or null | Registrar or configurable default per source type |

### Authority defaults

```python
_SOURCE_AUTHORITY: dict[MemorySource, float] = {
    MemorySource.USER_DIRECT: 0.95,       # "Steven said X" — highest
    MemorySource.USER_INFERRED: 0.70,     # Inferred from user patterns
    MemorySource.WORKSPACE_FILE: 0.80,    # README / code — factual but may be stale
    MemorySource.TOOL_OUTPUT: 0.60,       # Tool ran — correct at call time
    MemorySource.MEMORY_INFERENCE: 0.30,  # LLM-generated summary — minimum
    MemorySource.SYSTEM: 0.90,            # Hardcoded config / constants
    MemorySource.EXTERNAL: 0.40,          # Web / MCP — need verification
}
```

### Expiration defaults

| Source | Default TTL |
|--------|-------------|
| USER_DIRECT | None (never expires — persistent preference) |
| USER_INFERRED | 30 days |
| WORKSPACE_FILE | 7 days (code changes) |
| TOOL_OUTPUT | 1 day (stale quickly) |
| MEMORY_INFERENCE | 7 days |
| EXTERNAL | 1 day |

---

## Changes to FileMemory.write_entry (memory_files.py)

```python
def write_entry(
    self,
    content: str,
    entry_type: MemoryEntryType,
    description: str,
    source: MemorySource = MemorySource.SYSTEM,
    authority: float | None = None,       # Override default
    confidence: float | None = None,
    expires_at: str | None = None,        # ISO datetime or null
    # ... existing params ...
) -> str:
```

The frontmatter gains first-class fields:

```yaml
---
name: "Memory entry title"
description: "Short description"
type: observation
source: user_direct
authority: 0.95
confidence: 0.90
expires_at: null
created: 2026-07-14T12:00:00
quality_score: 0.85
---
Content here.
```

### Frontmatter changes

| Current | New | Status |
|---------|-----|--------|
| — | `source` | **Added** — MemorySource enum string |
| — | `authority` | **Added** — float 0.0-1.0 |
| `confidence` (optional) | `confidence` | **Promoted** — always present, defaults to 0.5 |
| `ttl_hours` + `expires_at` | `expires_at` | **Promoted** — first-class ISO datetime or null |

---

## Recall ranking changes (HybridMemoryManager.recall)

After hybrid search, apply trust-weighted re-ranking:

```python
async def recall(self, query, max_results=6, min_authority=0.0, ...):
    results = await self.index.search(query, max_results=fetch_count)

    # Trust-weighted re-ranking
    for r in results:
        # Read frontmatter for source/authority/confidence
        fm = self._read_frontmatter(r["file"])
        r["trust_score"] = (
            fm.get("authority", 0.5) * 0.4 +
            fm.get("confidence", 0.5) * 0.3 +
            r.get("score", 0.0) * 0.3       # Semantic relevance
        )

    # Filter by min authority
    results = [r for r in results if r["trust_score"] >= min_authority]

    results.sort(key=lambda r: r["trust_score"], reverse=True)
```

### Expiration enforcement

On `recall()`, entries with `expires_at` in the past are:
1. Still returned (don't silently delete)
2. Tagged with `stale: true` in the result
3. The calling session may choose to not inject them into context, or inject with a warning

```python
for r in results:
    expires_at = self._read_frontmatter(r["file"]).get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at) < datetime.now(UTC):
        r["stale"] = True
```

---

## Files to modify

| File | Change | ± Lines |
|------|--------|---------|
| `memory/memory_item.py` | Add `MemorySource` enum, add `source`/`authority`/`confidence`/`expires_at` fields to MemoryItem | +25 |
| `memory/memory_files.py` | Add `source`/`authority` params to `write_entry()`, promote confidence to first-class, add to frontmatter | +15 |
| `memory/hybrid_memory.py` | Add trust-weighted recall ranking, min_authority filter, expiration staleness tag | +25 |
| `memory/llm_extraction.py` | Tag inferred memories with `source=MEMORY_INFERENCE`, authority=0.3, confidence from LLM | +5 |
| `__init__.py` / compat shims | Export `MemorySource` | +2 |

## Security

- **Authority cannot be self-declared** — calling code sets it, not the memory content
- **Expiration is advisory** — stale memories are tagged, not deleted. Prevents data loss from bad TTLs
- **Source enum is registrar-enforced** — same pattern as TrustLevel in the injection defense spec

## Effort

- Implementation: ~0.5 day
- Tests: ~0.5 day (recall ranking, expiration tagging, authority defaults)
- Risk: Low (additive fields, no behavioral change to existing recall without min_authority)
