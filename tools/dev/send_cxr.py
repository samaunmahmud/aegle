"""Acts as a CR modality: wraps a chest X-ray JPEG in DICOM and C-STOREs it to Orthanc over mutual TLS."""
import ssl, sys
import numpy as np
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE
from pynetdicom.sop_class import ComputedRadiographyImageStorage

certs, jpeg, aet, mrn = sys.argv[1:5]
px = np.asarray(Image.open(jpeg).convert("L"), dtype=np.uint16) * 16   # 12-bit, as a real CR would be
ds = Dataset()
ds.file_meta = FileMetaDataset(); ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
ds.SOPClassUID = ComputedRadiographyImageStorage; ds.SOPInstanceUID = generate_uid()
ds.StudyInstanceUID = generate_uid(); ds.SeriesInstanceUID = generate_uid()
ds.PatientID = mrn; ds.PatientName = "TESTPATIENT^DICOM"; ds.PatientBirthDate = "20190305"; ds.PatientSex = "M"
ds.StudyDate = "20260926"; ds.AccessionNumber = "ACC-" + mrn
ds.Modality = "CR"; ds.BodyPartExamined = "CHEST"; ds.ViewPosition = "PA"
ds.Rows, ds.Columns = px.shape; ds.SamplesPerPixel = 1; ds.PhotometricInterpretation = "MONOCHROME2"
ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 12, 11, 0
ds.WindowCenter, ds.WindowWidth = 2048, 4096
ds.PixelData = px.tobytes()

ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=f"{certs}/ca.crt")
ctx.load_cert_chain(f"{certs}/modality.crt", f"{certs}/modality.key")
ae = AE(ae_title=aet); ae.add_requested_context(ComputedRadiographyImageStorage, ExplicitVRLittleEndian)
assoc = ae.associate("localhost", 4242, ae_title="ORTHANC", tls_args=(ctx, "localhost"))
assert assoc.is_established, "association refused"
status = assoc.send_c_store(ds); assoc.release()
print("C-STORE", hex(status.Status), "study", ds.StudyInstanceUID)
