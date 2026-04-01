"""Integration tests for Connection API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection import Connection, ConnectionType


@pytest.mark.asyncio
class TestConnectionCRUD:
    """Test Connection CRUD operations."""

    async def test_create_postgres_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test creating a PostgreSQL connection."""
        payload = {
            "name": "test-postgres",
            "connection_type": "postgres",
            "config": {
                "host": "localhost",
                "port": 5432,
                "database": "testdb",
                "username": "testuser",
            },
            "secrets": {
                "password": "testpassword123",
            },
            "description": "Test PostgreSQL connection",
        }

        response = await client.post("/api/v1/connections", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-postgres"
        assert data["connection_type"] == "postgres"
        assert "id" in data

        # Verify in database
        result = await db_session.execute(
            select(Connection).where(Connection.id == data["id"])
        )
        connection = result.scalar_one()
        assert connection is not None
        assert connection.name == "test-postgres"
        assert connection.connection_type == ConnectionType.POSTGRES
        assert connection.description == "Test PostgreSQL connection"

    async def test_create_clickhouse_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test creating a ClickHouse connection."""
        payload = {
            "name": "test-clickhouse",
            "connection_type": "clickhouse",
            "config": {
                "host": "localhost",
                "port": 8123,
                "database": "default",
                "username": "default",
            },
            "secrets": {
                "password": "clickhouse_password",
            },
        }

        response = await client.post("/api/v1/connections", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-clickhouse"
        assert data["connection_type"] == "clickhouse"

    async def test_create_s3_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test creating an S3 connection."""
        payload = {
            "name": "test-s3",
            "connection_type": "s3",
            "config": {
                "endpoint": "s3.amazonaws.com",
                "region": "us-east-1",
                "default_bucket": "my-bucket",
            },
            "secrets": {
                "access_key": "AKIAIOSFODNN7EXAMPLE",
                "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            },
        }

        response = await client.post("/api/v1/connections", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-s3"
        assert data["connection_type"] == "s3"

    async def test_create_spark_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test creating a Spark connection."""
        payload = {
            "name": "test-spark",
            "connection_type": "spark",
            "config": {
                "master_url": "spark://localhost:7077",
                "app_name": "TestApp",
                "deploy_mode": "client",
            },
            "secrets": {},
        }

        response = await client.post("/api/v1/connections", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-spark"
        assert data["connection_type"] == "spark"

    async def test_create_connection_duplicate_name(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test creating a connection with duplicate name."""
        payload = {
            "name": "test-duplicate",
            "connection_type": "postgres",
            "config": {
                "host": "localhost",
                "port": 5432,
                "database": "testdb",
                "username": "testuser",
            },
            "secrets": {"password": "password123"},
        }

        # Create first connection
        response1 = await client.post("/api/v1/connections", json=payload)
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = await client.post("/api/v1/connections", json=payload)
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"]

    async def test_create_connection_invalid_type(self, client: AsyncClient) -> None:
        """Test creating a connection with invalid type."""
        payload = {
            "name": "test-invalid",
            "connection_type": "invalid_type",
            "config": {},
            "secrets": {},
        }

        response = await client.post("/api/v1/connections", json=payload)

        assert response.status_code == 422  # Validation error

    async def test_list_connections(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test listing all connections."""
        # Create test connections
        connections_data = [
            {
                "name": "conn-1",
                "connection_type": "postgres",
                "config": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "db1",
                    "username": "user1",
                },
                "secrets": {"password": "pass1"},
            },
            {
                "name": "conn-2",
                "connection_type": "s3",
                "config": {
                    "endpoint": "s3.amazonaws.com",
                    "region": "us-east-1",
                    "default_bucket": "bucket1",
                },
                "secrets": {"access_key": "key1", "secret_key": "secret1"},
            },
        ]

        for conn_data in connections_data:
            await client.post("/api/v1/connections", json=conn_data)

        response = await client.get("/api/v1/connections")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

        # Check that secrets are not included
        for conn in data:
            assert "secrets" not in conn

    async def test_get_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test getting a connection by ID."""
        # Create a connection
        payload = {
            "name": "test-get",
            "connection_type": "postgres",
            "config": {
                "host": "localhost",
                "port": 5432,
                "database": "db",
                "username": "user",
            },
            "secrets": {"password": "password"},
        }
        create_response = await client.post("/api/v1/connections", json=payload)
        connection_id = create_response.json()["id"]

        # Get the connection
        response = await client.get(f"/api/v1/connections/{connection_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == connection_id
        assert data["name"] == "test-get"
        assert "secrets" not in data

    async def test_get_connection_not_found(self, client: AsyncClient) -> None:
        """Test getting a non-existent connection."""
        response = await client.get(
            "/api/v1/connections/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404

    async def test_update_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test updating a connection."""
        # Create a connection
        payload = {
            "name": "test-update",
            "connection_type": "postgres",
            "config": {
                "host": "localhost",
                "port": 5432,
                "database": "db",
                "username": "user",
            },
            "secrets": {"password": "password"},
        }
        create_response = await client.post("/api/v1/connections", json=payload)
        connection_id = create_response.json()["id"]

        # Update the connection
        update_payload = {
            "name": "test-update-renamed",
            "config": {
                "host": "newhost",
                "port": 5432,
                "database": "db",
                "username": "user",
            },
        }
        response = await client.put(
            f"/api/v1/connections/{connection_id}", json=update_payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-update-renamed"

        # Verify in database
        result = await db_session.execute(
            select(Connection).where(Connection.id == connection_id)
        )
        connection = result.scalar_one()
        assert connection.name == "test-update-renamed"
        assert connection.config["host"] == "newhost"

    async def test_update_connection_not_found(self, client: AsyncClient) -> None:
        """Test updating a non-existent connection."""
        response = await client.put(
            "/api/v1/connections/non-existent-id", json={"name": "new-name"}
        )

        assert response.status_code == 404

    async def test_delete_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test deleting a connection."""
        # Create a connection
        payload = {
            "name": "test-delete",
            "connection_type": "postgres",
            "config": {
                "host": "localhost",
                "port": 5432,
                "database": "db",
                "username": "user",
            },
            "secrets": {"password": "password"},
        }
        create_response = await client.post("/api/v1/connections", json=payload)
        connection_id = create_response.json()["id"]

        # Delete the connection
        response = await client.delete(f"/api/v1/connections/{connection_id}")

        assert response.status_code == 204

        # Verify deleted from database
        result = await db_session.execute(
            select(Connection).where(Connection.id == connection_id)
        )
        connection = result.scalar_one_or_none()
        assert connection is None

    async def test_delete_connection_not_found(self, client: AsyncClient) -> None:
        """Test deleting a non-existent connection."""
        response = await client.delete("/api/v1/connections/non-existent-id")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestConnectionTestEndpoint:
    """Test connection testing endpoint."""

    async def test_test_connection_postgres(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test testing a PostgreSQL connection."""
        # Create a connection with invalid credentials
        payload = {
            "name": "test-test-postgres",
            "connection_type": "postgres",
            "config": {
                "host": "localhost",
                "port": 5432,
                "database": "nonexistent_db",
                "username": "nonexistent_user",
            },
            "secrets": {"password": "wrong_password"},
        }
        create_response = await client.post("/api/v1/connections", json=payload)
        connection_id = create_response.json()["id"]

        # Test the connection
        response = await client.post(f"/api/v1/connections/{connection_id}/test")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data
        # Connection should fail (invalid credentials)
        assert data["success"] is False
        assert "error" in data

    async def test_test_connection_clickhouse(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test testing a ClickHouse connection."""
        payload = {
            "name": "test-test-clickhouse",
            "connection_type": "clickhouse",
            "config": {
                "host": "localhost",
                "port": 8123,
                "database": "default",
                "username": "default",
            },
            "secrets": {"password": "wrong_password"},
        }
        create_response = await client.post("/api/v1/connections", json=payload)
        connection_id = create_response.json()["id"]

        # Test the connection
        response = await client.post(f"/api/v1/connections/{connection_id}/test")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data
        # Connection should fail (invalid credentials)
        assert data["success"] is False
        assert "error" in data

    async def test_test_connection_s3(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test testing an S3 connection."""
        payload = {
            "name": "test-test-s3",
            "connection_type": "s3",
            "config": {
                "endpoint": "s3.amazonaws.com",
                "region": "us-east-1",
                "default_bucket": "nonexistent-bucket-xyz123",
            },
            "secrets": {
                "access_key": "AKIAIOSFODNN7EXAMPLE",
                "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            },
        }
        create_response = await client.post("/api/v1/connections", json=payload)
        connection_id = create_response.json()["id"]

        # Test the connection
        response = await client.post(f"/api/v1/connections/{connection_id}/test")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data
        # Connection should fail (invalid credentials)
        assert data["success"] is False
        assert "error" in data

    async def test_test_connection_spark(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test testing a Spark connection."""
        payload = {
            "name": "test-test-spark",
            "connection_type": "spark",
            "config": {
                "master_url": "spark://nonexistent-host:7077",
                "app_name": "TestApp",
                "deploy_mode": "client",
            },
            "secrets": {},
        }
        create_response = await client.post("/api/v1/connections", json=payload)
        connection_id = create_response.json()["id"]

        # Test the connection
        response = await client.post(f"/api/v1/connections/{connection_id}/test")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data
        # Connection should fail (unreachable host)
        assert data["success"] is False
        assert "error" in data
