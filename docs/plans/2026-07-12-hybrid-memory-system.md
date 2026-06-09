# Hybrid Memory System — Implementation Plan

> **For Hermes:** Use `subagent-driven-development` skill. Tasks 1 and 2 are independent — dispatch in parallel. Task 3 depends on both. Task 4 depends on Task 3.

**Goal:** Replace the hash-based embedding in `memory.py` with a hybrid file + vector memory system. Files are the canonical source of truth (human-readable, git-trackable). SQLite FTS5 + sqlite-vec is the derived index (machine recall). Hybrid search merges both with union semantics.

**Architecture:**
```
workspace/
  MEMORY.md              ← index (pointers only, ≤200 lines / 25KB)
  memory/
    YYYY-MM-DD.md        ← daily log (narrative + ## Retain section)
  bank/                  ← curated typed memory
    world.md             ← objective facts
    experience.md        ← what the agent did
    opinions.md          ← preferences + confidence scores
    entities/
      project.md
      steven.md
  .memory/
    index.sqlite         ← derived: FTS5 + sqlite-vec (auto-rebuildable)
```

**Embedding provider chain:** Gemini API → local all-MiniLM-L6-v2 → OpenRouter

---

## Task 1: File-Based Memory Layer

**Objective:** Create the file-based memory system with MEMORY.md index, daily logs, bank/ directory, and YAML frontmatter.

**Files:**
- Create: `src/nexusagent/memory_files.py`
- Test: `tests/test_memory_files.py`

### Step 1: Write failing test

```python
# tests/test_memory_files.py
import pytest
import tempfile
import os
from pathlib import Path
from nexusagent.memory_files import FileMemory, MemoryEntryType

@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d)

def test_create_workspace(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()
    assert (Path(tmp_workspace) / "MEMORY.md").exists()
    assert (Path(tmp_workspace) / "memory").exists()
    assert (Path(tmp_workspace) / "bank").exists()

def test_write_and_read_entry(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()
    
    entry_id = fm.write_entry(
        content="The auth module uses JWT tokens",
        entry_type=MemoryEntryType.WORLD,
        description="Auth uses JWT",
        entities=["auth", "jwt"],
    )
    
    # Should create a topic file
    topic_files = list(Path(tmp_workspace).glob("bank/*.md"))
    assert len(topic_files) >= 1
    
    # MEMORY.md should have a pointer
    mem_md = (Path(tmp_workspace) / "MEMORY.md").read_text()
    assert "JWT" in mem_md or "auth" in mem_md

def test_daily_log(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()
    
    fm.append_daily_log("Worked on memory system today")
    fm.append_daily_log("## Retain\n- W: Implemented hybrid memory with FTS5 + sqlite-vec")
    
    daily_files = list((Path(tmp_workspace) / "memory").glob("*.md"))
    assert len(daily_files) >= 1

def test_memory_index_truncation(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()
    
    # Write 250 entries (over the 200 line limit)
    for i in range(250):
        fm.write_entry(f"Entry {i}", MemoryEntryType.WORLD, f"Entry {i}")
    
    mem_md = (Path(tmp_workspace) / "MEMORY.md").read_text()
    lines = mem_md.strip().split("\n")
    # Should be truncated to ~200 lines
    assert len(lines) <= 210  # small buffer for header

def test_frontmatter_format(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()
    
    fm.write_entry("Test content", MemoryEntryType.OPINION, "Test opinion", 
                   confidence=0.8, entities=["test"])
    
    topic_files = list(Path(tmp_workspace).glob("bank/*.md"))
    content = topic_files[0].read_text()
    assert "---" in content  # YAML frontmatter
    assert "type: opinion" in content
    assert "confidence: 0.8" in content
```

### Step 2: Run test to verify failure
```bash
cd /home/sysop/Workspaces/NexusAgent && python -m pytest tests/test_memory_files.py -v
```
Expected: FAIL — module not found

### Step 3: Implement `memory_files.py`

```python
# src/nexusagent/memory_files.py
"""
File-based memory layer — canonical source of truth.

Memory layout:
  MEMORY.md              ← index (pointers only, ≤200 lines / 25KB)
  memory/YYYY-MM-DD.md   ← daily log (narrative + ## Retain)
  bank/                  ← curated typed memory pages
    world.md, experience.md, opinions.md, entities/*.md

Each topic file has YAML frontmatter:
  ---
  name: short-name
  description: one-line description (used by search/LLM selection)
  type: world|experience|opinion|observation
  confidence: 0.0-1.0 (opinions only)
  entities: [name1, name2]
  created: ISO-date
  ---

Design principles:
- Files are canonical. The SQLite index is derived and rebuildable.
- MEMORY.md is an index, NOT a store. Never put memory bodies in it.
- Daily logs use ## Retain sections with typed, self-contained bullets.
- Scoped writes: each session can only write to its own workspace.
"""
import logging
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

MEMORY_INDEX_MAX_LINES = 200
MEMORY_INDEX_MAX_BYTES = 25_000  # 25KB


class MemoryEntryType(StrEnum):
    WORLD = "world"           # Objective facts
    EXPERIENCE = "experience"  # What the agent did
    OPINION = "opinion"        # Preferences + confidence
    OBSERVATION = "observation"  # Summary/generated


class FileMemory:
    """File-based memory — canonical source of truth."""
    
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)
        self.memory_dir = self.workspace / "memory"
        self.bank_dir = self.workspace / "bank"
        self.entities_dir = self.bank_dir / "entities"
        self.index_file = self.workspace / "MEMORY.md"
    
    def initialize(self):
        """Create the memory directory structure if it doesn't exist."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.bank_dir.mkdir(parents=True, exist_ok=True)
        self.entities_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.index_file.exists():
            self.index_file.write_text(
                "# Memory Index\n\n"
                "This file is an index of memory entries. Do not edit manually — "
                "use memory_write() to add entries.\n\n"
                "## Entries\n"
            )
    
    def write_entry(
        self,
        content: str,
        entry_type: MemoryEntryType,
        description: str,
        confidence: float | None = None,
        entities: list[str] | None = None,
    ) -> str:
        """Write a memory entry to a topic file and update the index.
        
        Returns the path of the topic file.
        """
        # Generate a filename from the description
        slug = re.sub(r"[^a-z0-9]+", "-", description.lower())[:40].strip("-")
        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        filename = f"{slug}-{timestamp}.md"
        filepath = self.bank_dir / filename
        
        # Build YAML frontmatter
        frontmatter = {
            "name": description[:50],
            "description": description[:100],
            "type": entry_type.value,
            "created": datetime.now(ISO).isoformat(),
        }
        if confidence is not None:
            frontmatter["confidence"] = round(confidence, 2)
        if entities:
            frontmatter["entities"] = entities
        
        # Write topic file
        file_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{content}\n"
        
        # If file exists, append; otherwise create
        if filepath.exists():
            with open(filepath, "a") as f:
                f.write(f"\n---\n\n{content}\n")
        else:
            filepath.write_text(file_content)
        
        # Update index with a one-line pointer
        self._add_index_entry(description, filename, entry_type)
        
        # Update entity pages if entities specified
        if entities:
            for entity in entities:
                self._update_entity(entity, content, entry_type)
        
        return str(filepath)
    
    def _add_index_entry(self, description: str, filename: str, entry_type: MemoryEntryType):
        """Add a one-line pointer to MEMORY.md."""
        line = f"- [{entry_type.value[0].upper()}] {description} → bank/{filename}\n"
        
        content = self.index_file.read_text() if self.index_file.exists() else ""
        lines = content.split("\n")
        
        # Find the "## Entries" section
        entries_start = 0
        for i, l in enumerate(lines):
            if l.strip() == "## Entries":
                entries_start = i + 1
                break
        
        # Insert after the Entries header
        lines.insert(entries_start, line.rstrip())
        
        # Enforce truncation
        if len(lines) > MEMORY_INDEX_MAX_LINES:
            lines = lines[:MEMORY_INDEX_MAX_LINES]
            lines.append(f"\n⚠ Index truncated at {MEMORY_INDEX_MAX_LINES} lines. "
                        f"Consolidate entries or move detail to topic files.")
        
        # Enforce byte limit
        content = "\n".join(lines)
        if len(content.encode()) > MEMORY_INDEX_MAX_BYTES:
            # Truncate at last newline before limit
            truncated = content.encode()[:MEMORY_INDEX_MAX_BYTES]
            last_nl = truncated.rfind(b"\n")
            content = truncated[:last_nl].decode("utf-8", errors="ignore")
            content += f"\n⚠ Index truncated to {MEMORY_INDEX_MAX_BYTES} bytes."
        
        self.index_file.write_text(content)
    
    def _update_entity(self, entity: str, content: str, entry_type: MemoryEntryType):
        """Update an entity page with a new mention."""
        entity_slug = re.sub(r"[^a-z0-9]+", "-", entity.lower())[:30].strip("-")
        entity_file = self.entities_dir / f"{entity_slug}.md"
        
        entry = f"- [{entry_type.value[0].upper()}] {content[:100]}\n"
        
        if entity_file.exists():
            existing = entity_file.read_text()
            # Append after frontmatter
            parts = existing.split("\n---\n", 2)
            if len(parts) >= 2:
                entity_file.write_text(
                    parts[0] + "\n---\n" + parts[1] + entry
                )
            else:
                entity_file.write_text(existing + entry)
        else:
            frontmatter = {
                "name": entity,
                "type": "entity",
                "created": datetime.now(UTC).isoformat(),
            }
            entity_file.write_text(
                f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n"
                f"# {entity}\n\n{entry}"
            )
    
    def append_daily_log(self, content: str):
        """Append to today's daily log."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        log_file = self.memory_dir / f"{today}.md"
        
        timestamp = datetime.now(UTC).strftime("%H:%M")
        entry = f"\n### {timestamp}\n{content}\n"
        
        if log_file.exists():
            with open(log_file, "a") as f:
                f.write(entry)
        else:
            log_file.write_text(
                f"# {today}\n\n### Session Start\n{content}\n"
            )
    
    def get_index_entries(self) -> list[dict]:
        """Parse MEMORY.md and return list of index entries."""
        if not self.index_file.exists():
            return []
        
        content = self.index_file.read_text()
        entries = []
        
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- ["):
                # Parse: - [W] description → bank/filename.md
                match = re.match(r"- \[(\w)\] (.+) → (.+)", line)
                if match:
                    entries.append({
                        "type": match.group(1),
                        "description": match.group(2).strip(),
                        "file": match.group(3).strip(),
                    })
        
        return entries
    
    def read_topic_file(self, filename: str) -> str | None:
        """Read a topic file from the bank/ directory."""
        filepath = self.bank_dir / filename
        if filepath.exists():
            return filepath.read_text()
        return None
    
    def get_daily_logs(self, days: int = 2) -> list[dict]:
        """Get daily logs for the last N days (today + yesterday by default)."""
        from datetime import timedelta
        
        logs = []
        for i in range(days):
            date = (datetime.now(UTC) - timedelta(days=i)).strftime("%Y-%m-%d")
            log_file = self.memory_dir / f"{date}.md"
            if log_file.exists():
                content = log_file.read_text()
                # Extract ## Retain section if present
                retain = ""
                if "## Retain" in content:
                    parts = content.split("## Retain")
                    if len(parts) > 1:
                        retain = parts[1].strip()
                
                logs.append({
                    "date": date,
                    "content": content,
                    "retain": retain,
                })
        
        return logs
    
    def list_all_files(self) -> list[str]:
        """List all memory files (bank/ + memory/)."""
        files = []
        if self.bank_dir.exists():
            files.extend(str(f.relative_to(self.workspace)) for f in self.bank_dir.rglob("*.md"))
        if self.memory_dir.exists():
            files.extend(str(f.relative_to(self.workspace)) for f in self.memory_dir.glob("*.md"))
        return files
```

### Step 4: Run test to verify pass
```bash
python -m pytest tests/test_memory_files.py -v
```
Expected: PASS

### Step 5: Commit
```bash
git add src/nexusagent/memory_files.py tests/test_memory_files.py
git commit -m "feat(memory): add file-based memory layer with MEMORY.md index"
```

---

## Task 2: Hybrid Search Index

**Objective:** Build the derived SQLite index with FTS5 + sqlite-vec, hybrid union merge, and file watching.

**Files:**
- Create: `src/nexusagent/memory_index.py`
- Test: `tests/test_memory_index.py`

### Step 1: Write failing test

```python
# tests/test_memory_index.py
import pytest
import tempfile
import os
from pathlib import Path
from nexusagent.memory_index import HybridMemoryIndex

@pytest.fixture
def tmp_index_dir():
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d)

@pytest.fixture
def populated_index(tmp_index_dir):
    """Create an index with some test data."""
    idx = HybridMemoryIndex(tmp_index_dir)
    
    # Write some test files
    workspace = Path(tmp_index_dir)
    (workspace / "bank").mkdir(exist_ok=True)
    (workspace / "bank" / "auth.md").write_text(
        "---\nname: Auth System\ndescription: Authentication uses JWT tokens\ntype: world\n---\n\n"
        "The authentication module uses JWT tokens for session management."
    )
    (workspace / "bank" / "testing.md").write_text(
        "---\nname: Testing\ndescription: We use pytest for testing\ntype: opinion\nconfidence: 0.9\n---\n\n"
        "We use pytest with xdist for parallel test execution."
    )
    
    # Index the files
    idx.index_file("bank/auth.md")
    idx.index_file("bank/testing.md")
    
    return idx

@pytest.mark.asyncio
async def test_keyword_search(populated_index):
    results = await populated_index.search("pytest", max_results=5)
    assert len(results) >= 1
    assert any("pytest" in r["content"].lower() for r in results)

@pytest.mark.asyncio
async def test_semantic_search(populated_index):
    # "authentication" should match "auth" semantically
    results = await populated_index.search("authentication", max_results=5)
    assert len(results) >= 1

@pytest.mark.asyncio
async def test_hybrid_merges_results(populated_index):
    results = await populated_index.search("auth tokens", max_results=5)
    # Should get results from both keyword and vector
    assert len(results) >= 1

def test_citation_format(populated_index):
    results = populated_index.search_sync("pytest", max_results=5)
    for r in results:
        assert "file" in r
        assert "content" in r
        assert "score" in r

def test_rebuild_index(tmp_index_dir):
    idx = HybridMemoryIndex(tmp_index_dir)
    workspace = Path(tmp_index_dir)
    (workspace / "bank").mkdir(exist_ok=True)
    (workspace / "bank" / "test.md").write_text("Test content about Python")
    
    idx.index_file("bank/test.md")
    idx.rebuild()
    
    results = idx.search_sync("Python", max_results=5)
    assert len(results) >= 1
```

### Step 2: Run test to verify failure
```bash
python -m pytest tests/test_memory_index.py -v
```
Expected: FAIL — module not found

### Step 3: Implement `memory_index.py`

```python
# src/nexusagent/memory_index.py
"""
Hybrid memory search index — derived from file-based memory.

Uses SQLite FTS5 (keyword) + sqlite-vec (semantic) with union merge.
The index is always rebuildable from the files — files are canonical.

Search flow:
1. Embed query → vector
2. Run FTS5 keyword search (BM25)
3. Run sqlite-vec similarity search
4. Union merge with weighted scores (70% vector, 30% keyword)
5. Return top N with citations (file + line numbers)
"""
import logging
import sqlite3
import struct
from pathlib import Path
from typing import Any

import sqlite_vec

from nexusagent.config import settings

logger = logging.getLogger(__name__)

EMBED_DIM = 768  # Gemini embedding-001 dimension
CHUNK_SIZE = 400  # tokens per chunk
CHUNK_OVERLAP = 80  # overlap between chunks
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
CANDIDATE_MULTIPLIER = 4  # over-fetch factor


class EmbeddingProvider:
    """Tiered embedding provider: Gemini → local → OpenRouter."""
    
    def __init__(self):
        self._local_model = None
    
    async def embed(self, text: str) -> list[float]:
        """Get embedding vector with fallback chain."""
        # Try Gemini first
        try:
            return await self._embed_gemini(text)
        except Exception as e:
            logger.warning(f"Gemini embedding failed: {e}, trying local")
        
        # Fall back to local model
        try:
            return await self._embed_local(text)
        except Exception as e:
            logger.warning(f"Local embedding failed: {e}")
        
        # Last resort: hash-based (always works, low quality)
        return self._embed_hash(text)
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        import asyncio
        return await asyncio.gather(*[self.embed(t) for t in texts])
    
    async def _embed_gemini(self, text: str) -> list[float]:
        """Use Gemini embedding API."""
        import google.generativeai as genai
        
        api_key = getattr(settings, 'gemini_api_key', None) or __import__('os').environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("No Gemini API key configured")
        
        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
        )
        return result['embedding']
    
    async def _embed_local(self, text: str) -> list[float]:
        """Use local sentence-transformers model."""
        if self._local_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                raise ImportError("sentence-transformers not installed")
        
        import asyncio
        loop = asyncio.get_running_loop()
        vec = await loop.run_in_executor(
            None, lambda: self._local_model.encode(text, normalize_embeddings=True)
        )
        return vec.tolist()
    
    def _embed_hash(self, text: str) -> list[float]:
        """Fallback: deterministic hash-based embedding (low quality, always works)."""
        import hashlib
        import math
        
        vec = [0.0] * EMBED_DIM
        for i in range(0, len(text), 64):
            chunk = text[i:i+64]
            h = hashlib.sha256(chunk.encode()).digest()
            for j in range(min(EMBED_DIM, len(h))):
                vec[j] += struct.unpack("b", bytes([h[j]]))[0] / 128.0
        
        mag = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x / mag for x in vec]


def _vec_to_blob(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _blob_to_vec(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


class HybridMemoryIndex:
    """SQLite-based hybrid search index (FTS5 + sqlite-vec)."""
    
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)
        self.db_path = self.workspace / ".memory" / "index.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = EmbeddingProvider()
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    line_start INTEGER,
                    line_end INTEGER,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    indexed_at TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    content,
                    id UNINDEXED,
                    file_path UNINDEXED
                )
            """)
            
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
                    id TEXT PRIMARY KEY,
                    embedding float[{EMBED_DIM}]
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_meta (
                    file_path TEXT PRIMARY KEY,
                    mtime REAL,
                    hash TEXT,
                    last_indexed TEXT
                )
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    def index_file(self, relative_path: str):
        """Index a file: chunk it, embed chunks, store in DB."""
        filepath = self.workspace / relative_path
        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return
        
        content = filepath.read_text()
        
        # Remove YAML frontmatter for indexing
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]
        
        # Chunk the content
        chunks = self._chunk_text(content)
        
        conn = sqlite3.connect(str(self.db_path))
        try:
            # Delete old chunks for this file
            conn.execute("DELETE FROM chunks WHERE file_path = ?", (relative_path,))
            conn.execute("DELETE FROM chunks_fts WHERE file_path = ?", (relative_path,))
            
            # Note: sqlite-vec doesn't support DELETE easily, so we use REPLACE
            import uuid
            now = __import__('datetime').datetime.now(__import__('datetime').UTC).isoformat()
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{relative_path}:{i}:{uuid.uuid4().hex[:8]}"
                
                # Get embedding
                try:
                    import asyncio
                    vec = asyncio.get_running_loop().run_until_complete(
                        self.embedder.embed(chunk["content"])
                    )
                    vec_blob = _vec_to_blob(vec)
                except Exception as e:
                    logger.warning(f"Embedding failed for chunk: {e}")
                    vec_blob = None
                
                conn.execute(
                    "INSERT INTO chunks (id, file_path, line_start, line_end, content, embedding, indexed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (chunk_id, relative_path, chunk["start"], chunk["end"], 
                     chunk["content"], vec_blob, now)
                )
                
                conn.execute(
                    "INSERT INTO chunks_fts (id, content, file_path) VALUES (?, ?, ?)",
                    (chunk_id, chunk["content"], relative_path)
                )
                
                if vec_blob:
                    try:
                        conn.execute(
                            "INSERT OR REPLACE INTO chunks_vec (id, embedding) VALUES (?, ?)",
                            (chunk_id, vec_blob)
                        )
                    except Exception as e:
                        logger.warning(f"Vector insert failed: {e}")
            
            # Update file meta
            import hashlib
            file_hash = hashlib.md5(filepath.read_bytes()).hexdigest()
            conn.execute(
                "INSERT OR REPLACE INTO file_meta (file_path, mtime, hash, last_indexed) VALUES (?, ?, ?, ?)",
                (relative_path, filepath.stat().st_mtime, file_hash, now)
            )
            
            conn.commit()
        finally:
            conn.close()
    
    def _chunk_text(self, text: str) -> list[dict]:
        """Split text into overlapping chunks."""
        lines = text.split("\n")
        chunks = []
        current_chunk = []
        current_start = 0
        line_num = 0
        
        for line in lines:
            current_chunk.append(line)
            line_num += 1
            
            if len("\n".join(current_chunk)) >= CHUNK_SIZE * 4:  # ~4 chars per token
                chunks.append({
                    "content": "\n".join(current_chunk),
                    "start": current_start,
                    "end": line_num,
                })
                # Keep overlap
                overlap_lines = max(1, CHUNK_OVERLAP // 50)
                current_chunk = current_chunk[-overlap_lines:]
                current_start = line_num - overlap_lines
        
        if current_chunk:
            chunks.append({
                "content": "\n".join(current_chunk),
                "start": current_start,
                "end": line_num,
            })
        
        return chunks
    
    async def search(self, query: str, max_results: int = 6, min_score: float = 0.1) -> list[dict]:
        """Hybrid search: keyword + vector with union merge."""
        import asyncio
        
        # Get query embedding
        query_vec = await self.embedder.embed(query)
        
        # Run both searches
        keyword_results = await asyncio.get_running_loop().run_in_executor(
            None, self._search_keyword, query, max_results * CANDIDATE_MULTIPLIER
        )
        vector_results = await asyncio.get_running_loop().run_in_executor(
            None, self._search_vector, query_vec, max_results * CANDIDATE_MULTIPLIER
        )
        
        # Merge
        merged = self._merge_results(keyword_results, vector_results, max_results, min_score)
        return merged
    
    def search_sync(self, query: str, max_results: int = 6) -> list[dict]:
        """Synchronous search (uses hash embedding fallback)."""
        query_vec = self.embedder._embed_hash(query)
        keyword_results = self._search_keyword(query, max_results * CANDIDATE_MULTIPLIER)
        vector_results = self._search_vector(query_vec, max_results * CANDIDATE_MULTIPLIER)
        return self._merge_results(keyword_results, vector_results, max_results, 0.0)
    
    def _search_keyword(self, query: str, limit: int) -> list[dict]:
        """FTS5 keyword search."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            # Build FTS5 query (AND logic for tokens)
            tokens = query.split()
            fts_query = " AND ".join(f'"{t}"' for t in tokens if len(t) > 1)
            
            rows = conn.execute(
                """SELECT id, file_path, content, rank 
                   FROM chunks_fts 
                   WHERE chunks_fts MATCH ? 
                   ORDER BY rank 
                   LIMIT ?""",
                (fts_query, limit)
            ).fetchall()
            
            return [{"id": r[0], "file": r[1], "content": r[2], "rank": r[3]} for r in rows]
        except Exception as e:
            logger.warning(f"Keyword search failed: {e}")
            return []
        finally:
            conn.close()
    
    def _search_vector(self, query_vec: list[float], limit: int) -> list[dict]:
        """sqlite-vec similarity search."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            
            vec_blob = _vec_to_blob(query_vec)
            rows = conn.execute(
                """SELECT c.id, c.file_path, c.content, 
                          1.0 / (1.0 + v.distance) as similarity
                   FROM chunks_vec v
                   JOIN chunks c ON c.id = v.id
                   WHERE v.embedding MATCH ?
                   ORDER BY v.distance
                   LIMIT ?""",
                (vec_blob, limit)
            ).fetchall()
            
            return [{"id": r[0], "file": r[1], "content": r[2], "similarity": r[3]} for r in rows]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []
        finally:
            conn.close()
    
    def _merge_results(
        self, 
        keyword_results: list[dict], 
        vector_results: list[dict], 
        max_results: int,
        min_score: float,
    ) -> list[dict]:
        """Union merge with weighted scoring."""
        by_id: dict[str, dict] = {}
        
        # Add vector results
        for r in vector_results:
            by_id[r["id"]] = {
                "id": r["id"],
                "file": r["file"],
                "content": r["content"][:200],  # truncate for context
                "vector_score": r.get("similarity", 0),
                "keyword_score": 0.0,
            }
        
        # Merge keyword results
        for r in keyword_results:
            # Convert BM25 rank to score (rank 0 → 1.0, rank 1 → 0.5, etc.)
            rank = r.get("rank", 999)
            kw_score = 1.0 / (1.0 + abs(rank)) if isinstance(rank, (int, float)) else 0.0
            
            if r["id"] in by_id:
                by_id[r["id"]]["keyword_score"] = kw_score
            else:
                by_id[r["id"]] = {
                    "id": r["id"],
                    "file": r["file"],
                    "content": r["content"][:200],
                    "vector_score": 0.0,
                    "keyword_score": kw_score,
                }
        
        # Compute weighted score
        merged = []
        for entry in by_id.values():
            score = VECTOR_WEIGHT * entry["vector_score"] + KEYWORD_WEIGHT * entry["keyword_score"]
            if score >= min_score:
                merged.append({
                    "file": entry["file"],
                    "content": entry["content"],
                    "score": round(score, 4),
                    "vector_score": round(entry["vector_score"], 4),
                    "keyword_score": round(entry["keyword_score"], 4),
                })
        
        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged[:max_results]
    
    def rebuild(self):
        """Rebuild the entire index from files."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM chunks_fts")
            conn.execute("DELETE FROM chunks_vec")
            conn.execute("DELETE FROM file_meta")
            conn.commit()
        finally:
            conn.close()
        
        # Re-index all files
        for pattern in ["bank/**/*.md", "memory/**/*.md"]:
            for filepath in self.workspace.glob(pattern):
                self.index_file(str(filepath.relative_to(self.workspace)))
        
        logger.info(f"Rebuilt index from {len(list(self.workspace.glob('**/*.md')))} files")
```

### Step 4: Run test to verify pass
```bash
python -m pytest tests/test_memory_index.py -v
```
Expected: PASS

### Step 5: Commit
```bash
git add src/nexusagent/memory_index.py tests/test_memory_index.py
git commit -m "feat(memory): add hybrid search index (FTS5 + sqlite-vec) with union merge"
```

---

## Task 3: Memory Tools + Integration

**Objective:** Wire the file layer and index together, register `memory_search`/`memory_get`/`memory_write` tools, and integrate with the session system.

**Files:**
- Modify: `src/nexusagent/memory.py` — integrate FileMemory + HybridMemoryIndex
- Modify: `src/nexusagent/tools/register_all.py` — add memory tools
- Modify: `src/nexusagent/session.py` — add memory flush before compaction
- Test: `tests/test_memory_tools.py`

### Implementation Notes

1. **MemoryManager** gets a `workspace_dir` parameter. It creates both `FileMemory` and `HybridMemoryIndex` in that directory.

2. **Session** gets a `memory_dir` (defaults to `~/.nexusagent/sessions/{session_id}/memory`). On session start, it loads the MEMORY.md index into context. On session end, it writes a daily log entry.

3. **Three tools:**
   - `memory_search(query, max_results=6)` → calls `HybridMemoryIndex.search()`, returns results with citations
   - `memory_get(path, offset, limit)` → reads a specific file from the memory directory
   - `memory_write(content, type, description)` → writes to file + triggers re-index

4. **Pre-compaction flush:** Before any context compaction, the session runs a silent turn that prompts the agent to save important context to memory files.

### Commit
```bash
git add src/nexusagent/memory.py src/nexusagent/tools/register_all.py src/nexusagent/session.py tests/test_memory_tools.py
git commit -m "feat(memory): integrate file+index layer, add memory_search/get/write tools"
```

---

## Task 4: Context Compaction Pipeline

**Objective:** Implement the 5-layer graduated compaction system.

**Files:**
- Create: `src/nexusagent/compaction.py`
- Modify: `src/nexusagent/session.py` — wire compaction into the agent loop
- Test: `tests/test_compaction.py`

### Compaction Layers (cheapest → most expensive)

1. **Tool result clearing** — Clear old tool result content, keep structure
2. **Microcompact** — Remove cached tool results via cache_edits
3. **Context collapse** — Read-time projection (non-destructive)
4. **Autocompact** — LLM summarizes conversation (lossy, last resort)
5. **Emergency truncation** — Drop oldest messages to fit budget

### Trigger
- Check token usage before each model call
- Trigger at 75% of context window (not 95% — early is better)
- Pre-compaction: run memory flush turn first

### Commit
```bash
git add src/nexusagent/compaction.py src/nexusagent/session.py tests/test_compaction.py
git commit -m "feat(compaction): add 5-layer graduated context compaction pipeline"
```

---

## Verification

After all tasks:
```bash
python -m pytest tests/ -q
ruff check src/ tests/
ruff format src/ tests/
```

Expected: All existing 101 tests pass + new memory tests pass.
```
