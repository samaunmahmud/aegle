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
    planned: ["Echocardiogram ejection fraction (EchoNet-Dynamic): needs a signed data use agreement, and video support"],
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
    planned: [],
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
    planned: ["Glaucoma screening: first model withdrawn (its dataset let a trivial image-statistics model reach AUC 0.99); needs a cleaner dataset such as REFUGE"],
    presets: [{ label: "Retinal fundus photo", modality: "OP", bodyPart: "EYE" }],
  },
  {
    id: "PATHOLOGY",
    slug: "pathology",
    name: "Pathology",
    summary: "Blood smears and tissue biopsies",
    planned: ["Leukaemia (ALL) on blood smears: C-NMC 2019 (CC BY 3.0) only downloads through IBM Aspera", "Whole-slide Gleason score and grade group (patch-level patterns are available)"],
    presets: [
      { label: "Blood smear (cell)", modality: "SM", bodyPart: "BLOOD" },
      { label: "Colorectal tissue (H&E tile)", modality: "SM", bodyPart: "TISSUE" },
      { label: "Prostate biopsy (H&E patch)", modality: "SM", bodyPart: "PROSTATE" },
    ],
  },
  {
    id: "GASTROENTEROLOGY",
    slug: "gastroenterology",
    name: "Gastroenterology",
    summary: "Endoscopy: polyps and inflammatory bowel disease",
    planned: [],
    presets: [{ label: "Colonoscopy frame", modality: "ES", bodyPart: "COLON" }],
  },
  {
    id: "NEUROLOGY",
    slug: "neurology",
    name: "Neurology",
    summary: "Brain MRI, EEG",
    planned: ["Head CT stroke triage: first model withdrawn (99 patients were too few; it missed most ischaemic strokes); needs a large set such as RSNA Intracranial Haemorrhage"],
    presets: [
      { label: "Brain MRI (T1 contrast)", modality: "MR", bodyPart: "BRAIN" },
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
