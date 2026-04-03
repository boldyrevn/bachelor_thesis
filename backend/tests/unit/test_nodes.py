"""Unit tests for node architecture."""

import pytest

from app.nodes.base import BaseNode, NodeContext, NodeResult
from app.nodes.registry import NodeRegistry
from app.nodes.text_output import TextOutputNode


class TestNodeContext:
    """Tests for NodeContext dataclass."""

    def test_context_creation(self):
        """Test basic context creation."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
        )

        assert context.pipeline_id == "pipeline-123"
        assert context.pipeline_run_id == "run-456"
        assert context.node_id == "node-789"
        assert context.pipeline_params == {}
        assert context.upstream_outputs == {}

    def test_context_with_params(self):
        """Test context with pipeline parameters."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
            pipeline_params={"date": "2024-01-01", "env": "prod"},
        )

        assert context.pipeline_params["date"] == "2024-01-01"
        assert context.pipeline_params["env"] == "prod"

    def test_get_output(self):
        """Test retrieving upstream node outputs."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
            upstream_outputs={
                "node-a": {"text": "Hello", "count": 5},
                "node-b": {"s3_path": "s3://bucket/file.parquet"},
            },
        )

        assert context.get_output("node-a", "text") == "Hello"
        assert context.get_output("node-a", "count") == 5
        assert context.get_output("node-b", "s3_path") == "s3://bucket/file.parquet"
        assert context.get_output("node-c", "missing") is None

    def test_get_output_missing_node(self):
        """Test retrieving output from non-existent node."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
            upstream_outputs={},
        )

        assert context.get_output("nonexistent", "output") is None

    def test_get_output_missing_field(self):
        """Test retrieving non-existent output field."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
            upstream_outputs={"node-a": {"text": "Hello"}},
        )

        assert context.get_output("node-a", "nonexistent") is None


class TestNodeResult:
    """Tests for NodeResult dataclass."""

    def test_success_result(self):
        """Test successful result creation."""
        result = NodeResult(
            success=True,
            outputs={"text": "Hello"},
            logs=["Execution completed"],
        )

        assert result.success is True
        assert result.outputs == {"text": "Hello"}
        assert result.logs == ["Execution completed"]
        assert result.error is None

    def test_error_result(self):
        """Test error result creation."""
        result = NodeResult(
            success=False,
            outputs={},
            logs=["Error occurred"],
            error="Something went wrong",
        )

        assert result.success is False
        assert result.outputs == {}
        assert result.logs == ["Error occurred"]
        assert result.error == "Something went wrong"

    def test_default_values(self):
        """Test default values for optional fields."""
        result = NodeResult(success=True)

        assert result.outputs == {}
        assert result.logs == []
        assert result.error is None


class TestNodeRegistry:
    """Tests for NodeRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        NodeRegistry._registry = {}
        # Re-register TextOutputNode
        NodeRegistry.register(TextOutputNode)

    def test_get_registered_node(self):
        """Test retrieving a registered node class."""
        node_class = NodeRegistry.get("text_output")
        assert node_class == TextOutputNode
        assert node_class.node_type == "text_output"

    def test_create_node_instance(self):
        """Test creating a node instance."""
        node = NodeRegistry.create("text_output")
        assert isinstance(node, TextOutputNode)
        assert node.node_type == "text_output"

    def test_list_types(self):
        """Test listing registered node types."""
        types = NodeRegistry.list_types()
        assert "text_output" in types

    def test_is_registered(self):
        """Test checking if node type is registered."""
        assert NodeRegistry.is_registered("text_output") is True
        assert NodeRegistry.is_registered("unknown_node") is False

    def test_get_unregistered_node_raises_error(self):
        """Test retrieving unregistered node raises KeyError."""
        with pytest.raises(KeyError, match="Node type 'unknown' not found"):
            NodeRegistry.get("unknown")

    def test_create_unregistered_node_raises_error(self):
        """Test creating unregistered node raises KeyError."""
        with pytest.raises(KeyError, match="Node type 'unknown' not found"):
            NodeRegistry.create("unknown")

    def test_duplicate_registration_raises_error(self):
        """Test registering duplicate node type raises ValueError."""

        class DuplicateNode(BaseNode):
            node_type = "text_output"

            def execute(self, context: NodeContext) -> NodeResult:
                return NodeResult(success=True)

        with pytest.raises(ValueError, match="already registered"):
            NodeRegistry.register(DuplicateNode)


class TestTextOutputNode:
    """Tests for TextOutputNode."""

    def setup_method(self):
        """Create fresh TextOutputNode instance for each test."""
        self.node = TextOutputNode()

    def test_node_type(self):
        """Test node type identifier."""
        assert self.node.node_type == "text_output"

    def test_execute_default_message(self):
        """Test execution with default message."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
            pipeline_params={"node_config": {}},
        )

        result = self.node.execute(context, logger=None)

        assert result.success is True
        assert result.outputs["text"] == "Hello, World!"
        assert len(result.logs) == 3
        assert "Text output node completed successfully" in result.logs

    def test_execute_custom_message(self):
        """Test execution with custom message."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
            pipeline_params={"node_config": {"message": "Custom message"}},
        )

        result = self.node.execute(context, logger=None)

        assert result.success is True
        assert result.outputs["text"] == "Custom message"

    def test_execute_with_template(self):
        """Test execution with template reference."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
            pipeline_params={"node_config": {"message": "Result: {{ node-a.text }}"}},
            upstream_outputs={"node-a": {"text": "Hello from A"}},
        )

        result = self.node.execute(context, logger=None)

        assert result.success is True
        assert result.outputs["text"] == "Result: Hello from A"

    def test_execute_with_multiple_templates(self):
        """Test execution with multiple template references."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
            pipeline_params={
                "node_config": {"message": "{{ node-a.text }} and {{ node-b.text }}"}
            },
            upstream_outputs={
                "node-a": {"text": "First"},
                "node-b": {"text": "Second"},
            },
        )

        result = self.node.execute(context, logger=None)

        assert result.success is True
        assert result.outputs["text"] == "First and Second"

    def test_execute_with_unresolved_template(self):
        """Test execution with unresolved template keeps original."""
        context = NodeContext(
            pipeline_id="pipeline-123",
            pipeline_run_id="run-456",
            node_id="node-789",
            pipeline_params={
                "node_config": {"message": "Value: {{ nonexistent.output }}"}
            },
            upstream_outputs={},
        )

        result = self.node.execute(context, logger=None)

        assert result.success is True
        # Unresolved templates are kept as-is
        assert result.outputs["text"] == "Value: {{ nonexistent.output }}"

    def test_validate_config_valid(self):
        """Test validation with valid configuration."""
        config = {"message": "Hello"}
        # Should not raise
        self.node.validate_config(config)

    def test_validate_config_empty(self):
        """Test validation with empty configuration."""
        config = {}
        # Should not raise
        self.node.validate_config(config)

    def test_validate_config_non_dict_raises_error(self):
        """Test validation with non-dict config raises ValueError."""
        with pytest.raises(ValueError, match="Configuration must be a dictionary"):
            self.node.validate_config("not a dict")

    def test_validate_config_non_string_message_raises_error(self):
        """Test validation with non-string message raises ValueError."""
        config = {"message": 123}
        with pytest.raises(ValueError, match="Message must be a string"):
            self.node.validate_config(config)

    def test_repr(self):
        """Test string representation."""
        node = TextOutputNode()
        assert "TextOutputNode" in repr(node)
        assert "text_output" in repr(node)
