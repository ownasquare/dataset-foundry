"""Cosine-similarity boundaries with embedder compatibility enforcement."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from dataset_foundry.quality.embeddings import EmbeddingVector


class IncompatibleEmbeddingError(ValueError):
    """Raised instead of silently comparing vectors from different embedding spaces."""


@dataclass(frozen=True, slots=True)
class SimilarityMatch:
    item_id: str
    similarity: float


def cosine_similarity(left: EmbeddingVector, right: EmbeddingVector) -> float:
    if left.fingerprint != right.fingerprint:
        raise IncompatibleEmbeddingError("embedding fingerprints must match")
    if left.dimension != right.dimension:
        raise IncompatibleEmbeddingError("embedding dimensions must match")
    left_norm = math.sqrt(sum(value * value for value in left.values))
    right_norm = math.sqrt(sum(value * value for value in right.values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(left.values, right.values, strict=True))
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def nearest_match(
    query: EmbeddingVector, candidates: Mapping[str, EmbeddingVector]
) -> SimilarityMatch | None:
    nearest: SimilarityMatch | None = None
    for item_id, vector in candidates.items():
        similarity = cosine_similarity(query, vector)
        if (
            nearest is None
            or similarity > nearest.similarity
            or (similarity == nearest.similarity and item_id < nearest.item_id)
        ):
            nearest = SimilarityMatch(item_id=item_id, similarity=similarity)
    return nearest


def is_near_duplicate(similarity: float, *, threshold: float = 0.92) -> bool:
    if not 0 <= threshold <= 1:
        raise ValueError("similarity threshold must be between 0 and 1")
    return similarity >= threshold
