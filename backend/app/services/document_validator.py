"""
TrustRAG Document Validator Service
Performs pre-ingestion security, format, size, checksum, and path validation.
Adheres strictly to docs/architecture/ingestion-pipeline.md and failure-handling.md.
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Optional, Set

from backend.app.core.errors import (
    EmptyFileError,
    FileSizeLimitExceededError,
    FileValidationError,
    UnsupportedFileTypeError,
)
from backend.app.schemas.document import DocumentTypeEnum, ValidationResult

# Default maximum file size: 25 MB
DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

SUPPORTED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}


class DocumentValidator:
    """
    Validates document safety, bounds, and MIME signatures before parsing.
    """

    def __init__(self, max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES):
        self.max_file_size_bytes = max_file_size_bytes

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Removes path traversal sequences, null bytes, and unsafe characters.
        """
        if not filename or not isinstance(filename, str):
            raise FileValidationError("Invalid filename provided.", error_code="INVALID_FILENAME")

        # Strip null bytes and directory components
        clean = os.path.basename(filename.strip().replace("\x00", ""))
        
        # Remove any leading dots or traversal remnants
        clean = clean.lstrip(".")
        if not clean:
            raise FileValidationError("Filename contains only invalid or traversal characters.", error_code="INVALID_FILENAME")

        # Ensure filename does not contain dangerous shell characters
        if re.search(r'[<>:"/\\|?*]', clean):
            raise FileValidationError(f"Filename contains illegal characters: {clean}", error_code="ILLEGAL_FILENAME_CHARS")

        return clean

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """
        Computes SHA-256 hash using streaming blocks to minimize memory footprint.
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def validate_magic_bytes(self, file_path: Path, ext: str) -> DocumentTypeEnum:
        """
        Validates internal file header signatures (magic bytes) to prevent extension spoofing.
        """
        with open(file_path, "rb") as fh:
            header = fh.read(8)

        if ext == ".pdf":
            if not header.startswith(b"%PDF"):
                raise UnsupportedFileTypeError(
                    f"File has .pdf extension but lacks standard PDF magic bytes: {file_path.name}",
                    details={"header": str(header[:4])}
                )
            return DocumentTypeEnum.PDF

        elif ext == ".docx":
            # DOCX is an OpenXML ZIP archive starting with PK\x03\x04
            if not header.startswith(b"PK\x03\x04"):
                raise UnsupportedFileTypeError(
                    f"File has .docx extension but lacks valid ZIP/OpenXML magic bytes: {file_path.name}",
                    details={"header": str(header[:4])}
                )
            return DocumentTypeEnum.DOCX

        elif ext == ".txt":
            # TXT files should be decodable as text without binary execution headers (e.g. not ELF, MZ, PE)
            if header.startswith(b"MZ") or header.startswith(b"\x7fELF"):
                raise UnsupportedFileTypeError(
                    f"Executable binary masquerading as .txt file: {file_path.name}",
                    details={"header": str(header[:4])}
                )
            return DocumentTypeEnum.TXT

        raise UnsupportedFileTypeError(f"Unsupported extension: {ext}")

    def validate(self, file_path_str: str) -> ValidationResult:
        """
        Performs full validation on the target file.
        Returns a ValidationResult object or raises structured FileValidationError.
        """
        path = Path(file_path_str)

        # 1. Existence Check
        if not path.exists():
            raise FileValidationError(
                f"Document not found on disk: {path.name}",
                error_code="FILE_NOT_FOUND",
                details={"path": str(path)}
            )

        if not path.is_file():
            raise FileValidationError(
                f"Path is not a regular file: {path.name}",
                error_code="NOT_A_FILE",
                details={"path": str(path)}
            )

        # 2. Filename Safety Check
        sanitized_name = self.sanitize_filename(path.name)

        # 3. Extension Check
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file format '{ext}'. Only .pdf, .docx, and .txt files are supported.",
                details={"extension": ext, "filename": sanitized_name}
            )

        # 4. File Size Checks
        file_size = path.stat().st_size
        if file_size == 0:
            raise EmptyFileError(
                f"File '{sanitized_name}' is empty (0 bytes). Cannot ingest empty documents.",
                details={"filename": sanitized_name}
            )

        if file_size > self.max_file_size_bytes:
            raise FileSizeLimitExceededError(
                f"File '{sanitized_name}' ({file_size / (1024*1024):.2f} MB) exceeds maximum allowed size of {self.max_file_size_bytes / (1024*1024):.0f} MB.",
                details={"file_size": file_size, "limit": self.max_file_size_bytes}
            )

        # 5. Magic Bytes / MIME Validation
        detected_type = self.validate_magic_bytes(path, ext)

        # 6. Compute Cryptographic Checksum
        sha256_hash = self.compute_sha256(path)

        return ValidationResult(
            is_valid=True,
            file_type=detected_type,
            sha256_hash=sha256_hash,
            file_size_bytes=file_size,
        )

