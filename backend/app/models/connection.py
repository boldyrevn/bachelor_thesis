"""Connection model for storing external data source credentials."""

import enum
import uuid
from typing import Any, Optional

from sqlalchemy import Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ConnectionType(str, enum.Enum):
    """Supported connection types."""

    POSTGRES = "postgres"
    CLICKHOUSE = "clickhouse"
    S3 = "s3"
    SPARK = "spark"


class Connection(Base, TimestampMixin):
    """Represents a connection to an external data source.

    Stores connection configuration and secrets securely.
    Referenced by pipeline nodes for data access.
    """

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    connection_type: Mapped[ConnectionType] = mapped_column(
        Enum(ConnectionType), nullable=False, index=True
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    secrets: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Connection(id={self.id}, name={self.name}, type={self.connection_type})>"
        )
