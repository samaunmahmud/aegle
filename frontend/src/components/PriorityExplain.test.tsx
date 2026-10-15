import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { PriorityBreakdown } from "./PriorityExplain";

afterEach(cleanup);

const reason = {
  terms: [
    { label: "UNINFECTED", weight: 10, probability: 0.015, contribution: 0.15, urgencyClass: "ROUTINE" },
    { label: "PARASITIZED", weight: 100, probability: 0.985, contribution: 98.5, urgencyClass: "CRITICAL" },
  ],
  formula: "priority = sum(probability x urgency weight)",
};

describe("PriorityBreakdown", () => {
  it("lists terms largest first and adds the waiting bonus to the total", () => {
    const { container } = render(<PriorityBreakdown reason={reason} waitBonus={20} />);
    const rows = [...container.querySelectorAll(".pbreak-row")].map((r) => r.textContent);
    expect(rows[0]).toContain("Parasitized");
    expect(rows[0]).toContain("98.5% × 100");
    expect(rows[2]).toContain("Time waiting");
    expect(rows.at(-1)).toContain("118.7");
  });

  it("says so when no breakdown was recorded", () => {
    const { container } = render(<PriorityBreakdown reason={null} />);
    expect(container.textContent).toMatch(/No breakdown recorded/);
  });
});
