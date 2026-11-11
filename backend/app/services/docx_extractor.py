"""
TrustRAG DOCX Extractor Service
Extracts paragraphs, preserves active heading/section hierarchy, and converts
tables into clean Markdown representations using python-docx.
Adheres strictly to docs/architecture/ingestion-pipeline.md (Section 3.2).
"""

from pathlib import Path
from typing import List, Optional
import docx

from backend.app.core.errors import CorruptedFileError, ExtractionError
from backend.app.schemas.document import DocumentPage
from backend.app.services.text_cleaner import TextCleaner


class DOCXExtractor:
    """
    Extracts structural content from Word (.docx) documents.
    Preserves hierarchical section headings and converts tables into Markdown tables.
    Does not invent artificial page numbers.
    """

    @classmethod
    def _format_table_as_markdown(cls, table: docx.table.Table) -> str:
        """
        Converts a Word table into a standard Markdown table string to preserve tabular alignments.
        """
        rows_data = []
        for row in table.rows:
            # Extract cell text and strip internal newlines to keep single-line table cells
            cell_texts = [cell.text.replace("\n", " ").strip() for cell in row.cells]
            # Avoid empty rows
            if any(cell_texts):
                rows_data.append(cell_texts)

        if not rows_data:
            return ""

        # Normalize column count to the maximum width
        max_cols = max(len(r) for r in rows_data)
        normalized_rows = [r + [""] * (max_cols - len(r)) for r in rows_data]

        header = normalized_rows[0]
        header_line = "| " + " | ".join(header) + " |"
        separator_line = "| " + " | ".join(["---"] * max_cols) + " |"

        body_lines = ["| " + " | ".join(r) + " |" for r in normalized_rows[1:]]
        
        md_table = [header_line, separator_line] + body_lines
        return "\n".join(md_table)

    @classmethod
    def extract(cls, file_path: Path) -> List[DocumentPage]:
        """
        Parses DOCX file into structured DocumentPage objects segmented by section headings.
        """
        if not file_path.exists():
            raise ExtractionError(f"File not found: {file_path.name}")

        try:
            doc = docx.Document(str(file_path))
        except Exception as e:
            raise CorruptedFileError(f"Failed to parse DOCX document: {file_path.name}. Detail: {e}")

        # In python-docx, document elements (paragraphs and tables) exist in the document body.
        # We iterate through paragraphs while maintaining the active hierarchical section title.
        sections: List[DocumentPage] = []
        current_section_title: Optional[str] = None
        current_section_texts: List[str] = []

        # Helper to flush current section
        def flush_current_section():
            if current_section_texts:
                combined_text = "\n\n".join(current_section_texts)
                cleaned_text = TextCleaner.clean(combined_text)
                if cleaned_text:
                    sections.append(
                        DocumentPage(
                            page_number=None,  # Page numbers are non-existent in flowable DOCX
                            section_title=current_section_title,
                            text=cleaned_text,
                            char_count=len(cleaned_text),
                        )
                    )
                current_section_texts.clear()

        # Iterate paragraphs and extract heading markers
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            style_name = para.style.name.lower() if para.style else ""
            if "heading" in style_name or "title" in style_name:
                # Flush previous section before starting new heading
                flush_current_section()
                current_section_title = text
                current_section_texts.append(f"### {text}")
            else:
                current_section_texts.append(text)

        # Iterate tables and append them to current section
        for table in doc.tables:
            table_md = cls._format_table_as_markdown(table)
            if table_md:
                current_section_texts.append(table_md)

        # Flush final section
        flush_current_section()

        if not sections:
            raise ExtractionError(
                f"DOCX document '{file_path.name}' contains no readable text or structural elements.",
                error_code="EMPTY_DOCUMENT"
            )

        return sections

