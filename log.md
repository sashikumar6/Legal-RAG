# Development Log & Changelog

This log tracks the major features, bug fixes, and development progress of the Legal AI Agent.

## [2026-04-01] - Integration & UI Refinement (Latest)

### Added
- **Answerable Sample Questions**: Replaced generic placeholders in `WelcomeGrid.tsx` with specific, grounded questions for Titles 8 (Aliens), 11 (Bankruptcy), 15 (Commerce), 18 (Crime), 26 (Tax), and 29 (Labor).
- **Analysis Mode Chat**: Document-specific chat functionality is now fully operational within `AnalysisView.tsx`.
- **Active Workspace Selection**: Users can now click an uploaded document to activate it for focused Q&A.
- **Enhanced Analysis Panel**: The panel now dynamically displays metadata for the currently active document and lists citations for the active session.

### Fixed
- **Upload Extension Mismatch**: Backend now correctly accepts `.txt` files in addition to `.pdf` and `.docx`.
- **Upload ID Propagation**: `AnalysisView` now correctly passes the specific `upload_id` to the `LegalAI.chat` API, ensuring document-mode isolation.
- **Insufficient Retrieval Error**: Bypassed the strict `insufficient` error block in the LangGraph workflow when Qdrant returns 0 chunks. The LLM now handles low-evidence scenarios natively instead of throwing an agent-level error.
- **Knowledge Panel Text Bug**: Fixed a React rendering bug where citations were incorrectly quoted with string literal brackets.
- **Dead Interaction Cleanup**: Removed non-functional "Connect Drive" and "Attachment" buttons to maintain a professional, reliable UX.

### Modified
- **Lifted Global State**: Hoisted workspace and citation state to the top-level `page.tsx` for seamless reactivity between the central view and the right panel.

## [2024-03-31] - Initial Build & MVP

- **LangGraph Workflow**: Implemented the primary 13-node research logic.
- **Federal Ingestion**: Created the XML parsing pipeline for the U.S. Code.
- **Document Ingestion**: Built the PDF/DOCX processing service with structure-aware chunking.
- **Basic UI**: Established the Next.js foundation with dual-mode support.
- **Infrastructure**: Set up Docker Compose for Postgres, Redis, and Qdrant.
