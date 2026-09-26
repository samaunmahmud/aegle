"""Decode and draw ECG waveforms.

Accepted inputs:
  * DICOM waveform objects (e.g. 12-Lead ECG Waveform Storage), as ECG carts and PACS send
  * CSV: one column per lead with a header row of lead names, optionally preceded by
    "# fs=<Hz>" and "# units=mV|uV" comment lines (defaults 500 Hz, mV)

Like imaging.py, only signal data is read; patient tags are never touched or logged.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
MAX_BYTES = 50 * 1024 * 1024
MAX_SECONDS = 600


class UnsupportedWaveform(ValueError):
    """The upload could not be decoded as a supported ECG."""


@dataclass(frozen=True)
class Waveform:
    signals: np.ndarray      # (12, samples) in millivolts, rows in LEADS order
    fs: float                # samples per second

    @property
    def seconds(self) -> float:
        return self.signals.shape[1] / self.fs


def _lead_name(text: str) -> str | None:
    """'Lead I (Einthoven)', 'Lead aVR', 'V1', 'lead_ii' -> the standard name, or None."""
    t = re.sub(r"\(.*?\)", "", text).replace("Lead", "").replace("lead", "").strip(" _-").upper()
    for name in LEADS:
        if t == name.upper():
            return name
    return None


def _assemble(columns: dict[str, np.ndarray], fs: float) -> Waveform:
    missing = [l for l in LEADS if l not in columns]
    if missing:
        raise UnsupportedWaveform(f"A 12-lead ECG is required; missing leads: {', '.join(missing)}")
    signals = np.stack([columns[l] for l in LEADS]).astype(np.float32)
    if not np.isfinite(signals).all():
        raise UnsupportedWaveform("ECG contains non-numeric samples")
    if not 50 <= fs <= 10_000:
        raise UnsupportedWaveform("Unsupported sampling rate")
    if signals.shape[1] < fs * 2 or signals.shape[1] > fs * MAX_SECONDS:
        raise UnsupportedWaveform("ECG must be between 2 seconds and 10 minutes long")
    return Waveform(signals, float(fs))


def _decode_dicom(data: bytes) -> Waveform:
    import pydicom

    try:
        ds = pydicom.dcmread(io.BytesIO(data))
        seq = ds.WaveformSequence[0]
        arr = ds.waveform_array(0)            # (samples, channels), sensitivity applied
    except Exception as exc:
        raise UnsupportedWaveform("Could not read DICOM waveform data") from exc
    columns = {}
    for i, ch in enumerate(seq.ChannelDefinitionSequence):
        name = _lead_name(str(ch.ChannelSourceSequence[0].CodeMeaning))
        if name is None or name in columns:
            continue
        units = str(getattr(ch.ChannelSensitivityUnitsSequence[0], "CodeValue", "uV")) \
            if "ChannelSensitivityUnitsSequence" in ch else "uV"
        scale = {"uV": 1e-3, "mV": 1.0, "V": 1e3}.get(units, 1e-3)
        columns[name] = arr[:, i].astype(np.float32) * scale
    return _assemble(columns, float(seq.SamplingFrequency))


def _decode_csv(data: bytes) -> Waveform:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnsupportedWaveform("CSV must be UTF-8 text") from exc
    fs, scale, header, rows = 500.0, 1.0, None, []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            for key, value in re.findall(r"(\w+)\s*=\s*([\w.]+)", line):
                if key.lower() == "fs":
                    fs = float(value)
                elif key.lower() == "units":
                    scale = {"uv": 1e-3, "mv": 1.0}.get(value.lower(), 1.0)
            continue
        cells = [c.strip() for c in line.split(",")]
        if header is None:
            header = cells
            continue
        rows.append(cells)
    if header is None or not rows:
        raise UnsupportedWaveform("CSV needs a header row of lead names and samples")
    try:
        values = np.array(rows, dtype=np.float32) * scale
    except ValueError as exc:
        raise UnsupportedWaveform("CSV contains non-numeric samples") from exc
    columns = {}
    for i, h in enumerate(header):
        name = _lead_name(h)
        if name is not None and name not in columns:
            columns[name] = values[:, i]
    return _assemble(columns, fs)


def is_waveform(data: bytes) -> bool:
    """True for DICOM waveform objects and ECG CSVs (cheap check, no full decode)."""
    if len(data) > 132 and data[128:132] == b"DICM":
        import pydicom
        try:
            ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True)
        except Exception:
            return False
        return "WaveformSequence" in ds
    head = data[:2048]
    try:
        first = next(l for l in head.decode("utf-8").splitlines() if l.strip() and not l.startswith("#"))
    except (UnicodeDecodeError, StopIteration):
        return False
    names = {_lead_name(c) for c in first.split(",")}
    return {"I", "II", "V1"} <= names


def decode_waveform(data: bytes) -> Waveform:
    if not data:
        raise UnsupportedWaveform("Empty upload")
    if len(data) > MAX_BYTES:
        raise UnsupportedWaveform("File too large")
    if len(data) > 132 and data[128:132] == b"DICM":
        return _decode_dicom(data)
    return _decode_csv(data)


def resample(w: Waveform, fs: float, seconds: float) -> np.ndarray:
    """(12, fs*seconds) at the target rate: linear interpolation, first `seconds`, zero-padded."""
    n = int(round(fs * seconds))
    t_src = np.arange(w.signals.shape[1]) / w.fs
    t_dst = np.arange(n) / fs
    out = np.zeros((len(LEADS), n), dtype=np.float32)
    valid = t_dst <= t_src[-1]
    for i in range(len(LEADS)):
        out[i, valid] = np.interp(t_dst[valid], t_src, w.signals[i])
    return out


# ---------------------------------------------------------------- rendering
PX_PER_MM = 4
MM_PER_S = 25          # paper speed
MM_PER_MV = 10         # gain
ROW_MM = 18
LEFT_MM = 12


def render(w: Waveform, seconds: float = 10.0, saliency: np.ndarray | None = None) -> bytes:
    """Draw the 12 leads on standard ECG paper (25 mm/s, 10 mm/mV) as a PNG.

    `saliency`, values in [0, 1] over the drawn time span, shades the background where
    the model looked; the image size and trace are identical with or without it, so the
    two can be overlaid.
    """
    sig = resample(w, fs=250.0, seconds=min(seconds, w.seconds))
    width_mm = LEFT_MM + seconds * MM_PER_S + 4
    height_mm = ROW_MM * len(LEADS) + 6
    W, H = int(width_mm * PX_PER_MM), int(height_mm * PX_PER_MM)
    img = Image.new("RGB", (W, H), (255, 250, 250))
    d = ImageDraw.Draw(img)

    x0 = LEFT_MM * PX_PER_MM
    if saliency is not None:
        s = np.clip(np.asarray(saliency, dtype=np.float32), 0, 1)
        cols = np.interp(np.linspace(0, 1, W - x0), np.linspace(0, 1, len(s)), s)
        for i, v in enumerate(cols):
            if v > 0.15:
                a = float(v)
                d.line([(x0 + i, 0), (x0 + i, H)], fill=(255, int(250 - 120 * a), int(250 - 200 * a)))

    for mm in range(int(width_mm) + 1):                       # 1 mm and 5 mm grid
        x = mm * PX_PER_MM
        d.line([(x, 0), (x, H)], fill=(240, 180, 180) if mm % 5 == 0 else (250, 222, 222),
               width=1)
    for mm in range(int(height_mm) + 1):
        y = mm * PX_PER_MM
        d.line([(0, y), (W, y)], fill=(240, 180, 180) if mm % 5 == 0 else (250, 222, 222), width=1)

    px_per_sample = MM_PER_S * PX_PER_MM / 250.0
    for row, lead in enumerate(LEADS):
        base = (3 + ROW_MM * row + ROW_MM / 2) * PX_PER_MM
        d.text((6, base - 14), lead, fill=(40, 40, 40))
        # 1 mV calibration pulse
        cal = [(x0 - 28, base), (x0 - 24, base), (x0 - 24, base - MM_PER_MV * PX_PER_MM),
               (x0 - 12, base - MM_PER_MV * PX_PER_MM), (x0 - 12, base), (x0 - 8, base)]
        d.line(cal, fill=(20, 20, 20), width=1)
        y = base - np.clip(sig[row], -ROW_MM / MM_PER_MV, ROW_MM / MM_PER_MV) * MM_PER_MV * PX_PER_MM
        pts = [(x0 + i * px_per_sample, float(v)) for i, v in enumerate(y)]
        d.line(pts, fill=(15, 15, 15), width=2)

    d.text((x0, H - 14), f"{MM_PER_S} mm/s  {MM_PER_MV} mm/mV  {w.fs:g} Hz", fill=(90, 90, 90))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
