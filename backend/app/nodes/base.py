"""Node base class and registry for FlowForge pipeline execution."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeContext:
    """Context passed to nodes during execution.

    Contains resolved inputs from upstream nodes and pipeline parameters.
    """

    pipeline_id: str
    pipeline_run_id: str
    node_id: str
    pipeline_params: dict[str, Any] = field(default_factory=dict)
    upstream_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_output(self, node_id: str, output_name: str) -> Any:
        """Get output from an upstream node.

        Args:
            node_id: ID of the upstream node
            output_name: Name of the output to retrieve

        Returns:
            The output value, or None if not found
        """
        return self.upstream_outputs.get(node_id, {}).get(output_name)


@dataclass
class NodeResult:
    """Result of node execution.

    Contains output artifacts and execution logs.
    """

    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    error: str | None = None


class BaseNode(ABC):
    """Abstract base class for all FlowForge nodes.

    Each node type must:
    1. Declare a unique node_type class attribute
    2. Implement the execute() method
    3. Register itself with the NodeRegistry

    Nodes are stateless - they read from storage, process, and write back.
    Each node runs as an isolated Celery task.
    """

    node_type: str = "base"

    @abstractmethod
    def execute(
        self, context: NodeContext, logger: logging.Logger | None = None
    ) -> NodeResult:
        """Execute the node logic.

        Args:
            context: Execution context with inputs and parameters
            logger: Optional logger for streaming logs. If None, uses standard logging.

        Returns:
            NodeResult with outputs and logs
        """
        pass

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate node configuration before execution.

        Override in subclasses to add type-specific validation.

        Args:
            config: Node configuration from the graph definition

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(type={self.node_type})>"
