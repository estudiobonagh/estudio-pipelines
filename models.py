"""Pydantic data models and enums for the document pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---


class DocumentType(str, Enum):
    """Types of financial documents the classifier can identify."""

    FACTURA = "Factura"
    RECIBO = "Recibo"
    COMPROBANTE = "Comprobante"
    EXTRACTO = "Extracto"
    OTRO = "Otro"


class ProcessingStatus(str, Enum):
    """Lifecycle status of a document through the pipeline."""

    RECEIVED = "received"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    STORED = "stored"
    CONFIRMATION_SENT = "confirmation_sent"
    LOW_CONFIDENCE = "low_confidence"
    CLASSIFICATION_FAILED = "classification_failed"
    DOWNLOAD_FAILED = "download_failed"
    DRIVE_ERROR = "drive_error"
    IGNORED_NO_MEDIA = "ignored_no_media"
    IGNORED_UNSUPPORTED_TYPE = "ignored_unsupported_type"


# --- Core Models ---


class ClassificationResult(BaseModel):
    """Structured classification returned by Grok.

    Confidence must be between 0.0 and 1.0.
    """

    cliente: str = ""
    tipo_documento: str = ""
    periodo: str = ""  # MM-YYYY
    proveedor: str = ""
    monto: float = 0.0
    confianza: float = Field(ge=0.0, le=1.0)


class ProcessingRecord(BaseModel):
    """Full processing log entry — matches the SQLite schema."""

    id: Optional[int] = None
    sender_phone: str
    filename: str
    media_content_type: str
    classification_json: Optional[str] = None
    client_name: Optional[str] = None
    document_type: Optional[str] = None
    period: Optional[str] = None
    confidence: Optional[float] = None
    drive_file_id: Optional[str] = None
    drive_folder_path: Optional[str] = None
    status: ProcessingStatus = ProcessingStatus.RECEIVED
    error_message: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class HealthCheck(BaseModel):
    """Response from GET /health."""

    status: str  # "ok" | "degraded"
    uptime_seconds: float
    checks: dict[str, str]


class StatsResponse(BaseModel):
    """Response from GET /stats."""

    total: int
    successful: int  # confirmation_sent
    pending_review: int  # low_confidence
    failed: int  # classification_failed + drive_error
    ignored: int  # ignored_*
