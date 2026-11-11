# Data Schemas & Metadata Contracts

## 1. Overview

To guarantee type safety, reproducibility, and transparent interfaces across the 12 phases, all components in TrustRAG interact through explicit **Pydantic V2 / JSON Schema** data contracts.

---

## 2. Ingestion & Document Models

### 2.1 `DocumentRecord`
Represents an ingested document registered in the system.
```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class DocumentRecord(BaseModel):
    doc_id: str = Field(..., description="Unique hash-based document identifier (e.g., doc_a3f89b)")
    filename: str = Field(..., description="Original filename with extension")
    file_type: str = Field(..., description="MIME type or extension: pdf, docx, txt")
    file_size_bytes: int = Field(..., ge=1, description="Size in bytes")
    sha256_hash: str = Field(..., description="SHA-256 cryptographic checksum")
    total_pages: int = Field(..., ge=1, description="Total number of pages parsed")
    total_chunks: int = Field(..., ge=1, description="Total chunks generated")
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2.2 `DocumentChunk`
Represents an individual chunk indexed into ChromaDB.
```python
class DocumentChunk(BaseModel):
    chunk_id: str = Field(..., description="Composite ID: {doc_id}_p{page:03d}_c{idx:04d}")
    doc_id: str = Field(..., description="Foreign key to DocumentRecord")
    filename: str
    page_number: int = Field(..., ge=1, description="1-based document page index")
    section_title: Optional[str] = Field(None, description="Enclosing heading / section title")
    char_start: int = Field(..., ge=0, description="Start character offset in page")
    char_end: int = Field(..., ge=0, description="End character offset in page")
    text: str = Field(..., min_length=10, description="Normalized chunk text content")
    embedding: Optional[List[float]] = Field(None, description="384-dim dense embedding vector")
```

---

## 3. Retrieval Models

### 3.1 `RetrievedChunk`
Represents a chunk retrieved and scored during the hybrid search and reranking process.
```python
class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    filename: str
    page_number: int
    section_title: Optional[str]
    text: str
    dense_score: float = Field(..., description="Cosine similarity score [0.0, 1.0]")
    sparse_rank: int = Field(..., description="BM25 lexical rank")
    rrf_score: float = Field(..., description="Reciprocal Rank Fusion score")
    rerank_score: float = Field(..., description="Cross-Encoder relevance score [0.0, 1.0]")
```

### 3.2 `RetrievalResult`
Container for the complete retrieval phase output.
```python
class RetrievalResult(BaseModel):
    query: str
    expanded_queries: List[str]
    retrieved_chunks: List[RetrievedChunk]
    retrieval_latency_ms: float
```

---

## 4. Generation & Verification Models

### 4.1 `DraftAnswer`
```python
class CitedSource(BaseModel):
    source_index: int = Field(..., description="Citation index tag (e.g. 1 for [Source 1])")
    chunk_id: str
    doc_id: str
    filename: str
    page_number: int

class DraftAnswer(BaseModel):
    text: str = Field(..., description="Generated answer text containing inline [Source X, Page Y] tags")
    citations: List[CitedSource]
    generation_latency_ms: float
```

### 4.2 `ClaimStatusEnum` & `AtomicClaim`
```python
from enum import Enum

class ClaimStatusEnum(str, Enum):
    ENTAILMENT = "ENTAILMENT"
    CONTRADICTION = "CONTRADICTION"
    NEUTRAL = "NEUTRAL"

class AtomicClaim(BaseModel):
    claim_id: str = Field(..., description="Identifier: claim_001")
    text: str = Field(..., description="Decontextualized atomic factual assertion")
    status: ClaimStatusEnum = Field(..., description="NLI verification status")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Verification confidence")
    supporting_chunk_id: Optional[str] = Field(None, description="Chunk ID providing evidence")
    verbatim_quote: Optional[str] = Field(None, description="Direct quote from evidence passage")
    reasoning: Optional[str] = Field(None, description="Explanation of verification verdict")
```

### 4.3 `VerificationMatrix`
```python
class VerificationMatrix(BaseModel):
    total_claims: int
    entailed_claims_count: int
    contradicted_claims_count: int
    unsupported_claims_count: int
    claims: List[AtomicClaim]
    has_contradiction: bool = Field(..., description="True if any claim-level material contradiction exists")
    inter_document_conflict_detected: bool = Field(default=False, description="True if retrieved sources conflict with each other")
    conflicting_chunk_ids: Optional[List[str]] = Field(default=None, description="Chunk IDs of conflicting policies")
    verification_latency_ms: float
```

---

## 5. Trust Scoring & Decision Models

### 5.1 `TrustScoreResult`
```python
class TrustScoreBreakdown(BaseModel):
    retrieval_relevance: float = Field(..., ge=0.0, le=1.0)
    evidence_coverage: float = Field(..., ge=0.0, le=1.0)
    claim_faithfulness: float = Field(..., ge=0.0, le=1.0)
    source_provenance: float = Field(..., ge=0.0, le=1.0)
    contradiction_penalty: float = Field(..., description="Multiplier: 0.0 if contradicted, else 1.0")

class TrustScoreResult(BaseModel):
    reliability_score: float = Field(..., ge=0.0, le=1.0, description="Calibrated final evidence-support index [0.0, 1.0] (Not a probability of correctness)")
    breakdown: TrustScoreBreakdown
    is_safe: bool = Field(..., description="False if any claim-level contradiction was detected")
    calibration_version: str = Field(default="v1.0-provisional")
```

### 5.2 `DecisionActionEnum` & `DecisionResult`
```python
class DecisionActionEnum(str, Enum):
    ANSWER = "ANSWER"
    RETRY = "RETRY"
    CLARIFY = "CLARIFY"
    ABSTAIN = "ABSTAIN"
    ESCALATE = "ESCALATE"

class DecisionResult(BaseModel):
    action: DecisionActionEnum
    reason: str
    final_text: str
    trust_score: float
    citations: List[CitedSource]
    claims_matrix: VerificationMatrix
    hitl_ticket_id: Optional[str] = None
```

---

## 6. SQLite Relational Schema (DDL)

```sql
-- Documents Registry
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    sha256_hash TEXT UNIQUE NOT NULL,
    total_pages INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Query Audit & Reliability Records
CREATE TABLE IF NOT EXISTS query_audit_logs (
    query_id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    decision_action TEXT NOT NULL,
    reliability_score REAL NOT NULL,
    faithfulness_score REAL NOT NULL,
    coverage_score REAL NOT NULL,
    has_contradiction BOOLEAN NOT NULL,
    final_response_text TEXT NOT NULL,
    total_latency_ms REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Human-in-the-Loop Review Queue
CREATE TABLE IF NOT EXISTS hitl_review_queue (
    review_id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL REFERENCES query_audit_logs(query_id),
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'APPROVED', 'EDITED', 'REJECTED')),
    draft_answer TEXT NOT NULL,
    reviewer_notes TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP
);
```

