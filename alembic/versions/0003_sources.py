"""create sources

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_TYPES = ("markdown", "txt", "pdf", "docx", "transcript", "ticket_export")


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN (" + ", ".join(f"'{t}'" for t in SOURCE_TYPES) + ")",
            name=op.f("ck_sources_type_known"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_sources_content_hash_sha256")
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
    )


def downgrade() -> None:
    op.drop_table("sources")
