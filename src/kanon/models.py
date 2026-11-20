"""SQLAlchemy models.

Git stays canonical for procedures; their tables are a queryable copy tied to a commit.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Explicit constraint names keep migrations and the models in agreement.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Procedure(Base):
    """One procedure file as it was at one commit of the approved repository."""

    __tablename__ = "procedures"
    __table_args__ = (
        # The natural key: a path appears once per commit. This is what makes re-importing
        # the same commit impossible to duplicate.
        UniqueConstraint("commit_hash", "path", name="uq_procedures_commit_hash_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(Text)  # repository-relative, e.g. procedures/a.md
    title: Mapped[str] = mapped_column(Text)
    commit_hash: Mapped[str] = mapped_column(String(64))  # the version of the repository
    blob_hash: Mapped[str] = mapped_column(String(64))  # the version of this file

    sections: Mapped[list["ProcedureSection"]] = relationship(
        back_populates="procedure",
        order_by="ProcedureSection.position",
        cascade="all, delete-orphan",
        passive_deletes=True,  # the database cascades; do not load rows just to delete them
    )


class ProcedureSection(Base):
    __tablename__ = "procedure_sections"
    __table_args__ = (
        UniqueConstraint(
            "procedure_id", "position", name="uq_procedure_sections_procedure_position"
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint("start_offset >= 0", name="start_offset_non_negative"),
        CheckConstraint("end_offset >= start_offset", name="end_after_start"),
        CheckConstraint("level IS NULL OR level BETWEEN 1 AND 6", name="level_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    procedure_id: Mapped[int] = mapped_column(
        ForeignKey("procedures.id", ondelete="CASCADE"), index=False
    )
    position: Mapped[int] = mapped_column(Integer)  # 0-based order within the file
    heading: Mapped[str | None] = mapped_column(Text)  # NULL for the preamble
    level: Mapped[int | None] = mapped_column(Integer)  # 1-6, NULL for the preamble
    text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer)  # characters into the file at blob_hash
    end_offset: Mapped[int] = mapped_column(Integer)  # exclusive

    procedure: Mapped[Procedure] = relationship(back_populates="sections")


class SourceType(enum.StrEnum):
    """The input categories v1 supports (Product Scope 1.3, section 2.3)."""

    MARKDOWN = "markdown"
    TXT = "txt"
    PDF = "pdf"
    DOCX = "docx"
    TRANSCRIPT = "transcript"
    TICKET_EXPORT = "ticket_export"


SOURCE_TYPE_VALUES = tuple(t.value for t in SourceType)


class Source(Base):
    """A submitted source document. The file itself is kept on disk, named by its hash.

    Authority and effective date are added by a later migration, on purpose.
    """

    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(
            "type IN (" + ", ".join(f"'{v}'" for v in SOURCE_TYPE_VALUES) + ")",
            name="type_known",
        ),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # What the submitter called the file. Untrusted text: display only, never a path.
    original_filename: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 of the bytes, lowercase hex
    stored_path: Mapped[str] = mapped_column(Text)  # where the bytes live, derived from the hash
    type: Mapped[SourceType] = mapped_column(
        Enum(
            SourceType,
            native_enum=False,
            create_constraint=False,  # the named CheckConstraint above is the constraint
            length=20,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
