import { App } from "../../src/App";
import { createDemoApi } from "../../src/api/demo";

describe("Dataset Foundry workbench", () => {
  it("navigates the complete task-first workspace", () => {
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode />);

    cy.contains("h1", "Turn seed examples into training-ready data").should("be.visible");
    const headings = {
      Projects: "Projects",
      Generate: "Generate a dataset",
      Runs: "Generation runs",
      Review: "Review candidates",
      Exports: "Exports",
      Settings: "Settings",
    } as const;
    for (const view of Object.keys(headings) as Array<keyof typeof headings>) {
      cy.contains("button", new RegExp(`^${view}$`)).click();
      cy.contains("h1", headings[view]).should("be.visible");
    }
  });

  it("preflights and queues an offline generation", () => {
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode initialView="generate" />);

    cy.contains("button", "Check setup").click();
    cy.contains("Candidate cap").should("be.visible");
    cy.contains("button", "Start generation").should("not.be.disabled").click();
    cy.contains("Generation queued").should("be.visible");
  });
});
