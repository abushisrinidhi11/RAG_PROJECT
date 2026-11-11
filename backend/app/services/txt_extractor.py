"""
TrustRAG TXT Extractor Service
Handles UTF-8 and fallback encodings (latin-1), normalizes line endings,
and returns structured DocumentPage objects.
Adheres strictly to docs/architecture/ingestion-pipeline.md (Section 3.2).
"""

from pathlib import Path
from typing import List

from backend.app.core.errors import ExtractionError
from backend.app.schemas.document import DocumentPage
from backend.app.services.text_cleaner import TextCleaner


class TXTExtractor:
    """
    Extracts text from plain text (.txt) files.
    Employs safe multi-encoding fallback and normalizes line breaks.
    """

    ENCODINGS_TO_TRY = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    @classmethod
    def extract(cls, file_path: Path) -> List[DocumentPage]:
        """
        Reads and normalizes plain text file.
        """
        if not file_path.exists():
            raise ExtractionError(f"File not found: {file_path.name}")

        content: str = ""
        decoded = False

        for enc in cls.ENCODINGS_TO_TRY:
            try:
                with open(file_path, "r", encoding=enc) as fh:
                    content = fh.read()
                decoded = True
                break
            except UnicodeDecodeError:
                continue

        if not decoded:
            raise ExtractionError(
                f"Failed to decode TXT file '{file_path.name}' with supported text encodings.",
                error_code="ENCODING_DECODE_FAILED"
            )

        cleaned_text = TextCleaner.clean(content)
        if not cleaned_text:
            raise ExtractionError(
                f"TXT file '{file_path.name}' contains no readable non-whitespace text.",
                error_code="EMPTY_DOCUMENT"
            )

        return [
            DocumentPage(
                page_number=None,  # Plain text is unpaginated
                section_title=None,
                text=cleaned_text,
                char_count=len(cleaned_text),
            )
        ]

