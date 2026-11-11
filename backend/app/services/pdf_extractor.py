"""
TrustRAG PDF Extractor Service
Extracts page-level text, coordinates, and structural blocks using PyMuPDF (fitz).
Detects scanned/image-only PDFs (NEEDS_OCR), encrypted files, and corrupted binaries.
Adheres strictly to docs/architecture/ingestion-pipeline.md (Section 3.2).
"""

from pathlib import Path
from typing import List

try:
    import pymupdf  # Modern PyMuPDF API
except ImportError:
    import fitz as pymupdf  # Fallback for legacy import names

from backend.app.core.errors import (
    CorruptedFileError,
    EncryptedDocumentError,
    ExtractionError,
    NeedsOCRError,
)
from backend.app.schemas.document import DocumentPage
from backend.app.services.text_cleaner import TextCleaner


class PDFExtractor:
    """
    Robust page-by-page PDF parser utilizing PyMuPDF.
    Preserves exact 1-based page numbering and detects non-extractable text layers.
    """

    # Threshold for detecting scanned image-only PDFs (fewer than 20 printable characters across pages)
    MIN_CHARACTERS_FOR_TEXT_LAYER = 20

    # Margin fraction to discard running headers and footers (top 5% and bottom 5% of page height)
    HEADER_FOOTER_MARGIN_RATIO = 0.05

    @classmethod
    def extract(cls, file_path: Path) -> List[DocumentPage]:
        """
        Parses PDF file and returns a list of DocumentPage objects preserving 1-based page indexing.
        """
        if not file_path.exists():
            raise ExtractionError(f"File not found: {file_path.name}")

        try:
            doc = pymupdf.open(str(file_path))
        except Exception as e:
            err_msg = str(e).lower()
            if "password" in err_msg or "encrypted" in err_msg:
                raise EncryptedDocumentError(f"PDF is encrypted or password-protected: {file_path.name}")
            raise CorruptedFileError(f"Failed to open PDF due to corruption: {file_path.name}. Detail: {e}")

        try:
            # Check for encryption flags
            if getattr(doc, "is_encrypted", False) or getattr(doc, "needs_pass", False):
                raise EncryptedDocumentError(f"PDF is password-protected or encrypted: {file_path.name}")

            total_pages = len(doc)
            if total_pages == 0:
                raise ExtractionError(f"PDF contains 0 pages: {file_path.name}", error_code="EMPTY_DOCUMENT")

            pages: List[DocumentPage] = []
            total_extracted_chars = 0

            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_number = page_idx + 1  # Strictly 1-based page indexing
                page_height = page.rect.height

                # Extract text blocks with geometric coordinates: (x0, y0, x1, y1, text, block_no, block_type)
                # block_type == 0 indicates text block; 1 indicates image block
                blocks = page.get_text("blocks")
                page_text_segments: List[str] = []

                for block in blocks:
                    if len(block) >= 5:
                        x0, y0, x1, y1, text = block[:5]
                        block_type = block[6] if len(block) >= 7 else 0

                        if block_type == 0 and text.strip():
                            # Header & Footer geometric filtering
                            # Exclude blocks positioned in the extreme top 5% or bottom 5% of the page
                            if y1 <= (page_height * cls.HEADER_FOOTER_MARGIN_RATIO):
                                continue  # Skip running header
                            if y0 >= (page_height * (1.0 - cls.HEADER_FOOTER_MARGIN_RATIO)):
                                continue  # Skip running footer

                            page_text_segments.append(text)

                raw_page_text = "\n".join(page_text_segments)
                cleaned_page_text = TextCleaner.clean(raw_page_text)

                char_count = len(cleaned_page_text)
                total_extracted_chars += char_count

                pages.append(
                    DocumentPage(
                        page_number=page_number,
                        section_title=None,
                        text=cleaned_page_text,
                        char_count=char_count,
                    )
                )

            # Scanned / Image-Only PDF Detection
            # If a multi-page or single-page PDF yields negligible text (< 20 chars total), it lacks an extractable text layer.
            if total_extracted_chars < cls.MIN_CHARACTERS_FOR_TEXT_LAYER:
                raise NeedsOCRError(
                    f"PDF '{file_path.name}' contains {total_pages} page(s) but yielded only {total_extracted_chars} characters. "
                    "The document appears to be a scanned image without an embedded text layer. OCR is required."
                )

            return pages

        finally:
            doc.close()

