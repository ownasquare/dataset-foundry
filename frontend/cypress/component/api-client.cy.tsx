import { ApiError, fetchJson, httpApi } from "../../src/api/client";

describe("API client contracts", () => {
  it("retains stable problem codes and field issues", () => {
    cy.intercept("GET", "/api/v1/problem", {
      statusCode: 409,
      headers: { "content-type": "application/problem+json" },
      body: {
        title: "Run is not complete",
        status: 409,
        detail: "Choose a completed run.",
        code: "export_run_not_complete",
        request_id: "request-123",
        errors: [{ loc: ["path", "run_id"], msg: "Run is not complete.", type: "conflict" }],
      },
    });

    cy.wrap(null).then(async () => {
      try {
        await fetchJson("/problem");
        throw new Error("Expected the request to fail");
      } catch (error) {
        expect(error).to.be.instanceOf(ApiError);
        const problem = error as ApiError;
        expect(problem.code).to.equal("export_run_not_complete");
        expect(problem.requestId).to.equal("request-123");
        expect(problem.issues).to.deep.equal([
          { loc: ["path", "run_id"], msg: "Run is not complete.", type: "conflict" },
        ]);
      }
    });
  });

  it("prefers structured quality reasons and falls back to legacy evidence", () => {
    let requestCount = 0;
    cy.intercept("GET", "/api/v1/runs/run-1/candidates*", (request) => {
      requestCount += 1;
      request.reply({
        items: [{
          id: `candidate-${requestCount}`,
          run_id: "run-1",
          effective_decision: "needs_review",
          automated_decision: "needs_review",
          reason_codes: ["near_duplicate"],
          explanations: requestCount === 2 ? ["Legacy evidence"] : [],
          components: requestCount === 3
            ? [{
                label: "accepted_pool_diversity",
                score: 0.2,
                passed: false,
                reason_code: "near_duplicate",
                explanation: "Component evidence",
              }]
            : [],
          ...(requestCount === 1
            ? { quality_reasons: [{ code: "near_duplicate", evidence: "Structured evidence" }] }
            : {}),
        }],
        next_cursor: null,
      });
    });

    cy.wrap(null)
      .then(() => httpApi.listCandidates("run-1", "all", null))
      .then((page) => {
        expect(page.items[0]?.qualityReasons).to.deep.equal([
          { code: "near_duplicate", evidence: "Structured evidence" },
        ]);
      })
      .then(() => httpApi.listCandidates("run-1", "all", null))
      .then((page) => {
        expect(page.items[0]?.qualityReasons).to.deep.equal([
          { code: "near_duplicate", evidence: "Legacy evidence" },
        ]);
      })
      .then(() => httpApi.listCandidates("run-1", "all", null))
      .then((page) => {
        expect(page.items[0]?.qualityReasons).to.deep.equal([
          { code: "near_duplicate", evidence: "Component evidence" },
        ]);
      });
  });

  it("sends the project dependency with an export request", () => {
    cy.intercept("POST", "/api/v1/runs/run-1/exports", (request) => {
      expect(request.body.project_id).to.equal("project-1");
      request.reply({
        id: "export-1",
        run_id: "run-1",
        status: "ready",
        manifest: { total_count: 1 },
        artifacts: [{
          filename: "train.jsonl",
          format: "canonical_jsonl",
          row_count: 1,
          size_bytes: 100,
          sha256: "abc123",
          download_url: "/download/train.jsonl",
        }],
      });
    });

    cy.wrap(null)
      .then(() => httpApi.createExport({
        projectId: "project-1",
        runId: "run-1",
        name: "Snapshot",
        format: "canonical_jsonl",
        trainPercent: 90,
        validationPercent: 5,
        testPercent: 5,
      }))
      .its("format")
      .should("equal", "canonical_jsonl");
  });
});
