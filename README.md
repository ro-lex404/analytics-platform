# 📊 Hybrid AI Financial Reconciliation & Analytics Platform

[![CI Pipeline](https://github.com/ro-lex404/analytics-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/ro-lex404/analytics-platform/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000.svg?style=flat&logo=next.js)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-FF6F61.svg)](https://langchain-ai.github.io/langgraph/)
[![DuckDB](https://img.shields.io/badge/DuckDB-Vectorized_SQL-FFF000.svg?style=flat&logo=duckdb)](https://duckdb.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1.svg?style=flat&logo=postgresql)](https://github.com/pgvector/pgvector)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?style=flat&logo=docker)](https://www.docker.com/)

An enterprise-grade, agentic financial analytics & automated settlement reconciliation engine. Powered by **FastAPI**, **Next.js 15**, **LangGraph**, **DuckDB**, **Celery**, **Redis**, **PostgreSQL (`pgvector`)**, and **Groq Llama 3.3 70B**.

---

## 🌟 Key Features

### 📄 Multi-Pass Settlement & PDF Invoice Reconciliation
* **Vectorized SQL Processing (DuckDB):** Performs zero-copy multi-pass matching across payment gateway CSVs (e.g. Razorpay settlements), PDF bank statements, and uploaded invoice PDFs.
* **3-Pass Matching Pipeline:**
  1. **Pass 1 — Exact Matches:** Instant matching where transaction amount delta is `< ₹0.01` and settlement dates align perfectly.
  2. **Pass 2 — Fuzzy Matches:** Intelligent relaxation for date variance ($\le 2$ days) and minor fee/rounding deviations ($\le \text{₹}5.00$).
  3. **Pass 3 — Categorized Exception Auditing:** Automatic tagging and risk-scoring for *Missing Bank Entries*, *Amount/Date Mismatches*, and *Ghost Credits* (unmatched bank deposits).
* **LangGraph PDF Parser:** Multi-modal PDF extraction pipeline using LLM structured output schema (with regex fallback) to extract tabular financial records and verify them against bank records.
* **Timestamped PDF Audit Export:** One-click generation and downloading of PDF audit reports (built via ReportLab) detailing faulty transactions and recommended mitigation actions.

### 🤖 Intelligent AI Finance Controller (Multi-Agent Routing & Q&A)
* **Smart Intent Router:** Categorizes user natural language queries into `SQL` (numerical/tabular queries), `RAG` (unstructured PDF policy & document queries), `Both`, or `General`.
* **Sub-Second DuckDB Text-to-SQL:** Dynamically generates and runs sanitized SQL queries against uploaded tabular dataset schemas.
* **PostgreSQL + pgvector RAG:** Background document chunking and local embeddings (`all-MiniLM-L6-v2`) via Celery background workers for context-grounded document search.
* **Executive Financial Synthesizer:** Formats answers with Indian Rupee (₹) currency formatting, exact reference citations, forward cash settlement inflow forecasting (calculating gateway fees and GST deductions), and recommended financial compliance actions.

---

## 🏗️ System Architecture

```mermaid
graph TD
    User([User / Browser UI]) -->|Next.js 15 Dashboard| Frontend[Frontend Next.js App]
    Frontend -->|REST APIs| API[FastAPI Backend Server]

    subgraph LangGraph Multi-Agent Workflows
        API -->|Upload PDF Invoice| PDFGraph[PDF Reconciler Graph]
        PDFGraph -->|Extract Raw Text| PDFText[PyPDF Text Extractor]
        PDFText -->|Structured JSON Extraction| GroqLLM[Groq Llama 3.3 70B]
        GroqLLM -->|Vectorized SQL Matching| DuckDBEngine[(DuckDB Engine)]

        API -->|Chat Query| RouterGraph[Agent Router Graph]
        RouterGraph -->|Route Query| Intent{Query Classifier}
        Intent -->|Numerical / Tabular| SQLNode[DuckDB SQL Node]
        Intent -->|Unstructured Docs| RAGNode[PGVector RAG Node]
        Intent -->|Complex / Both| BothNode[Combined SQL + RAG]
        SQLNode & RAGNode & BothNode --> Synthesizer[Financial Controller Synthesizer]
    end

    subgraph Async Vector Ingestion
        API -->|Async Upload Job| Celery[Celery Worker Task]
        Celery <-->|Message Queue| Redis[(Redis Broker)]
        Celery -->|Chunk & Embed| MiniLM[HuggingFace all-MiniLM-L6-v2]
        MiniLM -->|Store Vectors| PGVector[(PostgreSQL + pgvector)]
    end

    Synthesizer -->|Markdown & Metrics| Frontend
    DuckDBEngine -->|JSON Matches & PDF Report| Frontend
```

---

## 📁 Repository Structure

```
analytics-platform/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI pipeline (backend & frontend)
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── pdf_reconciler.py  # LangGraph graph for structured PDF invoice extraction & DuckDB matching
│   │   │   └── router.py          # LangGraph agent router (SQL/RAG routing & financial synthesizer)
│   │   ├── services/
│   │   │   ├── duckdb_client.py   # DuckDB dynamic SQL execution engine
│   │   │   ├── pdf_report_generator.py # ReportLab audit PDF generator
│   │   │   ├── reconciliation.py # Multi-pass settlement reconciliation logic & context summarizer
│   │   │   └── vector_store.py    # PGVector embeddings management
│   │   ├── main.py                # FastAPI endpoints & CORS configuration
│   │   └── worker.py              # Celery background tasks for document chunking & embeddings
│   ├── Dockerfile                 # Backend container definition
│   └── requirements.txt           # Python dependencies (FastAPI, DuckDB, LangGraph, Celery, etc.)
├── frontend/
│   ├── app/
│   │   ├── globals.css            # Tailwind styling
│   │   ├── layout.tsx             # Main layout
│   │   └── page.tsx               # Next.js interactive UI (Reconciliation Dashboard & AI Chat)
│   ├── Dockerfile                 # Frontend Next.js container definition
│   └── package.json               # Node.js dependencies
├── razorpay-reconciler/
│   ├── data/                      # Sample financial settlement CSVs & invoice PDFs
│   ├── invoice_generator.py       # Synthetic PDF invoice generator script
│   └── synthetic-reportsgen.py    # Synthetic Razorpay settlement & bank statement generator script
├── docker-compose.yml             # Full-stack multi-container Docker compose orchestrator
├── docker-compose-infra.yml       # Infrastructure-only Docker compose file (DB & Redis)
├── .env.example                   # Template environment file
└── README.md                      # Project documentation
```

---

## 🚀 Quick Start Guide

### Prerequisites
* **Docker & Docker Compose** (Recommended)
* **Python 3.13+** and **Node.js 22+** (for manual local development)
* **Groq API Key** (Get one at [console.groq.com](https://console.groq.com/))

---

### 🐳 Running with Docker (Recommended)

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/ro-lex404/analytics-platform.git
   cd analytics-platform
   ```

2. **Configure Environment Variables:**
   Copy `.env.example` to `.env` and enter your Groq API key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```env
   GROQ_API_KEY=gsk_your_actual_groq_api_key_here
   ALLOWED_ORIGINS=http://localhost:3000
   DATABASE_URL=postgresql+psycopg2://myuser:mypassword@db:5432/hybrid_ai
   REDIS_URL=redis://redis:6379/0
   FINANCE_DATA_DIR=/app/finance-data
   ```

3. **Spin Up the Full Stack:**
   ```bash
   docker-compose up --build
   ```

4. **Access Applications:**
   * 🖥️ **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
   * ⚙️ **FastAPI Interactive Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   * 🗄️ **PostgreSQL (pgvector):** `localhost:5432` (`myuser` / `mypassword` / `hybrid_ai`)
   * 🔴 **Redis Broker:** `localhost:6379`

---

### 💻 Manual Local Development

If you prefer running services outside Docker containers:

#### 1. Start Infrastructure (PostgreSQL + pgvector & Redis)
```bash
docker-compose -f docker-compose-infra.yml up -d
```

#### 2. Setup & Run Backend API
```bash
cd backend

# Create & activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY="your_groq_api_key"
export DATABASE_URL="postgresql+psycopg2://myuser:mypassword@localhost:5432/hybrid_ai"
export REDIS_URL="redis://localhost:6379/0"

# Run FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. Run Celery Worker (In a separate terminal)
```bash
cd backend
# Activate venv
celery -A app.worker worker --loglevel=info
```

#### 4. Setup & Run Frontend
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 📡 API Endpoint Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/upload` | Uploads PDF/CSV files, triggers Celery vector storage, and runs live PDF reconciliation. |
| `POST` | `/chat` | Processes user financial query through LangGraph router (SQL/RAG) and returns synthesized markdown. |
| `POST` | `/finance/reconcile` | Runs vectorized settlement reconciliation between Razorpay CSV and Bank CSV via DuckDB. |
| `GET` | `/finance/verify` | Returns integrity verification metrics confirming 0 duplicate match set collisions. |
| `POST` | `/finance/extract-pdf` | LangGraph workflow extracting PDF invoice records & reconciling against bank statements. |
| `POST` | `/finance/export-report` | Generates & downloads a timestamped audit PDF report for faulty transactions. |

---

## 🧪 Generating Synthetic Test Data

The repository includes synthetic data generator utilities to benchmark reconciliation throughput and simulate payment gateway anomalies:

```bash
cd razorpay-reconciler

# Generate synthetic Razorpay settlement CSV and Bank Statement CSV
python synthetic-reportsgen.py

# Generate sample PDF invoices with varying layout structures
python invoice_generator.py
```
This generates:
* 150 settlement records in `razorpay-reconciler/data/razorpay_settlements.csv`
* Bank statement entries with injected anomalies (missing entries, amount deltas, ghost credits) in `bank_statement.csv`
* `invoices.pdf` for testing multi-page PDF extraction and reconciliation.

---

## 🛡️ Security & Quality

* **Security Policy:** See [SECURITY.md](SECURITY.md) for details on supported versions and vulnerability reporting.
* **CORS & Environment Protection:** Configured with explicit domain whitelist isolation and Pydantic validation.
* **CI/CD Automation:** GitHub Actions workflow running automated backend reconciliation unit verification and Next.js static builds on every push/PR.

---

## 📄 License

Distributed under the MIT License.
