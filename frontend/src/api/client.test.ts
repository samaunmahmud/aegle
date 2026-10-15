import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../auth/keycloak", () => ({ freshToken: vi.fn(async () => "test-token") }));

import { api, ApiError } from "./client";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

function json(status: number, body: unknown, statusText = "") {
  return new Response(JSON.stringify(body), {
    status,
    statusText,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api requests", () => {
  it("send the bearer token", async () => {
    fetchMock.mockResolvedValue(json(200, { id: "u1" }));
    await api.me();
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/me");
    expect(init.headers.Authorization).toBe("Bearer test-token");
  });

  it("build the worklist query from states and specialty", async () => {
    fetchMock.mockResolvedValue(json(200, { items: [] }));
    await api.worklist(["OPEN"], "NEUROLOGY");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/worklist?state=OPEN&limit=200&specialty=NEUROLOGY");
  });

  it("surface the API's problem detail as the error message", async () => {
    fetchMock.mockResolvedValue(json(403, { detail: "Model switched off for this organisation" }, "Forbidden"));
    const err = await api.models().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(403);
    expect(err.message).toBe("Model switched off for this organisation");
  });

  it("fall back to the status text for a non-JSON error", async () => {
    fetchMock.mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502, statusText: "Bad Gateway" }));
    const err = await api.models().catch((e) => e);
    expect(err.status).toBe(502);
    expect(err.message).toBe("Bad Gateway");
  });

  it("return nothing for 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.removeDicomSource("AEGLE/CR 1")).resolves.toBeUndefined();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/dicom-sources/AEGLE%2FCR%201");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
  });
});

describe("api.upload", () => {
  it("sends only the fields that are filled in", async () => {
    fetchMock.mockResolvedValue(json(201, { studyId: "s1" }));
    const file = new File(["x"], "scan.png", { type: "image/png" });
    await api.upload({ file, patientMrn: "MRN1", modality: "XR", bodyPart: "CHEST" });
    const form: FormData = fetchMock.mock.calls[0][1].body;
    expect(form.get("patientMrn")).toBe("MRN1");
    expect(form.get("modality")).toBe("XR");
    expect(form.has("patientName")).toBe(false);
    expect(form.has("accessionNo")).toBe(false);
  });
});
