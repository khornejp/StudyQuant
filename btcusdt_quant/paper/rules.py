"""Frozen F3, F3-w30, F3 5-minute and E1 paper-trading rules.

Thresholds use complete one-hour bars. Execution is the first available
one-minute open at or after the decision timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

F3 = "F3|1h|10/24|signal|LS"
F3_5M = "F3|5m|10/24|signal|LS"
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
    F3_5M: RuleSpec(F3_5M, 2_160, 720, .10, .90, 24),
    F3_W30: RuleSpec(F3_W30, 720, 720, .20, .80, 12),
    E1: RuleSpec(E1, None, None, None, None, 20, True),
}


def _f3_5m_details(minutes: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    """R2-37 V5: new 5m LS value against thresholds frozen at prior hour."""
    columns = ["bar_start", "decision_time", "open", "high", "low", "close", "volume",
               "global_ls_account", "lower_threshold", "upper_threshold", "volume_zscore",
               "prior_high_20", "side"]
    if minutes.empty or features.empty:
        return pd.DataFrame(columns=columns)
    bars = aggregate_hourly(minutes)
    if bars.empty:
        return pd.DataFrame(columns=columns)
    hourly_ls = _strict_prior_feature(bars, features, "global_ls_account")
    rolling = hourly_ls.rolling(2_160, min_periods=720)
    levels = pd.DataFrame({"decision_time": bars.decision_time,
                           "lower_threshold": rolling.quantile(.10),
                           "upper_threshold": rolling.quantile(.90)})

    source_columns = ["open_time", "global_ls_account"] + (
        ["source"] if "source" in features else [])
    events = features[source_columns].copy()
    events["open_time"] = pd.to_datetime(events.open_time, utc=True).astype(
        "datetime64[ns, UTC]")
    events = events.loc[events.open_time.dt.minute.mod(5).eq(0)].copy()
    if events.empty:
        return pd.DataFrame(columns=columns)
    archive = (events.source.ne("rest") if "source" in events else
               pd.Series(True, index=events.index))
    events["decision_time"] = events.open_time
    events.loc[archive, "decision_time"] += pd.Timedelta(minutes=5)
    events = events.sort_values("decision_time", kind="stable").drop_duplicates(
        "decision_time", keep="last")
    events = pd.merge_asof(events, levels.sort_values("decision_time"),
                           on="decision_time", direction="backward")

    market = minutes[["open_time", "open", "high", "low", "close", "volume"]].copy()
    market["open_time"] = pd.to_datetime(market.open_time, utc=True).astype(
        "datetime64[ns, UTC]")
    market["decision_time"] = market.open_time + pd.Timedelta(minutes=1)
    events = pd.merge_asof(events.sort_values("decision_time"),
                           market.sort_values("decision_time"), on="decision_time",
                           direction="backward")
    events = events.loc[events.decision_time.le(
        market.open_time.max() + pd.Timedelta(minutes=1))].copy()
    events["bar_start"] = events.decision_time - pd.Timedelta(minutes=5)
    events["volume_zscore"] = np.nan
    events["prior_high_20"] = np.nan
    side = np.zeros(len(events), np.int8)
    side[events.global_ls_account.ge(events.upper_threshold).fillna(False).to_numpy()] = -1
    side[events.global_ls_account.le(events.lower_threshold).fillna(False).to_numpy()] = 1
    events["side"] = side
    return events[columns].reset_index(drop=True)


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
    if candidate == F3_5M:
        if legacy_create_time_available:
            raise ValueError("F3 5m does not support legacy create-time availability")
        return _f3_5m_details(minutes, features)
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
                legacy_create_time_available: bool = False,
                decision_start: object | None = None) -> pd.DataFrame:
    """Run one frozen strategy as a single-position book before funding repricing."""
    decisions = signals(
        minutes, features, candidate,
        legacy_create_time_available=legacy_create_time_available)
    if decision_start is not None:
        decisions = decisions.loc[decisions.decision_time.ge(pd.Timestamp(decision_start))]
    spec = SPECS[candidate]
    source = minutes.copy()
    source["open_time"] = pd.to_datetime(source.open_time, utc=True)
    source = source.sort_values("open_time", kind="stable").reset_index(drop=True)
    times = source.open_time.array.asi8
    opens = source.open.to_numpy(float)
    if candidate == F3_5M:
        return _make_time_trades(decisions, source, spec, cost_bps, close_at_end)
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


def make_first_trades(minutes: pd.DataFrame, features: pd.DataFrame,
                      candidates: tuple[str, ...], *,
                      decision_start: object | None = None,
                      execution_delay_minutes: int = 0,
                      cost_bps: float = 4.0) -> pd.DataFrame:
    """Run a priority FIRST book directly from decisions, including held-signal drops."""
    decision_frames = [signals(minutes, features, candidate) for candidate in candidates]
    decisions = decision_frames[0][["decision_time"]].copy()
    for candidate, frame in zip(candidates, decision_frames):
        if not frame.decision_time.equals(decisions.decision_time):
            raise ValueError("FIRST candidates must share decision times")
        decisions[candidate] = frame.side.to_numpy(np.int8)
    if decision_start is not None:
        decisions = decisions.loc[decisions.decision_time.ge(pd.Timestamp(decision_start))]

    source = minutes.copy()
    source["open_time"] = pd.to_datetime(source.open_time, utc=True)
    source = source.sort_values("open_time", kind="stable").reset_index(drop=True)
    times = source.open_time.array.asi8
    opens = source.open.to_numpy(float)
    data_end = source.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    delay = pd.Timedelta(minutes=execution_delay_minutes)
    active: str | None = None
    side = 0
    entry_time: pd.Timestamp | None = None
    entry_price = np.nan
    expiry: pd.Timestamp | None = None
    rows: list[dict[str, object]] = []

    def close(time: pd.Timestamp, price: float) -> None:
        nonlocal active, side, entry_time, entry_price, expiry
        rows.append({**_raw_trade(side, entry_time, time, entry_price, price, cost_bps),
                     "candidate": active})
        active, side, entry_time, expiry = None, 0, None, None
        entry_price = np.nan

    for values in decisions.itertuples(index=False, name=None):
        decision_time, *side_values = values
        current = dict(zip(candidates, side_values))
        execution_target = pd.Timestamp(decision_time) + delay
        if execution_target >= data_end:
            break
        location = int(np.searchsorted(times, execution_target.value, side="left"))
        if location >= len(source):
            continue
        execution_time = source.open_time.iloc[location]
        execution_price = float(opens[location])
        if active is not None and expiry is not None and expiry <= execution_time:
            expiry_location = int(np.searchsorted(times, expiry.value, side="left"))
            close(source.open_time.iloc[expiry_location], float(opens[expiry_location]))
        if active is not None and int(current[active]) == -side:
            close(execution_time, execution_price)
        if active is None:
            chosen = next((candidate for candidate in candidates
                           if int(current[candidate]) != 0), None)
            if chosen is not None:
                active, side = chosen, int(current[chosen])
                entry_time, entry_price = execution_time, execution_price
                expiry = execution_time + pd.Timedelta(hours=SPECS[chosen].max_hold)
    if active is not None:
        close(data_end, float(source.close.iloc[-1]))
    return pd.DataFrame(rows, columns=[*TRADE_COLUMNS, "candidate"])


def _make_time_trades(decisions: pd.DataFrame, source: pd.DataFrame, spec: RuleSpec,
                      cost_bps: float, close_at_end: bool) -> pd.DataFrame:
    """Absolute-time hold used by R2-37 V5; held signals remain ignored."""
    if source.empty:
        return pd.DataFrame(columns=TRADE_COLUMNS)
    times = source.open_time.array.asi8
    opens = source.open.to_numpy(float)
    end_time = source.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    position = 0
    entry_time: pd.Timestamp | None = None
    entry_price = np.nan
    expiry: pd.Timestamp | None = None
    rows: list[dict[str, object]] = []

    def close(time: pd.Timestamp, price: float) -> None:
        nonlocal position, entry_time, entry_price, expiry
        rows.append(_raw_trade(position, entry_time, time, entry_price, price, cost_bps))
        position, entry_time, entry_price, expiry = 0, None, np.nan, None

    for row in decisions.loc[decisions.side.ne(0)].itertuples(index=False):
        decision_time, desired = pd.Timestamp(row.decision_time), int(row.side)
        if decision_time >= end_time:
            break
        if position and expiry is not None and expiry <= decision_time:
            location = int(np.searchsorted(times, expiry.value, side="left"))
            if location < len(source):
                close(source.open_time.iloc[location], float(opens[location]))
        location = int(np.searchsorted(times, decision_time.value, side="left"))
        if location >= len(source):
            continue
        execution_time = source.open_time.iloc[location]
        execution_price = float(opens[location])
        if position and desired == -position:
            close(execution_time, execution_price)
        if not position:
            position, entry_time, entry_price = desired, execution_time, execution_price
            expiry = execution_time + pd.Timedelta(hours=spec.max_hold)
    if position and expiry is not None and expiry < end_time:
        location = int(np.searchsorted(times, expiry.value, side="left"))
        if location < len(source):
            close(source.open_time.iloc[location], float(opens[location]))
    if position and close_at_end:
        close(end_time, float(source.close.iloc[-1]))
    return pd.DataFrame(rows, columns=TRADE_COLUMNS)


__all__ = ["E1", "F3", "F3_5M", "F3_W30", "RULE_INPUT_COLUMNS", "RuleSpec", "SPECS", "aggregate_hourly",
           "condition_details", "make_first_trades", "make_trades", "signals"]
