"""Qdrant client factory and collection management.

Default: Docker-hosted Qdrant.
Optional developer fallback: local-file mode via DEV_QDRANT_LOCAL_MODE=true.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def create_qdrant_client():
    """Create a Qdrant client based on configuration.
    
    - Default: connects to Docker-hosted Qdrant at qdrant_host:qdrant_port
    - Dev fallback: local-file mode when DEV_QDRANT_LOCAL_MODE=true
    
    Returns None if connection fails (logged as error).
    """
    from qdrant_client import QdrantClient

    if settings.dev_qdrant_local_mode:
        logger.info(
            f"Using local-file Qdrant (dev mode) at: {settings.dev_qdrant_local_path}"
        )
        try:
            client = QdrantClient(path=settings.dev_qdrant_local_path)
            return client
        except Exception as e:
            logger.error(f"Failed to create local Qdrant client: {e}")
            return None

    # Production default: Docker-hosted Qdrant
    logger.info(f"Connecting to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}")
    try:
        client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key,
            timeout=10,
        )
        # Verify connection
        client.get_collections()
        logger.info("Qdrant connection established")
        return client
    except Exception as e:
        logger.error(
            f"Failed to connect to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}: {e}. "
            f"Hint: Start Qdrant with 'docker run -p 6333:6333 qdrant/qdrant' "
            f"or set DEV_QDRANT_LOCAL_MODE=true for local-file fallback."
        )
        return None


def ensure_collections(client) -> None:
    """Create Qdrant collections if they don't exist."""
    if client is None:
        logger.warning("No Qdrant client — cannot ensure collections")
        return

    from qdrant_client.models import Distance, VectorParams

    for collection_name in [
        settings.qdrant_federal_collection,
        settings.qdrant_document_collection,
    ]:
        try:
            client.get_collection(collection_name)
            logger.info(f"Collection '{collection_name}' exists")
        except Exception:
            try:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=settings.embedding_dimensions,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created collection '{collection_name}'")
            except Exception as e:
                logger.error(f"Failed to create collection '{collection_name}': {e}")


def get_collection_info(client, collection_name: str) -> Optional[dict]:
    """Get collection info for inspection."""
    if client is None:
        return None
    try:
        info = client.get_collection(collection_name)
        return {
            "name": collection_name,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": str(info.status),
        }
    except Exception as e:
        logger.error(f"Failed to get collection info for '{collection_name}': {e}")
        return None
