"""SparkFromPostgresToS3 node — reads PostgreSQL table via Spark and writes to S3."""

import logging

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry
from app.schemas.connection import PostgresConnection, S3Connection, SparkConnection

# =============================================================================
# Typed Input / Output Schemas
# =============================================================================


class SparkFromPostgresToS3Input(BaseModel):
    """Input parameters for SparkFromPostgresToS3 node."""

    spark_connection: SparkConnection = Field(
        description="Spark connection to use for execution",
    )
    postgres_connection: PostgresConnection = Field(
        description="PostgreSQL connection to read data from",
    )
    s3_connection: S3Connection = Field(
        description="S3/MinIO connection to write data to",
    )
    table: str = Field(
        description="Table name to read from (e.g. 'public.users')",
    )
    s3_output_path: str = Field(
        description="S3 path to write parquet data (e.g. 's3://artifacts/raw_data/')",
    )
    spark_app_name: str = Field(
        default="FlowForge_PostgresToS3",
        description="Spark application name",
    )


class SparkFromPostgresToS3Output(BaseModel):
    """Output artifacts for SparkFromPostgresToS3 node."""

    row_count: int = Field(description="Number of rows read from the table")
    s3_output_path: str = Field(description="S3 path where data was written")


# =============================================================================
# Node Implementation
# =============================================================================


@NodeRegistry.register
class SparkFromPostgresToS3Node(
    BaseNode[SparkFromPostgresToS3Input, SparkFromPostgresToS3Output]
):
    """Reads a PostgreSQL table via Spark and writes parquet to S3."""

    node_type = "spark_from_postgres_to_s3"
    title = "Spark: Postgres → S3"
    description = (
        "Reads data from PostgreSQL table using Spark and saves as parquet to S3"
    )
    category = "data"
    input_schema = SparkFromPostgresToS3Input
    output_schema = SparkFromPostgresToS3Output

    def execute(
        self, inputs: SparkFromPostgresToS3Input, logger: logging.Logger
    ) -> SparkFromPostgresToS3Output:
        """Execute: read PostgreSQL → write parquet to S3."""
        from pyspark.sql import SparkSession

        s3 = inputs.s3_connection
        s3_path = inputs.s3_output_path.rstrip("/")
        s3_path = f"s3a://{inputs.s3_connection.default_bucket}/{inputs.s3_output_path.strip('/')}/"

        # Build JDBC URL
        pg = inputs.postgres_connection
        password = pg.password.get_value()
        jdbc_url = (
            f"jdbc:postgresql://{pg.host}:{pg.port}/{pg.database}"
            f"?user={pg.username}&password={password}"
        )

        # Build Spark session with S3A config for MinIO
        protocol = "https" if s3.use_ssl else "http"
        s3_endpoint = f"{protocol}://{s3.endpoint}"

        # Ivy package resolution — downloads JARs at runtime from Maven Central
        packages = ",".join([
            "org.postgresql:postgresql:42.7.1",
            "org.apache.hadoop:hadoop-aws:3.3.4",
            "com.amazonaws:aws-java-sdk-bundle:1.12.262",
        ])

        spark = (
            SparkSession.builder.appName(inputs.spark_app_name)
            .master(inputs.spark_connection.master_url)
            .config("spark.hadoop.fs.s3a.access.key", s3.access_key.get_value())
            .config("spark.hadoop.fs.s3a.secret.key", s3.secret_key.get_value())
            .config("spark.hadoop.fs.s3a.endpoint", s3_endpoint)
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.endpoint.region", s3.region)
            # Magic committer — prevents costly COMMIT calls on S3
            .config("spark.hadoop.fs.s3a.committer.magic.enabled", "true")
            .config(
                "spark.sql.sources.outputCommitterClass",
                "org.apache.spark.sql.execution.datasources.SQLHadoopMapReduceCommitProtocol",
            )
            .config("spark.jars.packages", packages)
            .config("spark.jars.ivy", "/tmp/ivy2")
            .getOrCreate()
        )

        try:
            logger.info(
                f"Reading table '{inputs.table}' from PostgreSQL at {pg.host}:{pg.port}"
            )

            # Read from PostgreSQL via JDBC
            df = (
                spark.read.format("jdbc")
                .option("url", jdbc_url)
                .option("dbtable", inputs.table)
                .option("driver", "org.postgresql.Driver")
                .load()
            )

            row_count = df.count()
            logger.info(f"Read {row_count} rows from '{inputs.table}'")

            # Write to S3 as parquet
            logger.info(f"Writing {row_count} rows to S3: {s3_path}")
            df.write.mode("overwrite").parquet(s3_path)

            return SparkFromPostgresToS3Output(
                row_count=row_count,
                s3_output_path=s3_path,
            )
        finally:
            spark.stop()
