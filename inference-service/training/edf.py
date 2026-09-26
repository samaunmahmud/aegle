"""Write EDF files (European Data Format), for tests and demo recordings."""
from __future__ import annotations

import numpy as np


def write_edf(signals_uv: np.ndarray, labels: list[str], fs: int, record_seconds: int = 1) -> bytes:
    """`signals_uv`: (channels, samples) in microvolts; samples must be a multiple of fs*record_seconds."""
    ns, n = signals_uv.shape
    spr = fs * record_seconds
    n_records = n // spr
    pmin, pmax, dmin, dmax = -3276.8, 3276.7, -32768, 32767

    def f(values, width):
        return "".join(str(v)[:width].ljust(width) for v in values).encode("ascii")

    header = (b"0       " + f(["X X X X"], 80) + f(["Startdate X X X X"], 80) + b"01.01.00" + b"00.00.00"
              + f([256 + 256 * ns], 8) + f([""], 44) + f([n_records], 8) + f([record_seconds], 8) + f([ns], 4))
    header += (f(labels, 16) + f([""] * ns, 80) + f(["uV"] * ns, 8) + f([pmin] * ns, 8) + f([pmax] * ns, 8)
               + f([dmin] * ns, 8) + f([dmax] * ns, 8) + f([""] * ns, 80) + f([spr] * ns, 8) + f([""] * ns, 32))
    digital = np.clip(np.round((signals_uv - pmin) / (pmax - pmin) * (dmax - dmin) + dmin), dmin, dmax)
    digital = digital[:, : n_records * spr].astype("<i2").reshape(ns, n_records, spr).transpose(1, 0, 2)
    return header + digital.tobytes()
