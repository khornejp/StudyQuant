"""127.0.0.1-only, read-only paper trading dashboard and JSON API."""

from __future__ import annotations

import csv
import io
import json
import math
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs

from .. import catalog, rules
from btcusdt_quant.sim.strategies import CATALOG
from ..config import credential_status, telegram_status

STATIC = Path(__file__).with_name("index.html")
VENDOR = Path(__file__).with_name("vendor")
REPO_ROOT = Path(__file__).resolve().parents[3]
TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
DEFAULT_BOOKS = ("C1", "C1_FLIP", "C1_SL200", "C1_5m", "C1_T1", "F3", "E1", "C4")
BOOK_LABELS = {"C1_FLIP": "C1 추세(F3 뒤집기) (비교)",
               "C1_SL200": "C1 손절 -200bps (비교)",
               "K03_TRAIL": "K03 추적 손절(비교)",
               "K03_S150": "K03 고정 손절 -150(비교)",
               "K03_V3": "K03 변동성 급등 손절(비교)",
               "B2_BE": "B2 본전 이동(비교)",
               "B2_S150": "B2 고정 손절 -150(비교)",
               "B2_V3": "B2 변동성 급등 손절(비교)",
               "C1_5m": "C1 역추세5분 (비교)",
               "C1_T1": "C1 T+1분 진입 (비교)"}
MAX_CANDLES = 2_000
CONDITION_BOOKS = {
    "F3": (rules.F3,), "E1": (rules.E1,),
    "C1": (rules.F3, rules.E1),
    "C1_FLIP": (rules.F3_FLIP, rules.E1),
    "C1_SL200": (rules.F3, rules.E1),
    "C1_T1": (rules.F3, rules.E1),
    "C1_5m": (rules.F3_5M, rules.E1),
    "C4": (rules.F3_W30, rules.E1),
}
CONDITION_NAMES = {rules.F3: "F3 역추세", rules.F3_FLIP: "F3 추세(뒤집기)",
                   rules.F3_W30: "F3-w30 역추세",
                   rules.F3_5M: "F3 역추세 5분 판단", rules.E1: "E1 거래량 돌파"}


def _public_status() -> tuple[dict[str, object], dict[str, object]]:
    """Dashboard is shared publicly via a tunnel: expose only whether secrets are set."""
    credentials, telegram = credential_status(), telegram_status()
    return ({"loaded": credentials["loaded"]},
            {"configured": telegram["configured"],
             "label": "텔레그램: 설정됨" if telegram["configured"] else "텔레그램: 미설정"})


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def _connect_ro(path: Path) -> sqlite3.Connection:
    """Open SQLite without schema migration, WAL mutation, or any other write."""
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _has_table(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _frame(connection: sqlite3.Connection, table: str, where: str = "",
           parameters: tuple[object, ...] = ()) -> pd.DataFrame:
    if not _has_table(connection, table):
        return pd.DataFrame()
    suffix = f" WHERE {where}" if where else ""
    return pd.read_sql_query(f"SELECT * FROM {table}{suffix}", connection, params=parameters)


def _meta(connection: sqlite3.Connection, key: str) -> str | None:
    if not _has_table(connection, "meta"):
        return None
    row = connection.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return None if row is None else str(row[0])


def _utc(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat()


def _q3_replay_inputs(connection: sqlite3.Connection, first: pd.Timestamp,
                      last: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Recover the exact external warm-up used to build the checked-in Q3 replay DB."""
    count = int(connection.execute("SELECT COUNT(*) FROM klines_1m").fetchone()[0])
    if count != 132_480 or first != pd.Timestamp("2026-07-01T00:00:00Z") or (
            last != pd.Timestamp("2026-09-30T23:59:00Z")):
        return None
    history_path = REPO_ROOT / "artifacts/btcusdt_2020_2026h1.parquet"
    old_features = (REPO_ROOT / "artifacts/short_quantile_sweep_20260826/feature_cache/"
                    "0fc9086b7d4b4c43c8b84f6f/feature_rows.parquet")
    q3_features = REPO_ROOT / "artifacts/hold_a_2026q3/features_2026q3.parquet"
    if not all(path.exists() for path in (history_path, old_features, q3_features)):
        return None
    market_start = first - pd.Timedelta(hours=20)
    market = pd.read_parquet(history_path, columns=["open_time", "open", "high", "low",
                                                           "close", "volume"],
                             filters=[("open_time", ">=", market_start),
                                      ("open_time", "<", first)])
    feature_start = first - pd.Timedelta(hours=2_161)
    columns = ["open_time", "global_ls_account"]
    features = pd.concat([
        pd.read_parquet(old_features, columns=columns,
                        filters=[("open_time", ">=", feature_start),
                                 ("open_time", "<", first)]),
        pd.read_parquet(q3_features, columns=columns,
                        filters=[("open_time", ">=", first),
                                 ("open_time", "<=", last)]),
    ], ignore_index=True)
    return market, features


def _condition_inputs(connection: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame,
                                                                  pd.Timestamp, str]:
    market = pd.read_sql_query(
        "SELECT open_time,open,high,low,close,volume FROM klines_1m "
        "WHERE closed=1 ORDER BY open_time", connection)
    if market.empty:
        return market, pd.DataFrame(columns=["open_time", "global_ls_account"]), pd.NaT, "sqlite"
    market["open_time"] = pd.to_datetime(market.open_time, utc=True)
    first, last = market.open_time.iloc[0], market.open_time.iloc[-1]
    features = pd.read_sql_query(
        "SELECT timestamp AS open_time,global_ls_account,source FROM ls_ratio ORDER BY timestamp",
        connection) if _has_table(connection, "ls_ratio") else pd.DataFrame()
    source = "sqlite:klines_1m+ls_ratio"
    if features.empty:
        replay = _q3_replay_inputs(connection, first, last)
        if replay is not None:
            warmup, features = replay
            warmup["open_time"] = pd.to_datetime(warmup.open_time, utc=True)
            market = pd.concat([warmup, market], ignore_index=True).sort_values(
                "open_time", kind="stable").reset_index(drop=True)
            source = "sqlite:klines_1m+frozen Q3 replay artifacts"
        else:
            features = pd.DataFrame(columns=["open_time", "global_ls_account"])
    features["open_time"] = pd.to_datetime(features.open_time, utc=True)
    return market, features, first, source


def _padded_to_hour(minutes: pd.DataFrame) -> pd.DataFrame | None:
    """Hold price and add zero volume to show a clearly-labelled nowcast."""
    if minutes.empty:
        return None
    last = minutes.open_time.iloc[-1]
    end = last.floor("h") + pd.Timedelta(minutes=59)
    if last >= end:
        return None
    missing = pd.date_range(last + pd.Timedelta(minutes=1), end, freq="min", tz="UTC")
    price = float(minutes.close.iloc[-1])
    padding = pd.DataFrame({"open_time": missing, "open": price, "high": price,
                            "low": price, "close": price, "volume": 0.0})
    return pd.concat([minutes, padding], ignore_index=True)


def _required_volume_for_zscore(prior_mean: object, prior_sse: object, *,
                                prior_count: int = 19, target: float = 3.0) -> object:
    """Volume boundary where z equals target after adding the current observation."""
    denominator = prior_count * (prior_count - target ** 2)
    if denominator <= 0:
        raise ValueError("target z must be below sqrt(prior_count)")
    return prior_mean + np.sqrt((prior_count + 1) * target ** 2 * prior_sse / denominator)


def _display_condition_details(frame: pd.DataFrame, candidate: str) -> pd.DataFrame:
    """Add dashboard-only values without changing frozen rule decisions."""
    if candidate != rules.E1:
        return frame
    frame = frame.copy()
    frame["prior_low_20"] = np.nan
    frame["required_volume"] = np.nan
    if frame.empty:
        return frame
    prior = frame.volume.shift().rolling(19)
    prior_sum = prior.sum()
    prior_mean = prior_sum / 19
    prior_sse = (frame.volume.pow(2).shift().rolling(19).sum()
                 - prior_sum.pow(2) / 19).clip(lower=0)
    frame["required_volume"] = _required_volume_for_zscore(prior_mean, prior_sse)
    frame["prior_low_20"] = frame.low.rolling(20).min().shift()
    return frame


def _row_value(row: object, name: str) -> object:
    if isinstance(row, pd.Series):
        return row.get(name)
    if isinstance(row, Mapping):
        return row.get(name)
    return getattr(row, name, None)


def _optional_float(row: object, name: str) -> float | None:
    value = _row_value(row, name)
    return None if value is None or pd.isna(value) else float(value)


def _ratio_pct(value: float) -> float:
    return value / (1 + value) * 100


def _condition_value(row: object | None, *, include_distances: bool = True) -> dict[str, object] | None:
    if row is None:
        return None
    fields = ("global_ls_account", "lower_threshold", "upper_threshold", "volume_zscore",
              "prior_high_20", "prior_low_20", "close", "volume", "required_volume")
    result: dict[str, object] = {
        "decision_time": _iso(pd.Timestamp(_row_value(row, "decision_time"))),
        **{name: _optional_float(row, name) for name in fields},
        "side": int(_row_value(row, "side")),
    }
    result["current_volume"] = result.pop("volume")
    ratio = result["global_ls_account"]
    lower = result["lower_threshold"]
    upper = result["upper_threshold"]
    if ratio is None or lower is None or upper is None:
        result.update(long_account_pct=None, upper_pct=None, lower_pct=None)
        if include_distances:
            result.update(distance_to_short=None, distance_to_long=None)
    else:
        ratio, lower, upper = float(ratio), float(lower), float(upper)
        long_pct, lower_pct, upper_pct = map(_ratio_pct, (ratio, lower, upper))
        result.update(long_account_pct=long_pct, upper_pct=upper_pct, lower_pct=lower_pct)
        if include_distances:
            result.update(
                distance_to_short={"ratio": max(0.0, upper - ratio),
                                   "pct_points": max(0.0, upper_pct - long_pct)},
                distance_to_long={"ratio": max(0.0, ratio - lower),
                                  "pct_points": max(0.0, long_pct - lower_pct)},
            )
    close, high = result["close"], result["prior_high_20"]
    result["price_distance_pct"] = (
        None if close is None or high is None or not float(close)
        else max(0.0, (float(high) / float(close) - 1) * 100))
    return result


def _condition_text(candidate: str, value: dict[str, object] | None) -> str:
    if value is None:
        return "계산 가능한 완성 봉이 없습니다."
    if candidate == rules.E1:
        zscore, high = value["volume_zscore"], value["prior_high_20"]
        required, current = value["required_volume"], value["current_volume"]
        if zscore is None or high is None or required is None:
            return "돌파: 20봉 준비 중 → 대기"
        met = int(value["side"]) > 0
        return (f"돌파: 거래량 필요 {required:,.1f} BTC / 현재 {current:,.1f} BTC, "
                f"직전 20봉 고가 {high:,.1f} 위 마감 필요 "
                f"(현재가 대비 +{value['price_distance_pct']:.2f}%) → "
                f"{'롱 조건 충족' if met else '대기'}")
    ratio, upper, lower = (value[name] for name in
                           ("global_ls_account", "upper_threshold", "lower_threshold"))
    flipped = candidate == rules.F3_FLIP
    label = "추세" if flipped else "역추세"
    if ratio is None or upper is None or lower is None:
        return f"{label}: 기준선 준비 중 → 대기"
    if float(ratio) >= float(upper):
        state = "롱 조건 충족" if flipped else "숏 조건 충족"
    elif float(ratio) <= float(lower):
        state = "숏 조건 충족" if flipped else "롱 조건 충족"
    else:
        state = "대기"
    upper_side, lower_side = (("롱", "숏") if flipped else ("숏", "롱"))
    upper_distance = value["distance_to_short"]
    lower_distance = value["distance_to_long"]
    return (f"{label}: 롱 계정 비율 {value['long_account_pct']:.1f}% "
            f"(롱숏비율 {ratio:.2f}) / {upper_side} 기준 {value['upper_pct']:.1f}% "
            f"(롱숏비율 {upper:.2f}) 이상 / {lower_side} 기준 {value['lower_pct']:.1f}% "
            f"(롱숏비율 {lower:.2f}) 이하 / 남은 거리 "
            f"{upper_side} {upper_distance['ratio']:.2f}·{upper_distance['pct_points']:.1f}%p, "
            f"{lower_side} {lower_distance['ratio']:.2f}·{lower_distance['pct_points']:.1f}%p → {state}")


class _ConditionCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.key: tuple[object, ...] | None = None
        self.value: dict[str, object] | None = None

    def get(self, connection: sqlite3.Connection) -> dict[str, object]:
        latest = connection.execute("SELECT MAX(open_time),COUNT(*) FROM klines_1m").fetchone()
        feature_latest = connection.execute("SELECT MAX(timestamp),COUNT(*) FROM ls_ratio").fetchone()
        key = (latest[0], latest[1], feature_latest[0], feature_latest[1])
        if self.key == key and self.value is not None:
            return self.value
        with self.lock:
            if self.key == key and self.value is not None:
                return self.value
            market, features, display_start, source = _condition_inputs(connection)
            details = {candidate: _display_condition_details(
                           rules.condition_details(market, features, candidate), candidate)
                       for candidate in rules.SPECS}
            if not pd.isna(display_start):
                details = {candidate: frame.loc[frame.bar_start.ge(display_start)].reset_index(drop=True)
                           for candidate, frame in details.items()}
            padded = _padded_to_hour(market)
            estimates = {}
            for candidate in rules.SPECS:
                estimate = None if padded is None else _display_condition_details(
                    rules.condition_details(padded, features, candidate), candidate)
                row = None if estimate is None or estimate.empty else estimate.iloc[-1]
                if row is not None and not details[candidate].empty and (
                        row.decision_time <= details[candidate].decision_time.iloc[-1]):
                    row = None
                estimates[candidate] = row
            cutoff = None if market.empty else market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
            self.key, self.value = key, {"details": details, "estimates": estimates,
                                         "market": market, "data_cutoff": cutoff,
                                         "source": source}
            return self.value


INDICATOR_LABELS = {
    "global_ls": "LS 비율", "q10": "q10", "q90": "q90", "q20": "q20", "q80": "q80",
    "volume_z": "거래량 z", "close": "종가", "high20": "직전20봉 고가", "high55": "직전55봉 고가",
    "low55": "직전55봉 저가", "low10": "직전10봉 저가", "high10": "직전10봉 고가",
    "pred_range_1h_bps": "예측 range_1h(bps)", "pred_exc_1h_bps": "예측 exc_1h(bps)",
    "squeeze_bars": "스퀴즈 연속봉", "bb_mid": "BB 중앙", "bb_lower": "BB 하단", "bb_upper": "BB 상단",
    "kc_upper": "KC 상단", "kc_lower": "KC 하단", "rsi": "RSI", "grid_step_bps": "그리드 간격(bps)", "base": "기준가",
    "ema9_minus_ema21": "EMA9−EMA21", "ema9": "EMA9", "ema21": "EMA21", "supertrend_direction": "슈퍼트렌드 방향",
    "sign_15m": "15분 부호", "sign_1h": "1시간 부호", "sign_4h": "4시간 부호", "range_high": "범위 고가",
    "range_low": "범위 저가", "range_bps": "범위(bps)", "vwap_gap_z": "VWAP 괴리 z", "vwap": "VWAP",
    "lower_wick_atr": "아래꼬리/ATR", "upper_wick_atr": "위꼬리/ATR", "streak": "연속봉(+양/−음)",
    "funding_bps": "funding(bps)", "q05_bps": "q05(bps)", "q95_bps": "q95(bps)", "premium_z": "premium z",
    "taker_share_z": "taker 비중 z", "taker_share": "taker 비중", "cvd": "CVD", "cvd_at_prior_high": "직전 고점 CVD",
    "cvd_at_prior_low": "직전 저점 CVD", "new_high": "20봉 신고가", "new_low": "20봉 신저가",
    "prior_day_high": "전일 고가", "prior_day_low": "전일 저가", "pivot": "피벗 P",
    "r1": "피벗 R1", "s1": "피벗 S1", "swing_high": "스윙 고점", "swing_low": "스윙 저점",
    "round_above": "라운드 위", "round_below": "라운드 아래",
    "adx_1h": "1시간 ADX", "volume_z": "거래량 z", "atr15": "ATR15", "day_mid": "전일 중간값",
    "A2_side": "A2", "E1_side": "E1", "F3_side": "F3-30", "F3W_side": "F3W-30"}


def _indicator_text(values: dict) -> str:
    parts = []
    for key, value in values.items():
        if value is None:
            continue
        text = f"{value:,.0f}" if abs(value) >= 1000 else f"{value:.4g}"
        parts.append(f"{INDICATOR_LABELS.get(key, key)} {text}")
    return " · ".join(parts)


def _catalog_row_text(row: dict) -> str:
    side = int(row["side"] or 0)
    parts = ["롱 신호" if side > 0 else "숏 신호" if side < 0 else "신호 없음"]
    indicators = json.loads(row.get("indicators") or "{}")
    if indicators:
        parts.append(_indicator_text(indicators))
    if row.get("entry") == "oco" and row.get("upper") is not None:
        parts.append(f"역지정가 위 {row['upper']:,.1f} / 아래 {row['lower']:,.1f}")
    if row.get("entry") == "grid" and row.get("upper") is not None:
        parts.append(f"그리드 1단 위 {row['upper']:,.1f} / 아래 {row['lower']:,.1f}")
    if row.get("M") is not None:
        parts.append(f"탐지기 M {row['M'] * 100:.0f}%")
    if row.get("stop_bps") is not None:
        parts.append(f"E {row['stop_bps']:.0f} bps")
    if row.get("exit_long"):
        parts.append("롱 청산 조건")
    if row.get("exit_short"):
        parts.append("숏 청산 조건")
    if not row.get("allow_entry"):
        parts.append("진입 차단(관문·예측 없음)")
    return " · ".join(parts)


def _catalog_conditions(connection: sqlite3.Connection, book: str, tf: str,
                        start_time: str | None) -> dict[str, object]:
    spec_id = catalog.BOOKS[book][0]
    spec = CATALOG[spec_id]
    try:
        signals = _frame(connection, "catalog_signals", "book=?", (book,))
    except Exception:
        signals = pd.DataFrame()
    trades = _frame(connection, "trades", "book=? AND boundary='PESS'", (book,))
    legacy_fills = set(pd.to_datetime(trades.entry_time, utc=True)) if not trades.empty else set()
    positions = _frame(connection, "positions", "book=?", (book,))
    for row in positions.itertuples(index=False):
        legacy_fills.add(pd.Timestamp(row.entry_time))
    linked = _frame(connection, "catalog_fills", "book=?", (book,))
    fill_of = {}
    if not linked.empty:
        linked["signal_time"] = pd.to_datetime(linked.signal_time, utc=True)
        linked["fill_time"] = pd.to_datetime(linked.fill_time, utc=True)
        linked = linked.sort_values(["signal_time", "fill_time"], kind="stable")
        fill_of = {pd.Timestamp(row.signal_time): row for row in linked.drop_duplicates("signal_time").itertuples()}
    gated = False                      # AX books use the ungated NATIVE table
    has_decisions = _has_table(connection, "catalog_decisions")
    try:
        decided = _frame(connection, "catalog_decisions", "book=?", (book,))
    except Exception:
        decided = pd.DataFrame()
    decision_of = ({pd.Timestamp(r["signal_time"]): r for r in _records(decided)} if not decided.empty else {})
    processed = _utc(_meta(connection, "last_processed_minute"))
    rows, model_rows = [], []
    for row in _records(signals.sort_values("decision_time")) if not signals.empty else []:
        decision = pd.Timestamp(row["decision_time"])
        side = int(row["side"] or 0)
        entry = row.get("entry")
        opening = bool(side) or entry in ("oco", "grid")
        event = decision_of.get(decision)
        effective = decision
        if event is not None and event.get("status") == "decided" and event.get("decision_time"):
            effective = pd.Timestamp(event["decision_time"])
        fill = fill_of.get(decision)
        status = reason = None
        if opening:
            if fill is not None or effective + pd.Timedelta(minutes=1) in legacy_fills:
                status = "filled"
            elif catalog.needs_model(book) and has_decisions and event is None:
                status = "pending"
            elif event is not None and event.get("status") != "decided":
                status, reason = "dropped", str(event.get("status") or "prediction")
            elif not row["allow_entry"]:
                status, reason = "dropped", "gate"
            else:
                expiry = int(row.get("expiry_min") or 0) if entry in ("oco", "grid") else 0
                deadline = effective + pd.Timedelta(minutes=1 + expiry)
                status = "dropped" if processed is not None and processed >= deadline else "pending"
                reason = "holding" if status == "dropped" else None
        indicators = json.loads(row.get("indicators") or "{}")
        primary = next(iter(indicators), None)
        value = ((None if row.get("M") is None else row["M"] * 100) if gated else
                 indicators.get(primary) if primary is not None else row.get("close"))
        value = None if value is None or pd.isna(value) else float(value)
        text = _catalog_row_text(row)
        if catalog.needs_model(book) and (side or row.get("entry") in ("oco", "grid")):
            text += " · " + _decision_text(event)
        fill_side = None if fill is None else int(fill.side)
        shown_side = fill_side if fill_side is not None else side
        fill_time = None if fill is None else _iso(pd.Timestamp(fill.fill_time))
        close = row.get("close")
        rows.append({"time": int(decision.timestamp()), "decision_time": _iso(decision), "side": side,
                     "fill_side": fill_side, "fill_time": fill_time, "value": value,
                     "close": None if close is None or pd.isna(close) else float(close),
                     "condition_met": opening,
                     "direction": "long" if shown_side > 0 else "short" if shown_side < 0 else None,
                     "signal_status": status, "signal_reason": reason, "text": text})
        model = json.loads(row.get("model") or "null")
        if model is not None:
            model_rows.append({"time": int(decision.timestamp()), "decision_time": _iso(decision), "side": 0,
                               "value": None if model["M"] is None else model["M"] * 100, "condition_met": False,
                               "signal_status": None, "text": _model_text(model, gated, spec.gate)})
    last = rows[-1] if rows else None
    primary_key = (next(iter(json.loads(signals.indicators.iloc[-1] or "{}")), None)
                   if not signals.empty and "indicators" in signals else None)
    holding = not positions.empty
    cadence = spec.cadence_min or 60
    now = pd.Timestamp.now(tz="UTC")
    next_decision = now.floor(f"{cadence}min") + pd.Timedelta(minutes=cadence)
    leg = {"candidate": f"catalog:{spec_id}", "name": catalog.label(book),
           "kind": "catalog", "value_label": "탐지기 M %" if gated else INDICATOR_LABELS.get(primary_key, primary_key or "종가"),
           "decision_cadence_minutes": cadence, "max_hold_hours": None,      # R2-52A: no max hold
           "last_decision": None if last is None else {"decision_time": last["decision_time"], "text": last["text"]},
           "next_estimate": None, "current_text": None if last is None else last["text"], "rows": rows,
           **{k: None for k in ("long_account_pct", "upper_pct", "lower_pct", "distance_to_short", "distance_to_long")}}
    legs = [leg]
    if model_rows:
        model_leg = {"candidate": f"model:{spec_id}", "name": "PatchTST 예측 (w730_raw, 15분마다)", "kind": "catalog",
                     "value_label": "탐지기 M %", "decision_cadence_minutes": 15, "max_hold_hours": None,
                     "last_decision": {"decision_time": model_rows[-1]["decision_time"], "text": model_rows[-1]["text"]},
                     "next_estimate": None, "current_text": model_rows[-1]["text"], "rows": model_rows,
                     **{k: None for k in ("long_account_pct", "upper_pct", "lower_pct", "distance_to_short",
                                          "distance_to_long")}}
        legs.append(model_leg)
    ax = _ax_state(connection, book)
    if ax is not None:
        legs.append({"candidate": f"ax:{spec_id}", "name": "적응형 청산 상태", "kind": "catalog",
                     "value_label": None, "decision_cadence_minutes": 1, "max_hold_hours": None,
                     "last_decision": None, "next_estimate": None, "current_text": _ax_text(ax), "rows": [], "ax": ax,
                     **{k: None for k in ("long_account_pct", "upper_pct", "lower_pct", "distance_to_short",
                                          "distance_to_long")}})
    cutoff = processed + pd.Timedelta(minutes=1) if processed is not None else None
    return {"schema_version": 3, "book": book, "tf": tf, "start_time": start_time, "source": "paper_catalog",
            "generated_at": _iso(now), "data_cutoff": (_iso(cutoff) if cutoff is not None else
                                                          None if last is None else last["decision_time"]),
            "summary": {"holding": holding, "holding_text": "보유 중, 신호 무시" if holding else "미보유",
                        "next_decision_time": _iso(next_decision),
                        "next_decision_kst": next_decision.tz_convert("Asia/Seoul").isoformat(),
                        "minutes_remaining": max(0, math.ceil((next_decision - now) / pd.Timedelta(minutes=1))),
                        "estimate_label": "5분 주기 계산",
                        "legs": [{k: x[k] for k in ("candidate", "name", "kind", "max_hold_hours",
                                                    "decision_cadence_minutes", "last_decision", "next_estimate",
                                                    "current_text")} for x in legs]},
            "legs": legs}


def _ax_state(connection: sqlite3.Connection, book: str) -> dict | None:
    """Open AX position state (scripts/paper_catalog.py catalog_ax_state)."""
    frame = _frame(connection, "catalog_ax_state", "book=? AND status='OPEN'", (book,))
    return None if frame.empty else _records(frame.sort_values("position_id"))[-1]


def _ax_text(ax: dict) -> str:
    value = lambda v, unit="": "—" if v is None else f"{float(v):,.2f}{unit}"
    return " · ".join([f"E0 {value(ax.get('e0_bps'), ' bps')}", f"E_t {value(ax.get('e_t_bps'), ' bps')}",
                       f"k {value(ax.get('k'))}", f"R0 {value(ax.get('r0_bps'), ' bps')}",
                       f"R_t {value(ax.get('r_bps'), ' bps')}", f"손절가 {value(ax.get('hard_stop'))}",
                       "추적 무장 " + ("예" if ax.get("trail_armed") else "아니오"),
                       f"최고/최저가 {value(ax.get('best_price'))}", f"추적 손절가 {value(ax.get('trail_stop'))}",
                       f"상태 청산 기준 {value(ax.get('anchor_upper') if ax.get('side', 0) > 0 else ax.get('anchor_lower'))}"])


def _decision_text(event: dict | None) -> str:
    if event is None:
        return "결정 대기(예측 대기)"
    status = event["status"]
    if status == "decided":
        lag = (pd.Timestamp(event["decided_at"]) - pd.Timestamp(event["signal_time"])).total_seconds()
        return f"결정 {_kst_hm(event['decision_time'])} KST · 체결 +1분 (신호 후 {lag:.0f}초)"
    return "만료(예측이 늦음)" if status == "expired_late" else "만료(예측 없음)"


def _kst_hm(value) -> str:
    return pd.Timestamp(value).tz_convert("Asia/Seoul").strftime("%H:%M")


def _model_text(model: dict, gated: bool, gate: str | None) -> str:
    parts = []
    if model.get("M") is not None:
        parts.append(f"M {model['M'] * 100:.0f}%")
    if model.get("L") is not None:
        parts.append(f"L {model['L'] * 100:.0f}%")
    if model.get("E_bps") is not None:
        parts.append(f"E(exc_{model['E_head']}) {model['E_bps']:.0f} bps")
    if model.get("available_at") and model.get("prediction_ts"):
        lag = (pd.Timestamp(model["available_at"]) - pd.Timestamp(model["prediction_ts"])).total_seconds()
        parts.append(f"예측 {_kst_hm(model['prediction_ts'])} KST, 생성 지연 {lag:.0f}초" if lag < 3600
                     else f"예측 {_kst_hm(model['prediction_ts'])} KST (백필)")
    elif model.get("M") is None:
        parts.append("예측 없음 → 신규 진입 금지")
    if gated and model.get("M") is not None:
        open_ = model["M"] >= 2 / 3 if gate == "HIGH" else model["M"] <= 1 / 3
        parts.append(("관문 열림" if open_ else "관문 닫힘") + (" (M ≥ 67%)" if gate == "HIGH" else " (M ≤ 33%)"))
    return " · ".join(parts)


def _conditions_payload(connection: sqlite3.Connection, cache: _ConditionCache,
                        book: str, tf: str,
                        start_time: str | None = None) -> dict[str, object]:
    requested_book = book
    if book.endswith("_x3"):
        book = book[:-3]
    if book in catalog.BOOKS:
        payload = _catalog_conditions(connection, book, tf, start_time)
        payload["book"] = requested_book
        state = _frame(connection, "leverage_state", "book=?", (requested_book,))
        if requested_book != book and not state.empty and state.status.iloc[0] != "RUNNING":
            payload["summary"]["note"] = "청산·중지된 장부입니다. 아래 값은 내부 원천 장부(1배) 상태입니다."
        return payload
    if book not in CONDITION_BOOKS and book not in catalog.BOOKS:
        raise ValueError(f"book must be one of {','.join((*CONDITION_BOOKS, *catalog.BOOKS))}")
    if tf not in TF_SECONDS:
        raise ValueError("tf must be one of 1m,5m,15m,1h,4h,1d")
    cached = cache.get(connection)
    market = cached["market"]
    market_times = market.open_time.array.asi8 if not market.empty else np.array([], dtype=np.int64)
    trades = _frame(connection, "trades", "book=? AND boundary='PESS'", (book,))
    accepted: set[tuple[int, str | None]] = set()
    if not trades.empty:
        accepted = {(pd.Timestamp(row.entry_time).value,
                     None if pd.isna(row.candidate) else str(row.candidate))
                    for row in trades.itertuples(index=False)}
    dropped = _frame(connection, "signals", "book=?", (book,))
    rejected: dict[tuple[int, str], str] = {}
    if not dropped.empty:
        rejected = {(pd.Timestamp(row.entry_time).value, str(row.candidate)): str(row.reason)
                    for row in dropped.itertuples(index=False)}
    position_table = "leverage_positions" if requested_book.endswith("_x3") else "positions"
    position = _frame(connection, position_table, "book=?", (requested_book,))
    holding = not position.empty
    # An open position is a filled entry too; without this the live entry showed as "dropped".
    for row in _frame(connection, "positions", "book=?", (book,)).itertuples(index=False):
        accepted.add((pd.Timestamp(row.entry_time).value, None))
    legs = []
    for candidate in CONDITION_BOOKS.get(book, ()):    # catalog books have no condition panel yet
        frame = cached["details"][candidate]
        rows = []
        for row in frame.itertuples(index=False):
            execution_ns = None
            if len(market_times):
                location = int(np.searchsorted(market_times, row.decision_time.value, side="left"))
                if location < len(market_times):
                    execution_ns = int(market_times[location])
            signal_status = signal_reason = None
            if int(row.side):
                if execution_ns is not None and ((execution_ns, candidate) in accepted or
                                                 (execution_ns, None) in accepted):
                    signal_status = "filled"
                else:
                    signal_status = "dropped"
                    signal_reason = rejected.get((execution_ns, candidate), "holding")
            ratio = None if pd.isna(row.global_ls_account) else float(row.global_ls_account)
            lower = None if pd.isna(row.lower_threshold) else float(row.lower_threshold)
            upper = None if pd.isna(row.upper_threshold) else float(row.upper_threshold)
            display = ({
                "prior_low_20": None if pd.isna(row.prior_low_20) else float(row.prior_low_20),
                "current_volume": float(row.volume),
                "required_volume": None if pd.isna(row.required_volume) else float(row.required_volume),
            } if candidate == rules.E1 else {})
            rows.append({
                "time": int(row.decision_time.timestamp()),
                "decision_time": _iso(row.decision_time),
                "global_ls_account": ratio, "lower_threshold": lower, "upper_threshold": upper,
                "volume_zscore": None if pd.isna(row.volume_zscore) else float(row.volume_zscore),
                "prior_high_20": None if pd.isna(row.prior_high_20) else float(row.prior_high_20),
                "close": float(row.close), "side": int(row.side), **display,
                "condition_met": bool(row.side), "direction": (
                    "long" if row.side > 0 else "short" if row.side < 0 else None),
                "signal_status": signal_status, "signal_reason": signal_reason,
            })
        last = _condition_value(None if frame.empty else frame.iloc[-1])
        estimate = _condition_value(cached["estimates"][candidate])
        current = estimate or last
        readable_fields = ("long_account_pct", "upper_pct", "lower_pct",
                           "distance_to_short", "distance_to_long")
        legs.append({"candidate": candidate, "name": CONDITION_NAMES[candidate],
                     "kind": ("breakout" if candidate == rules.E1 else
                              "trend" if candidate == rules.F3_FLIP else "contrarian"),
                     "decision_cadence_minutes": 5 if candidate == rules.F3_5M else 60,
                     "max_hold_hours": rules.SPECS[candidate].max_hold,
                     "last_decision": last, "next_estimate": estimate,
                     **{name: None if current is None else current[name]
                        for name in readable_fields},
                     "current_text": _condition_text(candidate, current), "rows": rows})
    now = pd.Timestamp.now(tz="UTC")
    cadence = (CATALOG[catalog.BOOKS[book][0]].cadence_min or 60 if book in catalog.BOOKS else
               5 if rules.F3_5M in CONDITION_BOOKS[book] else 60)
    next_decision = now.floor(f"{cadence}min") + pd.Timedelta(minutes=cadence)
    remaining = max(0, math.ceil((next_decision - now) / pd.Timedelta(minutes=1)))
    return {"schema_version": 3, "book": requested_book, "tf": tf,
            "start_time": start_time,
            "source": cached["source"],
            "generated_at": _iso(now),
            "data_cutoff": None if cached["data_cutoff"] is None else _iso(cached["data_cutoff"]),
            "summary": {"holding": holding,
                        "holding_text": "보유 중, 신호 무시" if holding else "미보유",
                        "next_decision_time": _iso(next_decision),
                        "next_decision_kst": next_decision.tz_convert("Asia/Seoul").isoformat(),
                        "minutes_remaining": remaining,
                        "estimate_label": "현재까지 데이터 기준",
                        "legs": [{key: leg[key] for key in
                                  ("candidate", "name", "kind", "max_hold_hours",
                                   "decision_cadence_minutes",
                                   "last_decision", "next_estimate", "current_text")}
                                 for leg in legs]},
            "legs": legs}


def _candle_rows(connection: sqlite3.Connection, tf: str, start: str | None,
                 end: str | None) -> tuple[list[dict[str, object]], dict[str, object]]:
    if tf not in TF_SECONDS:
        raise ValueError("tf must be one of 1m,5m,15m,1h,4h,1d")
    seconds = TF_SECONDS[tf]
    last_row = connection.execute(
        "SELECT open_time, close FROM klines_1m WHERE closed=1 ORDER BY open_time DESC LIMIT 1"
    ).fetchone()
    if last_row is None:
        return [], {"latest_price": None, "latest_time": None}
    last_time = _utc(str(last_row["open_time"]))
    assert last_time is not None
    end_stamp = _utc(end) or (last_time + pd.Timedelta(minutes=1))
    start_stamp = _utc(start)
    if start_stamp is None:
        start_stamp = last_time.floor(pd.Timedelta(seconds=seconds)) - pd.Timedelta(seconds=seconds * (MAX_CANDLES - 1))
    if end_stamp <= start_stamp:
        raise ValueError("to must be later than from")
    start_epoch = int(start_stamp.timestamp()) // seconds * seconds
    end_epoch = int(end_stamp.timestamp())
    # Indexed range probes avoid a million-row GROUP BY when 1d candles cover two years.
    rows = connection.execute("""
        WITH RECURSIVE bins(epoch) AS (
            VALUES(?) UNION ALL SELECT epoch+? FROM bins
            WHERE epoch+? < ? LIMIT ?
        ), ranges AS (
            SELECT epoch, MAX(epoch,?) AS lower_epoch, MIN(epoch+?,?) AS upper_epoch FROM bins
        ), candles AS (
            SELECT epoch,
                (SELECT open FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')
                 ORDER BY open_time LIMIT 1) AS open,
                (SELECT MAX(high) FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')) AS high,
                (SELECT MIN(low) FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')) AS low,
                (SELECT close FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')
                 ORDER BY open_time DESC LIMIT 1) AS close,
                (SELECT SUM(volume) FROM klines_1m WHERE closed=1
                 AND open_time>=strftime('%Y-%m-%dT%H:%M:%S+00:00',lower_epoch,'unixepoch')
                 AND open_time<strftime('%Y-%m-%dT%H:%M:%S+00:00',upper_epoch,'unixepoch')) AS volume
            FROM ranges
        )
        SELECT * FROM candles WHERE open IS NOT NULL ORDER BY epoch
    """, (start_epoch, seconds, seconds, end_epoch, MAX_CANDLES,
           int(start_stamp.timestamp()), seconds, end_epoch)).fetchall()
    payload = [{"time": int(row["epoch"]),
                "time_utc": datetime.fromtimestamp(int(row["epoch"]), timezone.utc).isoformat().replace("+00:00", "Z"),
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "volume": float(row["volume"])} for row in rows]
    return payload, {"latest_price": float(last_row["close"]), "latest_time": _iso(last_time)}


def _position_markers(positions: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for position in positions.to_dict("records"):
        side = int(position["side"])
        rows.append({"trade_id": None, "side": side, "side_label": "롱" if side > 0 else "숏",
                     "kind": "entry", "time": int(_utc(position["entry_time"]).timestamp()),
                     "time_utc": position["entry_time"], "price": float(position["entry_price"]),
                     "net_bps": None, "pnl_usd": None, "exit_reason": "보유 중"})
    return rows


def _trade_markers(trades: pd.DataFrame) -> list[dict[str, object]]:
    if trades.empty:
        return []
    if "boundary" in trades and trades.boundary.eq("PESS").any():
        trades = trades.loc[trades.boundary.eq("PESS")]
    rows: list[dict[str, object]] = []
    for trade in trades.sort_values("entry_time").to_dict("records"):
        side = int(trade["side"])
        net_bps, pnl_usd = trade.get("net_bps"), trade.get("pnl_usd")
        common = {"trade_id": int(trade["id"]), "side": side,
                  "side_label": "롱" if side > 0 else "숏"}
        rows.append({**common, "kind": "entry", "time": int(_utc(trade["entry_time"]).timestamp()),
                     "time_utc": trade["entry_time"], "price": float(trade["entry_price"]),
                     "net_bps": None if net_bps is None else float(net_bps),
                     "pnl_usd": None if pnl_usd is None else float(pnl_usd),
                     "exit_reason": trade["exit_reason"]})
        rows.append({**common, "kind": "exit", "time": int(_utc(trade["exit_time"]).timestamp()),
                     "time_utc": trade["exit_time"], "price": float(trade["exit_price"]),
                     "net_bps": None if net_bps is None else float(net_bps),
                     "pnl_usd": None if pnl_usd is None else float(pnl_usd),
                     "exit_reason": trade["exit_reason"]})
    return rows


def _with_forming(connection: sqlite3.Connection, tf: str, rows: list[dict[str, object]],
                  latest: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Append the live in-progress 1m bar (display only) to the last timeframe bucket."""
    raw = _meta(connection, "forming_kline")
    if not raw:
        return rows, latest
    forming = json.loads(raw)
    stamp = _utc(forming["open_time"])
    last_closed = _utc(latest.get("latest_time")) if latest.get("latest_time") else None
    if stamp is None or (last_closed is not None and stamp <= last_closed):
        return rows, latest
    seconds = TF_SECONDS[tf]
    epoch = int(stamp.timestamp()) // seconds * seconds
    rows = [dict(row) for row in rows]
    if rows and int(rows[-1]["time"]) == epoch:
        bar = rows[-1]
        bar.update(high=max(float(bar["high"]), forming["high"]), low=min(float(bar["low"]), forming["low"]),
                   close=forming["close"], volume=float(bar["volume"]) + forming["volume"])
    elif not rows or int(rows[-1]["time"]) < epoch:
        rows.append({"time": epoch, "time_utc": _iso(pd.Timestamp(epoch, unit="s", tz="UTC")),
                     "open": forming["open"], "high": forming["high"], "low": forming["low"],
                     "close": forming["close"], "volume": forming["volume"]})
    rows[-1]["forming"] = True
    return rows, {**latest, "latest_price": forming["close"], "latest_time": forming["updated_at"],
                  "forming": True}


def _drawdown(values: pd.Series) -> pd.Series:
    return values.cummax().clip(lower=0) - values


def _first_open_at(connection: sqlite3.Connection, time: pd.Timestamp) -> float | None:
    try:
        row = connection.execute("SELECT open FROM klines_1m WHERE closed=1 AND open_time>=? "
                                 "ORDER BY open_time LIMIT 1", (time.isoformat(),)).fetchone()
    except sqlite3.OperationalError:   # no 1m table (e.g. a reduced test database)
        return None
    return None if row is None else float(row[0])


def _has_minutes(connection: sqlite3.Connection) -> bool:
    try:
        return connection.execute("SELECT 1 FROM klines_1m LIMIT 1").fetchone() is not None
    except sqlite3.OperationalError:
        return False


def _open_unrealized_bps(connection: sqlite3.Connection, book: str) -> float:
    """Gross mark of the open position (no exit cost), 0 when flat."""
    try:
        row = connection.execute("SELECT unrealized_bps FROM positions WHERE book=?", (book,)).fetchone()
    except sqlite3.OperationalError:
        return 0.0
    return 0.0 if row is None or row[0] is None else float(row[0])


def _performance(connection: sqlite3.Connection, book: str,
                 daily_prices: list[dict[str, object]] | None = None,
                 start_time: str | None = None) -> dict[str, object]:
    if book.endswith("_x3"):
        daily = _frame(connection, "leverage_daily", "book=?", (book,))
        trades = _frame(connection, "leverage_trades", "book=?", (book,))
        state = _frame(connection, "leverage_state", "book=?", (book,))
        row = {} if state.empty else _records(state)[0]
        summary = {"book": book, "leverage": True, "trade_count": len(trades),
                   "win_rate": None if trades.empty else float((trades.pnl_usd > 0).mean()),
                   "balance_usd": row.get("balance_usd", 100.0),
                   "cumulative_pnl_usd": row.get("cumulative_pnl_usd", 0.0),
                   "cumulative_return_pct": row.get("cumulative_return_pct", 0.0),
                   "max_drawdown_usd": row.get("max_drawdown_usd", 0.0),
                   "max_drawdown_pct": row.get("max_drawdown_pct", 0.0),
                   "status": row.get("status", "RUNNING")}
        series = [] if daily.empty else [{"name": "X3", "date": daily.date.tolist(),
            "cumulative_pnl_usd": (daily.balance_usd - 100.0).tolist(),
            "drawdown_usd": daily.max_drawdown_usd.tolist()}]
        monthly = [] if daily.empty else _records(
            daily.assign(month=daily.date.str[:7]).groupby("month", as_index=False).day_pnl_usd.sum())
        return {"schema_version": 2, "book": book, "summary": summary,
                "series": series, "monthly": monthly}
    daily = _frame(connection, "daily_pnl", "book=?", (book,))
    trades = _frame(connection, "trades", "book=?", (book,))
    series: list[dict[str, object]] = []
    summary: dict[str, object] = {"book": book, "trade_count": 0, "win_rate": None,
                                  "net_pess_bps": 0.0, "net_opt_bps": 0.0,
                                  "max_drawdown_bps": 0.0, "buy_hold_bps": None,
                                  "vs_buy_hold_bps": None,
                                  "unrealized_bps": _open_unrealized_bps(connection, book)}
    if not trades.empty:
        pess = trades.loc[trades.boundary.eq("PESS")] if "boundary" in trades else trades
        summary["trade_count"] = int(len(pess))
        summary["win_rate"] = None if pess.empty else float((pess.net_bps > 0).mean())
    if not daily.empty:
        for boundary, part in daily.groupby("boundary", sort=True):
            part = part.sort_values("date")
            cumulative = part.net_bps.astype(float).cumsum()
            drawdown = _drawdown(cumulative)
            series.append({"name": str(boundary), "date": part.date.astype(str).tolist(),
                           "cumulative_net_bps": cumulative.tolist(),
                           "drawdown_bps": drawdown.tolist()})
            summary[f"net_{str(boundary).lower()}_bps"] = float(cumulative.iloc[-1])
            if boundary == "PESS":
                summary["max_drawdown_bps"] = float(drawdown.max())
        monthly = (daily.assign(month=daily.date.astype(str).str[:7])
                   .groupby(["month", "boundary"], as_index=False).net_bps.sum())
        monthly_rows = _records(monthly)
    else:
        monthly_rows = []
    if daily_prices is None:
        daily_prices, _ = _candle_rows(connection, "1d", None, None)
    prices = pd.DataFrame(daily_prices or [])
    anchor = None
    if start_time is not None and not prices.empty:
        # Buy-and-hold is the paper benchmark, so it starts at T0 like the books (none before T0):
        # keep the daily bar that contains T0 and price the entry at the first 1m open at or after T0.
        t0 = _utc(start_time)
        prices = prices.loc[pd.to_datetime(prices.time_utc, utc=True) >= t0.floor("D")]
        anchor = _first_open_at(connection, t0)
        if anchor is None and _has_minutes(connection):     # book not started yet: no benchmark
            prices = prices.iloc[0:0]
    if not prices.empty:
        entry = anchor if anchor is not None else float(prices.open.iloc[0])
        buy_hold = np.log(prices.close.astype(float) / entry) * 10_000
        series.append({"name": "BUY_HOLD", "date": prices.time_utc.str[:10].tolist(),
                       "cumulative_net_bps": buy_hold.tolist(),
                       "drawdown_bps": _drawdown(buy_hold).tolist()})
        # The open position's mark-to-market belongs in the comparison; closed trades alone hide it.
        unrealized = float(summary["unrealized_bps"])
        summary["buy_hold_bps"] = float(buy_hold.iloc[-1])
        summary["vs_buy_hold_bps"] = float(summary["net_pess_bps"]) + unrealized - float(buy_hold.iloc[-1])
    return {"schema_version": 2, "book": book, "summary": summary,
            "series": series, "monthly": monthly_rows}


def _book_rows(connection: sqlite3.Connection, book_names: tuple[str, ...],
               start_time: str | None,
               book_start_times: Mapping[str, str] | None = None,
               leverage_book_names: tuple[str, ...] | None = None,
               x3_only: bool = False) -> list[dict[str, object]]:
    positions, trades, daily = (_frame(connection, name) for name in ("positions", "trades", "daily_pnl"))
    last = _meta(connection, "last_processed_minute")
    names = [] if x3_only else list(dict.fromkeys((*book_names, *sorted(set(trades.get("book", ())) |
                                                                      set(positions.get("book", ()))))))
    starts = book_start_times or {}
    next_funding = _iso(_utc(last).floor("8h") + pd.Timedelta(hours=8)) if last else None
    rows = []
    for name in names:
        book_start = starts.get(name, start_time)
        started = book_start is None or (last is not None and _utc(last) >= _utc(book_start))
        trade_part = trades.loc[trades.book.eq(name)] if not trades.empty else trades
        position = positions.loc[positions.book.eq(name)] if not positions.empty else positions
        daily_part = daily.loc[daily.book.eq(name)] if not daily.empty else daily
        net = {boundary: float(part.net_bps.sum())
               for boundary, part in daily_part.groupby("boundary")} if not daily_part.empty else {}
        pess = trade_part.loc[trade_part.boundary.eq("PESS")] if (
            not trade_part.empty and "boundary" in trade_part) else trade_part
        cumulative = daily_part.loc[daily_part.boundary.eq("PESS")].sort_values("date").net_bps.cumsum(
            ) if not daily_part.empty else pd.Series(dtype=float)
        rows.append({"book": name, "display_book": BOOK_LABELS.get(name) or (
                         catalog.label(name) if name in catalog.BOOKS else name),
                     "start_time": book_start,
                     "position": None if position.empty else _records(position)[0],
                     "trades": int(len(pess)),
                     "net_bps": net.get("PESS", 0.0),
                     "net_pess_bps": net.get("PESS", 0.0), "net_opt_bps": net.get("OPT", 0.0),
                     "win_rate": None if pess.empty else float((pess.net_bps > 0).mean()),
                     "max_drawdown_bps": 0.0 if cumulative.empty else float(_drawdown(cumulative).max()),
                     "nonleveraged_balance_usd": 100.0 * math.exp(net.get("PESS", 0.0) / 10_000),
                     "nonleveraged_pnl_usd": 100.0 * math.expm1(net.get("PESS", 0.0) / 10_000),
                     "next_funding": next_funding,
                     "status": "running" if started else f"T0 대기 ({book_start})"})
    states = _frame(connection, "leverage_state")
    leverage_positions = _frame(connection, "leverage_positions")
    leverage_trades = _frame(connection, "leverage_trades")
    if states.empty and not x3_only:
        return rows
    for source_name in leverage_book_names or book_names:
        book_start = starts.get(source_name, start_time)
        started = book_start is None or (last is not None and _utc(last) >= _utc(book_start))
        name = f"{source_name}_x3"
        state = states.loc[states.book.eq(name)] if not states.empty else states
        position = (leverage_positions.loc[leverage_positions.book.eq(name)]
                    if not leverage_positions.empty else leverage_positions)
        trade_part = (leverage_trades.loc[leverage_trades.book.eq(name)]
                      if not leverage_trades.empty else leverage_trades)
        value = {} if state.empty else _records(state)[0]
        rows.append({"book": name, "display_book": (catalog.label(name) if source_name in catalog.BOOKS else
                                                    f"{source_name} ×3"),
                     "position": None if position.empty else _records(position)[0],
                     "trades": len(trade_part),
                     "win_rate": None if trade_part.empty else float((trade_part.pnl_usd > 0).mean()),
                     "balance_usd": value.get("balance_usd", 100.0),
                     "cumulative_pnl_usd": value.get("cumulative_pnl_usd", 0.0),
                     "cumulative_return_pct": value.get("cumulative_return_pct", 0.0),
                     "max_drawdown_usd": value.get("max_drawdown_usd", 0.0),
                     "max_drawdown_pct": value.get("max_drawdown_pct", 0.0),
                     "start_time": book_start,
                     "status": (value.get("status", "RUNNING") if started else
                                f"T0 대기 ({book_start})")})
    return rows


def _all_positions(connection: sqlite3.Connection) -> pd.DataFrame:
    frames = [_frame(connection, name) for name in ("positions", "leverage_positions")]
    return pd.concat([frame for frame in frames if not frame.empty], ignore_index=True, sort=False) if any(
        not frame.empty for frame in frames) else pd.DataFrame()


def _all_trades(connection: sqlite3.Connection) -> pd.DataFrame:
    frames = [_frame(connection, name) for name in ("trades", "leverage_trades")]
    return pd.concat([frame for frame in frames if not frame.empty], ignore_index=True, sort=False) if any(
        not frame.empty for frame in frames) else pd.DataFrame()


class DashboardServer(ThreadingHTTPServer):
    # Default backlog of 5 overflowed when a page refresh (~8 parallel calls through the
    # tunnel) met a slow conditions request; Windows then refused connections outright.
    request_queue_size = 128
    store_path: Path
    data_root: Path


def _handler(store_path: Path, data_root: Path, books: tuple[str, ...] = (),
             start_time: str | None = None,
             book_start_times: Mapping[str, str] | None = None,
             leverage_books: tuple[str, ...] | None = None,
             primary_book: str | None = None) -> type[BaseHTTPRequestHandler]:
    configured_books = books or DEFAULT_BOOKS
    configured_starts = dict(book_start_times or {})
    configured_leverage = configured_books if leverage_books is None else leverage_books
    # R2-52A: with AX sources only the derived x3 books are visible; hidden 1x sources and retired rows never appear
    x3_only = bool(configured_leverage) and all(name in catalog.BOOKS for name in configured_leverage)
    visible = tuple(f"{name}_x3" for name in configured_leverage) if x3_only else None
    default_book = ((f"{primary_book}_x3" if primary_book and f"{primary_book}_x3" in visible else visible[0])
                    if x3_only else configured_books[0])
    configured_books = visible if x3_only else configured_books

    def shown(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.loc[frame.book.isin(visible)] if x3_only and not frame.empty else frame

    def requested(query: dict[str, list[str]]) -> str:
        book = query.get("book", [default_book])[0]
        if x3_only and book not in visible:
            raise ValueError(f"book must be one of {','.join(visible)}")
        return book

    def book_start(book: str) -> str | None:
        source = book[:-3] if book.endswith("_x3") else book
        return configured_starts.get(source, start_time)
    condition_cache = _ConditionCache()
    with _connect_ro(store_path) as connection:
        condition_cache.get(connection)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, value: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(value)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(value)

        def _json(self, value: object, status: int = 200) -> None:
            self._send(json.dumps(value, ensure_ascii=False, allow_nan=False, default=str).encode(),
                       "application/json; charset=utf-8", status)

        def _csv(self, frame: pd.DataFrame) -> None:
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=list(frame.columns))
            writer.writeheader(); writer.writerows(_records(frame))
            self._send(stream.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook
            parsed, query = urlparse(self.path), parse_qs(urlparse(self.path).query)
            try:
                static = {"/": (STATIC, "text/html; charset=utf-8"),
                          "/vendor/lightweight-charts.standalone.production.js":
                              (VENDOR / "lightweight-charts.standalone.production.js", "application/javascript; charset=utf-8"),
                          "/vendor/LICENSE": (VENDOR / "LICENSE", "text/plain; charset=utf-8"),
                          "/vendor/README.md": (VENDOR / "README.md", "text/markdown; charset=utf-8")}
                if parsed.path in static:
                    path, content_type = static[parsed.path]
                    self._send(path.read_bytes(), content_type); return
                if parsed.path == "/plotly.min.js":
                    self._send(get_plotlyjs().encode(), "application/javascript; charset=utf-8"); return
                with _connect_ro(store_path) as connection:
                    if self._v2(connection, parsed.path, query): return
                    if self._v1(connection, parsed.path, query): return
                self._json({"error": "not found"}, 404) if parsed.path.startswith("/api/") else self._send(
                    b"not found", "text/plain", 404)
            except (ValueError, TypeError) as error:
                self._json({"error": str(error)}, 400)

        def _v2(self, connection: sqlite3.Connection, path: str,
                query: dict[str, list[str]]) -> bool:
            if path == "/api/candles":
                tf = query.get("tf", ["1h"])[0]
                rows, latest = _candle_rows(connection, tf, query.get("from", [None])[0],
                                            query.get("to", [None])[0])
                if not query.get("to"):
                    rows, latest = _with_forming(connection, tf, rows, latest)
                self._json({"schema_version": 2, "tf": tf, "max_rows": MAX_CANDLES,
                            "rows": rows, **latest}); return True
            if path == "/api/markers":
                book = requested(query)
                table = "leverage_trades" if book.endswith("_x3") else "trades"
                open_table = "leverage_positions" if book.endswith("_x3") else "positions"
                rows = (_trade_markers(_frame(connection, table, "book=?", (book,))) +
                        _position_markers(_frame(connection, open_table, "book=?", (book,))))
                self._json({"schema_version": 2, "book": book,
                            "rows": sorted(rows, key=lambda row: (row["time"], row["kind"] != "entry"))})
                return True
            if path in {"/api/positions", "/api/positions.csv"}:
                frame = shown(_all_positions(connection))
                if query.get("book") and not frame.empty: frame = frame.loc[frame.book.eq(query["book"][0])]
                self._csv(frame) if path.endswith(".csv") else self._json({"schema_version": 2, "rows": _records(frame)})
                return True
            if path in {"/api/trades", "/api/trades.csv", "/api/signals", "/api/signals.csv"}:
                table = "trades" if "trades" in path else "signals"
                time_column = "entry_time" if table == "trades" else "decision_time"
                clauses, parameters = [], []
                if query.get("book"): clauses.append("book=?"); parameters.append(query["book"][0])
                if query.get("from"): clauses.append(f"{time_column}>=?"); parameters.append(_iso(_utc(query["from"][0])))
                if query.get("to"): clauses.append(f"{time_column}<?"); parameters.append(_iso(_utc(query["to"][0])))
                if table == "trades":
                    frame = shown(_all_trades(connection))
                    if query.get("book") and not frame.empty:
                        frame = frame.loc[frame.book.eq(query["book"][0])]
                    if query.get("from") and not frame.empty:
                        frame = frame.loc[pd.to_datetime(frame[time_column], utc=True) >= _utc(query["from"][0])]
                    if query.get("to") and not frame.empty:
                        frame = frame.loc[pd.to_datetime(frame[time_column], utc=True) < _utc(query["to"][0])]
                else:
                    frame = shown(_frame(connection, table, " AND ".join(clauses), tuple(parameters)))
                if not frame.empty: frame = frame.sort_values(time_column, ascending=False, kind="stable")
                self._csv(frame) if path.endswith(".csv") else self._json({"schema_version": 1, "rows": _records(frame)})
                return True
            if path == "/api/performance":
                book = requested(query)
                self._json(_performance(connection, book, start_time=book_start(book))); return True
            if path == "/api/status":
                self._json(self._status(connection)); return True
            if path == "/api/conditions":
                book = requested(query)
                tf = query.get("tf", ["1h"])[0]
                self._json(_conditions_payload(connection, condition_cache, book, tf,
                                                book_start(book))); return True
            return False

        def _v1(self, connection: sqlite3.Connection, path: str,
                query: dict[str, list[str]]) -> bool:
            if path == "/api/summary":
                positions, trades, signals, daily = (shown(_frame(connection, name)) for name in
                                                      ("positions", "trades", "signals", "daily_pnl"))
                if x3_only:
                    positions, trades = shown(_all_positions(connection)), shown(_all_trades(connection))
                self._json({"schema_version": 1, "books": sorted(set(trades.get("book", ()))),
                            "position_count": len(positions), "trade_count": len(trades),
                            "signal_count": len(signals), "daily_count": len(daily)}); return True
            if path == "/api/books":
                self._json({"schema_version": 1, "default_book": default_book, "rows": _book_rows(
                    connection, configured_books, start_time, configured_starts,
                    configured_leverage, x3_only)}); return True
            if path == "/api/chart":
                rows = []
                daily_prices, _ = _candle_rows(connection, "1d", None, None)
                for book in configured_books:
                    for item in _performance(connection, book, daily_prices, book_start(book))["series"]:
                        rows.append({"book": book if item["name"] != "BUY_HOLD" else "BUY_HOLD",
                                     "boundary": item["name"], **{key: item[key] for key in
                                     ("date", "cumulative_net_bps", "drawdown_bps", "cumulative_pnl_usd",
                                      "drawdown_usd") if key in item}, "monthly": {}})
                self._json({"schema_version": 1, "series": rows}); return True
            if path == "/api/price":
                candles, _ = _candle_rows(connection, "1h", None, None)
                trades = shown(_all_trades(connection)) if x3_only else _frame(connection, "trades")
                markers = [] if trades.empty else _records(trades[["book", "entry_time", "exit_time",
                                                                   "entry_price", "exit_price", "side"]])
                self._json({"schema_version": 1, "price": [{"open_time": x["time_utc"], "close": x["close"]}
                                                            for x in candles], "markers": markers}); return True
            if path == "/api/reference":
                self._json({"schema_version": 1, "rows": self._reference()}); return True
            if path == "/api/health":
                status = self._status(connection)
                self._json({"schema_version": 1, "mode": "paper", "last_update": status["last_update_utc"],
                            "latest": status["sources"], "revision_count": status["reconcile"]["revision_count"],
                            "latency": status["latency"], "ws_closed_events": status["ws_closed_events"],
                            "notifications": status["notifications"], "book_ticker": status["book_ticker"],
                            "disk_free_ratio": status["disk_free_ratio"], "disk_warning": status["disk_warning"],
                            "credentials": _public_status()[0], "telegram": status["telegram"]}); return True
            return False

        def _reference(self) -> list[dict[str, object]]:
            rows = []
            timing_path = REPO_ROOT / "out/k45_ls_ratio_timing_r2_35_20261006/performance.parquet"
            if timing_path.exists():
                frame = pd.read_parquet(timing_path)
                frame = frame.loc[frame.delay_min.isin((0, 5)) & frame.cost_bps.eq(4)].copy()
                frame["timing_status"] = frame.delay_min.map({
                    5: "채택:+5분(create_time+5m<T)", 0: "legacy(시각 결함):create_time 즉시 가용"})
                frame["reference_primary"] = frame.delay_min.eq(5); rows.extend(_records(frame))
            e1_path = REPO_ROOT / "out/k45_candidate_compare_r2_23_20261004/metrics.parquet"
            if e1_path.exists():
                frame = pd.read_parquet(e1_path)
                frame = frame.loc[frame.candidate.eq("E1|1h|3|signal|L") &
                                  frame.segment.isin(("DEV_COMMON", "HOLD_B"))].copy()
                frame["timing_status"] = "not-affected:no-ls-ratio"; frame["reference_primary"] = True
                rows.extend(_records(frame))
            return rows

        def _status(self, connection: sqlite3.Connection) -> dict[str, object]:
            now = pd.Timestamp.now(tz="UTC")
            last = _meta(connection, "last_processed_minute")
            if last is None:
                last = connection.execute("SELECT MAX(open_time) FROM klines_1m").fetchone()[0]
            last_stamp, start_stamp = _utc(last), _utc(start_time)
            started = start_stamp is None or now >= start_stamp
            elapsed_days = 0 if not started or start_stamp is None else int((now - start_stamp).total_seconds() // 86400)
            latest_health, recent_health = pd.DataFrame(), pd.DataFrame()
            if _has_table(connection, "collector_health"):
                latest_health = pd.read_sql_query("""
                    SELECT * FROM collector_health ORDER BY minute DESC LIMIT 10000
                """, connection)
                latest_health = (latest_health.sort_values("minute", ascending=False)
                                 .drop_duplicates("source").sort_values("source"))
                recent_health = _frame(connection, "collector_health", "minute>=?",
                                       (_iso((last_stamp or now) - pd.Timedelta(hours=24)),))
            latency = [{"source": source, "count": len(part),
                        "p50_ms": float(part.lag_ms.quantile(.5)), "p95_ms": float(part.lag_ms.quantile(.95))}
                       for source, part in recent_health.dropna(subset=["lag_ms"]).groupby("source")]
            gap_count = int(recent_health.gaps.sum()) if not recent_health.empty else 0
            stale = last_stamp is None or (now >= last_stamp and now - last_stamp > pd.Timedelta(minutes=3))
            delayed = stale or not latency or max((x["p95_ms"] for x in latency), default=0) > 10_000
            state = "갭" if gap_count else "지연" if delayed else "정상"
            counts: dict[str, int] = {}
            if _has_table(connection, "notifications"):
                counts = {str(row[0]): int(row[1]) for row in connection.execute(
                    "SELECT status, COUNT(*) FROM notifications GROUP BY status")}
            ticker_count, ticker_last, ticker_gaps = 0, None, 0
            if _has_table(connection, "book_ticker_1m"):
                ticker_row = connection.execute(
                    "SELECT COUNT(*), MIN(minute), MAX(minute) FROM book_ticker_1m").fetchone()
                ticker_count, ticker_first, ticker_last = int(ticker_row[0]), ticker_row[1], ticker_row[2]
                if ticker_count > 1:
                    span = (_utc(ticker_last) - _utc(ticker_first)) / pd.Timedelta(minutes=1)
                    ticker_gaps = max(0, int(span) + 1 - ticker_count)
            revision_count = (int(connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0])
                              if _has_table(connection, "revisions") else 0)
            usage = shutil.disk_usage(data_root if data_root.exists() else data_root.parent)
            market_rows, latest = _candle_rows(connection, "1m",
                                                _iso((last_stamp or now) - pd.Timedelta(hours=24)), None)
            market_rows, latest = _with_forming(connection, "1m", market_rows, latest)
            change = None if not market_rows else (float(latest["latest_price"]) / float(market_rows[0]["open"]) - 1) * 100
            return {"schema_version": 2, "mode": "paper", "symbol": "BTCUSDT", "contract": "무기한",
                    "market": {**latest, "change_24h_pct": change},
                    "t0": {"start_time": start_time, "state": "진행" if started else "대기", "elapsed_days": elapsed_days},
                    "collector": {"state": state, "gap_count_24h": gap_count},
                    "sources": _records(latest_health), "latency": latency,
                    "last_update_utc": None if last_stamp is None else _iso(last_stamp),
                    "last_refresh_utc": _iso(now), "last_refresh_kst": now.tz_convert("Asia/Seoul").isoformat(),
                    "ws_closed_events": int(_meta(connection, "ws_closed_events") or 0),
                    "notifications": {"pending": int(counts.get("pending", 0)), "failed": int(counts.get("failed", 0))},
                    "book_ticker": {"rows": ticker_count, "gaps": ticker_gaps,
                                    "last_update": ticker_last},
                    "reconcile": {"result": "일치" if revision_count == 0 else "불일치",
                                  "revision_count": revision_count},
                    "disk_free_ratio": usage.free / usage.total, "disk_warning": usage.free / usage.total < .10,
                    "telegram": _public_status()[1]}

    return Handler


def make_server(store_path: str | Path, data_root: str | Path,
                host: str = "127.0.0.1", port: int = 8765, books: tuple[str, ...] = (),
                start_time: str | None = None,
                book_start_times: Mapping[str, str] | None = None,
                leverage_books: tuple[str, ...] | None = None,
                primary_book: str | None = None) -> DashboardServer:
    if host != "127.0.0.1":
        raise ValueError("dashboard must bind 127.0.0.1")
    path = Path(store_path)
    if not path.exists():
        raise FileNotFoundError(path)
    server = DashboardServer((host, port), _handler(
        path, Path(data_root), tuple(books), start_time, book_start_times, leverage_books, primary_book))
    server.store_path, server.data_root = path, Path(data_root)
    return server


__all__ = ["DashboardServer", "make_server"]
