"""PostgresQuery node — lists schemas and tables, outputs to logs."""

import logging

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry
from app.schemas.connection import PostgresConnection


# =============================================================================
# Typed Input / Output Schemas
# =============================================================================


class PostgresQueryInput(BaseModel):
    """Input parameters for PostgresQueryNode."""

    connection: PostgresConnection = Field(
        description="PostgreSQL connection to query",
    )
    include_system_schemas: bool = Field(
        default=False,
        description="Include system schemas (pg_catalog, information_schema, etc.)",
    )


class PostgresQueryOutput(BaseModel):
    """Output artifacts for PostgresQueryNode."""

    schema_count: int = Field(description="Number of schemas found")
    table_count: int = Field(description="Total number of tables found")


# =============================================================================
# Node Implementation
# =============================================================================


@NodeRegistry.register
class PostgresQueryNode(BaseNode[PostgresQueryInput, PostgresQueryOutput]):
    """Lists schemas and tables from a PostgreSQL connection and logs them."""

    node_type = "postgres_query"
    title = "Postgres Query"
    description = "Connects to PostgreSQL and logs available schemas and tables"
    category = "data"
    input_schema = PostgresQueryInput
    output_schema = PostgresQueryOutput

    def execute(
        self, inputs: PostgresQueryInput, logger: logging.Logger
    ) -> PostgresQueryOutput:
        """Execute: list schemas and tables, log the results."""
        import asyncio

        from asyncpg import create_pool

        password = inputs.connection.password.get_value()
        dsn = (
            f"postgresql://{inputs.connection.username}:{password}"
            f"@{inputs.connection.host}:{inputs.connection.port}/{inputs.connection.database}"
        )

        async def _fetch() -> tuple[int, int]:
            pool = await create_pool(dsn=dsn, min_size=1, max_size=1)
            try:
                async with pool.acquire() as conn:
                    # Fetch schemas
                    schema_query = """
                        SELECT schema_name
                        FROM information_schema.schemata
                        WHERE schema_name NOT LIKE 'pg_toast%'
                        ORDER BY schema_name
                    """
                    rows = await conn.fetch(schema_query)
                    schemas = [r["schema_name"] for r in rows]

                    # Filter system schemas if not requested
                    if not inputs.include_system_schemas:
                        schemas = [
                            s
                            for s in schemas
                            if s not in ("pg_catalog", "information_schema")
                        ]

                    logger.info(f"Found {len(schemas)} schema(s): {', '.join(schemas)}")

                    # Fetch tables per schema
                    total_tables = 0
                    for schema in schemas:
                        table_rows = await conn.fetch(
                            """
                            SELECT table_name FROM information_schema.tables
                            WHERE table_schema = $1 AND table_type = 'BASE TABLE'
                            ORDER BY table_name
                            """,
                            schema,
                        )
                        table_names = [r["table_name"] for r in table_rows]
                        total_tables += len(table_names)
                        logger.info(f"  Schema '{schema}': {len(table_names)} table(s) — {', '.join(table_names)}")

                    return len(schemas), total_tables
            finally:
                await pool.close()

        schema_count, table_count = asyncio.get_event_loop().run_until_complete(_fetch())

        logger.info(
            f"PostgresQueryNode complete: {schema_count} schema(s), {table_count} table(s)"
        )
        return PostgresQueryOutput(schema_count=schema_count, table_count=table_count)
