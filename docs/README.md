# TrustRAG Architecture Documentation Index

Welcome to the **TrustRAG (Intelligent Trust-Aware Retrieval-Augmented Generation System)** architecture and technical specifications library.

This documentation defines the foundational blueprint for all 12 implementation phases.

---

## Architecture Documents Map

| Document | Topic & Focus Area | Key Architectural Deliverables |
| :--- | :--- | :--- |
| **[1. System Overview](architecture/system-overview.md)** | End-to-End Architecture | High-level dataflow, component responsibility matrix, core architectural principles, and zero-budget stack choices. |
| **[2. Ingestion Pipeline](architecture/ingestion-pipeline.md)** | Document Parsing & Indexing | PyMuPDF/python-docx parsing, hierarchical chunking, provenance metadata preservation, and local ChromaDB persistence. |
| **[3. Retrieval & Generation](architecture/retrieval-generation.md)** | Hybrid Search & Grounded Generation | BM25 + dense vector fusion (RRF), Cross-Encoder reranking, citation tagging, and zero-temperature constrained prompts. |
| **[4. Verification Engine](architecture/verification-engine.md)** | Claim-Level Verification | Atomic claim decomposition, tripartite NLI classification (`ENTAILMENT`, `CONTRADICTION`, `NEUTRAL`), and dual execution pathways. |
| **[5. Trust & Reliability Framework](architecture/trust-scoring.md)** | Multi-Signal Scoring & Calibration | Mathematical formulation of $S_{\text{rel}}$ as an evidence-support index, provisional weights, 5 signal limitations, contradiction circuit breaker, and empirical calibration methodology. |
| **[6. Decision Engine & HITL](architecture/decision-engine.md)** | State Machine & Human Review | LangGraph cyclic workflow, 6 routing policies (`ANSWER`, `RETRY`, `CLARIFY`, `ABSTAIN`, `ESCALATE` for borderline scores or inter-document policy conflicts), and review queue workflow. |
| **[7. Data Models & Schemas](architecture/data-models.md)** | Pydantic & DDL Contracts | Complete Pydantic schemas across all pipeline stages, JSON data contracts, and SQLite relational database schema. |
| **[8. Error Handling & Resilience](architecture/failure-handling.md)** | Failure Modes & Fault Tolerance | API rate limit mitigation, unreadable/scanned document handling, prompt injection defense, and graceful degradation hierarchy. |
| **[9. Evaluation Benchmark](architecture/evaluation-framework.md)** | Testing & Benchmarking | 5 manually verified query topology benchmarks (answerable, unanswerable, contradictory, ambiguous, partially supported) and deep abstention quality metrics. |

---

## System Constraints Reference

1. **Python Runtime**: Python 3.12 target for machine learning and vector database wheel compatibility.
2. **Local First**: Embeddings via local CPU Sentence-Transformers (`all-MiniLM-L6-v2`); local persistent ChromaDB; local SQLite.
3. **Zero Budget**: Free-tier Google AI Studio API for generation; no paid services.
4. **Epistemic Stance**: Reliability score ($S_{\text{rel}}$) is an empirical *evidence-support index* within the provided corpus, NOT a Bayesian probability of correctness or metaphysical truth.
5. **Safety Rule & Escalation**: Material claim contradictions trigger an immediate safety override ($S_{\text{rel}} \equiv 0.00$); conflicting source policies are escalated to Human-in-the-Loop review without assuming the generated answer is false.
6. **No Blind Hallucinations**: Neutral/unsupported claims are never presented as verified facts.
7. **Empirical Validation**: Hybrid retrieval and provisional scoring weights are candidate designs to be validated against labeled benchmarks.

