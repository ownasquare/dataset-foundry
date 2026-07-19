import { Activity } from "lucide-react";

import { MetricCard } from "../../src/components/MetricCard";
import { StatePanel } from "../../src/components/StatePanel";
import { StatusBadge } from "../../src/components/StatusBadge";

describe("shared workbench states", () => {
  it("renders status and metric primitives", () => {
    cy.mount(
      <div style={{ display: "grid", gap: 16, padding: 24 }}>
        <MetricCard label="Generated" value="2,480" detail="1,934 accepted" icon={Activity} />
        <StatusBadge status="needs_review" />
      </div>,
    );
    cy.contains("Generated").should("be.visible");
    cy.contains("Needs review").should("be.visible");
  });

  it("renders loading, empty, and recoverable error states", () => {
    const retry = cy.stub().as("retry");
    cy.mount(
      <div style={{ display: "grid", gap: 16, padding: 24 }}>
        <StatePanel kind="loading" />
        <StatePanel kind="empty" title="No exports yet" message="Create one after review." />
        <StatePanel kind="error" onRetry={retry} />
      </div>,
    );
    cy.get('[aria-label="Loading data"]').should("exist");
    cy.contains("No exports yet").should("be.visible");
    cy.contains("button", "Retry").click();
    cy.get("@retry").should("have.been.calledOnce");
  });
});
