"""
TrustRAG Text Cleaner & Normalizer Service
Normalizes unicode, strips extraction artifacts, repairs line-break hyphenations,
and preserves structural punctuation without modifying semantic policy facts.
Adheres strictly to docs/architecture/ingestion-pipeline.md (Section 3.3).
"""

import re
import unicodedata


class TextCleaner:
    """
    Cleans raw extracted text while preserving strict factual fidelity.
    """

    # Matches syllable hyphenation split by line breaks: "infor-\nmation" -> "information"
    # Matches a lowercase/uppercase letter followed by a hyphen, optional space, newline, and next letter
    _HYPHEN_BREAK_REGEX = re.compile(r'([a-zA-Z])-\s*\n\s*([a-zA-Z])')

    # Matches multiple non-newline whitespace characters
    _HORIZONTAL_SPACE_REGEX = re.compile(r'[^\S\r\n]+')

    # Matches 3 or more consecutive newlines (reducing to standard paragraph break \n\n)
    _EXCESSIVE_NEWLINES_REGEX = re.compile(r'\n{3,}')

    @classmethod
    def clean(cls, text: str) -> str:
        """
        Cleans and normalizes extracted text content.
        Preserves numbers, dates, section titles, and semantic punctuation.
        """
        if not text or not isinstance(text, str):
            return ""

        # 1. Unicode NFKC Normalization (standardizes ligatures, accents, full-width chars)
        cleaned = unicodedata.normalize("NFKC", text)

        # 2. Normalize Windows/Mac line endings to standard Unix \n
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Replace non-standard whitespace (non-breaking spaces, form feeds, tabs)
        cleaned = cleaned.replace("\u00a0", " ").replace("\u200b", "").replace("\f", "\n")

        # 4. Repair line-break syllable splits: "infor-\nmation" -> "information"
        # Preserves legitimate compound hyphens like "work-from-home" that are not split across lines
        cleaned = cls._HYPHEN_BREAK_REGEX.sub(r'\1\2', cleaned)

        # 5. Clean trailing whitespace on each individual line
        lines = [cls._HORIZONTAL_SPACE_REGEX.sub(" ", line).strip() for line in cleaned.split("\n")]
        cleaned = "\n".join(lines)

        # 6. Normalize excessive consecutive blank lines down to standard double newline (paragraph boundary)
        cleaned = cls._EXCESSIVE_NEWLINES_REGEX.sub("\n\n", cleaned)

        # 7. Final strip
        return cleaned.strip()

