"""CatBoostPredictS3 node — loads a trained model and data from S3, makes predictions."""

import io
import logging

import boto3
import joblib
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from app.nodes.base import BaseNode
from app.nodes.registry import NodeRegistry
from app.schemas.connection import S3Connection


# =============================================================================
# Typed Input / Output Schemas
# =============================================================================


class CatBoostPredictS3Input(BaseModel):
    """Input parameters for CatBoostPredictS3 node."""

    s3_connection: S3Connection = Field(
        description="S3/MinIO connection for model and data",
    )
    s3_model_path: str = Field(
        description="S3 path to the trained model file (e.g. 's3://models/titanic_v1.joblib')",
    )
    s3_data_path: str = Field(
        description="S3 path to read data for prediction (parquet, e.g. 's3://artifacts/transformed/')",
    )
    s3_predictions_path: str = Field(
        description="S3 path to save predictions as CSV (e.g. 's3://artifacts/predictions.csv')",
    )


class CatBoostPredictS3Output(BaseModel):
    """Output artifacts for CatBoostPredictS3 node."""

    model_config = ConfigDict(protected_namespaces=())

    predictions_path: str = Field(description="S3 path where predictions CSV was saved")
    prediction_count: int = Field(description="Number of predictions made")


# =============================================================================
# Node Implementation
# =============================================================================


@NodeRegistry.register
class CatBoostPredictS3Node(BaseNode[CatBoostPredictS3Input, CatBoostPredictS3Output]):
    """Loads a trained CatBoost model from S3, predicts on data from S3, saves results."""

    node_type = "catboost_predict_s3"
    title = "CatBoost: Predict"
    description = (
        "Loads CatBoost model from S3, makes predictions on parquet data, saves CSV"
    )
    category = "ml"
    input_schema = CatBoostPredictS3Input
    output_schema = CatBoostPredictS3Output

    def execute(
        self, inputs: CatBoostPredictS3Input, logger: logging.Logger
    ) -> CatBoostPredictS3Output:
        """Execute: load model → predict → save predictions to S3."""
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

        # Load model
        model_bucket, model_key = self._parse_s3_path(inputs.s3_model_path)
        logger.info(f"Loading model from S3: s3://{model_bucket}/{model_key}")
        response = s3_client.get_object(Bucket=model_bucket, Key=model_key)
        model = joblib.load(io.BytesIO(response["Body"].read()))
        logger.info(f"Model loaded: {type(model).__name__}")

        # Load data (Spark parquet directory)
        data_bucket, data_key = self._parse_s3_path(inputs.s3_data_path)
        objects = s3_client.list_objects_v2(Bucket=data_bucket, Prefix=data_key)
        parquet_files = [
            obj["Key"] for obj in objects.get("Contents", [])
            if obj["Key"].endswith(".parquet")
        ]

        if not parquet_files:
            raise ValueError(f"No parquet files found at s3://{data_bucket}/{data_key}")

        logger.info(f"Loading {len(parquet_files)} parquet file(s) for prediction")
        frames = []
        for key in parquet_files:
            resp = s3_client.get_object(Bucket=data_bucket, Key=key)
            frames.append(pd.read_parquet(io.BytesIO(resp["Body"].read())))

        df = pd.concat(frames, ignore_index=True)
        logger.info(f"Data shape: {df.shape}, columns: {list(df.columns)}")

        # Make predictions
        logger.info(f"Making predictions on {len(df)} rows")
        predictions = model.predict(df)

        # Save predictions as CSV
        pred_df = pd.DataFrame({"prediction": predictions})
        csv_buffer = io.BytesIO()
        pred_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        pred_bucket, pred_key = self._parse_s3_path(inputs.s3_predictions_path)
        s3_client.put_object(
            Bucket=pred_bucket, Key=pred_key, Body=csv_buffer.read()
        )
        logger.info(f"Predictions saved to S3: {inputs.s3_predictions_path}")

        return CatBoostPredictS3Output(
            predictions_path=inputs.s3_predictions_path,
            prediction_count=len(predictions),
        )

    @staticmethod
    def _parse_s3_path(path: str) -> tuple[str, str]:
        """Parse S3 path into (bucket, key)."""
        path = path.strip("/")
        if path.startswith("s3://"):
            path = path[5:]
        elif path.startswith("s3a://"):
            path = path[6:]
        bucket, key = path.split("/", 1)
        return bucket, key
