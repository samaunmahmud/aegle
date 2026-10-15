import { describe, expect, it } from "vitest";
import { contentSecurityPolicy, keycloakOrigin, securityHeaders } from "./security-headers";

describe("contentSecurityPolicy", () => {
  const csp = contentSecurityPolicy("https://auth.example.org");
  const directives = Object.fromEntries(
    csp.split("; ").map((d) => {
      const [name, ...values] = d.split(" ");
      return [name, values];
    }),
  );

  it("allows no inline or third-party scripts", () => {
    expect(directives["script-src"]).toEqual(["'self'"]);
    expect(csp).not.toContain("unsafe-inline");
    expect(csp).not.toContain("unsafe-eval");
  });

  it("lets the app talk only to itself and Keycloak", () => {
    expect(directives["connect-src"]).toEqual(["'self'", "https://auth.example.org"]);
    expect(directives["frame-src"]).toEqual(["https://auth.example.org"]);
  });

  it("forbids plugins and framing", () => {
    expect(directives["object-src"]).toEqual(["'none'"]);
    expect(directives["frame-ancestors"]).toEqual(["'none'"]);
  });
});

describe("securityHeaders", () => {
  it("always sends HSTS, nosniff and no referrer", () => {
    const h = securityHeaders("https://auth.example.org", false);
    expect(h["Strict-Transport-Security"]).toMatch(/max-age=\d+/);
    expect(h["X-Content-Type-Options"]).toBe("nosniff");
    expect(h["Referrer-Policy"]).toBe("no-referrer");
    expect(h["Content-Security-Policy"]).toBeUndefined();
  });

  it("adds the CSP and frame denial when asked", () => {
    const h = securityHeaders("https://auth.example.org", true);
    expect(h["Content-Security-Policy"]).toBe(contentSecurityPolicy("https://auth.example.org"));
    expect(h["X-Frame-Options"]).toBe("DENY");
  });
});

describe("keycloakOrigin", () => {
  it("strips the path from a Keycloak URL", () => {
    expect(keycloakOrigin("https://auth.example.org:8443/realms/aegle")).toBe("https://auth.example.org:8443");
  });

  it("defaults to the local development Keycloak", () => {
    expect(keycloakOrigin(undefined)).toBe("https://localhost:8443");
  });
});
