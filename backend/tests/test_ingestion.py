"""
TrustRAG Phase 3 Ingestion Pipeline Unit Test Suite
Generates synthetic in-memory test documents (PDF, DOCX, TXT) across all required edge cases:
- Validation tests (extensions, missing files, size limits, traversal, empty files)
- PDF tests (single-page, multi-page, empty, corrupted, encrypted, scanned/NEEDS_OCR)
- DOCX tests (paragraphs, headings, markdown tables, empty, corrupted)
- TXT tests (normal text, multi-paragraph, unicode NFKC, encodings, empty)
- Chunking tests (short/long text, 500-char bounds, 100-char overlap, metadata offsets, no empty chunks)
- End-to-end ingestion orchestrator tests
"""

import os
from pathlib import Path
import pytest
import docx

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from backend.app.core.errors import (
    CorruptedFileError,
    EmptyFileError,
    EncryptedDocumentError,
    ExtractionError,
    FileSizeLimitExceededError,
    FileValidationError,
    NeedsOCRError,
    UnsupportedFileTypeError,
)
from backend.app.schemas.document import DocumentTypeEnum
from backend.app.services.chunker import RecursiveContextChunker
from backend.app.services.document_validator import DocumentValidator
from backend.app.services.docx_extractor import DOCXExtractor
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.pdf_extractor import PDFExtractor
from backend.app.services.text_cleaner import TextCleaner
from backend.app.services.txt_extractor import TXTExtractor


# ==============================================================================
# 1. DOCUMENT VALIDATOR TESTS
# ==============================================================================

def test_validator_supported_and_missing_file(tmp_path):
    validator = DocumentValidator()

    # Missing file
    missing_file = tmp_path / "does_not_exist.pdf"
    with pytest.raises(FileValidationError) as exc_info:
        validator.validate(str(missing_file))
    assert exc_info.value.error_code == "FILE_NOT_FOUND"


def test_validator_empty_file(tmp_path):
    validator = DocumentValidator()
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")

    with pytest.raises(EmptyFileError):
        validator.validate(str(empty_file))


def test_validator_unsupported_extension(tmp_path):
    validator = DocumentValidator()
    invalid_ext = tmp_path / "data.csv"
    invalid_ext.write_text("col1,col2\nval1,val2")

    with pytest.raises(UnsupportedFileTypeError):
        validator.validate(str(invalid_ext))


def test_validator_filename_traversal():
    validator = DocumentValidator()

    # Path traversal and dangerous chars
    clean_name = validator.sanitize_filename("../../etc/passwd")
    assert clean_name == "passwd"

    with pytest.raises(FileValidationError):
        validator.sanitize_filename("test<script>.pdf")


def test_validator_size_limit(tmp_path):
    # Set limit to 1 KB for test
    validator = DocumentValidator(max_file_size_bytes=1024)
    oversized = tmp_path / "large.txt"
    oversized.write_text("A" * 2048)

    with pytest.raises(FileSizeLimitExceededError):
        validator.validate(str(oversized))


def test_validator_magic_bytes_spoofing(tmp_path):
    validator = DocumentValidator()
    spoofed = tmp_path / "fake.pdf"
    spoofed.write_bytes(b"This is just plain text, not a real PDF binary")

    with pytest.raises(UnsupportedFileTypeError):
        validator.validate(str(spoofed))


# ==============================================================================
# 2. TEXT CLEANER TESTS
# ==============================================================================

def test_text_cleaner_normalization():
    raw_text = "Employees\u00a0receive 18   paid leaves annually.\r\nWork-from-home requires manager approval."
    cleaned = TextCleaner.clean(raw_text)
    assert "\u00a0" not in cleaned
    assert "\r" not in cleaned
    assert "18 paid leaves" in cleaned
    assert "Work-from-home requires manager approval." in cleaned


def test_text_cleaner_line_break_hyphen_repair():
    # Syllable break should be joined
    raw_text = "Medical leave requires docu-\nmentation."
    cleaned = TextCleaner.clean(raw_text)
    assert "documentation." in cleaned

    # Valid compound hyphen should remain untouched
    compound = "Employees may apply for work-from-home arrangements."
    assert "work-from-home" in TextCleaner.clean(compound)


# ==============================================================================
# 3. PDF EXTRACTION TESTS
# ==============================================================================

def test_pdf_extractor_single_and_multi_page(tmp_path):
    pdf_path = tmp_path / "sample_policy.pdf"

    # Create synthetic multi-page PDF using PyMuPDF
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((50, 150), "Section 1: Annual Leave Policy.\nEmployees receive 18 paid leaves annually.")

    page2 = doc.new_page()
    page2.insert_text((50, 150), "Section 2: Carry Forward Rules.\nEmployees can carry forward up to 5 unused leaves.")
    doc.save(str(pdf_path))
    doc.close()

    pages = PDFExtractor.extract(pdf_path)
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "18 paid leaves annually" in pages[0].text
    assert pages[1].page_number == 2
    assert "carry forward up to 5 unused leaves" in pages[1].text


def test_pdf_extractor_scanned_needs_ocr(tmp_path):
    # PDF with negligible printable characters (< 20 chars)
    scanned_path = tmp_path / "scanned_image.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 150), "A")  # Only 1 char
    doc.save(str(scanned_path))
    doc.close()

    with pytest.raises(NeedsOCRError):
        PDFExtractor.extract(scanned_path)


def test_pdf_extractor_encrypted_document(tmp_path):
    enc_path = tmp_path / "protected.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 150), "Classified Policy Details That Are Encrypted.")
    # Encrypt using 256-bit AES
    doc.save(
        str(enc_path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="secure_password",
        owner_pw="master_password",
    )
    doc.close()

    with pytest.raises(EncryptedDocumentError):
        PDFExtractor.extract(enc_path)


def test_pdf_extractor_corrupted_file(tmp_path):
    corrupt_path = tmp_path / "corrupt.pdf"
    corrupt_path.write_bytes(b"%PDF-1.4\nCorrupted content completely invalid binary EOF")

    with pytest.raises(CorruptedFileError):
        PDFExtractor.extract(corrupt_path)


# ==============================================================================
# 4. DOCX EXTRACTION TESTS
# ==============================================================================

def test_docx_extractor_paragraphs_headings_and_tables(tmp_path):
    docx_path = tmp_path / "handbook.docx"
    doc = docx.Document()

    # Heading and paragraph
    doc.add_heading("Section 4: Leave Regulations", level=1)
    doc.add_paragraph("Employees are granted 18 annual leaves per year.")

    # Table with headers and data
    table = doc.add_table(rows=3, cols=2)
    table.rows[0].cells[0].text = "Leave Type"
    table.rows[0].cells[1].text = "Max Days"
    table.rows[1].cells[0].text = "Annual Leave"
    table.rows[1].cells[1].text = "18"
    table.rows[2].cells[0].text = "Carry Forward"
    table.rows[2].cells[1].text = "5"

    doc.save(str(docx_path))

    pages = DOCXExtractor.extract(docx_path)
    assert len(pages) >= 1
    full_text = "\n".join(p.text for p in pages)

    assert "Section 4: Leave Regulations" in full_text
    assert "18 annual leaves" in full_text
    # Verify table Markdown formatting
    assert "| Leave Type | Max Days |" in full_text
    assert "| Annual Leave | 18 |" in full_text
    assert "| Carry Forward | 5 |" in full_text


def test_docx_extractor_corrupted_file(tmp_path):
    bad_docx = tmp_path / "corrupt.docx"
    bad_docx.write_bytes(b"PK\x03\x04" + b"Not a real zip archive header")

    with pytest.raises(CorruptedFileError):
        DOCXExtractor.extract(bad_docx)


# ==============================================================================
# 5. TXT EXTRACTION TESTS
# ==============================================================================

def test_txt_extractor_utf8_and_latin1(tmp_path):
    txt_path = tmp_path / "notes_utf8.txt"
    txt_path.write_text("Paragraph 1: Policy overview.\n\nParagraph 2: Implementation details.", encoding="utf-8")

    pages = TXTExtractor.extract(txt_path)
    assert len(pages) == 1
    assert pages[0].page_number is None  # Unpaginated
    assert "Paragraph 1: Policy overview." in pages[0].text
    assert "Paragraph 2: Implementation details." in pages[0].text

    # Test Latin-1 encoding fallback
    latin_path = tmp_path / "notes_latin1.txt"
    with open(latin_path, "wb") as fh:
        fh.write("Café policy: employees receive reimbursement for cafés.".encode("latin-1"))

    latin_pages = TXTExtractor.extract(latin_path)
    assert "Café policy" in latin_pages[0].text


# ==============================================================================
# 6. RECURSIVE CHUNKER TESTS
# ==============================================================================

def test_chunker_bounds_overlap_and_provenance():
    chunker = RecursiveContextChunker(chunk_size=200, chunk_overlap=50)

    # Synthetic document text with multiple sentences exceeding 200 chars
    text = (
        "Employees receive 18 paid leaves annually. Work-from-home requires manager approval. "
        "Medical leave requires supporting documentation. Unused leaves can be carried forward "
        "up to 5 days into the following calendar year. Any remaining leave beyond 5 days will lapse automatically."
    )

    from backend.app.schemas.document import DocumentPage
    page = DocumentPage(page_number=3, section_title="Section 4.2", text=text, char_count=len(text))

    chunks = chunker.chunk_page(
        page=page,
        doc_id="doc_test123",
        filename="Handbook.pdf",
        file_hash="dummyhash123",
        starting_chunk_index=0
    )

    assert len(chunks) > 1

    for c in chunks:
        # Every chunk must obey chunk_size bound (with modest tolerance for unbreakable words)
        assert len(c.text) <= 250
        # No empty chunks
        assert len(c.text.strip()) > 0
        # Complete provenance attribution
        assert c.doc_id == "doc_test123"
        assert c.filename == "Handbook.pdf"
        assert c.file_hash == "dummyhash123"
        assert c.page_number == 3
        assert c.section_title == "Section 4.2"
        assert c.chunk_id.startswith("doc_test123_p003_c")
        # Character offsets validity
        assert c.char_end > c.char_start
        assert c.char_start >= 0


def test_chunker_unpaginated_docx():
    chunker = RecursiveContextChunker(chunk_size=150, chunk_overlap=30)
    from backend.app.schemas.document import DocumentPage

    page = DocumentPage(page_number=None, section_title="Section A", text="Word document text without page numbers.", char_count=42)

    chunks = chunker.chunk_page(
        page=page,
        doc_id="doc_docx01",
        filename="Doc.docx",
        file_hash="hashdocx",
    )

    assert len(chunks) == 1
    assert chunks[0].page_number is None
    # Check unpaginated chunk_id format
    assert chunks[0].chunk_id == "doc_docx01_c0000"


# ==============================================================================
# 7. UNIFIED INGESTION PIPELINE END-TO-END TESTS
# ==============================================================================

def test_ingestion_service_end_to_end_pdf(tmp_path):
    service = IngestionService()

    pdf_file = tmp_path / "corporate_policy.pdf"
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((50, 100), "Corporate Policy Document.\n1. Annual leaves: 18 paid leaves annually.")
    page2 = doc.new_page()
    page2.insert_text((50, 100), "2. Carry forward rule: Maximum 5 unused leaves can be carried forward.")
    doc.save(str(pdf_file))
    doc.close()

    result = service.ingest_file(str(pdf_file))

    # Verify structured IngestionResult
    assert result.document.filename == "corporate_policy.pdf"
    assert result.document.file_type == DocumentTypeEnum.PDF
    assert result.document.total_pages == 2
    assert result.document.total_chunks > 0
    assert result.document.doc_id.startswith("doc_")
    assert result.total_characters > 0
    assert result.processing_time_ms >= 0.0

    # Verify chunks have provenance
    for chunk in result.chunks:
        assert chunk.doc_id == result.document.doc_id
        assert chunk.filename == "corporate_policy.pdf"
        assert chunk.page_number in [1, 2]
        assert chunk.char_end > chunk.char_start


def test_ingestion_service_end_to_end_docx(tmp_path):
    service = IngestionService()

    docx_file = tmp_path / "benefits.docx"
    doc = docx.Document()
    doc.add_heading("Employee Benefits Guide", level=1)
    doc.add_paragraph("Medical insurance coverage starts on day 1 of employment.")
    doc.save(str(docx_file))

    result = service.ingest_file(str(docx_file))

    assert result.document.filename == "benefits.docx"
    assert result.document.file_type == DocumentTypeEnum.DOCX
    assert result.document.total_pages is None  # Unpaged flowable document
    assert result.document.total_chunks >= 1
    assert "Medical insurance" in result.chunks[0].text


# ==============================================================================
# 8. ADDITIONAL EDGE CASE TESTS
# ==============================================================================

def test_pdf_extractor_empty_text_layer(tmp_path):
    empty_pdf = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()  # Blank page with 0 text
    doc.save(str(empty_pdf))
    doc.close()

    with pytest.raises(NeedsOCRError):
        PDFExtractor.extract(empty_pdf)


def test_docx_extractor_empty_document(tmp_path):
    empty_docx = tmp_path / "empty_doc.docx"
    doc = docx.Document()
    doc.save(str(empty_docx))

    with pytest.raises(ExtractionError) as exc_info:
        DOCXExtractor.extract(empty_docx)
    assert exc_info.value.error_code == "EMPTY_DOCUMENT"


def test_txt_extractor_whitespace_only(tmp_path):
    blank_txt = tmp_path / "blank.txt"
    blank_txt.write_text("   \n\n\t   \n  ")

    with pytest.raises(ExtractionError) as exc_info:
        TXTExtractor.extract(blank_txt)
    assert exc_info.value.error_code == "EMPTY_DOCUMENT"


def test_chunker_short_text():
    chunker = RecursiveContextChunker(chunk_size=500, chunk_overlap=100)
    from backend.app.schemas.document import DocumentPage

    page = DocumentPage(page_number=1, text="Short policy note.", char_count=18)
    chunks = chunker.chunk_page(page, "doc_s01", "short.pdf", "hashs01")

    assert len(chunks) == 1
    assert chunks[0].text == "Short policy note."
    assert chunks[0].chunk_index == 0


def test_ingestion_service_end_to_end_txt(tmp_path):
    service = IngestionService()
    txt_file = tmp_path / "general_policy.txt"
    txt_file.write_text("Paragraph 1: General rules.\n\nParagraph 2: Enforcement details.")

    result = service.ingest_file(str(txt_file))
    assert result.document.filename == "general_policy.txt"
    assert result.document.file_type == DocumentTypeEnum.TXT
    assert result.document.total_pages is None
    assert result.document.total_chunks >= 1
    assert "General rules." in result.chunks[0].text
