"""
TrustRAG Ingestion Schemas: Document Models & Validation Contracts
Adheres strictly to docs/architecture/data-models.md and docs/architecture/ingestion-pipeline.md.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class DocumentTypeEnum(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class DocumentStatusEnum(str, Enum):
    INGESTED = "INGESTED"
    NEEDS_OCR = "NEEDS_OCR"
    ENCRYPTED_DOCUMENT = "ENCRYPTED_DOCUMENT"
    CORRUPTED_DOCUMENT = "CORRUPTED_DOCUMENT"
    UNREADABLE_DOCUMENT = "UNREADABLE_DOCUMENT"
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"


class DocumentPage(BaseModel):
    """
    Extracted structural unit of a document.
    Page number is strictly 1-based for paginated formats (PDF) and None for unpaginated (DOCX/TXT).
    """
    page_number: Optional[int] = Field(None, ge=1, description="1-based page index for paged documents; None if unpaged")
    section_title: Optional[str] = Field(None, description="Enclosing section header or heading")
    text: str = Field(..., description="Extracted raw or normalized text from page/section")
    char_count: int = Field(..., ge=0, description="Character count in this page/section")


class DocumentRecord(BaseModel):
    """
    Represents an ingested document registered in the system.
    """
    doc_id: str = Field(..., description="Unique hash-based document identifier (e.g., doc_a3f89b)")
    filename: str = Field(..., description="Original filename without path traversal")
    file_type: DocumentTypeEnum = Field(..., description="Validated document format: pdf, docx, txt")
    file_size_bytes: int = Field(..., ge=1, description="Size in bytes")
    sha256_hash: str = Field(..., description="SHA-256 cryptographic checksum")
    total_pages: Optional[int] = Field(None, ge=1, description="Total pages parsed if applicable")
    total_chunks: int = Field(..., ge=0, description="Total chunks generated")
    status: DocumentStatusEnum = Field(default=DocumentStatusEnum.INGESTED, description="Ingestion outcome status")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationResult(BaseModel):
    """
    Outcome of pre-ingestion file validation.
    """
    is_valid: bool
    file_type: Optional[DocumentTypeEnum] = None
    sha256_hash: Optional[str] = None
    file_size_bytes: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

