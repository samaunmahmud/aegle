# Aegle web

React + TypeScript clinician UI: department overview, reporting worklist, study upload,
a reading-room study view (image viewer + Grad-CAM + signed review), the AI model
registry, and an audit log for admins/auditors. The Keycloak sign-in pages use a matching
theme (`infra/keycloak/themes/aegle`).

## Design

Modelled on hospital systems (EHR, RIS/PACS) rather than a SaaS dashboard:

- **Application bar** like an EHR: organisation and department, patient search by MRN
  (`/` focuses it), a 24-hour clock, the signed-in clinician and role, and a permanent
  research-prototype marker.
- **Patient banner** after the NHS Common User Interface layout: `FAMILY, Given`, date of
  birth with age, gender and MRN, always above the image. Dates are `15-Oct-2026` and
  times 24-hour everywhere (`src/format.ts`), so `03/04` can never be misread.
- **Reporting worklist** like a RIS: department rail with live counts, one-click
  critical/urgent/overdue filters, sortable columns, keyboard reading (up/down, Enter).
- **Triage is never colour alone**: every priority shows a code and a word (`P1 Critical`),
  which also works in greyscale and for colour-blind readers.
- **AI output is always marked** with the violet `AI` tag and stays a suggestion until a
  clinician signs a review (Agree / Amend / Disagree). Reviews cannot be signed from the
  keyboard, so a stray key cannot record a clinical decision.
- **Reading room**: images are read on a dark surface with PACS-style tools: wheel zoom
  about the cursor, drag to pan, brightness/contrast, invert, AI overlay with opacity,
  DICOM-style corner text, and shortcuts (`?` lists them).
- **Illustrations, not patient images**, on the overview and sign-in pages
  (`src/components/MedicalArt.tsx`, drawn procedurally). The repository holds no imaging
  data, and the app never loads a patient's image the clinician has not opened: every
  image view is written to the audit log. `npx vite-node scripts/render-art.tsx`
  regenerates the sign-in artwork from the same components.
- **Live AI pipeline**: a study opened after upload (drag and drop onto the form) shows
  Received → Queued → AI analysing → Ready with a running clock, and its findings and
  heatmap appear as soon as the model finishes, without a reload.
- **Critical results**: one shared poll of the department summary (reads are audited, so
  pages share it) feeds the bell, the tab title (`(6) Aegle`) and alerts for new P1
  findings, which stay until acknowledged.
- **Explainable triage**: "Why this priority?" shows the stored breakdown, each label's
  probability × urgency weight plus the waiting bonus, so a clinician can see, and
  question, why a case sits where it does.
- **Model evidence**: each model card opens its held-out confusion matrix, per-class
  sensitivity/precision and the gap above the image-statistics shortcut baseline.
- **Prior comparison**: earlier studies of the same examination open side by side; their
  images load only when asked for, since each view is audited.
- **Command palette** (`⌘K` / `Ctrl+K`): jump to any page or department, or find a
  patient by MRN.
- **Consults** (right-hand dock on every clinical page): a clinician unsure about a case
  asks a named colleague, filtered by department or "consultants only", or anyone on duty,
  and the thread stays linked to the study. The dock minimises to a rail that still shows
  what is waiting for you, opens to a panel, or maximises. Threads carry a link to the
  study, never the patient's identifiers; opening a thread, replying and resolving are
  audited, while polling for new messages and the unread count are not, so an open panel
  does not flood the audit log. "Ask a colleague" on a study pre-fills the question.
- **Clinician profiles**: grade (Consultant, Registrar, Foundation), job title and
  picture beside every message, so a junior can see who is answering. The pictures in
  `public/avatars` are illustrations of fictional people, generated for this demo with
  Figma AI; anyone without one gets initials.
- **Lights off**: a whole-application dark theme (moon icon, or the command palette) for
  reading rooms, where low ambient light helps reading accuracy and reduces fatigue. It has
  its own colour steps, checked for contrast, not an inverted light theme; the choice is
  remembered per device and follows the system setting until one is made.
- **Workload chart** on the overview: open studies per department split by AI priority,
  built from the same summary as the counts, so it adds no patient-level reads.
- **Strict CSP kept**: fonts (IBM Plex) are bundled and animation CSS is a stylesheet,
  so `style-src 'self'` needs no exceptions. Animations stop under
  `prefers-reduced-motion`.

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

The demo clinic has twelve clinicians (password `dev-only-password`), from consultants
such as `amara.okafor` (neuroradiology), `kwame.asante` (thoracic radiology),
`hannah.clarke` (histopathology) and `priya.raman` (dermatology), to `tomasz.nowak`
(registrar) and `sofia.rossi` (foundation doctor). Their grade, title and picture are set
in the dev seed (`core-api/src/main/resources/db/dev/R__dev_seed.sql`), not the token.
