import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { MeasurementPoint } from "../api/types";
import { formatValue, measurementTitle, MeasurementTrend } from "./MeasurementTrend";

afterEach(cleanup);

function point(studyId: string, studyDate: string, value: number): MeasurementPoint {
  return { studyId, studyDate, receivedAt: studyDate, name: "wound_area", value, unit: "px" } as MeasurementPoint;
}

describe("formatValue", () => {
  it("formats by unit", () => {
    expect(formatValue(12.345, "%")).toBe("12.3%");
    expect(formatValue(3.6, "count")).toBe("4");
    expect(formatValue(1234.4, "px")).toBe(`${(1234).toLocaleString()} px`);
  });
});

describe("measurementTitle", () => {
  it("names known measurements and falls back to the raw name", () => {
    expect(measurementTitle("wound_area")).toBe("Wound area");
    expect(measurementTitle("lesion_count")).toBe("lesion count");
  });
});

describe("MeasurementTrend", () => {
  const points = [point("s1", "2026-01-01", 2000), point("s2", "2026-02-01", 1500)];

  it("renders nothing without points", () => {
    const { container } = render(<MeasurementTrend title="Wound area" points={[]} currentStudyId="s1" />);
    expect(container.innerHTML).toBe("");
  });

  it("shows the latest value and the change since the first visit", () => {
    render(<MeasurementTrend title="Wound area" points={points} currentStudyId="s2" />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toBe(
      `Wound area over 2 visits, latest ${formatValue(1500, "px")}`,
    );
    expect(screen.getByText(/25% since first visit/).textContent).toContain("▼");
  });

  it("switches to a table that marks the current study", () => {
    render(<MeasurementTrend title="Wound area" points={points} currentStudyId="s2" />);
    fireEvent.click(screen.getByRole("button", { name: "Table" }));
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(rows[2].textContent).toContain("(this study)");
    expect(rows[1].textContent).not.toContain("(this study)");
  });
});
