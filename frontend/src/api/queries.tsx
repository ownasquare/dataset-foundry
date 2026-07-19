import { createContext, useContext } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import type {
  CreateExportInput,
  CreateProjectInput,
  CreateRunInput,
  DatasetFoundryApi,
  PreflightRequest,
  ReviewInput,
} from "./types";

export const ApiContext = createContext<DatasetFoundryApi | null>(null);

function useApi(): DatasetFoundryApi {
  const api = useContext(ApiContext);
  if (!api) throw new Error("Dataset Foundry API context is missing");
  return api;
}

export const queryKeys = {
  systemStatus: ["system-status"] as const,
  overview: ["overview"] as const,
  projects: ["projects"] as const,
  runs: ["runs"] as const,
  candidates: (runId: string, decision = "all", cursor: string | null = null) =>
    ["candidates", runId, decision, cursor] as const,
  candidateRun: (runId: string) => ["candidates", runId] as const,
  exports: ["exports"] as const,
  providers: ["providers"] as const,
};

export function useSystemStatus() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.systemStatus,
    queryFn: ({ signal }) => api.getSystemStatus(signal),
    refetchInterval: 5_000,
  });
}

async function invalidateWorkspace(client: QueryClient): Promise<void> {
  await Promise.all([
    client.invalidateQueries({ queryKey: queryKeys.overview }),
    client.invalidateQueries({ queryKey: queryKeys.projects }),
    client.invalidateQueries({ queryKey: queryKeys.runs }),
    client.invalidateQueries({ queryKey: queryKeys.exports }),
  ]);
}

export function useOverview() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.overview,
    queryFn: ({ signal }) => api.getOverview(signal),
  });
}

export function useProjects() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.projects,
    queryFn: ({ signal }) => api.listProjects(signal),
  });
}

export function useCreateProject() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateProjectInput) => api.createProject(input),
    onSuccess: () => invalidateWorkspace(client),
  });
}

export function useUploadSeeds() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, file }: { projectId: string; file: File }) =>
      api.uploadSeeds(projectId, file),
    onSuccess: () => invalidateWorkspace(client),
  });
}

export function usePreflight() {
  const api = useApi();
  return useMutation({ mutationFn: (input: PreflightRequest) => api.preflight(input) });
}

export function useRuns() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.runs,
    queryFn: ({ signal }) => api.listRuns(signal),
    refetchInterval: (query) => {
      const active = query.state.data?.some(
        (run) => run.status === "queued" || run.status === "running",
      );
      return active ? 2_500 : false;
    },
  });
}

export function useCreateRun() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateRunInput) => api.createRun(input),
    onSuccess: () => invalidateWorkspace(client),
  });
}

export function useCancelRun() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => api.cancelRun(runId),
    onSuccess: () => invalidateWorkspace(client),
  });
}

export function useCandidates(runId: string, decision: string, cursor: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.candidates(runId, decision, cursor),
    queryFn: ({ signal }) =>
      api.listCandidates(
        runId,
        decision as "accepted" | "needs_review" | "rejected" | "all",
        cursor,
        signal,
      ),
    enabled: Boolean(runId),
  });
}

export function useReviewCandidate(runId: string) {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: ReviewInput) => api.reviewCandidate(input),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.candidateRun(runId) }),
        client.invalidateQueries({ queryKey: queryKeys.overview }),
        client.invalidateQueries({ queryKey: queryKeys.runs }),
      ]);
    },
  });
}

export function useExports() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.exports,
    queryFn: ({ signal }) => api.listExports(signal),
  });
}

export function useCreateExport() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateExportInput) => api.createExport(input),
    onSuccess: () => invalidateWorkspace(client),
  });
}

export function useProviders() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.providers,
    queryFn: ({ signal }) => api.listProviders(signal),
    staleTime: 30_000,
  });
}
