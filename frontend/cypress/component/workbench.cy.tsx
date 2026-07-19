import { App } from "../../src/App";
import { ApiError } from "../../src/api/client";
import { createDemoApi } from "../../src/api/demo";
import type { Candidate } from "../../src/api/types";

describe("Dataset Foundry workbench", () => {
  beforeEach(() => {
    cy.window().then((window) => window.history.replaceState(null, "", "#overview"));
  });

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

  it("explains quality reasons in plain language while preserving raw codes", () => {
    const api = createDemoApi({ latencyMs: 0 });
    const originalList = api.listCandidates.bind(api);
    api.listCandidates = async (...args) => {
      const page = await originalList(...args);
      return {
        ...page,
        items: page.items.map((candidate, index) =>
          index === 0
            ? {
                ...candidate,
                reasonCodes: ["REFERENCE_DETAIL_EXPANDED", "near_duplicate", "policy_not_grounded"],
                qualityReasons: [
                  {
                    code: "REFERENCE_DETAIL_EXPANDED",
                    evidence: "The response adds usage guidance that the source did not provide.",
                  },
                  {
                    code: "near_duplicate",
                    evidence: "The wording is very close to an accepted example.",
                  },
                  { code: "policy_not_grounded", evidence: null },
                ],
              }
            : candidate,
        ),
      };
    };

    cy.mount(<App api={api} demoMode initialView="review" />);

    cy.contains("strong", "Adds an unsupported detail").should("be.visible");
    cy.contains("The response adds usage guidance that the source did not provide.").should(
      "be.visible",
    );
    cy.contains("strong", "Policy not grounded").should("be.visible");
    cy.contains("strong", "Near duplicate").should("be.visible");
    cy.contains(
      "This check came from a custom or newer scorer. Review the score details before deciding.",
    ).should("be.visible");
    cy.contains("summary", "Show raw reason codes").parent("details").should("not.have.attr", "open");
    cy.contains("summary", "Show raw reason codes").click();
    cy.contains("code", "REFERENCE_DETAIL_EXPANDED").should("be.visible");
    cy.contains("code", "policy_not_grounded").should("be.visible");
    cy.get('summary[aria-label="About quality reasons"]').focus().type("{enter}");
    cy.contains("These labels summarize automated checks.").should("be.visible");
    cy.get('summary[aria-label="About quality reasons"]').type("{esc}");
    cy.get('summary[aria-label="About quality reasons"]')
      .should("be.focused")
      .parent("details")
      .should("not.have.attr", "open");
  });

  it("keeps export inputs and localizes a stale run error", () => {
    const api = createDemoApi({ latencyMs: 0 });
    const originalRuns = api.listRuns.bind(api);
    let runBecameStale = false;
    api.listRuns = async (signal) => {
      const listed = await originalRuns(signal);
      return runBecameStale
        ? listed.filter((run) => run.id !== "run-support-tone")
        : listed;
    };
    const originalCreate = api.createExport.bind(api);
    let createAttempts = 0;
    api.createExport = async (input) => {
      createAttempts += 1;
      if (createAttempts > 1) return originalCreate(input);
      expect(input.projectId).to.equal("project-support");
      expect(input.runId).to.equal("run-support-tone");
      runBecameStale = true;
      throw new ApiError("This run is not ready to export. Choose a completed run.", {
        status: 409,
        code: "export_run_not_complete",
        issues: [{ loc: ["path", "run_id"], msg: "Run is not complete.", type: "conflict" }],
      });
    };

    cy.mount(<App api={api} demoMode initialView="exports" />);
    cy.contains("button", "New export").click();
    cy.contains("label", "Completed run").find("select").as("runSelect");
    cy.get("@runSelect").should("have.value", "run-support-tone");
    cy.contains("button", "Create immutable export").click();

    cy.contains("This run is not ready to export. Choose a completed run.").should("be.visible");
    cy.get("@runSelect").should("have.value", "").and("be.focused");
    cy.contains("label", "Export name").find("input").should("have.value", "Fine-tuning dataset · v1");
    cy.contains("label", "Format").find("select").should("have.value", "parquet");
    cy.contains("label", "Train %").find("input").should("have.value", "90");
    cy.contains("label", "Project").find("select").select("project-product");
    cy.contains("label", "Completed run").find("select").should("have.value", "run-product-grounding");
    cy.contains("button", "Create immutable export").click();
    cy.contains("h2", "Create export").should("not.exist");
  });

  it("shows a clear export prerequisite when no project exists", () => {
    const api = createDemoApi({ latencyMs: 0 });
    api.listProjects = async () => [];

    cy.mount(<App api={api} demoMode initialView="exports" />);
    cy.contains("button", "New export").click();

    cy.contains("No projects available").should("be.visible");
    cy.contains("Create a project and import seed examples before building an export.").should(
      "be.visible",
    );
    cy.contains("label", "Project").should("not.exist");
  });

  it("excludes completed runs without accepted examples", () => {
    const api = createDemoApi({ latencyMs: 0 });
    const originalRuns = api.listRuns.bind(api);
    api.listRuns = async (signal) => (await originalRuns(signal)).map((run) =>
      run.projectId === "project-support" && run.status.startsWith("completed")
        ? { ...run, acceptedCount: 0 }
        : run,
    );

    cy.mount(<App api={api} demoMode initialView="exports" />);
    cy.contains("button", "New export").click();

    cy.contains("No completed run with accepted examples is available for this project.").should(
      "be.visible",
    );
    cy.contains("label", "Completed run").find("select").should("have.value", "");
    cy.contains("button", "Create immutable export").should("be.disabled");
  });

  it("requires a corrected selection after the server reports no accepted examples", () => {
    const api = createDemoApi({ latencyMs: 0 });
    api.createExport = async () => {
      throw new ApiError(
        "This run has no accepted examples to package. Review candidates or choose another run.",
        { status: 409, code: "export_run_has_no_accepted_examples" },
      );
    };

    cy.mount(<App api={api} demoMode initialView="exports" />);
    cy.contains("button", "New export").click();
    cy.contains("button", "Create immutable export").click();

    cy.contains(
      "This run has no accepted examples to package. Review candidates or choose another run.",
    ).should("be.visible");
    cy.contains("button", "Create immutable export").should("be.disabled");
    cy.contains("label", "Export name").find("input").type(" updated");
    cy.contains(
      "This run has no accepted examples to package. Review candidates or choose another run.",
    ).should("be.visible");
    cy.contains("button", "Create immutable export").should("be.disabled");
    cy.contains("label", "Project").find("select").select("project-product");
    cy.contains(
      "This run has no accepted examples to package. Review candidates or choose another run.",
    ).should("not.exist");
    cy.contains("button", "Create immutable export").should("not.be.disabled");
  });

  it("keeps native percentage bounds active", () => {
    const api = createDemoApi({ latencyMs: 0 });

    cy.mount(<App api={api} demoMode initialView="exports" />);
    cy.contains("button", "New export").click();
    cy.contains("label", "Train %").find("input").clear().type("110").should("match", ":invalid");
    cy.get(".export-builder form").should("not.have.attr", "novalidate");
    cy.get(".export-builder form")
      .then(($form) => expect(($form[0] as HTMLFormElement).checkValidity()).to.equal(false));
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
