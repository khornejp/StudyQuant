"""Single-position FIRST book and frozen PESS/OPT funding ledger."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

BOUNDARIES = frozenset({"PESS", "OPT"})


def max_concurrent(trades: pd.DataFrame) -> int:
    if trades.empty:
        return 0
    events = [(pd.Timestamp(value), 1) for value in trades.entry_time]
    events += [(pd.Timestamp(value), -1) for value in trades.exit_time]
    active = peak = 0
    for _, change in sorted(events, key=lambda item: (item[0], item[1])):
        active += change
        peak = max(peak, active)
    return peak


def first_book(signals: pd.DataFrame, priority: list[str] | tuple[str, ...]
               ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Accept first available signal; drop held and same-minute conflicts."""
    missing = set(signals.candidate) - set(priority)
    if missing:
        raise ValueError(f"priority missing: {sorted(missing)}")
    source = signals.copy().reset_index(drop=True)
    for column in ("entry_time", "exit_time"):
        source[column] = pd.to_datetime(source[column], utc=True).astype("datetime64[ns, UTC]")
    source["source_signal_id"] = np.arange(len(source), dtype=np.int64)
    rank = {candidate: number for number, candidate in enumerate(priority)}
    accepted: list[dict[str, object]] = []
    dropped: list[dict[str, object]] = []
    active: int | None = None
    for entry_time, group in source.groupby("entry_time", sort=True):
        if active is not None and accepted[active]["exit_time"] <= entry_time:
            active = None
        rows = sorted(group.to_dict("records"),
                      key=lambda row: (rank[row["candidate"]], row["source_signal_id"]))
        if active is None:
            chosen = rows[0]
            accepted.append({**chosen, "original_entry_price": chosen["entry_price"],
                             "original_exit_time": chosen["exit_time"],
                             "original_exit_price": chosen["exit_price"],
                             "switched_out": False})
            active = len(accepted) - 1
            for row in rows[1:]:
                dropped.append({**row, "reason": "simultaneous",
                                "active_candidate": chosen["candidate"]})
        else:
            current = accepted[active]
            for row in rows:
                dropped.append({**row, "reason": "holding",
                                "active_candidate": current["candidate"]})
    accepted_frame = pd.DataFrame(accepted)
    dropped_frame = pd.DataFrame(dropped)
    if accepted_frame.empty:
        accepted_frame = pd.DataFrame(columns=list(source.columns) + [
            "original_entry_price", "original_exit_time", "original_exit_price", "switched_out"])
    if dropped_frame.empty:
        dropped_frame = pd.DataFrame(columns=list(source.columns) + ["reason", "active_candidate"])
    if len(accepted_frame):
        accepted_frame["hold_minutes"] = ((accepted_frame.exit_time - accepted_frame.entry_time) /
                                           pd.Timedelta(minutes=1)).astype(float)
    if max_concurrent(accepted_frame) > 1:
        raise AssertionError("single-position invariant")
    return accepted_frame, dropped_frame


def _funding_arrays(funding: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    times = funding.attrs.get("_time_ns")
    rates = funding.attrs.get("_rates")
    if times is None or rates is None:
        times = pd.DatetimeIndex(pd.to_datetime(funding.time, utc=True)).as_unit("ns").asi8
        rates = pd.to_numeric(funding.rate, errors="raise").to_numpy(float)
    return np.asarray(times), np.asarray(rates, float)


def reprice(trades: pd.DataFrame, funding: pd.DataFrame, boundary: str,
            cost_bps: float = 4.0, *, cost_first: bool = False) -> pd.DataFrame:
    """Apply exact research funding boundary and round-trip cost rules."""
    if boundary not in BOUNDARIES:
        raise ValueError(f"unknown boundary: {boundary}")
    out = trades.copy()
    out["entry_time"] = pd.to_datetime(out.entry_time, utc=True).astype("datetime64[ns, UTC]")
    out["exit_time"] = pd.to_datetime(out.exit_time, utc=True).astype("datetime64[ns, UTC]")
    if "source_gross_bps" not in out:
        out["source_gross_bps"] = (out.gross_bps if "gross_bps" in out else
                                    out.side * np.log(out.exit_price / out.entry_price) * 1e4)
    out["gross_bps"] = out.side.to_numpy(float) * np.log(
        out.exit_price.to_numpy(float) / out.entry_price.to_numpy(float)) * 1e4
    times, rates = _funding_arrays(funding)
    sides = out.side.to_numpy(float)
    entries = pd.DatetimeIndex(out.entry_time).as_unit("ns").asi8
    exits = pd.DatetimeIndex(out.exit_time).as_unit("ns").asi8
    left = np.searchsorted(times, entries, side="right")
    right = np.searchsorted(times, exits, side="left")
    prefix = np.r_[0.0, np.cumsum(rates)]
    internal = -sides * (prefix[right] - prefix[left]) * 1e4
    count = right - left
    edge_cashflow = np.zeros(len(out), float)
    for values in (entries, exits):
        positions = np.searchsorted(times, values, side="left")
        valid = positions < len(times)
        valid[valid] &= times[positions[valid]] == values[valid]
        edge = np.zeros(len(out), float)
        edge[valid] = -sides[valid] * rates[positions[valid]] * 1e4
        include = valid & ((edge < 0) if boundary == "PESS" else (edge > 0))
        edge_cashflow[include] += edge[include]
        count[include] += 1
    out["funding_bps"] = internal + edge_cashflow
    out["funding_event_count"] = count
    out["cost_bps"] = float(cost_bps)
    out["net_bps"] = (out.gross_bps - cost_bps + out.funding_bps if cost_first else
                      out.gross_bps + out.funding_bps - cost_bps)
    out["hold_minutes"] = (out.exit_time - out.entry_time) / pd.Timedelta(minutes=1)
    return out


def minute_components(trades: pd.DataFrame, closes: pd.Series, funding: pd.DataFrame,
                      boundary: str, cost_bps: float = 4.0) -> pd.DataFrame:
    """Return research-identical minute MTM gross, cost, funding and net bps."""
    index = pd.DatetimeIndex(pd.to_datetime(closes.index, utc=True)).as_unit("ns")
    close = pd.Series(closes.to_numpy(float), index=index)
    result = pd.DataFrame(0.0, index=index,
                          columns=["gross_bps", "cost_bps", "funding_bps", "net_bps"])
    log_close = np.log(close)
    funding_times, funding_rates = _funding_arrays(funding)
    for trade in trades.itertuples(index=False):
        entry, exit_ = pd.Timestamp(trade.entry_time), pd.Timestamp(trade.exit_time)
        left = index.searchsorted(entry, side="left")
        right = index.searchsorted(exit_, side="right")
        held = index[left:right]
        if not len(held):
            continue
        level = np.r_[log_close.loc[held[:-1]].to_numpy(), math.log(trade.exit_price)]
        previous = np.r_[math.log(trade.entry_price), level[:-1]]
        result.loc[held, "gross_bps"] += (level - previous) * 1e4 * trade.side
        result.loc[held[0], "cost_bps"] += cost_bps / 2
        result.loc[held[-1], "cost_bps"] += cost_bps / 2
        fleft = np.searchsorted(funding_times, entry.value, side="left")
        fright = np.searchsorted(funding_times, exit_.value, side="right")
        for event_time, rate in zip(funding_times[fleft:fright], funding_rates[fleft:fright]):
            value = float(-trade.side * rate * 1e4)
            inside = entry.value < event_time < exit_.value
            at_entry, at_exit = event_time == entry.value, event_time == exit_.value
            included = inside or ((at_entry or at_exit) and
                ((boundary == "PESS" and value < 0) or (boundary == "OPT" and value > 0)))
            if included:
                location = index.get_indexer([pd.Timestamp(event_time, tz="UTC")])[0]
                if location >= 0:
                    result.iloc[location, result.columns.get_loc("funding_bps")] += value
    result["net_bps"] = result.gross_bps - result.cost_bps + result.funding_bps
    return result


__all__ = ["BOUNDARIES", "first_book", "max_concurrent", "minute_components", "reprice"]
