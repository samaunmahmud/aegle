// The browser security headers for the web app: the single definition used by the Vite
// dev/preview servers (vite.config.ts) and by the production nginx image
// (scripts/nginx-headers.ts writes them into its config at build time).

/**
 * Only our own scripts and styles, API calls to our origin and Keycloak, images from
 * blob: URLs (study images and heatmaps). The Vite dev server leaves the CSP out
 * because React fast-refresh injects an inline script.
 */
export function contentSecurityPolicy(keycloakOrigin: string): string {
  return [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' blob: data:",
    `connect-src 'self' ${keycloakOrigin}`,
    `frame-src ${keycloakOrigin}`,
    "object-src 'none'",
    "base-uri 'self'",
    `form-action 'self' ${keycloakOrigin}`,
    "frame-ancestors 'none'",
  ].join("; ");
}

export function securityHeaders(keycloakOrigin: string, withCsp: boolean): Record<string, string> {
  const headers: Record<string, string> = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  };
  if (withCsp) {
    headers["Content-Security-Policy"] = contentSecurityPolicy(keycloakOrigin);
    headers["X-Frame-Options"] = "DENY";
  }
  return headers;
}

export function keycloakOrigin(url: string | undefined): string {
  return new URL(url || "https://localhost:8443").origin;
}
