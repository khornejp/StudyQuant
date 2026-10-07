from __future__ import annotations
import importlib.util, math, sys
from functools import lru_cache
from pathlib import Path
from typing import Callable
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEE_BPS_PER_SIDE = 2.0

@lru_cache(maxsize=1)
def _funding_module():
    spec = importlib.util.spec_from_file_location("k45_funding", ROOT / "out/k45_funding.py")
    module = importlib.util.module_from_spec(spec); sys.modules["k45_funding"] = module
    spec.loader.exec_module(module)
    return module

@lru_cache(maxsize=1)
def _settlements() -> pd.DataFrame:
    return _funding_module().load_settlements(ROOT / "artifacts/funding_2020_2026h1")

def fee_bps(units: float, per_side: float = FEE_BPS_PER_SIDE) -> float:
    return float(per_side * units)

def funding_bps(side: int, entry_time: pd.Timestamp, exit_time: pd.Timestamp, boundary: str = "PESS") -> float:
    interior, edge = _funding_module().trade_funding(side, entry_time, exit_time, _settlements(), boundary)
    return float(interior + edge)

@lru_cache(maxsize=1)
def _settlement_arrays() -> tuple[np.ndarray, np.ndarray]:
    settlements = _settlements()
    return (pd.DatetimeIndex(pd.to_datetime(settlements.time, utc=True)).as_unit("ns").asi8,
            settlements.rate.to_numpy(float))


def funding_events(side: int, entry_time: pd.Timestamp, exit_time: pd.Timestamp,
                   boundary: str = "PESS") -> list[tuple[pd.Timestamp, float]]:
    """Per-settlement cashflows (bps per unit) of one holding, same rule as k45_funding.trade_funding:
    strictly interior settlements always, a settlement at the entry or exit minute only if the boundary keeps it."""
    module = _funding_module()
    times, rates = _settlement_arrays()
    entry, exit_ = pd.Timestamp(entry_time).value, pd.Timestamp(exit_time).value
    out = []
    lo, hi = int(np.searchsorted(times, entry, side="left")), int(np.searchsorted(times, exit_, side="right"))
    for k in range(lo, hi):
        value = module.cashflow_bps(side, rates[k])
        edge = "entry" if times[k] == entry else "exit" if times[k] == exit_ else None
        if edge is not None and not module.include_boundary_cashflow(edge, value, boundary):
            continue
        out.append((pd.Timestamp(int(times[k]), tz="UTC"), float(value)))
    return out


def slippage_bps(notional_units: float, minute_volume_btc: float, minute_range_bps: float, k: float) -> float:
    return float(k * minute_range_bps * min(1.0, notional_units / max(minute_volume_btc, 1e-9)))

def latency_sampler(observed_ms: np.ndarray, rng: np.random.Generator) -> Callable[[], int]:
    values = np.asarray(observed_ms, float)
    def draw() -> int:
        return max(1, math.ceil(float(rng.choice(values)) / 60_000))
    return draw

def mark_price(last: float, premium: float) -> float:
    return float(last * (1.0 + premium))
