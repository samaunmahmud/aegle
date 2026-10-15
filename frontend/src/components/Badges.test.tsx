import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { AiTag, PriorityTag } from "./Badges";

afterEach(cleanup);

describe("PriorityTag", () => {
  it("states the priority in text, not only in colour", () => {
    expect(render(<PriorityTag urgency="CRITICAL" />).container.textContent).toBe("P1 Critical");
    cleanup();
    expect(render(<PriorityTag urgency="ROUTINE" />).container.textContent).toBe("P3 Routine");
  });

  it("shows a placeholder before the AI has assessed the study", () => {
    expect(render(<PriorityTag urgency={null} />).container.textContent).toBe("P–");
  });
});

describe("AiTag", () => {
  it("explains that AI output is a suggestion until signed", () => {
    const tag = render(<AiTag />).getByText("AI");
    expect(tag.getAttribute("title")).toMatch(/suggestion until a clinician signs/);
  });
});
