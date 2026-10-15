import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Separate from vite.config.ts, whose dev server needs the local TLS certificates.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}", "*.test.ts"],
    exclude: ["**/node_modules/**", "**/._*"],
  },
});
