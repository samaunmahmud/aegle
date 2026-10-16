// Mirrors the DTOs in core-api (StudyService, WorklistController, AuditController, MeController,
// ModelCatalogController).
import type { Specialty } from "../specialties";

export type StudyStatus = "RECEIVED" | "QUEUED" | "ANALYZING" | "READY" | "REVIEWED" | "FAILED";
export type WorklistState = "OPEN" | "IN_REVIEW" | "DONE";
export type Urgency = "CRITICAL" | "URGENT" | "ROUTINE";
export type ReviewDecision = "ACCEPT" | "REJECT" | "MODIFY";

export type Grade = "CONSULTANT" | "REGISTRAR" | "FOUNDATION";

export interface Me {
  userId: string;
  organisationId: string;
  organisationName: string;
  roles: string[];
  jobTitle: string | null;
  grade: Grade | null;
  specialty: Specialty | null;
  avatar: string | null;
}

export interface Person {
  id: string;
  name: string;
  jobTitle: string | null;
  grade: Grade | null;
  specialty: Specialty | null;
  avatar: string | null;
}

export interface ConsultThread {
  id: string;
  subject: string;
  specialty: Specialty | null;
  studyId: string | null;
  studyLabel: string | null;
  urgency: "ROUTINE" | "URGENT";
  status: "OPEN" | "RESOLVED";
  createdAt: string;
  lastMessageAt: string;
  createdBy: Person;
  askedOf: Person | null;
  messageCount: number;
  unread: number;
  lastMessage: { authorName: string; preview: string; at: string } | null;
}

export interface ConsultMessage {
  id: string;
  author: Person;
  body: string;
  at: string;
  mine: boolean;
}

export interface ConsultDetail {
  thread: ConsultThread;
  messages: ConsultMessage[];
}

export type ConsultBox = "for-me" | "mine" | "open" | "resolved";

export interface NewConsult {
  subject: string;
  body: string;
  specialty?: Specialty;
  studyId?: string;
  askedOf?: string;
  urgency: "ROUTINE" | "URGENT";
}

export interface WorklistItem {
  studyId: string;
  patientMrn: string;
  specialty: Specialty;
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
  specialty: Specialty;
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
  intendedUse: string;
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

export interface MeasurementView {
  name: string;
  value: number;
  unit: string;
}

export interface MeasurementPoint {
  studyId: string;
  studyDate: string | null;
  receivedAt: string;
  name: string;
  value: number;
  unit: string;
}

export interface StudyDetail {
  study: StudySummary;
  patient: Patient;
  predictions: PredictionView[];
  hasHeatmap: boolean;
  reviews: ReviewView[];
  jobs: JobView[];
  priority: unknown;
  measurements: MeasurementView[];
  measurementHistory: MeasurementPoint[];
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

export interface SpecialtySummary {
  specialty: Specialty;
  open: number;
  inReview: number;
  critical: number;
  urgent: number;
  slaBreached: number;
  oldestWaitingSince: string | null;
}

export interface ModelEntry {
  id: string;
  name: string;
  specialty: Specialty;
  modality: string;
  bodyPart: string | null;
  task: string;
  intendedUse: string;
  activeVersion: string | null;
  weightsSha256: string | null;
  approvedAt: string | null;
  metrics: Record<string, unknown> | null;
  enabledForOrganisation: boolean;
}
