import { App } from "../../src/App";
import { createDemoApi } from "../../src/api/demo";
import type { Candidate } from "../../src/api/types";

describe("Dataset Foundry workbench", () => {
  it("navigates the complete task-first workspace", () => {
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode />);

    cy.contains("h1", "Turn seed examples into training-ready data").should("be.visible");
    const coreHeadings = {
      Generate: "Generate a dataset",
      Review: "Review candidates",
      Exports: "Exports",
    } as const;
    for (const view of Object.keys(coreHeadings) as Array<keyof typeof coreHeadings>) {
      cy.contains("button", new RegExp(`^${view}$`)).click();
      cy.contains("h1", coreHeadings[view]).should("be.visible");
    }

    for (const secondary of ["Projects", "Runs", "Settings"]) {
      cy.contains("button", new RegExp(`^${secondary}$`)).should("not.exist");
    }
    cy.contains("button", "More").click();
    const secondaryHeadings = {
      Projects: "Projects",
      Runs: "Generation runs",
      Settings: "Settings",
    } as const;
    for (const view of Object.keys(secondaryHeadings) as Array<keyof typeof secondaryHeadings>) {
      cy.contains("button", new RegExp(`^${view}$`)).click();
      cy.contains("h1", secondaryHeadings[view]).should("be.visible");
    }
  });

  it("preflights and queues an offline generation", () => {
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode initialView="generate" />);

    cy.contains("button", "Check setup").click();
    cy.contains("Candidate cap").should("be.visible");
    cy.contains("button", "Start generation").should("not.be.disabled").click();
    cy.contains("Generation queued").should("be.visible");
  });

  it("explains advanced quality controls without adding default-page prose", () => {
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode initialView="generate" />);

    cy.contains("summary", "Quality and candidate limits").click();
    cy.get('summary[aria-label="About minimum quality"]').click();
    cy.contains("Examples scoring below this value are not automatically accepted.").should(
      "be.visible",
    );
  });

  it("cancels an active run from the workbench", () => {
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode initialView="runs" />);
    cy.on("window:confirm", () => true);

    cy.contains("button", "Cancel run").click();
    cy.contains("Run cancelled").should("be.visible");
    cy.contains("Cancelled").should("be.visible");
  });

  it("measures run progress against accepted examples instead of evaluated candidates", () => {
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode initialView="runs" />);

    cy.contains("133%").should("not.exist");
    cy.contains("135%").should("not.exist");
    cy.contains("100%").should("be.visible");
    cy.contains("button", "Grounded product answer expansion").click();
    cy.contains("500 of 500 accepted · 664 evaluated").should("be.visible");
  });

  it("turns an empty workspace into one clear first action", () => {
    const api = createDemoApi({ latencyMs: 0 });
    api.getOverview = async () => ({
      projectCount: 0,
      datasetCount: 0,
      seedExamples: 0,
      generatedExamples: 0,
      acceptedExamples: 0,
      acceptanceRate: 0,
      averageQuality: null,
      duplicateRate: null,
      activeRun: null,
      recentRuns: [],
      qualitySegments: [],
      readyExports: 0,
    });
    api.listProjects = async () => [];
    cy.mount(<App api={api} />);

    cy.contains("h2", "Create your first dataset").should("be.visible");
    cy.contains("button", "Create a project").click();
    cy.contains("h1", "Projects").should("be.visible");
    cy.contains("button", "New project").should("be.visible");
  });

  it("does not carry a review note onto the next candidate", () => {
    const api = createDemoApi({ latencyMs: 0 });
    const originalList = api.listCandidates.bind(api);
    let reviewQueue: Candidate[] | null = null;
    api.listCandidates = async (runId, decision) => {
      if (!reviewQueue) {
        const source = await originalList(runId, "all", null);
        reviewQueue = [
          { ...source.items[0]!, id: "review-first", generatedPrompt: "First review prompt", decision: "needs_review", reviewerNote: "First candidate only" },
          { ...source.items[0]!, id: "review-second", generatedPrompt: "Second review prompt", decision: "needs_review", reviewerNote: null },
        ];
      }
      return {
        items: reviewQueue.filter((candidate) => decision === "all" || candidate.decision === decision),
        nextCursor: null,
      };
    };
    api.reviewCandidate = async (input) => {
      reviewQueue = (reviewQueue ?? []).map((candidate) =>
        candidate.id === input.candidateId
          ? { ...candidate, decision: input.decision, reviewerNote: input.note || null }
          : candidate,
      );
    };

    cy.mount(<App api={api} demoMode initialView="review" />);
    cy.get('textarea[placeholder="Explain the decision for future reviewers"]').should(
      "have.value",
      "First candidate only",
    );
    cy.get(".decision-actions").contains("button", "Accept").click();
    cy.contains("h2", "Second review prompt").should("be.visible");
    cy.get('textarea[placeholder="Explain the decision for future reviewers"]').should(
      "have.value",
      "",
    );
  });

  it("reports an offline worker without implying generation is ready", () => {
    const api = createDemoApi({ latencyMs: 0 });
    api.getSystemStatus = async () => ({
      apiReady: true,
      workerReady: false,
      workerState: "missing",
    });
    cy.mount(<App api={api} />);

    cy.contains("API ready · worker offline").should("be.visible");
    cy.contains("uv run dataset-foundry worker").should("be.visible");
  });
});
