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
from btcusdt_quant.sim.exit_overlay import overlay
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


@pytest.mark.parametrize("rule,mfe,stop", [
    ("R2_TRAIL", 60.0, 30.0),
    ("R1_BREAKEVEN", 40.0, 4.0),
    ("S150", 0.0, -150.0),
])
@pytest.mark.parametrize("side", [1, -1])
@pytest.mark.parametrize("gap", [False, True])
def test_catalog_exit_overlays_touch_and_gap(rule, mfe, stop, side, gap) -> None:
    price = lambda directional_bps: 100.0 * np.exp(side * directional_bps / 1e4)
    fill = stop - 10.0 if gap else stop
    minute_open = fill if gap else stop + 10.0
    favourable = [mfe, max(mfe, minute_open), 0.0]
    adverse = [0.0, min(stop - 1.0, minute_open), 0.0]
    o = np.array([100.0, price(minute_open), 100.0])
    h = np.array([price(favourable[0]), price(favourable[1]), 100.0]) if side == 1 else np.array(
        [price(adverse[0]), price(adverse[1]), 100.0])
    l = np.array([price(adverse[0]), price(adverse[1]), 100.0]) if side == 1 else np.array(
        [price(favourable[0]), price(favourable[1]), 100.0])

    hit = overlay(side, 100.0, 0, len(o), o, h, l, rule, np.nan)

    assert hit == pytest.approx((1, price(fill)))
    times = pd.date_range("2026-01-01", periods=3, freq="min", tz="UTC")
    native = pd.DataFrame([{
        "decision_time": times[0], "entry_time": times[0], "exit_time": times[2],
        "side": side, "units": 1.0, "entry_price": 100.0, "exit_price": 100.0,
        "exit_reason": "max_hold", "gross_bps": 0.0, "fee_bps": 4.0,
        "funding_bps": 0.0, "net_bps": -4.0, "position_id": 1,
    }])
    minutes = pd.DataFrame({"open_time": times, "open": o, "high": h, "low": l, "close": o})
    applied = catalog._overlay_result(
        SimResult(native, pd.Series(0.0, index=times)), minutes, rule).trades.iloc[0]
    assert applied.exit_time == times[1]
    assert applied.exit_price == pytest.approx(price(fill))
    assert applied.exit_reason == ({"R1_BREAKEVEN": "breakeven", "R2_TRAIL": "trail"}.get(rule, "stop"))


def test_config_dashboard_and_notify_expose_comparison_books() -> None:
    config = load_config("config/paper.toml")
    assert config.books[:3] == ("C1", "C1_FLIP", "C1_SL200")
    assert config.comparison_books[:2] == ("C1_FLIP", "C1_SL200")
    assert config.book_start_times["C1_FLIP"] == "2026-10-07T10:00:00Z"
    assert config.book_start_times["C1_SL200"] == "2026-10-07T10:00:00Z"
    assert not {"C1_FLIP", "C1_SL200"} & set(config.leverage_books)
    assert DEFAULT_BOOKS[:3] == ("C1", "C1_FLIP", "C1_SL200")
    assert BOOK_LABELS["C1_FLIP"] == "C1 추세(F3 뒤집기) (비교)"
    assert BOOK_LABELS["C1_SL200"] == "C1 손절 -200bps (비교)"
    assert CONDITION_BOOKS["C1_FLIP"] == (rules.F3_FLIP, rules.E1)
    assert CONDITION_BOOKS["C1_SL200"] == (rules.F3, rules.E1)
    assert EXECUTION_DELAYS["C1_FLIP"] == EXECUTION_DELAYS["C1_SL200"] == 0
    assert FIXED_STOP_BPS == {"C1_SL200": 200.0}
    assert config.books[config.books.index("K03") + 1:config.books.index("K03") + 3] == (
        "K03_TRAIL", "K03_S150")
    assert config.books[config.books.index("B2") + 1:config.books.index("B2") + 3] == (
        "B2_BE", "B2_S150")
    assert config.comparison_books[config.comparison_books.index("K03") + 1:
                                   config.comparison_books.index("K03") + 3] == ("K03_TRAIL", "K03_S150")
    assert config.comparison_books[config.comparison_books.index("B2") + 1:
                                   config.comparison_books.index("B2") + 3] == ("B2_BE", "B2_S150")
    assert config.book_start_times["K03_TRAIL"] == "2026-10-07T10:00:00Z"
    assert config.book_start_times["B2_BE"] == "2026-10-07T10:00:00Z"
    assert config.book_start_times["K03_S150"] == "2026-10-07T11:00:00Z"
    assert config.book_start_times["B2_S150"] == "2026-10-07T11:00:00Z"
    assert not {"K03_TRAIL", "K03_S150", "B2_BE", "B2_S150"} & set(config.leverage_books)
    assert config.telegram_books is None
    assert catalog.BOOKS["K03_TRAIL"] == ("K03", False, "NATIVE")
    assert catalog.BOOKS["K03_S150"] == ("K03", False, "NATIVE")
    assert catalog.BOOKS["B2_BE"] == ("B2", False, "NATIVE")
    assert catalog.BOOKS["B2_S150"] == ("B2", False, "NATIVE")
    assert catalog.OVERLAY_RULES == {
        "K03_TRAIL": "R2_TRAIL", "K03_S150": "S150",
        "B2_BE": "R1_BREAKEVEN", "B2_S150": "S150",
    }
    assert BOOK_LABELS["K03_TRAIL"] == "K03 추적 손절(비교)"
    assert BOOK_LABELS["K03_S150"] == "K03 고정 손절 -150(비교)"
    assert BOOK_LABELS["B2_BE"] == "B2 본전 이동(비교)"
    assert BOOK_LABELS["B2_S150"] == "B2 고정 손절 -150(비교)"
    dashboard = Path("btcusdt_quant/paper/dashboard/index.html").read_text(encoding="utf-8")
    assert dashboard.index("K03_TRAIL") < dashboard.index("K03_S150")
    assert dashboard.index("B2_BE") < dashboard.index("B2_S150")
    assert REASONS["TRAIL"] == ("추적 손절", "TRAILING_STOP")
    message = format_message("entry", {
        "book": "C1_SL200", "side": 1, "price": 100,
        "candidate": rules.F3, "exit_time": "later",
    })
    assert "C1_SL200" in message and "방향 : LONG" in message


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
