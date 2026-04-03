"""Unit tests for graph resolver."""

import pytest

from app.orchestration.graph_resolver import (
    GraphResolver,
    ResolvedGraph,
    get_execution_order,
    validate_pipeline_graph,
)


class TestGraphResolverBasic:
    """Basic graph resolution tests."""

    def test_empty_graph(self):
        """Test resolving empty graph."""
        resolver = GraphResolver({"nodes": [], "edges": []})
        result = resolver.resolve()

        assert result.has_cycle is False
        assert result.execution_order == []
        assert result.nodes == {}

    def test_single_node(self):
        """Test resolving graph with single node."""
        graph = {
            "nodes": [
                {"id": "node-1", "type": "text_output", "data": {"message": "Hello"}}
            ],
            "edges": [],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is False
        assert result.execution_order == ["node-1"]
        assert "node-1" in result.nodes

    def test_two_nodes_no_edges(self):
        """Test resolving graph with two independent nodes."""
        graph = {
            "nodes": [
                {"id": "node-1", "type": "text_output", "data": {}},
                {"id": "node-2", "type": "text_output", "data": {}},
            ],
            "edges": [],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is False
        assert len(result.execution_order) == 2
        assert set(result.execution_order) == {"node-1", "node-2"}


class TestGraphResolverTopologicalSort:
    """Tests for topological sort functionality."""

    def test_linear_chain(self):
        """Test topological sort with linear chain A -> B -> C."""
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
                {"id": "C", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "B"},
                {"id": "e2", "source": "B", "target": "C"},
            ],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is False
        assert result.execution_order == ["A", "B", "C"]

    def test_fan_out_pattern(self):
        """Test topological sort with fan-out pattern (one to many)."""
        # A -> B, A -> C, A -> D
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
                {"id": "C", "type": "text_output", "data": {}},
                {"id": "D", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "B"},
                {"id": "e2", "source": "A", "target": "C"},
                {"id": "e3", "source": "A", "target": "D"},
            ],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is False
        assert result.execution_order[0] == "A"  # A must be first
        assert set(result.execution_order[1:]) == {"B", "C", "D"}

    def test_fan_in_pattern(self):
        """Test topological sort with fan-in pattern (many to one)."""
        # A -> D, B -> D, C -> D
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
                {"id": "C", "type": "text_output", "data": {}},
                {"id": "D", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "D"},
                {"id": "e2", "source": "B", "target": "D"},
                {"id": "e3", "source": "C", "target": "D"},
            ],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is False
        assert result.execution_order[-1] == "D"  # D must be last
        assert set(result.execution_order[:-1]) == {"A", "B", "C"}

    def test_complex_dag(self):
        """Test topological sort with complex DAG."""
        #     A
        #    / \
        #   B   C
        #    \ /
        #     D
        #     |
        #     E
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
                {"id": "C", "type": "text_output", "data": {}},
                {"id": "D", "type": "text_output", "data": {}},
                {"id": "E", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "B"},
                {"id": "e2", "source": "A", "target": "C"},
                {"id": "e3", "source": "B", "target": "D"},
                {"id": "e4", "source": "C", "target": "D"},
                {"id": "e5", "source": "D", "target": "E"},
            ],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is False
        assert result.execution_order[0] == "A"  # A must be first
        assert result.execution_order[-1] == "E"  # E must be last
        assert result.execution_order.index("B") < result.execution_order.index("D")
        assert result.execution_order.index("C") < result.execution_order.index("D")
        assert result.execution_order.index("D") < result.execution_order.index("E")


class TestGraphResolverCycleDetection:
    """Tests for cycle detection functionality."""

    def test_simple_cycle(self):
        """Test detection of simple cycle A -> B -> A."""
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "B"},
                {"id": "e2", "source": "B", "target": "A"},
            ],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is True
        assert len(result.cycle_path) > 0
        assert "A" in result.cycle_path
        assert "B" in result.cycle_path

    def test_self_loop(self):
        """Test detection of self-loop A -> A."""
        graph = {
            "nodes": [{"id": "A", "type": "text_output", "data": {}}],
            "edges": [{"id": "e1", "source": "A", "target": "A"}],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is True
        assert "A" in result.cycle_path

    def test_three_node_cycle(self):
        """Test detection of cycle A -> B -> C -> A."""
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
                {"id": "C", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "B"},
                {"id": "e2", "source": "B", "target": "C"},
                {"id": "e3", "source": "C", "target": "A"},
            ],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is True
        assert len(result.cycle_path) >= 3

    def test_cycle_in_complex_graph(self):
        """Test cycle detection in complex graph with cycle."""
        #     A
        #    / \
        #   B   C
        #    \ /
        #     D
        #     |
        #     E
        #     |
        #     B  (creates cycle B -> D -> E -> B)
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
                {"id": "C", "type": "text_output", "data": {}},
                {"id": "D", "type": "text_output", "data": {}},
                {"id": "E", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "B"},
                {"id": "e2", "source": "A", "target": "C"},
                {"id": "e3", "source": "B", "target": "D"},
                {"id": "e4", "source": "C", "target": "D"},
                {"id": "e5", "source": "D", "target": "E"},
                {"id": "e6", "source": "E", "target": "B"},  # Creates cycle
            ],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is True
        assert "B" in result.cycle_path
        assert "D" in result.cycle_path
        assert "E" in result.cycle_path


class TestGraphResolverPipelineParams:
    """Tests for handling PipelineParams nodes."""

    def test_skips_pipeline_params_node(self):
        """Test that PipelineParams nodes are excluded from execution."""
        graph = {
            "nodes": [
                {
                    "id": "params-1",
                    "type": "PipelineParams",
                    "data": {
                        "parameters": [
                            {"name": "date", "type": "string", "default": "2024-01-01"}
                        ]
                    },
                },
                {"id": "node-1", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "params-1", "target": "node-1"},
            ],
        }

        resolver = GraphResolver(graph)
        result = resolver.resolve()

        assert result.has_cycle is False
        assert "params-1" not in result.nodes
        assert "node-1" in result.execution_order


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_validate_pipeline_graph_valid(self):
        """Test validate_pipeline_graph with valid graph."""
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
            ],
            "edges": [{"id": "e1", "source": "A", "target": "B"}],
        }

        is_valid, error = validate_pipeline_graph(graph)

        assert is_valid is True
        assert error is None

    def test_validate_pipeline_graph_invalid(self):
        """Test validate_pipeline_graph with invalid graph (cycle)."""
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "B"},
                {"id": "e2", "source": "B", "target": "A"},
            ],
        }

        is_valid, error = validate_pipeline_graph(graph)

        assert is_valid is False
        assert error is not None
        assert "Cycle detected" in error

    def test_get_execution_order_valid(self):
        """Test get_execution_order with valid graph."""
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
            ],
            "edges": [{"id": "e1", "source": "A", "target": "B"}],
        }

        order = get_execution_order(graph)

        assert order == ["A", "B"]

    def test_get_execution_order_invalid_raises_error(self):
        """Test get_execution_order raises ValueError for invalid graph."""
        graph = {
            "nodes": [
                {"id": "A", "type": "text_output", "data": {}},
                {"id": "B", "type": "text_output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "A", "target": "B"},
                {"id": "e2", "source": "B", "target": "A"},
            ],
        }

        with pytest.raises(ValueError, match="Cycle detected"):
            get_execution_order(graph)


class TestResolvedGraph:
    """Tests for ResolvedGraph dataclass."""

    def test_resolved_graph_default_values(self):
        """Test ResolvedGraph default values."""
        result = ResolvedGraph(nodes={}, execution_order=[])

        assert result.has_cycle is False
        assert result.cycle_path == []
        assert result.error_message is None

    def test_resolved_graph_with_cycle(self):
        """Test ResolvedGraph with cycle information."""
        result = ResolvedGraph(
            nodes={},
            execution_order=[],
            has_cycle=True,
            cycle_path=["A", "B", "A"],
            error_message="Cycle detected: A -> B -> A",
        )

        assert result.has_cycle is True
        assert result.cycle_path == ["A", "B", "A"]
        assert "Cycle detected" in result.error_message
