from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from btcusdt_quant.paper import catalog, rules
from btcusdt_quant.paper.config import load_config
from btcusdt_quant.paper.dashboard.server import (
    BOOK_LABELS, CONDITION_BOOKS, DEFAULT_BOOKS, _ConditionCache, _conditions_payload,
)
from btcusdt_quant.paper.engine import BOOKS, EXECUTION_DELAYS, FIXED_STOP_BPS
from btcusdt_quant.paper.notify import format_message
from btcusdt_quant.paper.store import PaperStore
from btcusdt_quant.paper.telegram_format import REASONS
from btcusdt_quant.sim.exit_overlay import dynamic, m_series, overlay
from btcusdt_quant.sim.reference import SimResult


def test_c1_flip_reverses_f3_and_keeps_e1() -> None:
    complete_minutes = 720 * 60
    times = pd.date_range("2026-01-01", periods=complete_minutes + 1, freq="min", tz="UTC")
    market = pd.DataFrame({
        "open_time": times, "open": 100.0, "high": 100.0,
        "low": 100.0, "close": 100.0, "volume": 1.0,
    })
    feature_times = pd.date_range("2026-01-01", periods=720, freq="h", tz="UTC")
    features = pd.DataFrame({
        "open_time": feature_times,
        "global_ls_account": [1.0] * 719 + [10.0],
        "source": "rest",
    })
    decision = times[-1]

    c1 = rules.make_first_trades(
        market, features, (rules.F3, rules.E1), decision_start=decision)
    flipped = rules.make_first_trades(
        market, features, (rules.F3_FLIP, rules.E1), decision_start=decision)

    assert c1.loc[0, ["candidate", "side"]].tolist() == [rules.F3, -1]
    assert flipped.loc[0, ["candidate", "side"]].tolist() == [rules.F3_FLIP, 1]
    assert BOOKS["C1_FLIP"] == (rules.F3_FLIP, rules.E1)
    pd.testing.assert_frame_equal(
        rules.signals(market, features, BOOKS["C1"][1]),
        rules.signals(market, features, BOOKS["C1_FLIP"][1]),
    )


def _stop_market(*, touch_open: float, touch_low: float, touch_high: float = 100.0
                 ) -> pd.DataFrame:
    return pd.DataFrame({
        "open_time": pd.date_range("2026-01-01", periods=5, freq="min", tz="UTC"),
        "open": [100.0, touch_open, 100.0, 100.0, 100.0],
        "high": [100.0, touch_high, 100.0, 100.0, 100.0],
        "low": [100.0, touch_low, 100.0, 100.0, 100.0],
        "close": [100.0] * 5,
        "volume": [1.0] * 5,
    })


def _signal(monkeypatch: pytest.MonkeyPatch, side: int = 1) -> None:
    def signals(_minutes, _features, candidate, **_kwargs):
        return pd.DataFrame({
            "decision_time": pd.to_datetime(["2026-01-01T00:00:00Z"]),
            "side": [side if candidate == rules.F3 else 0],
        })

    monkeypatch.setattr(rules, "signals", signals)


@pytest.mark.parametrize(
    ("side", "touch_open", "touch_low", "touch_high", "expected_price"),
    [(1, 99.0, 98.0, 100.0, 100.0 * np.exp(-0.02)),
     (1, 97.0, 96.0, 100.0, 97.0),
     (-1, 101.0, 100.0, 103.0, 100.0 * np.exp(0.02)),
     (-1, 103.0, 100.0, 104.0, 103.0)],
)
def test_c1_sl200_touch_and_gap_fill(
        monkeypatch, side, touch_open, touch_low, touch_high, expected_price) -> None:
    _signal(monkeypatch, side)
    trades = rules.make_first_trades(
        _stop_market(touch_open=touch_open, touch_low=touch_low, touch_high=touch_high),
        pd.DataFrame(),
        (rules.F3, rules.E1), fixed_stop_bps=200.0)

    assert trades.loc[0, "exit_time"] == pd.Timestamp("2026-01-01T00:01:00Z")
    assert trades.loc[0, "exit_price"] == pytest.approx(expected_price)
    assert trades.loc[0, "exit_reason"] == "STOP"


def test_c1_sl200_without_touch_equals_c1(monkeypatch) -> None:
    _signal(monkeypatch)
    market = _stop_market(touch_open=100.0, touch_low=99.0)
    c1 = rules.make_first_trades(market, pd.DataFrame(), (rules.F3, rules.E1))
    stopped = rules.make_first_trades(
        market, pd.DataFrame(), (rules.F3, rules.E1), fixed_stop_bps=200.0)
    columns = [*rules.TRADE_COLUMNS, "candidate"]
    pd.testing.assert_frame_equal(c1[columns], stopped[columns], check_exact=True)
    assert stopped.exit_reason.tolist() == ["MAX_HOLD_OR_REVERSE"]


@pytest.mark.parametrize(("rule", "expected"), [
    ("V1_CHANDELIER", (1, 98.0)),
    ("V2_RV_SPIKE_LOSS", (2, 100.0)),
    ("V3_M_SPIKE_LOSS", (1, 100.0)),
])
def test_research_script_uses_shared_dynamic_rules(rule, expected) -> None:
    from scripts import sim_exit_overlay
    o = np.array([100.0] * 4)
    h = np.array([101.0, 102.0, 101.0, 100.0])
    l = np.array([99.0, 98.0, 97.0, 96.0])
    c = np.array([99.0, 99.0, 100.0, 100.0])
    series = {"atr60": np.ones(4), "rv60": np.array([0.0, 2.0, 0.0, 0.0]),
              "rv1440": np.ones(4), "m": np.array([0.0, .95, 0.0, 0.0])}
    assert sim_exit_overlay.dynamic(1, 100.0, 0, 4, o, h, l, c, rule, series) == expected
    assert sim_exit_overlay.dynamic is dynamic


def test_c1_flip_dashboard_labels_f3_as_trend() -> None:
    with PaperStore(":memory:") as store:
        payload = _conditions_payload(
            store.connection, _ConditionCache(), "C1_FLIP", "1h")
    assert [(leg["candidate"], leg["kind"]) for leg in payload["legs"]] == [
        (rules.F3_FLIP, "trend"), (rules.E1, "breakout")]

    dashboard = Path("btcusdt_quant/paper/dashboard/index.html").read_text(encoding="utf-8")
    assert "leg.kind==='contrarian'||leg.kind==='trend'" in dashboard
    assert '롱 기준(이상이면 롱)' in dashboard
    assert '숏 기준(이하이면 숏)' in dashboard
    assert "upperSide=trend?'롱':'숏',lowerSide=trend?'숏':'롱'" in dashboard
    assert "color:trend?'#26a69a':'#ef5350'" in dashboard
    assert "conditionText(leg.kind,leg.last_decision)" in dashboard
    assert "conditionText(leg.kind,leg.next_estimate)" in dashboard
