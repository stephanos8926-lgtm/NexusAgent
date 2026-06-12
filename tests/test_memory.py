"""Tests for the scoped memory system."""

import math
import struct
from pathlib import Path

import pytest

from nexusagent.memory.memory import MemoryManager, MemoryScope


# ---------------------------------------------------------------------------
# DRY-consolidation tests — verify memory.py imports from memory.index
# instead of duplicating constants and functions.
# ---------------------------------------------------------------------------


def test_embed_dim_imported_not_duplicated():
    """EMBED_DIM must be imported from memory.index, not hardcoded."""
    import nexusagent.memory.memory as mem_mod
    import nexusagent.memory.index as idx_mod

    # The value must match
    assert mem_mod.EMBED_DIM == idx_mod.EMBED_DIM == 3072


def test_embed_to_blob_shared():
    """_embed_to_blob must be the same function object as memory.index._vec_to_blob."""
    from nexusagent.memory.memory import _embed_to_blob
    from nexusagent.memory.index import _vec_to_blob

    # Must be the same function (imported, not duplicated)
    assert _embed_to_blob is _vec_to_blob

    # Verify it works
    vec = [1.0, 2.0, 3.0]
    blob = _embed_to_blob(vec)
    assert len(blob) == len(vec) * 4  # float32 = 4 bytes
    unpacked = struct.unpack(f"{len(vec)}f", blob)
    assert unpacked == (1.0, 2.0, 3.0)


def test_hash_embed_uses_shared_helpers():
    """_hash_embed must use the shared EMBED_DIM and struct (not local import)."""
    import inspect
    import nexusagent.memory.memory as mem_mod

    source = inspect.getsource(mem_mod._hash_embed)

    # Should NOT have local "import struct as _struct"
    assert "import struct as _struct" not in source, (
        "_hash_embed should use module-level struct import, not local alias"
    )

    # Should produce correct dimension
    vec = mem_mod._hash_embed("test")
    assert len(vec) == mem_mod.EMBED_DIM

    # Should be unit-normalized
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 0.01, f"Vector not unit-normalized: norm={norm}"


@pytest.fixture
async def tmp_db(tmp_path: Path):
    """Provide a temporary DB path and ensure cleanup."""
    db_path = str(tmp_path / "test_memory.db")
    yield db_path


async def test_remember_and_recall(tmp_db: str):
    """Create a memory, remember something, recall it."""
    mgr = MemoryManager(db_path=tmp_db)
    mem = await mgr.create("agent-1", MemoryScope.ISOLATED)

    item_id = await mem.remember("The project uses Python 3.13 and pytest", {"topic": "tech"})
    assert item_id

    results = await mem.recall("What Python version?", limit=5)
    assert len(results) >= 1
    assert "Python" in results[0].content
    assert results[0].metadata.get("topic") == "tech"

    await mgr.close()


async def test_fork_isolated(tmp_db: str):
    """Parent + child isolated: they cannot see each other's memories."""
    mgr = MemoryManager(db_path=tmp_db)
    parent = await mgr.create("parent", MemoryScope.ISOLATED)
    child = await parent.fork(MemoryScope.ISOLATED)

    await parent.remember("parent-only secret")
    await child.remember("child-only secret")

    # Parent cannot see child's memory
    parent_results = await parent.recall("child-only secret", limit=10)
    assert all("child-only" not in r.content for r in parent_results)

    # Child cannot see parent's memory
    child_results = await child.recall("parent-only secret", limit=10)
    assert all("parent-only" not in r.content for r in child_results)

    # But each sees their own
    parent_own = await parent.recall("parent-only secret", limit=10)
    assert any("parent-only" in r.content for r in parent_own)

    child_own = await child.recall("child-only secret", limit=10)
    assert any("child-only" in r.content for r in child_own)

    await mgr.close()


async def test_fork_scoped_reads_parent(tmp_db: str):
    """Parent + scoped child: child can read parent's memories."""
    mgr = MemoryManager(db_path=tmp_db)
    parent = await mgr.create("parent", MemoryScope.ISOLATED)
    child = await parent.fork(MemoryScope.SCOPED)

    await parent.remember("important context from parent")

    # Child should be able to recall parent's memory
    results = await child.recall("important context", limit=10)
    assert len(results) >= 1
    assert any("important context from parent" in r.content for r in results)

    # But child's own writes don't appear in parent
    await child.remember("child note")
    parent_results = await parent.recall("child note", limit=10)
    assert all("child note" not in r.content for r in parent_results)

    await mgr.close()


async def test_merge_selective(tmp_db: str):
    """Parent + child: merge child into parent; parent sees child's memories."""
    mgr = MemoryManager(db_path=tmp_db)
    parent = await mgr.create("parent", MemoryScope.ISOLATED)
    child = await parent.fork(MemoryScope.ISOLATED)

    await child.remember("discovered fact A")
    await child.remember("discovered fact B")
    # Also add something to parent
    await parent.remember("parent fact")

    moved = await parent.merge(child, strategy="selective")
    assert moved == 2

    # Parent should now see child's facts via recall
    results = await parent.recall("discovered fact", limit=10)
    contents = [r.content for r in results]
    assert any("discovered fact A" in c for c in contents)
    assert any("discovered fact B" in c for c in contents)

    await mgr.close()


async def test_fork_does_not_leak_connection(tmp_db: str):
    """fork() should share the parent's connection, not create a new one."""
    mgr = MemoryManager(db_path=tmp_db)
    parent = await mgr.create("parent-leak-test", MemoryScope.ISOLATED)
    await parent.remember("Parent memory", {})

    child = await parent.fork(MemoryScope.ISOLATED)
    await child.remember("Child memory", {})

    # Child should be able to recall its own memories
    child_results = await child.recall("memory", limit=10)
    assert len(child_results) >= 1

    # Parent should not see child's memories (isolated)
    parent_results = await parent.recall("memory", limit=10)
    assert any("Parent" in r.content for r in parent_results)
    assert not any("Child" in r.content for r in parent_results)

    await mgr.close()
