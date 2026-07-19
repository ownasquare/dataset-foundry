import {
  Activity,
  CalendarClock,
  CheckCircle2,
  CircleStop,
  Filter,
  Gauge,
  Layers3,
  PlayCircle,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";

import { useCancelRun, useRuns } from "../api/queries";
import type { Run, RunStatus } from "../api/types";
import { Disclosure } from "../components/Disclosure";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { ProgressBar } from "../components/ProgressBar";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { formatCount, formatDate, formatPercent, formatQuality } from "../components/format";

type RunFilter = "all" | "active" | "completed" | "attention";

function matchesFilter(run: Run, filter: RunFilter): boolean {
  if (filter === "all") return true;
  if (filter === "active") return run.status === "running" || run.status === "queued";
  if (filter === "completed") return run.status.startsWith("completed");
  return run.status === "failed" || run.status === "completed_with_review";
}

export function RunsView({
  onGenerate,
  onReview,
}: {
  onGenerate: () => void;
  onReview: () => void;
}) {
  const runs = useRuns();
  const cancelRun = useCancelRun();
  const [filter, setFilter] = useState<RunFilter>("all");
  const [selectedId, setSelectedId] = useState("");
  const [confirmation, setConfirmation] = useState("");

  const filtered = useMemo(
    () => (runs.data ?? []).filter((run) => matchesFilter(run, filter)),
    [filter, runs.data],
  );
  const selected =
    filtered.find((run) => run.id === selectedId) ??
    runs.data?.find((run) => run.id === selectedId) ??
    filtered[0] ??
    null;

  if (runs.isPending) return <StatePanel kind="loading" />;
  if (runs.isError) {
    return <StatePanel kind="error" message={runs.error.message} onRetry={() => void runs.refetch()} />;
  }

  const activeCount = runs.data.filter(
    (run) => run.status === "running" || run.status === "queued",
  ).length;
  const reviewCount = runs.data.reduce((total, run) => total + run.reviewCount, 0);
  const completedCount = runs.data.filter((run) => run.status.startsWith("completed")).length;

  return (
    <div className="view-stack">
      <PageHeader
        eyebrow="Create"
        title="Generation runs"
        description="Follow progress, reconcile every candidate decision, and inspect the immutable recipe behind each run."
      />

      <section className="metric-grid metric-grid--three" aria-label="Run metrics">
        <MetricCard label="Active" value={formatCount(activeCount)} detail="Queued or generating" icon={Activity} />
        <MetricCard
          label="Completed"
          value={formatCount(completedCount)}
          detail="Finished generation runs"
          icon={CheckCircle2}
          tone="positive"
        />
        <MetricCard
          label="Review queue"
          value={formatCount(reviewCount)}
          detail="Candidates awaiting a decision"
          icon={Gauge}
          tone={reviewCount ? "attention" : "default"}
        />
      </section>

      <div className="toolbar" aria-label="Run filters">
        <span className="toolbar__label"><Filter size={15} aria-hidden="true" /> Show</span>
        {(["all", "active", "completed", "attention"] as const).map((item) => (
          <button
            className={filter === item ? "chip is-selected" : "chip"}
            key={item}
            type="button"
            aria-pressed={filter === item}
            onClick={() => { setFilter(item); setSelectedId(""); setConfirmation(""); }}
          >
            {item === "all" ? "All runs" : item === "attention" ? "Needs attention" : item[0]?.toUpperCase() + item.slice(1)}
          </button>
        ))}
      </div>

      {runs.data.length === 0 ? (
        <StatePanel
          kind="empty"
          title="No generation runs"
          message="Configure a bounded recipe to create the first run."
          actionLabel="Start generating"
          onAction={onGenerate}
        />
      ) : null}

      {runs.data.length ? (
        <div className="master-detail">
          <section className="panel master-list" aria-labelledby="run-list-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Run history</p>
                <h2 id="run-list-title">
                  {filtered.length} matching {filtered.length === 1 ? "run" : "runs"}
                </h2>
              </div>
            </div>
            {filtered.length ? (
              <div className="run-list">
                {filtered.map((run) => {
                  const progress = run.targetCount ? run.acceptedCount / run.targetCount : 0;
                  return (
                    <button
                      className={`run-row${selected?.id === run.id ? " is-selected" : ""}`}
                      type="button"
                      key={run.id}
                      aria-pressed={selected?.id === run.id}
                      onClick={() => { setSelectedId(run.id); setConfirmation(""); }}
                    >
                      <span className="run-row__main">
                        <strong>{run.name}</strong>
                        <small>{run.projectName} · {formatDate(run.startedAt)}</small>
                      </span>
                      <span className="run-row__progress">
                        <span>{formatCount(run.acceptedCount)} accepted</span>
                        <span>{formatPercent(progress, 0)}</span>
                      </span>
                      <StatusBadge status={run.status} />
                    </button>
                  );
                })}
              </div>
            ) : (
              <StatePanel kind="empty" title="No runs match this filter" message="Choose another filter to see the full run history." />
            )}
          </section>

          {selected ? (
            <aside className="panel detail-panel" aria-labelledby="selected-run-title">
              <div className="detail-panel__topline">
                <span className="detail-panel__icon" aria-hidden="true"><PlayCircle size={20} /></span>
                <StatusBadge status={selected.status} />
              </div>
              <h2 id="selected-run-title">{selected.name}</h2>
              <p>{selected.projectName}</p>
              <ProgressBar
                value={selected.acceptedCount}
                max={selected.targetCount}
                label={`${formatCount(selected.acceptedCount)} of ${formatCount(selected.targetCount)} accepted · ${formatCount(selected.generatedCount)} evaluated`}
              />
              <dl className="definition-grid">
                <div><dt>Accepted</dt><dd>{formatCount(selected.acceptedCount)}</dd></div>
                <div><dt>Needs review</dt><dd>{formatCount(selected.reviewCount)}</dd></div>
                <div><dt>Rejected</dt><dd>{formatCount(selected.rejectedCount)}</dd></div>
                <div><dt>Avg. quality</dt><dd>{formatQuality(selected.averageQuality)}</dd></div>
              </dl>
              {selected.status === "completed_with_review" && selected.reviewCount > 0 ? (
                <button className="button button--primary button--full" type="button" onClick={onReview}>
                  Review {formatCount(selected.reviewCount)} candidates
                </button>
              ) : null}
              {selected.status === "running" || selected.status === "queued" ? (
                <button
                  className="button button--secondary button--danger button--full"
                  type="button"
                  disabled={cancelRun.isPending}
                  onClick={() => {
                    if (!window.confirm("Cancel this generation run? Accepted work is preserved.")) return;
                    cancelRun.mutate(selected.id, {
                      onSuccess: () => setConfirmation("Run cancelled"),
                    });
                  }}
                >
                  <CircleStop size={16} /> {cancelRun.isPending ? "Cancelling…" : "Cancel run"}
                </button>
              ) : null}
              {confirmation ? (
                <p className="inline-success" role="status"><CheckCircle2 size={16} /> {confirmation}</p>
              ) : null}
              {cancelRun.isError ? (
                <p className="form-error" role="alert">{cancelRun.error.message}</p>
              ) : null}
              <Disclosure summary="Recipe and provenance">
                <dl className="detail-list">
                  <div><dt>Provider</dt><dd>{selected.provider}</dd></div>
                  <div><dt>Model</dt><dd>{selected.model}</dd></div>
                  <div><dt>Started</dt><dd>{formatDate(selected.startedAt)}</dd></div>
                  <div><dt>Completed</dt><dd>{formatDate(selected.completedAt)}</dd></div>
                  <div><dt>Near duplicates</dt><dd>{formatPercent(selected.duplicateRate)}</dd></div>
                  <div><dt>Run reference</dt><dd><code>{selected.id}</code></dd></div>
                </dl>
              </Disclosure>
              <div className="detail-footnote">
                <CalendarClock size={15} aria-hidden="true" /> Run counts are read from persisted candidate decisions.
              </div>
            </aside>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
