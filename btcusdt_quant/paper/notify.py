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


def _bps(value: object) -> str:
    return f"{float(value):+.1f} bps"


CANDIDATE_NAMES = {"F3|1h|10/24|signal|LS": "F3 역추세 1시간", "F3|5m|10/24|signal|LS": "F3 역추세 5분",
                   "F3_global_ls_account|1h|w30|q20|h12|LS": "F3-w30 역추세", "E1|1h|3|signal|L": "E1 거래량 돌파"}
REASONS = {"MAX_HOLD_OR_REVERSE": "최대보유/반대신호", "MAX_HOLD": "최대보유", "REVERSE": "반대신호",
           "FLAG": "청산조건", "STOP": "손절", "TAKE": "1차 익절", "BREAKEVEN": "본전 손절",
           "REPLAY_END": "데이터 끝", "liquidation": "강제청산"}


def _side(value: object) -> str:
    return "▲롱" if int(value) > 0 else "▼숏"


def _kst(value: object) -> str:
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError):
        return str(value)
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp
    return stamp.tz_convert("Asia/Seoul").strftime("%m/%d %H:%M")


def _reason(value: object) -> str:
    return "+".join(REASONS.get(part, part) for part in str(value).split("+"))


def _hold(minutes: object) -> str:
    total = int(float(minutes))
    return f"{total // 60}시간 {total % 60}분" if total >= 60 else f"{total}분"


def _candidate(value: object) -> str:
    from . import catalog
    text = str(value)
    if text in CANDIDATE_NAMES:
        return CANDIDATE_NAMES[text]
    return catalog.label(text) if text in catalog.BOOKS else text


def format_message(event_type: str, event: Mapping[str, object]) -> str:
    """Multi-line Korean messages; prices with commas, bps with one decimal, times in KST."""
    if event_type == "entry":
        head = f"[진입] {event['book']} {_side(event['side'])}"
        if "notional_usd" in event:
            return (f"{head}\n가격 {float(event['price']):,.1f}\n"
                    f"명목 ${float(event['notional_usd']):,.2f} · 증거금 ${float(event['margin_usd']):,.2f}\n"
                    f"청산가 {float(event['liquidation_price']):,.1f} · 잔고 ${float(event['balance_usd']):,.2f}")
        return (f"{head}\n가격 {float(event['price']):,.1f}\n신호 {_candidate(event['candidate'])}\n"
                f"최대 보유 끝 {_kst(event['exit_time'])} KST")
    if event_type == "exit":
        head = f"[청산] {event['book']}" + (f" {_side(event['side'])}" if "side" in event else "")
        if "pnl_usd" in event:
            return (f"{head}\n가격 {float(event['price']):,.1f} · {_reason(event['reason'])}\n"
                    f"손익 ${float(event['pnl_usd']):+,.2f} · 잔고 ${float(event['balance_usd']):,.2f}\n"
                    f"명목 ${float(event['notional_usd']):,.2f} · 증거금 ${float(event['margin_usd']):,.2f}")
        prices = (f"{float(event['entry_price']):,.1f} → {float(event['price']):,.1f}" if "entry_price" in event
                  else f"{float(event['price']):,.1f}")
        return (f"{head}\n{prices} · {_hold(event['hold_minutes'])}\n사유 {_reason(event['reason'])}\n"
                f"순 {_bps(event['net_bps'])} (가격 {_bps(event['gross_bps'])} · 비용 {_bps(-float(event['cost_bps']))}"
                f" · 펀딩 {_bps(event['funding_bps'])})\n누적 {_bps(event['cumulative_net_bps'])}")
    if event_type == "liquidation":
        return (f"[강제청산] {event['book']}\n가격 {float(event['price']):,.1f} · 청산가 "
                f"{float(event['liquidation_price']):,.1f}\n손익 ${float(event['pnl_usd']):+,.2f} · 잔고 $0.00")
    if event_type == "distance_warning":
        return (f"[청산 경고] {event['book']}\n거리 {float(event['distance_pct']):.2f}%\n"
                f"현재 {float(event['price']):,.1f} · 청산가 {float(event['liquidation_price']):,.1f}")
    if event_type == "dropped_signal":
        return (f"[버린 신호] {event['book']} {_side(event['side'])}\n{_candidate(event['candidate'])} · "
                f"{event.get('reason') or '-'} · {_kst(event['entry_time'])} KST")
    if event_type == "catalog_digest":
        lines = event["lines"]
        return f"[기법 장부 체결 {len(lines)}건]\n" + "\n".join(lines)
    if event_type == "daily_summary":
        rows = event.get("rows", [])
        core = [r for r in rows if not r.get("catalog")]
        lines = [f"[일일 요약] {event['date']} UTC · BTC 보유 {_bps(event['buy_hold_bps'])}"]
        lines += [f"{r['book']}: 일 {_bps(r['day_net_bps'])} · 누적 {_bps(r['total_net_bps'])} · {int(r['trades'])}건"
                  for r in core]
        books = sorted((r for r in rows if r.get("catalog")), key=lambda r: r["total_net_bps"], reverse=True)
        if books:
            positive = sum(r["total_net_bps"] > 0 for r in books)
            lines.append(f"기법 장부 {len(books)}개 · 누적 양수 {positive}개")
            lines += ["상위: " + ", ".join(f"{r['book']} {_bps(r['total_net_bps'])}" for r in books[:5]),
                      "하위: " + ", ".join(f"{r['book']} {_bps(r['total_net_bps'])}" for r in books[-5:][::-1])]
        return "\n".join(lines)
    if event_type == "alert":
        return f"[장애] {event['kind']}\n{event['detail']}"
    if event_type == "connection_test":
        return str(event["text"])
    raise ValueError(f"unknown notification event: {event_type}")


def catalog_line(kind: str, row) -> str:
    """One digest line per catalog fill."""
    if kind == "entry":
        return f"진입 {row.book} {_side(row.side)} {float(row.entry_price):,.1f} ({_kst(row.entry_time)})"
    return (f"청산 {row.book} {_side(row.side)} {float(row.entry_price):,.1f}→{float(row.exit_price):,.1f} "
            f"{_reason(row.exit_reason)} 순 {_bps(row.net_bps)} ({_kst(row.exit_time)})")


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
            "catalog_digest": self.config.telegram_entry or self.config.telegram_exit,
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

    def enqueue_digest(self, items: list[tuple[str, str]]) -> bool:
        """Mark each (event_key, line) once; send the new lines as one message."""
        if not self.configured or not self._enabled("catalog_digest") or not items:
            return False
        now = pd.Timestamp.now(tz="UTC").isoformat()
        fresh = []
        with PaperStore(self.store_path) as store:
            for key, line in items:
                cursor = store.connection.execute(
                    "INSERT OR IGNORE INTO notifications(event_key,event_type,payload,status,attempts,created_at) "
                    "VALUES(?,'catalog_item',?,'digested',0,?)", (key, line, now))
                if cursor.rowcount:
                    fresh.append(line)
            store.connection.commit()
        if not fresh:
            return False
        for part in range(0, len(fresh), 40):      # Telegram messages stay under 4096 characters
            self.enqueue(f"catalog_digest:{now}:{part}", "catalog_digest", {"lines": fresh[part:part + 40]})
        return True

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
        if not trades.empty:
            trades["cumulative_net_bps"] = trades.groupby("book").net_bps.cumsum()
        if self.config.telegram_books is not None:
            keep = set(self.config.telegram_books)
            positions, trades, dropped = (frame.loc[frame.book.isin(keep)] if not frame.empty else frame
                                          for frame in (positions, trades, dropped))
        from . import catalog
        is_catalog = (lambda frame: frame.book.isin(set(catalog.BOOKS)) if not frame.empty
                      else pd.Series(dtype=bool))
        catalog_positions = positions.loc[is_catalog(positions)] if not positions.empty else positions
        catalog_trades = trades.loc[is_catalog(trades)] if not trades.empty else trades
        positions = positions.loc[~is_catalog(positions)] if not positions.empty else positions
        trades = trades.loc[~is_catalog(trades)] if not trades.empty else trades
        if since is not None:      # catalog books are written every 5 min, so look further back (keys dedupe)
            window = pd.Timestamp(since) - pd.Timedelta(minutes=30)
            if not catalog_positions.empty:
                catalog_positions = catalog_positions.loc[pd.to_datetime(catalog_positions.entry_time, utc=True).gt(window)]
            if not catalog_trades.empty:
                catalog_trades = catalog_trades.loc[pd.to_datetime(catalog_trades.exit_time, utc=True).gt(window)]
        items = [(f"entry:{row.book}:{row.entry_time}", catalog_line("entry", row))
                 for row in catalog_positions.itertuples(index=False)]
        items += [(f"exit:{row.book}:{row.entry_time}", catalog_line("exit", row))
                  for row in catalog_trades.sort_values("exit_time").itertuples(index=False)] if not catalog_trades.empty else []
        queued += int(self.enqueue_digest(items))
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
                "candidate": row.candidate, "exit_time": row.exit_time})
        for row in trades.itertuples(index=False):
            queued += self.enqueue(f"exit:{row.book}:{row.entry_time}", "exit", {
                "book": row.book, "side": row.side, "entry_price": row.entry_price,
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
        rows = []
        if self.config.telegram_books is not None and not daily.empty:
            daily = daily.loc[daily.book.isin(set(self.config.telegram_books))]
        for row in daily.itertuples(index=False):
            from . import catalog
            rows.append({"book": row.book, "catalog": row.book in catalog.BOOKS, "day_net_bps": row.net_bps,
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
