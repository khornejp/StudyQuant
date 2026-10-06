"""Frozen F3, F3-w30 and E1 paper-trading rules.

All decisions use complete one-hour bars. Execution is the first available
one-minute open at or after the decision timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

F3 = "F3|1h|10/24|signal|LS"
F3_W30 = "F3_global_ls_account|1h|w30|q20|h12|LS"
E1 = "E1|1h|3|signal|L"
RULE_INPUT_COLUMNS = frozenset({"open_time", "open", "high", "low", "close", "volume",
                                "global_ls_account"})

TRADE_COLUMNS = [
    "entry_time", "exit_time", "side", "entry_price", "exit_price",
    "gross_bps", "cost_bps", "funding_bps", "net_bps", "hold_minutes",
]


@dataclass(frozen=True)
class RuleSpec:
    """Frozen rule parameters."""

    candidate: str
    quantile_window: int | None
    min_periods: int | None
    lower_quantile: float | None
    upper_quantile: float | None
    max_hold: int
    long_only: bool = False


SPECS = {
    F3: RuleSpec(F3, 2_160, 720, .10, .90, 24),
    F3_W30: RuleSpec(F3_W30, 720, 720, .20, .80, 12),
    E1: RuleSpec(E1, None, None, None, None, 20, True),
}


def aggregate_hourly(minutes: pd.DataFrame) -> pd.DataFrame:
    """Aggregate only complete UTC one-hour bars."""
    required = {"open_time", "open", "high", "low", "close", "volume"}
    missing = required - set(minutes)
    if missing:
        raise ValueError(f"minute columns missing: {sorted(missing)}")
    source = minutes.copy()
    source["open_time"] = pd.to_datetime(source.open_time, utc=True).astype("datetime64[ns, UTC]")
    source = source.sort_values("open_time", kind="stable")
    frame = source.set_index("open_time")
    grouped = frame.resample("60min", origin="epoch", label="left", closed="left")
    bars = grouped.agg(open=("open", "first"), high=("high", "max"),
                       low=("low", "min"), close=("close", "last"),
                       volume=("volume", "sum"))
    count = grouped["close"].count()
    bars = bars.loc[count.eq(60)].reset_index().rename(columns={"open_time": "bar_start"})
    bars["decision_time"] = bars.bar_start + pd.Timedelta(hours=1)
    cutoff = source.open_time.max() + pd.Timedelta(minutes=1)
    return bars.loc[bars.decision_time.le(cutoff)].reset_index(drop=True)


def _strict_prior_feature(bars: pd.DataFrame, features: pd.DataFrame,
                          column: str,
                          legacy_create_time_available: bool = False) -> pd.Series:
    columns = ["open_time", column] + (["source"] if "source" in features else [])
    source = features[columns].copy()
    source["open_time"] = pd.to_datetime(source.open_time, utc=True).astype("datetime64[ns, UTC]")
    if not legacy_create_time_available:
        archive = (source.source.ne("rest") if "source" in source else
                   pd.Series(True, index=source.index))
        # Archive create_time is period-start; F3 may use it only when create_time + 5m < T.
        source.loc[archive, "open_time"] += pd.Timedelta(minutes=5)
    source = source.sort_values("open_time", kind="stable")
    indices = np.searchsorted(source.open_time.array.asi8,
                              bars.decision_time.array.asi8, side="left") - 1
    if np.any(indices < 0):
        values = np.full(len(indices), np.nan)
        valid = indices >= 0
        values[valid] = source.iloc[indices[valid]][column].to_numpy(float)
        return pd.Series(values, index=bars.index)
    return source.iloc[indices][column].reset_index(drop=True)


def condition_details(minutes: pd.DataFrame, features: pd.DataFrame, candidate: str, *,
                      legacy_create_time_available: bool = False) -> pd.DataFrame:
    """Return frozen decisions and the exact indicator values which produced them."""
    if candidate not in SPECS:
        raise ValueError(f"unknown candidate: {candidate}")
    bars = (aggregate_hourly(minutes) if not minutes.empty else
            pd.DataFrame(columns=["bar_start", "decision_time", "open", "high", "low",
                                  "close", "volume"]))
    side = np.zeros(len(bars), np.int8)
    bars["global_ls_account"] = np.nan
    bars["lower_threshold"] = np.nan
    bars["upper_threshold"] = np.nan
    bars["volume_zscore"] = np.nan
    bars["prior_high_20"] = np.nan
    if bars.empty:
        bars["side"] = pd.Series(dtype=np.int8)
        return bars
    if candidate == E1:
        mean = bars.volume.rolling(20).mean()
        zscore = (bars.volume - mean) / bars.volume.rolling(20).std(ddof=0)
        prior_high = bars.high.rolling(20).max().shift()
        side[(zscore > 3).to_numpy() & bars.close.gt(prior_high).fillna(False).to_numpy()] = 1
        bars["volume_zscore"] = zscore
        bars["prior_high_20"] = prior_high
    else:
        spec = SPECS[candidate]
        source = _strict_prior_feature(
            bars, features, "global_ls_account", legacy_create_time_available)
        rolling = source.rolling(spec.quantile_window, min_periods=spec.min_periods)
        lower = rolling.quantile(spec.lower_quantile)
        upper = rolling.quantile(spec.upper_quantile)
        side[source.ge(upper).fillna(False).to_numpy()] = -1
        side[source.le(lower).fillna(False).to_numpy()] = 1
        bars["global_ls_account"] = source
        bars["lower_threshold"] = lower
        bars["upper_threshold"] = upper
    bars["side"] = side
    return bars


def signals(minutes: pd.DataFrame, features: pd.DataFrame, candidate: str, *,
            legacy_create_time_available: bool = False
            ) -> pd.DataFrame:
    """Return every frozen decision, including repeated signals while holding."""
    details = condition_details(
        minutes, features, candidate,
        legacy_create_time_available=legacy_create_time_available)
    return details[["bar_start", "decision_time", "open", "high", "low", "close",
                    "volume", "side"]].copy()


def _raw_trade(side: int, entry_time: pd.Timestamp, exit_time: pd.Timestamp,
               entry_price: float, exit_price: float, cost_bps: float) -> dict[str, object]:
    gross = float(side * np.log(exit_price / entry_price) * 10_000)
    return {"entry_time": entry_time, "exit_time": exit_time, "side": side,
            "entry_price": entry_price, "exit_price": exit_price,
            "gross_bps": gross, "cost_bps": cost_bps, "funding_bps": 0.0,
            "net_bps": gross - cost_bps,
            "hold_minutes": (exit_time - entry_time) / pd.Timedelta(minutes=1)}


def make_trades(minutes: pd.DataFrame, features: pd.DataFrame, candidate: str,
                cost_bps: float = 4.0, close_at_end: bool = True, *,
                legacy_create_time_available: bool = False) -> pd.DataFrame:
    """Run one frozen strategy as a single-position book before funding repricing."""
    decisions = signals(
        minutes, features, candidate,
        legacy_create_time_available=legacy_create_time_available)
    spec = SPECS[candidate]
    source = minutes.copy()
    source["open_time"] = pd.to_datetime(source.open_time, utc=True)
    source = source.sort_values("open_time", kind="stable").reset_index(drop=True)
    times = source.open_time.array.asi8
    opens = source.open.to_numpy(float)
    position = 0
    entry_bar = -1
    entry_time: pd.Timestamp | None = None
    entry_price = np.nan
    rows: list[dict[str, object]] = []
    for i, row in enumerate(decisions.itertuples(index=False)):
        minute_index = int(np.searchsorted(times, row.decision_time.value, side="left"))
        if minute_index >= len(source):
            continue
        execution_time = source.open_time.iloc[minute_index]
        execution_price = float(opens[minute_index])
        desired = int(row.side)
        if position and (i - entry_bar >= spec.max_hold or desired == -position):
            rows.append(_raw_trade(position, entry_time, execution_time,
                                   entry_price, execution_price, cost_bps))
            position = 0
        if not position and desired:
            position = desired
            entry_time, entry_price, entry_bar = execution_time, execution_price, i
    if position and close_at_end:
        exit_time = source.open_time.iloc[-1] + pd.Timedelta(minutes=1)
        rows.append(_raw_trade(position, entry_time, exit_time, entry_price,
                               float(source.close.iloc[-1]), cost_bps))
    return pd.DataFrame(rows, columns=TRADE_COLUMNS)


__all__ = ["E1", "F3", "F3_W30", "RULE_INPUT_COLUMNS", "RuleSpec", "SPECS", "aggregate_hourly",
           "condition_details", "make_trades", "signals"]
