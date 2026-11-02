"""Initial schema

Creates every table, constraint and (partial) unique index from the SQLAlchemy models.

NOTE: this baseline migration builds the schema from the model metadata as it exists at
this revision. All FUTURE schema changes must be created with
`alembic revision --autogenerate -m "..."` so they contain explicit operations.

Revision ID: 0001
Revises:
Create Date: 2026-11-02
"""
from alembic import op

import app.models  # noqa: F401
from app.db.base import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
