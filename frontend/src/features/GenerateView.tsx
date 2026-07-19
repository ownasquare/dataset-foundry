import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  Cloud,
  Database,
  FileCheck2,
  Gauge,
  LoaderCircle,
  LockKeyhole,
  Play,
  ShieldCheck,
  Sparkles,
  Upload,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  useCreateRun,
  usePreflight,
  useProjects,
  useProviders,
  useUploadSeeds,
} from "../api/queries";
import type { PreflightRequest, ProviderKind, Run, SeedUploadResult } from "../api/types";
import { Disclosure } from "../components/Disclosure";
import { Dropzone } from "../components/Dropzone";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { formatCount, formatMoney } from "../components/format";

const MODEL_BY_PROVIDER: Record<ProviderKind, string> = {
  offline: "offline-deterministic-v1",
  openai: "gpt-5.6-luna",
  anthropic: "claude-sonnet-5",
};

export function GenerateView({
  initialProjectId,
  onOpenRuns,
}: {
  initialProjectId: string | null;
  onOpenRuns: () => void;
}) {
  const projects = useProjects();
  const providers = useProviders();
  const uploadSeeds = useUploadSeeds();
  const preflight = usePreflight();
  const createRun = useCreateRun();
  const [projectId, setProjectId] = useState(initialProjectId ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<SeedUploadResult | null>(null);
  const [runName, setRunName] = useState("Policy coverage expansion");
  const [targetCount, setTargetCount] = useState(1_000);
  const [provider, setProvider] = useState<ProviderKind>("offline");
  const [model, setModel] = useState(MODEL_BY_PROVIDER.offline);
  const [qualityThreshold, setQualityThreshold] = useState(0.78);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.92);
  const [candidateMultiplier, setCandidateMultiplier] = useState(2);
  const [allowExternalDataTransfer, setAllowExternalDataTransfer] = useState(false);
  const [preflightKey, setPreflightKey] = useState("");
  const [queuedRun, setQueuedRun] = useState<Run | null>(null);

  const resolvedProjectId = useMemo(() => {
    if (projectId && projects.data?.some((project) => project.id === projectId)) return projectId;
    if (initialProjectId && projects.data?.some((project) => project.id === initialProjectId)) {
      return initialProjectId;
    }
    return projects.data?.[0]?.id ?? "";
  }, [initialProjectId, projectId, projects.data]);

  const selectedProject = projects.data?.find((project) => project.id === resolvedProjectId);
  const input: PreflightRequest = useMemo(
    () => ({
      projectId: resolvedProjectId,
      runName: runName.trim(),
      targetCount,
      provider,
      model: model.trim(),
      qualityThreshold,
      similarityThreshold,
      candidateMultiplier,
      allowExternalDataTransfer,
    }),
    [
      allowExternalDataTransfer,
      candidateMultiplier,
      model,
      provider,
      qualityThreshold,
      resolvedProjectId,
      runName,
      similarityThreshold,
      targetCount,
    ],
  );
  const currentKey = JSON.stringify(input);
  const preflightIsFresh = preflight.isSuccess && preflightKey === currentKey;
  const canCheck = Boolean(
    resolvedProjectId &&
      runName.trim() &&
      model.trim() &&
      targetCount >= 1 &&
      targetCount <= 10_000,
  );

  const chooseProvider = (next: ProviderKind, providerModel: string) => {
    setProvider(next);
    setModel(providerModel || MODEL_BY_PROVIDER[next]);
    setAllowExternalDataTransfer(false);
    setQueuedRun(null);
  };

  const importFile = () => {
    if (!file || !resolvedProjectId) return;
    uploadSeeds.mutate(
      { projectId: resolvedProjectId, file },
      { onSuccess: (result) => setUploadResult(result) },
    );
  };

  const checkSetup = () => {
    if (!canCheck) return;
    setPreflightKey(currentKey);
    setQueuedRun(null);
    preflight.mutate(input);
  };

  const startRun = () => {
    if (!preflightIsFresh || !preflight.data.ready) return;
    createRun.mutate(
      { ...input, recipeId: preflight.data.recipeId },
      { onSuccess: (run) => setQueuedRun(run) },
    );
  };

  if (projects.isPending) return <StatePanel kind="loading" />;
  if (projects.isError) {
    return <StatePanel kind="error" message={projects.error.message} onRetry={() => void projects.refetch()} />;
  }
  if (!projects.data.length) {
    return (
      <StatePanel
        kind="empty"
        title="Create a project before generating"
        message="Projects keep seed data, recipes, quality decisions, and exports together."
      />
    );
  }

  return (
    <div className="view-stack">
      <PageHeader
        eyebrow="Create"
        title="Generate a dataset"
        description="Import representative seeds, define a bounded recipe, and review exactly what will happen before work starts."
      />

      <ol className="stepper" aria-label="Generation setup steps">
        <li className="is-current"><span>1</span><div><strong>Seeds</strong><small>Choose the source</small></div></li>
        <li><span>2</span><div><strong>Recipe</strong><small>Set quality bounds</small></div></li>
        <li><span>3</span><div><strong>Preflight</strong><small>Review cost and privacy</small></div></li>
      </ol>

      <div className="generation-layout">
        <div className="generation-layout__main">
          <section className="panel form-section" aria-labelledby="seeds-title">
            <div className="section-title-row">
              <span className="step-icon" aria-hidden="true"><Database size={18} /></span>
              <div>
                <p className="eyebrow">Step 1</p>
                <h2 id="seeds-title">Project and seed dataset</h2>
                <p>Use a small set that represents the behavior, edge cases, and language you need.</p>
              </div>
            </div>
            <label className="field">
              <span>Project</span>
              <select
                value={resolvedProjectId}
                onChange={(event) => {
                  setProjectId(event.target.value);
                  setUploadResult(null);
                  setQueuedRun(null);
                }}
              >
                {projects.data.map((project) => (
                  <option key={project.id} value={project.id}>{project.name}</option>
                ))}
              </select>
              <small>
                {selectedProject
                  ? `${formatCount(selectedProject.seedCount)} seeds currently available`
                  : "Choose a project"}
              </small>
            </label>
            <Dropzone file={file} onFile={(next) => { setFile(next); setUploadResult(null); }} />
            <div className="upload-action-row">
              <span>Uploading a new file adds a versioned seed dataset; it does not replace earlier data.</span>
              <button
                className="button button--secondary"
                type="button"
                disabled={!file || uploadSeeds.isPending}
                onClick={importFile}
              >
                {uploadSeeds.isPending ? <LoaderCircle className="spin" size={16} /> : <Upload size={16} />}
                {uploadSeeds.isPending ? "Importing…" : "Import seeds"}
              </button>
            </div>
            {uploadResult ? (
              <div className="inline-success" role="status">
                <CheckCircle2 size={17} aria-hidden="true" />
                <div>
                  <strong>{formatCount(uploadResult.importedCount)} seeds imported</strong>
                  <span>
                    {uploadResult.filename} · {uploadResult.duplicateCount} duplicates · fingerprint {uploadResult.fingerprint.slice(0, 10)}…
                  </span>
                </div>
              </div>
            ) : null}
            {uploadSeeds.isError ? <p className="form-error" role="alert">{uploadSeeds.error.message}</p> : null}
          </section>

          <section className="panel form-section" aria-labelledby="recipe-title">
            <div className="section-title-row">
              <span className="step-icon" aria-hidden="true"><Sparkles size={18} /></span>
              <div>
                <p className="eyebrow">Step 2</p>
                <h2 id="recipe-title">Generation recipe</h2>
                <p>Name the run, choose a provider, and bound the amount of work.</p>
              </div>
            </div>
            <div className="form-grid form-grid--two">
              <label className="field">
                <span>Run name</span>
                <input value={runName} onChange={(event) => setRunName(event.target.value)} maxLength={100} />
              </label>
              <label className="field">
                <span>Accepted examples target</span>
                <input
                  type="number"
                  min={1}
                  max={10_000}
                  step={50}
                  value={targetCount}
                  onChange={(event) => setTargetCount(Number(event.target.value))}
                />
                <small>Maximum 10,000 per run</small>
              </label>
            </div>

            <fieldset className="provider-fieldset">
              <legend>Generation provider</legend>
              {providers.isError ? (
                <div className="inline-warning" role="alert">
                  <AlertTriangle size={17} /> Provider readiness could not be loaded. Retry before starting.
                </div>
              ) : null}
              <div className="provider-options">
                {(providers.data ?? []).map((item) => (
                  <label className={`provider-option${provider === item.provider ? " is-selected" : ""}`} key={item.provider}>
                    <input
                      type="radio"
                      name="provider"
                      value={item.provider}
                      checked={provider === item.provider}
                      onChange={() => chooseProvider(item.provider, item.model)}
                      disabled={item.status === "unavailable"}
                    />
                    <span className="provider-option__icon" aria-hidden="true">
                      {item.provider === "offline" ? <LockKeyhole size={18} /> : <Cloud size={18} />}
                    </span>
                    <span className="provider-option__copy">
                      <strong>{item.label}</strong>
                      <small>{item.description}</small>
                    </span>
                    <StatusBadge status={item.status} />
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="field">
              <span>Model</span>
              <input value={model} onChange={(event) => setModel(event.target.value)} />
              <small>Model availability is validated by the API before the run is queued.</small>
            </label>

            {provider !== "offline" ? (
              <label className="consent-card">
                <input
                  type="checkbox"
                  checked={allowExternalDataTransfer}
                  onChange={(event) => setAllowExternalDataTransfer(event.target.checked)}
                />
                <span>
                  <strong>Allow this seed data to leave the local environment</strong>
                  <small>
                    The selected provider receives seed content and generated context. Charges may apply.
                  </small>
                </span>
              </label>
            ) : null}

            <Disclosure summary="Quality and candidate limits">
              <div className="form-grid form-grid--three">
                <label className="field">
                  <span>Minimum quality</span>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={qualityThreshold}
                    onChange={(event) => setQualityThreshold(Number(event.target.value))}
                  />
                </label>
                <label className="field">
                  <span>Similarity ceiling</span>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={similarityThreshold}
                    onChange={(event) => setSimilarityThreshold(Number(event.target.value))}
                  />
                </label>
                <label className="field">
                  <span>Candidate multiplier</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={candidateMultiplier}
                    onChange={(event) => setCandidateMultiplier(Number(event.target.value))}
                  />
                </label>
              </div>
              <p className="detail-note">
                The worker stops after accepting the target or evaluating {formatCount(targetCount * candidateMultiplier)} candidates. Exact duplicates always reject before scoring.
              </p>
            </Disclosure>
          </section>
        </div>

        <aside className="generation-layout__rail" aria-labelledby="preflight-title">
          <section className="panel preflight-panel">
            <div className="section-title-row section-title-row--compact">
              <span className="step-icon" aria-hidden="true"><ShieldCheck size={18} /></span>
              <div>
                <p className="eyebrow">Step 3</p>
                <h2 id="preflight-title">Review before starting</h2>
              </div>
            </div>

            {!preflightIsFresh ? (
              <div className="preflight-intro">
                <Gauge size={25} aria-hidden="true" />
                <strong>Check the complete plan</strong>
                <p>Validate seeds, provider readiness, candidate limits, external transfer, and the maximum cost.</p>
              </div>
            ) : null}

            {preflightIsFresh ? (
              <div className="preflight-results">
                <div className="preflight-summary">
                  <div><span>Target</span><strong>{formatCount(preflight.data.targetCount)}</strong></div>
                  <div><span>Candidate cap</span><strong>{formatCount(preflight.data.maximumCandidates)}</strong></div>
                  <div><span>Provider calls</span><strong>{formatCount(preflight.data.estimatedCalls)}</strong></div>
                  <div><span>Max estimate</span><strong>{formatMoney(preflight.data.estimatedCostUsd)}</strong></div>
                </div>
                <ul className="check-list">
                  {preflight.data.checks.map((check) => (
                    <li key={check.label} className={check.passed ? "is-passed" : "is-failed"}>
                      {check.passed ? <Check size={16} /> : <AlertTriangle size={16} />}
                      <div><strong>{check.label}</strong><span>{check.detail}</span></div>
                    </li>
                  ))}
                </ul>
                {preflight.data.warnings.map((warning) => (
                  <div className="inline-warning" key={warning}>
                    <AlertTriangle size={16} aria-hidden="true" /> {warning}
                  </div>
                ))}
              </div>
            ) : null}

            {preflight.isError && preflightKey === currentKey ? (
              <p className="form-error" role="alert">{preflight.error.message}</p>
            ) : null}

            <button
              className="button button--secondary button--full"
              type="button"
              onClick={checkSetup}
              disabled={!canCheck || preflight.isPending}
            >
              {preflight.isPending ? <LoaderCircle className="spin" size={17} /> : <FileCheck2 size={17} />}
              {preflight.isPending ? "Checking setup…" : preflightIsFresh ? "Check again" : "Check setup"}
            </button>
            <button
              className="button button--primary button--full"
              type="button"
              onClick={startRun}
              disabled={!preflightIsFresh || !preflight.data?.ready || createRun.isPending}
            >
              {createRun.isPending ? <LoaderCircle className="spin" size={17} /> : <Play size={17} />}
              {createRun.isPending ? "Queueing run…" : "Start generation"}
            </button>
            {!preflightIsFresh ? <p className="button-help">Run preflight after every recipe change.</p> : null}
          </section>

          {queuedRun ? (
            <section className="success-card" role="status">
              <span aria-hidden="true"><CheckCircle2 size={21} /></span>
              <div>
                <strong>Generation queued</strong>
                <p>{queuedRun.name} is ready for the worker.</p>
                <button className="text-action" type="button" onClick={onOpenRuns}>
                  Follow the run <ArrowRight size={15} />
                </button>
              </div>
            </section>
          ) : null}
          {createRun.isError ? <p className="form-error" role="alert">{createRun.error.message}</p> : null}
        </aside>
      </div>
    </div>
  );
}
