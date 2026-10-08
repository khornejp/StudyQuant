"""scripts/sim_adaptive_exit.py (R2-52A Task C, freeze out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json)."""
import importlib.util, math
from pathlib import Path
import numpy as np, pandas as pd
from btcusdt_quant.sim import rolling, schema
from btcusdt_quant.sim.reference import SimConfig

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ax_runner", ROOT / "scripts/sim_adaptive_exit.py")
ax = importlib.util.module_from_spec(spec); spec.loader.exec_module(ax)
T0 = pd.Timestamp("2024-01-01", tz="UTC")


def at(k):
    return T0 + pd.Timedelta(minutes=k)


def flat(n, price=100.0):
    t = pd.date_range(T0, periods=n, freq="1min", tz="UTC")
    p = np.full(n, price)
    return pd.DataFrame({"open_time": t, "open": p, "high": p, "low": p, "close": p})


def table(rows):
    base = {"entry": "market", "upper": np.nan, "lower": np.nan, "expiry_min": 0, "max_hold_min": 0,
            "stop_bps": np.nan, "take_bps": np.nan, "exit_long": False, "exit_short": False, "allow_entry": True,
            "ax_exit_long": False, "ax_exit_short": False}
    return schema.validate(pd.DataFrame([{**base, **r} for r in rows]))


def test_select_k_best_validation_pnl_and_ties_go_to_2():
    assert ax.select_k({1.0: 5.0, 1.5: 7.0, 2.0: 6.0}) == 1.5
    assert ax.select_k({1.0: 3.0, 1.5: 3.0, 2.0: 3.0}) == 2.0
    assert ax.select_k({1.0: -1.0, 1.5: -1.0, 2.0: -1.0 - 1e-12}) == 1.5     # tie side nearest 2.0


def test_trial_count_and_scope_from_freeze():
    assert len(ax.INCLUDED) == 29 and "K10" not in ax.INCLUDED and ax.INCLUDED[3] == "K01"
    assert ax.N_TRIALS == 87 and ax.K_VALUES == (1.0, 1.5, 2.0)
    assert len(ax.ATOMIC) == 26 and not any(i.startswith("B") for i in ax.ATOMIC)


def test_e_series_causal_latest_valid_and_same_minute_min():
    frame = pd.DataFrame({"timestamp": pd.DatetimeIndex([at(0), at(15), at(29) + pd.Timedelta(seconds=30), at(30)]),
                          "prediction_exc_4h": [100.0, np.nan, 80.0, 90.0]})
    times = pd.date_range(T0, periods=40, freq="1min", tz="UTC")
    e, e_min = ax.e_series(frame, times, "4h")
    assert e[0] == 100.0 and e[20] == 100.0               # exact T counts; the NaN row at 15 is skipped
    assert e[29] == 100.0                                  # 29:30 not yet available at open(29)
    assert e[30] == 90.0                                   # latest at open(30)
    assert e_min[30] == 80.0 and np.isnan(e_min[29])       # both arrivals in (open 29, open 30] -> min
    assert e_min[0] == 100.0 and np.isnan(e_min[15]) and np.isnan(e_min[20])
    late = pd.date_range(T0 + pd.Timedelta(hours=24, minutes=31), periods=2, freq="1min", tz="UTC")
    assert np.isnan(ax.e_series(frame, late, "4h")[0]).all()          # older than 24 h -> no E


def test_row_e0_uses_component_head_for_composites():
    regime_frame = pd.DataFrame({"timestamp": pd.DatetimeIndex([at(0)]), "prediction_exc_4h": [100.0],
                                 "prediction_exc_12h": [200.0]})
    t = table([{"decision_time": at(5), "side": 1, "component": c} for c in sorted(ax.legacy_heads())])
    e0 = ax.row_e0(t, regime_frame, "B1")
    heads = ax.legacy_heads()
    assert [e0[i] for i in range(len(t))] == [200.0 if heads[c] == "12h" else 100.0 for c in t.component]
    assert (ax.row_e0(t, regime_frame, "K02") == 100.0).all()          # single techniques: Spec.e_head


def windows(n=3):
    """Toy schedule: tests [0,100), [100,200), [200,300) minutes; validation = the 100 minutes before each test."""
    return [rolling.Window(f"W{q + 1:02d}", at(0), at(0), at(100 * q - 100), at(100 * q), at(100 * q),
                           at(100 * q + 100)) for q in range(n)]


def test_assign_k_by_execution_minute():
    t = table([{"decision_time": at(m), "side": 1, "component": 0} for m in (10, 98, 99, 150, 250)])
    k = ax.assign_k(t, {"W01": 1.0, "W02": 1.5, "W03": 2.0}, windows(), delay_min=1).k.tolist()
    assert k == [1.0, 1.0, 1.5, 1.5, 2.0]                 # decision 99 executes at 100 = W02


def config():
    return SimConfig(include_funding=False, exit_policy="R2_52A")


def test_stitched_position_keeps_its_k_across_boundary():
    m = flat(300)
    m.loc[150, "low"] = 100 * math.exp(-0.015)             # 150 bps adverse: stops k=1 (100 bps), not k=2 (200)
    t = ax.assign_k(table([{"decision_time": at(50), "side": 1}]), {"W01": 1.0, "W02": 2.0, "W03": 2.0}, windows())
    t = t.assign(e0_bps=100.0)
    e = np.full(len(m), 100.0); e_min = np.full(len(m), np.nan)
    r = ax.run_ax(t, m, e, e_min, at(0), at(300), config())
    tr = r.trades.iloc[0]
    assert tr.exit_reason == "stop" and tr.exit_time == at(150) and np.isclose(tr.exit_price, 100 * math.exp(-0.01))
    carried = ax.carried(r.trades, windows())
    assert [c["boundary"] for c in carried] == [at(100)] and carried[0]["position_id"] == tr.position_id


def test_validation_marks_open_position_without_exit_fee():
    m = flat(100); m.loc[60:, ["open", "high", "low", "close"]] = 100 * math.exp(0.005)
    t = table([{"decision_time": at(10), "side": 1}]).assign(e0_bps=100.0, k=1.0)
    e = np.full(len(m), 100.0)
    pnl = ax.validation_pnl(t, m, e, np.full(len(m), np.nan), at(0), at(100), config())
    assert np.isclose(pnl, 50.0 - 2.0)                     # +50 bps mark, entry fee only


def test_daily_zero_fill_and_paired_delta():
    days = pd.date_range(T0, periods=3, freq="D", tz="UTC")
    minute = pd.Series([1.0, 2.0], index=pd.DatetimeIndex([T0, T0 + pd.Timedelta(days=2, minutes=5)]))
    assert ax.daily(minute, days).tolist() == [1.0, 0.0, 2.0]
