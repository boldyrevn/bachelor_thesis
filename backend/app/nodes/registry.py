"""Node registry for discovering and instantiating node types."""

import logging
from pathlib import Path
from typing import Type

from .base import BaseNode

logger = logging.getLogger(__name__)


class NodeRegistry:
    """Registry for node types.

    Provides centralized registration and discovery of node types.
    Nodes are discovered via file scan (Airflow-style DAG discovery)
    and registered automatically via the @NodeRegistry.register decorator.
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
        logger.info(f"Registered node type: {node_type} ({node_class.title})")
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
        return node_class()

    @classmethod
    def list_types(cls) -> list[str]:
        """List all registered node types.

        Returns:
            List of registered node type identifiers
        """
        return list(cls._registry.keys())

    @classmethod
    def list_classes(cls) -> list[Type[BaseNode]]:
        """List all registered node classes.

        Returns:
            List of registered node classes
        """
        return list(cls._registry.values())

    @classmethod
    def is_registered(cls, node_type: str) -> bool:
        """Check if a node type is registered.

        Args:
            node_type: The node type identifier

        Returns:
            True if registered, False otherwise
        """
        return node_type in cls._registry

    @classmethod
    def scan_nodes(cls, nodes_dir: str | None = None) -> int:
        """Scan all .py files in the nodes directory and register nodes.

        Airflow-style DAG discovery: each file is exec()'d in a namespace
        containing BaseNode, NodeRegistry, logging, pydantic imports, and
        connection types. The @NodeRegistry.register decorator handles
        registration. No Python import system involvement — no sys.modules
        conflicts, no __init__.py requirements.

        Args:
            nodes_dir: Path to scan. Defaults to the directory containing
                       this module (app/nodes/).

        Returns:
            Number of node types discovered and registered
        """

        # Default to the directory containing this file
        if nodes_dir is None:
            nodes_dir = str(Path(__file__).parent)

        nodes_path = Path(nodes_dir)
        if not nodes_path.is_dir():
            raise ValueError(f"Nodes directory not found: {nodes_dir}")

        # Clear registry — fresh scan means fresh state
        cls._registry.clear()

        # Collect all .py files recursively
        py_files = sorted(nodes_path.rglob("*.py"))
        logger.info(f"Scanning {len(py_files)} .py files in {nodes_dir}")

        for py_file in py_files:
            # Skip private files, base, registry, and scanner
            # These are infrastructure, not node implementations
            if py_file.name.startswith("_"):
                continue
            if py_file.name in ("base.py", "registry.py", "scanner.py"):
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to read {py_file}: {e}", exc_info=True)
                continue

            # Build a namespace with common imports available
            namespace = {
                "BaseNode": BaseNode,
                "NodeRegistry": cls,
                "logging": logging,
            }

            # Add pydantic imports (most nodes use BaseModel, Field)
            try:
                from pydantic import BaseModel, Field

                namespace["BaseModel"] = BaseModel
                namespace["Field"] = Field
            except ImportError:
                pass

            # Add connection types
            try:
                from app.schemas.connection import (
                    ClickHouseConnection,
                    PostgresConnection,
                    S3Connection,
                    SparkConnection,
                )

                namespace["PostgresConnection"] = PostgresConnection
                namespace["ClickHouseConnection"] = ClickHouseConnection
                namespace["S3Connection"] = S3Connection
                namespace["SparkConnection"] = SparkConnection
            except ImportError:
                pass

            # Execute the file — decorators auto-register nodes
            try:
                exec(compile(source, str(py_file), "exec"), namespace)
                logger.debug(f"Scanned node file: {py_file.relative_to(nodes_path)}")
            except Exception as e:
                logger.error(
                    f"Failed to scan {py_file.relative_to(nodes_path)}: {e}",
                    exc_info=True,
                )

        logger.info(f"Node scan complete: {len(cls._registry)} types registered")
        return len(cls._registry)
