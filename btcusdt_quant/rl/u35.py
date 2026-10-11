"""35-sleeve universe (Codex A3 design 2026-10-11): the 32 paper books of config/paper.toml in their configured order
(x3 overlays excluded) + LBR_FUND, C1v2, C4v2. Every variant is its own sleeve. Families (9) follow the research
catalog Spec.family (btcusdt_quant/sim/strategies), with G3 / LBR split out; legacy.py holds K01 / K01_FLIP
("baseline"), B1/B2/B3 ("composite"), K02/K03 ("reversion") and K04/K05 ("volatility"); K19 lives in futures.py but is
registered as "reversion".

DEV-only research context for the AX books: minutes / funding from rl.dev_data (no 2026 file or row is used),
metrics and premium archives with a file-day cutoff, model predictions read with an open-time predicate, and the sim
funding settlements replaced by the DEV funding table for the duration of the run."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PAPER_BOOKS = ("C1_AX", "B1_AX", "B2_AX", "B3_AX", "K02_AX", "K03_AX", "K04_AX", "K05_AX", "K06_k0.5_AX",
               "K06_k1.0_AX", "K07_k0.5_AX", "K07_k1.0_AX", "K08_AX", "K09_AX", "K11_15m_AX", "K11_1h_AX",
               "K12_30m_AX", "K12_1h_AX", "K13_AX", "K14_AX", "K15_AX", "K19_AX", "K21_A_AX", "K21_B_AX", "K26_AX",
               "K29_AX", "K30_AX", "C1_FLIP_AX", "B3_AXC0", "K04_AXC0", "G3_LONG", "G3_SHORT")
RESEARCH = ("LBR_FUND", "C1v2", "C4v2")
UNIVERSE = PAPER_BOOKS + RESEARCH
EXISTING7 = ("G3_LONG", "G3_SHORT", "LBR_FUND", "B3_AXC0", "K04_AXC0", "C1v2", "C4v2")
AX_NEW = tuple(b for b in PAPER_BOOKS if b.endswith("_AX"))           # 28 books built here
SPEC_ID = {b: ("K01" if b == "C1_AX" else "K01_FLIP" if b == "C1_FLIP_AX" else b[:-3]) for b in AX_NEW}
SELECTED_K = {b: ROOT / ("out/k45_rl_r2_48_20261007/r2_52a_flip/selected_k.csv" if b == "C1_FLIP_AX"
                         else "out/k45_rl_r2_48_20261007/r2_52a/selected_k.csv") for b in AX_NEW}
REF_TRADES = {b: ROOT / ("out/k45_rl_r2_48_20261007/" + ("r2_52a_flip" if b == "C1_FLIP_AX" else "r2_52a")
                         + f"/trades_ax/{SPEC_ID[b]}.parquet") for b in AX_NEW}
REF_DAILY = {b: Path(str(p).replace("trades_ax", "daily")) for b, p in REF_TRADES.items()}
FAMILIES = ("G3", "LBR", "baseline", "composite", "reversion", "volatility", "trend", "futures", "levels")
FAMILY = {"G3_LONG": "G3", "G3_SHORT": "G3", "LBR_FUND": "LBR",
          "C1_AX": "baseline", "C1_FLIP_AX": "baseline", "C1v2": "baseline", "C4v2": "baseline",
          "B1_AX": "composite", "B2_AX": "composite", "B3_AX": "composite", "B3_AXC0": "composite",
          "K02_AX": "reversion", "K03_AX": "reversion", "K09_AX": "reversion", "K15_AX": "reversion",
          "K19_AX": "reversion",
          "K04_AX": "volatility", "K04_AXC0": "volatility", "K05_AX": "volatility", "K06_k0.5_AX": "volatility",
          "K06_k1.0_AX": "volatility", "K07_k0.5_AX": "volatility", "K07_k1.0_AX": "volatility",
          "K08_AX": "volatility",
          "K11_15m_AX": "trend", "K11_1h_AX": "trend", "K12_30m_AX": "trend", "K12_1h_AX": "trend",
          "K13_AX": "trend", "K14_AX": "trend",
          "K21_A_AX": "futures", "K21_B_AX": "futures",
          "K26_AX": "levels", "K29_AX": "levels", "K30_AX": "levels"}
AX_START = pd.Timestamp("2023-09-01", tz="UTC")                        # first rolling test window (W01)
DEV_END = pd.Timestamp("2026-01-01", tz="UTC")
assert len(UNIVERSE) == 35 and set(FAMILY) == set(UNIVERSE) and set(FAMILY.values()) == set(FAMILIES)


def catalog_family(book: str) -> str | None:
    """Research catalog family of an AX book's source id (None for non-catalog sleeves)."""
    from btcusdt_quant.sim.strategies import CATALOG
    return CATALOG[SPEC_ID[book]].family if book in SPEC_ID else None


def dev_predictions(end: pd.Timestamp = DEV_END) -> pd.DataFrame:
    """sim.data.load_predictions restricted to the DEV segments, rows read with timestamp < end."""
    from btcusdt_quant.sim import data
    segs = [s for s, st in data.SEGMENT_STARTS.items() if pd.Timestamp(st, tz="UTC") < end]
    paths = sorted(p for s in segs for p in (Path(data.PREDICTIONS_DIR) / s).glob("fold_*_predictions.parquet"))
    cols = ["timestamp", "retrain_time", "segment"] + [f"prediction_{t}" for t in data.TARGETS]
    f = pd.concat([pd.read_parquet(p, columns=cols, filters=[("timestamp", "<", end.to_pydatetime())])
                   for p in paths], ignore_index=True)
    for c in ("timestamp", "retrain_time"):
        f[c] = pd.to_datetime(f[c], utc=True)
    if (f.timestamp >= end).any():
        raise RuntimeError("prediction rows at/after the DEV end")
    return data.validate_predictions(f.sort_values("timestamp").reset_index(drop=True)), [str(p) for p in paths]


EIGHT_H = 8 * 3600 * 10**9


def scheduled(funding: pd.DataFrame) -> pd.DataFrame:
    """DEV funding rows (raw calc_time) snapped to the 00/08/16 UTC settlement as out/k45_funding.load_settlements
    does (|error| <= 60 s enforced)."""
    raw = funding.time.array.asi8.astype(np.int64)
    sch = ((raw + EIGHT_H // 2) // EIGHT_H) * EIGHT_H
    if np.any(np.abs(raw - sch) > 60 * 10**9):
        raise ValueError("funding timestamp beyond 60 s of its 8h settlement")
    return pd.DataFrame({"time": pd.to_datetime(sch, utc=True), "rate": funding.rate.to_numpy(float)})


def assert_settlement_grid(f: pd.DataFrame) -> pd.DataFrame:
    """Fail closed before any settlement array is built: every time on 00/08/16 UTC with zero seconds / sub-seconds,
    strictly increasing (no duplicate), and before the TEST start."""
    t = f.time.array.asi8.astype(np.int64)
    if len(t) == 0 or np.any(t % EIGHT_H != 0):
        raise ValueError("funding settlement off the 00/08/16 UTC grid (seconds / ms not zero)")
    if np.any(np.diff(t) <= 0):
        raise ValueError("funding settlements duplicated or unsorted")
    if int(t.max()) >= DEV_END.value:
        from .sleeve_precompute import TestAccessError
        raise TestAccessError("TEST-period funding settlement in the DEV table")
    return f


def _refuse_full_folder():
    from .sleeve_precompute import TestAccessError
    raise TestAccessError("sim.costs._settlements opens artifacts/funding_2020_2026h1 (2026 months included): refused; "
                          "use u35.dev_settlements")


@contextmanager
def no_full_settlements():
    """For a whole DEV run: any sim funding lookup outside dev_settlements raises before any file I/O."""
    from btcusdt_quant.sim import costs
    old = costs._settlements
    costs._settlements = _refuse_full_folder
    costs._settlement_arrays.cache_clear()
    try:
        yield
    finally:
        costs._settlements = old
        costs._settlement_arrays.cache_clear()


@contextmanager
def dev_settlements(funding: pd.DataFrame):
    """Replace the sim funding settlements (artifacts/funding_2020_2026h1, 2026 months included) by the DEV table
    snapped to the settlement schedule and checked by assert_settlement_grid."""
    from btcusdt_quant.sim import costs
    old = costs._settlements
    f = assert_settlement_grid(scheduled(funding))
    costs._settlements = lambda: f
    costs._settlement_arrays.cache_clear()
    try:
        yield
    finally:
        costs._settlements = old
        costs._settlement_arrays.cache_clear()


def dev_context():
    """-> (Context, DEV funding frame, input hashes); every input strictly before 2026-01-01."""
    from btcusdt_quant.sim import data, regime
    from btcusdt_quant.sim.strategies import Context
    from . import dev_data as DD
    minutes, funding, hashes = DD.load_dev()
    metrics = data.load_metrics(end=DEV_END)
    premium = data.load_premium(end=DEV_END)
    preds, ppaths = dev_predictions()
    ctx = Context(minutes=minutes, metrics=metrics, premium=premium, funding=funding.copy(),
                  regime=regime.load_regime(preds), end=DEV_END).truncate(DEV_END)
    hashes.update(metrics_files=len(data.archive_files(data.METRICS_DIR, DEV_END)),
                  premium_files=len(data.archive_files(data.PREMIUM_DIR, DEV_END)), prediction_files=ppaths,
                  prediction_rows=int(len(preds)), prediction_last=str(preds.timestamp.max()))
    return ctx, funding, hashes


def k_picks(book: str) -> dict:
    """Rolling k per test window W01..W10 from the research selection (each chosen on its own pre-window validation)."""
    s = pd.read_csv(SELECTED_K[book])
    s = s[s.id == SPEC_ID[book]]
    return dict(zip(s.window, s.k.astype(float)))
