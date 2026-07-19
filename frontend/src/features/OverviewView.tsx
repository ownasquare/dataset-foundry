import {
  ArrowRight,
  CheckCircle2,
  Database,
  FileArchive,
  Gauge,
  Layers3,
  Sparkles,
} from "lucide-react";

import type { ViewKey } from "../api/types";
import { useOverview } from "../api/queries";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { ProgressBar } from "../components/ProgressBar";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { formatCount, formatDate, formatPercent, formatQuality } from "../components/format";

export function OverviewView({ onNavigate }: { onNavigate: (view: ViewKey) => void }) {
  const overview = useOverview();

  if (overview.isPending) return <StatePanel kind="loading" />;
  if (overview.isError) {
    return (
      <StatePanel
        kind="error"
        message={overview.error.message}
        onRetry={() => void overview.refetch()}
      />
    );
  }

  const data = overview.data;
  const qualityTotal = data.qualitySegments.reduce((sum, segment) => sum + segment.count, 0);

  return (
    <div className="view-stack">
      <PageHeader
        eyebrow="Workspace overview"
        title="Turn seed examples into training-ready data"
        description="Generate structured examples, understand every quality decision, and export a dataset you can defend."
        actions={
          <button className="button button--primary" type="button" onClick={() => onNavigate("generate")}>
            <Sparkles size={17} aria-hidden="true" /> Start generating
          </button>
        }
      />

      <ol className="workflow-strip" aria-label="Dataset preparation workflow">
        {[
          ["1", "Import seeds", "Bring a small, representative set"],
          ["2", "Generate", "Expand with a bounded recipe"],
          ["3", "Review", "Resolve quality and similarity flags"],
          ["4", "Export", "Create immutable fine-tuning files"],
        ].map(([step, label, detail], index) => (
          <li key={step}>
            <span>{step}</span>
            <div>
              <strong>{label}</strong>
              <small>{detail}</small>
            </div>
            {index < 3 ? <ArrowRight size={16} aria-hidden="true" /> : null}
          </li>
        ))}
      </ol>

      <section className="metric-grid" aria-label="Workspace metrics">
        <MetricCard
          label="Projects"
          value={formatCount(data.projectCount)}
          detail={`${formatCount(data.datasetCount)} seed datasets`}
          icon={Layers3}
        />
        <MetricCard
          label="Generated"
          value={formatCount(data.generatedExamples)}
          detail={`${formatCount(data.acceptedExamples)} accepted`}
          icon={Database}
        />
        <MetricCard
          label="Acceptance rate"
          value={formatPercent(data.acceptanceRate)}
          detail="After automated quality gates"
          icon={CheckCircle2}
          tone="positive"
        />
        <MetricCard
          label="Average quality"
          value={formatQuality(data.averageQuality)}
          detail={
            data.duplicateRate === null
              ? "Available after scored runs"
              : `${formatPercent(data.duplicateRate)} near-duplicate rate`
          }
          icon={Gauge}
        />
      </section>

      <div className="overview-grid">
        <section className="panel panel--featured" aria-labelledby="active-run-title">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">In progress</p>
              <h2 id="active-run-title">Active generation</h2>
            </div>
            {data.activeRun ? <StatusBadge status={data.activeRun.status} /> : null}
          </div>
          {data.activeRun ? (
            <>
              <div className="active-run__title">
                <div>
                  <strong>{data.activeRun.name}</strong>
                  <span>{data.activeRun.projectName}</span>
                </div>
                <span>
                  {formatCount(data.activeRun.generatedCount)} / {formatCount(data.activeRun.targetCount)}
                </span>
              </div>
              <ProgressBar
                value={data.activeRun.generatedCount}
                max={data.activeRun.targetCount}
                label="Generation progress"
              />
              <div className="three-stat-row">
                <div>
                  <strong>{formatCount(data.activeRun.acceptedCount)}</strong>
                  <span>Accepted</span>
                </div>
                <div>
                  <strong>{formatCount(data.activeRun.reviewCount)}</strong>
                  <span>Needs review</span>
                </div>
                <div>
                  <strong>{formatCount(data.activeRun.rejectedCount)}</strong>
                  <span>Rejected</span>
                </div>
              </div>
              <button className="text-action" type="button" onClick={() => onNavigate("runs")}>
                Open run details <ArrowRight size={15} aria-hidden="true" />
              </button>
            </>
          ) : (
            <div className="compact-empty">
              <Sparkles size={22} aria-hidden="true" />
              <div>
                <strong>No active generation</strong>
                <p>Start a bounded run when you are ready to expand a dataset.</p>
              </div>
            </div>
          )}
        </section>

        <section className="panel" aria-labelledby="quality-mix-title">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Quality decisions</p>
              <h2 id="quality-mix-title">Candidate mix</h2>
            </div>
            <button className="text-action" type="button" onClick={() => onNavigate("review")}>
              Review queue <ArrowRight size={15} />
            </button>
          </div>
          <div className="quality-bar" aria-label="Candidate decision distribution">
            {data.qualitySegments.map((segment) => (
              <span
                key={segment.label}
                className={`quality-bar__segment quality-bar__segment--${segment.tone}`}
                style={{ width: `${qualityTotal ? (segment.count / qualityTotal) * 100 : 0}%` }}
                title={`${segment.label}: ${formatCount(segment.count)}`}
              />
            ))}
          </div>
          <ul className="quality-legend">
            {data.qualitySegments.map((segment) => (
              <li key={segment.label}>
                <span className={`legend-dot legend-dot--${segment.tone}`} aria-hidden="true" />
                <span>{segment.label}</span>
                <strong>{formatCount(segment.count)}</strong>
              </li>
            ))}
          </ul>
          <div className="export-ready-note">
            <FileArchive size={18} aria-hidden="true" />
            <div>
              <strong>{formatCount(data.readyExports)} exports ready</strong>
              <span>Immutable artifacts with manifests and hashes</span>
            </div>
          </div>
        </section>
      </div>

      <section className="panel" aria-labelledby="recent-runs-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Recent activity</p>
            <h2 id="recent-runs-title">Latest runs</h2>
          </div>
          <button className="text-action" type="button" onClick={() => onNavigate("runs")}>
            View all runs <ArrowRight size={15} />
          </button>
        </div>
        {data.recentRuns.length ? (
          <div className="data-list" role="list">
            {data.recentRuns.map((run) => (
              <article className="data-list__row" key={run.id} role="listitem">
                <div className="data-list__primary">
                  <strong>{run.name}</strong>
                  <span>
                    {run.projectName} · {formatDate(run.startedAt)}
                  </span>
                </div>
                <div className="data-list__metric">
                  <strong>{formatCount(run.acceptedCount)}</strong>
                  <span>accepted</span>
                </div>
                <div className="data-list__metric">
                  <strong>{formatQuality(run.averageQuality)}</strong>
                  <span>quality</span>
                </div>
                <StatusBadge status={run.status} />
              </article>
            ))}
          </div>
        ) : (
          <StatePanel kind="empty" title="No runs yet" message="Create a recipe and start your first generation." />
        )}
      </section>
    </div>
  );
}
