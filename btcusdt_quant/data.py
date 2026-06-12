from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    number_of_trades: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float
    gap_flag: int = 0
    gap_length: int = 0
    gap_ratio_20: float = 0.0
    gap_ratio_60: float = 0.0
    gap_ratio_120: float = 0.0
    max_gap_run_120: int = 0
    repaired: bool = False


def utc_minute(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


class CanonicalTimelineBuilder:
    """Builds a strict 1-minute timeline from BTCUSDT kline-like candles."""

    def build(self, candles: Sequence[Candle]) -> List[Candle]:
        if not candles:
            return []
        ordered = sorted(candles, key=lambda candle: candle.open_time)
        by_time = {candle.open_time: candle for candle in ordered}
        start = ordered[0].open_time
        end = ordered[-1].open_time
        result: List[Candle] = []
        last_close = ordered[0].close
        gap_run = 0
        current = start
        while current <= end:
            candle = by_time.get(current)
            if candle is None:
                gap_run += 1
                candle = Candle(
                    open_time=current,
                    open=last_close,
                    high=last_close,
                    low=last_close,
                    close=last_close,
                    volume=0.0,
                    quote_volume=0.0,
                    number_of_trades=0,
                    taker_buy_base_volume=0.0,
                    taker_buy_quote_volume=0.0,
                    gap_flag=1,
                    gap_length=gap_run,
                    repaired=True,
                )
            else:
                gap_run = 0
                last_close = candle.close
                candle = replace(candle, gap_flag=0, gap_length=0, repaired=False)
            result.append(candle)
            current += timedelta(minutes=1)
        return self._attach_gap_metrics(result)

    def _attach_gap_metrics(self, candles: Sequence[Candle]) -> List[Candle]:
        enriched: List[Candle] = []
        flags: List[int] = []
        for candle in candles:
            flags.append(candle.gap_flag)
            enriched.append(
                replace(
                    candle,
                    gap_ratio_20=gap_ratio(flags, 20),
                    gap_ratio_60=gap_ratio(flags, 60),
                    gap_ratio_120=gap_ratio(flags, 120),
                    max_gap_run_120=max_gap_run(flags, 120),
                )
            )
        return enriched


def gap_ratio(flags: Sequence[int], window: int) -> float:
    recent = list(flags[-window:])
    if not recent:
        return 0.0
    return sum(1 for flag in recent if flag == 1) / len(recent)


def max_gap_run(flags: Sequence[int], window: int) -> int:
    best = 0
    current = 0
    for flag in flags[-window:]:
        if flag == 1:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


@dataclass(frozen=True)
class GapPolicyDecision:
    action: str
    reason: str
    threshold: float | None = None


class GapContaminationGovernance:
    DEFAULT_THRESHOLDS = {
        "price_return_features": 0.10,
        "volatility_features": 0.05,
        "volume_trade_flow_features": 0.02,
        "mark_premium_features": 0.05,
        "safety_features": 1.00,
    }

    def __init__(self, thresholds: dict[str, float] | None = None, max_gap_run_threshold: int = 3) -> None:
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)
        self.max_gap_run_threshold = max_gap_run_threshold

    def decide(self, feature_group: str, gap_ratio_value: float, max_gap_run_value: int, live: bool) -> GapPolicyDecision:
        threshold = self.thresholds.get(feature_group, 0.10)
        if feature_group == "safety_features":
            return GapPolicyDecision("keep_as_state", "safety features retain gap state", threshold)
        if max_gap_run_value >= self.max_gap_run_threshold:
            return GapPolicyDecision("block_new_entries" if live else "drop_sample", "max_gap_run threshold breached", threshold)
        if live:
            if gap_ratio_value >= 0.20:
                return GapPolicyDecision("block_new_entries", "live hard gap_ratio threshold breached", threshold)
            if gap_ratio_value >= 0.10:
                return GapPolicyDecision("warn", "live warning zone", threshold)
            return GapPolicyDecision("allow", "gap policy passed", threshold)
        if gap_ratio_value >= threshold:
            return GapPolicyDecision("drop_sample", "gap_ratio threshold breached", threshold)
        return GapPolicyDecision("allow", "gap policy passed", threshold)


def local_fixture() -> List[Candle]:
    base = utc_minute(2026, 1, 1, 0, 0)
    rows: List[Candle] = []
    for idx in [0, 1, 2, 5, 6, 7]:
        price = 100000.0 + idx * 10.0
        rows.append(
            Candle(
                open_time=base + timedelta(minutes=idx),
                open=price,
                high=price + 20.0,
                low=price - 20.0,
                close=price + 5.0,
                volume=10.0 + idx,
                quote_volume=(10.0 + idx) * price,
                number_of_trades=100 + idx,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=5.0 * price,
            )
        )
    return rows


def returns(candles: Iterable[Candle]) -> List[float]:
    output: List[float] = []
    previous: float | None = None
    for candle in candles:
        if previous is None or previous == 0.0:
            output.append(0.0)
        else:
            output.append((candle.close - previous) / previous)
        previous = candle.close
    return output
