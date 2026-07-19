"""Explainable quality scoring and vector-similarity checks."""

from dataset_foundry.quality.embeddings import (
    EmbeddingProvider,
    EmbeddingVector,
    LexicalHashEmbedder,
    normalize_text,
)
from dataset_foundry.quality.pipeline import QualityPipeline, training_example_text
from dataset_foundry.quality.scorers import (
    CandidateScorer,
    ExplainableScorer,
    ScoreResult,
    candidate_instruction,
    candidate_response,
    candidate_text,
)
from dataset_foundry.quality.similarity import (
    IncompatibleEmbeddingError,
    SimilarityMatch,
    cosine_similarity,
    is_near_duplicate,
    nearest_match,
)

__all__ = [
    "CandidateScorer",
    "EmbeddingProvider",
    "EmbeddingVector",
    "ExplainableScorer",
    "IncompatibleEmbeddingError",
    "LexicalHashEmbedder",
    "QualityPipeline",
    "ScoreResult",
    "SimilarityMatch",
    "candidate_instruction",
    "candidate_response",
    "candidate_text",
    "cosine_similarity",
    "is_near_duplicate",
    "nearest_match",
    "normalize_text",
    "training_example_text",
]
