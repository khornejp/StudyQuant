"""Descriptive only: how often do positions turn from a gain into a loss? (Plan 2 trades, 2022-03..2025-12)

Per position: MFE / MAE in bps from 1 m highs and lows between entry and exit (entry minute included), the final
gross and net (4 bps). Reported per combination: share of positions whose MFE reached 20 bps (or 4 bps, the round
trip cost) but closed with a net loss, median MFE, median give-back (MFE - final gross), mean net.
No rule is chosen here; this only sizes the problem before any stop/take rule is pre-registered.
Writes out/k45_rl_r2_48_20261007/giveback.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.sim import data, rolling  # noqa: E402

TRADES = ROOT / "out/k45_rl_r2_48_20261007/strategies/trades"
OUT = ROOT / "out/k45_rl_r2_48_20261007/giveback.csv"


def position_table(trades: pd.DataFrame) -> pd.DataFrame:
    t = trades.assign(inv=trades.units / trades.entry_price)       # harmonic (quantity-weighted) average entry
    pos = t.groupby("position_id").agg(
        side=("side", "first"), entry_time=("entry_time", "min"), exit_time=("exit_time", "max"),
        units=("units", "sum"), inv=("inv", "sum"), gross=("gross_bps", "sum"), net=("net_bps", "sum"))
    return pos.assign(avg_entry=pos.units / pos.inv)


def main() -> None:
    minutes = data.load_minutes(end=rolling.END)
    times = minutes.open_time.array.asi8
    high, low = minutes.high.to_numpy(float), minutes.low.to_numpy(float)
    rows = []
    for path in sorted(TRADES.glob("*.parquet")):
        trades = pd.read_parquet(path)
        if trades.empty:
            continue
        pos = position_table(trades)
        a = np.searchsorted(times, pd.DatetimeIndex(pos.entry_time).as_unit("ns").asi8)
        b = np.searchsorted(times, pd.DatetimeIndex(pos.exit_time).as_unit("ns").asi8)
        mfe, mae = np.empty(len(pos)), np.empty(len(pos))
        for k, (i, j, side, entry) in enumerate(zip(a, b, pos.side, pos.avg_entry)):
            hi, lo = high[i:j + 1].max(), low[i:j + 1].min()
            best, worst = (hi, lo) if side == 1 else (lo, hi)
            mfe[k] = side * np.log(best / entry) * 1e4
            mae[k] = side * np.log(worst / entry) * 1e4
        pos["mfe"], pos["mae"] = mfe, mae
        gross_per_unit = pos.gross / pos.units
        net_per_unit = pos.net / pos.units
        rows.append({"combo": path.stem, "positions": len(pos),
                     "mfe20_then_loss_pct": 100 * float(((pos.mfe >= 20) & (net_per_unit < 0)).mean()),
                     "mfe4_then_loss_pct": 100 * float(((pos.mfe >= 4) & (net_per_unit < 0)).mean()),
                     "share_reaching_mfe20_pct": 100 * float((pos.mfe >= 20).mean()),
                     "of_mfe20_end_loss_pct": 100 * float((net_per_unit[pos.mfe >= 20] < 0).mean()) if (pos.mfe >= 20).any() else np.nan,
                     "median_mfe_bps": float(pos.mfe.median()), "median_mae_bps": float(pos.mae.median()),
                     "median_giveback_bps": float((pos.mfe - gross_per_unit).median()),
                     "mean_net_bps": float(net_per_unit.mean()), "total_net_bps": float(pos.net.sum())})
    frame = pd.DataFrame(rows).sort_values("combo")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)
    pd.set_option("display.width", 220)
    native = frame.loc[frame.combo.str.endswith("__NONE__NATIVE")]
    print(native.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
