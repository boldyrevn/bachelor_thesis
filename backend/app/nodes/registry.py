"""Node registry for discovering and instantiating node types."""

from typing import Type

from .base import BaseNode


class NodeRegistry:
    """Registry for node types.

    Provides centralized registration and discovery of node types.
    Nodes are registered automatically via class inheritance.
    """

    _registry: dict[str, Type[BaseNode]] = {}

    @classmethod
    def register(cls, node_class: Type[BaseNode]) -> Type[BaseNode]:
        """Register a node class.

        Used as a decorator or called directly to register node types.

        Args:
            node_class: The node class to register

        Returns:
            The same node class (for decorator usage)

        Raises:
            ValueError: If node_type is already registered
        """
        node_type = node_class.node_type
        if node_type in cls._registry:
            raise ValueError(f"Node type '{node_type}' is already registered")
        cls._registry[node_type] = node_class
        return node_class

    @classmethod
    def get(cls, node_type: str) -> Type[BaseNode]:
        """Get a node class by type.

        Args:
            node_type: The node type identifier

        Returns:
            The node class

        Raises:
            KeyError: If node type is not registered
        """
        if node_type not in cls._registry:
            raise KeyError(
                f"Node type '{node_type}' not found. "
                f"Available types: {list(cls._registry.keys())}"
            )
        return cls._registry[node_type]

    @classmethod
    def create(cls, node_type: str, **kwargs: dict) -> BaseNode:
        """Create a node instance by type.

        Args:
            node_type: The node type identifier
            **kwargs: Additional arguments passed to node constructor

        Returns:
            A new node instance

        Raises:
            KeyError: If node type is not registered
        """
        node_class = cls.get(node_type)
        return node_class(**kwargs)

    @classmethod
    def list_types(cls) -> list[str]:
        """List all registered node types.

        Returns:
            List of registered node type identifiers
        """
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, node_type: str) -> bool:
        """Check if a node type is registered.

        Args:
            node_type: The node type identifier

        Returns:
            True if registered, False otherwise
        """
        return node_type in cls._registry
