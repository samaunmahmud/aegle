// Mirrors the DTOs in core-api (StudyService, WorklistController, AuditController, MeController).

export type StudyStatus = "RECEIVED" | "QUEUED" | "ANALYZING" | "READY" | "REVIEWED" | "FAILED";
export type WorklistState = "OPEN" | "IN_REVIEW" | "DONE";
export type Urgency = "CRITICAL" | "URGENT" | "ROUTINE";
export type ReviewDecision = "ACCEPT" | "REJECT" | "MODIFY";

export interface Me {
  userId: string;
  organisationId: string;
  roles: string[];
}

export interface WorklistItem {
  studyId: string;
  patientMrn: string;
  modality: string;
  bodyPart: string;
  studyStatus: StudyStatus;
  state: WorklistState;
  priorityScore: number;
  waitBonus: number;
  effectivePriority: number;
  urgencyClass: Urgency | null;
  topLabel: string | null;
  topProbability: number | null;
  slaDueAt: string | null;
  slaBreached: boolean;
  studyCreatedAt: string;
  assignedTo: string | null;
  priorityReason: unknown;
}

export interface WorklistPage {
  items: WorklistItem[];
  total: number;
}

export interface StudySummary {
  id: string;
  status: StudyStatus;
  source: "UPLOAD" | "DICOM" | "DICOMWEB";
  modality: string;
  bodyPart: string;
  accessionNo: string | null;
  studyDate: string | null;
  createdAt: string;
  patientMrn: string;
}

export interface Patient {
  mrn: string;
  name: string | null;
  dob: string | null;
  sex: string | null;
}

export interface PredictionView {
  id: string;
  label: string;
  probability: number;
  urgencyClass: Urgency;
  modelName: string;
  modelVersion: string;
  weightsSha256: string;
  analysedAt: string;
}

export interface ReviewView {
  id: string;
  predictionId: string;
  decision: ReviewDecision;
  finalLabel: string | null;
  comment: string | null;
  reviewedAt: string;
  reviewer: string;
}

export interface JobView {
  id: string;
  status: string;
  attempts: number;
  error: string | null;
}

export interface StudyDetail {
  study: StudySummary;
  patient: Patient;
  predictions: PredictionView[];
  hasHeatmap: boolean;
  reviews: ReviewView[];
  jobs: JobView[];
  priority: unknown;
}

export interface UploadResult {
  studyId: string;
  status: StudyStatus;
  jobsQueued: number;
}

export interface UploadRequest {
  file: File;
  patientMrn: string;
  patientName?: string;
  patientDob?: string;
  patientSex?: "F" | "M" | "O" | "U";
  modality: string;
  bodyPart: string;
  accessionNo?: string;
  studyDate?: string;
}

export interface DicomSource {
  aeTitle: string;
  description: string | null;
  createdAt: string;
}

export interface AuditVerification {
  entries: number;
  intact: boolean;
  firstBrokenSeq: number | null;
  headHash: string;
}

export interface AuditEntry {
  id: number;
  at: string;
  actor: string;
  action: string;
  entityType: string;
  entityId: string;
  ip: string | null;
  details: unknown;
}
