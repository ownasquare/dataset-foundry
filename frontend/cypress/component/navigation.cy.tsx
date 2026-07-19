import { App } from "../../src/App";
import { createDemoApi } from "../../src/api/demo";
import type { ViewKey } from "../../src/api/types";
import { hashForView, parseViewHash, VIEW_HASHES } from "../../src/navigation";

const HEADINGS: Record<ViewKey, string> = {
  overview: "Turn seed examples into training-ready data",
  generate: "Generate a dataset",
  review: "Review candidates",
  exports: "Exports",
  projects: "Projects",
  runs: "Generation runs",
  settings: "Settings",
};

describe("workbench URL navigation", () => {
  beforeEach(() => {
    cy.window().then((win) => {
      win.history.replaceState(win.history.state, "", "#overview");
    });
  });

  it("keeps one canonical hash for every workbench view", () => {
    for (const [view, hash] of Object.entries(VIEW_HASHES) as Array<
      [ViewKey, (typeof VIEW_HASHES)[ViewKey]]
    >) {
      expect(hashForView(view)).to.equal(hash);
      expect(parseViewHash(hash)).to.equal(view);
    }
    expect(parseViewHash("")).to.equal(null);
    expect(parseViewHash("#unknown")).to.equal(null);
    expect(parseViewHash("#/review")).to.equal(null);
  });

  it("loads a direct view hash and gives an explicit initial view precedence", () => {
    cy.window().then((win) => {
      win.history.replaceState(win.history.state, "", "#review");
    });
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode />);
    cy.contains("h1", HEADINGS.review).should("be.visible");
    cy.hash().should("equal", "#review");
    cy.get("a.skip-link").click({ force: true });
    cy.hash().should("equal", "#review");
    cy.focused().should("have.id", "main-content");

    cy.mount(
      <App api={createDemoApi({ latencyMs: 0 })} demoMode initialView="exports" />,
    );
    cy.contains("h1", HEADINGS.exports).should("be.visible");
    cy.hash().should("equal", "#exports");
  });

  it("normalizes empty and invalid states to Overview", () => {
    cy.window().then((win) => {
      win.history.replaceState(win.history.state, "", "#not-a-view");
    });
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode />);
    cy.contains("h1", HEADINGS.overview).should("be.visible");
    cy.hash().should("equal", "#overview");

    cy.window().then((win) => {
      win.history.replaceState(win.history.state, "", `${win.location.pathname}${win.location.search}`);
      win.dispatchEvent(new win.HashChangeEvent("hashchange"));
    });
    cy.contains("h1", HEADINGS.overview).should("be.visible");
    cy.hash().should("equal", "#overview");
  });

  it("pushes navigation state and syncs the mobile drawer on browser history", () => {
    cy.viewport(390, 844);
    cy.mount(<App api={createDemoApi({ latencyMs: 0 })} demoMode />);

    cy.get('button[aria-label="Open navigation"]').click();
    cy.get('aside[aria-label="Primary navigation"]').within(() => {
      cy.contains("button", /^Review$/).click();
    });
    cy.contains("h1", HEADINGS.review).should("be.visible");
    cy.hash().should("equal", "#review");
    cy.get('aside[aria-label="Primary navigation"]').should("not.be.visible");

    cy.get('button[aria-label="Open navigation"]').click();
    cy.contains("button", "More").click();
    cy.contains("button", /^Projects$/).should("be.visible");
    cy.window().then((win) => {
      win.history.pushState(win.history.state, "", "#overview");
      win.dispatchEvent(new win.PopStateEvent("popstate"));
    });

    cy.contains("h1", HEADINGS.overview).should("be.visible");
    cy.get('aside[aria-label="Primary navigation"]').should("not.be.visible");
    cy.focused().should("have.id", "main-content");
    cy.get('button[aria-label="Open navigation"]').click();
    cy.contains("button", /^Projects$/).should("not.exist");
  });
});
