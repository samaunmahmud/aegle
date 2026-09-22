import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Frontend runs on :5173 (matches the Keycloak client's redirect URI and
// the core API's CORS config). API calls are proxied to core-api so the
// browser only ever talks to one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8090",
        changeOrigin: true,
      },
    },
  },
});
