"""OpenAI LLM and Embeddings client with retry logic and token tracking.

This module provides the real OpenAI integration used by the agent workflow.
It fails explicitly if the API key is missing — no silent fallback.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional

from app.core.config import settings
from app.observability import (
    llm_call_duration_seconds,
    llm_calls_total,
    llm_failures_total,
    llm_retry_total,
    llm_tokens_completion_total,
    llm_tokens_prompt_total,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry with exponential backoff + jitter
# ---------------------------------------------------------------------------

def _retry_with_backoff(
    fn,
    *,
    max_retries: int,
    base_delay: float,
    max_delay: float,
    operation: str,
    model: str,
):
    """Execute fn() with exponential backoff + jitter on transient failures."""
    import openai

    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError,
        ) as e:
            last_exc = e
            if attempt == max_retries:
                break
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
            logger.warning(
                f"OpenAI {operation} transient error (attempt {attempt + 1}/{max_retries + 1}): "
                f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s"
            )
            llm_retry_total.labels(model=model, operation=operation).inc()
            llm_failures_total.labels(model=model, error_type="transient").inc()
            time.sleep(delay)
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI authentication failed: {e}")
            llm_failures_total.labels(model=model, error_type="auth").inc()
            raise
        except openai.BadRequestError as e:
            logger.error(f"OpenAI bad request: {e}")
            llm_failures_total.labels(model=model, error_type="bad_request").inc()
            raise

    llm_failures_total.labels(model=model, error_type="exhausted_retries").inc()
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# OpenAI Chat Completion
# ---------------------------------------------------------------------------

def get_openai_client():
    """Get a configured OpenAI client. Raises if API key is missing."""
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Real LLM calls require a valid API key. "
            "Set it in your .env file or environment variables."
        )
    import openai
    return openai.OpenAI(api_key=settings.openai_api_key)


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    operation: str = "chat_completion",
) -> tuple[str, dict]:
    """Call OpenAI chat completion with retry logic.
    
    Returns (response_text, usage_info).
    Raises RuntimeError if API key is missing.
    Raises openai errors after retries are exhausted.
    """
    client = get_openai_client()
    _model = model or settings.llm_model
    _temperature = temperature if temperature is not None else settings.llm_temperature
    _max_tokens = max_tokens or settings.llm_max_tokens

    llm_calls_total.labels(model=_model, operation=operation).inc()

    def _call():
        return client.chat.completions.create(
            model=_model,
            messages=messages,
            temperature=_temperature,
            max_tokens=_max_tokens,
        )

    start_time = time.perf_counter()
    try:
        response = _retry_with_backoff(
            _call,
            max_retries=settings.openai_max_retries,
            base_delay=settings.openai_retry_base_delay,
            max_delay=settings.openai_retry_max_delay,
            operation=operation,
            model=_model,
        )
    finally:
        duration = time.perf_counter() - start_time
        llm_call_duration_seconds.labels(model=_model, operation=operation).observe(duration)

    content = response.choices[0].message.content or ""
    usage = {}
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
        # Track token usage in Prometheus
        llm_tokens_prompt_total.labels(model=_model).inc(response.usage.prompt_tokens)
        llm_tokens_completion_total.labels(model=_model).inc(response.usage.completion_tokens)

        logger.info(
            f"OpenAI {operation}: model={_model}, "
            f"prompt_tokens={usage['prompt_tokens']}, "
            f"completion_tokens={usage['completion_tokens']}, "
            f"total_tokens={usage['total_tokens']}, "
            f"duration={duration:.2f}s"
        )

    return content, usage


# ---------------------------------------------------------------------------
# OpenAI Embeddings
# ---------------------------------------------------------------------------

def create_embedding_fn():
    """Create an embedding function using OpenAI.
    
    Returns a callable: (list[str]) -> list[list[float]]
    Raises RuntimeError if API key is missing.
    """
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Embeddings require a valid API key."
        )
    import openai
    client = openai.OpenAI(api_key=settings.openai_api_key)

    def embed(texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts with retry logic."""
        llm_calls_total.labels(model=settings.embedding_model, operation="embed").inc()

        # OpenAI batch limit is 2048 inputs; chunk if needed
        all_embeddings: list[list[float]] = []
        batch_size = 512

        start_time = time.perf_counter()
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            def _call(batch=batch):
                return client.embeddings.create(
                    model=settings.embedding_model,
                    input=batch,
                    dimensions=settings.embedding_dimensions,
                )

            response = _retry_with_backoff(
                _call,
                max_retries=settings.openai_max_retries,
                base_delay=settings.openai_retry_base_delay,
                max_delay=settings.openai_retry_max_delay,
                operation="embed",
                model=settings.embedding_model,
            )
            all_embeddings.extend([d.embedding for d in response.data])

            if response.usage:
                llm_tokens_prompt_total.labels(model=settings.embedding_model).inc(
                    response.usage.total_tokens
                )
                logger.debug(
                    f"Embedding batch {i // batch_size + 1}: "
                    f"{response.usage.total_tokens} tokens"
                )

        duration = time.perf_counter() - start_time
        llm_call_duration_seconds.labels(
            model=settings.embedding_model, operation="embed"
        ).observe(duration)

        return all_embeddings

    return embed


def check_openai_configured() -> bool:
    """Check if OpenAI is properly configured."""
    return bool(settings.openai_api_key)
