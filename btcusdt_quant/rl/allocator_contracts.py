"""RL allocator contracts (Codex design 2026-10-10 sections 1, 3, 4; freeze.json + amendment A1; Codex round-2 env
spec). Pure functions and constants shared by the env, baselines and tests; no data access."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

SLEEVES = ("G3_LONG", "G3_SHORT", "LBR_FUND", "B3_AXC0", "K04_AXC0", "C1v2", "C4v2")
G3_FAMILY = ("G3_LONG", "G3_SHORT", "LBR_FUND")
NATIVE = ("B3_AXC0", "K04_AXC0", "C1v2", "C4v2")
TIGHTEN_SLEEVES = ("B3_AXC0", "K04_AXC0")              # sleeves with an R0 stop (R2-52A adaptive exit)
KIND = {s: ("lin" if s in G3_FAMILY else "log") for s in SLEEVES}
CELLS = ("o2_p0.5", "o2_p1.0", "o2_p2.0", "o5_p0.5", "o5_p1.0", "o5_p2.0")
CELL_PEN = {c: float(c.split("_p")[1]) for c in CELLS}

LEVELS = (0.0, 0.25, 0.50, 0.75, 1.00)                # entry head: OFF, 0.25, 0.50, 0.75, 1.00
PENDING_ACTIONS = ("KEEP", "CANCEL")
OPEN_ACTIONS = ("HOLD", "TIGHTEN_75", "TIGHTEN_50", "EXIT")
TIGHTEN_F = {"TIGHTEN_75": 0.75, "TIGHTEN_50": 0.50}
GROSS_CAP = 2.0
FEE_SIDE_BPS = 2.0                                     # maker 2 bps per side (4 bps round trip), slippage 0
DD_PENALTY, TURNOVER_PENALTY = 0.10, 0.25              # [가설] frozen before TEST (design section 3)
SEQ_LEN = 32
SEQ_COLUMNS = ("ret_1h", "range_1h", "logvol_1h", "taker_share_1h") + tuple(f"{s}_net4_1h" for s in SLEEVES)
N_STATIC = 453                                         # 204 scaled + 204 NaN masks + 45 unscaled (state manifest)
ACCOUNT_CHANNELS = ("alloc_mult", "alloc_exposure", "pending_alloc", "tighten_f")


@dataclass(frozen=True)
class Action:
    """One allocator decision for all sleeves (indices into LEVELS / PENDING_ACTIONS / OPEN_ACTIONS)."""
    entry: tuple
    pending: tuple
    open: tuple

    @staticmethod
    def hold(level_idx=None) -> "Action":
        e = tuple(level_idx) if level_idx is not None else (0,) * len(SLEEVES)
        return Action(e, (0,) * len(SLEEVES), (0,) * len(SLEEVES))


@dataclass
class Masks:
    entry: np.ndarray = field(default_factory=lambda: np.zeros((len(SLEEVES), len(LEVELS)), bool))
    pending: np.ndarray = field(default_factory=lambda: np.zeros((len(SLEEVES), len(PENDING_ACTIONS)), bool))
    open: np.ndarray = field(default_factory=lambda: np.zeros((len(SLEEVES), len(OPEN_ACTIONS)), bool))


def sleeve_masks(available: bool, has_pending: bool, has_open: bool, sleeve: str, tighten_f: float):
    """Per-sleeve legal actions. Unavailable: entry OFF only, pending KEEP only, open HOLD only (previous-epoch
    positions untouched). Tighten only for R0 sleeves and only to a smaller fraction (no widening)."""
    entry = np.zeros(len(LEVELS), bool)
    entry[0] = True
    if available:
        entry[:] = True
    pend = np.array([True, available and has_pending])
    op = np.zeros(len(OPEN_ACTIONS), bool)
    op[0] = True
    if available and has_open:
        op[OPEN_ACTIONS.index("EXIT")] = True
        if sleeve in TIGHTEN_SLEEVES:
            op[OPEN_ACTIONS.index("TIGHTEN_75")] = tighten_f > 0.75
            op[OPEN_ACTIONS.index("TIGHTEN_50")] = tighten_f > 0.50
    return entry, pend, op


def validate_action(action: Action, masks: Masks) -> None:
    """Integer indices in range, then legality under the masks (masked or malformed actions raise)."""
    for name in ("entry", "pending", "open"):
        raw = np.asarray(getattr(action, name))
        m = getattr(masks, name)
        if raw.shape != (len(SLEEVES),) or not np.issubdtype(raw.dtype, np.integer):
            raise ValueError(f"{name}: need {len(SLEEVES)} integer indices, got {raw.dtype} {raw.shape}")
        if np.any(raw < 0) or np.any(raw >= m.shape[1]):
            raise ValueError(f"{name}: index out of range {raw.tolist()}")
        ok = m[np.arange(len(SLEEVES)), raw]
        if not ok.all():
            raise ValueError(f"masked {name} action for {[SLEEVES[k] for k in np.flatnonzero(~ok)]}")


def validate_static_weights(w) -> np.ndarray:
    """Static baseline weights: shape (7,), finite, each in [0, 1], sum <= gross cap; None -> all zero."""
    if w is None:
        return np.zeros(len(SLEEVES))
    a = np.asarray(w, float)
    if a.shape != (len(SLEEVES),) or not np.isfinite(a).all() or np.any(a < 0) or np.any(a > 1)             or a.sum() > GROSS_CAP + 1e-12:
        raise ValueError(f"invalid static weights {w}")
    return a


def reserved_at(e: int, end: int, expiry: int, tau: int) -> bool:
    """Opportunity occupies cap at minute tau: filled -> until its exit minute (an exit at tau releases the cap for
    entries at tau, e.g. a same-minute reversal); unfilled -> while its order still rests (expiry >= tau)."""
    return (end > tau) if e >= 0 else (expiry >= tau)


def project_cap(existing_gross: float, requested: np.ndarray, cap: float = GROSS_CAP) -> np.ndarray:
    """Gross cap projector: existing open/pending exposure keeps priority; simultaneous new entries (|requested|)
    are scaled pro rata into the remaining cap (never below 0)."""
    req = np.abs(np.asarray(requested, float))
    room = max(cap - existing_gross, 0.0)
    tot = req.sum()
    if tot <= room or tot == 0:
        return np.ones(len(req))
    return np.full(len(req), room / tot)


def step_reward(d_rl: float, d_st: float, dmdd_rl: float, dmdd_st: float, to_rl: float, to_st: float) -> float:
    """Design section 3 (bps): excess net minus 0.10 x excess drawdown growth minus 0.25 x excess turnover (bps of
    traded notional at the 2 bps side fee). Identical books give exactly 0."""
    return (d_rl - d_st) - DD_PENALTY * max(0.0, dmdd_rl - dmdd_st) - TURNOVER_PENALTY * max(0.0, to_rl - to_st)


def static_action(weights, masks: Masks) -> Action:
    """RL action equal to a LEVELS-valued static baseline: entry level = frozen weight (OFF where masked), pending
    KEEP, open HOLD. (The env's static book applies any weights in [0, 1] directly.)"""
    lv = [LEVELS.index(float(w)) for w in weights]
    entry = tuple(l if masks.entry[k, l] else 0 for k, l in enumerate(lv))
    return Action(entry, (0,) * len(SLEEVES), (0,) * len(SLEEVES))
