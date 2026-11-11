"""
TrustRAG Ingestion Exceptions & Error Definitions
Adheres strictly to docs/architecture/failure-handling.md and docs/architecture/ingestion-pipeline.md.
"""


class IngestionError(Exception):
    """Base exception for all ingestion pipeline failures."""
    def __init__(self, message: str, error_code: str = "INGESTION_FAILED", details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class FileValidationError(IngestionError):
    """Raised when a document fails pre-ingestion validation."""
    def __init__(self, message: str, error_code: str = "VALIDATION_FAILED", details: dict = None):
        super().__init__(message, error_code=error_code, details=details)


class UnsupportedFileTypeError(FileValidationError):
    """Raised when document extension or magic bytes are unsupported."""
    def __init__(self, message: str = "Unsupported file type. Only PDF, DOCX, and TXT are supported.", details: dict = None):
        super().__init__(message, error_code="UNSUPPORTED_FILE_TYPE", details=details)


class FileSizeLimitExceededError(FileValidationError):
    """Raised when file size exceeds the maximum threshold (default 25 MB)."""
    def __init__(self, message: str = "File size exceeds the 25 MB maximum limit.", details: dict = None):
        super().__init__(message, error_code="FILE_SIZE_EXCEEDED", details=details)


class EmptyFileError(FileValidationError):
    """Raised when file contains 0 bytes."""
    def __init__(self, message: str = "File is empty (0 bytes).", details: dict = None):
        super().__init__(message, error_code="EMPTY_FILE", details=details)


class ExtractionError(IngestionError):
    """Raised when content extraction fails."""
    def __init__(self, message: str, error_code: str = "EXTRACTION_FAILED", details: dict = None):
        super().__init__(message, error_code=error_code, details=details)


class NeedsOCRError(ExtractionError):
    """Raised when a PDF contains no extractable text layer (scanned/image-only)."""
    def __init__(self, message: str = "Document contains scanned images without extractable text. OCR required.", details: dict = None):
        super().__init__(message, error_code="NEEDS_OCR", details=details)


class EncryptedDocumentError(ExtractionError):
    """Raised when a document is password protected or encrypted."""
    def __init__(self, message: str = "Document is password protected or encrypted.", details: dict = None):
        super().__init__(message, error_code="ENCRYPTED_DOCUMENT", details=details)


class CorruptedFileError(ExtractionError):
    """Raised when a document has corrupted internal structure."""
    def __init__(self, message: str = "Document is corrupted and cannot be parsed.", details: dict = None):
        super().__init__(message, error_code="CORRUPTED_DOCUMENT", details=details)

