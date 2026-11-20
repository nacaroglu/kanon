"""create procedures and procedure_sections

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "procedures",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("commit_hash", sa.String(length=64), nullable=False),
        sa.Column("blob_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_procedures"),
        sa.UniqueConstraint("commit_hash", "path", name="uq_procedures_commit_hash_path"),
    )
    op.create_table(
        "procedure_sections",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("procedure_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_procedure_sections_position_non_negative")
        ),
        sa.CheckConstraint(
            "start_offset >= 0", name=op.f("ck_procedure_sections_start_offset_non_negative")
        ),
        sa.CheckConstraint(
            "end_offset >= start_offset", name=op.f("ck_procedure_sections_end_after_start")
        ),
        sa.CheckConstraint(
            "level IS NULL OR level BETWEEN 1 AND 6", name=op.f("ck_procedure_sections_level_range")
        ),
        sa.ForeignKeyConstraint(
            ["procedure_id"],
            ["procedures.id"],
            name="fk_procedure_sections_procedure_id_procedures",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_procedure_sections"),
        sa.UniqueConstraint(
            "procedure_id", "position", name="uq_procedure_sections_procedure_position"
        ),
    )


def downgrade() -> None:
    op.drop_table("procedure_sections")
    op.drop_table("procedures")
