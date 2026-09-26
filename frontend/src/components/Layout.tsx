import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { SPECIALTIES } from "../specialties";
import { Icon, SpecialtyIcon } from "./Icons";

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? "nav-link active" : "nav-link";
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

export function Layout() {
  const { roles, name, logout } = useAuth();
  const [organisation, setOrganisation] = useState<string | null>(null);
  const clinician = roles.includes("RADIOLOGIST") || roles.includes("PHYSICIAN");
  const canAudit = roles.includes("ADMIN") || roles.includes("AUDITOR");
  const isAdmin = roles.includes("ADMIN");

  useEffect(() => {
    api
      .me()
      .then((me) => setOrganisation(me.organisationName))
      .catch(() => setOrganisation(null));
  }, []);

  return (
    <div className="app-shell">
      <div className="env-banner" role="note">
        Research prototype · AI output is decision support only · Not for clinical use
      </div>

      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand">
          <Icon.Logo />
          <div>
            <div className="brand-name">Aegle</div>
            <div className="brand-org">{organisation ?? "Clinical decision support"}</div>
          </div>
        </div>

        {clinician && (
          <nav className="nav-section" aria-label="Clinical">
            <div className="nav-heading">Clinical</div>
            <NavLink to="/worklist" end className={navClass}>
              <Icon.Worklist /> All worklists
            </NavLink>
            <NavLink to="/upload" className={navClass}>
              <Icon.Upload /> New study
            </NavLink>
          </nav>
        )}

        {clinician && (
          <nav className="nav-section" aria-label="Specialties">
            <div className="nav-heading">Specialties</div>
            {SPECIALTIES.map((s) => (
              <NavLink key={s.id} to={`/worklist/${s.slug}`} className={navClass}>
                <SpecialtyIcon specialty={s.id} /> {s.name}
              </NavLink>
            ))}
          </nav>
        )}

        <nav className="nav-section" aria-label="Governance">
          <div className="nav-heading">Governance</div>
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

        <div className="sidebar-footer">
          <div className="avatar" aria-hidden="true">
            {initials(name)}
          </div>
          <div className="who">
            <div className="who-name">{name}</div>
            <div className="who-roles">{roles.map((r) => r.toLowerCase()).join(", ")}</div>
          </div>
          <button className="icon-button" onClick={logout} title="Sign out" aria-label="Sign out">
            <Icon.SignOut />
          </button>
        </div>
      </aside>

      <div className="main">
        <main className="content">
          <Outlet />
        </main>
        <footer className="footer">
          Aegle suggests; the clinician decides. Every AI finding must be reviewed by a qualified clinician. All access
          is audited.
        </footer>
      </div>
    </div>
  );
}
