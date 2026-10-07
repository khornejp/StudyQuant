import numpy as np, pandas as pd
from btcusdt_quant.paper import catalog


def test_level_books_are_enabled_after_existing_k_series() -> None:
    from pathlib import Path
    from btcusdt_quant.paper.config import load_config
    from btcusdt_quant.paper.dashboard.server import INDICATOR_LABELS
    config = load_config("config/paper.toml")
    existing = tuple(f"K{number}{suffix}" for number in range(25, 29) for suffix in ("", "_G", "_D", "_GD"))
    added = tuple(f"K{number}{suffix}" for number in range(29, 31) for suffix in ("", "_G", "_D", "_GD"))
    variants = existing + added
    start = config.books.index("K25")
    assert config.books[start:start + 24] == variants
    assert config.books[start - 1] == "K22_GD" and config.books[start + 24] == "B1"
    assert config.comparison_books[config.comparison_books.index("K25"):
                                   config.comparison_books.index("K25") + 24] == variants
    assert all(config.book_start_times[name] == "2026-10-07T12:00:00Z" for name in added)
    assert not set(variants) & set(config.leverage_books)
    assert all(catalog.label(name).endswith("(연구 음수)") for name in variants)
    assert {key: INDICATOR_LABELS[key] for key in (
        "prior_day_high", "prior_day_low", "pivot", "r1", "s1", "swing_high", "swing_low",
        "round_above", "round_below", "adx_1h", "volume_z", "atr15", "day_mid")
    } == {"prior_day_high": "전일 고가", "prior_day_low": "전일 저가", "pivot": "피벗 P",
         "r1": "피벗 R1", "s1": "피벗 S1", "swing_high": "스윙 고점", "swing_low": "스윙 저점",
         "round_above": "라운드 위", "round_below": "라운드 아래", "adx_1h": "1시간 ADX",
         "volume_z": "거래량 z", "atr15": "ATR15", "day_mid": "전일 중간값"}
    assert catalog.DEFINITIONS["K25"].startswith("전일 고가·저가 반전")
    assert catalog.DEFINITIONS["K26"].startswith("피벗 R1·S1 반전(P 도달 청산)")
    assert catalog.DEFINITIONS["K27"].startswith("스윙 고점·저점 반전(1시간봉 좌우 5봉)")
    assert catalog.DEFINITIONS["K28"].startswith("1,000달러 라운드 넘버 반전")
    assert catalog.DEFINITIONS["K29"] == "필터 반전: 횡보(1시간 ADX<20)에서 검증된 지지·저항(7일 내 2회 이상 터치)을 꼬리로 뚫고 0.25 ATR 이상 안쪽 마감 + 거래량 z≥1.5 시 반대 진입, 손절 꼬리 너머, 전일 중간값 도달 또는 4시간 청산"
    assert catalog.DEFINITIONS["K30"] == "돌파 후 되돌림: 추세(1시간 ADX≥25, EMA50 방향)에서 검증된 선을 1시간 종가로 0.25 ATR 이상 돌파 후 12시간 내 첫 되돌림에서 돌파 방향 진입, 손절 선 너머 0.5 ATR, 최대 8시간"
    assert all((config.telegram_entry, config.telegram_exit, config.telegram_daily_summary, config.telegram_alert))
    assert "K(?:2[5-9]|30)" in Path("btcusdt_quant/paper/dashboard/index.html").read_text(encoding="utf-8")


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
    assert np.isclose(d.net_bps.sum(), closed_net)                              # open mark lives only in positions
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


def test_catalog_condition_uses_confirmed_and_delayed_fill_linkage(tmp_path):
    from btcusdt_quant.paper.dashboard.server import _catalog_conditions
    from btcusdt_quant.paper.store import PaperStore
    with PaperStore(tmp_path / "t.sqlite") as store:
        c = store.connection
        c.execute("CREATE TABLE catalog_signals (book TEXT, decision_time TEXT, side INTEGER, entry TEXT, upper REAL, "
                  "lower REAL, stop_bps REAL, allow_entry INTEGER, exit_long INTEGER, exit_short INTEGER, M REAL, "
                  "close REAL, indicators TEXT, model TEXT, expiry_min INTEGER)")
        c.execute("CREATE TABLE catalog_decisions (book TEXT, signal_time TEXT, decision_time TEXT, status TEXT, "
                  "prediction_ts TEXT, available_at TEXT, decided_at TEXT, model_id TEXT)")
        c.execute("CREATE TABLE catalog_fills (book TEXT, signal_time TEXT, fill_time TEXT, side INTEGER, "
                  "fill_price REAL)")
        c.execute("INSERT INTO catalog_signals VALUES "
                  "('K09_G','2026-10-07T06:15:00+00:00',1,'market',NULL,NULL,NULL,1,0,0,.8,100,'{}',NULL,0),"
                  "('K09_G','2026-10-07T06:30:00+00:00',-1,'market',NULL,NULL,NULL,0,0,0,.2,101,'{}',NULL,0)")
        c.execute("INSERT INTO catalog_decisions VALUES "
                  "('K09_G','2026-10-07T06:15:00+00:00','2026-10-07T06:17:00+00:00','decided',"
                  "'2026-10-07T06:15:00+00:00','2026-10-07T06:16:20+00:00','2026-10-07T06:16:20+00:00','m'),"
                  "('K09_G','2026-10-07T06:30:00+00:00','2026-10-07T06:31:00+00:00','decided',"
                  "'2026-10-07T06:30:00+00:00','2026-10-07T06:30:20+00:00','2026-10-07T06:30:20+00:00','m')")
        c.execute("INSERT INTO catalog_fills VALUES "
                  "('K09_G','2026-10-07T06:15:00+00:00','2026-10-07T06:18:00+00:00',1,100)")
        store.set_meta("last_processed_minute", "2026-10-07T06:40:00+00:00")
        rows = _catalog_conditions(c, "K09_G", "1h", None)["legs"][0]["rows"]
    assert [row["signal_status"] for row in rows] == ["filled", "dropped"]
    assert rows[0]["fill_time"] == "2026-10-07T06:18:00+00:00"


def test_catalog_condition_marks_oco_fill_and_keeps_pending_order_hidden(tmp_path):
    from btcusdt_quant.paper.dashboard.server import _catalog_conditions
    from btcusdt_quant.paper.store import PaperStore
    with PaperStore(tmp_path / "t.sqlite") as store:
        c = store.connection
        c.execute("CREATE TABLE catalog_signals (book TEXT, decision_time TEXT, side INTEGER, entry TEXT, upper REAL, "
                  "lower REAL, stop_bps REAL, allow_entry INTEGER, exit_long INTEGER, exit_short INTEGER, M REAL, "
                  "close REAL, indicators TEXT, model TEXT, expiry_min INTEGER)")
        c.execute("CREATE TABLE catalog_fills (book TEXT, signal_time TEXT, fill_time TEXT, side INTEGER, fill_price REAL)")
        c.execute("INSERT INTO catalog_signals VALUES "
                  "('K06_k0.5','2026-10-07T06:00:00+00:00',0,'oco',101,99,NULL,1,0,0,.5,100,'{}',NULL,60),"
                  "('K06_k0.5','2026-10-07T07:00:00+00:00',0,'oco',102,98,NULL,1,0,0,.5,100,'{}',NULL,60)")
        c.execute("INSERT INTO catalog_fills VALUES "
                  "('K06_k0.5','2026-10-07T06:00:00+00:00','2026-10-07T06:45:00+00:00',-1,99)")
        store.set_meta("last_processed_minute", "2026-10-07T07:10:00+00:00")
        rows = _catalog_conditions(c, "K06_k0.5", "1h", None)["legs"][0]["rows"]
    assert rows[0]["condition_met"] and rows[0]["signal_status"] == "filled" and rows[0]["fill_side"] == -1
    assert rows[1]["condition_met"] and rows[1]["signal_status"] == "pending"


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


def test_mix_minute_keeps_long_heads_held():
    from btcusdt_quant.paper import detector
    names = detector.target_names()
    fresh, held = np.ones((1, len(names))), np.zeros((1, len(names)))
    out = detector.mix_minute(fresh, held)[0]
    assert all(out[j] == (1.0 if n.split("_", 1)[1] in ("30m", "1h", "4h") else 0.0) for j, n in enumerate(names))


def test_bind_predictions_includes_off_grid_minute_rows():
    base = _predictions(pd.DatetimeIndex([pd.Timestamp("2026-10-07T07:00Z")]),
                        [pd.Timestamp("2026-10-07T07:00:20Z")])
    minute = _predictions(pd.DatetimeIndex([pd.Timestamp("2026-10-07T07:05Z")]),
                          [pd.Timestamp("2026-10-07T07:05:20Z")])
    base.attrs["minute"] = minute
    bound = catalog.bind_predictions(base, pd.DatetimeIndex([pd.Timestamp("2026-10-07T07:05Z")]))
    assert bound.prediction_ts.iloc[0] == pd.Timestamp("2026-10-07T07:05Z")


def test_composite_dropped_signal_keeps_direction():
    t = pd.Timestamp("2026-10-07T07:00Z")
    table = pd.DataFrame({"decision_time": [t, t], "side": [0, -1], "allow_entry": [True, False],
                          "component": [1, 2], "ind_close": [100.0, 100.0]})
    row = catalog._merge_components(table).iloc[0]
    assert row.side == -1 and not row.allow_entry and row.ind_E1_side == -1


def test_fill_rows_maps_confirmed_decision_and_open_add_on_to_original_signals():
    signal = pd.Timestamp("2026-10-07T07:00Z")
    confirmed = signal + pd.Timedelta(minutes=2)
    add_signal = signal + pd.Timedelta(minutes=15)
    add_confirmed = add_signal + pd.Timedelta(minutes=1)
    decisions = pd.DataFrame({"book": ["K09_D", "K09_D"], "signal_time": [signal, add_signal],
                              "decision_time": [confirmed, add_confirmed], "status": ["decided", "decided"]})
    trades = pd.DataFrame({"decision_time": [confirmed], "entry_time": [confirmed + pd.Timedelta(minutes=1)],
                           "side": [1], "entry_price": [100.0], "boundary": ["PESS"]})
    held = {"legs": [{"decision_time": add_confirmed, "entry_time": add_confirmed + pd.Timedelta(minutes=1),
                       "side": 1, "units": .5, "entry_price": 101.0}]}
    fills = catalog.fill_rows("K09_D", trades, held, decisions)
    assert fills.signal_time.tolist() == [signal, add_signal]
    assert fills.fill_time.tolist() == [confirmed + pd.Timedelta(minutes=1),
                                        add_confirmed + pd.Timedelta(minutes=1)]


def test_recompute_preserves_failed_book_and_publishes_other_book(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from btcusdt_quant.paper.store import PaperStore
    from scripts import paper_catalog
    path = tmp_path / "live.sqlite"
    old = {"boundary": "PESS", "candidate": "K09", "entry_time": "2026-10-07T00:01:00+00:00",
           "exit_time": "2026-10-07T00:02:00+00:00", "side": 1, "entry_price": 100.0, "exit_price": 100.0,
           "gross_bps": 0.0, "cost_bps": 4.0, "funding_bps": 0.0, "net_bps": -4.0,
           "hold_minutes": 1.0, "exit_reason": "OLD"}
    with PaperStore(path) as store:
        store.insert("trades", {"book": "K09", **old})
        store.insert("trades", {"book": "K11_15m", **{**old, "candidate": "K11_15m",
                                                       "entry_time": "2026-10-07T00:03:00+00:00"}})
        ctx = SimpleNamespace(minutes=pd.DataFrame({"close": [100.0]}))
        config = SimpleNamespace(books=("K09", "K11_15m"), book_start_times={},
                                 start_time="2026-10-07T00:00:00Z")

        def run(name, *_args, **_kwargs):
            if name == "K09":
                raise RuntimeError("one bad book")
            trade = pd.DataFrame([{**old, "book": name, "candidate": name,
                                   "entry_time": pd.Timestamp("2026-10-07T00:04Z"),
                                   "exit_time": pd.Timestamp("2026-10-07T00:05Z"),
                                   "decision_time": pd.Timestamp("2026-10-07T00:03Z")}])
            daily = pd.DataFrame([{"book": name, "boundary": "PESS", "date": "2026-10-07",
                                   "gross_bps": 0.0, "cost_bps": 4.0, "funding_bps": 0.0, "net_bps": -4.0}])
            return trade, daily, None

        monkeypatch.setattr(catalog, "run_book", run)
        assert paper_catalog.recompute_books(store, config, pd.Timestamp("2026-10-07T01:00Z"),
                                             ctx, pd.DataFrame(), with_signals=False) == 1
        rows = store.frame("trades").sort_values("book")
    assert rows.loc[rows.book.eq("K09"), "exit_reason"].tolist() == ["OLD"]
    assert rows.loc[rows.book.eq("K11_15m"), "entry_time"].tolist() == ["2026-10-07T00:04:00+00:00"]


def test_engine_replay_with_only_catalog_books_preserves_catalog_rows(tmp_path):
    from btcusdt_quant.paper.config import PaperConfig
    from btcusdt_quant.paper.engine import PaperEngine
    from btcusdt_quant.paper.store import PaperStore
    path = tmp_path / "live.sqlite"
    start = pd.Timestamp("2026-10-07T00:00Z")
    with PaperStore(path) as store:
        store.upsert("klines_1m", {"open_time": start.isoformat(), "open": 100.0, "high": 100.0, "low": 100.0,
                                    "close": 100.0, "volume": 1.0, "source": "test",
                                    "received_at": start.isoformat(), "closed": 1})
        store.insert("trades", {"book": "K09", "boundary": "PESS", "candidate": "K09",
                                "entry_time": start.isoformat(), "exit_time": (start + pd.Timedelta(minutes=1)).isoformat(),
                                "side": 1, "entry_price": 100.0, "exit_price": 100.0, "gross_bps": 0.0,
                                "cost_bps": 4.0, "funding_bps": 0.0, "net_bps": -4.0,
                                "hold_minutes": 1.0, "exit_reason": "OLD"})
        config = PaperConfig(books=("K09",), primary_book="K09", start_time=start.isoformat(),
                             comparison_books=(), leverage_books=(), sqlite_path=str(path))
        result = PaperEngine(store, config).replay_books(start, start + pd.Timedelta(minutes=1))
        assert result.empty and store.frame("trades").book.tolist() == ["K09"]


def test_open_position_mark_is_removed_from_realized_daily_pnl():
    from btcusdt_quant.sim.reference import SimResult
    times = pd.date_range("2026-10-07", periods=2, freq="1min", tz="UTC")
    gain = np.log(1.1) * 1e4
    result = SimResult(pd.DataFrame(), pd.Series([-2.0, gain], index=times), {
        "legs": [{"decision_time": times[0] - pd.Timedelta(minutes=1), "entry_time": times[0],
                  "side": 1, "units": 1.0, "entry_price": 100.0}]})
    realized = catalog._realized_minute_pnl(result, pd.Series([100.0, 110.0], index=times))
    assert np.allclose(realized, 0.0)


def test_catalog_funding_is_attributed_to_settlement_day():
    legs = pd.DataFrame({"entry_time": [pd.Timestamp("2026-10-06T07:00Z")],
                         "exit_time": [pd.Timestamp("2026-10-07T01:00Z")], "side": [1], "units": [.5]})
    funding = pd.DataFrame({"time": [pd.Timestamp("2026-10-06T08:00Z")], "rate": [.001]})
    daily = catalog._funding_by_day(legs, funding, "PESS")
    assert daily.index.tolist() == [pd.Timestamp("2026-10-06T00:00Z")]
    assert daily.iloc[0] == -5.0
