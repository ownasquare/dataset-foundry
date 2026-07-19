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
  ProviderStatus,
  ReviewInput,
  Run,
  SeedUploadResult,
} from "./types";

const NOW = "2026-07-18T16:40:00Z";

const INITIAL_PROJECTS: Project[] = [
  {
    id: "project-support",
    name: "Customer support assistant",
    description: "Policy-grounded conversations for refunds, delivery, and account help.",
    seedCount: 48,
    generatedCount: 1_680,
    acceptedCount: 1_312,
    lastActivity: "2026-07-18T16:32:00Z",
    activeRunId: "run-support-edge",
  },
  {
    id: "project-product",
    name: "Product Q&A",
    description: "Grounded product questions with concise, citation-ready answers.",
    seedCount: 32,
    generatedCount: 800,
    acceptedCount: 622,
    lastActivity: "2026-07-18T14:55:00Z",
    activeRunId: null,
  },
  {
    id: "project-onboarding",
    name: "Onboarding coach",
    description: "Friendly onboarding guidance across English, French, and Spanish.",
    seedCount: 24,
    generatedCount: 360,
    acceptedCount: 281,
    lastActivity: "2026-07-17T21:14:00Z",
    activeRunId: null,
  },
];

const INITIAL_RUNS: Run[] = [
  {
    id: "run-support-edge",
    projectId: "project-support",
    projectName: "Customer support assistant",
    name: "Support policy edge cases",
    status: "running",
    provider: "offline",
    model: "offline-deterministic-v1",
    targetCount: 1_000,
    generatedCount: 724,
    acceptedCount: 568,
    reviewCount: 41,
    rejectedCount: 115,
    averageQuality: 0.847,
    duplicateRate: 0.086,
    startedAt: "2026-07-18T16:12:00Z",
    completedAt: null,
  },
  {
    id: "run-product-grounding",
    projectId: "project-product",
    projectName: "Product Q&A",
    name: "Grounded product answer expansion",
    status: "completed_with_review",
    provider: "offline",
    model: "offline-deterministic-v1",
    targetCount: 500,
    generatedCount: 664,
    acceptedCount: 500,
    reviewCount: 27,
    rejectedCount: 137,
    averageQuality: 0.882,
    duplicateRate: 0.104,
    startedAt: "2026-07-18T14:31:00Z",
    completedAt: "2026-07-18T14:55:00Z",
  },
  {
    id: "run-support-tone",
    projectId: "project-support",
    projectName: "Customer support assistant",
    name: "Refund tone diversity",
    status: "completed",
    provider: "openai",
    model: "gpt-5.6-luna",
    targetCount: 750,
    generatedCount: 1_012,
    acceptedCount: 750,
    reviewCount: 0,
    rejectedCount: 262,
    averageQuality: 0.913,
    duplicateRate: 0.071,
    startedAt: "2026-07-18T10:07:00Z",
    completedAt: "2026-07-18T10:42:00Z",
  },
  {
    id: "run-onboarding-locales",
    projectId: "project-onboarding",
    projectName: "Onboarding coach",
    name: "Multi-locale onboarding",
    status: "completed_with_review",
    provider: "anthropic",
    model: "claude-sonnet-5",
    targetCount: 300,
    generatedCount: 402,
    acceptedCount: 281,
    reviewCount: 18,
    rejectedCount: 103,
    averageQuality: 0.824,
    duplicateRate: 0.129,
    startedAt: "2026-07-17T20:48:00Z",
    completedAt: "2026-07-17T21:14:00Z",
  },
];

const INITIAL_CANDIDATES: Candidate[] = [
  {
    id: "candidate-201",
    runId: "run-product-grounding",
    sourceSeedId: "product-seed-12",
    sourcePrompt: "Does the TrailPack 24 include a rain cover?",
    sourceResponse: "Yes. A removable rain cover is stored in the lower zip pocket.",
    generatedPrompt: "Where can I find the rain cover that comes with the TrailPack 24?",
    generatedResponse:
      "The included rain cover is tucked inside the lower zippered pocket. Pull it out and stretch its elastic edge around the pack when the weather turns.",
    decision: "needs_review",
    automatedDecision: "needs_review",
    qualityScore: 0.86,
    nearestSimilarity: 0.74,
    nearestCandidateId: "candidate-144",
    reasonCodes: ["REFERENCE_DETAIL_EXPANDED"],
    scores: [
      { label: "Completeness", value: 0.92, explanation: "Answers where the cover is stored." },
      { label: "Seed novelty", value: 0.81, explanation: "Changes the wording and user intent." },
      { label: "Grounding", value: 0.84, explanation: "Adds a usage detail not present in the seed." },
      { label: "Diversity", value: 0.88, explanation: "Distinct from accepted examples." },
    ],
    reviewerNote: null,
    providerTrace: "offline-deterministic · template family product-location · batch 7",
  },
  {
    id: "candidate-202",
    runId: "run-product-grounding",
    sourceSeedId: "product-seed-07",
    sourcePrompt: "How long does the bottle keep drinks cold?",
    sourceResponse: "Up to 24 hours when filled with cold liquid and ice.",
    generatedPrompt: "Will the Northline bottle keep water cold through a full day hike?",
    generatedResponse:
      "Yes. It is rated to keep cold drinks chilled for up to 24 hours, so it covers a typical full-day hike.",
    decision: "accepted",
    automatedDecision: "accepted",
    qualityScore: 0.94,
    nearestSimilarity: 0.61,
    nearestCandidateId: "candidate-118",
    reasonCodes: [],
    scores: [
      { label: "Completeness", value: 0.98, explanation: "Directly answers the duration question." },
      { label: "Seed novelty", value: 0.93, explanation: "Introduces a realistic use case." },
      { label: "Grounding", value: 0.97, explanation: "All claims are supported by the seed." },
      { label: "Diversity", value: 0.9, explanation: "No near duplicate was found." },
    ],
    reviewerNote: null,
    providerTrace: "offline-deterministic · template family product-duration · batch 6",
  },
  {
    id: "candidate-203",
    runId: "run-product-grounding",
    sourceSeedId: "product-seed-19",
    sourcePrompt: "Can I machine wash the Merino Base 200?",
    sourceResponse: "Machine wash cold on a gentle cycle and lay flat to dry.",
    generatedPrompt: "How should I wash the Merino Base 200?",
    generatedResponse: "Machine wash cold and tumble dry on high heat.",
    decision: "rejected",
    automatedDecision: "rejected",
    qualityScore: 0.42,
    nearestSimilarity: 0.48,
    nearestCandidateId: null,
    reasonCodes: ["CONTRADICTS_REFERENCE", "UNSUPPORTED_CARE_INSTRUCTION"],
    scores: [
      { label: "Completeness", value: 0.71, explanation: "Provides a complete but incorrect answer." },
      { label: "Seed novelty", value: 0.86, explanation: "Wording is sufficiently different." },
      { label: "Grounding", value: 0.08, explanation: "Drying guidance contradicts the seed." },
      { label: "Diversity", value: 0.89, explanation: "No near duplicate was found." },
    ],
    reviewerNote: null,
    providerTrace: "offline-deterministic · template family product-care · batch 5",
  },
];

const INITIAL_EXPORTS: ExportArtifact[] = [
  {
    id: "export-support-v3",
    exportId: "export-support-v3",
    projectId: "project-support",
    projectName: "Customer support assistant",
    runId: "run-support-tone",
    name: "Support fine-tuning set · v3",
    format: "openai_chat_jsonl",
    status: "ready",
    exampleCount: 750,
    sizeBytes: 2_842_112,
    sha256: "8e42129a8ba7c1bc343ea6cda36fd126a5d969581715c58983cf19df5f83b1d3",
    createdAt: "2026-07-18T11:02:00Z",
    downloadUrl: "/api/v1/exports/export-support-v3/download",
  },
  {
    id: "export-product-parquet",
    exportId: "export-product-parquet",
    projectId: "project-product",
    projectName: "Product Q&A",
    runId: "run-product-grounding",
    name: "Product answers · grouped splits",
    format: "parquet",
    status: "ready",
    exampleCount: 500,
    sizeBytes: 1_186_304,
    sha256: "34eb5d7e58839b83c771dd5752731bf04ed6f61afc7e16bdf32c8629019a706e",
    createdAt: "2026-07-18T15:12:00Z",
    downloadUrl: "/api/v1/exports/export-product-parquet/download",
  },
];

const PROVIDERS: ProviderStatus[] = [
  {
    provider: "offline",
    label: "Offline deterministic",
    status: "ready",
    description: "Key-free template variations for demos, tests, and repeatable baselines.",
    model: "offline-deterministic-v1",
    dataLeavesEnvironment: false,
  },
  {
    provider: "openai",
    label: "OpenAI",
    status: "setup_needed",
    description: "Native structured generation. Configure credentials on the API service.",
    model: "gpt-5.6-luna",
    dataLeavesEnvironment: true,
  },
  {
    provider: "anthropic",
    label: "Anthropic",
    status: "setup_needed",
    description: "Native structured generation. Configure credentials on the API service.",
    model: "claude-sonnet-5",
    dataLeavesEnvironment: true,
  },
];

function clone<T>(value: T): T {
  return structuredClone(value);
}

function overview(projects: Project[], runs: Run[], exports: ExportArtifact[]): OverviewData {
  const generatedExamples = projects.reduce((sum, project) => sum + project.generatedCount, 0);
  const acceptedExamples = projects.reduce((sum, project) => sum + project.acceptedCount, 0);
  const scored = runs.filter((run) => run.averageQuality !== null);
  const duplicates = runs.filter((run) => run.duplicateRate !== null);
  return {
    projectCount: projects.length,
    datasetCount: projects.filter((project) => project.seedCount > 0).length,
    seedExamples: projects.reduce((sum, project) => sum + project.seedCount, 0),
    generatedExamples,
    acceptedExamples,
    acceptanceRate: generatedExamples ? acceptedExamples / generatedExamples : 0,
    averageQuality:
      scored.reduce((sum, run) => sum + (run.averageQuality ?? 0), 0) / Math.max(scored.length, 1),
    duplicateRate:
      duplicates.reduce((sum, run) => sum + (run.duplicateRate ?? 0), 0) /
      Math.max(duplicates.length, 1),
    activeRun: runs.find((run) => run.status === "running") ?? null,
    recentRuns: runs.slice(0, 4),
    qualitySegments: [
      {
        label: "Accepted",
        count: runs.reduce((sum, run) => sum + run.acceptedCount, 0),
        tone: "success",
      },
      {
        label: "Needs review",
        count: runs.reduce((sum, run) => sum + run.reviewCount, 0),
        tone: "warning",
      },
      {
        label: "Rejected",
        count: runs.reduce((sum, run) => sum + run.rejectedCount, 0),
        tone: "danger",
      },
    ],
    readyExports: exports.filter((item) => item.status === "ready").length,
  };
}

export function createDemoApi(options: { latencyMs?: number } = {}): DatasetFoundryApi {
  let projects = clone(INITIAL_PROJECTS);
  let runs = clone(INITIAL_RUNS);
  let candidates = clone(INITIAL_CANDIDATES);
  let exports = clone(INITIAL_EXPORTS);
  let nextId = 300;
  const latencyMs = options.latencyMs ?? 90;

  const respond = async <T>(value: T): Promise<T> => {
    if (latencyMs > 0) {
      await new Promise((resolve) => window.setTimeout(resolve, latencyMs));
    }
    return clone(value);
  };

  return {
    getSystemStatus: () =>
      respond({ apiReady: true, workerReady: true, workerState: "idle" as const }),
    getOverview: () => respond(overview(projects, runs, exports)),
    listProjects: () => respond(projects),
    async createProject(input: CreateProjectInput) {
      const project: Project = {
        id: `project-${nextId++}`,
        name: input.name,
        description: input.description,
        seedCount: 0,
        generatedCount: 0,
        acceptedCount: 0,
        lastActivity: NOW,
        activeRunId: null,
      };
      projects = [project, ...projects];
      return respond(project);
    },
    async uploadSeeds(projectId: string, file: File): Promise<SeedUploadResult> {
      projects = projects.map((project) =>
        project.id === projectId
          ? { ...project, seedCount: project.seedCount + 12, lastActivity: NOW }
          : project,
      );
      return respond({
        datasetId: `dataset-${nextId++}`,
        filename: file.name,
        importedCount: 12,
        duplicateCount: 0,
        fingerprint: "4d03f095c9c2721ab68b8e8c6a7283f7",
      });
    },
    preflight(input: PreflightRequest): Promise<PreflightResult> {
      const project = projects.find((item) => item.id === input.projectId);
      const isExternal = input.provider !== "offline";
      const transferReady = !isExternal || input.allowExternalDataTransfer;
      return respond({
        recipeId: `recipe-${nextId++}`,
        ready: Boolean(project?.seedCount) && transferReady,
        seedCount: project?.seedCount ?? 0,
        targetCount: input.targetCount,
        maximumCandidates: input.targetCount * input.candidateMultiplier,
        estimatedCalls: input.provider === "offline" ? 0 : Math.ceil(input.targetCount / 20),
        estimatedTokens: input.targetCount * 340,
        estimatedCostUsd: input.provider === "offline" ? 0 : input.targetCount * 0.0068,
        provider: input.provider,
        model: input.model,
        warnings: isExternal
          ? ["Seed content will be sent to the selected external provider."]
          : [],
        checks: [
          {
            label: "Seed coverage",
            passed: Boolean(project?.seedCount),
            detail: `${project?.seedCount ?? 0} valid seed examples are available.`,
          },
          {
            label: "Candidate budget",
            passed: input.candidateMultiplier <= 20,
            detail: `At most ${(input.targetCount * input.candidateMultiplier).toLocaleString()} candidates.`,
          },
          {
            label: "Data transfer",
            passed: transferReady,
            detail: isExternal
              ? "External transfer must be explicitly acknowledged."
              : "All generation stays in this local environment.",
          },
        ],
      });
    },
    listRuns: () => respond(runs),
    async createRun(input: CreateRunInput) {
      const project = projects.find((item) => item.id === input.projectId);
      const run: Run = {
        id: `run-${nextId++}`,
        projectId: input.projectId,
        projectName: project?.name ?? "Project",
        name: input.runName,
        status: "queued",
        provider: input.provider,
        model: input.model,
        targetCount: input.targetCount,
        generatedCount: 0,
        acceptedCount: 0,
        reviewCount: 0,
        rejectedCount: 0,
        averageQuality: null,
        duplicateRate: null,
        startedAt: NOW,
        completedAt: null,
      };
      runs = [run, ...runs];
      projects = projects.map((item) =>
        item.id === input.projectId ? { ...item, activeRunId: run.id, lastActivity: NOW } : item,
      );
      return respond(run);
    },
    async cancelRun(runId: string) {
      const current = runs.find((run) => run.id === runId);
      if (!current || !["queued", "running"].includes(current.status)) {
        throw new Error("Only queued or running runs can be cancelled.");
      }
      const cancelled: Run = { ...current, status: "cancelled", completedAt: NOW };
      runs = runs.map((run) => (run.id === runId ? cancelled : run));
      projects = projects.map((project) =>
        project.activeRunId === runId ? { ...project, activeRunId: null } : project,
      );
      return respond(cancelled);
    },
    listCandidates: (runId: string, decision) =>
      respond({
        items: candidates.filter(
          (candidate) =>
            (runId === "all" || candidate.runId === runId) &&
            (decision === "all" || candidate.decision === decision),
        ),
        nextCursor: null,
      }),
    async reviewCandidate(input: ReviewInput) {
      let updated: Candidate | undefined;
      candidates = candidates.map((candidate) => {
        if (candidate.id !== input.candidateId) return candidate;
        updated = {
          ...candidate,
          decision:
            input.decision === "accepted"
              ? "accepted"
              : input.decision === "rejected"
                ? "rejected"
                : "needs_review",
          reviewerNote: input.note || null,
        };
        return updated;
      });
      if (!updated) throw new Error("Candidate not found");
      await respond(updated);
    },
    listExports: () => respond(exports),
    async createExport(input: CreateExportInput) {
      const project = projects.find((item) => item.id === input.projectId);
      const run = runs.find((item) => item.id === input.runId);
      const exportId = `export-${nextId++}`;
      const artifact: ExportArtifact = {
        id: exportId,
        exportId,
        projectId: input.projectId,
        projectName: project?.name ?? "Project",
        runId: input.runId,
        name: input.name,
        format: input.format,
        status: "ready",
        exampleCount: run?.acceptedCount ?? 0,
        sizeBytes: 942_080,
        sha256: "f2344a71ea9ee40de57ab3e1de89f80399108db5417d683cda5393e9bb1bd376",
        createdAt: NOW,
        downloadUrl: `/api/v1/exports/${exportId}/download`,
      };
      exports = [artifact, ...exports];
      return respond(artifact);
    },
    listProviders: () => respond(PROVIDERS),
  };
}
