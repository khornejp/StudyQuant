import importlib.util, json, subprocess, sys
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import core, guard, rolling
from btcusdt_quant.sim.reference import SimConfig, TRADE_COLUMNS
from btcusdt_quant.sim.strategies import Context, build_variant

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("runner", ROOT / "scripts/sim_strategy_rolling.py")
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
DAYS = pd.date_range(rolling.WINDOWS[0].val_start, rolling.END, freq="D", tz="UTC", inclusive="left")


def test_baseline2_picks_previous_validation_best():
    daily = {"A": pd.Series(0.0, index=DAYS), "B": pd.Series(0.0, index=DAYS), "C": pd.Series(0.0, index=DAYS)}
    w1, w2 = rolling.WINDOWS[0], rolling.WINDOWS[1]
    daily["B"].loc[w1.val_start] = 5.0                  # best in W01 validation
    daily["B"].loc[w1.test_start] = -3.0                # its W01 test result
    daily["C"].loc[w2.val_start] = 7.0                  # W02 validation = W01 test period, C best
    daily["C"].loc[w2.test_start] = 2.0
    empty = pd.DataFrame(columns=TRADE_COLUMNS)
    windows = pd.DataFrame([r for n, s in daily.items() for r in runner.window_rows(n, s, empty)])
    picks, concat = runner.baseline2(windows, daily)
    assert picks.combo.tolist()[:2] == ["B", "C"]
    assert picks.combo.iloc[2] == "C"                   # W03 validation = W02 test, where C made +2
    assert picks.combo.iloc[3] == "A"                   # all zero: tie -> lowest name
    assert np.isclose(concat.sum(), -3.0 + 2.0) and concat.index.min() == w1.test_start


def test_zero_trade_window_has_reason():
    rows = runner.window_rows("Z", pd.Series(0.0, index=DAYS), pd.DataFrame(columns=TRADE_COLUMNS))
    assert all(r["zero_reason"] == "no trades in window" and r["net_4bps"] == 0 for r in rows)
    guard.check({"diagnostics": {}, "strategies": [{"id": "Z", "trade_n": 0, "zero_reason": rows[0]["zero_reason"]}]})
    with pytest.raises(ValueError, match="zero trades"):
        guard.check({"diagnostics": {}, "strategies": [{"id": "Z", "trade_n": 0}]})


def test_cost_rescaling_matches_resimulation():
    ctx = Context.load(start=pd.Timestamp("2023-03-01", tz="UTC"), end=pd.Timestamp("2023-09-01", tz="UTC"))
    table, config = build_variant(ctx, "K04", False, "DETEXIT")
    a = core.simulate(table, ctx.minutes, ctx.minutes.open_time.iloc[0], ctx.end, config)
    b = core.simulate(table, ctx.minutes, ctx.minutes.open_time.iloc[0], ctx.end,
                      SimConfig(reentry=config.reentry, exit_style=config.exit_style, fee_per_side=4.0))
    lo, hi = pd.Timestamp("2023-06-01", tz="UTC"), pd.Timestamp("2023-09-01", tz="UTC")
    d = a.minute_pnl.groupby(a.minute_pnl.index.floor("D")).sum()
    units = runner._fill_units(a.trades, lo, hi)
    rescaled = d.loc[(d.index >= lo) & (d.index < hi)].sum() - (8.0 - 4.0) / 2 * units
    direct = b.minute_pnl.loc[(b.minute_pnl.index >= lo) & (b.minute_pnl.index < hi)].sum()
    assert len(a.trades) > 0 and np.isclose(rescaled, direct, atol=1e-6)


@pytest.mark.slow
def test_runner_smoke(tmp_path):
    subprocess.run([sys.executable, "scripts/sim_strategy_rolling.py", "--ids", "K04", "K10", "--workers", "2",
                    "--out", str(tmp_path), "--no-register"], check=True, cwd=ROOT)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["n_combinations"] == 8 and manifest["data_cutoff"] == "2025-12-31"
    status = pd.read_parquet(tmp_path / "combos.parquet")
    assert set(status.status) <= {"ok", "skipped"} and (status.status == "skipped").sum() == 2
    assert len(pd.read_parquet(tmp_path / "baseline2.parquet")) == len(rolling.WINDOWS)


def test_position_window_pnl_adds_up_to_the_ledger():
    from tests.sim.test_core_differential import random_case
    s, m = random_case(3)
    cfg = SimConfig(exit_style="DETEXIT", close_at_end=True)
    r = core.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1] + pd.Timedelta(minutes=1), cfg)
    closes = m.set_index("open_time").close
    a, b = m.open_time.iloc[700], m.open_time.iloc[2100]
    window = r.minute_pnl.loc[(r.minute_pnl.index >= a) & (r.minute_pnl.index < b)].sum()
    parts = runner.position_window_pnl(r.trades, closes, a, b)
    assert len(parts) > 3 and np.isclose(parts.sum(), window, atol=1e-6)
    pos = runner.positions(r.trades)
    assert len(pos) == r.trades.position_id.nunique() < len(r.trades)       # DETEXIT legs merged per position
