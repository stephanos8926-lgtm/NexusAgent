from threading import Thread
from time import sleep
from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from src.nexusagent.tools.registry.core import register_tool, registry
from src.nexusagent.tools.registry.types import ToolInfo


@pytest.fixture(autouse=True)
def clear_registry_for_tests():
    # Ensure a clean registry for each test
    with registry._lock:
        registry._pending.clear()
        registry._snapshots.clear()
        registry._latest_version = 0


def test_toolinfo_is_frozen():
    with pytest.raises(AttributeError, match="cannot assign to field 'name'"):
        info = ToolInfo(
            name="test",
            func=MagicMock(),
            description="desc",
            parameters={},
            example="ex",
            category="cat",
        )
        info.name = "new_name"


def test_toolregistry_initial_state():
    assert registry.version == 0
    assert len(registry.current) == 0


def test_toolregistry_register_and_freeze():
    @register_tool(name="tool1", description="desc1", parameters={}, example="ex1")
    def tool1():
        pass

    assert "tool1" in registry._pending
    # Before first freeze, current is a live view of pending
    assert "tool1" in registry.current

    version = registry.freeze()
    assert version == 1
    assert registry.version == 1
    assert "tool1" in registry.current
    assert isinstance(registry.current, MappingProxyType)


def test_toolregistry_snapshot_immutability():
    @register_tool(name="tool2", description="desc2", parameters={}, example="ex2")
    def tool2():
        pass

    registry.freeze()
    snapshot1 = registry.current

    @register_tool(name="tool3", description="desc3", parameters={}, example="ex3")
    def tool3():
        pass

    registry.freeze()
    snapshot2 = registry.current

    assert "tool3" not in snapshot1  # snapshot1 should be immutable
    assert "tool2" in snapshot2
    assert "tool3" in snapshot2


def test_toolregistry_concurrent_rlock_safety():
    results = []

    def register_and_freeze(thread_id):
        for i in range(5):

            @register_tool(
                name=f"thread{thread_id}_tool{i}",
                description="desc",
                parameters={},
                example="ex",
            )
            def _tool():
                pass

            version = registry.freeze()
            results.append((thread_id, version, len(registry.current)))
            sleep(0.001)  # Yield to other threads

    threads = []
    for i in range(3):
        t = Thread(target=register_and_freeze, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Verify that versions are monotonic and no data was lost
    versions = [r[1] for r in results]
    assert all(versions[i] <= versions[i + 1] for i in range(len(versions) - 1))
    assert registry.version == 15  # 3 threads * 5 freezes each
    assert len(registry.current) == 15  # All tools should be present in final snapshot


def test_toolregistry_prune():
    @register_tool(name="toolA", description="descA", parameters={}, example="exA")
    def toola():
        pass

    registry.freeze()  # version 1

    @register_tool(name="toolB", description="descB", parameters={}, example="exB")
    def toolb():
        pass

    registry.freeze()  # version 2

    @register_tool(name="toolC", description="descC", parameters={}, example="exC")
    def toolc():
        pass

    registry.freeze()  # version 3

    assert registry.get_snapshot(1) is not None
    assert registry.get_snapshot(2) is not None
    assert registry.get_snapshot(3) is not None

    registry.prune(1)  # Prune versions <= 1
    assert registry.get_snapshot(1) is None
    assert registry.get_snapshot(2) is not None
    assert registry.get_snapshot(3) is not None

    registry.prune(2)  # Prune versions <= 2
    assert registry.get_snapshot(1) is None
    assert registry.get_snapshot(2) is None
    assert registry.get_snapshot(3) is not None


def test_toolregistry_get_snapshot_graceful_handling():
    assert registry.get_snapshot() is None  # Before first freeze, it's None

    registry.freeze()  # Freeze to create version 1
    assert isinstance(registry.get_snapshot(), MappingProxyType)  # Now it's a MappingProxyType
    assert registry.get_snapshot(999) is None  # Non-existent version still None


def test_toolregistry_registryproxy_typeerror_on_mutation():
    @register_tool(name="toolX", description="descX", parameters={}, example="exX")
    def toolx():
        pass

    registry.freeze()
    proxy = registry.current

    with pytest.raises(TypeError, match="does not support item assignment"):
        proxy["new_tool"] = ToolInfo(
            name="new_tool",
            func=MagicMock(),
            description="new",
            parameters={},
            example="ex",
            category="cat",
        )

    with pytest.raises(TypeError, match="does not support item deletion"):
        del proxy["toolX"]


def test_toolregistry_register_idempotency():
    @register_tool(name="idem_tool", description="initial", parameters={}, example="ex")
    def idem_tool_v1():
        pass

    registry.freeze()
    assert registry.current["idem_tool"].description == "initial"

    @register_tool(name="idem_tool", description="updated", parameters={}, example="ex")
    def idem_tool_v2():
        pass

    registry.freeze()
    assert registry.current["idem_tool"].description == "updated"
