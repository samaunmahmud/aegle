# Aegle web

React + TypeScript clinician UI: worklist, study upload, study detail
(image + Grad-CAM heatmap + review), and an audit log for admins/auditors.

## Run locally

Core API and Keycloak must already be up (`docker compose up -d` from the
repo root, then `core-api` running with `SPRING_PROFILES_ACTIVE=dev`).

```bash
npm install
cp .env.example .env.local   # defaults already match the dev stack
npm run dev                  # https://localhost:5173 (needs infra/tls/generate.sh first)
```

Sign in with one of the demo users from `infra/keycloak/aegle-realm.json`
(password `dev-only-password` for all of them):

| Username           | Role        |
|--------------------|-------------|
| rita.radiologist   | RADIOLOGIST |
| paul.physician     | PHYSICIAN   |
| alex.auditor       | AUDITOR     |
| ada.admin          | ADMIN (manages DICOM senders; sees no patient data) |
| otto.other         | RADIOLOGIST (different org, for tenant-isolation checks) |

The password (direct access) grant is disabled for `aegle-web`: sign-in only works
through the browser.

Security headers, including the Content-Security-Policy, are defined once in
`security-headers.ts`. `npm run preview` sends them, and the production image
(`Dockerfile`, nginx; see the root README) writes them into its nginx config at
build time.

## How auth works

`keycloak-js` runs the Authorization Code + PKCE flow against the `aegle-web`
public client. The access token's `realm_access.roles` claim drives what's
shown in the nav (e.g. the audit log is RADIOLOGIST/PHYSICIAN-hidden), and is
sent as a bearer token on every API call — the API is the actual authority on
what a role can do, the UI just doesn't show what it knows will be refused.

## API calls

`/api/*` is proxied by Vite (see `vite.config.ts`) to core-api on `:8090`, so
the browser only ever talks to one origin. `src/api/client.ts` wraps `fetch`,
attaches a freshly-refreshed bearer token, and parses the RFC 7807
`ProblemDetail` error bodies core-api returns.

## Demo user IDs

Keycloak runs in `start-dev` mode with no persistent volume for its own store, so it
re-imports `infra/keycloak/aegle-realm.json` on every container start. The realm pins
each demo user's `id`, so their token subject stays the same across restarts and the
`users` rows core-api provisioned on first login keep working. Give any user you add to
the realm a fixed `id` too; otherwise each restart issues a new subject and that login
gets a 403 (core-api refuses a second account for the same email).
