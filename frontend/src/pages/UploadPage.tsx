import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { ModelEntry } from "../api/types";
import { Icon, SpecialtyIcon } from "../components/Icons";
import { PageHeader } from "../components/PageHeader";
import { SPECIALTIES, type SpecialtyInfo, type StudyPreset } from "../specialties";

type Choice = { specialty: SpecialtyInfo; preset: StudyPreset };

function fileKind(f: File) {
  const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
  return { dcm: "DICOM", edf: "EDF (EEG)", csv: "ECG CSV", tif: "TIFF", tiff: "TIFF", png: "PNG", jpg: "JPEG", jpeg: "JPEG" }[ext] ?? (ext.toUpperCase() || "File");
}

export function UploadPage() {
  const navigate = useNavigate();
  const [choice, setChoice] = useState<Choice>({ specialty: SPECIALTIES[0], preset: SPECIALTIES[0].presets[0] });
  const [file, setFile] = useState<File | null>(null);
  const [patientMrn, setPatientMrn] = useState("");
  const [patientName, setPatientName] = useState("");
  const [patientDob, setPatientDob] = useState("");
  const [patientSex, setPatientSex] = useState<"F" | "M" | "O" | "U">("U");
  const [accessionNo, setAccessionNo] = useState("");
  const [studyDate, setStudyDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  // A local preview of the clinician's own file (browsers show PNG and JPEG only). EEG and
  // ECG exports also tell us the study type, so the matching preset is selected for them.
  function pick(f: File | null) {
    setFile(f);
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old);
      return f && /^image\/(png|jpeg)$/.test(f.type) ? URL.createObjectURL(f) : null;
    });
    const ext = f?.name.split(".").pop()?.toLowerCase();
    const modality = ext === "edf" ? "EEG" : ext === "csv" ? "ECG" : null;
    const match = modality && SPECIALTIES.flatMap((sp) => sp.presets.map((p) => ({ specialty: sp, preset: p }))).find((c) => c.preset.modality === modality);
    if (match) setChoice(match);
  }

  useEffect(() => {
    api.models().then(setModels).catch(() => setModels([]));
  }, []);

  /** Models that will run automatically for a study of this type here. */
  function modelsFor(p: StudyPreset) {
    return models.filter(
      (m) =>
        m.activeVersion &&
        m.enabledForOrganisation &&
        m.modality === p.modality &&
        (m.bodyPart == null || m.bodyPart === p.bodyPart),
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file || !patientMrn) {
      setError("A file and the patient's MRN are required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.upload({
        file,
        patientMrn,
        patientName: patientName || undefined,
        patientDob: patientDob || undefined,
        patientSex,
        modality: choice.preset.modality,
        bodyPart: choice.preset.bodyPart,
        accessionNo: accessionNo || undefined,
        studyDate: studyDate || undefined,
      });
      navigate(`/studies/${result.studyId}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="narrow">
      <PageHeader
        icon={<Icon.Upload />}
        title="New study"
        subtitle="Studies from connected modalities arrive automatically over DICOM. Use this form for files from elsewhere."
      />

      <form onSubmit={submit} className="form">
        <div className="form-section-title">1 · Study type</div>
        {SPECIALTIES.map((sp) => (
          <div key={sp.id}>
            <div className="specialty-chip" style={{ marginBottom: "0.35rem" }}>
              <SpecialtyIcon specialty={sp.id} /> {sp.name}
            </div>
            <div className="preset-grid">
              {sp.presets.map((p) => {
                const selected = choice.preset === p;
                const disabled = p.supported === false;
                return (
                  <button
                    key={p.label}
                    type="button"
                    className={`preset${selected ? " selected" : ""}`}
                    aria-pressed={selected}
                    disabled={disabled}
                    onClick={() => setChoice({ specialty: sp, preset: p })}
                  >
                    <span>
                      {p.label}
                      <span className="preset-meta">
                        {disabled ? "Coming soon: needs waveform/video support" : `${p.modality} · ${p.bodyPart}`}
                      </span>
                      {!disabled &&
                        (modelsFor(p).length > 0 ? (
                          <span className="preset-ai has-model">AI: {modelsFor(p).map((m) => m.name).join(", ")}</span>
                        ) : (
                          <span className="preset-ai no-model">No AI model yet: stored for clinician review</span>
                        ))}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        <div className="form-section-title">
          2 · {["ECG", "EEG"].includes(choice.preset.modality) ? "Recording" : "Image"}
        </div>
        <label
          className={`dropzone${dragging ? " dragging" : ""}${file ? " has-file" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            pick(e.dataTransfer.files?.[0] ?? null);
          }}
        >
          <input
            type="file"
            className="visually-hidden"
            accept="image/png,image/jpeg,image/tiff,.tif,.tiff,.dcm,application/dicom,.csv,text/csv,.edf"
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
          />
          {file ? (
            <div className="drop-file">
              {preview ? <img src={preview} alt="Preview of the selected image" /> : <div className="drop-filetype">{fileKind(file)}</div>}
              <div>
                <div className="cell-primary">{fileKind(file)} · {(file.size / 1024 / 1024).toFixed(1)} MB</div>
                <div className="cell-secondary">Ready to send. Click or drop to replace.</div>
              </div>
            </div>
          ) : (
            <div className="drop-empty">
              <Icon.Upload />
              <div className="cell-primary">
                Drop the {{ ECG: "ECG file", EEG: "EEG recording" }[choice.preset.modality] ?? "image"} here, or click to choose
              </div>
            </div>
          )}
          <span className="cell-secondary">
            {choice.preset.modality === "ECG"
              ? "DICOM 12-lead ECG, or a CSV with a header row of lead names (I, II, III, aVR, aVL, aVF, V1–V6) and optional “# fs=500 units=mV” line."
              : choice.preset.modality === "EEG"
                ? "EDF export with 10-20 electrodes (bipolar or referential), up to 50 MB."
                : "PNG, JPEG, TIFF or DICOM, up to 50 MB."}{" "}
            File names are never stored.
          </span>
        </label>

        <div className="form-section-title">3 · Patient</div>
        <div className="form-row">
          <label>
            <span>
              MRN <span className="required">*</span>
            </span>
            <input value={patientMrn} onChange={(e) => setPatientMrn(e.target.value)} maxLength={64} required />
          </label>
          <label>
            Full name
            <input value={patientName} onChange={(e) => setPatientName(e.target.value)} maxLength={200} />
          </label>
        </div>
        <div className="form-row">
          <label>
            Date of birth
            <input type="date" value={patientDob} onChange={(e) => setPatientDob(e.target.value)} />
          </label>
          <label>
            Sex
            <select value={patientSex} onChange={(e) => setPatientSex(e.target.value as typeof patientSex)}>
              <option value="U">Unknown</option>
              <option value="F">Female</option>
              <option value="M">Male</option>
              <option value="O">Other</option>
            </select>
          </label>
        </div>

        <div className="form-section-title">4 · Order (optional)</div>
        <div className="form-row">
          <label>
            Accession number
            <input value={accessionNo} onChange={(e) => setAccessionNo(e.target.value)} maxLength={64} />
          </label>
          <label>
            Study date
            <input type="date" value={studyDate} onChange={(e) => setStudyDate(e.target.value)} />
          </label>
        </div>

        {error && <p className="error-text">{error}</p>}
        <div className="toolbar">
          <button type="submit" disabled={submitting}>
            {submitting ? "Uploading…" : `Submit ${choice.preset.label.toLowerCase()}`}
          </button>
          <span className="cell-secondary">
            Patient identifiers are encrypted at rest. Every AI model deployed for {choice.specialty.name.toLowerCase()} ·{" "}
            {choice.preset.modality}/{choice.preset.bodyPart} runs automatically.
          </span>
        </div>
      </form>
    </div>
  );
}
