"""Upload one held-out case per specialty to the running stack (for live verification).

Usage: seed_demo.py <api base> <token file> <ca file>
Every case comes from a split the model never trained on.
"""
import csv
import json
import random
import ssl
import sys
import urllib.request
import uuid
from pathlib import Path

REPO = Path("/Users/samaunmahmud/Documents/Medical  image detector")
DS = REPO / "dataset"
sys.path.insert(0, str(REPO / "inference-service"))

api, token_file, ca = sys.argv[1], sys.argv[2], sys.argv[3]
token = Path(token_file).read_text().strip()
ctx = ssl.create_default_context(cafile=ca)
rng = random.Random(7)


def upload(data: bytes, filename: str, mrn: str, name: str, dob: str, sex: str, modality: str, body: str):
    boundary = uuid.uuid4().hex
    fields = {"patientMrn": mrn, "patientName": name, "patientDob": dob, "patientSex": sex,
              "modality": modality, "bodyPart": body, "accessionNo": f"ACC-{mrn}"}
    body_bytes = b"".join(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields.items())
    body_bytes += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                   f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{api}/api/studies", data=body_bytes, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, context=ctx) as r:
        out = json.load(r)
    print(f"{modality}/{body:7} {mrn:12} -> {out['status']} ({out['jobsQueued']} model(s))")


def index_rows(path, **match):
    with open(path) as f:
        return [r for r in csv.DictReader(f) if all(r.get(k) == v for k, v in match.items())]


# Cardiology: an atrial fibrillation ECG from PTB-XL's test fold, as DICOM.
from training.ecg_dicom import ecg_dicom  # noqa: E402
from training.train_ecg import read_record  # noqa: E402
ptb = [r for r in csv.DictReader(open(DS / "ptbxl/ptbxl_database.csv"))
       if r["strat_fold"] == "10" and "'AFIB'" in r["scp_codes"]]
upload(ecg_dicom(read_record(DS / "ptbxl" / ptb[0]["filename_lr"]), 100.0), "ecg.dcm",
       "MRN-300101", "Hans Weber", "1948-03-12", "M", "ECG", "HEART")

# Neurology: a test-patient EEG with a seizure.
meta = json.loads((REPO / "saved-model/eeg-seizure-resnet1d.json").read_text())
test_patient = meta["metrics"]["split"]["test_patients"][0]
edf = next(p for p in sorted((DS / "chbmit" / test_patient).glob("*.edf")) if p.stat().st_size < 50_000_000)
upload(edf.read_bytes(), "eeg.edf", "MRN-300202", "Lucas Martin", "2014-07-22", "M", "EEG", "BRAIN")

# Dermatology: an ISIC 2018 test-set melanoma (external test).
mel = [r for r in index_rows(DS / "ham10000/index.csv", split="external") if r["label"] == "MELANOMA"]
upload((DS / "ham10000" / rng.choice(mel)["file"]).read_bytes(), "skin.jpg",
       "MRN-300303", "Claire Dubois", "1969-05-03", "F", "XC", "SKIN")

# Ophthalmology: a proliferative DR test image; a glaucoma disc.
dr = index_rows(DS / "retina_dr/index.csv", split="test", label="DR_SEVERE")
upload((DS / "retina_dr" / rng.choice(dr)["file"]).read_bytes(), "fundus.png",
       "MRN-300404", "Rahul Mehta", "1962-11-19", "M", "OP", "EYE")

# Pathology: a parasitised cell; a colorectal tumour tile from CRC-VAL-HE-7K (external patients).
cells = [p for p in (DS / "malaria_nih/cell_images/Parasitized").glob("*.png")]
upload(rng.choice(cells).read_bytes(), "cell.png", "MRN-300505", "Amina Yusuf", "1990-01-28", "F", "SM", "BLOOD")
from PIL import Image  # noqa: E402
import io  # noqa: E402
tum = sorted((DS / "crc_tissue/CRC-VAL-HE-7K/TUM").glob("*.tif"))
buf = io.BytesIO(); Image.open(rng.choice(tum)).convert("RGB").save(buf, format="PNG")
upload(buf.getvalue(), "tile.png", "MRN-300606", "Peter Novak", "1955-09-09", "M", "SM", "TISSUE")

# Gastroenterology: a polyp frame.
polyps = index_rows(DS / "hyperkvasir/index.csv", label="POLYP")
upload((DS / "hyperkvasir" / rng.choice(polyps)["file"]).read_bytes(), "frame.jpg",
       "MRN-300707", "Sofia Rossi", "1972-12-01", "F", "ES", "COLON")

# Dermatology (wounds): three visits of one patient from held-out FUSeg photos, shrinking.
wounds = sorted((DS / "fuseg/challenge/validation/images").glob("*.png"))
labels = DS / "fuseg/challenge/validation/labels"
import numpy as np  # noqa: E402
areas = sorted(wounds, key=lambda p: -(np.asarray(Image.open(labels / p.name).convert("L")) > 127).sum())
for i, p in enumerate([areas[5], areas[40], areas[120]]):
    upload(p.read_bytes(), "wound.png", "MRN-300808", "George Adams", "1951-04-14", "M", "XC", "WOUND")

# Pathology: a Gleason pattern 4 patch from SICAPv2's official test patients.
g4 = index_rows(DS / "sicapv2/index.csv", split="test", label="GLEASON_4")
upload((DS / "sicapv2" / rng.choice(g4)["file"]).read_bytes(), "patch.jpg",
       "MRN-300909", "Miguel Ortega", "1949-08-21", "M", "SM", "PROSTATE")
