"""Non-blocking Telegram notifications backed by a durable SQLite outbox."""

from __future__ import annotations

import logging
import math
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd
import requests

from .config import PaperConfig, load_env_slots
from .store import PaperStore

LOG = logging.getLogger(__name__)


def _bps(value: object) -> str:
    return f"{float(value):+.1f} bps"


def format_message(event_type: str, event: Mapping[str, object]) -> str:
    """Format terse Korean messages; every bps value has one decimal place."""
    if event_type == "entry":
        side = "롱" if int(event["side"]) > 0 else "숏"
        return (f"진입 | {event['book']} {side} | {float(event['price']):,.1f} | "
                f"신호 {event['candidate']} | 예정 {event['exit_time']}")
    if event_type == "exit":
        return (f"청산 | {event['book']} | {float(event['price']):,.1f} | "
                f"보유 {int(float(event['hold_minutes']))}분 | {event['reason']} | "
                f"총 {_bps(event['gross_bps'])} / 비용 {_bps(event['cost_bps'])} / "
                f"펀딩 {_bps(event['funding_bps'])} / 순 {_bps(event['net_bps'])} | "
                f"누적 {_bps(event['cumulative_net_bps'])}")
    if event_type == "dropped_signal":
        side = "롱" if int(event["side"]) > 0 else "숏"
        return (f"버린 신호 | {event['book']} {side} | {event['candidate']} | "
                f"{event.get('reason') or '-'} | {event['entry_time']}")
    if event_type == "daily_summary":
        rows = event.get("rows", [])
        detail = "; ".join(
            f"{row['book']} 일 {_bps(row['day_net_bps'])}, 누적 {_bps(row['total_net_bps'])}, "
            f"{int(row['trades'])}건" for row in rows)
        return f"일일 요약 | {event['date']} UTC | {detail} | BTC 보유 {_bps(event['buy_hold_bps'])}"
    if event_type == "alert":
        return f"장애 | {event['kind']} | {event['detail']}"
    if event_type == "connection_test":
        return str(event["text"])
    raise ValueError(f"unknown notification event: {event_type}")


class TelegramNotifier:
    """Queue immediately; a daemon worker owns network delivery and retries."""

    def __init__(self, store_path: str | Path, config: PaperConfig | None = None,
                 env_path: str | Path = ".env"):
        self.store_path = Path(store_path)
        self.config = config or PaperConfig(sqlite_path=str(store_path))
        secrets = load_env_slots(env_path)
        self._token = secrets["TELEGRAM_BOT_TOKEN"]
        self._chat_id = secrets["TELEGRAM_CHAT_ID"]
        self.configured = bool(self._token and self._chat_id)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def _enabled(self, event_type: str) -> bool:
        setting = {
            "entry": self.config.telegram_entry,
            "exit": self.config.telegram_exit,
            "dropped_signal": self.config.telegram_dropped_signal,
            "daily_summary": self.config.telegram_daily_summary,
            "alert": self.config.telegram_alert,
            "connection_test": True,
        }
        return bool(setting[event_type])

    def enqueue(self, event_key: str, event_type: str, event: Mapping[str, object]) -> bool:
        if not self.configured or not self._enabled(event_type):
            return False
        now = pd.Timestamp.now(tz="UTC").isoformat()
        payload = format_message(event_type, event)
        with PaperStore(self.store_path) as store:
            cursor = store.connection.execute(
                "INSERT OR IGNORE INTO notifications"
                "(event_key,event_type,payload,status,attempts,next_attempt_at,created_at) "
                "VALUES(?,?,?,'pending',0,?,?)",
                (event_key, event_type, payload, now, now))
            store.connection.commit()
            inserted = bool(cursor.rowcount)
        if inserted:
            self._wake.set()
        return inserted

    def deliver_pending(self, now: object | None = None) -> int:
        """Attempt due rows once. Errors are reduced to non-secret type/code."""
        if not self.configured:
            return 0
        stamp = pd.Timestamp(now or datetime.now(timezone.utc))
        sent = 0
        with PaperStore(self.store_path) as store:
            rows = store.connection.execute(
                "SELECT id,payload,attempts FROM notifications "
                "WHERE status IN ('pending','failed') AND "
                "(next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY id", (stamp.isoformat(),)
            ).fetchall()
            for row in rows:
                attempts = int(row["attempts"]) + 1
                try:
                    response = requests.post(
                        f"https://api.telegram.org/bot{self._token}/sendMessage",
                        data={"chat_id": self._chat_id, "text": row["payload"]}, timeout=15)
                    if response.status_code != 200:
                        raise RuntimeError(f"HTTP_{response.status_code}")
                    body = response.json()
                    if not bool(body.get("ok")):
                        raise RuntimeError(f"API_{body.get('error_code', 'ERROR')}")
                except Exception as error:  # delivery must never escape into the engine loop
                    delay = min(self.config.telegram_retry_max_seconds,
                                self.config.telegram_retry_base_seconds * (2 ** (attempts - 1)))
                    next_attempt = stamp + pd.Timedelta(seconds=delay)
                    error_text = str(error)
                    safe_error = (error_text if isinstance(error, RuntimeError) and
                                  error_text.startswith(("HTTP_", "API_")) else type(error).__name__)
                    store.connection.execute(
                        "UPDATE notifications SET status='failed',attempts=?,next_attempt_at=?,"
                        "last_error=? WHERE id=?",
                        (attempts, next_attempt.isoformat(), safe_error, row["id"]))
                    LOG.warning("telegram delivery failed: %s", safe_error)
                else:
                    store.connection.execute(
                        "UPDATE notifications SET status='sent',attempts=?,sent_at=?,"
                        "next_attempt_at=NULL,last_error=NULL WHERE id=?",
                        (attempts, stamp.isoformat(), row["id"]))
                    sent += 1
                store.connection.commit()
        return sent

    def start(self) -> None:
        if not self.configured or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="telegram-outbox", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.deliver_pending()
            self._wake.wait(1.0)
            self._wake.clear()

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def publish_store_events(self, since: object | None = None) -> int:
        queued = 0
        with PaperStore(self.store_path) as store:
            positions = store.frame("positions")
            trades = store.frame("trades", "boundary='PESS'").sort_values("exit_time")
            dropped = store.frame("signals", "accepted=0")
        if not trades.empty:
            trades["cumulative_net_bps"] = trades.groupby("book").net_bps.cumsum()
        if since is not None:
            cutoff = pd.Timestamp(since)
            positions = positions.loc[pd.to_datetime(positions.entry_time, utc=True).gt(cutoff)]
            trades = trades.loc[pd.to_datetime(trades.exit_time, utc=True).gt(cutoff)]
            dropped = dropped.loc[pd.to_datetime(dropped.entry_time, utc=True).gt(cutoff)]
        for row in positions.itertuples(index=False):
            queued += self.enqueue(f"entry:{row.book}:{row.entry_time}", "entry", {
                "book": row.book, "side": row.side, "price": row.entry_price,
                "candidate": row.candidate, "exit_time": row.exit_time})
        for row in trades.itertuples(index=False):
            queued += self.enqueue(f"exit:{row.book}:{row.entry_time}", "exit", {
                "book": row.book, "price": row.exit_price, "hold_minutes": row.hold_minutes,
                "reason": row.exit_reason, "gross_bps": row.gross_bps,
                "cost_bps": row.cost_bps, "funding_bps": row.funding_bps,
                "net_bps": row.net_bps, "cumulative_net_bps": row.cumulative_net_bps})
        for row in dropped.itertuples(index=False):
            queued += self.enqueue(
                f"drop:{row.book}:{row.candidate}:{row.decision_time}", "dropped_signal",
                {"book": row.book, "side": row.side, "candidate": row.candidate,
                 "reason": row.reason, "entry_time": row.entry_time})
        return queued

    def publish_daily_summary(self, day: str) -> bool:
        with PaperStore(self.store_path) as store:
            daily = store.frame("daily_pnl", "date=? AND boundary='PESS'", (day,))
            all_daily = store.frame("daily_pnl", "boundary='PESS'")
            trades = store.frame("trades", "boundary='PESS' AND exit_time>=? AND exit_time<?",
                                 (f"{day}T00:00:00+00:00",
                                  (pd.Timestamp(day, tz="UTC") + pd.Timedelta(days=1)).isoformat()))
            bars = store.frame("klines_1m", "open_time>=? AND open_time<?",
                               (f"{day}T00:00:00+00:00",
                                (pd.Timestamp(day, tz="UTC") + pd.Timedelta(days=1)).isoformat()))
        rows = []
        for row in daily.itertuples(index=False):
            rows.append({"book": row.book, "day_net_bps": row.net_bps,
                         "total_net_bps": all_daily.loc[all_daily.book.eq(row.book), "net_bps"].sum(),
                         "trades": int(trades.book.eq(row.book).sum()) if not trades.empty else 0})
        buy_hold = 0.0 if len(bars) < 2 else float(
            math.log(float(bars.close.iloc[-1]) / float(bars.open.iloc[0])) * 10_000)
        return self.enqueue(f"daily:{day}", "daily_summary",
                            {"date": day, "rows": rows, "buy_hold_bps": buy_hold})

    def publish_health_alerts(self, data_root: str | Path, since: object | None = None) -> int:
        queued = 0
        with PaperStore(self.store_path) as store:
            health = store.frame("collector_health",
                                 "source IN ('ws','rest','ws_kline_error','ws_book_error')")
            revisions = store.frame("revisions")
        if since is not None:
            health = health.loc[pd.to_datetime(health.minute, utc=True).gt(pd.Timestamp(since))]
        for row in health.tail(200).itertuples(index=False):
            if str(row.status).startswith("ERROR"):
                queued += self.enqueue(f"alert:{row.source}:{row.minute}", "alert",
                                       {"kind": "수집 오류", "detail": row.status})
            if int(row.gaps) >= self.config.alert_gap_minutes:
                queued += self.enqueue(f"alert:gap:{row.source}:{row.minute}", "alert",
                                       {"kind": "수집 갭", "detail": f"{row.gaps}분"})
            if row.lag_ms is not None and float(row.lag_ms) / 1000 >= self.config.alert_collector_lag_seconds:
                queued += self.enqueue(f"alert:lag:{row.source}:{row.minute}", "alert",
                                       {"kind": "수집 지연", "detail": f"{float(row.lag_ms)/1000:.1f}초"})
        if len(revisions):
            queued += self.enqueue(f"alert:reconcile:{len(revisions)}", "alert",
                                   {"kind": "대조 불일치", "detail": f"{len(revisions)}건"})
        root = Path(data_root)
        usage = shutil.disk_usage(root if root.exists() else root.parent)
        ratio = usage.free / usage.total
        if ratio < self.config.alert_disk_free_ratio:
            day = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
            queued += self.enqueue(f"alert:disk:{day}", "alert",
                                   {"kind": "디스크", "detail": f"여유 {ratio:.1%}"})
        return queued


__all__ = ["TelegramNotifier", "format_message"]
