"""SQLite database layer — async engine, ORM, CRUD operations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from models import ProcessingStatus


class Base(DeclarativeBase):
    pass


class ProcessingLog(Base):
    """Processing log table — tracks every document through the pipeline."""

    __tablename__ = "processing_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_phone: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    media_content_type: Mapped[str] = mapped_column(String, nullable=False)
    classification_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    period: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    drive_file_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    drive_folder_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=ProcessingStatus.RECEIVED.value
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


async def init_db(
    database_path: str,
) -> tuple:
    """Create async engine and session factory. Creates tables if needed.

    Returns (engine, sessionmaker).
    """
    # Ensure parent directory exists
    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    return engine, session_factory


async def create_log(
    session: AsyncSession,
    sender_phone: str,
    filename: str,
    media_content_type: str,
    status: str = ProcessingStatus.RECEIVED.value,
) -> ProcessingLog:
    """Insert a new processing log entry and return the ORM object."""
    now = _now_iso()
    record = ProcessingLog(
        sender_phone=sender_phone,
        filename=filename,
        media_content_type=media_content_type,
        status=status,
        created_at=now,
        updated_at=now,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def update_log(
    session: AsyncSession,
    log_id: int,
    status: str,
    **extra_fields: object,
) -> None:
    """Update status and optional extra fields. Sets updated_at to now."""
    record = await session.get(ProcessingLog, log_id)
    if record is None:
        return

    record.status = status
    record.updated_at = _now_iso()

    for field, value in extra_fields.items():
        if hasattr(record, field):
            setattr(record, field, value)

    await session.commit()


async def get_stats(session: AsyncSession) -> dict:
    """Return aggregate processing counts for the /stats endpoint."""
    from sqlalchemy import func, select

    stmt_total = select(func.count()).select_from(ProcessingLog)
    stmt_successful = select(func.count()).where(
        ProcessingLog.status == ProcessingStatus.CONFIRMATION_SENT.value
    )
    stmt_pending = select(func.count()).where(
        ProcessingLog.status == ProcessingStatus.LOW_CONFIDENCE.value
    )
    stmt_failed = select(func.count()).where(
        ProcessingLog.status.in_(
            [
                ProcessingStatus.CLASSIFICATION_FAILED.value,
                ProcessingStatus.DRIVE_ERROR.value,
            ]
        )
    )
    stmt_ignored = select(func.count()).where(
        ProcessingLog.status.like("ignored_%")
    )

    total = (await session.execute(stmt_total)).scalar() or 0
    successful = (await session.execute(stmt_successful)).scalar() or 0
    pending_review = (await session.execute(stmt_pending)).scalar() or 0
    failed = (await session.execute(stmt_failed)).scalar() or 0
    ignored = (await session.execute(stmt_ignored)).scalar() or 0

    return {
        "total": total,
        "successful": successful,
        "pending_review": pending_review,
        "failed": failed,
        "ignored": ignored,
    }


async def check_duplicate(
    session: AsyncSession,
    sender_phone: str,
    filename: str,
) -> bool:
    """Check if the same sender sent the same filename in the last 24 hours."""
    from datetime import timedelta

    from sqlalchemy import select

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    stmt = select(ProcessingLog).where(
        ProcessingLog.sender_phone == sender_phone,
        ProcessingLog.filename == filename,
        ProcessingLog.created_at >= cutoff,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None
