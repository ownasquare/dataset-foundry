from __future__ import annotations

import math

import pytest

from dataset_foundry.quality import (
    EmbeddingVector,
    IncompatibleEmbeddingError,
    LexicalHashEmbedder,
    cosine_similarity,
    is_near_duplicate,
    nearest_match,
)


def vector(cosine: float, *, fingerprint: str = "a" * 64) -> EmbeddingVector:
    return EmbeddingVector(
        values=(cosine, math.sqrt(max(0.0, 1 - cosine * cosine))),
        fingerprint=fingerprint,
    )


def test_similarity_threshold_boundary_is_exact() -> None:
    query = EmbeddingVector(values=(1.0, 0.0), fingerprint="a" * 64)
    below = cosine_similarity(query, vector(0.919))
    above = cosine_similarity(query, vector(0.921))

    assert below == pytest.approx(0.919)
    assert above == pytest.approx(0.921)
    assert not is_near_duplicate(below, threshold=0.92)
    assert is_near_duplicate(above, threshold=0.92)


def test_mismatched_embedding_fingerprints_are_never_compared() -> None:
    with pytest.raises(IncompatibleEmbeddingError, match="fingerprints"):
        cosine_similarity(vector(0.5, fingerprint="a" * 64), vector(0.5, fingerprint="b" * 64))


def test_nearest_match_has_stable_tie_breaking() -> None:
    query = EmbeddingVector(values=(1.0, 0.0), fingerprint="a" * 64)
    match = nearest_match(query, {"z": vector(0.8), "a": vector(0.8)})
    assert match is not None
    assert match.item_id == "a"


def test_lexical_hash_embedding_is_normalized_and_repeatable() -> None:
    embedder = LexicalHashEmbedder(dimension=64)
    first = embedder.embed("Reset the PASSWORD now")
    second = embedder.embed(" reset   the password now ")

    assert first == second
    assert sum(value * value for value in first.values) == pytest.approx(1.0)
    assert len(first.fingerprint) == 64
