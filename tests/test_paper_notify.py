from __future__ import annotations

import logging

import pandas as pd

from btcusdt_quant.paper.config import PaperConfig, telegram_status
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper.notify import TelegramNotifier, format_message
from btcusdt_quant.paper.store import PaperStore


def _secrets(tmp_path, token="token-abcdefgh-12345678"):
    path = tmp_path / "telegram-secrets.txt"
    path.write_text(f"TELEGRAM_BOT_TOKEN={token}\nTELEGRAM_CHAT_ID=123456\n", encoding="utf-8")
    return path


def test_message_format_and_outbox_dedup_restart(tmp_path, monkeypatch) -> None:
    path = tmp_path / "live.sqlite"
    with PaperStore(path):
        pass
    secrets = _secrets(tmp_path)
    message = format_message("exit", {"book": "C1", "price": 100, "hold_minutes": 60,
        "reason": "MAX_HOLD", "gross_bps": 1.24, "cost_bps": 4,
        "funding_bps": -.06, "net_bps": -2.82, "cumulative_net_bps": 7.77})
    assert "가격 +1.2 bps" in message and "순 -2.8 bps" in message
    notifier = TelegramNotifier(path, env_path=secrets)
    event = {"book": "C1", "side": -1, "price": 100, "candidate": "F3",
             "exit_time": "2026-10-07T00:00:00+00:00"}
    assert notifier.enqueue("entry:C1:1", "entry", event)
    assert not notifier.enqueue("entry:C1:1", "entry", event)

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"ok": True}

    monkeypatch.setattr("btcusdt_quant.paper.notify.requests.post", lambda *a, **k: Response())
    restarted = TelegramNotifier(path, env_path=secrets)
    assert restarted.deliver_pending() == 1
    with PaperStore(path) as store:
        rows = store.frame("notifications")
    assert rows.status.tolist() == ["sent"] and rows.attempts.tolist() == [1]


def test_failure_is_nonblocking_and_never_exposes_token(tmp_path, monkeypatch, caplog) -> None:
    token = "token-must-never-appear-87654321"
    secrets = _secrets(tmp_path, token)
    path = tmp_path / "live.sqlite"
    with PaperStore(path):
        pass
    notifier = TelegramNotifier(path, PaperConfig(telegram_retry_base_seconds=.01), secrets)
    assert notifier.enqueue("alert:1", "alert", {"kind": "테스트", "detail": "실패"})
    monkeypatch.setattr("btcusdt_quant.paper.notify.requests.post",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError(token)))
    with caplog.at_level(logging.WARNING):
        assert notifier.deliver_pending() == 0
    with PaperStore(path) as store:
        row = store.frame("notifications").iloc[0]
        engine = PaperEngine(store)
        assert engine.process_closed_minute({"open_time": pd.Timestamp("2026-10-01T00:00:00Z"),
            "open": 1, "high": 1, "low": 1,
            "close": 1, "volume": 1})
    assert row.status == "failed" and row.last_error == "RuntimeError"
    assert token not in caplog.text and token not in row.to_json()


def test_missing_keys_disable_only_notifications_and_status_is_masked(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    with PaperStore(path):
        pass
    missing = tmp_path / "missing"
    notifier = TelegramNotifier(path, env_path=missing)
    assert not notifier.configured
    assert not notifier.enqueue("alert:1", "alert", {"kind": "x", "detail": "y"})
    with PaperStore(path) as store:
        assert store.frame("notifications").empty
    assert telegram_status(missing)["label"] == "텔레그램: 미설정"
    status = telegram_status(_secrets(tmp_path))
    assert status["configured"] and status["token"] == "toke...5678"
    assert "token-abcdefgh-12345678" not in str(status)


def test_rest_catchup_lag_is_not_alerted_but_stalled_stream_is(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    now = pd.Timestamp.now(tz="UTC").floor("min")
    with PaperStore(path) as store:
        for minute, source, lag in [(now - pd.Timedelta(minutes=10), "ws", 200.0),
                                    (now - pd.Timedelta(minutes=9), "rest", 61_000.0)]:
            store.upsert("collector_health", {"minute": minute.isoformat(), "source": source,
                                              "lag_ms": lag, "gaps": 0, "retries": 0, "status": "OK"})
    notifier = TelegramNotifier(path, env_path=_secrets(tmp_path))
    notifier.publish_health_alerts(tmp_path, since=now - pd.Timedelta(minutes=2))
    with PaperStore(path) as store:
        keys = store.frame("notifications").event_key.tolist()
    assert not [key for key in keys if key.startswith("alert:lag:")]
    assert len([key for key in keys if key.startswith("alert:ws_down:")]) == 1


def test_leverage_entry_distance_warning_once_and_liquidation_alert(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    entry = "2026-10-06T03:00:00+00:00"
    with PaperStore(path) as store:
        store.upsert("leverage_positions", {"book": "C1_x3", "source_book": "C1",
            "side": 1, "candidate": "F3", "entry_time": entry, "entry_price": 100.0,
            "mark_price": 70.0, "notional_usd": 300.0, "margin_usd": 100.0,
            "liquidation_price": 67.0, "liquidation_distance_pct": 4.285,
            "unrealized_pnl_usd": -90.0, "balance_usd": 100.0, "updated_at": entry})
        store.insert("leverage_trades", {"book": "F3_x3", "source_book": "F3",
            "candidate": "F3", "entry_time": entry, "exit_time": entry, "side": -1,
            "entry_price": 100.0, "exit_price": 132.9, "notional_usd": 300.0,
            "margin_usd": 100.0, "initial_liquidation_price": 132.9,
            "liquidation_price": 132.9, "max_adverse_pnl_usd": -100.0,
            "liquidated": 1, "gross_pnl_usd": -99.94, "cost_usd": .06,
            "funding_usd": 0.0, "pnl_usd": -100.0, "balance_before_usd": 100.0,
            "balance_after_usd": 0.0, "hold_minutes": 0.0, "exit_reason": "LIQUIDATED"})
    notifier = TelegramNotifier(path, env_path=_secrets(tmp_path))
    # Ongoing positions are still checked after their entry cycle.
    assert notifier.publish_store_events(since=entry) == 1
    assert notifier.publish_store_events() == 2
    assert notifier.publish_store_events() == 0
    with PaperStore(path) as store:
        rows = store.frame("notifications")
    assert rows.event_type.value_counts().to_dict() == {
        "entry": 1, "distance_warning": 1, "liquidation": 1}


def test_ws_down_alert_respects_live_forming_bar(tmp_path):
    import json
    import pandas as pd
    from btcusdt_quant.paper.config import PaperConfig
    from btcusdt_quant.paper.notify import TelegramNotifier
    from btcusdt_quant.paper.store import PaperStore
    path = tmp_path / "live.sqlite"
    old = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=2)).floor("min").isoformat()
    with PaperStore(path) as store:
        store.upsert("collector_health", {"minute": old, "source": "ws", "lag_ms": 0.0, "gaps": 0, "retries": 0,
                                          "status": "OK"})
        store.set_meta("forming_kline", json.dumps({"updated_at": pd.Timestamp.now(tz="UTC").isoformat()}))
    notifier = TelegramNotifier(path, PaperConfig(sqlite_path=str(path)))
    notifier.configured = True
    notifier.publish_health_alerts(tmp_path)
    with PaperStore(path) as store:
        keys = [r[0] for r in store.connection.execute("SELECT event_key FROM notifications")]
    assert not [k for k in keys if k.startswith("alert:ws_down:")]      # socket alive, REST simply won the race
