# SPEC-007: RW_InferenceEngine Integration — Embeddings & Reranker Provider

**Status**: Draft  
**Author**: Lucien  
**Date**: 2026-07-30  
**Dependencies**: Phase 9 Memory Evolution (SPEC-001–006 complete), RW_InferenceEngine deployed on infra VM (port 8300)

---

## Executive Summary

Integrate **RW_InferenceEngine** (Rust/ONNX, port 8300 on infra VM) as a **configurable embedding provider** for NexusAgent's memory system, alongside existing Gemini and local fallbacks. Additionally, add **reranker model support** for hybrid search relevance scoring.

**Key principle**: Zero breaking changes. Gemini remains default; RW_IE is opt-in via config. User choice preserved.

---

## Current Architecture

### NexusAgent Embedding Chain (current)
```
embed(text) 
  → try Gemini (gemini-embedding-001, 3072-dim) 
    → fallback: local sentence-transformers (all-MiniLM-L6-v2, 384-dim → padded to 3072) 
      → fallback: hash-based (deterministic, low quality)
```

**File**: `src/nexusagent/memory/index/embeddings.py` — `EmbeddingProvider` class

### RW_InferenceEngine (existing)
- **Deployed**: infra VM (100.122.246.112), port 8300
- **Models**: 
  - Embedding: ONNX BERT model at `models/embedding/primary/model.onnx` — **384-dim** (hidden_size: 384, 12 layers)
  - Reranker: ONNX BERT-for-SequenceClassification at `models/reranker/primary/model.onnx` — **384-dim** (hidden_size: 384, 6 layers, cross-encoder)
  - Tokenizer: `models/embedding/primary/tokenizer.json` (BERT tokenizer, vocab 30522)
- **Endpoints** (from router/routes):
  - `POST /embed` — single/batch embedding
  - `POST /rerank` — rerank query + docs
  - `GET /health` — health check
- **Config**: `config/default.toml` (port 8300, model paths, thread pool)

---

## Design Requirements

### 1. Embedding Provider Abstraction
- New `EmbeddingProvider` trait/interface in `src/nexusagent/memory/index/embeddings.py`
- Pluggable providers: `GeminiProvider`, `LocalProvider`, `RWIEProvider`, `HashProvider`
- Config-driven selection: `embedding.provider = "gemini" | "local" | "rw_ie" | "hash"`

### 2. Dimension Compatibility
- Current `EMBED_DIM = 3072` (Gemini `gemini-embedding-001`)
- RW_IE embedding model dims: **384** (BERT, hidden_size: 384)
- **Strategy**: 
  - Store native dims (384 for RW_IE, 3072 for Gemini) — add `embedding_dim` column to vector index
  - Or: pad 384 → 3072 with config option (zeros)
  - **Recommendation**: Store native dims, make index dim-agnostic. Add `embedding_dim` column to `vector_chunks` table. This makes the system future-proof for any model.

### 3. Reranker Integration
- New `RerankerProvider` trait
- Hybrid search: `vector_search(query) → top_k → rerank(query, docs) → final top_k`
- Config: `search.rerank.enabled = true`, `search.rerank.provider = "rw_ie"`

### 4. Configuration Schema
```yaml
# config/nexusagent.yaml additions
embedding:
  provider: "gemini"  # "gemini" | "local" | "rw_ie" | "hash"
  rw_ie:
    base_url: "http://100.122.246.112:8300"  # infra VM
    timeout_secs: 30
    batch_size: 32
  local:
    model: "all-MiniLM-L6-v2"
  dims: 3072  # target dims (pad/truncate if provider differs)

search:
  rerank:
    enabled: false
    provider: "rw_ie"  # only rw_ie supports rerank currently
    top_k_before_rerank: 50
    top_k_after_rerank: 10
    rw_ie:
      base_url: "http://100.122.246.112:8300"
```

---

## Implementation Plan

### Phase 1: Provider Abstraction (Embeddings)
**Files to create/modify:**
1. `src/nexusagent/memory/index/embeddings.py` — Add `EmbeddingProvider` protocol + provider classes
2. `src/nexusagent/memory/index/__init__.py` — Export new providers
3. `src/nexusagent/infrastructure/config.py` — Add `EmbeddingConfig`, `RWIEEmbeddingConfig`
4. `config/nexusagent.yaml` — Add embedding config section

**Provider classes:**
```python
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dims(self) -> int: ...
    @property
    def name(self) -> str: ...

class RWIEProvider:
    def __init__(self, base_url: str, timeout: int, batch_size: int):
        self.base_url = base_url
        # HTTP client with connection pooling
    
    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/embed", json={"text": text})
            return resp.json()["embedding"]
```

### Phase 2: Reranker Abstraction
**Files:**
1. `src/nexusagent/memory/index/rerank.py` — New module
2. `src/nexusagent/memory/hybrid_memory.py` — Integrate rerank in search
3. Config additions

```python
class RerankerProvider(Protocol):
    async def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]: ...
    # Returns list of (doc_index, relevance_score)
```

### Phase 3: Hybrid Search Integration
- Modify `HybridMemoryManager.search()` to:
  1. Vector search → get top 50
  2. If rerank enabled → call reranker → re-score → top 10
  3. Combine with keyword search (RRF fusion)

### Phase 4: Configuration & Testing
- Add config validation
- Unit tests for each provider
- Integration test: end-to-end with RW_IE
- Dimension migration script (if dims change)

---

## API Contract (RW_InferenceEngine)

### POST /embed
```json
Request:
{
  "text": "string" | ["string", ...],
  "batch_size": 32
}

Response:
{
  "embeddings": [[float, ...], ...],
  "model": "embedding-model-name",
  "dimensions": 384
}
```

### POST /rerank
```json
Request:
{
  "query": "string",
  "documents": ["doc1", "doc2", ...],
  "top_k": 10
}

Response:
{
  "results": [
    {"index": 0, "score": 0.95, "document": "doc1"},
    {"index": 2, "score": 0.87, "document": "doc3"}
  ],
  "model": "reranker-model-name"
}
```

### GET /health
```json
Response:
{
  "status": "healthy",
  "models_loaded": ["embedding", "reranker"],
  "uptime_secs": 12345
}
```

---

## Dimension Handling Strategy

| Scenario | Action |
|----------|--------|
| RW_IE dims = 3072 | Direct use, no padding |
| RW_IE dims < 3072 (e.g., 384) | Option A: Pad to 3072 (zeros) — simple, wastes space<br>Option B: Store native dims, add `embedding_dim` column — clean, requires index migration<br>Option C: Project to 3072 via learned projection — complex |
| RW_IE dims > 3072 | Truncate or project down |

**Recommended**: **Option B** — Store native dims. Add `embedding_dim` to vector index schema. Makes system future-proof for any model.

---

## Migration Path

1. **Deploy RW_IE** on infra (already done ✅)
2. **Verify model dims** — check `models/embedding/primary/config.json`
3. **Add provider abstraction** (Phase 1)
4. **Add RWIEProvider** with HTTP client
5. **Add config schema** with `provider` selector
6. **Test with `provider: "rw_ie"`** in dev
7. **Add reranker** (Phase 2–3)
8. **Default stays "gemini"** — zero breaking changes
9. **Document** in AGENTS.md and CONFIG.md

---

## Open Questions

1. **What are RW_IE embedding model dimensions?** Need to check `models/embedding/primary/config.json`
2. **Reranker model type?** Cross-encoder? Bi-encoder? Affects API contract.
3. **Batch embedding support?** Current RW_IE `/embed` accepts array — confirm batch size limits.
4. **Authentication?** Currently open on infra VM Tailscale — add API — need API key for production?
5. **Model hot-reload?** RW_IE supports file watcher — how to trigger from NexusAgent config change?

---

## Acceptance Criteria

- [ ] `embedding.provider = "rw_ie"` works end-to-end
- [ ] Gemini remains default (`provider: "gemini"`)
- [ ] Local fallback still works (`provider: "local"`)
- [ ] Hash fallback still works (`provider: "hash"`)
- [ ] Reranker integrates into hybrid search (`search.rerank.enabled: true`)
- [ ] Dimension mismatch handled gracefully (pad/truncate/configurable)
- [ ] All existing tests pass
- [ ] New unit tests for RWIEProvider, RerankerProvider
- [ ] Integration test in CI (requires RW_IE running)
- [ ] Documentation updated (AGENTS.md, CONFIG.md, CONFIG.yaml.example)

---

## Estimated Effort

| Phase | Tasks | Est. Days |
|-------|-------|-----------|
| 1: Provider Abstraction | Interface, 4 providers, config, tests | 2 |
| 2: Reranker | Trait, RWIE impl, hybrid search integration | 2 |
| 3: Config & Migration | Schema, validation, dim handling, docs | 1 |
| **Total** | | **~5 days** |

---

## References

- RW_InferenceEngine: `/home/sysop/Workspaces/RW_InferenceEngine/`
- Current embeddings: `src/nexusagent/memory/index/embeddings.py`
- Hybrid memory: `src/nexusagent/memory/hybrid_memory.py`
- Config schema: `src/nexusagent/infrastructure/config.py`
- Phase 9 specs: `docs/specs/SPEC-001` through `SPEC-006`