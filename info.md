# Project Information: Dual-Mode Legal AI Agent

The **Dual-Mode Federal Law and Document AI Intake Agent** is a sophisticated legal research platform designed to provide strictly isolated, high-confidence answers based on two distinct data sources: the U.S. Federal Code and user-uploaded legal documents.

## Core Value Proposition

Unlike generalized AI assistants, this agent enforces **source isolation**. 
- It will never hallucinate federal law when asked about a private contract.
- It will never use general training data to answer specific document-related questions unless explicitly grounded in the provided text.

## Technical Architecture

### 1. Backend: FastAPI & LangGraph
The backend is built with **FastAPI** for high-performance asynchronous API handling. The core logic is orchestrated by **LangGraph**, a framework for building stateful, multi-agent workflows.

- **State Management**: Every query flows through a 13-node graph that handles ingestion, mode classification, entity extraction, planning, isolated retrieval, grading, and verification.
- **Verification Loop**: Before an answer is returned, a dedicated "verify" node checks the LLM's draft against the retrieved evidence to ensure every claim is grounded and cited.

### 2. Isolated Retrieval Layer
We use **Qdrant** as our vector database.
- **Federal Partition**: A curated corpus of U.S. Code Titles (8, 11, 15, 18, 26, 28, 29, 42).
- **Document Partition**: Dynamically created collections per `upload_id` to ensure private documents are never leaked into the global search space.

### 3. Frontend: Next.js & Tailwind
The frontend is a premium, three-pane interface:
- **Navigation/Sidebar**: Seamless switching between "Knowledge Mode" (Federal) and "Analysis Mode" (Documents).
- **Chat Interface**: A clean, focused research environment with markdown support and real-time "thinking" indicators.
- **Context Panel**: A dedicated right-hand panel that displays citations, document metadata, and referenced sources in real-time.

## Tech Stack Highlights

- **LLM**: OpenAI GPT-4o / gpt-4o-mini
- **Orchestration**: LangGraph, Pydantic
- **Vector DB**: Qdrant
- **Database**: PostgreSQL (for session/log persistence)
- **Styling**: Vanilla CSS & Tailwind CSS for a premium, enterprise-grade aesthetic.
- **Icons**: Lucide React
