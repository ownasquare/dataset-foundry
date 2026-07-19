export type ViewKey =
  | "overview"
  | "projects"
  | "generate"
  | "runs"
  | "review"
  | "exports"
  | "settings";

export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_with_review"
  | "failed"
  | "cancelled";

export type CandidateDecision = "accepted" | "needs_review" | "rejected";
export type ReviewDecision = "accepted" | "rejected" | "needs_review";
export type ProviderKind = "offline" | "openai" | "anthropic";
export type ExportFormat =
  | "canonical_jsonl"
  | "openai_chat_jsonl"
  | "alpaca_jsonl"
  | "parquet";

export interface Project {
  id: string;
  name: string;
  description: string;
  seedCount: number;
  generatedCount: number;
  acceptedCount: number;
  lastActivity: string;
  activeRunId: string | null;
}

export interface Run {
  id: string;
  projectId: string;
  projectName: string;
  name: string;
  status: RunStatus;
  provider: ProviderKind;
  model: string;
  targetCount: number;
  generatedCount: number;
  acceptedCount: number;
  reviewCount: number;
  rejectedCount: number;
  averageQuality: number | null;
  duplicateRate: number | null;
  startedAt: string;
  completedAt: string | null;
}

export interface QualitySegment {
  label: string;
  count: number;
  tone: "success" | "warning" | "danger" | "neutral";
}

export interface OverviewData {
  projectCount: number;
  datasetCount: number;
  seedExamples: number;
  generatedExamples: number;
  acceptedExamples: number;
  acceptanceRate: number;
  averageQuality: number | null;
  duplicateRate: number | null;
  activeRun: Run | null;
  recentRuns: Run[];
  qualitySegments: QualitySegment[];
  readyExports: number;
}

export interface CandidateScore {
  label: string;
  value: number;
  explanation: string;
}

export interface CandidateReason {
  code: string;
  evidence: string | null;
}

export interface Candidate {
  id: string;
  runId: string;
  sourceSeedId: string;
  sourcePrompt: string;
  sourceResponse: string;
  generatedPrompt: string;
  generatedResponse: string;
  decision: CandidateDecision;
  automatedDecision: CandidateDecision;
  qualityScore: number | null;
  nearestSimilarity: number | null;
  nearestCandidateId: string | null;
  reasonCodes: string[];
  qualityReasons: CandidateReason[];
  scores: CandidateScore[];
  reviewerNote: string | null;
  providerTrace: string;
}

export interface CandidatePage {
  items: Candidate[];
  nextCursor: string | null;
}

export interface ExportArtifact {
  id: string;
  exportId: string;
  projectId: string;
  projectName: string;
  runId: string;
  name: string;
  format: ExportFormat;
  status: "building" | "ready" | "failed";
  exampleCount: number;
  sizeBytes: number | null;
  sha256: string | null;
  createdAt: string;
  downloadUrl: string | null;
}

export interface ProviderStatus {
  provider: ProviderKind;
  label: string;
  status: "ready" | "setup_needed" | "unavailable";
  description: string;
  model: string;
  dataLeavesEnvironment: boolean;
}

export interface SystemStatus {
  apiReady: boolean;
  workerReady: boolean;
  workerState: "idle" | "busy" | "stale" | "stopped" | "missing";
}

export interface SeedUploadResult {
  datasetId: string;
  filename: string;
  importedCount: number;
  duplicateCount: number;
  fingerprint: string;
}

export interface PreflightRequest {
  projectId: string;
  runName: string;
  targetCount: number;
  provider: ProviderKind;
  model: string;
  qualityThreshold: number;
  similarityThreshold: number;
  candidateMultiplier: number;
  allowExternalDataTransfer: boolean;
}

export interface PreflightResult {
  recipeId: string;
  ready: boolean;
  seedCount: number;
  targetCount: number;
  maximumCandidates: number;
  estimatedCalls: number;
  estimatedTokens: number;
  estimatedCostUsd: number | null;
  provider: ProviderKind;
  model: string;
  warnings: string[];
  checks: Array<{ label: string; passed: boolean; detail: string }>;
}

export interface CreateProjectInput {
  name: string;
  description: string;
}

export interface CreateRunInput extends PreflightRequest {
  recipeId: string;
}

export interface ReviewInput {
  candidateId: string;
  decision: ReviewDecision;
  note: string;
}

export interface CreateExportInput {
  projectId: string;
  runId: string;
  name: string;
  format: ExportFormat;
  trainPercent: number;
  validationPercent: number;
  testPercent: number;
}

export interface DatasetFoundryApi {
  getSystemStatus(signal?: AbortSignal): Promise<SystemStatus>;
  getOverview(signal?: AbortSignal): Promise<OverviewData>;
  listProjects(signal?: AbortSignal): Promise<Project[]>;
  createProject(input: CreateProjectInput): Promise<Project>;
  uploadSeeds(projectId: string, file: File): Promise<SeedUploadResult>;
  preflight(input: PreflightRequest): Promise<PreflightResult>;
  listRuns(signal?: AbortSignal): Promise<Run[]>;
  createRun(input: CreateRunInput): Promise<Run>;
  cancelRun(runId: string): Promise<Run>;
  listCandidates(
    runId: string,
    decision: CandidateDecision | "all",
    cursor: string | null,
    signal?: AbortSignal,
  ): Promise<CandidatePage>;
  reviewCandidate(input: ReviewInput): Promise<void>;
  listExports(signal?: AbortSignal): Promise<ExportArtifact[]>;
  createExport(input: CreateExportInput): Promise<ExportArtifact>;
  listProviders(signal?: AbortSignal): Promise<ProviderStatus[]>;
}
