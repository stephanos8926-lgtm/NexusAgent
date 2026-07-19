# Typed Trust Boundaries — Specification v1

## Problem
`agent.py:31-65` defines `_detect_injection()` + `sanitize_tool_output()` but `sanitize_tool_output` is **never called** — dead code. Zero runtime prompt injection defense in production.

The current dead code uses regex detection (6 patterns) which is:
1. Trivially bypassed (whitespace, homoglyphs)
2. Only checks tool output (not MCP descs, @file injections, memory)
3. Advisory text marker (LLM still reads adversarial content)

## Design
Three-layer defense:

### Layer 1 — Provenance Tagging
```python
class TrustLevel(IntEnum):
    BUILTIN = 5       # System prompt
    VALIDATED = 4     # @file injection content
    MEMORY = 3        # Self-written memory
    TOOL_INTERNAL = 2 # Internal tool output
    TOOL_EXTERNAL = 1 # MCP/external tool output
    UNTRUSTED = 0     # Unvalidated external
```

### Layer 2 — TrustedContent dataclass
```python
@dataclass(frozen=True)
class TrustedContent:
    text: str
    trust: TrustLevel
    provenance: str
    anomaly_score: float
    injected_at: float
```

### Layer 3 — AnomalyScorer (replaces regex)
Multi-signal: pattern (40%), entropy (30%), length (20%), instruction density (10%).

## Files to modify
1. `src/nexusagent/core/trust.py` — NEW: TrustLevel, TrustedContent, AnomalyScorer (~120 lines)
2. `src/nexusagent/core/agent.py` — Replace detect/sanitize with annotate_tool_output
3. `src/nexusagent/core/session/session.py` — Wire annotate into tool result path; inject trust schema into system prompt
4. `src/nexusagent/infrastructure/prompt_loader.py` — Anomaly scoring on @file injection
5. `src/nexusagent/tools/registry/types.py` — Add trust/provenance fields to ToolInfo
6. `src/nexusagent/tools/register_all.py` — Tag MCP tools with TOOL_EXTERNAL
7. `src/nexusagent/infrastructure/config.py` — Add enabled/anomaly_threshold fields

## Non-goals
- Structural message channel in deepagents (can't change framework bus)
- Per-tool anomaly history persistence
- Active blocking of tool output
- Cross-turn correlation
