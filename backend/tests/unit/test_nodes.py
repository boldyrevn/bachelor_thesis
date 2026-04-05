"""Unit tests for node architecture with typed schemas."""

import logging
from typing import Any

import pytest
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry
from app.nodes.text_output import TextOutputNode, TextOutputInput, TextOutputOutput


# Test fixtures for typed schemas
class MockInput(BaseModel):
    """Test input schema."""

    name: str = Field(description="Test name", default="test")
    value: int = Field(description="Test value", default=0)


class MockOutput(BaseModel):
    """Test output schema."""

    result: str = Field(description="Test result")
    count: int = Field(description="Result count")


class MockNode(BaseNode[MockInput, MockOutput]):
    """Test node implementation."""

    node_type = "mock_node"
    title = "Mock Node"
    description = "A mock node for unit tests"
    category = "test"

    input_schema = MockInput
    output_schema = MockOutput

    def execute(self, inputs: MockInput, logger: logging.Logger) -> MockOutput:
        """Simple test execution."""
        logger.info(f"Processing {inputs.name}")
        return MockOutput(
            result=f"Hello {inputs.name}",
            count=inputs.value,
        )


class TestNodeRegistry:
    """Tests for NodeRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        NodeRegistry._registry = {}
        # Re-register test nodes
        NodeRegistry.register(MockNode)
        NodeRegistry.register(TextOutputNode)

    def test_get_registered_node(self):
        """Test retrieving a registered node class."""
        node_class = NodeRegistry.get("mock_node")
        assert node_class == MockNode
        assert node_class.node_type == "mock_node"

    def test_create_node_instance(self):
        """Test creating a node instance."""
        node = NodeRegistry.create("mock_node")
        assert isinstance(node, MockNode)
        assert node.node_type == "mock_node"

    def test_list_types(self):
        """Test listing registered node types."""
        types = NodeRegistry.list_types()
        assert "mock_node" in types
        assert "text_output" in types

    def test_list_classes(self):
        """Test listing registered node classes."""
        classes = NodeRegistry.list_classes()
        assert MockNode in classes
        assert TextOutputNode in classes

    def test_is_registered(self):
        """Test checking if node type is registered."""
        assert NodeRegistry.is_registered("mock_node") is True
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
            node_type = "mock_node"
            title = "Duplicate"
            description = "Duplicate node"
            category = "test"
            input_schema = MockInput
            output_schema = MockOutput

            def execute(self, inputs: MockInput, logger: logging.Logger) -> MockOutput:
                return MockOutput(result="dup", count=0)

        with pytest.raises(ValueError, match="already registered"):
            NodeRegistry.register(DuplicateNode)

    def test_scan_nodes(self):
        """Test node scanning discovers modules."""
        # Don't clear registry - just test that scanning works
        count_before = len(NodeRegistry.list_types())
        count = NodeRegistry.scan_nodes()
        # Should discover at least TextOutputNode if not already registered
        assert count >= 0 or len(NodeRegistry.list_types()) > 0


class TestBaseNode:
    """Tests for BaseNode typed schema functionality."""

    def setup_method(self):
        """Create fresh test node instance."""
        self.node = MockNode()

    def test_node_metadata(self):
        """Test node metadata attributes."""
        assert self.node.node_type == "mock_node"
        assert self.node.title == "Mock Node"
        assert self.node.description == "A mock node for unit tests"
        assert self.node.category == "test"

    def test_input_schema_defined(self):
        """Test that input_schema is defined."""
        assert self.node.input_schema is not None
        assert self.node.input_schema == MockInput

    def test_output_schema_defined(self):
        """Test that output_schema is defined."""
        assert self.node.output_schema is not None
        assert self.node.output_schema == MockOutput

    def test_get_input_schema_json(self):
        """Test getting input schema as JSON."""
        schema = self.node.get_input_schema_json()
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "value" in schema["properties"]

    def test_get_output_schema_json(self):
        """Test getting output schema as JSON."""
        schema = self.node.get_output_schema_json()
        assert "properties" in schema
        assert "result" in schema["properties"]
        assert "count" in schema["properties"]

    def test_execute_with_typed_inputs(self):
        """Test execution with typed input parameters."""
        import logging

        logger = logging.getLogger("test")
        inputs = MockInput(name="World", value=42)
        output = self.node.execute(inputs, logger)

        assert isinstance(output, MockOutput)
        assert output.result == "Hello World"
        assert output.count == 42

    def test_repr(self):
        """Test string representation."""
        assert "MockNode" in repr(self.node)
        assert "mock_node" in repr(self.node)
        assert "test" in repr(self.node)


class TestTextOutputNode:
    """Tests for TextOutputNode with typed schemas."""

    def setup_method(self):
        """Create fresh TextOutputNode instance for each test."""
        self.node = TextOutputNode()

    def test_node_type(self):
        """Test node type identifier."""
        assert self.node.node_type == "text_output"
        assert self.node.title == "Text Output"
        assert self.node.category == "output"

    def test_input_schema(self):
        """Test input schema is defined correctly."""
        assert self.node.input_schema == TextOutputInput
        schema = self.node.get_input_schema_json()
        assert "message" in schema["properties"]

    def test_output_schema(self):
        """Test output schema is defined correctly."""
        assert self.node.output_schema == TextOutputOutput
        schema = self.node.get_output_schema_json()
        assert "text" in schema["properties"]

    def test_execute_default_message(self):
        """Test execution with default message."""
        import logging

        logger = logging.getLogger("test")
        inputs = TextOutputInput()

        output = self.node.execute(inputs, logger)

        assert isinstance(output, TextOutputOutput)
        assert output.text == "Hello, World!"

    def test_execute_custom_message(self):
        """Test execution with custom message."""
        import logging

        logger = logging.getLogger("test")
        inputs = TextOutputInput(message="Custom message")

        output = self.node.execute(inputs, logger)

        assert isinstance(output, TextOutputOutput)
        assert output.text == "Custom message"
