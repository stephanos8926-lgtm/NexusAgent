# Architectural Specification & ADR: Phase 9 Memory Evolution

## Context & Problem Statement
The legacy memory system used a single unified memory store (`HybridMemoryManager` backed by `FileMemory` and `HybridMemoryIndex`), which had no security boundaries. Low-trust content (such as unverified external tool responses or direct user prompt injects) could be memorized and contaminate semantic knowledge.

## Proposed Design (ADR)
We adopt a **4-layer Memory taxonomy**:
- **Working Memory**: Session-lifetime, ephemeral, system-owned (high trust).
- **Episodic Memory**: Append-only historical event/session transcripts.
- **Semantic Memory**: Curated project/factual knowledge. Restricted to `TRUSTED` authority sources and confidence `>= 0.6`.
- **Procedural Memory**: Skills, workflows, and automation procedures.

### Trust & Confidence Rules
1. **Trust-aware Ingestion**: Any write to `SemanticMemoryBackend` from content with an authority level below `TrustLevel.TRUSTED` is rejected to prevent poisoning.
2. **Confidence-aware Promotion**: If an `EPISODIC` memory's confidence reaches `>= 0.9` and has a `TRUSTED` authority, it is automatically promoted (copied) to the `SEMANTIC` layer.
3. **Repeated Observations**: When a memory is observed again (detected via token-overlap Jaccard similarity `>= 0.7`), its confidence is incremented by `+0.15` up to a maximum of `1.0`.

## Architecture Details
- The new components reside under `src/nexusagent/memory/`.
- `LayerMemoryManager` acts as the coordinator across the four file-backed layers under `<workspace_dir>/.nexusagent/layers/`.
- `HybridMemoryManager` is refactored internally to instantiate `LayerMemoryManager` and route entries dynamically on `remember()`.
