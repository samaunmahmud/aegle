"""Send a held-out stroke patient's head CT slices to Orthanc as one DICOM CT series (mutual TLS)."""
import csv, ssl, sys
import numpy as np
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage

certs, data_dir, patient, aet, mrn = sys.argv[1:6]
rows = [r for r in csv.DictReader(open(f"{data_dir}/index.csv")) if r["group"] == patient]
rows.sort(key=lambda r: int(r["file"].rsplit("_", 1)[1].split(".")[0]))
study, series = generate_uid(), generate_uid()
ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=f"{certs}/ca.crt")
ctx.load_cert_chain(f"{certs}/modality.crt", f"{certs}/modality.key")
ae = AE(ae_title=aet); ae.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
assoc = ae.associate("localhost", 4242, ae_title="ORTHANC", tls_args=(ctx, "localhost"))
assert assoc.is_established
for i, r in enumerate(rows):
    px = np.asarray(Image.open(f"{data_dir}/{r['file']}").convert("L"), dtype=np.uint8)
    ds = Dataset(); ds.file_meta = FileMetaDataset(); ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = CTImageStorage; ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID, ds.SeriesInstanceUID = study, series
    ds.PatientID, ds.PatientName, ds.PatientBirthDate, ds.PatientSex = mrn, "NAVARRO^ELENA", "19540612", "F"
    ds.StudyDate, ds.AccessionNumber, ds.Modality, ds.BodyPartExamined = "20260927", "ACC-" + mrn, "CT", "BRAIN"
    ds.InstanceNumber = i + 1
    ds.Rows, ds.Columns = px.shape; ds.SamplesPerPixel = 1; ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = ds.BitsStored = 8; ds.HighBit = 7; ds.PixelRepresentation = 0
    ds.PixelData = px.tobytes()
    assert assoc.send_c_store(ds).Status == 0
assoc.release()
print(f"sent {len(rows)} slices of test patient {patient} as study {study}; labels:",
      {l: sum(r['label'] == l for r in rows) for l in ('HAEMORRHAGE', 'ISCHAEMIC_STROKE', 'NO_STROKE')})
