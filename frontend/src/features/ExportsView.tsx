import {
  Archive,
  CheckCircle2,
  Download,
  FileArchive,
  FileJson2,
  Fingerprint,
  LoaderCircle,
  PackageCheck,
} from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { useCreateExport, useExports, useProjects, useRuns } from "../api/queries";
import type { ExportFormat } from "../api/types";
import { Disclosure } from "../components/Disclosure";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import {
  formatBytes,
  formatCount,
  formatDate,
  formatExportFormat,
} from "../components/format";

export function ExportsView() {
  const exportsQuery = useExports();
  const projects = useProjects();
  const runs = useRuns();
  const createExport = useCreateExport();
  const [showBuilder, setShowBuilder] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [runId, setRunId] = useState("");
  const [name, setName] = useState("Fine-tuning dataset · v1");
  const [format, setFormat] = useState<ExportFormat>("parquet");
  const [train, setTrain] = useState(90);
  const [validation, setValidation] = useState(5);
  const [test, setTest] = useState(5);

  const resolvedProjectId = projectId || projects.data?.[0]?.id || "";
  const eligibleRuns = useMemo(
    () =>
      (runs.data ?? []).filter(
        (run) => run.projectId === resolvedProjectId && run.status.startsWith("completed"),
      ),
    [resolvedProjectId, runs.data],
  );
  const resolvedRunId =
    runId && eligibleRuns.some((run) => run.id === runId) ? runId : eligibleRuns[0]?.id ?? "";
  const splitTotal = train + validation + test;

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!resolvedProjectId || !resolvedRunId || splitTotal !== 100) return;
    createExport.mutate(
      {
        projectId: resolvedProjectId,
        runId: resolvedRunId,
        name: name.trim(),
        format,
        trainPercent: train,
        validationPercent: validation,
        testPercent: test,
      },
      { onSuccess: () => setShowBuilder(false) },
    );
  };

  const ready = exportsQuery.data?.filter((item) => item.status === "ready") ?? [];
  const readyPackages = Array.from(
    new Map(ready.map((item) => [item.exportId, item])).values(),
  );
  const totalExamples = readyPackages.reduce((sum, item) => sum + item.exampleCount, 0);
  const totalBytes = ready.reduce((sum, item) => sum + (item.sizeBytes ?? 0), 0);

  return (
    <div className="view-stack">
      <PageHeader
        eyebrow="Prepare"
        title="Exports"
        description="Package accepted examples into immutable, fine-tuning-ready files with grouped splits and a verifiable manifest."
        actions={
          <button className="button button--primary" type="button" onClick={() => setShowBuilder(true)}>
            <Archive size={17} /> New export
          </button>
        }
      />

      <section className="metric-grid metric-grid--three" aria-label="Export metrics">
        <MetricCard label="Ready exports" value={formatCount(readyPackages.length)} detail="Immutable artifact packages" icon={PackageCheck} tone="positive" />
        <MetricCard label="Examples packaged" value={formatCount(totalExamples)} detail="Accepted examples only" icon={FileJson2} />
        <MetricCard label="Artifact size" value={formatBytes(totalBytes)} detail="Across ready exports" icon={FileArchive} />
      </section>

      {showBuilder ? (
        <section className="panel export-builder" aria-labelledby="export-builder-title">
          <div className="panel-heading">
            <div><p className="eyebrow">Immutable package</p><h2 id="export-builder-title">Create export</h2></div>
          </div>
          <form onSubmit={submit}>
            <div className="form-grid form-grid--two">
              <label className="field">
                <span>Project</span>
                <select value={resolvedProjectId} onChange={(event) => { setProjectId(event.target.value); setRunId(""); }}>
                  {(projects.data ?? []).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                </select>
              </label>
              <label className="field">
                <span>Completed run</span>
                <select value={resolvedRunId} onChange={(event) => setRunId(event.target.value)}>
                  {eligibleRuns.map((run) => <option key={run.id} value={run.id}>{run.name} · {formatCount(run.acceptedCount)} accepted</option>)}
                </select>
                {!eligibleRuns.length ? <small>No completed run is available for this project.</small> : null}
              </label>
              <label className="field">
                <span>Export name</span>
                <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} required />
              </label>
              <label className="field">
                <span>Format</span>
                <select value={format} onChange={(event) => setFormat(event.target.value as ExportFormat)}>
                  <option value="parquet">Parquet splits</option>
                  <option value="canonical_jsonl">Canonical JSONL</option>
                  <option value="openai_chat_jsonl">OpenAI chat JSONL</option>
                  <option value="alpaca_jsonl">Alpaca JSONL</option>
                </select>
              </label>
            </div>
            <fieldset className="split-fields">
              <legend>Grouped data splits</legend>
              <div className="form-grid form-grid--three">
                <label className="field"><span>Train %</span><input type="number" min={0} max={100} value={train} onChange={(event) => setTrain(Number(event.target.value))} /></label>
                <label className="field"><span>Validation %</span><input type="number" min={0} max={100} value={validation} onChange={(event) => setValidation(Number(event.target.value))} /></label>
                <label className="field"><span>Test %</span><input type="number" min={0} max={100} value={test} onChange={(event) => setTest(Number(event.target.value))} /></label>
              </div>
              <p className={splitTotal === 100 ? "split-total is-valid" : "split-total is-invalid"}>
                {splitTotal === 100 ? <CheckCircle2 size={15} /> : null} Split total: {splitTotal}%
              </p>
            </fieldset>
            <Disclosure summary="What the package contains">
              <ul className="plain-list">
                <li>Fine-tuning files in the selected format</li>
                <li>Lineage-grouped train, validation, and test splits</li>
                <li>Dataset card with quality and provider boundaries</li>
                <li>Manifest with SHA-256 for every file</li>
              </ul>
            </Disclosure>
            <div className="form-actions">
              <button className="button button--secondary" type="button" onClick={() => setShowBuilder(false)}>Cancel</button>
              <button className="button button--primary" type="submit" disabled={!resolvedRunId || !name.trim() || splitTotal !== 100 || createExport.isPending}>
                {createExport.isPending ? <LoaderCircle className="spin" size={16} /> : <PackageCheck size={16} />}
                {createExport.isPending ? "Building…" : "Create immutable export"}
              </button>
            </div>
            {createExport.isError ? <p className="form-error" role="alert">{createExport.error.message}</p> : null}
          </form>
        </section>
      ) : null}

      {exportsQuery.isPending ? <StatePanel kind="loading" /> : null}
      {exportsQuery.isError ? <StatePanel kind="error" message={exportsQuery.error.message} onRetry={() => void exportsQuery.refetch()} /> : null}
      {exportsQuery.data?.length === 0 ? <StatePanel kind="empty" title="No exports yet" message="Complete review, then package accepted examples for fine-tuning." /> : null}
      {exportsQuery.data?.length ? (
        <section className="panel" aria-labelledby="export-history-title">
          <div className="panel-heading"><div><p className="eyebrow">Artifact history</p><h2 id="export-history-title">Dataset packages</h2></div></div>
          <div className="export-list">
            {exportsQuery.data.map((artifact) => (
              <article className="export-row" key={artifact.id}>
                <span className="export-row__icon" aria-hidden="true"><FileArchive size={20} /></span>
                <div className="export-row__main">
                  <strong>{artifact.name}</strong>
                  <span>{artifact.projectName} · {formatExportFormat(artifact.format)}</span>
                  <small>{formatCount(artifact.exampleCount)} examples · {formatBytes(artifact.sizeBytes)} · {formatDate(artifact.createdAt)}</small>
                </div>
                <StatusBadge status={artifact.status} />
                <div className="export-row__actions">
                  {artifact.sha256 ? <span className="hash-label" title={artifact.sha256}><Fingerprint size={14} /> {artifact.sha256.slice(0, 10)}…</span> : null}
                  {artifact.downloadUrl ? (
                    <a className="button button--secondary button--compact" href={artifact.downloadUrl} download>
                      <Download size={15} /> Download
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
