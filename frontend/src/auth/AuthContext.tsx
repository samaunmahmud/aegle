import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { keycloak, roles as parseRoles, displayName, type Role } from "./keycloak";

interface AuthState {
  ready: boolean;
  roles: Role[];
  name: string;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [roles, setRoles] = useState<Role[]>([]);
  const [name, setName] = useState("");

  useEffect(() => {
    let cancelled = false;
    keycloak
      .init({
        onLoad: "login-required",
        pkceMethod: "S256",
        checkLoginIframe: false,
      })
      .then((authenticated) => {
        if (cancelled) return;
        if (!authenticated) {
          keycloak.login();
          return;
        }
        setRoles(parseRoles());
        setName(displayName());
        setReady(true);
      })
      .catch((err) => {
        console.error("Keycloak init failed", err);
      });

    // Keep the token fresh in the background so long-open tabs (e.g. a
    // radiologist reading a worklist for an hour) don't get logged out
    // mid-session.
    const interval = setInterval(() => {
      keycloak.updateToken(60).catch(() => keycloak.login());
    }, 30_000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const value: AuthState = {
    ready,
    roles,
    name,
    logout: () => keycloak.logout({ redirectUri: window.location.origin }),
  };

  if (!ready) {
    return (
      <div className="centered-loader">
        <p>Signing in&hellip;</p>
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
