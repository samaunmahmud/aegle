import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import https from "node:https";
import path from "node:path";

// Frontend runs on https://localhost:5173 (matches the Keycloak client's redirect URI and
// the core API's CORS config). API calls are proxied to core-api so the browser only
// ever talks to one origin. Everything is TLS, using infra/tls/generate.sh's certificates.
const CERTS = path.resolve(import.meta.dirname, "../infra/tls/certs");

function cert(file: string): Buffer {
  try {
    return fs.readFileSync(path.join(CERTS, file));
  } catch {
    throw new Error(`Missing ${path.join(CERTS, file)}: run infra/tls/generate.sh first`);
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const keycloak = new URL(env.VITE_KEYCLOAK_URL || "https://localhost:8443").origin;
  const tls = { key: cert("server.key"), cert: cert("server.crt") };

  const proxy = {
    "/api": {
      target: env.AEGLE_API_URL || "https://localhost:8090",
      changeOrigin: true,
      secure: true,
      agent: new https.Agent({ ca: cert("ca.crt") }),
    },
  };

  const headers = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  };

  // The production bundle's policy: only our own scripts and styles, API calls to our
  // origin and Keycloak, images from blob: URLs (study images and heatmaps). The dev
  // server omits it because React fast-refresh injects an inline script. Whatever serves
  // dist/ in production must send these same headers.
  const csp = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' blob: data:",
    `connect-src 'self' ${keycloak}`,
    `frame-src ${keycloak}`,
    "object-src 'none'",
    "base-uri 'self'",
    `form-action 'self' ${keycloak}`,
    "frame-ancestors 'none'",
  ].join("; ");

  return {
    plugins: [react()],
    server: { port: 5173, strictPort: true, https: tls, headers, proxy },
    preview: {
      port: 5173,
      strictPort: true,
      https: tls,
      headers: { ...headers, "Content-Security-Policy": csp, "X-Frame-Options": "DENY" },
      proxy,
    },
  };
});
