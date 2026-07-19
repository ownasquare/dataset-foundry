"""Deterministic lexical embeddings and an adapter protocol for future models."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from typing import Protocol

from dataset_foundry.ingestion.fingerprint import fingerprint_mapping

_TOKEN_PATTERN = re.compile(r"\b[\w-]+\b", flags=re.UNICODE)


@lru_cache(maxsize=200_000)
def _lexical_values(normalized_text: str, dimension: int) -> tuple[float, ...]:
    """Cache deterministic vectors reused across seeds, batches, and recovery."""

    tokens = _TOKEN_PATTERN.findall(normalized_text)
    features = [*tokens, *(f"{left}:{right}" for left, right in pairwise(tokens))]
    values = [0.0] * dimension
    for feature in features:
        digest = hashlib.blake2b(
            feature.encode("utf-8"), digest_size=8, usedforsecurity=False
        ).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimension
        sign = -1.0 if digest[4] & 1 else 1.0
        values[bucket] += sign
    norm = math.sqrt(sum(value * value for value in values))
    if norm:
        values = [value / norm for value in values]
    return tuple(values)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(normalized.split())


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    values: tuple[float, ...]
    fingerprint: str

    @property
    def dimension(self) -> int:
        return len(self.values)


class EmbeddingProvider(Protocol):
    @property
    def fingerprint(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, text: str) -> EmbeddingVector: ...

    def embed_many(self, texts: list[str]) -> list[EmbeddingVector]: ...


class LexicalHashEmbedder:
    """Stable unigram/bigram hashing for tests and explicitly lexical demo quality."""

    name = "lexical-hash-v1"

    def __init__(self, *, dimension: int = 384) -> None:
        if not 64 <= dimension <= 2_048:
            raise ValueError("embedding dimension must be between 64 and 2048")
        self._dimension = dimension
        self._fingerprint = fingerprint_mapping(
            {"name": self.name, "version": 1, "dimension": dimension, "features": "uni+bi"}
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def embed(self, text: str) -> EmbeddingVector:
        values = _lexical_values(normalize_text(text), self.dimension)
        return EmbeddingVector(values=values, fingerprint=self.fingerprint)

    def embed_many(self, texts: list[str]) -> list[EmbeddingVector]:
        return [self.embed(text) for text in texts]
