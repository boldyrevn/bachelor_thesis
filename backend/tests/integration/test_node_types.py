"""Integration tests for node types API and scanner."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.node_type import NodeType
from app.nodes.registry import NodeRegistry
from app.nodes.text_output import TextOutputNode


class TestNodeTypesAPI:
    """Integration tests for node types API endpoints."""

    @pytest.mark.asyncio
    async def test_list_node_types_empty(self, client, db_session: AsyncSession):
        """Test listing node types when database is empty."""
        # Clear any existing node types
        await db_session.execute(text("DELETE FROM node_types"))
        await db_session.commit()

        response = await client.get("/api/v1/node-types")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["node_types"] == []

    @pytest.mark.asyncio
    async def test_list_node_types_with_data(self, client, db_session: AsyncSession):
        """Test listing node types with data in database."""
        # Insert a test node type
        node_type = NodeType(
            node_type="test_type",
            title="Test Type",
            description="A test node type",
            category="test",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            output_schema={
                "type": "object",
                "properties": {"result": {"type": "string"}},
            },
            version=1,
            is_active=True,
        )
        db_session.add(node_type)
        await db_session.commit()

        response = await client.get("/api/v1/node-types")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["node_types"]) == 1
        assert data["node_types"][0]["node_type"] == "test_type"
        assert data["node_types"][0]["title"] == "Test Type"

    @pytest.mark.asyncio
    async def test_get_node_type_by_id(self, client, db_session: AsyncSession):
        """Test getting a specific node type by ID."""
        # Clear existing and insert test node
        await db_session.execute(text("DELETE FROM node_types"))
        await db_session.commit()

        node_type = NodeType(
            node_type="test_type",
            title="Test Type",
            description="A test node type",
            category="test",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            output_schema={
                "type": "object",
                "properties": {"result": {"type": "string"}},
            },
            version=1,
            is_active=True,
        )
        db_session.add(node_type)
        await db_session.commit()

        response = await client.get("/api/v1/node-types/test_type")
        assert response.status_code == 200
        data = response.json()
        assert data["node_type"] == "test_type"
        assert data["title"] == "Test Type"

    @pytest.mark.asyncio
    async def test_get_node_type_not_found(self, client):
        """Test getting a non-existent node type."""
        response = await client.get("/api/v1/node-types/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_node_type_inactive(self, client, db_session: AsyncSession):
        """Test getting an inactive node type returns 404."""
        node_type = NodeType(
            node_type="inactive_type",
            title="Inactive Type",
            description="An inactive node type",
            category="test",
            input_schema={},
            output_schema={},
            version=1,
            is_active=False,
        )
        db_session.add(node_type)
        await db_session.commit()

        response = await client.get("/api/v1/node-types/inactive_type")
        assert response.status_code == 404


class TestNodeScannerIntegration:
    """Integration tests for node scanner."""

    @pytest.mark.asyncio
    async def test_scan_and_persist_creates_nodes(
        self, client, db_session: AsyncSession
    ):
        """Test that scanning creates node types in database."""
        # Clear existing
        await db_session.execute(text("DELETE FROM node_types"))
        await db_session.commit()

        # Ensure TextOutputNode is registered
        if not NodeRegistry.is_registered("text_output"):
            NodeRegistry.register(TextOutputNode)

        # Call scan endpoint
        response = await client.post("/api/v1/node-types/scan")
        assert response.status_code == 200
        data = response.json()
        assert data["created"] >= 1 or data["updated"] >= 1
        assert len(data["errors"]) == 0

        # Verify in database
        result = await db_session.execute(
            select(NodeType).where(NodeType.node_type == "text_output")
        )
        node_type = result.scalar_one_or_none()
        assert node_type is not None
        assert node_type.title == "Text Output"
        assert node_type.category == "output"
        assert "message" in str(node_type.input_schema)
        assert "text" in str(node_type.output_schema)

    @pytest.mark.asyncio
    async def test_scan_deactivates_orphaned_nodes(
        self, client, db_session: AsyncSession
    ):
        """Test that scanning deactivates node types no longer in code."""
        # Insert an orphaned node type (not in registry)
        orphaned = NodeType(
            node_type="orphaned_type",
            title="Orphaned Type",
            description="This type no longer exists in code",
            category="test",
            input_schema={},
            output_schema={},
            version=1,
            is_active=True,
        )
        db_session.add(orphaned)
        await db_session.commit()

        # Call scan
        response = await client.post("/api/v1/node-types/scan")
        assert response.status_code == 200
        data = response.json()
        assert data["deactivated"] >= 1

        # Verify orphaned type is now inactive
        result = await db_session.execute(
            select(NodeType).where(NodeType.node_type == "orphaned_type")
        )
        node_type = result.scalar_one()
        assert node_type.is_active is False

    @pytest.mark.asyncio
    async def test_scan_updates_existing_node(self, client, db_session: AsyncSession):
        """Test that scanning updates existing node types with new metadata."""
        # Clear existing first
        await db_session.execute(text("DELETE FROM node_types"))
        await db_session.commit()

        # Insert text_output with old metadata
        old_node = NodeType(
            node_type="text_output",
            title="Old Title",
            description="Old description",
            category="old_category",
            input_schema={"old": "schema"},
            output_schema={"old": "schema"},
            version=1,
            is_active=True,
        )
        db_session.add(old_node)
        await db_session.commit()

        # Ensure TextOutputNode is registered
        if not NodeRegistry.is_registered("text_output"):
            NodeRegistry.register(TextOutputNode)

        # Call scan
        response = await client.post("/api/v1/node-types/scan")
        assert response.status_code == 200
        data = response.json()
        assert data["updated"] >= 1

        # Verify updated in database
        result = await db_session.execute(
            select(NodeType).where(NodeType.node_type == "text_output")
        )
        node_type = result.scalar_one()
        assert node_type.title == "Text Output"
        assert node_type.description != "Old description"
        assert node_type.category == "output"
        assert node_type.version == 2
