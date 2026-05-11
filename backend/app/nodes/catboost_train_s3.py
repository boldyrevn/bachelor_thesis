"""CatBoostTrainS3 node — trains a CatBoost model on data from S3 and saves it."""

import io
import logging

import boto3
import joblib
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from pydantic import BaseModel, ConfigDict, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry
from app.schemas.connection import S3Connection


# =============================================================================
# Typed Input / Output Schemas
# =============================================================================


class CatBoostTrainS3Input(BaseModel):
    """Input parameters for CatBoostTrainS3 node."""

    s3_connection: S3Connection = Field(
        description="S3/MinIO connection to read data and save model",
    )
    s3_data_path: str = Field(
        description="S3 path to read training data as parquet (e.g. 's3://artifacts/transformed/')",
    )
    s3_model_path: str = Field(
        description="S3 path to save the trained model (e.g. 's3://models/catboost_v1/')",
    )
    target_column: str = Field(
        description="Name of the target column in the dataset",
    )
    cat_features: str = Field(
        default="",
        description="Comma-separated list of categorical feature column names (e.g. 'category,region')",
    )
    task_type: str = Field(
        default="classification",
        description="Task type: 'classification' or 'regression'",
    )
    iterations: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Number of training iterations",
    )


class CatBoostTrainS3Output(BaseModel):
    """Output artifacts for CatBoostTrainS3 node."""

    model_config = ConfigDict(protected_namespaces=())

    model_path: str = Field(description="S3 path where the model was saved")
    train_accuracy: float = Field(description="Training accuracy (classification) or R² (regression)")


# =============================================================================
# Node Implementation
# =============================================================================


@NodeRegistry.register
class CatBoostTrainS3Node(BaseNode[CatBoostTrainS3Input, CatBoostTrainS3Output]):
    """Trains a CatBoost model on parquet data from S3 and saves it back to S3."""

    node_type = "catboost_train_s3"
    title = "CatBoost: Train"
    description = "Reads parquet from S3, trains CatBoost model, saves model to S3"
    category = "ml"
    input_schema = CatBoostTrainS3Input
    output_schema = CatBoostTrainS3Output

    def execute(
        self, inputs: CatBoostTrainS3Input, logger: logging.Logger
    ) -> CatBoostTrainS3Output:
        """Execute: read parquet from S3 → train CatBoost → save model to S3."""
        s3 = inputs.s3_connection
        protocol = "https" if s3.use_ssl else "http"
        endpoint_url = f"{protocol}://{s3.endpoint}"

        # Setup S3 client
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=s3.access_key.get_value(),
            aws_secret_access_key=s3.secret_key.get_value(),
            region_name=s3.region,
        )

        # Parse S3 data path
        data_bucket, data_key = self._parse_s3_path(inputs.s3_data_path)

        logger.info(f"Downloading parquet data from S3: s3://{data_bucket}/{data_key}")

        # Spark writes parquet as a directory — download all .parquet files
        objects = s3_client.list_objects_v2(Bucket=data_bucket, Prefix=data_key)
        parquet_files = [
            obj["Key"] for obj in objects.get("Contents", [])
            if obj["Key"].endswith(".parquet")
        ]

        if not parquet_files:
            raise ValueError(f"No parquet files found at s3://{data_bucket}/{data_key}")

        logger.info(f"Found {len(parquet_files)} parquet file(s)")

        # Download all parquet files and concatenate
        frames = []
        for key in parquet_files:
            response = s3_client.get_object(Bucket=data_bucket, Key=key)
            data_bytes = response["Body"].read()
            df_part = pd.read_parquet(io.BytesIO(data_bytes))
            frames.append(df_part)
            logger.info(f"  Loaded {key} — {len(df_part)} rows")

        df = pd.concat(frames, ignore_index=True)
        logger.info(f"Combined dataframe shape: {df.shape}, columns: {list(df.columns)}")

        # Parse categorical features
        cat_features = [c.strip() for c in inputs.cat_features.split(",") if c.strip()]

        # Prepare features and target
        target = df[inputs.target_column]
        features = df.drop(columns=[inputs.target_column])

        # Train model
        logger.info(
            f"Training CatBoost: {inputs.task_type}, {inputs.iterations} iterations, "
            f"features={len(features.columns)}, cat_features={cat_features}"
        )

        is_classification = inputs.task_type == "classification"
        model = (
            CatBoostClassifier(
                iterations=inputs.iterations,
                cat_features=cat_features,
                verbose=0,
            )
            if is_classification
            else CatBoostRegressor(
                iterations=inputs.iterations,
                cat_features=cat_features,
                verbose=0,
            )
        )

        model.fit(features, target)

        # Calculate metric
        if is_classification:
            train_accuracy = float(model.score(features, target))
            logger.info(f"Training accuracy: {train_accuracy:.4f}")
        else:
            train_accuracy = float(model.score(features, target))
            logger.info(f"Training R²: {train_accuracy:.4f}")

        # Save model to S3
        model_bytes = io.BytesIO()
        joblib.dump(model, model_bytes)
        model_bytes.seek(0)

        model_bucket, model_key = self._parse_s3_path(inputs.s3_model_path)
        s3_client.put_object(
            Bucket=model_bucket, Key=model_key, Body=model_bytes.read()
        )
        logger.info(f"Model saved to S3: {inputs.s3_model_path}")

        return CatBoostTrainS3Output(
            model_path=inputs.s3_model_path,
            train_accuracy=round(train_accuracy, 4),
        )

    @staticmethod
    def _parse_s3_path(path: str) -> tuple[str, str]:
        """Parse S3 path into (bucket, key).

        Handles both 's3://bucket/key' and 'bucket/key' formats.
        """
        path = path.strip("/")
        if path.startswith("s3://"):
            path = path[5:]
        elif path.startswith("s3a://"):
            path = path[6:]
        bucket, key = path.split("/", 1)
        return bucket, key
