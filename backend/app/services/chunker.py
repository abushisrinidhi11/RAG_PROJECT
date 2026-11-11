"""
TrustRAG Context-Preserving Recursive Character Chunker
Implements recursive splitting with configurable chunk size (500 chars),
overlap (100 chars), and strict provenance attribution.
Adheres strictly to docs/architecture/ingestion-pipeline.md (Section 3.4).
"""

from typing import List, Optional
from backend.app.schemas.chunk import DocumentChunk
from backend.app.schemas.document import DocumentPage

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100

# Priority list of separators
SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]


class RecursiveContextChunker:
    """
    Context-aware recursive character chunker.
    Splits text along semantic natural language boundaries before falling back to word/char splits.
    Attaches complete provenance metadata to every generated chunk.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap ({chunk_overlap}) must be strictly smaller than chunk_size ({chunk_size})")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_text_recursively(self, text: str, separators: List[str]) -> List[str]:
        """
        Recursively splits text using the highest-priority separator that exists in the text.
        """
        final_chunks: List[str] = []

        # Find the first separator present in the text
        separator = ""
        new_separators = []
        for i, s in enumerate(separators):
            if s in text:
                separator = s
                new_separators = separators[i + 1:]
                break

        # If no separator found, split by characters if length exceeds chunk_size
        if not separator:
            if len(text) <= self.chunk_size:
                return [text] if text.strip() else []
            # Hard fallback split into chunk_size pieces
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                slice_chunk = text[i:i + self.chunk_size].strip()
                if slice_chunk:
                    final_chunks.append(slice_chunk)
            return final_chunks

        # Split by the active separator
        splits = text.split(separator)
        current_chunk: List[str] = []
        current_length = 0

        for split in splits:
            split_len = len(split)

            # If a single split is larger than chunk_size, recursively split it with remaining separators
            if split_len > self.chunk_size:
                # Flush existing buffer first
                if current_chunk:
                    merged = separator.join(current_chunk).strip()
                    if merged:
                        final_chunks.append(merged)
                    current_chunk = []
                    current_length = 0

                sub_splits = self._split_text_recursively(split, new_separators)
                final_chunks.extend(sub_splits)
                continue

            # Check if adding this split exceeds chunk_size
            sep_len = len(separator) if current_chunk else 0
            if current_length + sep_len + split_len > self.chunk_size:
                if current_chunk:
                    merged = separator.join(current_chunk).strip()
                    if merged:
                        final_chunks.append(merged)

                    # Build overlap from the end of the previous buffer
                    overlap_buffer: List[str] = []
                    overlap_len = 0
                    for prev_split in reversed(current_chunk):
                        if overlap_len + len(prev_split) + len(separator) <= self.chunk_overlap:
                            overlap_buffer.insert(0, prev_split)
                            overlap_len += len(prev_split) + len(separator)
                        else:
                            break
                    current_chunk = overlap_buffer
                    current_length = sum(len(s) for s in current_chunk) + (len(separator) * (len(current_chunk) - 1) if current_chunk else 0)

            current_chunk.append(split)
            current_length += (len(separator) if len(current_chunk) > 1 else 0) + split_len

        # Flush final remaining buffer
        if current_chunk:
            merged = separator.join(current_chunk).strip()
            if merged:
                final_chunks.append(merged)

        return final_chunks

    def chunk_page(
        self,
        page: DocumentPage,
        doc_id: str,
        filename: str,
        file_hash: str,
        starting_chunk_index: int = 0,
    ) -> List[DocumentChunk]:
        """
        Chunks an individual DocumentPage into DocumentChunk models with exact character offsets.
        """
        raw_text = page.text
        if not raw_text.strip():
            return []

        text_pieces = self._split_text_recursively(raw_text, SEPARATORS)
        chunks: List[DocumentChunk] = []
        global_idx = starting_chunk_index
        search_start = 0

        for piece in text_pieces:
            clean_piece = piece.strip()
            if not clean_piece:
                continue

            # Calculate character offsets within the page text
            char_start = raw_text.find(clean_piece, search_start)
            if char_start == -1:
                # If exact substring find misses due to stripped whitespace, locate first word
                first_word = clean_piece.split()[0] if clean_piece.split() else clean_piece[:10]
                char_start = raw_text.find(first_word, search_start)
                if char_start == -1:
                    char_start = search_start

            char_end = char_start + len(clean_piece)
            # Advance search_start with overlap consideration
            search_start = max(0, char_start + 1)

            # Generate composite Chunk ID according to architecture specification:
            # {doc_id}_p{page:03d}_c{idx:04d} or {doc_id}_c{idx:04d} for unpaged formats
            if page.page_number is not None:
                chunk_id = f"{doc_id}_p{page.page_number:03d}_c{global_idx:04d}"
            else:
                chunk_id = f"{doc_id}_c{global_idx:04d}"

            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    filename=filename,
                    file_hash=file_hash,
                    page_number=page.page_number,
                    section_title=page.section_title,
                    chunk_index=global_idx,
                    char_start=char_start,
                    char_end=char_end,
                    text=clean_piece,
                )
            )
            global_idx += 1

        return chunks

    def chunk_document(
        self,
        pages: List[DocumentPage],
        doc_id: str,
        filename: str,
        file_hash: str,
    ) -> List[DocumentChunk]:
        """
        Chunks an entire document across all its pages/sections, maintaining continuous chunk indices.
        """
        all_chunks: List[DocumentChunk] = []
        current_index = 0

        for page in pages:
            page_chunks = self.chunk_page(
                page=page,
                doc_id=doc_id,
                filename=filename,
                file_hash=file_hash,
                starting_chunk_index=current_index,
            )
            all_chunks.extend(page_chunks)
            current_index = len(all_chunks)

        return all_chunks

