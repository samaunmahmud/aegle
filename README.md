<p align="center">
  <img src="docs/screenshots/hero.webp" alt="Aegle: the reporting worklist with critical malaria cases at the top, a brain MRI with the AI heatmap on a phone, and a consult between two doctors" width="100%" />
</p>

<h1 align="center">Aegle: so the most urgent scan is read first</h1>

<p align="center">
  A clinical decision-support platform for hospital departments.<br>
  Eleven AI models read incoming scans, blood smears, ECGs and EEGs across seven specialties, push the urgent ones to the top of the doctor's worklist, and show <i>why</i>.<br>
  The AI suggests. A clinician decides, and signs every finding.
</p>

<p align="center">
  <a href="https://github.com/samaunmahmud/aegle/actions/workflows/ci.yml"><img src="https://github.com/samaunmahmud/aegle/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/status-research_prototype-c0271c?style=flat-square" alt="Status: research prototype" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Java_17-ED8B00?style=flat-square&logo=openjdk&logoColor=white" alt="Java 17" />
  <img src="https://img.shields.io/badge/Spring_Boot-3.5-6DB33F?style=flat-square&logo=springboot&logoColor=white" alt="Spring Boot 3.5" />
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white" alt="PyTorch" />
  <img src="https://img.shields.io/badge/React_18-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React 18" />
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/PostgreSQL_16-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL 16" />
  <img src="https://img.shields.io/badge/Keycloak-4D4D4D?style=flat-square&logo=keycloak&logoColor=white" alt="Keycloak" />
  <img src="https://img.shields.io/badge/DICOM_·_Orthanc-1F6FB2?style=flat-square" alt="DICOM and Orthanc" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker" />
</p>

> [!WARNING]
> **Research prototype. Not a medical device and not for clinical use.** The models were trained on public research datasets and have not been validated in a hospital. Every patient in the screenshots is fictional; the medical images come from public, de-identified research datasets ([credits](#data-and-image-credits)).

<p align="center"><b><i>Every minute a critical scan sits at the bottom of a pile is a minute a patient waits for treatment.<br>Aegle exists to move that scan to the top, and to show the doctor why it's there.</i></b></p>

---

## The 60-second version

- **What it is:** a web app a hospital department runs on its own servers. Scans arrive from the scanners (DICOM) or by upload, an AI model reads each one in seconds, and the case lands on a **worklist ranked by urgency** instead of arrival time.
- **Who it's for:** radiologists, pathologists, cardiologists and other doctors who read images and recordings, the juniors who need a second opinion, and the governance teams who must prove who saw what.
- **What makes it different:** the AI is never a black box and never has the last word. Every ranking can be explained, every model shows where it fails, every finding needs a clinician's signature, and every read of patient data is written to a tamper-evident audit log.
- **What it's built from:** a Spring Boot API, a Python/PyTorch inference service, a React front end, PostgreSQL with row-level security, Keycloak for sign-in, Orthanc for DICOM, MinIO for images, TLS on every connection, and 150+ automated tests in CI.

## Contents

- [The problem](#the-problem)
- [What Aegle does](#what-aegle-does)
- [Who it helps](#who-it-helps)
- [Results in numbers](#results-in-numbers)
- [A tour of the app](#a-tour-of-the-app)
- [How it works](#how-it-works)
- [The AI models](#the-ai-models)
- [Security and privacy](#security-and-privacy)
- [How the project was planned](#how-the-project-was-planned)
- [Design decisions](#design-decisions)
- [Getting started](#getting-started)
- [Tests](#tests)
- [Project structure](#project-structure)
- [Limitations](#limitations)
- [What's next](#whats-next)
- [Data and image credits](#data-and-image-credits)

---

## The problem

Hospitals produce far more scans, slides and recordings than their specialists can read the moment they arrive. Most departments read them roughly in the order they came in. That creates three problems:

1. **The urgent case waits behind the routine ones.** A chest X-ray showing pneumonia, or a blood smear full of malaria parasites, looks exactly like every other item in the queue until someone opens it.
2. **"AI" tools often make it worse, not better.** A score with no explanation is hard to trust, a model that is quietly wrong on some patients is dangerous, and a tool that decides on its own takes responsibility away from the clinician.
3. **Doctors work alone at the moment they most need a colleague.** A junior who is unsure about a scan has to phone around or walk to another floor, and the conversation is lost the moment it ends.

**Aegle puts the most urgent work first, explains every decision it makes, keeps the doctor in charge, and puts a senior colleague one click away.**

## What Aegle does

1. **A scan arrives.** From a scanner over DICOM (mutual TLS), or dragged into the browser. Patient identifiers are encrypted the moment they are stored.
2. **The right AI model reads it.** Each model is registered for a modality and body part, so a chest X-ray goes to the pneumonia model and a blood smear to the malaria model. It returns probabilities, a heatmap of where it looked, and the exact model version and weights hash.
3. **It joins the worklist by urgency.** A priority score built from *probability × clinical urgency + time waiting* ranks the case. Critical findings raise an alert that stays until someone acknowledges it.
4. **A clinician reads it in a reading-room viewer.** Zoom, pan, contrast, invert, the AI overlay, comparison with the patient's earlier scans, and a "why this priority?" breakdown.
5. **Unsure? Ask a colleague.** A consult panel on every page sends the question to a named consultant or anyone on duty, linked to the study.
6. **The clinician signs.** Agree, amend or disagree. The AI's output only becomes part of the record once a clinician has signed it, and every step is in the audit log.

## Who it helps

| | |
|---|---|
| 🩻 **Reporting doctors** | One worklist for the whole department, critical cases first, the reason for each ranking one hover away, and the tools of a PACS workstation in the browser. |
| 🧑‍⚕️ **Junior doctors** | A safety net: the AI flags what looks urgent, and a consultant can be asked about the exact case without leaving the screen. |
| 🏥 **Department leads** | A live view of open, critical, urgent and overdue work per specialty, so staff can be moved to where the queue is growing. |
| 🛡️ **Governance and audit** | Every read and every decision is recorded in a hash-chained log that shows if anyone rewrote history. Each hospital can switch any model off. |
| 🧑‍🤝‍🧑 **Patients** | The scan that matters most is looked at sooner, by a doctor who can see what the AI saw and decide for themselves. |
| 🌍 **Under-resourced settings** | Malaria on blood smears, diabetic eye disease and pneumonia are exactly the readings where specialists are scarcest. The same platform takes a new model without new code in the rest of the system. |

## Results in numbers

| | |
|---|---|
| **AI models live** | **11 models across 7 specialties**: radiology, cardiology, dermatology, ophthalmology, pathology, gastroenterology and neurology |
| **Held-out evaluation** | about **20,600 test cases** (images and ECGs) plus **32 hours of EEG**, all from patients the models never trained on |
| **Best results** | malaria cells **AUC 0.997**, colonoscopy **0.995**, colorectal tissue **0.994**, brain MRI tumour type **0.992**, chest X-ray **0.974** |
| **Honesty checks** | every image model is compared with a "shortcut" model that sees only image size and colour; **2 models were withdrawn** after failing their checks |
| **Speed** | a study goes from upload to AI finding on the worklist in **a few seconds** on a laptop CPU |
| **Tests** | **73 backend** (JUnit with a real Postgres in Testcontainers), **40 inference** (pytest), **40 frontend** (Vitest), run by GitHub Actions on every push |
| **Code** | about **3,200 lines of Java**, **4,200 of Python** and **5,700 of TypeScript**; 8 database migrations |
| **Security** | TLS on every connection, mutual TLS for DICOM, row-level security per hospital, encrypted patient identifiers, a hash-chained audit log, rate limits and a strict Content Security Policy |

---

## A tour of the app

Every screenshot below is the real application running locally, signed in as one of the demo clinicians. The patients are fictional. Click any image to see it at full resolution.

### 1. Signing in

Hospital staff sign in through Keycloak with a branded page. Single sign-on, multi-factor authentication and account policies live in the identity provider, not in the app.

![Sign-in page: a secure clinical sign-in form next to illustrations of each specialty's imaging](docs/screenshots/signin.webp)

### 2. The department at a glance

The first screen after sign-in: open, critical, urgent and overdue work across the department, a workload chart by specialty, and a card per department. All of it comes from **one shared, audited summary request**, so no patient-level data is read just to draw a dashboard.

![Department overview: totals, a workload chart by department and a card per specialty with live counts](docs/screenshots/overview.webp)

The workload chart puts departments with critical findings first and keeps every bar on one scale:

![Workload by department: critical, urgent and other open studies per specialty, with overdue counts](docs/screenshots/workload.webp)

### 3. The reporting worklist

Cases ranked by AI-assessed urgency and time waiting, not arrival order. Every priority shows a code and a word (`P1 Critical`), so it never relies on colour alone. A department rail, one-click filters, sorting, and keyboard reading (↑ ↓ Enter) make it work like a radiology information system.

![Reporting worklist: critical malaria cases at the top, then urgent brain MRIs, with AI findings, waiting time and report deadlines](docs/screenshots/worklist.webp)

**"Why this priority?"** The score is never a black box: hover the ⓘ to see each label's probability × its urgency weight, plus a bonus for time waiting.

![The priority breakdown: 98.5% parasitized × urgency weight 100, plus 20 points for time waiting, gives 118.7](docs/screenshots/priority-why.webp)

**Critical cases only:** one click narrows the list to P1 findings.

![Worklist filtered to critical cases](docs/screenshots/worklist-critical.webp)

### 4. Reading a study

A dark reading-room viewer with PACS-style tools: wheel zoom about the cursor, drag to pan, brightness and contrast, invert, and the AI heatmap with adjustable opacity. The patient banner follows the NHS Common User Interface layout, so identity is always above the image, and the pipeline strip shows where the study is.

![Brain MRI with the AI heatmap over a tumour, the model's finding (glioma 99.9%) and the Agree / Amend / Disagree review panel](docs/screenshots/study-brain.webp)

`?` lists the viewer's shortcuts. Reviews can never be signed from the keyboard, so a stray key cannot record a clinical decision.

![Chest X-ray with the viewer shortcut card open](docs/screenshots/viewer-shortcuts.webp)

### 5. Every department, one platform

The same worklist, viewer and review flow for every specialty. Only the model behind it changes.

**Radiology: chest X-ray, pneumonia**
![Chest X-ray with the pneumonia heatmap](docs/screenshots/study-chest.webp)

**Pathology: malaria on a blood smear** (a P1 critical finding)
![A blood-smear cell flagged as parasitized, P1 critical](docs/screenshots/study-malaria.webp)

**Pathology: colorectal tissue**
![An H&E tissue tile classified as tumour epithelium](docs/screenshots/study-tissue.webp)

**Pathology: prostate Gleason pattern**
![A prostate biopsy patch graded Gleason 3, with a prior to compare](docs/screenshots/study-prostate.webp)

**Gastroenterology: colonoscopy**
![A colonoscopy frame with a polyp highlighted](docs/screenshots/study-colonoscopy.webp)

**Ophthalmology: diabetic retinopathy**
![A retinal photograph graded moderate diabetic retinopathy](docs/screenshots/study-fundus.webp)

**Dermatology: skin lesion**
![A dermoscopy image classified as basal cell carcinoma](docs/screenshots/study-skin.webp)

**Cardiology: 12-lead ECG**
![A 12-lead ECG read as atrial fibrillation](docs/screenshots/study-ecg.webp)

**Neurology: EEG seizure detection**
![An EEG recording with the AI's seizure timeline](docs/screenshots/study-eeg.webp)

### 6. The clinician decides

The AI's output stays a suggestion until a clinician chooses **Agree**, **Amend** (with the correct label) or **Disagree**, adds a comment and signs. Each finding also explains its priority, the model's intended use and limits, and the exact weights it ran with.

| The finding, explained | Signing a review |
| :---: | :---: |
| <img src="docs/screenshots/study-explained.webp" alt="The finding with its priority breakdown and what the model can and cannot do" width="400" /> | <img src="docs/screenshots/review.webp" alt="Agree selected with a comment, ready to sign" width="400" /> |

Once signed, the review history shows who decided what, and when:

![A chest X-ray whose AI finding has been accepted by a consultant](docs/screenshots/reviewed.webp)

### 7. Comparing with earlier scans

Earlier studies of the same examination for the same patient appear as chips above the viewer. **Compare** opens the prior side by side, with every tool working on both. Priors are looked up on the server, and a prior's image only loads when asked for, because every image view is audited.

![A chest X-ray from 16 October next to the same patient's film from 15 October](docs/screenshots/compare.webp)

### 8. New study, live AI, critical alert

Drag a file onto the form, pick the examination and enter the patient:

![The new-study form with a blood-smear image dropped in](docs/screenshots/upload.webp)

The study page then follows the pipeline live (**Received → Queued → AI analysing → Ready**):

![The study page while the AI is still queued](docs/screenshots/pipeline.webp)

…and the finding and heatmap appear the moment the model finishes, without a reload:

![The same study with the AI finding: parasitized, P1 critical](docs/screenshots/pipeline-done.webp)

When a new P1 finding lands, an alert appears that **stays until someone acknowledges it**, as critical results must. The bell and the browser tab title count them too.

<p align="center">
  <img src="docs/screenshots/critical-alert.webp" alt="A critical-finding alert with Open worklist and Acknowledge" width="760" />
</p>
<p align="center">
  <img src="docs/screenshots/bell.webp" alt="The bell's panel: critical findings awaiting a report, by department" width="580" />
</p>

### 9. Consults: ask a colleague

A consult panel lives on the right of every clinical page. A doctor who is unsure asks **a named colleague** (filter by department, or "consultants only") or **anyone on duty**, marks it urgent if it is, and links the study on screen. Every message shows the sender's picture and grade, so a junior can see who is answering. The panel minimises to a slim rail that still shows what is waiting for you, opens to a side panel, or maximises.

The thread carries **a link to the study, never the patient's details**. Opening a thread, replying and resolving are audited; the background refresh is not, so an open panel doesn't flood the audit log.

![The worklist with the consult panel open](docs/screenshots/consults.webp)

| Consults waiting | A conversation |
| :---: | :---: |
| <img src="docs/screenshots/consult-list.webp" alt="The consult list: urgency, department and study chips, who asked whom, unread counts" width="400" /> | <img src="docs/screenshots/consult-thread.webp" alt="A consult thread between a histopathologist and a radiologist about a malaria smear" width="400" /> |
| **Asking a colleague** | **The same panel, Lights off** |
| <img src="docs/screenshots/consult-new.webp" alt="The new-consult form with colleagues listed by grade" width="400" /> | <img src="docs/screenshots/consult-thread-dark.webp" alt="A consult thread in the dark theme" width="400" /> |

Maximised, the panel gives a long discussion room to breathe:

![The consult panel maximised: a cardiologist asking about a post-operative chest X-ray](docs/screenshots/consult-max.webp)

### 10. The AI model registry, with the evidence

Every model's held-out results, training data and licence, intended use and known limits, approval date and weights hash.

![The AI model registry: held-out accuracy, AUC and calibration error, training data and intended use](docs/screenshots/models.webp)

Each card opens the evidence as charts: a confusion matrix you can hover, sensitivity and precision per class, and the model against the "shortcut" baseline. Weaknesses are shown, not hidden: the skin model, for example, misses about a third of melanomas.

![Performance charts for the retinopathy model: confusion matrix, per-class sensitivity and precision, and the shortcut baseline](docs/screenshots/model-performance.webp)

### 11. Command palette

`⌘K` / `Ctrl+K` jumps to any page or department, switches the theme, or finds a patient by MRN.

<p align="center">
  <img src="docs/screenshots/palette.webp" alt="The command palette finding a patient by MRN" width="668" />
</p>

### 12. Governance: audit log and DICOM senders

Auditors see every read and write of patient data, newest first, and can **verify the hash chain** in one click. They can see the model registry, but never patient images.

![The audit log with the chain verified intact](docs/screenshots/audit.webp)

Administrators register the scanners (DICOM AE titles) whose studies flow in:

![The DICOM senders page with a registered CR room](docs/screenshots/dicom.webp)

### 13. Lights off

Reading rooms are kept dim because low ambient light helps reading accuracy and reduces fatigue. One click (or the command palette) switches the whole application to a dark theme with its own contrast-checked colours, not an inverted light theme.

![Department overview, dark](docs/screenshots/overview-dark.webp)

![Reporting worklist, dark](docs/screenshots/worklist-dark.webp)

![Reporting worklist with the consult panel, dark](docs/screenshots/consults-dark.webp)

![Brain MRI study, dark](docs/screenshots/study-brain-dark.webp)

### 14. On a phone

The same app on a phone: the consult panel becomes a floating button and opens full screen, and nothing scrolls sideways.

<p align="center">
  <img src="docs/screenshots/phone-overview.webp" width="270" alt="Department overview on a phone" />
  <img src="docs/screenshots/phone-worklist.webp" width="270" alt="Worklist on a phone" />
  <img src="docs/screenshots/phone-study.webp" width="270" alt="Brain MRI study on a phone" />
</p>
<p align="center">
  <img src="docs/screenshots/phone-consult.webp" width="270" alt="A consult on a phone" />
  <img src="docs/screenshots/phone-overview-dark.webp" width="270" alt="Department overview on a phone, dark" />
  <img src="docs/screenshots/phone-study-dark.webp" width="270" alt="Brain MRI study on a phone, dark" />
</p>
<p align="center">
  <img src="docs/screenshots/phone-worklist-dark.webp" width="270" alt="Worklist on a phone, dark" />
  <img src="docs/screenshots/phone-consult-dark.webp" width="270" alt="A consult on a phone, dark" />
</p>

---

## How it works

### In plain English

Think of Aegle as a hospital department's **sorting office with a very fast first reader**:

- **The front door (Keycloak)** checks who you are and what you're allowed to do: a radiologist can read and sign, an auditor can only read the log.
- **The post room (Orthanc and the upload form)** receives scans. Scanners speak DICOM, the hospital imaging standard; people can also drag a file in.
- **The filing clerk (core API)** files each scan under the right hospital, locks the patient's name and number in an encrypted drawer, and passes the scan to the readers.
- **The first readers (inference service)** are the AI models. Each one only reads the kind of scan it was trained for, and writes down how sure it is and where it looked.
- **The in-tray (worklist)** puts the most urgent case on top and keeps it there until a doctor signs it off.
- **The logbook (audit log)** records every time anyone opens anything, chained together so a removed page would be noticed.

### The architecture

```mermaid
flowchart LR
    subgraph Hospital["Hospital network"]
        Scanner["Scanners / PACS<br/>(DICOM over mutual TLS)"]
        Browser["Clinician's browser<br/>React + TypeScript"]
    end

    subgraph Aegle["Aegle (runs on the hospital's servers)"]
        Web["nginx<br/>static app, CSP, /api proxy"]
        KC["Keycloak<br/>sign-in, roles, MFA"]
        API["Core API<br/>Spring Boot 3.5 · Java 17"]
        Inf["Inference service<br/>FastAPI · PyTorch"]
        Orthanc["Orthanc<br/>DICOM server"]
        DB[("PostgreSQL 16<br/>row-level security<br/>audit hash chain")]
        S3[("MinIO / S3<br/>images, heatmaps")]
    end

    Browser -- "HTTPS + OIDC token" --> Web --> API
    Browser -- "sign in (PKCE)" --> KC
    API -- "verifies JWT" --> KC
    Scanner -- "C-STORE" --> Orthanc
    API -- "follows change log" --> Orthanc
    API -- "TLS, verify-full" --> DB
    API -- "TLS" --> S3
    API -- "TLS + service token" --> Inf
```

| Part | What it does | Built with |
|---|---|---|
| **Front end** | Worklist, reading-room viewer, upload, consults, model registry, audit log | React 18, TypeScript, Vite, keycloak-js, Vitest |
| **Core API** | Patients, studies, worklist, triage, reviews, consults, audit, DICOM import, model registry | Spring Boot 3.5, Java 17, JdbcClient, Flyway, Spring Security (OAuth2 resource server) |
| **Inference service** | One adapter per model: pre-processing, inference, calibration, Grad-CAM heatmaps, measurements | FastAPI, PyTorch, torchvision, pydicom |
| **Database** | Every tenant table has `org_id` and Postgres row-level security; patient identifiers encrypted | PostgreSQL 16 |
| **Identity** | Sign-in, roles (radiologist, physician, auditor, admin), organisation claim in the token | Keycloak 25, OIDC with PKCE |
| **Imaging** | Receives studies from scanners; images and heatmaps in object storage | Orthanc, MinIO (S3 API) |
| **Delivery** | Every service over TLS; CI on every push | Docker Compose, GitHub Actions |

### A scan's journey

```mermaid
sequenceDiagram
    autonumber
    participant D as Doctor or scanner
    participant A as Core API
    participant DB as Postgres
    participant W as Job worker (core API)
    participant M as AI model
    D->>A: Upload / DICOM study
    A->>DB: Encrypt patient ids, store study, queue a job per matching model
    A-->>D: 201 Created (study page starts following the pipeline)
    W->>DB: Claim the job (FOR UPDATE SKIP LOCKED)
    W->>M: Image or recording
    M-->>W: Probabilities, heatmap, weights hash, measurements
    W->>DB: Prediction + priority score + reason, worklist item, audit entry
    D->>A: Worklist (ranked) → open study → review
    A->>DB: Signed review, study REVIEWED, audit entry (hash-chained)
```

The priority score is stored **with its reason**, so the "why this priority?" view shows exactly what the ranking used:

```
priority = Σ (probability of each label × urgency weight of that label) + time-waiting bonus (0.5 per hour, at most 20)
```

---

## The AI models

Every model is trained by transfer learning (ResNet-18 for images, a 1-D ResNet for ECG and EEG, a U-Net for wound outlines) and evaluated on **patients, lesions or recordings it never trained on**. Probabilities are **temperature-scaled on a validation set** so that "90%" means roughly nine in ten. Data is split by patient (or slide, lesion or procedure), so no patient sits on both sides, and near-duplicate images are removed first where a dataset contains them.

| Specialty | Model | Held-out result | Test cases | Data |
|---|---|---|---|---|
| Radiology | Chest X-ray: pneumonia | accuracy 89.6%, AUC 0.974 | 624 | Kermany et al. 2018 (CC BY 4.0) |
| Neurology | Brain MRI: tumour type | accuracy 92.8%, AUC 0.992 | 457 | Cheng et al., Figshare (CC BY 4.0) |
| Neurology | EEG: seizure detection | 36.6% of seizures caught, 2.3 false alarms/hour | 32 h | CHB-MIT (ODC-BY 1.0) |
| Pathology | Blood smear: malaria | accuracy 98.0%, AUC 0.997 | 5,177 | NIH/NLM (public domain) |
| Pathology | Colorectal tissue (9 classes) | accuracy 95.1%, AUC 0.994 | 7,180 | Kather et al. 2019 (CC BY 4.0) |
| Pathology | Prostate: Gleason pattern | accuracy 74.1%, AUC 0.919 | 2,122 | SICAPv2 (CC BY 4.0) |
| Gastroenterology | Colonoscopy findings | accuracy 90.1%, AUC 0.995 | 750 | HyperKvasir (CC BY 4.0) |
| Ophthalmology | Diabetic retinopathy grade | accuracy 72.0%, AUC 0.928 | 400 | DeepDRiD (CC BY-SA 4.0) |
| Cardiology | 12-lead ECG rhythm (7 labels) | macro AUC 0.957 | 2,198 | PTB-XL (CC BY 4.0) |
| Dermatology | Skin lesion (7 classes) | accuracy 81.2%, AUC 0.960 | 1,513 | HAM10000 (CC BY-NC 4.0) |
| Dermatology | Wound outline and area | Dice 0.857 | 200 | FUSeg 2021 (research use) |

Full per-class results, calibration, shortcut checks and known limits for every model are in **[docs/models.md](docs/models.md)**, generated from the training metadata.

### Honesty over headline numbers

- **The shortcut check.** For each image model, a trivial classifier that sees only image size and colour statistics is trained on the same split. If the real model barely beats it, the model is probably reading *how* the image was taken, not the disease.
- **The glaucoma model was withdrawn** despite scoring 100% on its test set: the shortcut baseline scored 92%, so the "perfect" result came from the camera, not the optic nerve.
- **The head CT stroke model was withdrawn** because there were too few patients to trust it.
- **The colonoscopy model learnt a burnt-in screen overlay** as a shortcut; the overlays are now blacked out before training and serving.
- **A colorectal tissue v0.2 was rejected** because training on more data made it worse on the rarest class.
- **The registry shows the weak spots**, such as the skin model missing about a third of melanomas, so clinicians know when not to lean on it.

---

## Security and privacy

| | |
|---|---|
| 🔐 **Encrypted everywhere** | TLS on every connection, including internal ones (database `verify-full`, object storage, inference, Keycloak). DICOM uses **mutual TLS**: a scanner without a certificate from the hospital's CA is refused. |
| 🏥 **One hospital can't see another's data** | Every tenant table carries `org_id` with **Postgres row-level security**. The organisation comes only from the signed login token, and a query with no tenant set returns no rows. |
| 🗝️ **Patient identifiers locked away** | MRN, name and date of birth are encrypted by the application and kept in one table; the AI pipeline only ever sees internal ids. Consults link a study, never copy identifiers. |
| 🧾 **Tamper-evident audit** | Every read and write of patient data is logged, append-only (the database refuses updates and deletes), and **chained with SHA-256** per organisation. One click recomputes the chain. |
| 👥 **Least privilege** | Radiologists and physicians see patients; auditors see the log and the registry; admins manage DICOM senders. Deactivated accounts are refused within a minute, whatever their token says. |
| 🧱 **Hardened web layer** | A deny-by-default Content Security Policy, no framing, HSTS, per-user rate limits shared across API instances, and no secrets in the browser. |
| 🧬 **No data in the repository** | No patient data, datasets or model weights are committed. Demo patients are fictional and generated by a script. |

---

## How the project was planned

Aegle started small and grew in deliberate stages, each one finished, tested and documented before the next began.

| Stage | When | What it delivered |
|---|---|---|
| **0. Prototype** | Jun 2026 | One pneumonia classifier in Java (DL4J) with a drag-and-drop page. It worked, and it showed what a real product would need: many models, real users, real security. ([notes](docs/pneumonia-prototype.md)) |
| **1. Architecture and data model** | Sep 2026 | Split into a Spring Boot API, a Python inference service and a React app. Multi-tenant schema with row-level security, encrypted identifiers and an explainable priority score from day one. |
| **2. Clinical workflow** | Sep 2026 | Upload, worklist, study page with heatmap, clinician review, audit log. |
| **3. Security and compliance** | Sep 2026 | Authenticated service-to-service calls, TLS everywhere, mutual-TLS DICOM, hash-chained audit, rate limits, security headers, per-hospital model switches. |
| **4. Seven specialties** | Sep–Oct 2026 | Ten more models, ECG and EEG pipelines, wound measurement over visits, shortcut checks for every model, two models withdrawn, v0.2 retraining with calibration. |
| **5. Quality** | Oct 2026 | CI for all three services, frontend tests, an end-to-end check of every model through the full stack. |
| **6. A hospital-grade interface** | Oct 2026 | EHR-style shell, reading-room viewer, RIS worklist, live pipeline, critical alerts, explainable triage, model evidence charts, prior comparison, consults, Lights off, phone layout. |

The research behind the interface: the NHS Common User Interface guidance for patient banners and dates, PACS reading-room practice (dark viewers, keyboard-first tools), studies of reading-room lighting, and EHR usability guidance on preventing errors (which is why reviews can't be signed from the keyboard and critical alerts must be acknowledged).

---

## Design decisions

| Decision | Why |
|---|---|
| **The AI suggests; a clinician signs** | Responsibility stays with a qualified person, and the record shows who decided. Nothing the model says is final until reviewed. |
| **Priority = probability × urgency + waiting time, stored with its reason** | A ranking clinicians can check and argue with is one they can trust. The waiting bonus stops routine cases from waiting forever. |
| **Two services: Java for the clinic, Python for the AI** | Spring Boot is strong at transactions, security and integration; the ML ecosystem lives in Python. A narrow HTTPS contract keeps each replaceable. |
| **Models as plug-ins** | Each model registers its modality, body part, task and intended use. Adding a specialty means adding an adapter, not changing the API or the UI. |
| **Row-level security in Postgres, not just in code** | A bug in one query can't leak another hospital's data, because the database itself filters by tenant. |
| **A shortcut baseline for every model** | High accuracy can come from the scanner, not the disease. Comparing with a model that can't see anatomy catches that. |
| **Audit reads, not just writes** | In healthcare, *who looked* matters as much as who changed something. The UI is designed to avoid needless reads: priors load on request, the dashboard shares one summary. |
| **Consults link a study, never copy it** | The conversation can be shared without spreading identifiers; opening the study is access-controlled and audited like any other read. |
| **Dark theme as its own palette** | Reading rooms are dim. Each dark colour is chosen and contrast-checked, not inverted. |

---

## Getting started

### Prerequisites

Docker, Java 17 and Maven, Python 3.11, Node 22.

### Run it

```bash
cp .env.example .env          # then change the values
infra/tls/generate.sh         # local dev CA + certificates (once)
set -a; source .env; set +a   # in every shell that starts a service below
docker compose up -d          # Postgres, MinIO, Orthanc, Keycloak (all over TLS)

cd core-api && SPRING_PROFILES_ACTIVE=dev mvn spring-boot:run                     # https://localhost:8090
cd inference-service && .venv/bin/uvicorn app.main:app --port 8000 \
    --ssl-keyfile ../infra/tls/certs/server.key --ssl-certfile ../infra/tls/certs/server.crt
docker compose --profile web up -d --build web                                     # https://localhost:5443
```

`cd frontend && npm install && npm run dev` serves the app with hot reload on https://localhost:5173 instead. To trust the local CA in your browser (macOS):

```bash
security add-trusted-cert -r trustRoot -k ~/Library/Keychains/login.keychain-db infra/tls/certs/ca.crt
```

### Demo logins

All demo accounts use the password `dev-only-password` (local development only).

| Username | Role |
|---|---|
| `rita.radiologist` | Consultant radiologist (the main demo account) |
| `amara.okafor`, `kwame.asante`, `hannah.clarke`, `priya.raman`, `wei.chen`, `fatima.alsayed`, `james.whitfield`, `daniel.mensah` | Consultants in each specialty |
| `paul.physician`, `tomasz.nowak` | Registrars |
| `sofia.rossi` | Foundation doctor |
| `alex.auditor` | Information governance (audit log only) |
| `ada.admin` | System administrator (DICOM senders) |
| `otto.other` | A radiologist at a *different* hospital: sees none of this one's data |

`tools/dev/seed_clinic.py` fills the demo clinic with fictional patients, studies analysed by the real models, signed reports and consults (it needs the training datasets on disk).

<details>
<summary><b>More: DICOM from scanners, the production-style frontend, and the database role</b></summary>

#### DICOM from modalities

Scanners and PACS send to Orthanc (C-STORE, port 4242, mutual TLS). core-api follows Orthanc's change log and, once a study is complete, imports it into the organisation that registered the sender's calling AE title: identifiers are encrypted as for uploads, images go to object storage with a de-identified header subset, matching models are queued, and the study appears in the worklist. Admins register AE titles on the "DICOM senders" page; the dev seed registers `AEGLE_DEV_CR`. `tools/dev/send_cxr.py` acts as a CR modality for testing.

- Studies from unregistered AE titles, or without a PatientID, stay in Orthanc and are logged.
- Each Orthanc study is imported once; configure modalities to send a study in one association.
- The TLS certificate proves the sender is one of yours, not which AE title it may use.
- Browsers cannot display DICOM: the image endpoint returns a PNG rendered on first view and kept next to the original.

#### Production-style frontend

nginx serves the built app with the full header set (the CSP is generated from `frontend/security-headers.ts`, the same source the dev server uses) and proxies `/api` to core-api over verified TLS (`AEGLE_API_UPSTREAM`). It replaces any client-sent `X-Forwarded-For`; core-api only trusts that header from `AEGLE_TRUSTED_PROXIES`, so audit entries record the real client address.

If a port is taken, override it: `AEGLE_API_PORT`, `AEGLE_API_URL` and a full `AEGLE_DB_URL` (keep `sslmode` and `sslrootcert`).

#### The database role

The schema lives in `core-api/src/main/resources/db/migration/`. The application must connect as `aegle_app` (created `NOLOGIN` by the migration) because superusers bypass row-level security:

```sql
ALTER ROLE aegle_app LOGIN PASSWORD '...';
```

Per transaction the API sets the tenant with `SET LOCAL app.current_org_id = '<uuid>'`; with no tenant set, queries return no rows.

</details>

---

## Tests

GitHub Actions runs all three suites on every push and pull request.

```bash
cd core-api && mvn test                                 # 73 tests; real Postgres via Testcontainers (needs Docker)
cd inference-service && .venv/bin/python -m pytest -q  # 40 tests; builds small models, no weights needed
cd frontend && npm run lint && npm test && npm run build   # 40 tests
```

The backend tests run against the production migrations and the restricted database role, so row-level security is tested as it runs, including that one hospital can't read another's studies or consults. `inference-service/training/serving_check.py` checks a running inference service against each model's recorded held-out results.

## Project structure

```
aegle/
├── core-api/            Spring Boot clinical API
│   └── src/main/java/com/aegle/
│       ├── study/       upload, study detail, images, priors
│       ├── worklist/    ranked worklist and department summary
│       ├── inference/   job queue worker, triage policy, model registry sync
│       ├── review/      clinician decisions
│       ├── consult/     clinician-to-clinician consults
│       ├── dicom/       Orthanc import and DICOM senders
│       ├── audit/       hash-chained audit log
│       ├── security/    token → user, roles, rate limits
│       └── phi/         encryption of patient identifiers
├── inference-service/   FastAPI + PyTorch
│   ├── app/             serving: model adapters, Grad-CAM, ECG/EEG pipelines
│   └── training/        data preparation, training, evaluation, model report
├── frontend/            React + TypeScript app (worklist, viewer, consults, registry)
├── infra/               Keycloak realm and theme, Postgres init, TLS scripts
├── docs/                model report, screenshots, prototype notes
└── tools/dev/           demo seeding, DICOM senders, login and screenshot helpers
```

## Limitations

- **Not validated for clinical use.** The models are trained on public research datasets, mostly from one or two centres; none has been tested on a hospital's own patients.
- **One label per image.** Each model answers one question (for example, "which tumour type?"); the brain MRI model cannot say whether a tumour is present, because every training slice had one.
- **Some models are modest.** Retinopathy grading (72% accuracy) and seizure detection (about a third of seizures caught) are useful demonstrations, not tools to rely on.
- **Not yet a full PACS.** One image per study is viewed in the browser; multi-frame series, measurements on the image and hanging protocols are not built.
- **Polling, not push.** The worklist, alerts and consults refresh every 5–30 seconds; a hospital-scale deployment would use server push.

## What's next

1. **Server push** for the worklist, alerts and consults.
2. **Echocardiography, leukaemia and glaucoma models**, waiting on data access (data-use agreements and a glaucoma dataset without acquisition shortcuts).
3. **External validation** of each model on data from a different hospital, with drift monitoring once live.
4. **HL7 FHIR** export of signed reports to the hospital's record system.
5. **A hosted demo** with real certificates.

## Data and image credits

The medical images shown in the screenshots come from public, de-identified research datasets, used under their licences: chest X-rays (Kermany et al., CC BY 4.0), brain MRI (Cheng et al., CC BY 4.0), malaria cells (NIH/NLM, public domain), colorectal tissue (Kather et al., CC BY 4.0), prostate biopsies (SICAPv2, CC BY 4.0), colonoscopy (HyperKvasir, CC BY 4.0), retinal photographs (DeepDRiD, CC BY-SA 4.0), dermoscopy (HAM10000, CC BY-NC 4.0, non-commercial), ECG (PTB-XL, CC BY 4.0) and EEG (CHB-MIT, ODC-BY 1.0). All patient names and details are fictional. The clinicians' pictures are illustrations of fictional people generated with Figma AI.

<p align="center">
  Built by <a href="https://github.com/samaunmahmud">Samaun Mahmud</a> · Computer Science (AI), Brunel University London
</p>
