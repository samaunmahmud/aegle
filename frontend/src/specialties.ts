// Clinical specialties: the same seven the API derives from modality and body part
// (core-api migration V6, aegle_specialty). Presets drive the upload form.

export type Specialty =
  | "RADIOLOGY"
  | "CARDIOLOGY"
  | "DERMATOLOGY"
  | "OPHTHALMOLOGY"
  | "PATHOLOGY"
  | "GASTROENTEROLOGY"
  | "NEUROLOGY";

export interface StudyPreset {
  label: string;
  modality: string;
  bodyPart: string;
  /** False for data the platform cannot ingest yet (waveforms, video). */
  supported?: boolean;
}

export interface SpecialtyInfo {
  id: Specialty;
  slug: string;
  name: string;
  summary: string;
  presets: StudyPreset[];
  /** Models in development for this specialty, shown in the model registry. */
  planned: string[];
}

export const SPECIALTIES: SpecialtyInfo[] = [
  {
    id: "RADIOLOGY",
    slug: "radiology",
    name: "Radiology",
    summary: "Radiographs, CT and MRI outside the brain",
    planned: [],
    presets: [{ label: "Chest X-ray", modality: "XR", bodyPart: "CHEST" }],
  },
  {
    id: "CARDIOLOGY",
    slug: "cardiology",
    name: "Cardiology",
    summary: "ECG rhythm analysis and echocardiography",
    planned: ["ECG arrhythmia detection (PTB-XL): needs waveform ingestion", "Echocardiogram ejection fraction (EchoNet-Dynamic): needs a data use agreement"],
    presets: [
      { label: "12-lead ECG", modality: "ECG", bodyPart: "HEART" },
      { label: "Echocardiogram", modality: "US", bodyPart: "HEART", supported: false },
    ],
  },
  {
    id: "DERMATOLOGY",
    slug: "dermatology",
    name: "Dermatology",
    summary: "Skin lesion classification and wound tracking",
    planned: ["Skin lesion classification (HAM10000; non-commercial licence)", "Chronic wound measurement over time"],
    presets: [
      { label: "Skin lesion (dermoscopy)", modality: "XC", bodyPart: "SKIN" },
      { label: "Chronic wound photo", modality: "XC", bodyPart: "WOUND" },
    ],
  },
  {
    id: "OPHTHALMOLOGY",
    slug: "ophthalmology",
    name: "Ophthalmology",
    summary: "Retinal photography: diabetic retinopathy, glaucoma",
    planned: ["Diabetic retinopathy grading", "Glaucoma screening"],
    presets: [{ label: "Retinal fundus photo", modality: "OP", bodyPart: "EYE" }],
  },
  {
    id: "PATHOLOGY",
    slug: "pathology",
    name: "Pathology",
    summary: "Blood smears and tissue biopsies",
    planned: ["Malaria parasites on blood smears (NIH)", "Leukaemia (ALL) on blood smears", "Colorectal tissue classification (NCT-CRC-HE)"],
    presets: [
      { label: "Blood smear (cell)", modality: "SM", bodyPart: "BLOOD" },
      { label: "Tissue biopsy (H&E tile)", modality: "SM", bodyPart: "TISSUE" },
    ],
  },
  {
    id: "GASTROENTEROLOGY",
    slug: "gastroenterology",
    name: "Gastroenterology",
    summary: "Endoscopy: polyps and inflammatory bowel disease",
    planned: ["Polyps and ulcerative colitis on endoscopy (HyperKvasir)"],
    presets: [{ label: "Colonoscopy frame", modality: "ES", bodyPart: "COLON" }],
  },
  {
    id: "NEUROLOGY",
    slug: "neurology",
    name: "Neurology",
    summary: "Brain CT and MRI, EEG",
    planned: ["Acute stroke and haemorrhage on head CT: needs data access", "Seizure detection on EEG (CHB-MIT): needs waveform ingestion"],
    presets: [
      { label: "Brain MRI (T1 contrast)", modality: "MR", bodyPart: "BRAIN" },
      { label: "Head CT", modality: "CT", bodyPart: "BRAIN" },
      { label: "Scalp EEG (EDF)", modality: "EEG", bodyPart: "BRAIN" },
    ],
  },
];

export function specialtyById(id: string | null | undefined): SpecialtyInfo | undefined {
  return SPECIALTIES.find((s) => s.id === id);
}

export function specialtyBySlug(slug: string | undefined): SpecialtyInfo | undefined {
  return SPECIALTIES.find((s) => s.slug === slug);
}
