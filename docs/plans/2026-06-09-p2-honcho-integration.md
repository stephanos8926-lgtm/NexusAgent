# P2: Integrate Honcho as NexusAgent Memory Backend

> **For Hermes:** Use `subagent-driven-development` skill. Read this entire plan before dispatching.

**Goal:** Make NexusAgent use Honcho (already running at `http://rapidwebs-01:8000`) as its persistent memory backend, replacing the file-based system we built. Honcho provides server-side persistence, dialectic reasoning, cross-session continuity, and 5 memory tools.

**Current State:**
- Honcho server: `http://rapidwebs-01:8000` (healthy, `/health` returns `{"status":"ok"}`)
- Hermes config: `memory.provider: honcho` already active
- `~/.hermes/honcho.json`: configured with `baseUrl`, `workspace: "hermes"`, `peerName: "sysop"`, `aiPeer: "hermes"`
- NexusAgent has: file-based memory (memory_files.py), hybrid search index (memory_index.py), compaction (compaction.py)

**Architecture Change:**
```
BEFORE: NexusAgent → file-based memory (MEMORY.md + bank/ + sqlite index)
AFTER:  NexusAgent → Honcho API (server-side) + local file cache for offline
```

**Honcho API (v3):**
- `POST /v3/workspaces/{workspace_id}/peers/{peer_id}/sessions` — create/get session
- `POST /v3/workspaces/{workspace_id}/sessions/{session_id}/messages` — store messages
- `POST /v3/workspaces/{workspace_id}/sessions/{session_id}/search` — semantic search
- `POST /v3/workspaces/{workspace_id}/peers/{peer_id}/chat` — dialectic reasoning
- `POST /v3/workspaces/{workspace_id}/peers/{peer_id}/representation` — get peer model
- `GET  /v3/workspaces/{workspace_id}/peers/{peer_id}/card` — peer card (key facts)
- `POST /v3/workspaces/{workspace_id}/conclusions` — create conclusion
- `POST /v3/workspaces/{workspace_id}/conclusions/list` — list conclusions

**Integration Plan:**

## Task 1: Create Honcho Client (TDD)

**Objective:** Create `src/nexusagent/honcho_client.py` — async HTTP client for Honcho API.

**Files:**
- Create: `src/nexusagent/honcho_client.py`
- Test: `tests/test_honcho_client.py`

**Interface:**
```python
class HonchoClient:
    def __init__(self, base_url: str, workspace: str, peer_name: str, ai_peer: str):
        ...
    
    async def get_or_create_session(self, session_id: str) -> dict:
        """Get or create a Honcho session."""
        
    async def store_message(self, session_id: str, role: str, content: str) -> dict:
        """Store a message in the session."""
        
    async def search(self, session_id: str, query: str, max_results: int = 6) -> list[dict]:
        """Semantic search over session context."""
        
    async def get_context(self, session_id: str) -> dict:
        """Get full session context (summary, representation, card, messages)."""
        
    async def get_peer_card(self, peer_id: str = "user") -> dict:
        """Get peer card (key facts)."""
        
    async def create_conclusion(self, conclusion: str) -> dict:
        """Create a persistent conclusion."""
        
    async def list_conclusions(self, limit: int = 20) -> list[dict]:
        """List conclusions."""
```

**TDD Steps:**
1. Write failing test for `get_or_create_session`
2. Run test → FAIL
3. Implement `HonchoClient` with `httpx.AsyncClient`
4. Run test → PASS
5. Repeat for each method

## Task 2: Create Honcho Memory Provider (TDD)

**Objective:** Create `src/nexusagent/honcho_memory.py` — replaces `HybridMemoryManager` with Honcho-backed storage.

**Files:**
- Create: `src/nexusagent/honcho_memory.py`
- Test: `tests/test_honcho_memory.py`

**Interface:**
```python
class HonchoMemoryProvider:
    def __init__(self, client: HonchoClient, session_id: str):
        ...
    
    async def remember(self, content: str, metadata: dict = None) -> str:
        """Store a message + extract conclusion if important."""
        
    async def recall(self, query: str, max_results: int = 6) -> list[dict]:
        """Search Honcho for relevant context."""
        
    async def get_memory_context(self, query: str, max_results: int = 5) -> str:
        """Format Honcho context for system prompt injection."""
        
    async def flush(self, session_summary: str):
        """Store session summary as conclusion."""
```

## Task 3: Wire Into Session (TDD)

**Objective:** Replace `HybridMemoryManager` with `HonchoMemoryProvider` in `session.py`.

**Files:**
- Modify: `src/nexusagent/session.py`
- Test: Update `tests/test_session_memory.py`

**Changes:**
1. Import `HonchoClient` and `HonchoMemoryProvider`
2. In `Session.__init__`, create `HonchoClient` from config
3. Replace `self.hybrid_memory` with `self.honcho_memory`
4. Update `send()` to use async `honcho_memory` methods
5. Update `pre_compaction_flush()` to use Honcho

## Task 4: Update Config

**Objective:** Add Honcho config to `AgentConfig` and load from `honcho.json`.

**Files:**
- Modify: `src/nexusagent/config.py`
- Modify: `src/nexusagent/session.py` (config loading)

**Config to add:**
```python
class HonchoConfig(BaseModel):
    base_url: str = "http://localhost:8000"
    workspace: str = "hermes"
    peer_name: str = "sysop"
    ai_peer: str = "hermes"
    enabled: bool = True
```

## Execution Order

**Phase 1 (Parallel):**
- Task 1: HonchoClient (independent)
- Task 4: Config updates (independent)

**Phase 2 (Sequential):**
- Task 2: HonchoMemoryProvider (depends on Task 1)
- Task 3: Session wiring (depends on Tasks 2, 4)

**Phase 3:**
- Full integration test
- Run full suite
- Commit

## Verification

```bash
python3 -m pytest tests/ -q
ruff check src/ tests/
ruff format src/ tests/
```

Expected: 155+ tests passing (151 existing + 4+ new Honcho tests).
