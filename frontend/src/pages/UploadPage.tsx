import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";

export function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [patientMrn, setPatientMrn] = useState("");
  const [patientName, setPatientName] = useState("");
  const [patientDob, setPatientDob] = useState("");
  const [patientSex, setPatientSex] = useState<"F" | "M" | "O" | "U">("U");
  const [modality, setModality] = useState("XR");
  const [bodyPart, setBodyPart] = useState("CHEST");
  const [accessionNo, setAccessionNo] = useState("");
  const [studyDate, setStudyDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file || !patientMrn) {
      setError("A file and patient MRN are required.");
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
        modality,
        bodyPart,
        accessionNo: accessionNo || undefined,
        studyDate: studyDate || undefined,
      });
      navigate(`/studies/${result.studyId}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="narrow">
      <h1>Upload a study</h1>
      <p className="muted">
        The study is queued for inference immediately. Whichever model is
        registered for this modality and body part will run automatically.
      </p>
      <form onSubmit={submit} className="form">
        <label>
          Image file <span className="required">*</span>
          <input
            type="file"
            accept="image/*,.dcm"
            required
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>

        <div className="form-row">
          <label>
            Patient MRN <span className="required">*</span>
            <input value={patientMrn} onChange={(e) => setPatientMrn(e.target.value)} required maxLength={64} />
          </label>
          <label>
            Patient name
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

        <div className="form-row">
          <label>
            Modality
            <select value={modality} onChange={(e) => setModality(e.target.value)}>
              <option value="XR">X-ray</option>
              <option value="CT">CT</option>
              <option value="MR">MRI</option>
            </select>
          </label>
          <label>
            Body part
            <input value={bodyPart} onChange={(e) => setBodyPart(e.target.value)} maxLength={64} list="body-parts" />
            <datalist id="body-parts">
              <option value="CHEST" />
              <option value="BRAIN" />
            </datalist>
          </label>
        </div>

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

        <button type="submit" disabled={submitting}>
          {submitting ? "Uploading…" : "Upload and queue"}
        </button>
      </form>
    </div>
  );
}
