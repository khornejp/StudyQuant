"""Causal 7-sleeve regime router (Codex information-sufficiency check after the G3-only RL branch was stopped).

At each hourly decision T the score of sleeve s is its canonical unit net4 over the lookback window (minutes closed
before T, availability epoch only: allocator_state.sleeve_channels mtm_<lookback>). Among sleeves available at T the
two with the largest strictly positive scores get entry level 1.0, every other sleeve OFF; pending KEEP, open HOLD
(no exits, no tighten). The env (shadow canonical ledger, 4 bps maker, gross cap 2.0) executes the levels."""
from __future__ import annotations
import numpy as np
from . import allocator_contracts as C

LOOKBACKS = {"30d": "mtm_30d", "90d": "mtm_90d", "180d": "mtm_180d"}
TOP_K = 2


def router_levels(scores: np.ndarray, avail: np.ndarray, k: int = TOP_K) -> np.ndarray:
    """scores [N, 7] (NaN = unknown), avail [N, 7] bool -> entry level indices [N, 7] (4 = 1.0, 0 = OFF).
    Ties are broken by sleeve order (stable)."""
    s = np.where(avail & np.isfinite(scores) & (scores > 0), scores, -np.inf)
    order = np.argsort(-s, axis=1, kind="stable")[:, :k]
    out = np.zeros(scores.shape, np.int64)
    rows = np.arange(len(s))[:, None]
    pick = np.isfinite(s[rows, order])
    out[rows, order] = np.where(pick, C.LEVELS.index(1.0), 0)
    return out
