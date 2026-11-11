# TrustRAG: Intelligent Trust-Aware Retrieval-Augmented Generation System

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Architecture Docs](https://img.shields.io/badge/docs-Phase%201%20Architecture-green.svg)](docs/README.md)

---

## 1. Project Overview

**TrustRAG** is an enterprise-grade document question-answering system designed to overcome the core failure mode of standard RAG applications: **hallucinations, ungrounded extrapolations, and over-confident inaccuracies**.

Unlike standard chatbots that simply retrieve text passages and generate text blindly, TrustRAG introduces an **independent Trust & Reliability Verification Layer**. 

### How It Works
1. **Document Ingestion**: Parses enterprise PDFs, DOCX, and TXT files, preserving granular provenance (exact page number, section heading, character offsets).
2. **Hybrid Retrieval**: Combines dense semantic vector retrieval (Sentence Transformers + ChromaDB) with sparse lexical search (BM25) and Cross-Encoder reranking.
3. **Constrained Generation**: Generates draft answers strictly bound to evidence with mandatory citation references (`[Doc_X, p. Y]`).
4. **Claim-Level Verification**: Decomposes answers into atomic factual claims and evaluates them against evidence via tripartite Natural Language Inference (`ENTAILMENT`, `CONTRADICTION`, `NEUTRAL/UNSUPPORTED`).
5. **Calibrated Trust Scoring**: Computes a multi-signal empirical **Reliability Score** ($S_{\text{rel}} \in [0.0, 1.0]$) incorporating relevance, coverage, faithfulness, and an **immediate safety circuit breaker** for contradictions.
6. **Decision Router & Human-in-the-Loop**: Automatically determines whether to **Answer**, **Retry**, **Clarify**, **Abstain**, or **Escalate** to human reviewers for ambiguous or conflicting policies.

Detailed design specifications are available in the [Architecture Documentation](docs/README.md).

---

## 2. Technology Stack (Zero-Budget & Local-First)

| Component | Selected Technology | Rationale |
| :--- | :--- | :--- |
| **Language & Runtime** | Python 3.12 | Optimal binary wheel compatibility on Windows for ML and vector DB packages. |
| **Backend API** | FastAPI + Uvicorn | Asynchronous, typed, high-performance web framework. |
| **Local Embeddings** | Sentence-Transformers (`all-MiniLM-L6-v2`) | Runs 100% locally on CPU; zero cost; no rate limits. |
| **Vector Storage** | ChromaDB (Local Persistent) | Embedded, persistent vector index stored on disk (`./data/chromadb`). |
| **Metadata & Audit DB** | SQLite + SQLAlchemy | Zero-configuration local relational database for audit logs and review queues. |
| **Workflow Engine** | LangGraph | Stateful cyclic graph execution, retries, and Human-in-the-Loop pauses. |
| **LLM Provider** | Google AI Studio (Gemini Free Tier) | Free tier API for grounded generation and NLI verification. |
| **Document Parsers** | PyMuPDF (`fitz`) & `python-docx` | Fast, robust document extraction preserving layout and page coordinates. |
| **Testing** | pytest + httpx | Automated test execution and API contract validation. |

---

## 3. Project Directory Structure

```text
TrustRAG/
│
├── backend/                  # Backend application source code
│   ├── app/
│   │   ├── api/              # FastAPI routers and endpoints
│   │   ├── core/             # Configuration, logging, and security
│   │   ├── models/           # SQLAlchemy ORM database models
│   │   ├── schemas/          # Pydantic V2 request/response contracts
│   │   └── services/         # Ingestion, retrieval, verification services
│   └── tests/                # Backend unit and integration tests
│
├── frontend/                 # Web client user interface
│
├── data/                     # Local data storage (ignored by Git)
│   ├── raw/                  # Source uploaded documents (PDF, DOCX, TXT)
│   ├── interim/              # Extracted text, cleaned pages, and debug chunks
│   └── processed/            # Serialized metadata and index files
│
├── evaluation/               # Benchmark testing and evaluation suite
│   ├── datasets/             # Labeled benchmark holdout test sets
│   └── reports/              # Benchmark evaluation result artifacts
│
├── scripts/                  # Utility scripts (verification, data seeding)
│   └── verify_env.py         # Phase 2 environment verification script
│
├── docs/                     # System documentation & specifications
│   ├── README.md             # Architecture documentation catalog
│   └── architecture/         # Phase 1 technical specifications
│
├── .env.example              # Environment variables template
├── .gitignore                # Git exclusions configuration
├── requirements.txt          # Python dependency specifications
└── README.md                 # Project root documentation (this file)
```

---

## 4. Setup & Installation Guide (Windows)

Follow these step-by-step instructions to set up the development environment.

### Step 1: Prerequisites
Ensure you have **Python 3.12** installed on your system.
Verify available Python installations:
```powershell
py --list
```
If Python 3.12 is not listed, see [Section 5: Installing Python 3.12](#5-installing-python-312-on-windows).

---

### Step 2: Clone the Repository & Switch to Working Branch
```powershell
git clone https://github.com/abushisrinidhi11/RAG_PROJECT.git
cd RAG_PROJECT
git checkout feature/phase-2-environment
```

---

### Step 3: Create & Activate Virtual Environment
Using the Windows Python launcher to target Python 3.12:
```powershell
# Create an isolated virtual environment named .venv
py -3.12 -m venv .venv

# Activate the virtual environment in PowerShell
.\.venv\Scripts\Activate.ps1
```

*Note: If PowerShell shows an `Execution_Policies` restriction, run:*
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Once activated, your terminal prompt will display `(.venv)`.

---

### Step 4: Upgrade Pip & Install Dependencies
With `(.venv)` active:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 5: Configure Environment Variables
Copy the template file to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` and review the default configuration.

---

### Step 6: Run Environment Verification
Execute the automated environment verification script:
```powershell
python scripts/verify_env.py
```
This script validates your Python 3.12 runtime, virtual environment isolation, directory layout, security exclusions in `.gitignore`, Phase 1 documentation integrity, and active Phase 2 dependencies.

---

## 5. Installing Python 3.12 on Windows

If your system only has Python 3.14 or older versions installed:

1. **Official Installer**:
   - Download the official **Python 3.12 Windows 64-bit installer**:
     [https://www.python.org/downloads/release/python-3128/](https://www.python.org/downloads/release/python-3128/)
   - Scroll to **Files** $\rightarrow$ Click **Windows installer (64-bit)**.
2. **Installation Options**:
   - Run the downloaded installer `python-3.12.x-amd64.exe`.
   - **IMPORTANT**: Check the box: `[X] Use developer features` and `[X] Add python.exe to PATH`.
   - Click **Install Now**.
3. **Verify Installation**:
   Open a new PowerShell window and run:
   ```powershell
   py -3.12 --version
   ```
   It should return: `Python 3.12.x`.

---

## 6. Development Rules & Workflow

1. **Strict Zero-Budget**: Use only local embeddings (`sentence-transformers`), local ChromaDB, and free-tier APIs. Never introduce paid resources.
2. **Feature Branching**: Each phase is developed on its own dedicated feature branch (`feature/phase-X-...`).
3. **Git Hygiene**: Never commit `.env` files, virtual environments, local databases, or private documents.

