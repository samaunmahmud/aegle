import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { SpecialtySummary } from "../api/types";
import { WorkloadChart } from "./WorkloadChart";
import { Avatar } from "./Avatar";

afterEach(cleanup);

const row = (specialty: SpecialtySummary["specialty"], open: number, critical: number, urgent: number): SpecialtySummary => ({
  specialty,
  open,
  inReview: 0,
  critical,
  urgent,
  slaBreached: 0,
  oldestWaitingSince: null,
});

describe("WorkloadChart", () => {
  it("puts departments with critical findings first and scales bars to the busiest", () => {
    const { container } = render(
      <MemoryRouter>
        <WorkloadChart summary={[row("RADIOLOGY", 20, 0, 5), row("PATHOLOGY", 10, 4, 1)]} />
      </MemoryRouter>,
    );
    const names = [...container.querySelectorAll(".workload-name")].map((n) => n.textContent?.trim());
    expect(names[0]).toBe("Pathology");
    expect(names[1]).toBe("Radiology");
    const crit = container.querySelector(".workload-row .wseg-critical") as HTMLElement;
    expect(crit.style.width).toBe("20%"); // 4 of the busiest department's 20
  });
});

describe("Avatar", () => {
  it("shows the clinician's picture, or initials when there is none", () => {
    const { container, rerender } = render(<Avatar name="Amara Okafor" avatar="amara-okafor" />);
    expect(container.querySelector("img")?.getAttribute("src")).toBe("/avatars/amara-okafor.webp");
    rerender(<Avatar name="Amara Okafor" avatar={null} />);
    expect(container.textContent).toBe("AO");
  });
});
