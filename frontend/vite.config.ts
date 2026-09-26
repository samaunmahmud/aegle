import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import https from "node:https";
import path from "node:path";
import { keycloakOrigin, securityHeaders } from "./security-headers.ts";

// Frontend runs on https://localhost:5173 (matches the Keycloak client's redirect URI and
// the core API's CORS config). API calls are proxied to core-api so the browser only
// ever talks to one origin. Everything is TLS, using infra/tls/generate.sh's certificates.
// Production serves dist/ from the nginx image instead (Dockerfile, nginx.conf.template).
const CERTS = path.resolve(import.meta.dirname, "../infra/tls/certs");

function cert(file: string): Buffer {
  try {
    return fs.readFileSync(path.join(CERTS, file));
  } catch {
    throw new Error(`Missing ${path.join(CERTS, file)}: run infra/tls/generate.sh first`);
  }
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const plugins = [react()];
  if (command === "build") {
    return { plugins };   // certificates are only needed to serve
  }

  const keycloak = keycloakOrigin(env.VITE_KEYCLOAK_URL);
  const tls = { key: cert("server.key"), cert: cert("server.crt") };
  const proxy = {
    "/api": {
      target: env.AEGLE_API_URL || "https://localhost:8090",
      changeOrigin: true,
      secure: true,
      agent: new https.Agent({ ca: cert("ca.crt") }),
    },
  };

  return {
    plugins,
    server: { port: 5173, strictPort: true, https: tls, headers: securityHeaders(keycloak, false), proxy },
    preview: { port: 5173, strictPort: true, https: tls, headers: securityHeaders(keycloak, true), proxy },
  };
});
