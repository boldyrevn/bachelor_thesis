"""SparkTransformS3 node — reads parquet from S3, applies SQL transform, writes back."""

import logging

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry
from app.schemas.connection import S3Connection, SparkConnection
from app.schemas.node_types import MultilineStr


# =============================================================================
# Typed Input / Output Schemas
# =============================================================================


class SparkTransformS3Input(BaseModel):
    """Input parameters for SparkTransformS3 node."""

    spark_connection: SparkConnection = Field(
        description="Spark connection to use for execution",
    )
    s3_connection: S3Connection = Field(
        description="S3/MinIO connection to read/write data",
    )
    s3_input_path: str = Field(
        description="S3 path to read parquet from (e.g. 's3://artifacts/raw_data/')",
    )
    s3_output_path: str = Field(
        description="S3 path to write transformed parquet (e.g. 's3://artifacts/transformed/')",
    )
    spark_app_name: str = Field(
        default="FlowForge_SparkTransform",
        description="Spark application name",
    )
    transform_sql: MultilineStr = Field(
        description=(
            "SQL query to transform data. "
            "Input data is available as temp view 'df'. "
            "Example: SELECT *, price * quantity AS total FROM df WHERE price IS NOT NULL"
        ),
    )


class SparkTransformS3Output(BaseModel):
    """Output artifacts for SparkTransformS3 node."""

    row_count: int = Field(description="Number of rows after transformation")
    s3_output_path: str = Field(description="S3 path where data was written")


# =============================================================================
# Node Implementation
# =============================================================================


@NodeRegistry.register
class SparkTransformS3Node(BaseNode[SparkTransformS3Input, SparkTransformS3Output]):
    """Reads parquet from S3, applies SQL transformation, writes back to S3."""

    node_type = "spark_transform_s3"
    title = "Spark: Transform S3"
    description = "Reads parquet from S3, applies SQL transform, writes result back"
    category = "transform"
    input_schema = SparkTransformS3Input
    output_schema = SparkTransformS3Output

    def execute(
        self, inputs: SparkTransformS3Input, logger: logging.Logger
    ) -> SparkTransformS3Output:
        """Execute: read parquet → SQL transform → write parquet."""
        from pyspark.sql import SparkSession

        s3 = inputs.s3_connection
        s3_input = inputs.s3_input_path.rstrip("/")
        s3_output = inputs.s3_output_path.rstrip("/")

        # Build Spark session with S3A config for MinIO
        protocol = "https" if s3.use_ssl else "http"
        s3_endpoint = f"{protocol}://{s3.endpoint}"

        packages = ",".join([
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
            # Magic committer
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
            logger.info(f"Reading parquet from S3: {s3_input}")

            # Read parquet
            df = spark.read.parquet(s3_input)
            logger.info(f"Read {df.count()} rows from S3")

            # Register as temp view for SQL queries
            df.createOrReplaceTempView("df")

            # Apply user's SQL transform
            logger.info(f"Applying transform SQL:\n{inputs.transform_sql}")
            result_df = spark.sql(inputs.transform_sql)

            row_count = result_df.count()
            logger.info(f"Transformation result: {row_count} rows")

            # Write back to S3
            logger.info(f"Writing {row_count} rows to S3: {s3_output}")
            result_df.write.mode("overwrite").parquet(s3_output)

            return SparkTransformS3Output(
                row_count=row_count,
                s3_output_path=s3_output,
            )
        finally:
            spark.stop()
