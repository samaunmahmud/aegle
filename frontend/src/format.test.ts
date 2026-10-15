import { describe, expect, it } from "vitest";
import { age, clinicalDate, clinicalDateTime, clinicalDay, clock, duration, patientName, probability, slaStatus, titleCase, waited } from "./format";

describe("duration", () => {
  it("uses minutes, then hours, then days", () => {
    expect(duration(45)).toBe("45m");
    expect(duration(135)).toBe("2h 15m");
    expect(duration(47 * 60 + 59)).toBe("47h 59m");
    expect(duration(76 * 60)).toBe("3d 4h");
  });

  it("never shows a negative time", () => {
    expect(duration(-5)).toBe("0m");
  });
});

describe("slaStatus", () => {
  const now = Date.parse("2026-01-01T12:00:00Z");

  it("is null without a deadline", () => {
    expect(slaStatus(null, now)).toBeNull();
  });

  it("is ok an hour or more before the deadline", () => {
    expect(slaStatus("2026-01-01T14:00:00Z", now)).toEqual({ text: "2h 0m left", state: "ok" });
  });

  it("is soon within the last hour", () => {
    expect(slaStatus("2026-01-01T12:30:00Z", now)).toEqual({ text: "30m left", state: "soon" });
  });

  it("is breached after the deadline", () => {
    expect(slaStatus("2026-01-01T11:00:00Z", now)).toEqual({ text: "1h 0m overdue", state: "breached" });
  });
});

describe("waited", () => {
  it("counts from the given time", () => {
    expect(waited("2026-01-01T11:20:00Z", Date.parse("2026-01-01T12:00:00Z"))).toBe("40m");
  });
});

describe("age", () => {
  it("is null without a date of birth", () => {
    expect(age(null)).toBeNull();
  });

  it("does not count this year's birthday before it happens", () => {
    const t = new Date();
    const past = new Date(t.getFullYear() - 30, t.getMonth(), t.getDate());
    const tomorrow = new Date(t.getFullYear() - 30, t.getMonth(), t.getDate() + 1);
    const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T00:00:00`;
    expect(age(iso(past))).toBe(30);
    expect(age(iso(tomorrow))).toBe(29);
  });
});

describe("titleCase", () => {
  it("turns API enums into words", () => {
    expect(titleCase("CANCER_STROMA")).toBe("Cancer stroma");
  });
});

describe("probability", () => {
  it("shows one decimal place", () => {
    expect(probability(0.4567)).toBe("45.7%");
  });

  it("never claims certainty", () => {
    expect(probability(0.99996)).toBe(">99.9%");
    expect(probability(1)).toBe(">99.9%");
    expect(probability(0.00004)).toBe("<0.1%");
    expect(probability(0)).toBe("<0.1%");
  });
});

describe("clinical display formats", () => {
  it("writes dates with a named month, so 03/04 cannot be misread", () => {
    expect(clinicalDate("1971-02-19")).toBe("19-Feb-1971");
    expect(clinicalDate(new Date(2026, 9, 5, 23, 59))).toBe("05-Oct-2026");
  });

  it("uses the 24-hour clock", () => {
    expect(clinicalDateTime(new Date(2026, 9, 15, 9, 5))).toBe("15-Oct-2026 09:05");
    expect(clock(new Date(2026, 9, 15, 22, 41))).toBe("22:41");
    expect(clinicalDay(new Date(2026, 9, 15))).toBe("Thu 15-Oct-2026");
  });

  it("puts the family name first, in capitals", () => {
    expect(patientName("Priya Natarajan")).toBe("NATARAJAN, Priya");
    expect(patientName("Mary Ann Smith")).toBe("SMITH, Mary Ann");
    expect(patientName("Cher")).toBe("CHER");
    expect(patientName(null)).toBeNull();
  });
});
