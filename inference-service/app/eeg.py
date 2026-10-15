"""Read and draw scalp EEG (EDF files).

The European Data Format is the usual EEG export. Only signal headers and samples are
read; the header's patient and recording identification fields are skipped, never
decoded or logged.

Signals are brought to the 18-channel longitudinal bipolar ("double banana") montage,
directly when the file is already bipolar or by subtracting electrodes when it is
referential, and resampled to FS Hz.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

MONTAGE = ["FP1-F7", "F7-T7", "T7-P7", "P7-O1", "FP1-F3", "F3-C3", "C3-P3", "P3-O1",
           "FP2-F4", "F4-C4", "C4-P4", "P4-O2", "FP2-F8", "F8-T8", "T8-P8", "P8-O2", "FZ-CZ", "CZ-PZ"]
FS = 128.0
MAX_BYTES = 100 * 1024 * 1024
# Older 10-20 names for the same temporal electrodes.
ALIASES = {"T3": "T7", "T4": "T8", "T5": "P7", "T6": "P8"}


class UnsupportedEeg(ValueError):
    """The upload could not be read as a scalp EEG."""


@dataclass(frozen=True)
class Eeg:
    signals: np.ndarray      # (18, samples) in microvolts, rows in MONTAGE order, at FS
    fs: float = FS

    @property
    def seconds(self) -> float:
        return self.signals.shape[1] / self.fs


def is_edf(data: bytes) -> bool:
    return len(data) >= 256 and data[:8] == b"0       "


def _field(block: bytes, n: int, width: int) -> list[str]:
    return [block[i * width:(i + 1) * width].decode("ascii", "replace").strip() for i in range(n)]


def _electrode(label: str) -> str:
    """'EEG Fp1-REF', 'FP1-LE', 'Fp1' -> 'FP1' (referential electrode name)."""
    name = re.sub(r"^(EEG|EKG|ECG)\s+", "", label.upper())
    name = re.sub(r"-(REF|LE|AR|AVG|A1|A2|M1|M2)$", "", name).strip()
    return ALIASES.get(name, name)


def _bipolar(label: str) -> str | None:
    """'FP1-F7', 'T8-P8-0', 'EEG T3-T5' -> montage name, or None if not a bipolar pair."""
    m = re.match(r"^(?:EEG\s+)?([A-Z0-9]+)-([A-Z0-9]+)(?:-\d+)?$", label.upper().strip())
    if not m:
        return None
    a, b = ALIASES.get(m.group(1), m.group(1)), ALIASES.get(m.group(2), m.group(2))
    return f"{a}-{b}"


def read_edf(data: bytes) -> Eeg:
    if not is_edf(data):
        raise UnsupportedEeg("Not an EDF file")
    if len(data) > MAX_BYTES:
        raise UnsupportedEeg("File too large")
    try:
        header_bytes = int(data[184:192])
        n_records = int(data[236:244])
        duration = float(data[244:252])
        ns = int(data[252:256])
        h = data[256:header_bytes]
        labels = _field(h, ns, 16)
        off = ns * (16 + 80)
        units = _field(h[off:], ns, 8); off += ns * 8
        pmin = np.array(_field(h[off:], ns, 8), float); off += ns * 8
        pmax = np.array(_field(h[off:], ns, 8), float); off += ns * 8
        dmin = np.array(_field(h[off:], ns, 8), float); off += ns * 8
        dmax = np.array(_field(h[off:], ns, 8), float); off += ns * 8
        off += ns * 80
        spr = np.array(_field(h[off:], ns, 8), int)
    except (ValueError, IndexError) as exc:
        raise UnsupportedEeg("Corrupt EDF header") from exc
    if n_records <= 0 or duration <= 0 or ns <= 0:
        raise UnsupportedEeg("EDF has no data records")

    record = int(spr.sum())
    raw = np.frombuffer(data, dtype="<i2", offset=header_bytes, count=n_records * record)
    if raw.size < n_records * record:
        raise UnsupportedEeg("EDF is truncated")
    raw = raw.reshape(n_records, record)
    starts = np.concatenate([[0], np.cumsum(spr)])
    gain = (pmax - pmin) / np.where(dmax - dmin == 0, 1, dmax - dmin)

    channels: dict[str, tuple[np.ndarray, float]] = {}
    for i, label in enumerate(labels):
        fs = spr[i] / duration
        if fs < 64:
            continue                                  # annotations, oximetry, markers
        x = (raw[:, starts[i]:starts[i + 1]].reshape(-1).astype(np.float32) - dmin[i]) * gain[i] + pmin[i]
        scale = {"MV": 1000.0, "V": 1e6, "NV": 1e-3}.get(units[i].upper(), 1.0)   # to microvolts
        channels.setdefault(label, (x * scale, fs))

    bipolar = {_bipolar(l): v for l, v in channels.items() if _bipolar(l)}
    referential = {_electrode(l): v for l, v in channels.items()}
    rows = []
    for pair in MONTAGE:
        if pair in bipolar:
            x, fs = bipolar[pair]
        else:
            a, b = pair.split("-")
            if a not in referential or b not in referential:
                raise UnsupportedEeg(f"EEG lacks channel {pair} (needs the 10-20 electrodes)")
            (xa, fs), (xb, _) = referential[a], referential[b]
            x = xa - xb
        rows.append(_resample(x, fs, FS))
    n = min(len(r) for r in rows)
    signals = np.stack([r[:n] for r in rows])
    if n < FS * 10:
        raise UnsupportedEeg("EEG must be at least 10 seconds long")
    return Eeg(signals.astype(np.float32))


def _resample(x: np.ndarray, fs: float, target: float) -> np.ndarray:
    if fs == target:
        return x
    if fs % target == 0:                                  # e.g. 256 -> 128: average, anti-aliased
        k = int(fs // target)
        return x[: len(x) // k * k].reshape(-1, k).mean(axis=1)
    t = np.arange(int(len(x) * target / fs)) / target
    return np.interp(t, np.arange(len(x)) / fs, x)


def windows(eeg: Eeg, seconds: float = 8.0, stride: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    """Model input: (n, 18, seconds*FS) scaled to ~unit range, and each window's start (s)."""
    w, s = int(seconds * eeg.fs), int(stride * eeg.fs)
    starts = np.arange(0, eeg.signals.shape[1] - w + 1, s)
    x = np.stack([eeg.signals[:, i:i + w] for i in starts]) / 100.0
    return np.clip(x, -10, 10).astype(np.float32), starts / eeg.fs


# ---------------------------------------------------------------- rendering
PX_PER_MM = 4
MM_PER_S = 30
UV_PER_MM = 7
ROW_MM = 12
LEFT_MM = 16
TIMELINE_PX = 70
PAGE_S = 10.0


def render(eeg: Eeg, page_start: float = 0.0, probabilities: np.ndarray | None = None,
           window_starts: np.ndarray | None = None, window_seconds: float = 8.0,
           label: str = "Seizure probability") -> bytes:
    """A 10 s page of the 18-channel montage (30 mm/s, 7 uV/mm) as PNG. With model output, a
    timeline across the whole recording is drawn on top and the page's windows are shaded."""
    page_start = float(np.clip(page_start, 0, max(0.0, eeg.seconds - PAGE_S)))
    width_mm = LEFT_MM + PAGE_S * MM_PER_S + 4
    W = int(width_mm * PX_PER_MM)
    H = TIMELINE_PX + int((ROW_MM * len(MONTAGE) + 8) * PX_PER_MM)
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    x0 = LEFT_MM * PX_PER_MM

    # Timeline of the whole recording.
    d.rectangle([0, 0, W, TIMELINE_PX - 1], fill=(246, 248, 251))
    # Without model output this is the plain recording view; the study page shows the analysis
    # separately ("AI view"), so say where it is rather than suggest it never ran.
    d.text((6, 6), label if probabilities is not None else "Recording, first 10 s (analysis: see AI view)",
           fill=(60, 60, 60))
    tl = (x0, 22, W - 8, TIMELINE_PX - 10)
    d.rectangle(tl, outline=(200, 205, 212))
    if probabilities is not None and window_starts is not None and len(probabilities):
        span = max(eeg.seconds, 1e-6)
        for p, s in zip(probabilities, window_starts):
            xa = tl[0] + (s / span) * (tl[2] - tl[0])
            xb = tl[0] + ((s + window_seconds) / span) * (tl[2] - tl[0])
            top = tl[3] - p * (tl[3] - tl[1])
            d.rectangle([xa, top, max(xa + 1, xb), tl[3]], fill=(214, 64, 49) if p >= 0.5 else (120, 150, 190))
    pa = tl[0] + page_start / max(eeg.seconds, 1e-6) * (tl[2] - tl[0])
    pb = tl[0] + (page_start + PAGE_S) / max(eeg.seconds, 1e-6) * (tl[2] - tl[0])
    d.rectangle([pa, tl[1] - 3, max(pa + 2, pb), tl[3] + 3], outline=(10, 95, 180), width=2)
    d.text((tl[0], TIMELINE_PX - 9), "0 s", fill=(90, 90, 90))
    d.text((tl[2] - 60, TIMELINE_PX - 9), f"{eeg.seconds:.0f} s", fill=(90, 90, 90))

    # Shade the page where the model's windows were positive.
    y_top = TIMELINE_PX
    if probabilities is not None and window_starts is not None:
        for p, s in zip(probabilities, window_starts):
            if p < 0.5 or s + window_seconds < page_start or s > page_start + PAGE_S:
                continue
            xa = x0 + max(0.0, s - page_start) * MM_PER_S * PX_PER_MM
            xb = x0 + min(PAGE_S, s + window_seconds - page_start) * MM_PER_S * PX_PER_MM
            d.rectangle([xa, y_top, xb, H], fill=(255, 236, 230))

    for s in range(int(PAGE_S) + 1):                      # one line per second
        x = x0 + s * MM_PER_S * PX_PER_MM
        d.line([(x, y_top), (x, H)], fill=(225, 228, 233), width=1)

    a = int(page_start * eeg.fs)
    page = eeg.signals[:, a:a + int(PAGE_S * eeg.fs)]
    px_per_sample = MM_PER_S * PX_PER_MM / eeg.fs
    for row, name in enumerate(MONTAGE):
        base = y_top + (4 + ROW_MM * row + ROW_MM / 2) * PX_PER_MM
        d.text((4, base - 6), name, fill=(40, 40, 40))
        y = base - np.clip(page[row] / UV_PER_MM, -ROW_MM, ROW_MM) * PX_PER_MM
        d.line([(x0 + i * px_per_sample, float(v)) for i, v in enumerate(y)], fill=(20, 20, 20), width=1)
    d.text((x0, H - 14), f"{page_start:.0f}-{page_start + PAGE_S:.0f} s  {MM_PER_S} mm/s  {UV_PER_MM} uV/mm",
           fill=(90, 90, 90))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
