"""align sentiment_metrics schema with current ORM

Revision ID: b1c2d3e4f5ab
Revises: 6694fbaad3c6
Create Date: 2025-06-25 17:43:00.000000

This migration removes the legacy `metric_name`-based design and makes the
primary-key match `SentimentMetricORM` (time_bucket, source, source_id, label).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b1c2d3e4f5ab"
down_revision: Union[str, None] = "6694fbaad3c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "sentiment_metrics"
OLD_PK = "pk_sentiment_metric"  # name from original model
NEW_PK = "pk_sentiment_metric"  # we will reuse the same name for clarity

LEGACY_COLUMNS = [
    "metric_name",
    "metric_value_int",
    "metric_value_float",
    "metric_value_json",
    # metric_timestamp cannot be dropped directly because it is the hypertable
    # partitioning dimension. We rename it to `time_bucket` instead.
    "tags",
    "source_component",
    "model_version",
]

def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Drop existing primary key (likely includes metric_name)
    pk_constraints = inspector.get_pk_constraint(TABLE)
    if pk_constraints and pk_constraints.get("name"):
        op.drop_constraint(pk_constraints["name"], TABLE, type_="primary")

    existing_cols = {c["name"] for c in inspector.get_columns(TABLE)}

    # 2. Ensure we have a `time_bucket` mirror column for ORM compatibility.
    if "time_bucket" not in existing_cols:
        op.add_column(TABLE, sa.Column("time_bucket", sa.TIMESTAMP(timezone=True), nullable=True))
        # Back-fill from metric_timestamp (partition column)
        op.execute(f"UPDATE {TABLE} SET time_bucket = metric_timestamp")
        # Now set NOT NULL
        op.alter_column(TABLE, "time_bucket", nullable=False)
        existing_cols.add("time_bucket")

    # 3. Drop other legacy columns that are no longer needed.
    for col in LEGACY_COLUMNS:
        if col in existing_cols:
            op.drop_column(TABLE, col)

    # 4. Create new primary key aligned with partitioning requirement (metric_timestamp)

    op.create_primary_key(NEW_PK, TABLE, [
        "metric_timestamp",
        "source",
        "source_id",
        "label",
    ])


def downgrade() -> None:
    """Best-effort restore of legacy design (metric_name nullable)."""
    # 1. Drop new PK
    op.drop_constraint(NEW_PK, TABLE, type_="primary")

    # 2. Recreate metric_name column (nullable) so legacy queries don’t break
    op.add_column(TABLE, sa.Column("metric_name", sa.Text(), nullable=True))

    # 3. Recreate old PK including metric_name (still allowing NULL until back-filled)
    op.create_primary_key(OLD_PK, TABLE, [
        "time_bucket",
        "source",
        "source_id",
        "label",
        "metric_name",
    ])
