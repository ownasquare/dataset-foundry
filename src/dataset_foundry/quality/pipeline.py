"""Structural, duplicate, similarity, and explainable scoring pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import numpy as np
from numpy.typing import NDArray

from dataset_foundry.domain import (
    CandidateDecision,
    GeneratedCandidate,
    QualityComponent,
    QualityReport,
    TrainingExample,
)
from dataset_foundry.quality.embeddings import (
    EmbeddingProvider,
    EmbeddingVector,
    LexicalHashEmbedder,
    normalize_text,
)
from dataset_foundry.quality.scorers import CandidateScorer, ExplainableScorer, candidate_text
from dataset_foundry.quality.similarity import (
    IncompatibleEmbeddingError,
    SimilarityMatch,
    is_near_duplicate,
    nearest_match,
)


def training_example_text(example: TrainingExample) -> str:
    return "\n".join(message.content for message in example.messages)


def _nearest(
    text: str,
    values: Sequence[tuple[str, str]],
    embedder: EmbeddingProvider,
) -> SimilarityMatch | None:
    if not values:
        return None
    query = embedder.embed(text)
    vectors = {item_id: embedder.embed(item_text) for item_id, item_text in values}
    return nearest_match(query, vectors)


def _normalized_matrix(
    vectors: Sequence[EmbeddingVector],
    *,
    fingerprint: str,
    dimension: int,
) -> NDArray[np.float32]:
    if not vectors:
        return np.empty((0, dimension), dtype=np.float32)
    if any(vector.fingerprint != fingerprint for vector in vectors):
        raise IncompatibleEmbeddingError("embedding fingerprints must match")
    if any(vector.dimension != dimension for vector in vectors):
        raise IncompatibleEmbeddingError("embedding dimensions must match")
    matrix = np.asarray([vector.values for vector in vectors], dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return cast(NDArray[np.float32], matrix / norms)


def _nearest_from_matrix(
    query: NDArray[np.float32],
    matrix: NDArray[np.float32],
    item_ids: Sequence[str],
) -> SimilarityMatch | None:
    if matrix.shape[0] == 0:
        return None
    similarities = matrix @ query
    raw_maximum = float(np.max(similarities))
    maximum = max(-1.0, min(1.0, raw_maximum))
    tied_indices = np.flatnonzero(np.isclose(similarities, raw_maximum, rtol=0, atol=1e-7))
    selected = min((int(index) for index in tied_indices), key=lambda index: item_ids[index])
    return SimilarityMatch(item_id=item_ids[selected], similarity=maximum)


class QualityPipeline:
    """Evaluate candidates with explicit hard gates and persisted explanations."""

    def __init__(
        self,
        *,
        embedder: EmbeddingProvider | None = None,
        scorer: CandidateScorer | None = None,
        quality_threshold: float = 0.72,
        similarity_threshold: float = 0.92,
        review_margin: float = 0.05,
    ) -> None:
        if not 0 <= quality_threshold <= 1:
            raise ValueError("quality_threshold must be between 0 and 1")
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        if not 0 <= review_margin <= 1:
            raise ValueError("review_margin must be between 0 and 1")
        self.embedder = embedder or LexicalHashEmbedder()
        self.quality_threshold = quality_threshold
        self.similarity_threshold = similarity_threshold
        self.review_margin = review_margin
        self.scorer = scorer or ExplainableScorer()

    def _build_report(
        self,
        candidate: GeneratedCandidate,
        *,
        exact_match_id: str | None,
        seed_nearest: SimilarityMatch | None,
        accepted_nearest: SimilarityMatch | None,
        constraints: list[str] | None,
    ) -> QualityReport:
        nearest = max(
            (match for match in (seed_nearest, accepted_nearest) if match is not None),
            key=lambda match: match.similarity,
            default=None,
        )
        seed_similarity = seed_nearest.similarity if seed_nearest else 0.0
        accepted_similarity = accepted_nearest.similarity if accepted_nearest else 0.0
        score_result = self.scorer.score(
            candidate,
            seed_similarity=seed_similarity,
            accepted_similarity=accepted_similarity,
            constraints=constraints,
        )

        reason_codes: list[str] = []
        explanations: list[str] = []
        decision: CandidateDecision
        if exact_match_id is not None:
            decision = CandidateDecision.rejected
            reason_codes.append("exact_duplicate")
            explanations.append(f"Normalized content exactly matches {exact_match_id}.")
        elif nearest is not None and is_near_duplicate(
            nearest.similarity, threshold=self.similarity_threshold
        ):
            decision = CandidateDecision.rejected
            reason_codes.append("near_duplicate")
            explanations.append(
                f"Similarity {nearest.similarity:.3f} to {nearest.item_id} meets or exceeds "
                f"the {self.similarity_threshold:.3f} threshold."
            )
        elif score_result.score >= self.quality_threshold:
            decision = CandidateDecision.accepted
        elif score_result.score >= max(0.0, self.quality_threshold - self.review_margin):
            decision = CandidateDecision.needs_review
            reason_codes.append("borderline_quality")
            explanations.append(
                f"Score {score_result.score:.3f} is within the human-review margin below "
                f"{self.quality_threshold:.3f}."
            )
        else:
            decision = CandidateDecision.rejected
            reason_codes.append("below_quality_threshold")
            explanations.append(
                f"Score {score_result.score:.3f} is below the "
                f"{self.quality_threshold:.3f} threshold."
            )

        failed_components = [
            component for component in score_result.components if not component.passed
        ]
        for component in failed_components:
            if component.reason_code and component.reason_code not in reason_codes:
                reason_codes.append(component.reason_code)
                explanations.append(component.explanation)

        components: list[QualityComponent] = list(score_result.components)
        return QualityReport(
            candidate_id=candidate.id,
            score=score_result.score,
            automated_decision=decision,
            components=components,
            reason_codes=reason_codes,
            explanations=explanations,
            nearest_match_id=nearest.item_id if nearest else None,
            nearest_similarity=nearest.similarity if nearest else None,
            embedder_fingerprint=self.embedder.fingerprint,
        )

    def evaluate(
        self,
        candidate: GeneratedCandidate,
        *,
        seeds: Sequence[TrainingExample] = (),
        accepted: Sequence[GeneratedCandidate] = (),
        constraints: list[str] | None = None,
    ) -> QualityReport:
        text = candidate_text(candidate)
        normalized = normalize_text(text)
        seed_values = [(seed.id, training_example_text(seed)) for seed in seeds]
        accepted_values = [(item.id, candidate_text(item)) for item in accepted]

        exact = next(
            (
                item_id
                for item_id, item_text in [*seed_values, *accepted_values]
                if normalize_text(item_text) == normalized
            ),
            None,
        )
        seed_nearest = _nearest(text, seed_values, self.embedder)
        accepted_nearest = _nearest(text, accepted_values, self.embedder)
        return self._build_report(
            candidate,
            exact_match_id=exact,
            seed_nearest=seed_nearest,
            accepted_nearest=accepted_nearest,
            constraints=constraints,
        )

    def evaluate_many(
        self,
        candidates: Sequence[GeneratedCandidate],
        *,
        seeds: Sequence[TrainingExample] = (),
        accepted: Sequence[GeneratedCandidate] = (),
        constraints: list[str] | None = None,
    ) -> list[QualityReport]:
        candidate_texts = [candidate_text(candidate) for candidate in candidates]
        candidate_normalized = [normalize_text(text) for text in candidate_texts]
        seed_values = sorted(
            ((seed.id, training_example_text(seed)) for seed in seeds), key=lambda item: item[0]
        )
        seed_ids = [item_id for item_id, _text in seed_values]
        seed_normalized = {normalize_text(text): item_id for item_id, text in seed_values}
        prior_accepted_values = sorted(
            ((item.id, candidate_text(item)) for item in accepted), key=lambda item: item[0]
        )
        prior_accepted_ids = [item_id for item_id, _text in prior_accepted_values]
        prior_accepted_normalized = {
            normalize_text(text): item_id for item_id, text in prior_accepted_values
        }

        candidate_vectors = self.embedder.embed_many(candidate_texts)
        seed_vectors = self.embedder.embed_many([text for _item_id, text in seed_values])
        prior_accepted_vectors = self.embedder.embed_many(
            [text for _item_id, text in prior_accepted_values]
        )
        candidate_matrix = _normalized_matrix(
            candidate_vectors,
            fingerprint=self.embedder.fingerprint,
            dimension=self.embedder.dimension,
        )
        seed_matrix = _normalized_matrix(
            seed_vectors,
            fingerprint=self.embedder.fingerprint,
            dimension=self.embedder.dimension,
        )
        prior_accepted_matrix = _normalized_matrix(
            prior_accepted_vectors,
            fingerprint=self.embedder.fingerprint,
            dimension=self.embedder.dimension,
        )

        accepted_indices: list[int] = []
        accepted_normalized: dict[str, str] = dict(prior_accepted_normalized)
        reports: list[QualityReport] = []
        for index, candidate in enumerate(candidates):
            normalized = candidate_normalized[index]
            exact = seed_normalized.get(normalized) or accepted_normalized.get(normalized)
            seed_nearest = _nearest_from_matrix(candidate_matrix[index], seed_matrix, seed_ids)
            prior_accepted_nearest = _nearest_from_matrix(
                candidate_matrix[index], prior_accepted_matrix, prior_accepted_ids
            )
            current_accepted_ids = [
                candidates[accepted_index].id for accepted_index in accepted_indices
            ]
            current_accepted_matrix = candidate_matrix[accepted_indices]
            current_accepted_nearest = _nearest_from_matrix(
                candidate_matrix[index], current_accepted_matrix, current_accepted_ids
            )
            accepted_nearest = max(
                (
                    match
                    for match in (prior_accepted_nearest, current_accepted_nearest)
                    if match is not None
                ),
                key=lambda match: match.similarity,
                default=None,
            )
            report = self._build_report(
                candidate,
                exact_match_id=exact,
                seed_nearest=seed_nearest,
                accepted_nearest=accepted_nearest,
                constraints=constraints,
            )
            reports.append(report)
            if report.decision is CandidateDecision.accepted:
                accepted_indices.append(index)
                accepted_normalized[normalized] = candidate.id
        return reports
