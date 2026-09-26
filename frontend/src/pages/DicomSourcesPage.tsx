import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { DicomSource } from "../api/types";

// Mirrors the server's rule: 1-16 printable ASCII characters, no leading/trailing space.
const AE_TITLE = /^[!-~]([ -~]{0,14}[!-~])?$/;

export function DicomSourcesPage() {
  const [sources, setSources] = useState<DicomSource[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aeTitle, setAeTitle] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  function message(e: unknown, fallback: string) {
    return e instanceof ApiError ? e.message : fallback;
  }

  useEffect(() => {
    api
      .dicomSources()
      .then(setSources)
      .catch((e) => setError(message(e, "Failed to load DICOM senders")));
  }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const created = await api.addDicomSource(aeTitle, description.trim());
      setSources((prev) => [...(prev ?? []), created].sort((a, b) => a.aeTitle.localeCompare(b.aeTitle)));
      setAeTitle("");
      setDescription("");
    } catch (err) {
      setError(message(err, "Could not register the sender"));
    } finally {
      setSaving(false);
    }
  }

  async function remove(s: DicomSource) {
    if (!window.confirm(`Stop accepting studies from ${s.aeTitle}?`)) return;
    setError(null);
    try {
      await api.removeDicomSource(s.aeTitle);
      setSources((prev) => (prev ?? []).filter((x) => x.aeTitle !== s.aeTitle));
    } catch (err) {
      setError(message(err, "Could not remove the sender"));
    }
  }

  const titleValid = AE_TITLE.test(aeTitle);

  return (
    <div>
      <h1>DICOM senders</h1>
      <p className="muted">
        Modalities and PACS whose studies come into this organisation. Aegle matches each study by the
        sender's calling AE title; studies from titles not listed here are not imported. Senders also
        need a TLS client certificate from your administrator.
      </p>
      {error && <p className="error-text">{error}</p>}

      {sources === null ? (
        <p>Loading&hellip;</p>
      ) : sources.length === 0 ? (
        <p className="muted">No senders registered yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>AE title</th>
              <th>Description</th>
              <th>Registered</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.aeTitle}>
                <td>
                  <code>{s.aeTitle}</code>
                </td>
                <td>{s.description ?? "—"}</td>
                <td>{new Date(s.createdAt).toLocaleString()}</td>
                <td>
                  <button className="link-button" onClick={() => remove(s)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form className="form" onSubmit={add}>
        <h2>Register a sender</h2>
        <div className="form-row">
          <label>
            Calling AE title
            <input
              value={aeTitle}
              onChange={(e) => setAeTitle(e.target.value)}
              maxLength={16}
              placeholder="e.g. CR_ROOM_2"
              required
            />
          </label>
          <label>
            Description (optional)
            <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={200} />
          </label>
        </div>
        {aeTitle && !titleValid && (
          <p className="error-text">An AE title is 1–16 printable characters with no leading or trailing space.</p>
        )}
        <div>
          <button type="submit" disabled={saving || !titleValid}>
            {saving ? "Registering…" : "Register sender"}
          </button>
        </div>
      </form>
    </div>
  );
}
