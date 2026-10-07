from __future__ import annotations

import math

import numpy as np
import pandas as pd

from out import run_k45_vol_gated_exits_r2_46 as r


def empty_funding() -> pd.DataFrame:
    frame = pd.DataFrame({"time": pd.Series([], dtype="datetime64[ns, UTC]"),
                          "rate": pd.Series([], dtype=float)})
    frame.attrs["_time_ns"] = np.array([], dtype=np.int64)
    frame.attrs["_rates"] = np.array([], dtype=float)
    return frame


def market(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    times = pd.date_range("2024-01-01 00:01Z", periods=len(rows), freq="min")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"]).assign(open_time=times)[
        ["open_time", "open", "high", "low", "close"]]


def entry(exit_minute: int, side: int = 1, component: str = "E1-15",
          entry_price: float = 100.0, exit_price: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame({
        "book": ["B1_FAST_NONE"], "component": [component],
        "decision_time": [pd.Timestamp("2024-01-01 00:00Z")],
        "entry_time": [pd.Timestamp("2024-01-01 00:01Z")],
        "exit_time": [pd.Timestamp("2024-01-01 00:00Z") + pd.Timedelta(minutes=exit_minute)],
        "side": [side], "entry_price": [entry_price], "exit_price": [exit_price],
        "exit_reason": ["max_hold"], "source_entry_id": ["B1_FAST_NONE:000000"],
        "E_bps": [100.0],
    })


def signals(component: str = "E1-15", side: int = 0) -> dict[str, pd.DataFrame]:
    fast = pd.DataFrame({component: [side]}, index=[pd.Timestamp("2024-01-01 00:15Z")])
    return {"fast": fast, "hourly": pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC"))}


START = pd.Timestamp("2024-01-01", tz="UTC")
END = pd.Timestamp("2024-01-02", tz="UTC")


def test_stop_price_units_and_cost_match_hand_calculation():
    stop = 100 * math.exp(-0.01)
    data = market([(100, 100.2, stop - 0.01, 99.2), (99, 99, 99, 99)])
    got = r.simulate_exit(entry(2, exit_price=99), data, empty_funding(), signals(), START, END)
    trade = got["trades"].iloc[0]
    fills = got["fills"]
    assert trade.exit_reason == "stop"
    assert math.isclose(fills.iloc[-1].price, stop)
    assert math.isclose(fills.iloc[-1].units, 0.5)
    assert math.isclose(trade.gross_bps, -50.0, abs_tol=1e-10)
    assert math.isclose(trade.cost_bps, 2.0)
    assert math.isclose(trade.net_bps, -52.0, abs_tol=1e-10)


def test_target_half_then_same_bar_breakeven_closes_remainder():
    target = 100 * math.exp(0.01)
    data = market([(100, target + 0.01, 99.5, 100), (100, 100, 100, 100)])
    got = r.simulate_exit(entry(2), data, empty_funding(), signals(), START, END)
    exits = got["fills"].loc[got["fills"].fill_kind.str.startswith("exit_")]
    assert exits.fill_kind.tolist() == ["exit_target_1", "exit_breakeven"]
    assert exits.units.tolist() == [0.25, 0.25]
    assert math.isclose(exits.price.iloc[1], 100.0)
    assert math.isclose(got["trades"].net_bps.iloc[0], 23.0, abs_tol=1e-10)


def test_same_bar_stop_and_target_uses_stop():
    stop, target = 100 * math.exp(-0.01), 100 * math.exp(0.01)
    data = market([(100, target + 1, stop - 1, 100), (100, 100, 100, 100)])
    got = r.simulate_exit(entry(2), data, empty_funding(), signals(), START, END)
    assert got["trades"].exit_reason.iloc[0] == "stop"
    assert not got["trades"].target_touched.iloc[0]


def test_gap_stop_fills_at_open():
    data = market([(100, 100, 100, 100), (98, 99, 97, 98), (98, 98, 98, 98)])
    got = r.simulate_exit(entry(3, exit_price=98), data, empty_funding(), signals(), START, END)
    exit_fill = got["fills"].loc[got["fills"].fill_kind == "exit_stop"].iloc[0]
    assert exit_fill.price == 98


def test_second_entry_is_half_unit_at_next_decision_plus_one():
    rows = [(100, 100.02, 99.98, 100)] * 15 + [(101, 101.02, 100.98, 101), (102, 102, 102, 102)]
    got = r.simulate_exit(entry(17, exit_price=102), market(rows), empty_funding(), signals(side=1), START, END)
    fills = got["fills"]
    second = fills.loc[fills.fill_kind == "entry_2"].iloc[0]
    assert second.fill_time == pd.Timestamp("2024-01-01 00:16Z")
    assert second.units == 0.5
    assert got["trades"].entered_units.iloc[0] == 1.0
    assert got["trades"].second_entry_filled.iloc[0]
    assert math.isclose(fills.loc[fills.fill_kind.str.startswith("exit_"), "units"].sum(), 1.0)


def test_signal_drop_keeps_only_first_half_unit():
    rows = [(100, 100.02, 99.98, 100)] * 16 + [(101, 101, 101, 101)]
    got = r.simulate_exit(entry(17, exit_price=101), market(rows), empty_funding(), signals(side=0), START, END)
    assert not got["trades"].second_entry_filled.iloc[0]
    assert got["trades"].entered_units.iloc[0] == 0.5
    assert "entry_2" not in got["fills"].fill_kind.tolist()


def test_base_is_one_unit_four_bps_round_trip():
    data = market([(100, 100, 100, 100), (110, 110, 110, 110)])
    got = r.simulate_base(entry(2, exit_price=110), data, empty_funding(), START, END)
    expected = math.log(1.1) * 1e4 - 4
    assert got["trades"].entered_units.iloc[0] == 1.0
    assert math.isclose(got["trades"].net_bps.iloc[0], expected)
    assert math.isclose(got["net_bps"], expected)


def test_exact_e_and_future_predictions_do_not_change_entry_e():
    times = pd.date_range("2023-12-31 23:45Z", periods=4, freq="15min")
    predictions = pd.DataFrame({"timestamp": times, "prediction_exc_4h": [80., 100., 120., 140.],
                                "prediction_exc_12h": [180., 200., 220., 240.],
                                "prediction_exc_24h": [280., 300., 320., 340.]})
    source = entry(2).assign(decision_time=times[1])
    got = r.annotate_entries(source, predictions)
    changed = predictions.copy(); changed.loc[2:, "prediction_exc_4h"] = 99999
    changed_got = r.annotate_entries(source, changed)
    assert got.E_exact_T.iloc[0]
    assert got.E_bps.iloc[0] == 100
    assert changed_got.E_bps.iloc[0] == 100


def test_missing_boundary_prediction_uses_only_last_prior_row_with_24h_cap():
    times = pd.date_range("2023-12-31 22:00Z", periods=8, freq="15min")
    predictions = pd.DataFrame({"timestamp": times, "prediction_exc_4h": np.arange(8) + 1.,
                                "prediction_exc_12h": np.arange(8) + 2.,
                                "prediction_exc_24h": np.arange(8) + 3.})
    source = entry(2).assign(decision_time=times[-1] + pd.Timedelta(minutes=15))
    got = r.annotate_entries(source, predictions)
    assert not got.E_exact_T.iloc[0]
    assert got.E_source_time.iloc[0] == times[-1]
    assert got.E_bps.iloc[0] == predictions.prediction_exc_4h.iloc[-1]


def test_entry_ids_remain_one_to_one_between_base_and_exit():
    data = market([(100, 100, 100, 100), (100, 100, 100, 100)])
    source = entry(2)
    base = r.simulate_base(source, data, empty_funding(), START, END)
    exit_ = r.simulate_exit(source, data, empty_funding(), signals(), START, END)
    assert base["trades"].source_entry_id.tolist() == exit_["trades"].source_entry_id.tolist()


def test_no_balance_sizing_or_liquidation_columns_remain():
    data = market([(100, 100, 100, 100), (100, 100, 100, 100)])
    got = r.simulate_exit(entry(2), data, empty_funding(), signals(), START, END)
    forbidden = {"balance_before", "balance_after", "margin_ratio", "planned_margin", "liquidated"}
    assert forbidden.isdisjoint(got["trades"].columns)
