# Aegle web

React + TypeScript clinician UI: worklist, study upload, study detail
(image + Grad-CAM heatmap + review), and an audit log for admins/auditors.

## Run locally

Core API and Keycloak must already be up (`docker compose up -d` from the
repo root, then `core-api` running with `SPRING_PROFILES_ACTIVE=dev`).

```bash
npm install
cp .env.example .env.local   # defaults already match the dev stack
npm run dev                  # http://localhost:5173
```

Sign in with one of the demo users from `infra/keycloak/aegle-realm.json`
(password `dev-only-password` for all of them):

| Username           | Role        |
|--------------------|-------------|
| rita.radiologist   | RADIOLOGIST |
| paul.physician     | PHYSICIAN   |
| alex.auditor       | AUDITOR     |
| otto.other         | RADIOLOGIST (different org, for tenant-isolation checks) |

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

## Known dev-environment gotcha

Keycloak runs in `start-dev` mode with no persistent volume for its own
store, so **restarting the `keycloak` container reissues new internal user
IDs** for the demo users even though the realm JSON looks identical. If a
demo login that used to work suddenly gets a 403 from core-api after a
`docker compose restart`/`up` cycle, that's why: core-api provisions a user
row keyed by Keycloak's subject claim on first login, and the old row (same
email, different subject) is still there. Fix locally with `docker compose
down -v` (wipes all local dev data), or, when you want to keep local test
data, re-point the row by hand: update the `users.idp_subject` for that email
to the new token's `sub`.
