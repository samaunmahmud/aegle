"""Write a 12-lead ECG as a DICOM 12-Lead ECG Waveform object, as an ECG cart would.

Used by tests and to turn PTB-XL records into realistic DICOM for end-to-end demos.
"""
from __future__ import annotations

import io

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.waveform import LEADS

TWELVE_LEAD_ECG = "1.2.840.10008.5.1.4.1.1.9.1.1"


def _code(value: str, scheme: str, meaning: str) -> Dataset:
    c = Dataset()
    c.CodeValue, c.CodingSchemeDesignator, c.CodeMeaning = value, scheme, meaning
    return c


def ecg_dicom(signals_mv: np.ndarray, fs: float, patient_id: str = "TEST", patient_name: str = "TEST^ECG",
              **study) -> bytes:
    """`signals_mv`: (12, samples) in LEADS order. Stored as 16-bit integers in microvolts."""
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = TWELVE_LEAD_ECG
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = Dataset()
    ds.file_meta = meta
    ds.SOPClassUID, ds.SOPInstanceUID = TWELVE_LEAD_ECG, meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID, ds.SeriesInstanceUID = generate_uid(), generate_uid()
    ds.PatientID, ds.PatientName, ds.Modality = patient_id, patient_name, "ECG"
    for k, v in study.items():
        setattr(ds, k, v)

    wf = Dataset()
    wf.WaveformOriginality = "ORIGINAL"
    wf.NumberOfWaveformChannels = len(LEADS)
    wf.NumberOfWaveformSamples = signals_mv.shape[1]
    wf.SamplingFrequency = fs
    wf.WaveformBitsAllocated = 16
    wf.WaveformSampleInterpretation = "SS"
    channels = []
    for lead in LEADS:
        ch = Dataset()
        ch.ChannelSourceSequence = Sequence([_code("5.6.3-9-1", "SCPECG", f"Lead {lead}")])
        ch.ChannelSensitivity = 1.0
        ch.ChannelSensitivityUnitsSequence = Sequence([_code("uV", "UCUM", "microvolt")])
        ch.ChannelSensitivityCorrectionFactor = 1.0
        ch.ChannelBaseline = 0.0
        ch.WaveformBitsStored = 16
        channels.append(ch)
    wf.ChannelDefinitionSequence = Sequence(channels)
    uv = np.clip(np.round(signals_mv * 1000), -32768, 32767).astype("<i2")
    wf.WaveformData = uv.T.tobytes()                      # interleaved: sample-major
    ds.WaveformSequence = Sequence([wf])

    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    return buf.getvalue()
