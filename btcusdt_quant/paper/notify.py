"""Non-blocking Telegram notifications backed by a durable SQLite outbox."""

from __future__ import annotations

import json
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


# Message layout lives in telegram_format (user format 2026-10-07).
from .telegram_format import format_message, split_message  # noqa: E402


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
            "liquidation": self.config.telegram_exit,
            "distance_warning": self.config.telegram_alert,
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
        parts = split_message(format_message(event_type, event))      # Telegram limit 4,096 characters
        inserted = False
        with PaperStore(self.store_path) as store:
            for k, payload in enumerate(parts):
                cursor = store.connection.execute(
                    "INSERT OR IGNORE INTO notifications"
                    "(event_key,event_type,payload,status,attempts,next_attempt_at,created_at) "
                    "VALUES(?,?,?,'pending',0,?,?)",
                    (event_key if k == 0 else f"{event_key}#{k + 1}", event_type, payload, now, now))
                inserted |= bool(cursor.rowcount)
            store.connection.commit()
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
            leverage_positions = store.frame("leverage_positions")
            leverage_trades = store.frame("leverage_trades").sort_values("exit_time")
            has_fills = store.connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='catalog_fills'").fetchone() is not None
            catalog_fills = (pd.read_sql_query(
                "SELECT book,signal_time,fill_time AS entry_time,side,fill_price AS entry_price "
                "FROM catalog_fills ORDER BY fill_time", store.connection) if has_fills else pd.DataFrame())
        if not trades.empty:
            trades["cumulative_net_bps"] = trades.groupby("book").net_bps.cumsum()
        if self.config.telegram_books is not None:
            keep = set(self.config.telegram_books)
            positions, trades, dropped = (frame.loc[frame.book.isin(keep)] if not frame.empty else frame
                                          for frame in (positions, trades, dropped))
            if not catalog_fills.empty:
                catalog_fills = catalog_fills.loc[catalog_fills.book.isin(keep)]
        from . import catalog
        is_catalog = (lambda frame: frame.book.isin(set(catalog.BOOKS)) if not frame.empty
                      else pd.Series(dtype=bool))
        catalog_positions = positions.loc[is_catalog(positions)] if not positions.empty else positions
        catalog_trades = trades.loc[is_catalog(trades)] if not trades.empty else trades
        positions = positions.loc[~is_catalog(positions)] if not positions.empty else positions
        trades = trades.loc[~is_catalog(trades)] if not trades.empty else trades
        if since is not None:      # look back across collector/catalog scheduling jitter; keys dedupe
            window = pd.Timestamp(since) - pd.Timedelta(minutes=30)
            if not catalog_fills.empty:
                catalog_fills = catalog_fills.loc[pd.to_datetime(catalog_fills.entry_time, utc=True).gt(window)]
            if not catalog_positions.empty:
                catalog_positions = catalog_positions.loc[pd.to_datetime(catalog_positions.entry_time, utc=True).gt(window)]
            if not catalog_trades.empty:
                catalog_trades = catalog_trades.loc[pd.to_datetime(catalog_trades.exit_time, utc=True).gt(window)]
        if has_fills and not catalog_positions.empty:
            missing = catalog_positions.loc[~catalog_positions.book.isin(set(catalog_fills.get("book", ())))]
            entries = pd.concat([catalog_fills, missing], ignore_index=True, sort=False)
        else:
            entries = catalog_fills if has_fills else catalog_positions
        # Catalog books use the same full entry/exit messages as the core books (user format 2026-10-07).
        for row in entries.itertuples(index=False):
            queued += self.enqueue(f"entry:{row.book}:{row.entry_time}:{getattr(row, 'entry_price', '')}", "entry", {
                "book": row.book, "side": row.side, "price": row.entry_price, "candidate": row.book,
                "entry_time": row.entry_time, "exit_time": getattr(row, "exit_time", None)})
        for row in (catalog_trades.itertuples(index=False) if not catalog_trades.empty else ()):
            # a DETEXIT position closes in legs (TAKE, then the rest), so the key carries exit time and reason
            queued += self.enqueue(f"exit:{row.book}:{row.entry_time}:{row.exit_time}:{row.exit_reason}", "exit", {
                "book": row.book, "candidate": row.book, "side": row.side, "entry_price": row.entry_price,
                "entry_time": row.entry_time, "exit_time": row.exit_time, "price": row.exit_price,
                "hold_minutes": row.hold_minutes, "reason": row.exit_reason, "gross_bps": row.gross_bps,
                "cost_bps": row.cost_bps, "funding_bps": row.funding_bps, "net_bps": row.net_bps,
                "cumulative_net_bps": row.cumulative_net_bps,
                # ponytail: leg size inferred from the 4 bps round-trip fee; store units if fees ever vary
                "units": float(row.cost_bps) / 4.0 if float(row.cost_bps) > 0 else 1.0})
        warning_positions = leverage_positions.copy()
        if since is not None:
            cutoff = pd.Timestamp(since)
            positions = positions.loc[pd.to_datetime(positions.entry_time, utc=True).gt(cutoff)]
            trades = trades.loc[pd.to_datetime(trades.exit_time, utc=True).gt(cutoff)]
            dropped = dropped.loc[pd.to_datetime(dropped.entry_time, utc=True).gt(cutoff)]
            leverage_positions = leverage_positions.loc[
                pd.to_datetime(leverage_positions.entry_time, utc=True).gt(cutoff)]
            leverage_trades = leverage_trades.loc[
                pd.to_datetime(leverage_trades.exit_time, utc=True).gt(cutoff)]
        for row in positions.itertuples(index=False):
            queued += self.enqueue(f"entry:{row.book}:{row.entry_time}", "entry", {
                "book": row.book, "side": row.side, "price": row.entry_price,
                "candidate": row.candidate, "exit_time": row.exit_time, "entry_time": row.entry_time})
        for row in trades.itertuples(index=False):
            queued += self.enqueue(f"exit:{row.book}:{row.entry_time}", "exit", {
                "book": row.book, "candidate": row.candidate, "side": row.side, "entry_price": row.entry_price,
                "entry_time": row.entry_time, "exit_time": row.exit_time,
                "price": row.exit_price, "hold_minutes": row.hold_minutes,
                "reason": row.exit_reason, "gross_bps": row.gross_bps,
                "cost_bps": row.cost_bps, "funding_bps": row.funding_bps,
                "net_bps": row.net_bps, "cumulative_net_bps": row.cumulative_net_bps})
        for row in leverage_positions.itertuples(index=False):
            event = {"book": row.book, "side": row.side, "price": row.entry_price,
                     "notional_usd": row.notional_usd, "margin_usd": row.margin_usd,
                     "liquidation_price": row.liquidation_price,
                     "balance_usd": row.balance_usd}
            queued += self.enqueue(f"entry:{row.book}:{row.entry_time}", "entry", event)
        for row in warning_positions.itertuples(index=False):
            if float(row.liquidation_distance_pct) < 5.0:
                queued += self.enqueue(f"distance:{row.book}:{row.entry_time}",
                    "distance_warning", {"book": row.book,
                    "distance_pct": row.liquidation_distance_pct, "price": row.mark_price,
                    "liquidation_price": row.liquidation_price})
        for row in leverage_trades.itertuples(index=False):
            event = {"book": row.book, "price": row.exit_price,
                     "reason": row.exit_reason, "pnl_usd": row.pnl_usd,
                     "notional_usd": row.notional_usd, "margin_usd": row.margin_usd,
                     "liquidation_price": row.liquidation_price,
                     "balance_usd": row.balance_after_usd}
            event_type = "liquidation" if int(row.liquidated) else "exit"
            queued += self.enqueue(f"exit:{row.book}:{row.entry_time}", event_type, event)
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
            positions = store.frame("positions")
        rows = []
        if self.config.telegram_books is not None and not daily.empty:
            daily = daily.loc[daily.book.isin(set(self.config.telegram_books))]
        for row in daily.itertuples(index=False):
            from . import catalog
            mine = trades.loc[trades.book.eq(row.book)] if not trades.empty else trades
            if not len(mine):          # user 2026-10-08: only books that closed a trade that day
                continue
            rows.append({"book": row.book, "catalog": row.book in catalog.BOOKS, "day_net_bps": row.net_bps,
                         "total_net_bps": all_daily.loc[all_daily.book.eq(row.book), "net_bps"].sum(),
                         "trades": len(mine), "wins": int(mine.net_bps.gt(0).sum()) if len(mine) else 0,
                         "longs": int(mine.side.gt(0).sum()) if len(mine) else 0})
        buy_hold = 0.0 if len(bars) < 2 else float(
            math.log(float(bars.close.iloc[-1]) / float(bars.open.iloc[0])) * 10_000)
        return self.enqueue(f"daily:{day}", "daily_summary",
                            {"date": day, "rows": rows, "buy_hold_bps": buy_hold,
                             "open_positions": len(positions),
                             "open_unrealized_bps": float(positions.unrealized_bps.sum()) if len(positions) else 0.0})

    def publish_health_alerts(self, data_root: str | Path, since: object | None = None) -> int:
        queued = 0
        with PaperStore(self.store_path) as store:
            health = store.frame("collector_health",
                                 "source IN ('ws','rest','ws_kline_error','ws_book_error')")
            revisions = store.frame("revisions")
            forming = store.get_meta("forming_kline")
        ws_minutes = pd.to_datetime(health.loc[health.source.eq("ws"), "minute"], utc=True)
        if since is not None:
            health = health.loc[pd.to_datetime(health.minute, utc=True).gt(pd.Timestamp(since))]
        for row in health.tail(200).itertuples(index=False):
            if str(row.status).startswith("ERROR"):
                queued += self.enqueue(f"alert:{row.source}:{row.minute}", "alert",
                                       {"kind": "수집 오류", "detail": row.status})
            if int(row.gaps) >= self.config.alert_gap_minutes:
                queued += self.enqueue(f"alert:gap:{row.source}:{row.minute}", "alert",
                                       {"kind": "수집 갭", "detail": f"{row.gaps}분"})
            # REST rows are catch-up fills after a restart; their "lag" is just the outage length.
            if (row.source == "ws" and row.lag_ms is not None
                    and float(row.lag_ms) / 1000 >= self.config.alert_collector_lag_seconds):
                queued += self.enqueue(f"alert:lag:{row.source}:{row.minute}", "alert",
                                       {"kind": "수집 지연", "detail": f"{float(row.lag_ms)/1000:.1f}초"})
        now = pd.Timestamp.now(tz="UTC")
        # The socket is alive while the in-progress bar keeps updating, even when REST stored the closed bar first.
        last_seen = ws_minutes.max() if len(ws_minutes) else None
        if forming:
            updated = pd.to_datetime(json.loads(forming).get("updated_at"), utc=True)
            if pd.notna(updated) and (last_seen is None or updated > last_seen):
                last_seen = updated
        if last_seen is not None and now - last_seen > pd.Timedelta(minutes=3):
            queued += self.enqueue(f"alert:ws_down:{now.floor('h').isoformat()}", "alert",
                                   {"kind": "실시간 스트림 끊김", "detail": f"마지막 수신 {last_seen:%H:%M} UTC, REST 대체 중"})
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
