"""Smallest runnable custom quality-scorer example."""

from dataset_foundry.domain import (
    ChatMessage,
    GeneratedCandidate,
    ProviderName,
    ProviderTrace,
    QualityComponent,
)
from dataset_foundry.quality import QualityPipeline, ScoreResult, candidate_response


class PolicyPhraseScorer:
    """Accept examples only when the response names an approved escalation path."""

    def score(
        self,
        candidate: GeneratedCandidate,
        *,
        seed_similarity: float,
        accepted_similarity: float,
        constraints: list[str] | None = None,
    ) -> ScoreResult:
        del seed_similarity, accepted_similarity, constraints
        grounded = "billing specialist" in candidate_response(candidate).casefold()
        component = QualityComponent(
            name="policy_grounding",
            score=1.0 if grounded else 0.0,
            passed=grounded,
            reason_code=None if grounded else "missing_escalation_path",
            explanation=(
                "The approved billing-specialist escalation path is present."
                if grounded
                else "The response must name the billing-specialist escalation path."
            ),
        )
        return ScoreResult(score=component.score, components=(component,))


def build_quality_pipeline(
    *,
    quality_threshold: float,
    similarity_threshold: float,
) -> QualityPipeline:
    """Factory that can be injected into ``Container`` for worker-backed runs."""

    return QualityPipeline(
        quality_threshold=quality_threshold,
        similarity_threshold=similarity_threshold,
        scorer=PolicyPhraseScorer(),
    )


candidate = GeneratedCandidate(
    id="custom-scorer-example",
    messages=[
        ChatMessage(role="user", content="Who handles a disputed duplicate charge?"),
        ChatMessage(
            role="assistant",
            content="Verify both charges, then escalate the case to a billing specialist.",
        ),
    ],
    source_seed_ids=["example-seed"],
    provider_trace=ProviderTrace(
        provider=ProviderName.offline,
        model="offline-deterministic-v1",
        mode="offline-deterministic",
    ),
)

if __name__ == "__main__":
    report = build_quality_pipeline(
        quality_threshold=0.72,
        similarity_threshold=0.92,
    ).evaluate(candidate)
    print(report.decision.value, report.score, report.reason_codes)
