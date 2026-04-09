# Dual-Mode Federal Law and Document AI Intake Agent

A production-grade AI-powered legal research system with two strictly isolated modes:

1. **Federal Legal Knowledge Q&A** — Answer general U.S. federal law questions using a curated corpus of selected U.S. Code titles (8, 11, 15, 18, 26, 28, 29, 42) with retrieval-augmented generation and citation support.
2. **Legal Document Q&A** — Upload PDF/DOCX/TXT files and ask questions grounded only in the uploaded document, with page/section/clause-level citations.

> **🆕 Documentation Updates**:
> - For a deep dive into architecture and design decisions, see [info.md](info.md).
> - For the latest development status and fixed issues, see [log.md](log.md).
> - For a step-by-step free deployment on Oracle Cloud, see [ORACLE_DEPLOYMENT.md](docs/ORACLE_DEPLOYMENT.md).

> **⚠️ Disclaimer**: This system does NOT provide legal advice. All outputs are informational only and based on retrieved statutory text. Consult a qualified attorney for legal guidance.

---

## Architecture

```mermaid
graph TB
    subgraph Frontend["Next.js Frontend"]
        UI[Chat Interface]
        UP[Upload Panel]
        CV[Citation Viewer]
        ED[Evidence Drawer]
    end

    subgraph API["FastAPI Backend"]
        GW[API Gateway]
        AUTH[Auth Middleware]
        METRICS[Prometheus Metrics]
    end

    subgraph AgentWorkflow["LangGraph Agent Workflow"]
        II[ingest_input] --> CM[classify_mode]
        CM --> EE[extract_entities]
        EE --> DTH[detect_title_hints]
        DTH --> DDS[detect_document_scope]
        DDS --> MP[make_plan]
        MP --> RTR[route_to_retriever]
        RTR --> RC[retrieve_context]
        RC --> GR[grade_retrieval]
        GR --> GA[generate_answer]
        GA --> VA[verify_answer]
        VA --> ROF[retry_or_finalize]
        ROF --> PLM[persist_logs_and_metrics]
    end

    subgraph Retrieval["Isolated Retrieval"]
        FR[Federal Retriever]
        DR[Document Retriever]
    end

    subgraph Storage["Data Layer"]
        PG[(PostgreSQL)]
        RD[(Redis)]
        QD[(Qdrant)]
    end

    subgraph Workers["Background Workers"]
        CW[Celery Workers]
        FI[Federal Ingestion]
        DI[Document Ingestion]
    end

    UI --> GW
    UP --> GW
    GW --> II
    RTR --> FR
    RTR --> DR
    FR --> QD
    DR --> QD
    CW --> FI
    CW --> DI
    FI --> QD
    DI --> QD
    PLM --> PG
    GW --> RD
```

## Sequence Diagrams

### Federal Legal Knowledge Q&A Mode

```mermaid
sequenceDiagram
    actor User
    participant FE as Next.js Frontend
    participant API as FastAPI
    participant Agent as LangGraph Agent
    participant FR as Federal Retriever
    participant Qdrant as Qdrant VectorDB
    participant LLM as LLM Provider
    participant DB as PostgreSQL

    User->>FE: Ask federal law question
    FE->>API: POST /chat {query, mode: auto}
    API->>Agent: ingest_input(query)
    Agent->>Agent: classify_mode → FEDERAL
    Agent->>Agent: extract_entities
    Agent->>Agent: detect_title_hints
    Agent->>Agent: make_plan
    Agent->>FR: route_to_retriever(FEDERAL)
    FR->>Qdrant: Search federal corpus (filtered by title hints)
    Qdrant-->>FR: Retrieved chunks with metadata
    FR-->>Agent: Ranked evidence chunks
    Agent->>Agent: grade_retrieval (confidence check)
    alt Retrieval is strong
        Agent->>LLM: generate_answer(query, evidence)
        LLM-->>Agent: Draft answer with citations
        Agent->>Agent: verify_answer (check claims vs evidence)
        alt Verification passes
            Agent->>DB: persist_logs_and_metrics
            Agent-->>API: Final answer + citations + confidence
            API-->>FE: Response with evidence
            FE-->>User: Display answer + citation viewer
        else Verification fails
            Agent->>Agent: retry_or_finalize (stricter grounding)
            Agent-->>API: Refined answer or insufficient evidence
        end
    else Retrieval is weak
        Agent->>Agent: retry retrieval once
        alt Still weak
            Agent-->>API: "Insufficient evidence" response
        end
    end
```

### Legal Document Q&A Mode

```mermaid
sequenceDiagram
    actor User
    participant FE as Next.js Frontend
    participant API as FastAPI
    participant Worker as Celery Worker
    participant Parser as PDF/DOCX Parser
    participant Qdrant as Qdrant VectorDB
    participant Agent as LangGraph Agent
    participant DR as Document Retriever
    participant LLM as LLM Provider

    User->>FE: Upload PDF/DOCX
    FE->>API: POST /upload (multipart)
    API->>Worker: Enqueue document processing
    Worker->>Parser: Parse document
    Parser-->>Worker: Extracted text + page/heading metadata
    Worker->>Worker: Structure-aware chunking
    Worker->>Qdrant: Index chunks (upload_id isolated)
    Worker-->>API: Processing complete
    API-->>FE: Document ready

    User->>FE: Ask question about uploaded document
    FE->>API: POST /chat {query, upload_id}
    API->>Agent: ingest_input(query, upload_id)
    Agent->>Agent: classify_mode → DOCUMENT
    Agent->>Agent: detect_document_scope
    Agent->>DR: route_to_retriever(DOCUMENT, upload_id)
    DR->>Qdrant: Search ONLY upload_id collection
    Qdrant-->>DR: Document-specific chunks
    DR-->>Agent: Evidence with page/heading refs
    Agent->>Agent: grade_retrieval
    Agent->>LLM: generate_answer(query, doc_evidence)
    LLM-->>Agent: Answer with page/section citations
    Agent->>Agent: verify_answer
    Agent-->>API: Final answer + document citations
    API-->>FE: Response with evidence drawer
    FE-->>User: Display answer + page references
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js, React, Tailwind CSS |
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Cache/Queue | Redis, Celery |
| Vector Store | Qdrant |
| Agent Framework | LangGraph |
| Document Parsing | PyMuPDF, python-docx, pdfplumber |
| Federal Corpus | lxml, USLM XML parsing |
| Observability | Prometheus metrics |
| Infra | Docker, Docker Compose, Nginx |

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes
│   │   ├── agents/         # LangGraph workflow
│   │   ├── retrieval/      # Federal + Document retrievers
│   │   ├── ingestion/      # Federal corpus XML parsing
│   │   ├── document_ingestion/  # PDF/DOCX processing
│   │   ├── database/       # SQLAlchemy models + Alembic
│   │   ├── services/       # Business logic
│   │   ├── observability/  # Prometheus metrics
│   │   ├── workers/        # Celery tasks
│   │   ├── core/           # Config, settings, utils
│   │   └── tests/          # Test suite
│   ├── alembic/            # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── infra/
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── .env.example
├── docs/
├── scripts/
└── sample_data/
```

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### Local Development

```bash
# 1. Clone and configure
cp infra/.env.example .env

# 2. Start infrastructure
docker compose -f infra/docker-compose.yml up -d

# 3. Run backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 4. Run frontend
cd frontend
npm install
npm run dev

# 5. Ingest federal corpus
python -m app.ingestion.run_ingestion
```

### Docker Deployment

```bash
docker compose -f infra/docker-compose.yml --profile full up --build
```

---

## Deployment (100% Free Forever Stack)

This project is optimized to run entirely on the **Free Tiers** of various cloud providers, ensuring $0/month cost.

### 1. Provision Free Services
You will need to create free accounts and get connection strings from these providers:

*   **Frontend & Backend**: [Render](https://render.com) (Free Web Service)
*   **Database**: [Supabase](https://supabase.com) (Free Postgres)
*   **Vector Store**: [Qdrant Cloud](https://qdrant.tech/cloud/) (Free Cluster)
*   **Redis (Cache/Queue)**: [Upstash](https://upstash.com) (Free Redis)

### 2. Configure Render Blueprint
1.  Log in to [Render](https://dashboard.render.com/) and click **New > Blueprint**.
2.  Connect your GitHub repository.
3.  Render will detect the `render.yaml` file. Click **Apply**.
4.  **Important**: In the Render dashboard, go to the **backend** service and set these Environment Variables:
    *   `DATABASE_URL`: Your Supabase URI (`postgresql://...`)
    *   `REDIS_URL`: Your Upstash Redis URL (`redis://...`)
    *   `QDRANT_HOST`: Your Qdrant Cloud Cluster URL (`https://...`)
    *   `QDRANT_API_KEY`: Your Qdrant Cloud API Key
    *   `OPENAI_API_KEY`: Your OpenAI API Key

### 3. Data Ingestion (Free Tier)
Since Render's free tier has no persistent disk, the federal law XML data is not stored on the server.
1.  **Local Ingestion**: The easiest way is to run the ingestion from your local machine, pointing to your **Qdrant Cloud** URL.
    ```bash
    # In your local backend folder
    export QDRANT_HOST="https://your-qdrant-cloud-url"
    export QDRANT_API_KEY="your-api-key"
    python -m app.ingestion.run_ingestion
    ```
2.  **Document Uploads**: In the "Document Q&A" mode, files you upload are processed and stored in Qdrant Cloud. They will persist even if the Render service restarts.

---

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Submit a query (auto-detects mode or uses explicit mode) |
| `/upload` | POST | Upload PDF/DOCX for document Q&A |
| `/retrieval` | POST | Direct retrieval endpoint for testing |
| `/health` | GET | Overall health check |
| `/health/live` | GET | Liveness probe |
| `/health/ready` | GET | Readiness probe |
| `/metrics` | GET | Prometheus metrics endpoint |

---

## Federal Corpus

> [!NOTE]
> **Current Scope**: Due to vector storage and performance constraints in the current development environment, the RAG index is currently optimized for **Title 11 (Bankruptcy)** and **Title 26 (Internal Revenue Code)**.

The system is architected to ingest U.S. Code XML (USLM format). The following titles are supported by the parser, with **11** and **26** currently active in the production-ready index:

| Title | Subject | Status |
|-------|---------|--------|
| 8 | Aliens and Nationality | Parser Ready |
| **11** | **Bankruptcy** | **Index Active** |
| 15 | Commerce and Trade | Parser Ready |
| 18 | Crimes and Criminal Procedure | Parser Ready |
| **26** | **Internal Revenue Code** | **Index Active** |
| 28 | Judiciary and Judicial Procedure | Parser Ready |
| 29 | Labor | Parser Ready |
| 42 | The Public Health and Welfare | Parser Ready |

---

## Roadmap & Future Plans

We are actively working to expand the system's breadth and depth:

1.  **Full U.S. Code Coverage**: Expanding the elastic vector index to support all 54 U.S. Code titles.
2.  **State Law Integration**: Incorporating state-level statutes, starting with major jurisdictions (CA, NY, TX, FL).
3.  **Jurisdictional Cross-Referencing**: Enabling the agent to identify conflicts or overlaps between federal and state laws.
4.  **Case Law Integration**: Moving beyond statutes to include relevant judicial precedents and court rulings.

---

## Mode Isolation Rules

1. **Federal mode**: Retrieves ONLY from the federal U.S. Code corpus
2. **Document mode**: Retrieves ONLY from the active uploaded document
3. **Ambiguous queries**: System asks a clarifying question
4. **Never mix**: Federal and document evidence are never combined
5. **No silent fallback**: If retrieval is weak, the system says so explicitly

---

## License

MIT
