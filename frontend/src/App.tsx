import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { createDemoApi } from "./api/demo";
import { httpApi } from "./api/client";
import { ApiContext } from "./api/queries";
import type { DatasetFoundryApi, ViewKey } from "./api/types";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { AppShell } from "./components/AppShell";
import { ThemeProvider } from "./components/ThemeProvider";
import { ExportsView } from "./features/ExportsView";
import { GenerateView } from "./features/GenerateView";
import { OverviewView } from "./features/OverviewView";
import { ProjectsView } from "./features/ProjectsView";
import { ReviewView } from "./features/ReviewView";
import { RunsView } from "./features/RunsView";
import { SettingsView } from "./features/SettingsView";

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 8_000, retry: 1, refetchOnWindowFocus: false },
      mutations: { retry: 0 },
    },
  });
}

export interface AppProps {
  api?: DatasetFoundryApi;
  demoMode?: boolean;
  initialView?: ViewKey;
}

export function App({ api, demoMode = false, initialView = "overview" }: AppProps) {
  const [queryClient] = useState(createQueryClient);
  const [demoApi] = useState(() => createDemoApi());
  const [activeView, setActiveView] = useState<ViewKey>(initialView);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const selectedApi = api ?? (demoMode ? demoApi : httpApi);

  const openGenerate = (projectId?: string) => {
    if (projectId) setSelectedProjectId(projectId);
    setActiveView("generate");
  };

  let view;
  switch (activeView) {
    case "projects":
      view = <ProjectsView onGenerate={openGenerate} />;
      break;
    case "generate":
      view = (
        <GenerateView
          initialProjectId={selectedProjectId}
          onCreateProject={() => setActiveView("projects")}
          onOpenRuns={() => setActiveView("runs")}
        />
      );
      break;
    case "runs":
      view = (
        <RunsView
          onGenerate={() => setActiveView("generate")}
          onReview={() => setActiveView("review")}
        />
      );
      break;
    case "review":
      view = <ReviewView onGenerate={() => setActiveView("generate")} />;
      break;
    case "exports":
      view = <ExportsView onGenerate={() => setActiveView("generate")} />;
      break;
    case "settings":
      view = <SettingsView demoMode={demoMode} />;
      break;
    default:
      view = <OverviewView onNavigate={(next) => next === "generate" ? openGenerate() : setActiveView(next)} />;
  }

  return (
    <AppErrorBoundary>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <ApiContext.Provider value={selectedApi}>
            <AppShell activeView={activeView} onNavigate={setActiveView} demoMode={demoMode}>
              {view}
            </AppShell>
          </ApiContext.Provider>
        </QueryClientProvider>
      </ThemeProvider>
    </AppErrorBoundary>
  );
}
