import type {
  Candidate,
  CreateExportInput,
  CreateProjectInput,
  CreateRunInput,
  DatasetFoundryApi,
  ExportArtifact,
  OverviewData,
  PreflightRequest,
  PreflightResult,
  Project,
  ProviderKind,
  ProviderStatus,
  ReviewInput,
  Run,
  SeedUploadResult,
  SystemStatus,
} from "./types";

const API_ROOT = "/api/v1";
const DEFAULT_TIMEOUT_MS = 15_000;

interface ProblemDetail {
  detail?: string;
  message?: string;
  title?: string;
  code?: string;
  request_id?: string;
  retryable?: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly retryable: boolean;

  constructor(
    message: string,
    options: { status: number; code?: string; requestId?: string | null; retryable?: boolean },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code ?? "request_failed";
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? options.status >= 500;
  }
}

function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (normalized.includes("..") || normalized.startsWith("//")) {
    throw new Error("API paths must remain inside /api/v1");
  }
  return `${API_ROOT}${normalized}`;
}

function asItems<T>(payload: T[] | { items: T[] }): T[] {
  return Array.isArray(payload) ? payload : payload.items;
}

export async function fetchJson<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort("timeout"), timeoutMs);
  const externalSignal = init.signal;
  const abortFromExternal = () => controller.abort(externalSignal?.reason);

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort(externalSignal.reason);
    } else {
      externalSignal.addEventListener("abort", abortFromExternal, { once: true });
    }
  }

  try {
    const headers = new Headers(init.headers);
    if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    headers.set("Accept", "application/json");

    const response = await fetch(apiUrl(path), {
      ...init,
      headers,
      signal: controller.signal,
    });

    if (response.status === 204) {
      return undefined as T;
    }

    const contentType = response.headers.get("content-type") ?? "";
    const payload: unknown = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      const problem =
        typeof payload === "object" && payload !== null ? (payload as ProblemDetail) : {};
      const message =
        problem.detail ??
        problem.message ??
        problem.title ??
        (typeof payload === "string" && payload ? payload : `Request failed (${response.status})`);
      throw new ApiError(message, {
        status: response.status,
        code: problem.code ?? "request_failed",
        requestId: problem.request_id ?? response.headers.get("x-request-id"),
        retryable: problem.retryable ?? response.status >= 500,
      });
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (controller.signal.aborted) {
      throw new ApiError("The request took too long or was cancelled.", {
        status: 0,
        code: externalSignal?.aborted ? "request_cancelled" : "request_timeout",
        retryable: !externalSignal?.aborted,
      });
    }
    throw new ApiError(error instanceof Error ? error.message : "The API could not be reached.", {
      status: 0,
      code: "network_error",
      retryable: true,
    });
  } finally {
    window.clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", abortFromExternal);
  }
}

function projectFromWire(value: Record<string, unknown>): Project {
  return {
    id: String(value.id ?? ""),
    name: String(value.name ?? "Untitled project"),
    description: String(value.description ?? ""),
    seedCount: Number(value.seed_count ?? value.seedCount ?? 0),
    generatedCount: Number(value.generated_count ?? value.generatedCount ?? 0),
    acceptedCount: Number(value.accepted_count ?? value.acceptedCount ?? 0),
    lastActivity: String(value.last_activity ?? value.updated_at ?? value.lastActivity ?? ""),
    activeRunId:
      value.active_run_id === null || value.activeRunId === null
        ? null
        : String(value.active_run_id ?? value.activeRunId ?? "") || null,
  };
}

function runFromWire(value: Record<string, unknown>): Run {
  return {
    id: String(value.id ?? ""),
    projectId: String(value.project_id ?? value.projectId ?? ""),
    projectName: String(value.project_name ?? value.projectName ?? "Project"),
    name: String(value.name ?? "Generation run"),
    status: String(value.status ?? "queued") as Run["status"],
    provider: String(value.provider ?? "offline") as Run["provider"],
    model: String(value.model ?? "offline-deterministic"),
    targetCount: Number(value.target_count ?? value.targetCount ?? 0),
    generatedCount: Number(value.generated_count ?? value.generatedCount ?? 0),
    acceptedCount: Number(value.accepted_count ?? value.acceptedCount ?? 0),
    reviewCount: Number(value.needs_review_count ?? value.review_count ?? value.reviewCount ?? 0),
    rejectedCount: Number(value.rejected_count ?? value.rejectedCount ?? 0),
    averageQuality:
      value.average_quality == null && value.averageQuality == null
        ? null
        : Number(value.average_quality ?? value.averageQuality),
    duplicateRate:
      value.duplicate_rate == null && value.duplicateRate == null
        ? null
        : Number(value.duplicate_rate ?? value.duplicateRate),
    startedAt: String(value.started_at ?? value.startedAt ?? ""),
    completedAt:
      value.finished_at == null && value.completed_at == null && value.completedAt == null
        ? null
        : String(value.finished_at ?? value.completed_at ?? value.completedAt),
  };
}

const exportFormats = new Set<ExportArtifact["format"]>([
  "canonical_jsonl",
  "openai_chat_jsonl",
  "alpaca_jsonl",
  "parquet",
]);

function exportRowsFromWire(value: Record<string, unknown>, run?: Run): ExportArtifact[] {
  const artifacts = Array.isArray(value.artifacts) ? value.artifacts : null;
  if (artifacts) {
    const manifest =
      typeof value.manifest === "object" && value.manifest !== null
        ? (value.manifest as Record<string, unknown>)
        : {};
    const exportId = String(value.id ?? "");
    const runId = String(value.run_id ?? value.runId ?? "");
    const rawStatus = String(value.status ?? "building");
    const status = (rawStatus === "completed" ? "ready" : rawStatus) as ExportArtifact["status"];
    const createdAt = String(value.created_at ?? value.createdAt ?? manifest.created_at ?? "");
    return artifacts.flatMap((rawArtifact) => {
      if (typeof rawArtifact !== "object" || rawArtifact === null) return [];
      const artifact = rawArtifact as Record<string, unknown>;
      const format = String(artifact.format ?? "") as ExportArtifact["format"];
      if (!exportFormats.has(format)) return [];
      const filename = String(artifact.filename ?? artifact.path ?? "Dataset artifact");
      return [{
        id: `${exportId}:${filename}`,
        exportId,
        projectId: run?.projectId ?? "",
        projectName: run?.projectName ?? `Run ${runId.slice(0, 8)}`,
        runId,
        name: filename,
        format,
        status,
        exampleCount: Number(manifest.total_count ?? artifact.row_count ?? 0),
        sizeBytes: artifact.size_bytes == null ? null : Number(artifact.size_bytes),
        sha256: artifact.sha256 == null ? null : String(artifact.sha256),
        createdAt,
        downloadUrl:
          artifact.download_url == null ? null : String(artifact.download_url),
      }];
    });
  }

  return [{
    id: String(value.id ?? ""),
    exportId: String(value.export_id ?? value.id ?? ""),
    projectId: String(value.project_id ?? value.projectId ?? ""),
    projectName: String(value.project_name ?? value.projectName ?? "Project"),
    runId: String(value.run_id ?? value.runId ?? ""),
    name: String(value.name ?? "Dataset export"),
    format: String(value.format ?? "canonical_jsonl") as ExportArtifact["format"],
    status: String(value.status ?? "building") as ExportArtifact["status"],
    exampleCount: Number(value.example_count ?? value.exampleCount ?? 0),
    sizeBytes:
      value.size_bytes == null && value.sizeBytes == null
        ? null
        : Number(value.size_bytes ?? value.sizeBytes),
    sha256: value.sha256 == null ? null : String(value.sha256),
    createdAt: String(value.created_at ?? value.createdAt ?? ""),
    downloadUrl:
      value.download_url == null && value.downloadUrl == null
        ? null
        : String(value.download_url ?? value.downloadUrl),
  }];
}

function candidateFromWire(value: Record<string, unknown>): Candidate {
  const example =
    typeof value.example === "object" && value.example !== null
      ? (value.example as Record<string, unknown>)
      : {};
  const messages = Array.isArray(example.messages) ? example.messages : [];
  const messageRecords = messages.filter(
    (message): message is Record<string, unknown> => typeof message === "object" && message !== null,
  );
  let userMessage: Record<string, unknown> | undefined;
  let assistantMessage: Record<string, unknown> | undefined;
  for (let index = messageRecords.length - 1; index >= 0; index -= 1) {
    const message = messageRecords[index];
    if (!message) continue;
    if (!userMessage && message.role === "user") userMessage = message;
    if (!assistantMessage && message.role === "assistant") assistantMessage = message;
    if (userMessage && assistantMessage) break;
  }
  const sourceIds = Array.isArray(value.source_seed_ids) ? value.source_seed_ids : [];
  const sourceExamples = Array.isArray(value.source_examples) ? value.source_examples : [];
  const firstSource =
    typeof sourceExamples[0] === "object" && sourceExamples[0] !== null
      ? (sourceExamples[0] as Record<string, unknown>)
      : {};
  const sourceMessages = Array.isArray(firstSource.messages) ? firstSource.messages : [];
  const sourceMessageRecords = sourceMessages.filter(
    (message): message is Record<string, unknown> => typeof message === "object" && message !== null,
  );
  let sourceUserMessage: Record<string, unknown> | undefined;
  let sourceAssistantMessage: Record<string, unknown> | undefined;
  for (let index = sourceMessageRecords.length - 1; index >= 0; index -= 1) {
    const message = sourceMessageRecords[index];
    if (!message) continue;
    if (!sourceUserMessage && message.role === "user") sourceUserMessage = message;
    if (!sourceAssistantMessage && message.role === "assistant") sourceAssistantMessage = message;
    if (sourceUserMessage && sourceAssistantMessage) break;
  }
  const rawScores = Array.isArray(value.components)
    ? value.components
    : Array.isArray(value.scores)
      ? value.scores
      : [];
  return {
    id: String(value.id ?? ""),
    runId: String(value.run_id ?? value.runId ?? ""),
    sourceSeedId: String(sourceIds[0] ?? value.source_seed_id ?? value.sourceSeedId ?? ""),
    sourcePrompt: String(sourceUserMessage?.content ?? value.source_prompt ?? value.sourcePrompt ?? ""),
    sourceResponse: String(
      sourceAssistantMessage?.content ?? value.source_response ?? value.sourceResponse ?? "",
    ),
    generatedPrompt: String(
      userMessage?.content ?? value.generated_prompt ?? value.generatedPrompt ?? "Generated prompt unavailable",
    ),
    generatedResponse: String(
      assistantMessage?.content ?? value.generated_response ?? value.generatedResponse ?? "Generated response unavailable",
    ),
    decision: String(value.effective_decision ?? value.decision ?? "needs_review") as Candidate["decision"],
    automatedDecision: String(
      value.automated_decision ?? value.automatedDecision ?? value.decision ?? "needs_review",
    ) as Candidate["automatedDecision"],
    qualityScore:
      value.quality_score == null && value.qualityScore == null
        ? null
        : Number(value.quality_score ?? value.qualityScore),
    nearestSimilarity:
      value.nearest_similarity == null && value.nearestSimilarity == null
        ? null
        : Number(value.nearest_similarity ?? value.nearestSimilarity),
    nearestCandidateId:
      value.nearest_match_id == null &&
      value.nearest_candidate_id == null &&
      value.nearestCandidateId == null
        ? null
        : String(value.nearest_match_id ?? value.nearest_candidate_id ?? value.nearestCandidateId),
    reasonCodes: Array.isArray(value.reason_codes ?? value.reasonCodes)
      ? ((value.reason_codes ?? value.reasonCodes) as unknown[]).map(String)
      : [],
    scores: rawScores.map((score) => {
      const item = score as Record<string, unknown>;
      return {
        label: String(item.label ?? item.name ?? "Score"),
        value: Number(item.value ?? item.score ?? 0),
        explanation: String(item.explanation ?? item.reason ?? ""),
      };
    }),
    reviewerNote:
      value.reviewer_note == null && value.reviewerNote == null
        ? null
        : String(value.reviewer_note ?? value.reviewerNote),
    providerTrace: String(
      value.provider_trace ??
        value.providerTrace ??
        ([value.provider, value.model].filter(Boolean).join(" · ") || "Recorded by the API"),
    ),
  };
}

interface OverviewWire {
  projects?: number;
  datasets?: number;
  seed_examples?: number;
  generated_examples?: number;
  runs?: Partial<Record<Run["status"], number>>;
  candidates?: Partial<Record<Candidate["decision"], number>>;
  exports?: number;
}

interface ProviderCatalogWire {
  default_provider?: string;
  providers?: Array<{
    id?: string;
    label?: string;
    configured?: boolean;
    live?: boolean;
    requires_external_data_transfer?: boolean;
    model?: string;
  }>;
}

interface PreflightWire {
  ready?: boolean;
  provider?: string;
  model?: string;
  seed_count?: number;
  candidate_budget?: number;
  call_budget?: number;
  estimated_tokens?: number;
  external_data_transfer_required?: boolean;
  blockers?: string[];
  worker_ready?: boolean;
}

function buildOverview(payload: OverviewWire, runs: Run[]): OverviewData {
  const accepted = Number(payload.candidates?.accepted ?? 0);
  const review = Number(payload.candidates?.needs_review ?? 0);
  const rejected = Number(payload.candidates?.rejected ?? 0);
  const generated = accepted + review + rejected;
  const completedRuns = runs.filter((run) => run.status.startsWith("completed"));
  const scoredRuns = completedRuns.filter((run) => run.averageQuality !== null);
  const averageQuality = scoredRuns.length
    ? scoredRuns.reduce((total, run) => total + (run.averageQuality ?? 0), 0) / scoredRuns.length
    : null;
  const duplicateRuns = completedRuns.filter((run) => run.duplicateRate !== null);
  const duplicateRate = duplicateRuns.length
    ? duplicateRuns.reduce((total, run) => total + (run.duplicateRate ?? 0), 0) /
      duplicateRuns.length
    : null;

  return {
    projectCount: Number(payload.projects ?? 0),
    datasetCount: Number(payload.datasets ?? 0),
    seedExamples: Number(payload.seed_examples ?? 0),
    generatedExamples: Number(payload.generated_examples ?? generated),
    acceptedExamples: accepted,
    acceptanceRate: generated ? accepted / generated : 0,
    averageQuality,
    duplicateRate,
    activeRun: runs.find((run) => run.status === "running" || run.status === "queued") ?? null,
    recentRuns: runs.slice(0, 4),
    qualitySegments: [
      { label: "Accepted", count: accepted, tone: "success" },
      { label: "Needs review", count: review, tone: "warning" },
      { label: "Rejected", count: rejected, tone: "danger" },
    ],
    readyExports: Number(payload.exports ?? 0),
  };
}

export const httpApi: DatasetFoundryApi = {
  async getSystemStatus(signal) {
    const payload = await fetchJson<Record<string, unknown>>(
      "/system/status",
      signal ? { signal } : {},
    );
    return {
      apiReady: Boolean(payload.api_ready ?? true),
      workerReady: Boolean(payload.worker_ready),
      workerState: String(payload.worker_state ?? "missing") as SystemStatus["workerState"],
    };
  },

  async getOverview(signal) {
    const [payload, runs] = await Promise.all([
      fetchJson<OverviewWire>("/overview", signal ? { signal } : {}),
      this.listRuns(signal),
    ]);
    return buildOverview(payload, runs);
  },

  async listProjects(signal) {
    const payload = await fetchJson<Record<string, unknown>[] | { items: Record<string, unknown>[] }>(
      "/projects",
      signal ? { signal } : {},
    );
    return asItems(payload).map(projectFromWire);
  },

  async createProject(input: CreateProjectInput) {
    const payload = await fetchJson<Record<string, unknown>>("/projects", {
      method: "POST",
      body: JSON.stringify(input),
    });
    return projectFromWire(payload);
  },

  async uploadSeeds(projectId: string, file: File) {
    const body = new FormData();
    body.set("file", file);
    const payload = await fetchJson<Record<string, unknown>>(
      `/projects/${encodeURIComponent(projectId)}/seeds`,
      {
      method: "POST",
      body,
      },
    );
    return {
      datasetId: String(payload.id ?? ""),
      filename: String(payload.name ?? file.name),
      importedCount: Number(payload.row_count ?? 0),
      duplicateCount: Number(payload.duplicate_count ?? 0),
      fingerprint: String(payload.fingerprint ?? ""),
    } satisfies SeedUploadResult;
  },

  async preflight(input: PreflightRequest) {
    const recipe = await fetchJson<Record<string, unknown>>(
      `/projects/${encodeURIComponent(input.projectId)}/recipes`,
      {
        method: "POST",
        body: JSON.stringify({
          name: input.runName,
          target_count: input.targetCount,
          provider: input.provider,
          model: input.model,
          min_quality_score: input.qualityThreshold,
          max_similarity: input.similarityThreshold,
          candidate_multiplier: input.candidateMultiplier,
          seed: 17,
          allow_external_data_transfer: input.allowExternalDataTransfer,
        }),
      },
    );
    const recipeId = String(recipe.id ?? "");
    const result = await fetchJson<PreflightWire>(
      `/recipes/${encodeURIComponent(recipeId)}/preflight`,
      {
        method: "POST",
        body: JSON.stringify({
          provider: input.provider,
          model: input.model,
          allow_external_data_transfer: input.allowExternalDataTransfer,
        }),
      },
    );
    const blockers = result.blockers ?? [];
    const workerReady = Boolean(result.worker_ready);
    const externalTransfer = Boolean(result.external_data_transfer_required);
    const transferReady = !externalTransfer || input.allowExternalDataTransfer;
    return {
      recipeId,
      ready: Boolean(result.ready) && workerReady,
      seedCount: Number(result.seed_count ?? 0),
      targetCount: input.targetCount,
      maximumCandidates: Number(result.candidate_budget ?? input.targetCount * input.candidateMultiplier),
      estimatedCalls: Number(result.call_budget ?? 0),
      estimatedTokens: Number(result.estimated_tokens ?? 0),
      estimatedCostUsd: null,
      provider: String(result.provider ?? input.provider) as ProviderKind,
      model: String(result.model ?? input.model),
      warnings: [
        ...(externalTransfer
          ? ["Seed content will be sent to the selected external provider."]
          : []),
        ...(!workerReady
          ? ["No active worker was detected. Start `uv run dataset-foundry worker`."]
          : []),
      ],
      checks: [
        {
          label: "Recipe readiness",
          passed: Boolean(result.ready),
          detail: blockers.length ? blockers.join(" · ") : "The API accepted the bounded recipe.",
        },
        {
          label: "Candidate budget",
          passed: Number(result.candidate_budget ?? 0) > 0,
          detail: `At most ${Number(result.candidate_budget ?? 0).toLocaleString()} candidates.`,
        },
        {
          label: "Worker availability",
          passed: workerReady,
          detail: workerReady
            ? "A generation worker is ready to process this run."
            : "Start `uv run dataset-foundry worker` before queueing the run.",
        },
        {
          label: "Data transfer",
          passed: transferReady,
          detail: externalTransfer
            ? "External transfer requires explicit acknowledgement."
            : "Generation stays in this local environment.",
        },
      ],
    };
  },

  async listRuns(signal) {
    const payload = await fetchJson<Record<string, unknown>[] | { items: Record<string, unknown>[] }>(
      "/runs",
      signal ? { signal } : {},
    );
    return asItems(payload).map(runFromWire);
  },

  async createRun(input: CreateRunInput) {
    const payload = await fetchJson<Record<string, unknown>>("/runs", {
      method: "POST",
      body: JSON.stringify({
        project_id: input.projectId,
        recipe_id: input.recipeId,
        provider: input.provider,
        model: input.model,
        allow_external_data_transfer: input.allowExternalDataTransfer,
      }),
    });
    return runFromWire(payload);
  },

  async cancelRun(runId: string) {
    const payload = await fetchJson<Record<string, unknown>>(
      `/runs/${encodeURIComponent(runId)}/cancel`,
      { method: "POST" },
    );
    return runFromWire(payload);
  },

  async listCandidates(runId: string, decision, cursor, signal) {
    const params = new URLSearchParams({ limit: "100" });
    if (decision !== "all") params.set("decision", decision);
    if (cursor) params.set("cursor", cursor);
    const payload = await fetchJson<{
      items: Record<string, unknown>[];
      next_cursor?: string | null;
    }>(
      `/runs/${encodeURIComponent(runId)}/candidates?${params.toString()}`,
      signal ? { signal } : {},
    );
    return {
      items: payload.items.map(candidateFromWire),
      nextCursor: payload.next_cursor ?? null,
    };
  },

  async reviewCandidate(input: ReviewInput) {
    await fetchJson<Record<string, unknown>>(
      `/candidates/${encodeURIComponent(input.candidateId)}/reviews`,
      {
      method: "POST",
      body: JSON.stringify({ decision: input.decision, note: input.note }),
      },
    );
  },

  async listExports(signal) {
    const [payload, runs] = await Promise.all([
      fetchJson<Record<string, unknown>[] | { items: Record<string, unknown>[] }>(
        "/exports",
        signal ? { signal } : {},
      ),
      this.listRuns(signal),
    ]);
    const runsById = new Map(runs.map((run) => [run.id, run]));
    return asItems(payload).flatMap((item) =>
      exportRowsFromWire(item, runsById.get(String(item.run_id ?? item.runId ?? ""))),
    );
  },

  async createExport(input: CreateExportInput) {
    const payload = await fetchJson<Record<string, unknown>>(
      `/runs/${encodeURIComponent(input.runId)}/exports`,
      {
      method: "POST",
      body: JSON.stringify({
        name: input.name,
        formats: [input.format],
        train_percent: input.trainPercent,
        validation_percent: input.validationPercent,
        test_percent: input.testPercent,
      }),
      },
    );
    const rows = exportRowsFromWire(payload);
    const artifact = rows.find((item) => item.format === input.format) ?? rows[0];
    if (!artifact) {
      throw new ApiError("The export completed without a downloadable dataset file.", {
        status: 500,
        code: "export_artifact_missing",
      });
    }
    return artifact;
  },

  async listProviders(signal) {
    const payload = await fetchJson<ProviderCatalogWire>("/providers", signal ? { signal } : {});
    return (payload.providers ?? []).map((item) => {
      const provider = String(item.id ?? "offline") as ProviderKind;
      const configured = provider === "offline" || Boolean(item.configured);
      return {
        provider,
        label: String(item.label ?? provider),
        status: configured ? "ready" : "setup_needed",
        description:
          provider === "offline"
            ? "Key-free deterministic generation for demos, tests, and repeatable baselines."
            : configured
              ? "Configured on the API service and available for structured generation."
              : "Configure credentials on the API service to enable structured generation.",
        model: String(item.model ?? ""),
        dataLeavesEnvironment: Boolean(item.requires_external_data_transfer),
      } satisfies ProviderStatus;
    });
  },
};

export { API_ROOT };
