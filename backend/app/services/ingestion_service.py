"""
TrustRAG Unified Document Ingestion Service
Orchestrates validation, extraction, cleaning, chunking, and metadata provenance tagging.
Adheres strictly to docs/architecture/ingestion-pipeline.md and data-models.md.
"""

import time
from pathlib import Path
from typing import List, Optional

from backend.app.core.errors import (
    ExtractionError,
    FileValidationError,
    IngestionError,
)
from backend.app.schemas.chunk import DocumentChunk, IngestionResult
from backend.app.schemas.document import (
    DocumentPage,
    DocumentRecord,
    DocumentStatusEnum,
    DocumentTypeEnum,
)
from backend.app.services.chunker import RecursiveContextChunker
from backend.app.services.document_validator import DocumentValidator
from backend.app.services.docx_extractor import DOCXExtractor
from backend.app.services.pdf_extractor import PDFExtractor
from backend.app.services.txt_extractor import TXTExtractor


class IngestionService:
    """
    Central orchestration service for the TrustRAG Ingestion Pipeline.
    Validates, extracts, normalizes, and chunks PDF, DOCX, and TXT files.
    """

    def __init__(
        self,
        validator: Optional[DocumentValidator] = None,
        chunker: Optional[RecursiveContextChunker] = None,
    ):
        self.validator = validator or DocumentValidator()
        self.chunker = chunker or RecursiveContextChunker()

    @staticmethod
    def generate_doc_id(sha256_hash: str) -> str:
        """
        Generates standard deterministic doc_id from first 8 chars of SHA-256 hash.
        Example: doc_a3f89b12
        """
        return f"doc_{sha256_hash[:8]}"

    def ingest_file(self, file_path_str: str) -> IngestionResult:
        """
        Executes end-to-end ingestion pipeline for a given document path.
        Returns IngestionResult with complete provenance and chunks.
        """
        start_time = time.perf_counter()
        warnings: List[str] = []
        path = Path(file_path_str)

        # 1. Validation & Security Phase
        val_result = self.validator.validate(str(path))
        file_type = val_result.file_type
        sha256_hash = val_result.sha256_hash
        file_size = val_result.file_size_bytes
        sanitized_filename = self.validator.sanitize_filename(path.name)
        doc_id = self.generate_doc_id(sha256_hash)

        # 2. Format-Specific Content Extraction Phase
        pages: List[DocumentPage] = []
        total_pages: Optional[int] = None

        try:
            if file_type == DocumentTypeEnum.PDF:
                pages = PDFExtractor.extract(path)
                total_pages = len(pages)
            elif file_type == DocumentTypeEnum.DOCX:
                pages = DOCXExtractor.extract(path)
                total_pages = None  # Flowable format, unpaged
            elif file_type == DocumentTypeEnum.TXT:
                pages = TXTExtractor.extract(path)
                total_pages = None  # Flat text, unpaged
            else:
                raise FileValidationError(
                    f"Unsupported document format: {file_type}",
                    error_code="UNSUPPORTED_TYPE"
                )
        except IngestionError:
            raise
        except Exception as e:
            raise ExtractionError(
                f"Unexpected failure during content extraction from '{sanitized_filename}': {e}",
                error_code="EXTRACTION_FAILURE",
                details={"filename": sanitized_filename, "error": str(e)}
            )

        # 3. Context-Preserving Chunking & Provenance Phase
        try:
            chunks: List[DocumentChunk] = self.chunker.chunk_document(
                pages=pages,
                doc_id=doc_id,
                filename=sanitized_filename,
                file_hash=sha256_hash,
            )
        except Exception as e:
            raise IngestionError(
                f"Unexpected failure during document chunking for '{sanitized_filename}': {e}",
                error_code="CHUNKING_FAILURE",
                details={"filename": sanitized_filename, "error": str(e)}
            )

        total_characters = sum(len(c.text) for c in chunks)

        # 4. Construct Document Record
        doc_record = DocumentRecord(
            doc_id=doc_id,
            filename=sanitized_filename,
            file_type=file_type,
            file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            total_pages=total_pages,
            total_chunks=len(chunks),
            status=DocumentStatusEnum.INGESTED,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return IngestionResult(
            document=doc_record,
            chunks=chunks,
            total_characters=total_characters,
            processing_time_ms=round(elapsed_ms, 2),
            warnings=warnings,
        )

