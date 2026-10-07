"""Pre-registered exit-rule overlay (out/k45_rl_r2_48_20261007/exit_rules_freeze.json) on Plan 2 NATIVE entries.

R1_BREAKEVEN, R2_TRAIL and R3_ATR are applied minute by minute after each NATIVE entry; the native exit still
applies when it comes first. Writes out/k45_rl_r2_48_20261007/exit_overlay.csv
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.sim import analytics, bars, costs, data, indicators, rolling  # noqa: E402
from btcusdt_quant.sim.exit_overlay import overlay  # noqa: E402
from btcusdt_quant.sim.strategies import CATALOG  # noqa: E402

O = ROOT / "out/k45_rl_r2_48_20261007"
FEE = 4.0
BAR_MINUTES = {"K14": 5, "K18": 15}           # techniques without a fixed cadence: the bars their signal uses
SPANS = {"full": (rolling.TRAIN_START, rolling.END), "test": (rolling.WINDOWS[0].test_start, rolling.END)}


def atr_at_decisions(minutes: pd.DataFrame, minutes_per_bar: int, decisions: pd.Series) -> np.ndarray:
    b = bars.aggregate(minutes, minutes_per_bar)
    atr_bps = (indicators.atr(b, 14) / b.close * 1e4).to_numpy()
    return pd.Series(atr_bps, index=b.decision_time).reindex(pd.DatetimeIndex(decisions)).to_numpy()


def main(rule_set=("NATIVE", "R1_BREAKEVEN", "R2_TRAIL", "R3_ATR"), out_name: str = "exit_overlay.csv",
         only=None) -> None:
    minutes = data.load_minutes(end=rolling.END)
    times = minutes.open_time.array.asi8
    o, h, l, c = (minutes[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    rows, daily_all = [], {}
    for path in sorted((O / "strategies/trades").glob("*__NONE__NATIVE.parquet")):
        spec_id = path.stem.split("__")[0]
        if CATALOG[spec_id].simulator != "core" or (only and spec_id not in only):
            continue
        t = pd.read_parquet(path)
        if t.empty:
            continue
        atr = atr_at_decisions(minutes, BAR_MINUTES.get(spec_id, CATALOG[spec_id].cadence_min), t.decision_time)
        i0s = np.searchsorted(times, pd.DatetimeIndex(t.entry_time).as_unit("ns").asi8)
        ixs = np.searchsorted(times, pd.DatetimeIndex(t.exit_time).as_unit("ns").asi8)
        for rule in rule_set:
            out = []
            for k, tr in enumerate(t.itertuples(index=False)):
                exit_time, exit_price = tr.exit_time, tr.exit_price
                if rule != "NATIVE":
                    hit = overlay(tr.side, tr.entry_price, i0s[k], ixs[k], o, h, l, rule, atr[k])
                    if hit is not None:
                        exit_time, exit_price = minutes.open_time.iloc[hit[0]], hit[1]
                gross = tr.side * np.log(exit_price / tr.entry_price) * 1e4
                funding = sum(v for _, v in costs.funding_events(tr.side, tr.entry_time, exit_time, "PESS"))
                out.append((exit_time, gross - FEE + funding))
            frame = pd.DataFrame(out, columns=["exit_time", "net"])
            daily = frame.groupby(frame.exit_time.dt.floor("D")).net.sum()
            daily_all[(spec_id, rule)] = daily
            for span, (a, b) in SPANS.items():
                inside = (frame.exit_time >= a) & (frame.exit_time < b)
                cum = daily.loc[(daily.index >= a) & (daily.index < b)].cumsum()
                rows.append({"id": spec_id, "rule": rule, "span": span, "positions": int(inside.sum()),
                             "net_4bps": float(frame.net[inside].sum()),
                             "net_8bps": float(frame.net[inside].sum() - 4.0 * inside.sum()),
                             "worst_position_bps": float(frame.net[inside].min()) if inside.any() else None,
                             "max_drawdown_bps": float((cum.cummax().clip(lower=0) - cum).max()) if len(cum) else 0.0})
    result = pd.DataFrame(rows)
    native = result.loc[result.rule == "NATIVE"].set_index(["id", "span"]).net_4bps
    result["vs_native"] = result.net_4bps - result.set_index(["id", "span"]).index.map(native).to_numpy()
    days = pd.date_range(*SPANS["test"], freq="D", tz="UTC", inclusive="left")
    lows = {}
    for (spec_id, rule), daily in daily_all.items():
        if rule == "NATIVE":
            continue
        diff = (daily.reindex(days, fill_value=0.0) - daily_all[(spec_id, "NATIVE")].reindex(days, fill_value=0.0)).to_numpy()
        lows[(spec_id, rule)] = analytics.pw_mean_ci(diff)["lower"]
    result["test_paired_pw_lower"] = [lows.get((i, r)) if s == "test" else None
                                      for i, r, s in zip(result.id, result.rule, result.span)]
    result.to_csv(O / out_name, index=False)
    pd.set_option("display.width", 220)
    test = result.loc[result.span == "test"].pivot(index="id", columns="rule", values="net_4bps").round(0)
    print(test.to_string())
    better = result.loc[(result.span == "test") & (result.rule != "NATIVE") & (result.test_paired_pw_lower > 0)]
    print("paired PW lower > 0:", better[["id", "rule", "vs_native", "test_paired_pw_lower"]].round(2).to_string(index=False))


if __name__ == "__main__":
    if "--fixed-stops" in sys.argv:
        main(("NATIVE", "S150", "S200", "S300"), "fixed_stop_overlay.csv")
    else:
        main()
