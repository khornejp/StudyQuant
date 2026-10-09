"""Transactional closed-minute engine and deterministic history replay."""

from __future__ import annotations

import logging

import json
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from . import book, leverage, rules
from .broker import PaperBroker
from .config import PaperConfig
from .store import PaperStore, utc_text

BOOKS = {"H1": (rules.F3,), "H2": (rules.E1,),
         "H3": (rules.F3, rules.E1), "H5": (rules.F3_W30, rules.E1),
         "F3": (rules.F3,), "E1": (rules.E1,),
         "C1": (rules.F3, rules.E1),
         "C1_FLIP": (rules.F3_FLIP, rules.E1),
         "C1_SL200": (rules.F3, rules.E1),
         "C1_T1": (rules.F3, rules.E1),
         "C1_5m": (rules.F3_5M, rules.E1),
         "C4": (rules.F3_W30, rules.E1)}

LEVERAGE_TABLES = ("leverage_state", "leverage_positions", "leverage_trades", "leverage_daily", "leverage_skips")
EXECUTION_DELAYS = {"C1_FLIP": 0, "C1_SL200": 0, "C1_T1": 1}
# out/k45_rl_r2_48_20261007/fixed_stop_freeze.json: K01 S200 test
# 2023-09..2025-12 +10,714 vs +11,555 bps; max drawdown 1,910 vs 2,987.
FIXED_STOP_BPS = {"C1_SL200": 200.0}


def _kline_row(row: Mapping[str, object], received_at: object, source: str) -> dict[str, object]:
    if not bool(row.get("closed", True)):
        raise ValueError("in-progress kline is display-only")
    return {"open_time": utc_text(row["open_time"]),
            **{name: float(row[name]) for name in ("open", "high", "low", "close", "volume")},
            "quote_volume": float(row.get("quote_volume", 0.0)),
            "number_of_trades": int(row.get("number_of_trades", 0)),
            "taker_buy_base_volume": float(row.get("taker_buy_base_volume", row["volume"])),
            "taker_buy_quote_volume": float(row.get("taker_buy_quote_volume", 0.0)),
            "source": source, "received_at": utc_text(received_at), "closed": 1}


class PaperEngine:
    """Persist each closed minute and replay frozen books from persisted history."""

    def __init__(self, store: PaperStore, config: PaperConfig | None = None):
        self.store = store
        self.config = config or PaperConfig()
        if self.config.mode != "paper":
            raise RuntimeError("live mode is disabled")
        self.broker = PaperBroker()
        self.store.set_meta("config_hash", self.config.hash)

    def process_closed_minute(self, row: Mapping[str, object], *,
                              received_at: object | None = None,
                              source: str = "archive") -> bool:
        """Commit raw bar, gap health and resume cursor as one transaction."""
        received = pd.Timestamp(received_at or row["open_time"])
        values = _kline_row(row, received, source)
        stamp = pd.Timestamp(values["open_time"])
        exists = self.store.connection.execute(
            "SELECT 1 FROM klines_1m WHERE open_time=?", (stamp.isoformat(),)).fetchone()
        if exists is not None:
            return False
        last_text = self.store.get_meta("last_processed_minute")
        is_forward = last_text is None or stamp > pd.Timestamp(last_text)
        gap = 0 if not is_forward or last_text is None else max(0, int(
            (stamp - pd.Timestamp(last_text)) / pd.Timedelta(minutes=1)) - 1)
        lag_ms = max(0.0, (received - (stamp + pd.Timedelta(minutes=1))).total_seconds() * 1000)
        with self.store.transaction() as connection:
            self.store.upsert("klines_1m", values, connection)
            self.store.upsert("collector_health", {
                "minute": stamp.isoformat(), "source": source, "lag_ms": lag_ms,
                "gaps": gap, "retries": 0,
                "status": "BACKFILL" if not is_forward else "GAP" if gap else "OK"}, connection)
            if is_forward:
                connection.execute(
                    "INSERT INTO meta(key,value) VALUES('last_processed_minute',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (stamp.isoformat(),))
        return True

    def process_replay_minutes(self, frame: pd.DataFrame, *, source: str = "archive",
                               checkpoint_rows: int = 1_000) -> int:
        """Advance the simulated clock one minute at a time with batched durable checkpoints."""
        if checkpoint_rows < 1:
            raise ValueError("checkpoint_rows must be positive")
        inserted = 0
        records = frame.to_dict("records")
        for offset in range(0, len(records), checkpoint_rows):
            last_text = self.store.get_meta("last_processed_minute")
            last = pd.Timestamp(last_text) if last_text else None
            with self.store.transaction() as connection:
                for row in records[offset:offset + checkpoint_rows]:
                    received = pd.Timestamp(row["open_time"]) + pd.Timedelta(minutes=1)
                    values = _kline_row({**row, "closed": True}, received, source)
                    stamp = pd.Timestamp(values["open_time"])
                    if last is not None and stamp <= last:
                        continue
                    gap = 0 if last is None else max(0, int(
                        (stamp - last) / pd.Timedelta(minutes=1)) - 1)
                    self.store.upsert("klines_1m", values, connection)
                    self.store.upsert("collector_health", {
                        "minute": stamp.isoformat(), "source": source, "lag_ms": 0.0,
                        "gaps": gap, "retries": 0, "status": "GAP" if gap else "OK"}, connection)
                    last = stamp
                    inserted += 1
                if last is not None:
                    connection.execute(
                        "INSERT INTO meta(key,value) VALUES('last_processed_minute',?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (last.isoformat(),))
        return inserted

    def store_ls_ratio(self, timestamp: object, value: float, *, source: str = "archive",
                       received_at: object | None = None) -> None:
        stamp = pd.Timestamp(timestamp)
        self.store.upsert("ls_ratio", {"timestamp": utc_text(stamp),
                          "global_ls_account": float(value), "long_account": None,
                          "short_account": None, "source": source,
                          "received_at": utc_text(received_at or stamp)})

    def store_funding(self, time: object, rate: float, *, raw_calc_time: object | None = None,
                      source: str = "archive", received_at: object | None = None,
                      interval_hours: float | None = None) -> None:
        """Actual fundingTime as-is (R2-54: no 8 h rounding). interval_hours unknown -> NULL + interval_missing."""
        raw = pd.Timestamp(raw_calc_time or time)
        raw_text = utc_text(raw)
        received = pd.Timestamp(received_at or raw)
        # legacy rows were keyed by the rounded 8 h time; the same raw event must not become a second event
        legacy = self.store.connection.execute(
            "SELECT 1 FROM funding WHERE raw_calc_time=? AND time<>?", (raw_text, raw_text)).fetchone()
        if legacy is None:
            self.store.upsert("funding", {"time": raw_text, "rate": float(rate), "raw_calc_time": raw_text,
                              "source": source, "received_at": utc_text(received)})
        hours = None if interval_hours is None or pd.isna(interval_hours) else float(interval_hours)
        self.store.put_versioned("funding_events", {
            "funding_time": raw_text, "funding_rate": float(rate), "interval_hours": hours,
            "interval_missing": int(hours is None), "source_timestamp": raw_text,
            "logical_available_at": utc_text(max(raw, received) if source == "rest" else raw),
            "received_at": utc_text(received), "source": source})

    def replay_books(self, start: object, end: object,
                     features: pd.DataFrame | None = None,
                     history: pd.DataFrame | None = None,
                     funding_history: pd.DataFrame | None = None,
                     publish_open_positions: bool = False) -> pd.DataFrame:
        """Recompute frozen books from stored bars, then atomically publish ledger."""
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("replay bounds must be timezone-aware")
        market = self.store.frame("klines_1m")
        market["open_time"] = pd.to_datetime(market.open_time, utc=True)
        if history is not None:
            warmup = history.copy()
            warmup["open_time"] = pd.to_datetime(warmup.open_time, utc=True)
            market = pd.concat([warmup, market], ignore_index=True, sort=False)
        market = market.sort_values("open_time", kind="stable").reset_index(drop=True)
        market = market.drop_duplicates("open_time", keep="last").reset_index(drop=True)
        if features is None:
            features = self.store.frame("ls_ratio").rename(columns={"timestamp": "open_time"})
        feature_columns = ["open_time", "global_ls_account"] + (
            ["source"] if "source" in features else [])
        features = features[feature_columns].copy()
        features["open_time"] = pd.to_datetime(features.open_time, utc=True)
        funding = self.store.frame("funding")[["time", "rate"]]
        funding["time"] = pd.to_datetime(funding.time, utc=True, format="mixed")
        if funding_history is not None:
            prior = funding_history[["time", "rate"]].copy()
            prior["time"] = pd.to_datetime(prior.time, utc=True)
            funding = pd.concat([prior, funding], ignore_index=True)
        funding = funding.sort_values("time", kind="stable").reset_index(drop=True)
        funding = funding.drop_duplicates("time", keep="last").reset_index(drop=True)
        funding.attrs["_time_ns"] = funding.time.array.asi8
        funding.attrs["_rates"] = funding.rate.to_numpy(float)
        # Only active legacy books are replayed; catalog (AX) books are written by scripts/paper_catalog.py and
        # retired books are never touched again (r2_52a_exit_freeze.json paper_rollout.retirement).
        legacy = tuple(name for name in self.config.books if name in BOOKS)
        candidates_used = tuple(dict.fromkeys(candidate for name in legacy for candidate in BOOKS[name]))
        generated = {candidate: rules.make_trades(market, features, candidate)
                     for candidate in candidates_used}
        end_price = float(market.loc[market.open_time.lt(end), "close"].iloc[-1])
        data_end = market.open_time.iloc[-1] + pd.Timedelta(minutes=1)

        def window(frame: pd.DataFrame, candidate: str | None,
                   book_start: pd.Timestamp = start) -> pd.DataFrame:
            result = frame.loc[(frame.exit_time > book_start) & (frame.entry_time < end)].copy()
            if result.empty:  # e.g. a book before its own T0: untyped empty columns break the math below
                result["_active"] = pd.Series(dtype=bool)
                result["exit_reason"] = pd.Series(dtype=object)
                return result.reset_index(drop=True)
            hold_hours = (result.candidate.map(
                {name: spec.max_hold for name, spec in rules.SPECS.items()})
                if candidate is None else rules.SPECS[candidate].max_hold)
            natural_end = result.entry_time + pd.to_timedelta(hold_hours, unit="h")
            result["_active"] = result.exit_time.eq(data_end) & natural_end.gt(data_end)
            forced = result.exit_time > end
            result.loc[forced, "exit_time"] = end
            result.loc[forced, "exit_price"] = end_price
            result.loc[forced, "gross_bps"] = (result.loc[forced, "side"] * np.log(
                result.loc[forced, "exit_price"] / result.loc[forced, "entry_price"]) * 1e4)
            if "exit_reason" not in result:
                result["exit_reason"] = "MAX_HOLD_OR_REVERSE"
            else:
                result["exit_reason"] = result.exit_reason.fillna("MAX_HOLD_OR_REVERSE")
            result.loc[forced, "exit_reason"] = "REPLAY_END"
            return result.reset_index(drop=True)

        base = {candidate: window(frame, candidate) for candidate, frame in generated.items()}
        output: list[pd.DataFrame] = []
        open_rows: list[dict[str, object]] = []
        leverage_results: list[leverage.LeverageResult] = []
        leverage_books = (self.config.books if self.config.leverage_books is None else
                          self.config.leverage_books)
        for name in legacy:
            book_start = pd.Timestamp(self.config.book_start_times.get(name, start))
            if book_start.tzinfo is None:
                raise ValueError("book start must be timezone-aware")
            candidates = BOOKS[name]
            execution_delay = EXECUTION_DELAYS.get(name, 0)
            fixed_stop_bps = FIXED_STOP_BPS.get(name)
            if execution_delay or fixed_stop_bps is not None:
                raw = window(rules.make_first_trades(
                    market, features, candidates, decision_start=book_start,
                    execution_delay_minutes=execution_delay,
                    fixed_stop_bps=fixed_stop_bps,
                    cost_bps=self.config.cost_bps), None, book_start)
                dropped = pd.DataFrame()
            elif book_start != start:
                local_generated = {candidate: rules.make_trades(
                    market, features, candidate, decision_start=book_start)
                    for candidate in candidates}
                book_base = {candidate: window(frame, candidate, book_start)
                             for candidate, frame in local_generated.items()}
            else:
                book_base = base
            if not execution_delay and fixed_stop_bps is None:
                if len(candidates) == 1:
                    raw = book_base[candidates[0]].copy()
                    raw["candidate"] = None if name in {"H1", "H2"} else candidates[0]
                else:
                    source = pd.concat([book_base[candidate].assign(candidate=candidate)
                                        for candidate in candidates], ignore_index=True)
                    raw, dropped = book.first_book(source, list(candidates))
                    for row in dropped.itertuples(index=False):
                        self.store.insert("signals", {"decision_time": utc_text(row.entry_time),
                            "entry_time": utc_text(row.entry_time), "book": name,
                            "candidate": row.candidate, "side": int(row.side), "accepted": 0,
                            "reason": row.reason})
            if publish_open_positions and len(raw) and bool(raw.iloc[-1].get("_active", False)):
                current = raw.iloc[-1]
                current_candidate = current.candidate or candidates[0]
                elapsed = int((end - current.entry_time) / pd.Timedelta(minutes=1))
                maximum = rules.SPECS[current_candidate].max_hold * 60
                open_rows.append({"book": name, "side": int(current.side),
                    "candidate": current_candidate, "entry_time": utc_text(current.entry_time),
                    "entry_price": float(current.entry_price), "exit_time": utc_text(current.exit_time),
                    "remaining_minutes": max(0, maximum - elapsed),
                    "unrealized_bps": float(current.side * np.log(end_price / current.entry_price) * 1e4),
                    "updated_at": utc_text(end)})
            for boundary in ("PESS", "OPT"):
                output.append(book.reprice(
                    raw, funding, boundary, self.config.cost_bps,
                    cost_first=name == "C1_T1").assign(
                    book=name, boundary=boundary))
            if name in leverage_books:
                # The x3 overlay is reference only; its failure must not block the 1x books.
                try:
                    raw = raw.assign(exit_phase=leverage.exit_phases(raw, market))
                    leverage_results.append(leverage.simulate_book(
                        raw, market, funding, name, book_start, end,
                        leverage=self.config.leverage, budget_usd=self.config.budget_usd,
                        maintenance_margin_rate=self.config.maintenance_margin_rate,
                        liquidation_fee_rate=self.config.liquidation_fee_rate,
                        cost_bps=self.config.cost_bps))
                except Exception:
                    logging.getLogger(__name__).exception("x3 overlay failed for %s", name)
        ledger = (pd.concat(output, ignore_index=True) if output else
                  pd.DataFrame(columns=["book", "boundary", "_active"]))
        published = ledger.loc[~ledger["_active"].fillna(False)].copy() if publish_open_positions else ledger
        closes = market.set_index("open_time").close
        daily_parts = []
        for (name, boundary), trades in published.groupby(["book", "boundary"]):
            minute = book.minute_components(trades, closes, funding, boundary, self.config.cost_bps)
            book_start = pd.Timestamp(self.config.book_start_times.get(name, start))
            minute = minute.loc[(minute.index >= book_start) & (minute.index < end)]
            daily = minute.groupby(minute.index.strftime("%Y-%m-%d")).sum().reset_index(
                names="date")
            daily.insert(0, "boundary", boundary); daily.insert(0, "book", name)
            daily_parts.append(daily)
        daily = pd.concat(daily_parts, ignore_index=True) if daily_parts else pd.DataFrame()
        x3 = tuple(f"{name}_x{self.config.leverage:g}" for name in legacy if name in leverage_books)
        with self.store.transaction() as connection:
            for table, names in (("trades", legacy), ("daily_pnl", legacy), ("positions", legacy),
                                 *((table, x3) for table in LEVERAGE_TABLES)):
                if names:       # per-book rewrite of the active legacy books only; never table-wide
                    connection.execute(f"DELETE FROM {table} WHERE book IN ({','.join('?' * len(names))})", names)
            for position in open_rows:
                self.store.upsert("positions", position, connection)
            for row in published.itertuples(index=False):
                connection.execute(
                    "INSERT INTO trades(book,boundary,candidate,entry_time,exit_time,side,"
                    "entry_price,exit_price,gross_bps,cost_bps,funding_bps,net_bps,hold_minutes,"
                    "exit_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (row.book, row.boundary, row.candidate, utc_text(row.entry_time),
                     utc_text(row.exit_time), int(row.side), float(row.entry_price),
                     float(row.exit_price), float(row.gross_bps), float(row.cost_bps),
                     float(row.funding_bps), float(row.net_bps), float(row.hold_minutes),
                     getattr(row, "exit_reason", "MAX_HOLD_OR_REVERSE")))
            for row in daily.itertuples(index=False):
                self.store.upsert("daily_pnl", row._asdict(), connection)
            for result in leverage_results:
                state = dict(result.state)
                state["liquidated_at"] = (None if state["liquidated_at"] is None else
                                           utc_text(state["liquidated_at"]))
                state["updated_at"] = utc_text(state["updated_at"])
                self.store.upsert("leverage_state", state, connection)
                if result.position is not None:
                    position = dict(result.position)
                    for column in ("entry_time", "updated_at"):
                        position[column] = utc_text(position[column])
                    if pd.isna(position.get("candidate")):
                        position["candidate"] = None
                    self.store.upsert("leverage_positions", position, connection)
                for row in result.trades.to_dict("records"):
                    for column in ("entry_time", "exit_time"):
                        row[column] = utc_text(row[column])
                    if pd.isna(row.get("candidate")):
                        row["candidate"] = None
                    self.store.insert("leverage_trades", row, connection)
                for row in result.daily.to_dict("records"):
                    self.store.upsert("leverage_daily", row, connection)
                for row in result.skips.to_dict("records"):
                    row["entry_time"] = utc_text(row["entry_time"])
                    if pd.isna(row.get("candidate")):
                        row["candidate"] = None
                    self.store.insert("leverage_skips", row, connection)
            connection.execute(
                "INSERT INTO meta(key,value) VALUES('last_replay',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps({"start": start.isoformat(), "end": end.isoformat()}),))
        return ledger


__all__ = ["BOOKS", "EXECUTION_DELAYS", "FIXED_STOP_BPS", "PaperEngine"]
