# tests/core/test_dag.py
"""Unit tests for Phase 6 DAG structures, validation, and topological sorting."""

from __future__ import annotations

import pytest

from nexusagent.core.dag import DAG, DAGEdge, DAGNode, DAGValidationError


def test_valid_dag_topological_sort() -> None:
    """Verify topological sorting on a valid DAG."""
    n1 = DAGNode(node_id="n1", objective="Research architecture")
    n2 = DAGNode(node_id="n2", objective="Implement core modules", dependencies=["n1"])
    n3 = DAGNode(node_id="n3", objective="Create documentation", dependencies=["n1"])
    n4 = DAGNode(node_id="n4", objective="Verify whole application", dependencies=["n2", "n3"])

    dag = DAG(
        graph_id="test-g1",
        nodes=[n1, n2, n3, n4],
    )

    dag.validate_graph()
    order = dag.topological_sort()

    assert order[0] == "n1"
    assert set(order[1:3]) == {"n2", "n3"}
    assert order[3] == "n4"


def test_dag_with_explicit_edges() -> None:
    """Verify validation and topological sorting when dependencies are defined via edges."""
    n1 = DAGNode(node_id="n1", objective="Step 1")
    n2 = DAGNode(node_id="n2", objective="Step 2")
    n3 = DAGNode(node_id="n3", objective="Step 3")

    # n2 depends on n1, n3 depends on n2
    edge1 = DAGEdge(from_node_id="n1", to_node_id="n2")
    edge2 = DAGEdge(from_node_id="n2", to_node_id="n3")

    dag = DAG(
        graph_id="test-edges",
        nodes=[n1, n2, n3],
        edges=[edge1, edge2],
    )

    dag.validate_graph()
    order = dag.topological_sort()
    assert order == ["n1", "n2", "n3"]


def test_circular_dependency_fails() -> None:
    """Verify cycle detection raises DAGValidationError."""
    n1 = DAGNode(node_id="n1", objective="Step 1", dependencies=["n3"])
    n2 = DAGNode(node_id="n2", objective="Step 2", dependencies=["n1"])
    n3 = DAGNode(node_id="n3", objective="Step 3", dependencies=["n2"])

    dag = DAG(
        graph_id="cycle-g",
        nodes=[n1, n2, n3],
    )

    with pytest.raises(DAGValidationError, match="Circular dependency detected"):
        dag.validate_graph()

    with pytest.raises(DAGValidationError, match="Circular dependency detected"):
        dag.topological_sort()


def test_self_dependency_fails() -> None:
    """Verify self-dependency is rejected."""
    n1 = DAGNode(node_id="n1", objective="Step 1", dependencies=["n1"])

    dag = DAG(
        graph_id="self-dep",
        nodes=[n1],
    )

    with pytest.raises(DAGValidationError, match="cannot depend on itself"):
        dag.validate_graph()


def test_missing_dependency_fails() -> None:
    """Verify referencing non-existent dependency node raises DAGValidationError."""
    n1 = DAGNode(node_id="n1", objective="Step 1", dependencies=["ghost-node"])

    dag = DAG(
        graph_id="ghost-dep",
        nodes=[n1],
    )

    with pytest.raises(DAGValidationError, match="references non-existent dependency"):
        dag.validate_graph()


def test_orphaned_nodes_fails() -> None:
    """Verify disconnected components / orphan nodes raise validation errors."""
    n1 = DAGNode(node_id="n1", objective="Step 1")
    n2 = DAGNode(node_id="n2", objective="Step 2", dependencies=["n1"])
    # Disconnected node
    n3 = DAGNode(node_id="n3", objective="Isolated Step")

    dag = DAG(
        graph_id="orphan-g",
        nodes=[n1, n2, n3],
    )

    with pytest.raises(DAGValidationError, match="Orphaned/disconnected nodes detected"):
        dag.validate_graph()


def test_empty_dag_fails() -> None:
    """Verify empty DAG raises validation errors."""
    dag = DAG(graph_id="empty", nodes=[])
    with pytest.raises(DAGValidationError, match="at least one node"):
        dag.validate_graph()
