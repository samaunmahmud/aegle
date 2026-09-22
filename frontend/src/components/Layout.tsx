import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { roles, name, logout } = useAuth();
  const canAudit = roles.includes("ADMIN") || roles.includes("AUDITOR");

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          Aegle <span className="brand-tag">clinical decision support</span>
        </div>
        <nav className="topnav">
          <NavLink to="/worklist" className={({ isActive }) => (isActive ? "active" : "")}>
            Worklist
          </NavLink>
          <NavLink to="/upload" className={({ isActive }) => (isActive ? "active" : "")}>
            Upload study
          </NavLink>
          {canAudit && (
            <NavLink to="/audit" className={({ isActive }) => (isActive ? "active" : "")}>
              Audit log
            </NavLink>
          )}
        </nav>
        <div className="who">
          <span className="who-name">{name}</span>
          <span className="who-roles">{roles.join(", ")}</span>
          <button className="link-button" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
      <footer className="footer">
        Aegle suggests; the clinician decides. Not a medical device. Not for
        clinical use.
      </footer>
    </div>
  );
}
