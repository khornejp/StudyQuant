"""How much does waiting for a 15-minute decision grid cost each technique? (NONE gate, NATIVE exits, 4 bps)

A: original decision time, execute +1 min.  B: decision snapped up to the next 15-minute boundary (a 15-minute
RL cadence), execute +1 min.  C: fixed execution delays of 8 and 15 minutes. Test windows 2023-09-01..2026-01-01.
Writes out/k45_rl_r2_48_20261007/latency_cost.csv
"""
from __future__ import annotations
import sys
from dataclasses import replace
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.sim import core, rolling, schema  # noqa: E402
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant  # noqa: E402

A, B = rolling.WINDOWS[0].test_start, rolling.END
OUT = ROOT / "out/k45_rl_r2_48_20261007/latency_cost.csv"


def net(table: pd.DataFrame, minutes: pd.DataFrame, config) -> tuple[float, int]:
    r = core.simulate(table, minutes, A, B, config)
    t = r.trades
    return float(r.minute_pnl.sum()), int(((t.entry_time >= A) & (t.entry_time < B)).sum())


def main() -> None:
    ctx = Context.load()
    minutes = ctx.minutes.loc[ctx.minutes.open_time >= rolling.TRAIN_START].reset_index(drop=True)
    rows = []
    for spec_id, spec in sorted(CATALOG.items()):
        if spec.simulator != "core" or spec.post_freeze:
            continue
        table, config = build_variant(ctx, spec_id, False, "NATIVE")
        config = replace(config, include_funding=False)
        on_grid = float((table.decision_time.dt.minute % 15 == 0).mean())
        snapped = table.assign(decision_time=table.decision_time.dt.ceil("15min"))
        # several signals inside one 15-minute window collapse into the last one before the boundary
        snapped = schema.validate(snapped.drop_duplicates(["decision_time", "component"], keep="last"))
        row = {"id": spec_id, "cadence_min": spec.cadence_min, "share_on_15m_grid": round(on_grid, 3)}
        row["A_net"], row["A_trades"] = net(table, minutes, config)
        row["B_grid15_net"], row["B_trades"] = net(snapped, minutes, config)
        for d in (8, 15):
            row[f"C_delay{d}_net"], _ = net(table, minutes, replace(config, delay_min=d))
        row["B_minus_A"] = row["B_grid15_net"] - row["A_net"]
        rows.append(row)
        print(spec_id, {k: (round(v, 1) if isinstance(v, float) else v) for k, v in row.items() if k != "id"}, flush=True)
    frame = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)
    print(frame.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
