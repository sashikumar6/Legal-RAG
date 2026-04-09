"""Core configuration and settings for the application."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class QueryMode(str, Enum):
    """Strictly isolated query modes."""
    FEDERAL = "federal"
    DOCUMENT = "document"
    AUTO = "auto"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Federal Law & Document AI Intake Agent"
    app_version: str = "0.2.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    api_prefix: str = "/api/v1"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/federal_law_agent"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/federal_law_agent"
    database_pool_size: int = 20
    database_max_overflow: int = 10


    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_api_key: Optional[str] = None
    qdrant_federal_collection: str = "federal_corpus"
    qdrant_document_collection: str = "uploaded_documents"

    # Developer fallback: use local-file Qdrant instead of Docker.
    # Set to true ONLY for local development when Docker is unavailable.
    # Docker Qdrant is the production default.
    dev_qdrant_local_mode: bool = False
    dev_qdrant_local_path: str = "./qdrant_local_data"

    # LLM — OPENAI_API_KEY must be set in environment or .env for real calls.
    openai_api_key: Optional[str] = None
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # OpenAI retry settings
    openai_max_retries: int = 3
    openai_retry_base_delay: float = 1.0
    openai_retry_max_delay: float = 30.0

    # Federal Corpus
    federal_xml_base_path: str = Field(
        default_factory=lambda: os.environ.get(
            "FEDERAL_XML_BASE_PATH",
            str(Path(__file__).parent.parent.parent.parent)
        )
    )
    federal_titles: list[int] = [11, 18]

    @field_validator("federal_titles", mode="before")
    @classmethod
    def parse_federal_titles(cls, v: Any) -> list[int]:
        if isinstance(v, str):
            if v.startswith("["):
                import json
                try:
                    return [int(x) for x in json.loads(v)]
                except Exception:
                    pass
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v

    # Document Upload
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50
    allowed_extensions: list[str] = [".pdf", ".docx", ".txt"]

    # Retrieval
    retrieval_top_k: int = 10
    retrieval_score_threshold: float = 0.65
    retrieval_rerank_top_k: int = 5

    # Verification
    verification_confidence_threshold: float = 0.7
    max_retries: int = 1

    cors_origins: str | list[str] = ["http://localhost:3000", "http://localhost:8080"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    model_config = {
        "env_file": "../infra/.env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Global settings instance
settings = Settings()

# Title number to filename mapping
TITLE_FILE_MAP: dict[int, str] = {
    8: "usc08.xml",
    11: "usc11.xml",
    15: "usc15.xml",
    18: "usc18.xml",
    26: "usc26.xml",
    28: "usc28.xml",
    29: "usc29.xml",
    42: "usc42.xml",
}

TITLE_NAME_MAP: dict[int, str] = {
    8: "Aliens and Nationality",
    11: "Bankruptcy",
    15: "Commerce and Trade",
    18: "Crimes and Criminal Procedure",
    26: "Internal Revenue Code",
    28: "Judiciary and Judicial Procedure",
    29: "Labor",
    42: "The Public Health and Welfare",
}
