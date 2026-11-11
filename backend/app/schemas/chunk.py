"""
TrustRAG Ingestion Schemas: Document Chunk Models & Pipeline Output Contracts
Adheres strictly to docs/architecture/data-models.md and docs/architecture/ingestion-pipeline.md.
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.document import DocumentRecord


class DocumentChunk(BaseModel):
    """
    Represents an individual chunk extracted with provenance metadata.
    Does not invent page numbers for unpaginated documents.
    """
    chunk_id: str = Field(..., description="Unique composite identifier: {doc_id}_p{page:03d}_c{idx:04d} or {doc_id}_c{idx:04d}")
    doc_id: str = Field(..., description="Foreign key reference to DocumentRecord.doc_id")
    filename: str = Field(..., description="Original filename for provenance attribution")
    file_hash: str = Field(..., description="SHA-256 hash of parent document")
    page_number: Optional[int] = Field(None, ge=1, description="1-based page number for paged documents; None for unpaged")
    section_title: Optional[str] = Field(None, description="Enclosing heading / section title if available")
    chunk_index: int = Field(..., ge=0, description="Sequential index of this chunk within the document")
    char_start: int = Field(..., ge=0, description="Character start offset within page or document")
    char_end: int = Field(..., ge=0, description="Character end offset within page or document")
    text: str = Field(..., min_length=1, description="Cleaned, normalized text content of chunk")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestionResult(BaseModel):
    """
    Complete structured output returned by the Ingestion Pipeline.
    """
    document: DocumentRecord
    chunks: List[DocumentChunk]
    total_characters: int = Field(..., ge=0, description="Total characters extracted across all chunks")
    processing_time_ms: float = Field(..., ge=0.0, description="Pipeline latency in milliseconds")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings encountered during extraction")

