import numpy as np, pandas as pd
from btcusdt_quant.paper import catalog


def test_catalog_book_trades_and_open_position_from_paper_tables():
    t = pd.date_range("2026-07-01", periods=6 * 24 * 60, freq="1min", tz="UTC")
    close = 100 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 1e-3, len(t))))
    market = pd.DataFrame({"open_time": t, "open": np.r_[close[0], close[:-1]], "high": close * 1.001,
                           "low": close * .999, "close": close, "volume": 1.0, "quote_volume": 1.0,
                           "number_of_trades": 1, "taker_buy_base_volume": .5})
    empty_ls = pd.DataFrame({"open_time": pd.Series(dtype="datetime64[ns, UTC]"), "global_ls_account": [], "source": []})
    empty_premium = pd.DataFrame({"open_time": [], "premium_index": []})
    funding = pd.DataFrame({"time": pd.Series(dtype="datetime64[ns, UTC]"), "rate": pd.Series(dtype=float)})
    ctx = catalog.live_context(market, empty_ls, empty_premium, funding)
    start, end = t[0] + pd.Timedelta(days=1), t[-1] + pd.Timedelta(minutes=1)
    trades, daily, held = catalog.run_book("K11_15m", ctx, funding, start, end)
    assert len(trades) > 0 and set(trades.boundary) == {"PESS", "OPT"} and (trades.entry_time >= start).all()
    pess = trades.loc[trades.boundary == "PESS"]
    assert np.allclose(pess.net_bps, pess.gross_bps - 4.0)                      # no funding events
    d = daily.loc[daily.boundary == "PESS"]
    closed_net = pess.net_bps.sum()
    open_mark = 0.0 if held is None else d.net_bps.sum() - closed_net
    assert held is not None or np.isclose(d.net_bps.sum(), closed_net)
    detexit, _, _ = catalog.run_book("K11_15m_D", ctx, funding, start, end)
    assert not detexit.duplicated(["boundary", "entry_time"]).any()             # partial exits merged per entry


def test_catalog_condition_payload(tmp_path):
    from btcusdt_quant.paper.dashboard.server import _catalog_conditions
    from btcusdt_quant.paper.store import PaperStore
    with PaperStore(tmp_path / "t.sqlite") as store:
        c = store.connection
        c.execute("CREATE TABLE catalog_signals (book TEXT, decision_time TEXT, side INTEGER, entry TEXT, upper REAL, "
                  "lower REAL, stop_bps REAL, allow_entry INTEGER, exit_long INTEGER, exit_short INTEGER, M REAL, close REAL)")
        c.execute("INSERT INTO catalog_signals VALUES ('K09_G','2026-10-07T06:15:00+00:00',1,'market',NULL,NULL,NULL,1,0,0,.2,100.0)")
        c.execute("INSERT INTO catalog_signals VALUES ('K09_G','2026-10-07T06:30:00+00:00',-1,'market',NULL,NULL,NULL,0,0,0,.9,101.0)")
        c.execute("INSERT INTO trades(book,boundary,candidate,entry_time,exit_time,side,entry_price,exit_price,gross_bps,"
                  "cost_bps,funding_bps,net_bps,hold_minutes,exit_reason) VALUES ('K09_G','PESS','K09',"
                  "'2026-10-07T06:16:00+00:00','2026-10-07T07:00:00+00:00',1,100,101,99,4,0,95,44,'FLAG')")
        payload = _catalog_conditions(c, "K09_G", "1h", "2026-10-07T06:00:00Z")
    rows = payload["legs"][0]["rows"]
    assert [r["signal_status"] for r in rows] == ["filled", "dropped"] and rows[1]["signal_reason"] == "gate"
    assert rows[0]["value"] == 20.0 and "관문" in payload["legs"][0]["name"]
    assert payload["legs"][0]["kind"] == "catalog" and "진입 차단" in rows[1]["text"]


def _decision_inputs():
    t = pd.date_range("2026-10-07T07:00", periods=3, freq="15min", tz="UTC")
    table = pd.DataFrame({"decision_time": t, "side": [1, 0, -1], "entry": "market", "exit_long": [False, True, False],
                          "exit_short": False, "allow_entry": True, "component": 1})
    return t, table


def _predictions(times, available):
    return pd.DataFrame({"timestamp": times, "available_at": available, "model_id": "w730_raw_20261001"})


def test_decide_once_when_prediction_first_observed():
    t, table = _decision_inputs()
    preds = _predictions(t[:1], [t[0] + pd.Timedelta(seconds=20)])
    now = t[0] + pd.Timedelta(seconds=10)
    assert catalog.decide("K09_G", table, preds, set(), now, t[0]) == []              # pending: not yet available
    now = t[0] + pd.Timedelta(seconds=30)
    [event] = catalog.decide("K09_G", table, preds, set(), now, t[0])
    assert event["status"] == "decided" and event["decision_time"] == t[0] + pd.Timedelta(minutes=1)
    assert catalog.decide("K09_G", table, preds, {t[0].isoformat()}, now, t[0]) == []  # recorded once


def test_decide_expires_late_and_missing():
    t, table = _decision_inputs()
    preds = _predictions(t[:1], [t[0] + pd.Timedelta(seconds=20)])
    late = catalog.decide("K09_G", table, preds, set(), t[0] + pd.Timedelta(minutes=20), t[0])   # service was down
    assert [e["status"] for e in late] == ["expired_late"]
    missing = catalog.decide("K09_G", table, preds.iloc[:0], set(), t[2] + pd.Timedelta(minutes=61), t[0])
    assert [e["status"] for e in missing] == ["expired_missing", "expired_missing"]


def test_live_table_moves_openings_keeps_exits():
    t, table = _decision_inputs()
    table.loc[0, "exit_short"] = True
    decisions = pd.DataFrame({"signal_time": [t[0], t[2]], "decision_time": [t[0] + pd.Timedelta(minutes=2), pd.NaT],
                              "status": ["decided", "expired_late"]})
    out = catalog.live_table(table, decisions)
    opens = out.loc[out.side != 0]
    assert opens.decision_time.tolist() == [t[0] + pd.Timedelta(minutes=2)]                # t[2] expired: no entry
    assert out.loc[out.decision_time == t[0]].exit_short.all() and (out.loc[out.decision_time == t[0]].side == 0).all()
    assert out.loc[out.decision_time == t[1]].exit_long.all()
