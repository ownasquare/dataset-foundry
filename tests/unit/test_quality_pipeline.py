from __future__ import annotations

from dataset_foundry.domain import (
    CandidateDecision,
    ChatMessage,
    GeneratedCandidate,
    MessageRole,
    ProviderName,
    ProviderTrace,
    QualityComponent,
    TrainingExample,
)
from dataset_foundry.quality import (
    EmbeddingVector,
    LexicalHashEmbedder,
    QualityPipeline,
    ScoreResult,
)


class CountingEmbedder:
    def __init__(self) -> None:
        self.base = LexicalHashEmbedder(dimension=64)
        self.embed_calls = 0

    @property
    def fingerprint(self) -> str:
        return self.base.fingerprint

    @property
    def dimension(self) -> int:
        return self.base.dimension

    def embed(self, text: str) -> EmbeddingVector:
        self.embed_calls += 1
        return self.base.embed(text)

    def embed_many(self, texts: list[str]) -> list[EmbeddingVector]:
        return [self.embed(text) for text in texts]


class FixedScorer:
    def score(self, *_args: object, **_kwargs: object) -> ScoreResult:
        component = QualityComponent(
            name="policy_grounding",
            score=0.2,
            passed=False,
            reason_code="policy_not_grounded",
            explanation="The answer does not cite an allowed policy fact.",
        )
        return ScoreResult(score=0.2, components=(component,))


def candidate(identifier: str, instruction: str, response: str) -> GeneratedCandidate:
    return GeneratedCandidate(
        id=identifier,
        messages=[
            ChatMessage(role=MessageRole.user, content=instruction),
            ChatMessage(role=MessageRole.assistant, content=response),
        ],
        source_seed_ids=["seed-root"],
        provider_trace=ProviderTrace(
            provider=ProviderName.offline,
            model="offline-deterministic-v1",
            mode="offline-deterministic",
        ),
    )


def test_exact_normalized_duplicates_always_reject_with_explanation() -> None:
    seed = TrainingExample(
        id="seed-1",
        messages=[
            ChatMessage(role="user", content="How do I reset my password?"),
            ChatMessage(
                role="assistant",
                content="Request a new link and use only the latest email.",
            ),
        ],
    )
    duplicate = candidate(
        "candidate-1",
        "  HOW do I reset my password? ",
        "Request a new link and use only the latest email.",
    )

    report = QualityPipeline().evaluate(duplicate, seeds=[seed])

    assert report.decision is CandidateDecision.rejected
    assert "exact_duplicate" in report.reason_codes
    assert report.explanations


def test_high_quality_candidate_is_accepted_with_explainable_components() -> None:
    generated = candidate(
        "candidate-2",
        "A customer sees two pending charges after one checkout. What should support do?",
        "Confirm that the order was submitted once, explain that one entry may be a temporary "
        "authorization, and ask the customer to wait for settlement. Open a billing "
        "investigation if both charges post to the account.",
    )

    report = QualityPipeline().evaluate(generated)

    assert report.decision is CandidateDecision.accepted
    assert report.score >= 0.72
    assert {component.name for component in report.components} >= {
        "completeness",
        "seed_novelty",
        "accepted_pool_diversity",
        "constraints",
    }


def test_low_quality_and_constraint_failures_are_machine_readable() -> None:
    generated = candidate("candidate-3", "Do it.", "Generated response")
    report = QualityPipeline(quality_threshold=0.95).evaluate(
        generated, constraints=["must_include:verified reference"]
    )

    assert report.decision is CandidateDecision.rejected
    assert "below_quality_threshold" in report.reason_codes
    assert "boilerplate_detected" in report.reason_codes
    assert "constraint_violation" in report.reason_codes


def test_evaluate_many_deduplicates_against_the_accepted_pool() -> None:
    first = candidate(
        "candidate-4",
        "What steps resolve an expired account reset link?",
        (
            "Issue a new reset email, tell the customer to use the newest link, "
            "and escalate if it fails."
        ),
    )
    second = first.model_copy(update={"id": "candidate-5", "generation_index": 1})

    reports = QualityPipeline().evaluate_many([first, second])

    assert reports[0].decision is CandidateDecision.accepted
    assert reports[1].decision is CandidateDecision.rejected
    assert "exact_duplicate" in reports[1].reason_codes


def test_evaluate_many_deduplicates_against_prior_batches() -> None:
    accepted = candidate(
        "prior-accepted",
        "How should support replace an expired account reset link?",
        (
            "Issue a new reset email, explain that only the newest link works, "
            "and document the result."
        ),
    )
    duplicate = accepted.model_copy(update={"id": "later-duplicate", "generation_index": 50})

    report = QualityPipeline().evaluate_many([duplicate], accepted=[accepted])[0]

    assert report.decision is CandidateDecision.rejected
    assert report.nearest_match_id == accepted.id
    assert "exact_duplicate" in report.reason_codes


def test_evaluate_many_embeds_each_seed_and_candidate_only_once() -> None:
    embedder = CountingEmbedder()
    seed = TrainingExample(
        id="seed-count",
        messages=[
            ChatMessage(role="user", content="Describe a baseline support request."),
            ChatMessage(role="assistant", content="Verify context and follow the documented path."),
        ],
    )
    generated = [
        candidate(
            f"count-{index}",
            f"Resolve distinct support scenario number {index} with appropriate safeguards.",
            f"For scenario {index}, verify the account context, explain the applicable policy, "
            "and provide a documented escalation path if the normal resolution fails.",
        )
        for index in range(12)
    ]

    QualityPipeline(embedder=embedder).evaluate_many(generated, seeds=[seed])

    assert embedder.embed_calls == len(generated) + 1


def test_quality_pipeline_accepts_an_injected_scorer() -> None:
    generated = candidate(
        "custom-score",
        "Which policy applies to a late refund request?",
        "Ask a manager because the applicable policy has not been identified.",
    )

    report = QualityPipeline(scorer=FixedScorer(), quality_threshold=0.7).evaluate(generated)

    assert report.decision is CandidateDecision.rejected
    assert "policy_not_grounded" in report.reason_codes
    assert report.components[0].name == "policy_grounding"
