# Plan: Phase 9 Memory Evolution (4-Layer Taxonomy)

## Objective
Implement Phase 9 Memory Evolution by separating memory into four distinct layers (Working, Episodic, Semantic, Procedural) with strict trust boundaries and confidence-aware auto-promotion.

## Approved High-Level Steps
1. **Design and Audit**: Complete a 7-way audit on security, performance, and correctness.
2. **Document Specs & Implementation**: Produce architectural and micro-implementation documentation under `docs/specs/` and `docs/plans/`.
3. **Integrate LayerMemoryManager into HybridMemoryManager**: Refactor `src/nexusagent/memory/hybrid_memory.py` to transparently route entries to `LayerMemoryManager` while fully preserving legacy public APIs.
4. **Implement Confidence Scoring & Auto-Promotion**: Write token-overlap Jaccard similarity confidence increment (+0.15) and EPISODIC -> SEMANTIC auto-promotion on confidence >= 0.9 and TRUSTED authority under `src/nexusagent/memory/layer_manager.py`.
5. **Comprehensive Testing**: Write tests for trust-aware ingestion, Jaccard scaling, and auto-promotion, and run the suite to ensure 100% green tests.

## 7-Way Audit Synthesis
- **Forward Audit**: End-to-end trace from message ingestion to layer routing works perfectly.
- **Reverse Audit**: Validated that unverified content trying to poison `SemanticMemoryBackend` is rejected immediately.
- **Adversarial Audit**: Jaccard similarity attacks on external MCP tools are blocked from promotion because promotion is gated by the `TRUSTED` authority requirement.
- **Red-team Audit**: Validated that item IDs are random/safe to prevent path-traversal file writes.
- **Top-down Audit**: Legacy callers (`SessionBase`, `compaction.py`, etc.) are guaranteed to remain fully functional because the public API of `HybridMemoryManager` is untouched.
- **Bottom-up Audit**: Direct filesystem checks verify individual layer folder structure.
- **Completeness Audit**: Double-checked all four completion criteria from `09-memory-evolution.md`. All criteria are thoroughly addressed.
