"""Node scanner service for discovering and persisting node metadata."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.node_type import NodeType
from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry
from app.schemas.node_input_validation import validate_input_schema

logger = logging.getLogger(__name__)


class NodeScannerError(Exception):
    """Base exception for node scanner errors."""

    pass


class NodeScanner:
    """Scans node types and persists their metadata to the database.

    This service:
    1. Scans the nodes package for all registered node types
    2. Extracts metadata (title, description, category, schemas)
    3. Upserts into the node_types table (create or update)
    4. Deactivates node types that are no longer registered

    Called on application startup and via admin API endpoint.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the scanner.

        Args:
            session: Async database session
        """
        self.session = session

    async def scan_and_persist(self) -> dict[str, Any]:
        """Scan all registered nodes and persist metadata to DB.

        Returns:
            Dictionary with scan statistics:
                - created: Number of new node types created
                - updated: Number of existing node types updated
                - deactivated: Number of node types deactivated (no longer in code)
                - total: Total number of active node types
                - errors: List of error messages (if any)

        Raises:
            NodeScannerError: If database operation fails
        """
        stats = {"created": 0, "updated": 0, "deactivated": 0, "total": 0, "errors": []}

        try:
            # Re-scan node modules to discover new files (hot reload)
            count_before = len(NodeRegistry.list_types())
            NodeRegistry.scan_nodes()
            new_count = len(NodeRegistry.list_types()) - count_before
            if new_count > 0:
                logger.info(f"Discovered {new_count} new node type(s) from disk")

            # Get all currently registered node types from code
            registered_types = set(NodeRegistry.list_types())
            logger.info(f"Scanning {len(registered_types)} registered node types")

            # Get all node types from database
            existing_types_result = await self.session.execute(select(NodeType))
            existing_types = {
                row.node_type: row for row in existing_types_result.scalars().all()
            }
            existing_type_names = set(existing_types.keys())

            # Upsert registered nodes
            for node_type_name in registered_types:
                try:
                    node_class = NodeRegistry.get(node_type_name)
                    await self._persist_node_type(node_class)

                    if node_type_name in existing_type_names:
                        stats["updated"] += 1
                    else:
                        stats["created"] += 1
                except Exception as e:
                    error_msg = f"Failed to persist '{node_type_name}': {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    stats["errors"].append(error_msg)

            # Deactivate node types that are no longer in code
            orphaned_types = existing_type_names - registered_types
            for orphaned_type in orphaned_types:
                try:
                    existing_node = existing_types[orphaned_type]
                    existing_node.is_active = False
                    stats["deactivated"] += 1
                    logger.info(f"Deactivated orphaned node type: {orphaned_type}")
                except Exception as e:
                    error_msg = f"Failed to deactivate '{orphaned_type}': {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    stats["errors"].append(error_msg)

            await self.session.commit()

            # Count active node types
            stats["total"] = len(registered_types)

            logger.info(
                f"Node scan completed: created={stats['created']}, "
                f"updated={stats['updated']}, deactivated={stats['deactivated']}, "
                f"total={stats['total']}, errors={len(stats['errors'])}"
            )

        except Exception as e:
            await self.session.rollback()
            error_msg = f"Database operation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            stats["errors"].append(error_msg)
            raise NodeScannerError(error_msg) from e

        return stats

    async def _persist_node_type(self, node_class: type[BaseNode]) -> None:
        """Persist a single node type to the database.

        Args:
            node_class: Node class to persist

        Raises:
            ValueError: If node class is missing required attributes
        """
        # Validate required attributes
        if not node_class.input_schema:
            raise ValueError(f"Node '{node_class.node_type}' missing input_schema")
        if not node_class.output_schema:
            raise ValueError(f"Node '{node_class.node_type}' missing output_schema")

        # Validate input schema field types
        validation_errors = validate_input_schema(node_class.input_schema)
        if validation_errors:
            raise ValueError(
                f"Node '{node_class.node_type}' has invalid input_schema: "
                + "; ".join(validation_errors)
            )

        # Extract schemas as JSON
        input_schema_json = node_class().get_input_schema_json()
        output_schema_json = node_class().get_output_schema_json()

        # Check if node type already exists
        existing = await self.session.get(NodeType, node_class.node_type)

        if existing:
            # Update existing record
            existing.title = node_class.title
            existing.description = node_class.description
            existing.category = node_class.category
            existing.input_schema = input_schema_json
            existing.output_schema = output_schema_json
            existing.is_active = True
            existing.version += 1
            logger.debug(
                f"Updated node type: {node_class.node_type} (v{existing.version})"
            )
        else:
            # Create new record
            new_node_type = NodeType(
                node_type=node_class.node_type,
                title=node_class.title,
                description=node_class.description,
                category=node_class.category,
                input_schema=input_schema_json,
                output_schema=output_schema_json,
                version=1,
                is_active=True,
            )
            self.session.adccccbgibjhkdiebrvnjbvtjeekbhfnbbielceeknrtghd(new_node_type)
            logger.debug(f"Created node type: {node_class.node_type}")
