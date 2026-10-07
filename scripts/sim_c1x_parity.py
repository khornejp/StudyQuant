"""C1_X reproduction pre-check (spec §2.2): rebuild R2-39's C1_X book with btcusdt_quant.sim.core.

R2-39 rules encoded in the signal table: hourly decisions; F3 has priority over E1; F3 holds 24 h and E1 20 h;
only F3's own opposite signal reverses an F3 position (component column); entry and exit at decision + 1 minute;
after an exit an entry is allowed at the same minute (reentry="stop_and_reverse").
Writes out/sim_parity_20261007/c1x_parity.json.
"""
from __future__ import annotations
import importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.sim import core, reference, schema  # noqa: E402

R239 = ROOT / "out/run_k45_short_router_r2_39.py"
EXPECTED = ROOT / "out/k45_short_router_r2_39_20261006/baseline_trades.parquet"
OUT = ROOT / "out/sim_parity_20261007/c1x_parity.json"
# costs.funding_bps reads artifacts/funding_2020_2026h1 only, so net_bps is compared where that archive covers the trade
FUNDING_END = pd.Timestamp("2026-07-01", tz="UTC")
DEV = (pd.Timestamp("2021-03-01", tz="UTC"), pd.Timestamp("2026-01-01", tz="UTC"))
# spec §2.2 pre-check figure (R2-47 DEV window): 367 trades, 9,230.67 bps
SPEC_DEV = (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2026-01-01", tz="UTC"))
SPEC_DEV_COUNT, SPEC_DEV_NET = 367, 9230.6734882525
KEYS = ["entry_time", "exit_time", "side", "entry_price", "exit_price"]
COMPONENTS = {"F3": 1, "E1": 2}


def load_r239():
    spec = importlib.util.spec_from_file_location("run_k45_short_router_r2_39", R239)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def c1x_signals(bars: pd.DataFrame, signals: dict[str, np.ndarray]) -> pd.DataFrame:
    f3, e1 = signals["F3"].astype(int), signals["E1"].astype(int)
    use_f3 = f3 != 0
    keep = use_f3 | (e1 != 0)
    frame = pd.DataFrame({
        "decision_time": bars.decision_time.to_numpy()[keep],
        "side": np.where(use_f3, f3, e1)[keep],
        "component": np.where(use_f3, COMPONENTS["F3"], COMPONENTS["E1"])[keep],
        "entry": "market", "upper": np.nan, "lower": np.nan, "expiry_min": 0,
        "max_hold_min": np.where(use_f3, 24 * 60, 20 * 60)[keep],
        "stop_bps": np.nan, "take_bps": np.nan, "exit_long": False, "exit_short": False, "allow_entry": True})
    return schema.validate(frame)


def main() -> None:
    r239 = load_r239()
    market = r239.load_market()
    funding = r239.load_funding()
    bars = r239.hourly_frame(market, r239.load_metrics(), r239.load_premium(), funding)
    signals, _ = r239.build_signals(bars, funding)
    table = c1x_signals(bars, signals)
    config = reference.SimConfig(delay_min=1, reentry="stop_and_reverse", include_funding=True, funding_boundary="PESS")
    result = core.simulate(table, market, market.open_time.iloc[0], market.open_time.iloc[-1] + pd.Timedelta(minutes=1), config)
    actual = result.trades.sort_values("entry_time").reset_index(drop=True)

    expected_all = pd.read_parquet(EXPECTED)
    expected_all = expected_all.loc[expected_all.policy.eq("C1_X")].sort_values("entry_time").reset_index(drop=True)
    for c in ("entry_time", "exit_time", "decision_time"):
        expected_all[c] = pd.to_datetime(expected_all[c], utc=True)
    # R2-39 force-closes the last open position at its data end; the simulator leaves it open
    cutoff = expected_all.exit_reason.eq("data_cutoff")
    expected = expected_all.loc[~cutoff].reset_index(drop=True)

    n = min(len(expected), len(actual))
    first_mismatch = None
    for i in range(n):
        a, e = actual.iloc[i], expected.iloc[i]
        same = (a.entry_time == e.entry_time and a.exit_time == e.exit_time and int(a.side) == int(e.side)
                and np.isclose(a.entry_price, e.entry_price, rtol=0, atol=1e-9)
                and np.isclose(a.exit_price, e.exit_price, rtol=0, atol=1e-9))
        if not same:
            first_mismatch = {"index": i, "expected": e[KEYS + ["exit_reason", "component"]].astype(str).to_dict(),
                              "actual": a[KEYS + ["exit_reason"]].astype(str).to_dict()}
            break
    covered = expected.exit_time < FUNDING_END
    diff = (actual.net_bps.iloc[:n].to_numpy() - expected.net_bps.iloc[:n].to_numpy())
    covered_n = covered.iloc[:n].to_numpy()
    max_abs = float(np.max(np.abs(diff[covered_n]))) if covered_n.any() else float("nan")
    in_dev = (expected.entry_time >= DEV[0]) & (expected.entry_time < DEV[1])
    actual_dev = (actual.entry_time >= DEV[0]) & (actual.entry_time < DEV[1])
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"r2_39_script": str(R239.relative_to(ROOT)), "expected_trades": str(EXPECTED.relative_to(ROOT))},
        "market_end": str(market.open_time.iloc[-1]),
        "n_expected": int(len(expected)), "n_actual": int(len(actual)),
        "n_expected_data_cutoff_excluded": int(cutoff.sum()),
        "first_mismatch": first_mismatch,
        "max_abs_diff_net_bps": max_abs,
        "net_compared_trades": int(covered_n.sum()),
        "net_not_compared_reason": "exit after 2026-06-30: costs.funding_bps archive ends 2026-06-30 (R2-39 adds Q3 funding)",
        "q3_net_diff_bps": float(np.sum(diff[~covered_n])) if (~covered_n).any() else 0.0,
        "dev_common": {"n_expected": int(in_dev.sum()), "n_actual": int(actual_dev.sum()),
                       "net_expected_bps": float(expected.net_bps[in_dev].sum()),
                       "net_actual_bps": float(actual.net_bps[actual_dev].sum())},
        "spec_dev_2024_2025": {
            "n_required": SPEC_DEV_COUNT, "net_required_bps": SPEC_DEV_NET,
            "n_actual": int(((actual.entry_time >= SPEC_DEV[0]) & (actual.entry_time < SPEC_DEV[1])).sum()),
            "net_actual_bps": float(actual.net_bps[(actual.entry_time >= SPEC_DEV[0]) & (actual.entry_time < SPEC_DEV[1])].sum())},
        "total_net_expected_bps": float(expected.net_bps.sum()), "total_net_actual_bps": float(actual.net_bps.sum()),
    }
    spec = payload["spec_dev_2024_2025"]
    payload["passed"] = bool(first_mismatch is None and len(expected) == len(actual) and max_abs < 1e-6
                             and spec["n_actual"] == SPEC_DEV_COUNT and abs(spec["net_actual_bps"] - SPEC_DEV_NET) < 1e-6)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
