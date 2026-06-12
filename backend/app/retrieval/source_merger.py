"""Source merger — combines and deduplicates results from multiple retrieval sources.

Used by CROSS_SOURCE mode to merge federal, CFR, and case law chunks.
Implements text cosine-similarity deduplication (threshold 0.95) and
explicit conflict detection. Never silently resolves conflicts.
"""

from __future__ import annotations

import logging
import re
from math import sqrt
from typing import Any

logger = logging.getLogger(__name__)

_DEDUP_THRESHOLD = 0.95
_CONFLICT_THRESHOLD = 0.70

# Phrases that signal a legal position may differ from an affirmative statement
_NEGATION_PATTERNS = [
    "not required", "not necessary", "does not require", "is not",
    "shall not", "may not", "cannot", "must not", "prohibited",
    "inapplicable", "does not apply", "exception", "notwithstanding",
    "overruled", "reversed", "vacated",
]


# ---------------------------------------------------------------------------
# Text cosine similarity helpers
# ---------------------------------------------------------------------------

def _tf_vector(text: str) -> dict[str, float]:
    """Compute a normalized term-frequency vector for a text string."""
    tokens = re.findall(r'\b[a-z0-9]+\b', text.lower())
    if not tokens:
        return {}
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    n = len(tokens)
    return {k: v / n for k, v in freq.items()}


def _cosine_similarity(a: str, b: str) -> float:
    """Cosine similarity of term-frequency vectors for two text strings."""
    va = _tf_vector(a)
    vb = _tf_vector(b)
    if not va or not vb:
        return 0.0
    dot = sum(va.get(k, 0.0) * vb.get(k, 0.0) for k in va)
    mag_a = sqrt(sum(v * v for v in va.values()))
    mag_b = sqrt(sum(v * v for v in vb.values()))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def _extract_topic_hint(text_a: str, text_b: str, max_len: int = 80) -> str:
    """Extract a short topic hint from the shared vocabulary of two texts."""
    _STOPWORDS = {
        "that", "this", "with", "from", "have", "been", "will", "shall",
        "which", "their", "there", "where", "when", "what", "such", "under",
        "section", "court", "federal", "states", "united", "code", "also",
    }
    tokens_a = set(re.findall(r'\b[a-z]{4,}\b', text_a.lower()))
    tokens_b = set(re.findall(r'\b[a-z]{4,}\b', text_b.lower()))
    common = sorted((tokens_a & tokens_b) - _STOPWORDS)
    hint = ", ".join(common[:6])
    return hint[:max_len] if hint else "overlapping legal topic"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate(chunks: list[dict], threshold: float) -> list[dict]:
    """
    Remove near-duplicate chunks using text cosine similarity.

    When two chunks exceed the threshold, keep the one with the higher score.
    O(n²) — acceptable for retrieval result sets (typically ≤ 30 chunks).
    """
    if len(chunks) <= 1:
        return chunks

    dropped: set[int] = set()
    for i in range(len(chunks)):
        if i in dropped:
            continue
        for j in range(i + 1, len(chunks)):
            if j in dropped:
                continue
            sim = _cosine_similarity(
                chunks[i].get("text", ""),
                chunks[j].get("text", ""),
            )
            if sim > threshold:
                score_i = chunks[i].get("score", 0.0)
                score_j = chunks[j].get("score", 0.0)
                if score_j > score_i:
                    dropped.add(i)
                    logger.debug(f"Dedup: dropped chunk {i} (sim={sim:.3f}) in favour of chunk {j}")
                else:
                    dropped.add(j)
                    logger.debug(f"Dedup: dropped chunk {j} (sim={sim:.3f}) in favour of chunk {i}")

    retained = [c for idx, c in enumerate(chunks) if idx not in dropped]
    if len(chunks) != len(retained):
        logger.info(f"Deduplication: {len(chunks)} → {len(retained)} chunks")
    return retained


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def _detect_conflicts(chunks: list[dict], threshold: float) -> list[dict]:
    """
    Detect potential conflicts between chunks from different source_types.

    A conflict is flagged when:
    - Two chunks from different source_types have cosine similarity > threshold
      (same legal concept / topic area)
    - One chunk contains negation or limiting language the other does not

    Conflicts are NEVER silently resolved — they are always surfaced.
    """
    conflicts: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for i, ci in enumerate(chunks):
        for j, cj in enumerate(chunks):
            if j <= i:
                continue
            source_i = ci.get("metadata", {}).get("source_type", "")
            source_j = cj.get("metadata", {}).get("source_type", "")
            if source_i == source_j:
                continue

            text_i = ci.get("text", "").lower()
            text_j = cj.get("text", "").lower()
            sim = _cosine_similarity(text_i, text_j)
            if sim < threshold:
                continue

            neg_i = any(p in text_i for p in _NEGATION_PATTERNS)
            neg_j = any(p in text_j for p in _NEGATION_PATTERNS)
            if neg_i == neg_j:
                continue

            # Deduplicate identical conflict pairs regardless of direction
            key = tuple(sorted([source_i, source_j]))
            topic = _extract_topic_hint(text_i, text_j)
            full_key = (key[0], key[1], topic)
            if full_key in seen:
                continue
            seen.add(full_key)

            conflict = {
                "source_a": source_i,
                "source_b": source_j,
                "topic": topic,
                "description": (
                    f"Potential conflict between {source_i} and {source_j} on: {topic}. "
                    f"One source contains limiting or negating language not present in the other. "
                    f"Review both sources carefully."
                ),
            }
            conflicts.append(conflict)
            logger.info(
                f"Conflict detected: {source_i} vs {source_j} "
                f"(sim={sim:.3f}, topic={topic!r})"
            )

    return conflicts


# ---------------------------------------------------------------------------
# SourceMerger
# ---------------------------------------------------------------------------

class SourceMerger:
    """
    Merges retrieval results from federal, CFR, and case law sources.

    Steps:
    1. Combine all chunks, preserving source_type metadata.
    2. Deduplicate: cosine similarity > 0.95 → keep the higher-scoring chunk.
    3. Detect conflicts: same legal concept, materially different statements
       across different source_types. Never silently resolve — always surface.
    4. Return merged result with chunks, conflicts, and sources_used.
    """

    def merge(
        self,
        federal_chunks: list[dict],
        cfr_chunks: list[dict],
        case_law_chunks: list[dict],
    ) -> dict[str, Any]:
        """
        Merge chunks from federal, CFR, and case law sources.

        Returns:
            {
                "chunks":       deduplicated list (highest-scoring wins on ties),
                "conflicts":    list of conflict dicts, empty if none detected,
                "sources_used": list of source_type strings with results,
            }
        """
        all_chunks = list(federal_chunks) + list(cfr_chunks) + list(case_law_chunks)

        sources_used: list[str] = []
        if federal_chunks:
            sources_used.append("federal")
        if cfr_chunks:
            sources_used.append("cfr")
        if case_law_chunks:
            sources_used.append("case_law")

        if not all_chunks:
            return {"chunks": [], "conflicts": [], "sources_used": sources_used}

        deduped = _deduplicate(all_chunks, _DEDUP_THRESHOLD)
        conflicts = _detect_conflicts(deduped, _CONFLICT_THRESHOLD)

        logger.info(
            f"SourceMerger: {len(all_chunks)} raw → {len(deduped)} after dedup, "
            f"{len(conflicts)} conflict(s), sources={sources_used}"
        )

        return {
            "chunks": deduped,
            "conflicts": conflicts,
            "sources_used": sources_used,
        }
