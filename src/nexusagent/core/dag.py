# src/nexusagent/core/dag.py
"""Phase 6 — DAG Execution Engine Graph Model for NexusAgent.

Defines Directed Acyclic Graph (DAG) structures, schemas, and validation logic.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DAGValidationError(ValueError):
    """Raised when a DAG fails validation."""


class DAGNode(BaseModel):
    """A unit of execution within the DAG."""

    node_id: str = Field(description="Unique identifier for the execution node")
    task_id: str | None = Field(default=None, description="Reference to the parent task ID")
    objective: str = Field(description="Description of the required work")
    dependencies: list[str] = Field(default_factory=list, description="List of dependent node_ids")
    worker_type: str | None = Field(default=None, description="Required worker capability class")
    capabilities_required: list[str] | None = Field(default_factory=list, description="Required permissions")
    priority: int = Field(default=1, ge=1, le=5, description="Priority level of execution (1-5)")
    timeout: float = Field(default=1800.0, ge=0.0, description="Maximum execution duration in seconds")
    retries: int = Field(default=3, ge=0, description="Number of retries allowed on failure")
    verification_requirements: list[str] | None = Field(default_factory=list, description="Success verification criteria")
    payload: dict[str, Any] = Field(default_factory=dict, description="Generic metadata or task contract fields")

    @property
    def id(self) -> str:
        """Alias for node_id to support alternative interfaces."""
        return self.node_id

    @property
    def deps(self) -> list[str]:
        """Alias for dependencies."""
        return self.dependencies


class DAGEdge(BaseModel):
    """A directed dependency edge between two DAG nodes."""

    from_node_id: str = Field(description="The source node (must complete first)")
    to_node_id: str = Field(description="The destination node (depends on source)")
    predicate: str | None = Field(default=None, description="Optional conditional execution predicate")


class DAG(BaseModel):
    """The Directed Acyclic Graph containing nodes, edges, and execution state."""

    graph_id: str = Field(description="Unique identifier for the graph")
    nodes: list[DAGNode] = Field(description="List of nodes in the graph")
    edges: list[DAGEdge] = Field(default_factory=list, description="List of dependency edges")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Graph-level metadata")

    def validate_graph(self) -> None:
        """Perform full structural validation on the graph.

        Checks:
        - All dependencies exist as nodes in the graph.
        - The graph is Directed and Acyclic (no cycles).
        - No orphan (disconnected) nodes exist.
        - Worker requirements and capabilities are valid.
        """
        node_ids = {n.node_id for n in self.nodes}
        if not node_ids:
            raise DAGValidationError("The graph must contain at least one node.")

        # 1. Dependency checks (All dependency references must exist as nodes)
        unified_deps: set[tuple[str, str]] = set()  # (child_id, parent_id)

        # Capture from nodes' internal dependency lists
        for node in self.nodes:
            for dep_id in node.dependencies:
                if dep_id not in node_ids:
                    raise DAGValidationError(f"Node '{node.node_id}' references non-existent dependency: '{dep_id}'")
                if dep_id == node.node_id:
                    raise DAGValidationError(f"Node '{node.node_id}' cannot depend on itself.")
                unified_deps.add((node.node_id, dep_id))

        # Capture from explicit DAGEdges list
        for edge in self.edges:
            if edge.from_node_id not in node_ids:
                raise DAGValidationError(f"Edge references non-existent source node: '{edge.from_node_id}'")
            if edge.to_node_id not in node_ids:
                raise DAGValidationError(f"Edge references non-existent destination node: '{edge.to_node_id}'")
            if edge.from_node_id == edge.to_node_id:
                raise DAGValidationError(f"Self-loop is not allowed: '{edge.from_node_id}'")
            unified_deps.add((edge.to_node_id, edge.from_node_id))

        # 2. Cycle detection (DFS check)
        adj_graph: dict[str, list[str]] = {nid: [] for nid in node_ids}
        for child, parent in unified_deps:
            adj_graph[parent].append(child)

        visited: dict[str, int] = {nid: 0 for nid in node_ids}  # 0=unvisited, 1=visiting, 2=visited

        def has_cycle(nid: str) -> bool:
            visited[nid] = 1
            for child in adj_graph[nid]:
                if visited[child] == 1:
                    return True
                if visited[child] == 0:
                    if has_cycle(child):
                        return True
            visited[nid] = 2
            return False

        for nid in node_ids:
            if visited[nid] == 0:
                if has_cycle(nid):
                    raise DAGValidationError("Circular dependency detected in the DAG.")

        # 3. No orphaned tasks (Connectivity check treated as undirected graph)
        undirected_adj: dict[str, set[str]] = {nid: set() for nid in node_ids}
        for child, parent in unified_deps:
            undirected_adj[parent].add(child)
            undirected_adj[child].add(parent)

        # BFS/DFS traversal from a starting node
        start_node = next(iter(node_ids))
        visited_nodes = {start_node}
        queue = [start_node]
        while queue:
            curr = queue.pop(0)
            for neighbor in undirected_adj[curr]:
                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append(neighbor)

        unreachable = node_ids - visited_nodes
        if unreachable:
            raise DAGValidationError(
                f"Orphaned/disconnected nodes detected: {unreachable}"
            )

        # 4. Valid worker requirements & capabilities
        for node in self.nodes:
            if node.worker_type is not None and not isinstance(node.worker_type, str):
                raise DAGValidationError(f"Node '{node.node_id}' has invalid worker_type format.")
            if node.capabilities_required is not None and not isinstance(node.capabilities_required, list):
                raise DAGValidationError(f"Node '{node.node_id}' has invalid capabilities_required format.")

    def topological_sort(self) -> list[str]:
        """Return a topological ordering of node IDs (parents execute before children)."""
        self.validate_graph()

        node_ids = {n.node_id for n in self.nodes}
        unified_deps: set[tuple[str, str]] = set()
        for node in self.nodes:
            for dep_id in node.dependencies:
                unified_deps.add((node.node_id, dep_id))
        for edge in self.edges:
            unified_deps.add((edge.to_node_id, edge.from_node_id))

        adj_graph: dict[str, list[str]] = {nid: [] for nid in node_ids}
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

        for child, parent in unified_deps:
            adj_graph[parent].append(child)
            in_degree[child] += 1

        queue = sorted([nid for nid in node_ids if in_degree[nid] == 0])
        order: list[str] = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for child in sorted(adj_graph[curr]):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return order
