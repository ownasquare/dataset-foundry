import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  FileSearch,
  Gauge,
  MessageSquareText,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useCandidates, useReviewCandidate, useRuns } from "../api/queries";
import type { Candidate, CandidateDecision, ReviewDecision } from "../api/types";
import { Disclosure } from "../components/Disclosure";
import { PageHeader } from "../components/PageHeader";
import { ProgressBar } from "../components/ProgressBar";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { formatPercent, formatQuality } from "../components/format";

type ReviewFilter = CandidateDecision | "all";

function CandidatePreview({ candidate }: { candidate: Candidate }) {
  return (
    <>
      <strong>{candidate.generatedPrompt}</strong>
      <span>{candidate.generatedResponse}</span>
      <small>Quality {formatQuality(candidate.qualityScore)} · similarity {formatPercent(candidate.nearestSimilarity)}</small>
    </>
  );
}

export function ReviewView({ onGenerate }: { onGenerate: () => void }) {
  const runs = useRuns();
  const reviewableRuns = useMemo(
    () => (runs.data ?? []).filter((run) => run.status.startsWith("completed")),
    [runs.data],
  );
  const [runId, setRunId] = useState("");
  const resolvedRunId = runId || reviewableRuns.find((run) => run.reviewCount > 0)?.id || reviewableRuns[0]?.id || "";
  const [filter, setFilter] = useState<ReviewFilter>("needs_review");
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<Array<string | null>>([]);
  const candidates = useCandidates(resolvedRunId, filter, cursor);
  const review = useReviewCandidate(resolvedRunId);
  const [selectedId, setSelectedId] = useState("");
  const [note, setNote] = useState("");
  const [confirmation, setConfirmation] = useState("");

  const filtered = candidates.data?.items ?? [];
  const selected =
    filtered.find((candidate) => candidate.id === selectedId) ??
    filtered[0] ??
    null;

  useEffect(() => {
    setNote(selected?.reviewerNote ?? "");
  }, [selected?.id, selected?.reviewerNote]);

  const selectCandidate = (candidate: Candidate) => {
    setSelectedId(candidate.id);
    setNote(candidate.reviewerNote ?? "");
    setConfirmation("");
  };

  const decide = (decision: ReviewDecision) => {
    if (!selected) return;
    setSelectedId(selected.id);
    review.mutate(
      { candidateId: selected.id, decision, note: note.trim() },
      {
        onSuccess: () => {
          setSelectedId("");
          setNote("");
          setConfirmation(
            decision === "accepted"
              ? "Candidate accepted"
              : decision === "rejected"
                ? "Candidate rejected"
                : "Candidate kept in review",
          );
        },
      },
    );
  };

  if (runs.isPending) return <StatePanel kind="loading" />;
  if (runs.isError) {
    return <StatePanel kind="error" message={runs.error.message} onRetry={() => void runs.refetch()} />;
  }

  return (
    <div className="view-stack">
      <PageHeader
        eyebrow="Prepare"
        title="Review candidates"
        description="Inspect the generated example, source lineage, quality evidence, and similarity signal before overriding an automated decision."
      />

      {reviewableRuns.length === 0 ? (
        <StatePanel
          kind="empty"
          title="No completed runs to review"
          message="Complete a generation run before reviewing candidate evidence."
          actionLabel="Start generating"
          onAction={onGenerate}
        />
      ) : (
        <>
          <div className="review-toolbar">
            <label className="field field--compact">
              <span>Run</span>
              <select
                value={resolvedRunId}
                onChange={(event) => {
                  setRunId(event.target.value);
                  setCursor(null);
                  setCursorHistory([]);
                  setSelectedId("");
                  setConfirmation("");
                }}
              >
                {reviewableRuns.map((run) => (
                  <option key={run.id} value={run.id}>{run.name} · {run.projectName}</option>
                ))}
              </select>
            </label>
            <div className="segmented-control" aria-label="Candidate decision filter">
              {(["needs_review", "accepted", "rejected", "all"] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  className={filter === item ? "is-selected" : undefined}
                  aria-pressed={filter === item}
                  onClick={() => {
                    setFilter(item);
                    setCursor(null);
                    setCursorHistory([]);
                    setSelectedId("");
                    setConfirmation("");
                  }}
                >
                  {item === "needs_review" ? "Needs review" : item[0]?.toUpperCase() + item.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {confirmation ? <p className="inline-success" role="status"><Check size={16} /> {confirmation}</p> : null}
          {candidates.isPending ? <StatePanel kind="loading" /> : null}
          {candidates.isError ? (
            <StatePanel kind="error" message={candidates.error.message} onRetry={() => void candidates.refetch()} />
          ) : null}
          {candidates.data && filtered.length === 0 ? (
            <StatePanel kind="empty" title="No candidates in this view" message="Choose another decision filter or select a different completed run." />
          ) : null}

          {selected ? (
            <div className="review-layout">
              <aside className="panel candidate-queue" aria-labelledby="candidate-queue-title">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">Review queue</p>
                    <h2 id="candidate-queue-title">{filtered.length} candidates on this page</h2>
                  </div>
                </div>
                <div className="candidate-list">
                  {filtered.map((candidate) => (
                    <button
                      key={candidate.id}
                      type="button"
                      className={selected.id === candidate.id ? "candidate-list__item is-selected" : "candidate-list__item"}
                      aria-pressed={selected.id === candidate.id}
                      onClick={() => selectCandidate(candidate)}
                    >
                      <CandidatePreview candidate={candidate} />
                      <ChevronRight size={17} aria-hidden="true" />
                    </button>
                  ))}
                </div>
              </aside>

              <article className="candidate-review" aria-labelledby="candidate-title">
                <section className="panel candidate-review__header">
                  <div className="candidate-review__topline">
                    <StatusBadge status={selected.decision} />
                    <span>Automated decision: {selected.automatedDecision.replaceAll("_", " ")}</span>
                  </div>
                  <h2 id="candidate-title">{selected.generatedPrompt}</h2>
                  <p className="candidate-answer">{selected.generatedResponse}</p>
                  {selected.reasonCodes.length ? (
                    <div className="reason-codes" aria-label="Quality reason codes">
                      {selected.reasonCodes.map((code) => <code key={code}>{code}</code>)}
                    </div>
                  ) : (
                    <div className="inline-success"><ShieldCheck size={16} /> Automated gates found no blocking issue.</div>
                  )}
                </section>

                <div className="evidence-grid">
                  <section className="panel" aria-labelledby="source-evidence-title">
                    <div className="evidence-heading">
                      <span aria-hidden="true"><MessageSquareText size={17} /></span>
                      <h3 id="source-evidence-title">Source seed</h3>
                    </div>
                    {selected.sourcePrompt || selected.sourceResponse ? (
                      <dl className="conversation-pair">
                        <div><dt>User</dt><dd>{selected.sourcePrompt || "Not included"}</dd></div>
                        <div><dt>Assistant</dt><dd>{selected.sourceResponse || "Not included"}</dd></div>
                      </dl>
                    ) : (
                      <p className="detail-note">Source seed content is not included in this API response. Lineage remains available by ID.</p>
                    )}
                  </section>
                  <section className="panel" aria-labelledby="score-evidence-title">
                    <div className="evidence-heading">
                      <span aria-hidden="true"><Gauge size={17} /></span>
                      <h3 id="score-evidence-title">Quality evidence</h3>
                    </div>
                    <div className="score-list">
                      {selected.scores.map((score) => (
                        <div key={score.label}>
                          <ProgressBar value={score.value} max={1} label={score.label} />
                          <p>{score.explanation}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>

                <Disclosure summary="Similarity, lineage, and provider trace">
                  <dl className="detail-list detail-list--columns">
                    <div><dt>Source seed</dt><dd><code>{selected.sourceSeedId}</code></dd></div>
                    <div><dt>Nearest similarity</dt><dd>{formatPercent(selected.nearestSimilarity)}</dd></div>
                    <div><dt>Nearest candidate</dt><dd><code>{selected.nearestCandidateId ?? "None"}</code></dd></div>
                    <div><dt>Provider trace</dt><dd>{selected.providerTrace}</dd></div>
                  </dl>
                </Disclosure>

                <section className="panel review-decision" aria-labelledby="decision-title">
                  <div className="evidence-heading">
                    <span aria-hidden="true"><FileSearch size={17} /></span>
                    <h3 id="decision-title">Human review decision</h3>
                  </div>
                  <label className="field">
                    <span>Review note <small>optional</small></span>
                    <textarea
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      rows={3}
                      maxLength={500}
                      placeholder="Explain the decision for future reviewers"
                    />
                  </label>
                  <div className="decision-actions">
                    <button className="button button--secondary button--danger" type="button" disabled={review.isPending} onClick={() => decide("rejected")}>
                      <X size={16} /> Reject
                    </button>
                    <button className="button button--secondary" type="button" disabled={review.isPending} onClick={() => decide("needs_review")}>
                      <AlertTriangle size={16} /> Keep in review
                    </button>
                    <button className="button button--primary" type="button" disabled={review.isPending} onClick={() => decide("accepted")}>
                      <Check size={16} /> Accept
                    </button>
                  </div>
                  {review.isError ? <p className="form-error" role="alert">{review.error.message}</p> : null}
                </section>

                <div className="review-pager">
                  <button
                    className="button button--secondary"
                    type="button"
                    disabled={cursorHistory.length === 0}
                    onClick={() => {
                      const previous = cursorHistory[cursorHistory.length - 1] ?? null;
                      setCursor(previous);
                      setCursorHistory((history) => history.slice(0, -1));
                      setSelectedId("");
                    }}
                  >
                    <ArrowLeft size={16} /> Previous page
                  </button>
                  <span>Page {cursorHistory.length + 1} · item {filtered.findIndex((candidate) => candidate.id === selected.id) + 1} of {filtered.length}</span>
                  <button
                    className="button button--secondary"
                    type="button"
                    disabled={!candidates.data?.nextCursor}
                    onClick={() => {
                      const next = candidates.data?.nextCursor;
                      if (!next) return;
                      setCursorHistory((history) => [...history, cursor]);
                      setCursor(next);
                      setSelectedId("");
                    }}
                  >
                    Next page <ArrowRight size={16} />
                  </button>
                </div>
              </article>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
