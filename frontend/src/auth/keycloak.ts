import Keycloak from "keycloak-js";

// Config matches infra/keycloak/aegle-realm.json's "aegle-web" public client.
export const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL ?? "http://localhost:8080",
  realm: import.meta.env.VITE_KEYCLOAK_REALM ?? "aegle",
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "aegle-web",
});

/** Roles the API and UI both understand (see SecurityConfig / aegle-realm.json). */
export type Role = "ADMIN" | "RADIOLOGIST" | "PHYSICIAN" | "AUDITOR";

export function roles(): Role[] {
  const realmAccess = keycloak.tokenParsed?.realm_access as { roles?: string[] } | undefined;
  return (realmAccess?.roles ?? []) as Role[];
}

export function hasRole(...allowed: Role[]): boolean {
  const mine = roles();
  return allowed.some((r) => mine.includes(r));
}

export function displayName(): string {
  const t = keycloak.tokenParsed as { name?: string; preferred_username?: string } | undefined;
  return t?.name ?? t?.preferred_username ?? "Unknown";
}

/**
 * Returns a valid bearer token, refreshing it first if it's within 30s of
 * expiry. Every API call should route through this rather than reading
 * keycloak.token directly, since that can be stale.
 */
export async function freshToken(): Promise<string> {
  try {
    await keycloak.updateToken(30);
  } catch {
    // Refresh token is gone or expired: only a fresh login can recover.
    await keycloak.login();
  }
  if (!keycloak.token) {
    throw new Error("Not authenticated");
  }
  return keycloak.token;
}
