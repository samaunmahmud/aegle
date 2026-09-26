import { freshToken } from "../auth/keycloak";
import type { Specialty } from "../specialties";
import type {
  AuditEntry,
  AuditVerification,
  DicomSource,
  Me,
  ModelEntry,
  SpecialtySummary,
  StudyDetail,
  UploadRequest,
  UploadResult,
  WorklistPage,
  WorklistState,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await freshToken();
  const res = await fetch(path, {
    ...init,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    // core-api returns RFC 7807 ProblemDetail bodies: { detail: "..." }.
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body; fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function requestBlob(path: string): Promise<Blob> {
  const token = await freshToken();
  const res = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  return res.blob();
}

export const api = {
  me: () => request<Me>("/api/me"),

  worklist: (states: WorklistState[] = ["OPEN", "IN_REVIEW"], specialty?: Specialty) =>
    request<WorklistPage>(
      `/api/worklist?state=${states.join(",")}&limit=200${specialty ? `&specialty=${specialty}` : ""}`,
    ),

  models: () => request<ModelEntry[]>("/api/models"),

  worklistSummary: () => request<SpecialtySummary[]>("/api/worklist/summary"),

  setModelEnabled: (modelId: string, enabled: boolean) =>
    request<{ modelId: string; enabled: boolean }>(`/api/models/${modelId}/enabled`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    }),

  claim: (studyId: string) =>
    request<{ studyId: string; state: string }>(`/api/worklist/${studyId}/claim`, { method: "POST" }),

  studies: (status?: string) =>
    request<
      Array<{
        id: string;
        status: string;
        modality: string;
        bodyPart: string;
        accessionNo: string | null;
        studyDate: string | null;
        createdAt: string;
        patientMrn: string;
      }>
    >(`/api/studies${status ? `?status=${status}` : ""}`),

  study: (id: string) => request<StudyDetail>(`/api/studies/${id}`),

  studyImage: (id: string) => requestBlob(`/api/studies/${id}/image`),
  studyHeatmap: (id: string) => requestBlob(`/api/studies/${id}/heatmap`),

  upload: async (req: UploadRequest): Promise<UploadResult> => {
    const form = new FormData();
    form.append("file", req.file);
    form.append("patientMrn", req.patientMrn);
    if (req.patientName) form.append("patientName", req.patientName);
    if (req.patientDob) form.append("patientDob", req.patientDob);
    if (req.patientSex) form.append("patientSex", req.patientSex);
    form.append("modality", req.modality);
    form.append("bodyPart", req.bodyPart);
    if (req.accessionNo) form.append("accessionNo", req.accessionNo);
    if (req.studyDate) form.append("studyDate", req.studyDate);

    const token = await freshToken();
    const res = await fetch("/api/studies", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        // ignore
      }
      throw new ApiError(res.status, detail);
    }
    return res.json();
  },

  review: (
    predictionId: string,
    body: { decision: "ACCEPT" | "REJECT" | "MODIFY"; finalLabel?: string; comment?: string },
  ) =>
    request<{ reviewId: string; studyId: string; decision: string }>(
      `/api/predictions/${predictionId}/review`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    ),

  audit: (before?: number, action?: string) => {
    const params = new URLSearchParams({ limit: "100" });
    if (before) params.set("before", String(before));
    if (action) params.set("action", action);
    return request<AuditEntry[]>(`/api/audit?${params}`);
  },

  verifyAudit: () => request<AuditVerification>("/api/audit/verify"),

  dicomSources: () => request<DicomSource[]>("/api/admin/dicom-sources"),

  addDicomSource: (aeTitle: string, description: string) =>
    request<DicomSource>("/api/admin/dicom-sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aeTitle, description: description || null }),
    }),

  removeDicomSource: (aeTitle: string) =>
    request<void>(`/api/admin/dicom-sources/${encodeURIComponent(aeTitle)}`, { method: "DELETE" }),
};
