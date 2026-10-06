from __future__ import annotations

import pandas as pd

from btcusdt_quant.paper.config import PaperConfig
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper.leverage import liquidation_price, simulate_book
from btcusdt_quant.paper.store import PaperStore


def _trade(side=1, entry=100.0, exit_=110.0, start="2026-01-01T00:00Z",
           end="2026-01-01T00:02Z") -> pd.DataFrame:
    return pd.DataFrame([{"entry_time": pd.Timestamp(start), "exit_time": pd.Timestamp(end),
                          "side": side, "entry_price": entry, "exit_price": exit_,
                          "candidate": "test", "exit_reason": "NORMAL", "_active": False}])


def _minutes(lows=(99.0, 99.0), highs=(101.0, 101.0), closes=(100.0, 100.0)):
    return pd.DataFrame({"open_time": pd.date_range("2026-01-01", periods=len(lows),
                                                     freq="min", tz="UTC"),
                         "low": lows, "high": highs, "close": closes})


def test_long_and_short_liquidation_price() -> None:
    assert liquidation_price(100, 1, 100, 300, .004) == 67.06666666666668
    assert liquidation_price(100, -1, 100, 300, .004) == 132.93333333333334


def test_exact_maintenance_boundary_liquidates() -> None:
    price = liquidation_price(100, 1, 100, 300, .004)
    result = simulate_book(_trade(exit_=100), _minutes((price, price), (101, 101)),
                           pd.DataFrame(columns=["time", "rate"]), "C1",
                           pd.Timestamp("2026-01-01T00:00Z"),
                           pd.Timestamp("2026-01-01T00:03Z"))
    assert result.state["status"] == "LIQUIDATED"
    assert result.trades.iloc[0].exit_price == price
    assert result.trades.iloc[0].balance_after_usd == 0


def test_funding_moves_liquidation_boundary() -> None:
    funding = pd.DataFrame({"time": [pd.Timestamp("2026-01-01T00:00Z")], "rate": [.01]})
    # A long pays funding, moving its liquidation price from 67.0667 to 68.0667.
    result = simulate_book(_trade(exit_=100), _minutes((68.0, 99.0), (101, 101)), funding,
                           "C1", pd.Timestamp("2026-01-01T00:00Z"),
                           pd.Timestamp("2026-01-01T00:03Z"))
    assert result.trades.iloc[0].liquidated == 1
    assert round(result.trades.iloc[0].exit_price, 8) == round(68.06666666666668, 8)


def test_liquidation_skips_later_trades() -> None:
    trades = pd.concat([_trade(exit_=100), _trade(start="2026-01-01T00:03Z",
                                                   end="2026-01-01T00:04Z")], ignore_index=True)
    minutes = pd.DataFrame({"open_time": pd.date_range("2026-01-01", periods=4,
                                                        freq="min", tz="UTC"),
                            "low": [60, 99, 99, 99], "high": [101] * 4,
                            "close": [100] * 4})
    result = simulate_book(trades, minutes, pd.DataFrame(columns=["time", "rate"]), "C1",
                           pd.Timestamp("2026-01-01T00:00Z"),
                           pd.Timestamp("2026-01-01T00:05Z"))
    assert result.skips.reason.tolist() == ["LIQUIDATED"]


def test_compounding_and_notional_cost() -> None:
    trades = pd.concat([_trade(exit_=110), _trade(entry=100, exit_=110,
                           start="2026-01-01T00:03Z", end="2026-01-01T00:05Z")],
                       ignore_index=True)
    minutes = pd.DataFrame({"open_time": pd.date_range("2026-01-01", periods=5,
                                                        freq="min", tz="UTC"),
                            "low": [99] * 5, "high": [111] * 5, "close": [100] * 5})
    result = simulate_book(trades, minutes, pd.DataFrame(columns=["time", "rate"]), "C1",
                           pd.Timestamp("2026-01-01T00:00Z"),
                           pd.Timestamp("2026-01-01T00:06Z"))
    first, second = result.trades.iloc[0], result.trades.iloc[1]
    assert first.cost_usd == .12
    assert round(first.balance_after_usd, 8) == 129.88
    assert second.margin_usd == first.balance_after_usd
    assert second.notional_usd == first.balance_after_usd * 3
    assert round(result.state["balance_usd"], 8) == round(129.88 * 1.2988, 8)


def test_engine_restart_rebuilds_same_leverage_state_and_base_ledger(tmp_path,
                                                                     monkeypatch) -> None:
    start = pd.Timestamp("2026-01-01T00:00Z")
    stamps = pd.date_range(start, periods=3, freq="min", tz="UTC")
    price = pd.Series(100.0, index=range(len(stamps)))
    volume = pd.Series(1.0, index=range(len(stamps)))
    market = pd.DataFrame({"open_time": stamps, "open": price, "high": price + 1,
                           "low": price - 1, "close": price, "volume": volume})
    generated = _trade(exit_=101, start=start.isoformat(),
                       end=(start + pd.Timedelta(minutes=2)).isoformat())
    generated["gross_bps"] = 0.0
    generated["cost_bps"] = 4.0
    generated["funding_bps"] = 0.0
    generated["net_bps"] = -4.0
    generated["hold_minutes"] = 2.0
    monkeypatch.setattr("btcusdt_quant.paper.engine.rules.make_trades",
                        lambda *args, **kwargs: generated.copy())
    path = tmp_path / "restart.sqlite"
    config = PaperConfig(books=("E1",), primary_book="E1", start_time=start.isoformat(),
                         sqlite_path=str(path))
    with PaperStore(path) as store:
        engine = PaperEngine(store, config)
        engine.process_replay_minutes(market)
        first_base = engine.replay_books(start, start + pd.Timedelta(minutes=3))
        first_state = store.frame("leverage_state")
        first_trades = store.frame("leverage_trades").drop(columns="id")
    with PaperStore(path) as store:
        engine = PaperEngine(store, config)
        second_base = engine.replay_books(start, start + pd.Timedelta(minutes=3))
        pd.testing.assert_frame_equal(first_state, store.frame("leverage_state"), check_exact=True)
        pd.testing.assert_frame_equal(first_trades, store.frame("leverage_trades").drop(columns="id"),
                                      check_exact=True)
    pd.testing.assert_frame_equal(first_base, second_base, check_exact=True)


def test_simulate_book_with_no_trades_returns_initial_state() -> None:
    # Live books start empty; the first cycles after T0 must not crash.
    import pandas as pd
    from btcusdt_quant.paper import leverage

    start = pd.Timestamp("2026-10-06T03:00:00Z")
    minutes = pd.DataFrame({"open_time": [start], "high": [1.0], "low": [1.0], "close": [1.0]})
    empty = pd.DataFrame(columns=["entry_time", "exit_time", "side", "entry_price", "exit_price"])
    funding = pd.DataFrame(columns=["time", "rate"])
    result = leverage.simulate_book(empty, minutes, funding, "C1", start, start + pd.Timedelta(minutes=1))
    assert result is not None
