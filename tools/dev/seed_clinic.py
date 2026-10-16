"""Fill the local dev clinic with fictional patients, studies (held-out test images through the
real pipeline), signed reports and consult conversations between the demo doctors.

Needs the dev stack running (core-api on 8090 with the dev profile, inference service,
Keycloak) and the training datasets on disk, since the images are each model's held-out
test split. Nothing it uploads is committed.

    cd inference-service && .venv/bin/python ../tools/dev/seed_clinic.py
"""
import json
import random
import ssl
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, ".")
from training.serving_check import image_cases  # noqa: E402

HERE = Path(__file__).resolve().parent
CA = "../infra/tls/certs/ca.crt"
API = "https://localhost:8090"
CTX = ssl.create_default_context(cafile=CA)
rng = random.Random(7)

DOCTORS = ["rita.radiologist", "paul.physician", "amara.okafor", "kwame.asante", "tomasz.nowak", "james.whitfield",
           "priya.raman", "wei.chen", "hannah.clarke", "fatima.alsayed", "daniel.mensah", "sofia.rossi"]
TOK = {}


def token(user):
    if user not in TOK:
        TOK[user] = subprocess.run([sys.executable, str(HERE / "login.py"), user, "dev-only-password", CA],
                                   capture_output=True, text=True, check=True).stdout.strip()
    return TOK[user]


def call(user, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token(user)}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()[:300]}") from None


def upload(user, path, p, modality, body_part, study_date, acc):
    out = subprocess.run(["curl", "-sf", "--cacert", CA, "-H", f"Authorization: Bearer {token(user)}",
                          "-F", f"file=@{path}", "-F", f"patientMrn={p['mrn']}", "-F", f"patientName={p['name']}",
                          "-F", f"patientDob={p['dob']}", "-F", f"patientSex={p['sex']}",
                          "-F", f"modality={modality}", "-F", f"bodyPart={body_part}",
                          "-F", f"accessionNo={acc}", "-F", f"studyDate={study_date}", API + "/api/studies"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["studyId"]


FIRST_F = ["Olivia", "Amelia", "Isla", "Ava", "Grace", "Freya", "Zara", "Aisha", "Maya", "Chloe", "Niamh", "Ruth",
           "Margaret", "Joan", "Leah", "Priyanka", "Mei", "Yasmin", "Eleanor", "Bethany"]
FIRST_M = ["Oliver", "George", "Arthur", "Noah", "Harry", "Leo", "Mohammed", "Jack", "Thomas", "Samuel", "Ibrahim",
           "Kofi", "David", "Stanley", "Rhys", "Callum", "Arjun", "Hamza", "Edward", "Patrick"]
LAST = ["Thompson", "Patel", "Hughes", "Wright", "Begum", "Evans", "Kowalski", "Okoro", "Davies", "Murphy", "Ahmed",
        "Robinson", "Clarke", "Walker", "Nguyen", "Fraser", "Bennett", "Hussain", "Morgan", "Doyle", "Campbell",
        "Mensah", "Sharma", "Gallagher", "Price"]


def patient(i):
    sex = rng.choice("FM")
    first = rng.choice(FIRST_F if sex == "F" else FIRST_M)
    dob = date(1938, 1, 1) + timedelta(days=rng.randrange(0, 365 * 80))
    return {"mrn": f"RXH{400100 + i * 37}", "name": f"{first} {rng.choice(LAST)}", "dob": dob.isoformat(), "sex": sex}


MODELS = {  # model -> (modality, body part, how many cases, uploader pool)
    "chest-xray-pneumonia": ("XR", "CHEST", 9, ["kwame.asante", "tomasz.nowak", "paul.physician"]),
    "brain-mri-tumor-type": ("MR", "BRAIN", 8, ["amara.okafor", "daniel.mensah", "rita.radiologist"]),
    "skin-lesion-dermoscopy": ("XC", "SKIN", 8, ["priya.raman", "sofia.rossi"]),
    "fundus-diabetic-retinopathy": ("OP", "EYE", 6, ["wei.chen"]),
    "colonoscopy-findings": ("ES", "COLON", 6, ["fatima.alsayed"]),
    "blood-smear-malaria": ("SM", "BLOOD", 6, ["hannah.clarke", "paul.physician"]),
    "colorectal-tissue-he": ("SM", "TISSUE", 6, ["hannah.clarke"]),
    "prostate-gleason-pattern": ("SM", "PROSTATE", 5, ["hannah.clarke"]),
}

patients = [patient(i) for i in range(40)]
today = date.today()
uploads = []  # (study id, model, true label, uploader, patient)
acc = 9100
for model, (modality, body_part, n, pool) in MODELS.items():
    cases = image_cases(model)
    rng.shuffle(cases)
    by_label = {}
    for path, label in cases:
        by_label.setdefault(label, []).append(path)
    labels = sorted(by_label)
    picked = [(by_label[labels[k % len(labels)]].pop(), labels[k % len(labels)]) for k in range(n)]
    for path, label in picked:
        p = rng.choice(patients)
        acc += rng.randrange(1, 9)
        user = rng.choice(pool)
        sid = upload(user, path, p, modality, body_part, (today - timedelta(days=rng.randrange(0, 21))).isoformat(),
                     f"ACC{acc}")
        uploads.append((sid, model, label, user, p))
        print("uploaded", model, label, p["mrn"], flush=True)

# A follow-up for a few patients, so the prior-comparison view has something to show.
for sid, model, label, user, p in rng.sample(uploads, 5):
    modality, body_part, _, pool = MODELS[model]
    path, lab = rng.choice(image_cases(model))
    acc += 3
    sid2 = upload(user, path, p, modality, body_part, today.isoformat(), f"ACC{acc}")
    uploads.append((sid2, model, lab, user, p))

print("waiting for the AI to finish", len(uploads), "studies", flush=True)
pending = {u[0] for u in uploads}
deadline = time.time() + 900
while pending and time.time() < deadline:
    for sid in list(pending):
        st = call("rita.radiologist", "GET", f"/api/studies/{sid}")["study"]["status"]
        if st in ("READY", "REVIEWED", "FAILED"):
            pending.discard(sid)
    if pending:
        time.sleep(5)
print("still pending:", len(pending))

# Sign off about a third, by the department's consultant, so "Reported" has history.
REVIEWER = {"chest-xray-pneumonia": "kwame.asante", "brain-mri-tumor-type": "amara.okafor",
            "skin-lesion-dermoscopy": "priya.raman", "fundus-diabetic-retinopathy": "wei.chen",
            "colonoscopy-findings": "fatima.alsayed", "blood-smear-malaria": "hannah.clarke",
            "colorectal-tissue-he": "hannah.clarke", "prostate-gleason-pattern": "hannah.clarke"}
details = {}
for sid, model, label, user, p in uploads:
    details[sid] = call("rita.radiologist", "GET", f"/api/studies/{sid}")
reviewed = 0
for sid, model, label, user, p in rng.sample(uploads, len(uploads) // 3):
    preds = details[sid].get("predictions") or []
    if not preds:
        continue
    top = preds[0]
    agree = top["label"] == label
    body = {"decision": "ACCEPT"} if agree else {"decision": "MODIFY", "finalLabel": label,
                                                 "comment": "Disagree with the AI suggestion on review."}
    call(REVIEWER[model], "POST", f"/api/predictions/{top['id']}/review", body)
    reviewed += 1
print("reviewed", reviewed)


def study_for(model, want=None):
    for sid, m, label, user, p in uploads:
        d = details[sid]
        if m == model and d["study"]["status"] == "READY" and (want is None or (d.get("predictions") or [{}])[0].get("label") == want):
            return sid
    return next(u[0] for u in uploads if u[1] == model)


ID = {u["name"].split()[0].lower(): u["id"] for u in call("rita.radiologist", "GET", "/api/consults/colleagues")}
for c in call("paul.physician", "GET", "/api/consults/colleagues"):
    if c["name"].startswith("Rita"):
        ID["rita"] = c["id"]

THREADS = [
    ("tomasz.nowak", "kwame", "chest-xray-pneumonia", "pneumonia", "URGENT", "Right lower zone: consolidation or atelectasis?",
     [("tomasz.nowak", "AI flags pneumonia at high probability. I can see increased opacity at the right base but the "
                       "hemidiaphragm is still visible. Would you call this consolidation?"),
      ("kwame.asante", "Had a look. There are air bronchograms behind the heart shadow on the right, so I'd call it "
                       "consolidation. Agree with the AI here."),
      ("kwame.asante", "Suggest clinical correlation with CRP and a repeat film in 6 weeks to confirm resolution."),
      ("tomasz.nowak", "Thanks, that's really helpful. I'll report it as right lower lobe consolidation.")], True),
    ("paul.physician", "amara", "brain-mri-tumor-type", None, "URGENT", "Extra-axial lesion: meningioma vs dural metastasis?",
     [("paul.physician", "68-year-old with headaches. AI suggests meningioma. Patient has a history of breast cancer, "
                         "so I'm worried about a dural metastasis. Could you take a look before I speak to the family?"),
      ("amara.okafor", "Broad dural base and a CSF cleft, which favours meningioma. No bone destruction. I wouldn't "
                       "exclude a metastasis on one sequence though."),
      ("amara.okafor", "I'd ask for post-contrast T1 and perfusion. I'll add it to the neuro-oncology MDT on Thursday.")], False),
    ("sofia.rossi", "priya", "skin-lesion-dermoscopy", None, "ROUTINE", "Pigmented lesion on the back: refer on 2-week wait?",
     [("sofia.rossi", "First time using the dermoscopy model. It says naevus with moderate confidence. There is some "
                      "asymmetry. Is this enough to refer urgently?"),
      ("priya.raman", "Good question to ask. Remember the model misses about a third of melanomas, so a 'naevus' call "
                      "does not reassure on its own. Asymmetry plus colour variation: I'd refer on the 2-week pathway.")], False),
    ("wei.chen", None, "fundus-diabetic-retinopathy", None, "ROUTINE", "Grading disagreement: moderate vs severe NPDR",
     [("wei.chen", "AI grades moderate NPDR. I count haemorrhages in all four quadrants, which would make it severe "
                   "(4-2-1 rule). Anyone available for a second grader opinion?")], False),
    ("fatima.alsayed", "hannah", "colonoscopy-findings", None, "ROUTINE", "Polyp morphology: sessile serrated?",
     [("fatima.alsayed", "Flat lesion in the ascending colon, AI calls it a polyp. Mucus cap visible. I've resected it; "
                         "please could histology look for sessile serrated features?"),
      ("hannah.clarke", "Will do. I'll flag it for a serrated pathway review and let you know.")], False),
    ("hannah.clarke", "rita", "blood-smear-malaria", "parasitized", "URGENT", "Possible P. falciparum on smear: please confirm",
     [("hannah.clarke", "AI marks this cell as parasitized at >99%. Ring forms on my side too. Rita, are you on today? "
                        "The clinical team will want a parasitaemia estimate quickly."),
      ("hannah.clarke", "Thick film being prepared now.")], False),
    ("james.whitfield", "rita", "chest-xray-pneumonia", None, "ROUTINE", "Post-op CXR: effusion size before discharge",
     [("james.whitfield", "Day 4 after cardiac surgery. Small left effusion on yesterday's film. Is it any larger today? "
                          "Deciding whether to discharge.")], False),
    ("daniel.mensah", "amara", "brain-mri-tumor-type", None, "ROUTINE", "Pituitary lesion: is this a macroadenoma?",
     [("daniel.mensah", "Bitemporal field loss on exam. AI suggests pituitary tumour. Is there chiasmal compression?"),
      ("amara.okafor", "Yes: suprasellar extension with mild upward displacement of the chiasm. Macroadenoma, about "
                       "14 mm. Needs endocrine bloods and a neurosurgical opinion."),
      ("daniel.mensah", "Thank you, referring today.")], True),
]
for asker, asked, model, want, urgency, subject, msgs, resolve in THREADS:
    sid = study_for(model, want)
    first = msgs[0][1]
    d = call(asker, "POST", "/api/consults", {"subject": subject, "body": first, "studyId": sid, "urgency": urgency,
                                              **({"askedOf": ID[asked]} if asked else {})})
    tid = d["thread"]["id"]
    for who, text in msgs[1:]:
        time.sleep(1.2)
        call(who, "POST", f"/api/consults/{tid}/messages", {"body": text})
    if resolve:
        call(asker, "POST", f"/api/consults/{tid}/resolve")
    print("consult", subject)
print("done")
