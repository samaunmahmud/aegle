import { useEffect, useRef, useState, type FormEvent } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { clinicalDay, clock } from "../format";
import { Icon } from "./Icons";

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? "tab-link active" : "tab-link";
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

const ROLE_TITLE: Record<string, string> = {
  RADIOLOGIST: "Consultant Radiologist",
  PHYSICIAN: "Physician",
  ADMIN: "System Administrator",
  AUDITOR: "Information Governance",
};

/** Wall clock in the clinical format; clinicians read times off the header, not the OS. */
function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 15_000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="appbar-clock" aria-label="Current date and time">
      <span>{clinicalDay(now)}</span>
      <strong>{clock(now)}</strong>
    </div>
  );
}

/** Find a patient's studies by MRN from anywhere; "/" focuses it, as in most clinical systems. */
function PatientSearch() {
  const navigate = useNavigate();
  const ref = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement;
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) {
        e.preventDefault();
        ref.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function submit(e: FormEvent) {
    e.preventDefault();
    const mrn = q.trim();
    if (mrn) navigate(`/worklist?mrn=${encodeURIComponent(mrn)}`);
  }

  return (
    <form className="appbar-search" role="search" onSubmit={submit}>
      <Icon.Search />
      <input
        ref={ref}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Find patient by MRN"
        aria-label="Find patient by MRN"
        spellCheck={false}
      />
      <kbd>/</kbd>
    </form>
  );
}

export function Layout() {
  const { roles, name, logout } = useAuth();
  const [organisation, setOrganisation] = useState<string | null>(null);
  const clinician = roles.includes("RADIOLOGIST") || roles.includes("PHYSICIAN");
  const canAudit = roles.includes("ADMIN") || roles.includes("AUDITOR");
  const isAdmin = roles.includes("ADMIN");
  const role = roles.find((r) => ROLE_TITLE[r]);

  useEffect(() => {
    api
      .me()
      .then((me) => setOrganisation(me.organisationName))
      .catch(() => setOrganisation(null));
  }, []);

  return (
    <div className="app-shell">
      <header className="appbar">
        <div className="appbar-brand">
          <Icon.Logo />
          <div>
            <div className="brand-name">Aegle</div>
            <div className="brand-sub">Clinical Imaging</div>
          </div>
        </div>
        <div className="appbar-site">
          <div className="site-name">{organisation ?? "—"}</div>
          <div className="site-dept">Imaging &amp; Diagnostics</div>
        </div>
        {clinician && <PatientSearch />}
        <div className="appbar-spacer" />
        <span
          className="env-chip"
          title="AI output is decision support only. Not a medical device; not for clinical use."
        >
          Research prototype
        </span>
        <Clock />
        <div className="appbar-user">
          <div className="avatar" aria-hidden="true">
            {initials(name)}
          </div>
          <div className="who">
            <div className="who-name">{name}</div>
            <div className="who-role">{role ? ROLE_TITLE[role] : roles.join(", ").toLowerCase()}</div>
          </div>
          <button className="icon-button" onClick={logout} title="Sign out" aria-label="Sign out">
            <Icon.SignOut />
          </button>
        </div>
      </header>

      <nav className="tabbar" aria-label="Main navigation">
        {clinician && (
          <>
            <NavLink to="/overview" className={navClass}>
              <Icon.Overview /> Department
            </NavLink>
            <NavLink to="/worklist" className={navClass}>
              <Icon.Worklist /> Reporting worklist
            </NavLink>
            <NavLink to="/upload" className={navClass}>
              <Icon.Upload /> New study
            </NavLink>
          </>
        )}
        <NavLink to="/models" className={navClass}>
          <Icon.Models /> AI models
        </NavLink>
        {canAudit && (
          <NavLink to="/audit" className={navClass}>
            <Icon.Audit /> Audit log
          </NavLink>
        )}
        {isAdmin && (
          <NavLink to="/admin/dicom" className={navClass}>
            <Icon.Network /> DICOM senders
          </NavLink>
        )}
      </nav>

      <div className="main">
        <main className="content">
          <Outlet />
        </main>
        <footer className="footer">
          <span>Aegle suggests; the clinician decides. Every AI finding is reviewed and signed by a qualified clinician.</span>
          <span>All access is audited.</span>
        </footer>
      </div>
    </div>
  );
}
