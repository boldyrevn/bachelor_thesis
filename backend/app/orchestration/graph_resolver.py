"""Graph resolver for pipeline DAG validation and execution ordering.

Provides topological sort and cycle detection for pipeline graphs.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """Represents a node in the execution graph."""

    id: str
    node_type: str
    data: dict[str, Any] = field(default_factory=dict)
    dependencies: set[str] = field(default_factory=set)
    dependents: set[str] = field(default_factory=set)


@dataclass
class ResolvedGraph:
    """Result of graph resolution with execution order."""

    nodes: dict[str, GraphNode]
    execution_order: list[str]
    has_cycle: bool = False
    cycle_path: list[str] = field(default_factory=list)
    error_message: str | None = None


class GraphResolver:
    """Resolves pipeline graph for execution.

    Performs:
    1. Graph validation (detect cycles)
    2. Topological sort (determine execution order)
    3. Dependency resolution

    Usage:
        resolver = GraphResolver(graph_definition)
        resolved = resolver.resolve()
        if resolved.has_cycle:
            raise ValueError(f"Cycle detected: {resolved.cycle_path}")
        print(resolved.execution_order)
    """

    def __init__(self, graph_definition: dict[str, Any]):
        """Initialize resolver with graph definition.

        Args:
            graph_definition: React Flow graph state with nodes and edges
        """
        self.nodes_raw = graph_definition.get("nodes", [])
        self.edges_raw = graph_definition.get("edges", [])

    def resolve(self) -> ResolvedGraph:
        """Resolve the graph and determine execution order.

        Returns:
            ResolvedGraph with execution order and any errors
        """
        # Build graph nodes
        nodes = self._build_nodes()

        # Build edges (dependencies)
        self._build_edges(nodes)

        # Detect cycles
        cycle_path = self._detect_cycle(nodes)
        if cycle_path:
            return ResolvedGraph(
                nodes=nodes,
                execution_order=[],
                has_cycle=True,
                cycle_path=cycle_path,
                error_message=f"Cycle detected: {' -> '.join(cycle_path)}",
            )

        # Topological sort
        execution_order = self._topological_sort(nodes)

        return ResolvedGraph(
            nodes=nodes,
            execution_order=execution_order,
            has_cycle=False,
        )

    def _build_nodes(self) -> dict[str, GraphNode]:
        """Build graph nodes from raw node definitions.

        Returns:
            Dictionary of node_id -> GraphNode
        """
        nodes = {}
        for node_data in self.nodes_raw:
            node_id = node_data.get("id", "")
            node_type = node_data.get("type", "unknown")

            # Skip parameter nodes (they don't execute)
            if node_type == "PipelineParams":
                continue

            nodes[node_id] = GraphNode(
                id=node_id,
                node_type=node_type,
                data=node_data.get("data", {}),
            )
        return nodes

    def _build_edges(self, nodes: dict[str, GraphNode]) -> None:
        """Build dependency edges between nodes.

        Args:
            nodes: Dictionary of existing nodes
        """
        for edge_data in self.edges_raw:
            source_id = edge_data.get("source", "")
            target_id = edge_data.get("target", "")

            # Skip if target doesn't exist (e.g., edge to PipelineParams)
            if target_id not in nodes:
                continue

            # Skip if source is PipelineParams (it's not an executable node)
            source_node = next(
                (n for n in self.nodes_raw if n.get("id") == source_id), None
            )
            if source_node and source_node.get("type") == "PipelineParams":
                continue

            # target depends on source (source must execute before target)
            if source_id in nodes:
                nodes[target_id].dependencies.add(source_id)
                nodes[source_id].dependents.add(target_id)

    def _detect_cycle(self, nodes: dict[str, GraphNode]) -> list[str]:
        """Detect cycles in the graph using DFS.

        Args:
            nodes: Dictionary of nodes

        Returns:
            List of node IDs forming the cycle path, or empty if no cycle
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node_id: WHITE for node_id in nodes}
        parent = {node_id: None for node_id in nodes}

        def dfs(node_id: str) -> list[str]:
            color[node_id] = GRAY

            for dependent in nodes[node_id].dependents:
                if dependent not in color:
                    continue

                if color[dependent] == GRAY:
                    # Found cycle - reconstruct path
                    cycle = [dependent, node_id]
                    current = node_id
                    while parent[current] and parent[current] != dependent:
                        current = parent[current]
                        cycle.append(current)
                    cycle.append(dependent)
                    return list(reversed(cycle))

                if color[dependent] == WHITE:
                    parent[dependent] = node_id
                    result = dfs(dependent)
                    if result:
                        return result

            color[node_id] = BLACK
            return []

        for node_id in nodes:
            if color[node_id] == WHITE:
                result = dfs(node_id)
                if result:
                    return result

        return []

    def _topological_sort(self, nodes: dict[str, GraphNode]) -> list[str]:
        """Perform topological sort using Kahn's algorithm.

        Args:
            nodes: Dictionary of nodes

        Returns:
            List of node IDs in execution order
        """
        if not nodes:
            return []

        # Calculate in-degree for each node
        in_degree = {node_id: len(node.dependencies) for node_id, node in nodes.items()}

        # Start with nodes that have no dependencies
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort queue for deterministic order
            queue.sort()
            node_id = queue.pop(0)
            result.append(node_id)

            # Reduce in-degree for dependents
            for dependent in nodes[node_id].dependents:
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return result


def validate_pipeline_graph(
    graph_definition: dict[str, Any],
) -> tuple[bool, str | None]:
    """Validate a pipeline graph definition.

    Args:
        graph_definition: React Flow graph state

    Returns:
        Tuple of (is_valid, error_message)
    """
    resolver = GraphResolver(graph_definition)
    resolved = resolver.resolve()

    if resolved.has_cycle:
        return False, resolved.error_message

    return True, None


def get_execution_order(graph_definition: dict[str, Any]) -> list[str]:
    """Get the execution order for a pipeline graph.

    Args:
        graph_definition: React Flow graph state

    Returns:
        List of node IDs in execution order

    Raises:
        ValueError: If graph contains a cycle
    """
    resolver = GraphResolver(graph_definition)
    resolved = resolver.resolve()

    if resolved.has_cycle:
        raise ValueError(resolved.error_message)

    return resolved.execution_order
