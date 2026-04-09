"""Tests for health endpoints, mode routing, and isolation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.agents import (
    classify_mode,
    detect_title_hints,
    extract_entities,
    grade_retrieval,
    ingest_input,
    verify_answer,
    GraphState,
)
from app.core.schemas import ConfidenceLevel, QueryMode


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "environment" in data

    def test_liveness(self, client):
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_metrics(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "http_requests_total" in response.text


# ---------------------------------------------------------------------------
# Mode classification tests
# ---------------------------------------------------------------------------

class TestModeClassification:
    def test_federal_mode_with_explicit_reference(self):
        state: GraphState = {
            "query": "What does Title 8 say about immigration?",
            "session_id": "test-session",
        }
        result = classify_mode(state)
        assert result["resolved_mode"] == QueryMode.FEDERAL
        assert not result.get("needs_clarification")

    def test_federal_mode_with_topic(self):
        state: GraphState = {
            "query": "What are the bankruptcy filing requirements?",
            "session_id": "test-session",
        }
        result = classify_mode(state)
        assert result["resolved_mode"] == QueryMode.FEDERAL

    def test_document_mode_with_upload_id(self):
        state: GraphState = {
            "query": "What are the key terms in section 3?",
            "session_id": "test-session",
            "upload_id": "upload-123",
        }
        result = classify_mode(state)
        assert result["resolved_mode"] == QueryMode.DOCUMENT
        assert not result.get("needs_clarification")

    def test_document_mode_without_upload_asks_clarification(self):
        state: GraphState = {
            "query": "What does the uploaded document say about liability?",
            "session_id": "test-session",
        }
        result = classify_mode(state)
        assert result.get("needs_clarification") is True


# ---------------------------------------------------------------------------
# Mode isolation tests
# ---------------------------------------------------------------------------

class TestModeIsolation:
    def test_verify_rejects_cross_mode_federal_to_document(self):
        """Federal mode must not have document citations."""
        state: GraphState = {
            "query": "test",
            "resolved_mode": QueryMode.FEDERAL,
            "draft_answer": "Some answer based on evidence.",
            "confidence": ConfidenceLevel.HIGH,
            "citations": [
                {
                    "source_type": "document",  # VIOLATION
                    "document_id": "doc-1",
                    "text": "some text",
                }
            ],
            "verification_issues": [],
        }
        result = verify_answer(state)
        assert not result["verification_passed"]
        assert any("Mode violation" in i for i in result["verification_issues"])

    def test_verify_rejects_cross_mode_document_to_federal(self):
        """Document mode must not have federal citations."""
        state: GraphState = {
            "query": "test",
            "resolved_mode": QueryMode.DOCUMENT,
            "draft_answer": "Some answer.",
            "confidence": ConfidenceLevel.HIGH,
            "citations": [
                {
                    "source_type": "federal",  # VIOLATION
                    "document_id": "chunk-1",
                    "text": "some text",
                }
            ],
            "verification_issues": [],
        }
        result = verify_answer(state)
        assert not result["verification_passed"]
        assert any("Mode violation" in i for i in result["verification_issues"])

    def test_verify_passes_correct_federal_citations(self):
        """Federal mode with federal citations should pass."""
        state: GraphState = {
            "query": "test",
            "resolved_mode": QueryMode.FEDERAL,
            "draft_answer": "Answer grounded in evidence.",
            "confidence": ConfidenceLevel.HIGH,
            "citations": [
                {
                    "source_type": "federal",
                    "document_id": "chunk-1",
                    "text": "some federal text",
                    "canonical_citation": "8 U.S.C. § 1101",
                }
            ],
            "verification_issues": [],
        }
        result = verify_answer(state)
        assert result["verification_passed"]

    def test_verify_passes_correct_document_citations(self):
        """Document mode with document citations should pass."""
        state: GraphState = {
            "query": "test",
            "resolved_mode": QueryMode.DOCUMENT,
            "draft_answer": "Answer from document.",
            "confidence": ConfidenceLevel.HIGH,
            "citations": [
                {
                    "source_type": "document",
                    "document_id": "chunk-1",
                    "text": "contract clause text",
                    "page_number": 3,
                }
            ],
            "verification_issues": [],
        }
        result = verify_answer(state)
        assert result["verification_passed"]


# ---------------------------------------------------------------------------
# Title hint detection tests
# ---------------------------------------------------------------------------

class TestTitleHints:
    def test_detects_explicit_title(self):
        state: GraphState = {
            "query": "What does Title 18 say about fraud?",
            "resolved_mode": QueryMode.FEDERAL,
            "title_hints": [],
        }
        result = detect_title_hints(state)
        assert 18 in result["title_hints"]

    def test_detects_topic_hints(self):
        state: GraphState = {
            "query": "What are the immigration requirements for naturalization?",
            "resolved_mode": QueryMode.FEDERAL,
            "title_hints": [],
        }
        result = detect_title_hints(state)
        assert 8 in result["title_hints"]

    def test_detects_usc_reference(self):
        state: GraphState = {
            "query": "What is 26 U.S.C. 501(c)(3)?",
            "resolved_mode": QueryMode.FEDERAL,
            "title_hints": [],
        }
        result = detect_title_hints(state)
        assert 26 in result["title_hints"]


# ---------------------------------------------------------------------------
# Entity extraction tests
# ---------------------------------------------------------------------------

class TestEntityExtraction:
    def test_extracts_section_reference(self):
        state: GraphState = {
            "query": "What does section 1101 say?",
            "entities": [],
        }
        result = extract_entities(state)
        assert len(result["entities"]) > 0

    def test_extracts_quoted_terms(self):
        state: GraphState = {
            "query": 'What is the definition of "alien" in federal law?',
            "entities": [],
        }
        result = extract_entities(state)
        assert "alien" in result["entities"]


# ---------------------------------------------------------------------------
# Retrieval grading tests
# ---------------------------------------------------------------------------

class TestRetrievalGrading:
    def test_empty_retrieval_is_insufficient(self):
        state: GraphState = {
            "retrieved_chunks": [],
            "retrieval_score": 0.0,
        }
        result = grade_retrieval(state)
        assert not result["retrieval_sufficient"]
        assert result["confidence"] == ConfidenceLevel.INSUFFICIENT

    def test_high_quality_retrieval(self):
        state: GraphState = {
            "retrieved_chunks": [
                {"score": 0.9, "text": "chunk 1"},
                {"score": 0.85, "text": "chunk 2"},
                {"score": 0.8, "text": "chunk 3"},
            ],
            "retrieval_score": 0.0,
        }
        result = grade_retrieval(state)
        assert result["retrieval_sufficient"]
        assert result["confidence"] == ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# Chat API tests
# ---------------------------------------------------------------------------

class TestChatAPI:
    def test_chat_endpoint_exists(self, client):
        response = client.post(
            "/api/v1/chat",
            json={"query": "What is bankruptcy?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "mode" in data
        assert "confidence" in data
        assert "disclaimer" in data

    def test_chat_with_empty_query_fails(self, client):
        response = client.post(
            "/api/v1/chat",
            json={"query": ""},
        )
        assert response.status_code == 422

    def test_chat_federal_mode(self, client):
        response = client.post(
            "/api/v1/chat",
            json={"query": "What does Title 8 say?", "mode": "federal"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "federal"
