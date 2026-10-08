"""Deterministic isolated-margin overlay for accepted paper-book trades."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class LeverageResult:
    trades: pd.DataFrame
    daily: pd.DataFrame
    skips: pd.DataFrame
    state: dict[str, object]
    position: dict[str, object] | None


PHASES = ("OPEN", "INTRAMINUTE_STOP", "CLOSE")


def exit_phases(trades: pd.DataFrame, minutes: pd.DataFrame) -> pd.Series:
    """Source exit execution phase: OPEN when it filled at the exit minute's open, INTRAMINUTE_STOP for a stop or
    trail touched inside the minute, else CLOSE (e.g. a replay/data end after the last stored minute)."""
    opens = minutes.assign(open_time=pd.to_datetime(minutes.open_time, utc=True)).set_index("open_time").open
    at = opens.reindex(pd.to_datetime(trades.exit_time, utc=True)).to_numpy(float)
    price = trades.exit_price.to_numpy(float)
    stop = trades.exit_reason.astype(str).str.upper().isin(["STOP", "TRAIL"]).to_numpy()
    phase = np.where(price == at, "OPEN", np.where(stop & np.isfinite(at), "INTRAMINUTE_STOP", "CLOSE"))
    return pd.Series(phase, index=trades.index)


def liquidation_price(entry_price: float, side: int, margin_usd: float,
                      notional_usd: float, maintenance_margin_rate: float,
                      funding_usd: float = 0.0) -> float:
    """Price where margin + price PnL + funding equals maintenance margin."""
    if side not in (-1, 1):
        raise ValueError("side must be -1 or 1")
    if min(entry_price, margin_usd, notional_usd) <= 0:
        raise ValueError("price, margin and notional must be positive")
    loss_fraction = ((margin_usd + funding_usd) / notional_usd
                     - maintenance_margin_rate)
    return float(entry_price * (1.0 - side * loss_fraction))


def _funding_cashflows(funding: pd.DataFrame, side: int, notional: float,
                       entry: pd.Timestamp, exit_: pd.Timestamp) -> dict[pd.Timestamp, float]:
    if funding.empty:
        return {}
    source = funding.copy()
    source["time"] = pd.to_datetime(source.time, utc=True)
    source = source.loc[source.time.between(entry, exit_, inclusive="both")]
    result: dict[pd.Timestamp, float] = {}
    for row in source.itertuples(index=False):
        stamp = pd.Timestamp(row.time)
        cashflow = float(-side * notional * row.rate)
        if entry < stamp < exit_ or cashflow < 0:  # PESS at both boundaries.
            result[stamp] = result.get(stamp, 0.0) + cashflow
    return result


def simulate_book(accepted: pd.DataFrame, minutes: pd.DataFrame, funding: pd.DataFrame,
                  source_book: str, start: object, end: object, *, leverage: float = 3.0,
                  budget_usd: float = 100.0, maintenance_margin_rate: float = .004,
                  liquidation_fee_rate: float = 0.0, cost_bps: float = 4.0,
                  minimum_balance_usd: float = 1.0) -> LeverageResult:
    """Apply xN isolated margin without creating or changing any signal. Each closed source row carries its
    exit_reason and exit_phase; an `_active` row is the still-open source position (no max hold of its own)."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("bounds must be timezone-aware")
    if leverage <= 0 or budget_usd <= 0 or not 0 <= maintenance_margin_rate < 1:
        raise ValueError("invalid leverage settings")
    book_name = f"{source_book}_x{leverage:g}"
    market = minutes[["open_time", "open", "high", "low", "close"]].copy()
    market["open_time"] = pd.to_datetime(market.open_time, utc=True)
    market = market.sort_values("open_time", kind="stable").drop_duplicates("open_time", keep="last")
    market_times = pd.DatetimeIndex(market.open_time).as_unit("ns").asi8
    balance = float(budget_usd)
    status = "RUNNING"
    closed_rows: list[dict[str, object]] = []
    skip_rows: list[dict[str, object]] = []
    observations: list[tuple[pd.Timestamp, float]] = [(start, balance)]
    position: dict[str, object] | None = None
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    peak_equity = balance
    liquidation_time: pd.Timestamp | None = None  # also needed when there are no trades yet

    def observe(stamp: pd.Timestamp, equity: float) -> None:
        nonlocal peak_equity, max_drawdown, max_drawdown_pct
        peak_equity = max(peak_equity, equity)
        max_drawdown = max(max_drawdown, peak_equity - equity)
        max_drawdown_pct = max(max_drawdown_pct, (peak_equity - equity) / peak_equity * 100.0
                               if peak_equity else 0.0)
        observations.append((stamp, equity))

    source = accepted.copy().sort_values("entry_time", kind="stable").reset_index(drop=True)
    for row in source.to_dict("records"):
        entry, scheduled_exit = pd.Timestamp(row["entry_time"]), pd.Timestamp(row["exit_time"])
        active = bool(row.get("_active", False))
        if status != "RUNNING" or balance < minimum_balance_usd:
            if status == "RUNNING":
                status = "STOPPED_BUDGET"
            skip_rows.append({"book": book_name, "source_book": source_book,
                              "entry_time": entry, "candidate": row.get("candidate"),
                              "reason": status})
            continue
        phase = row.get("exit_phase")
        if not active and (pd.isna(row.get("exit_reason")) or phase not in PHASES):
            raise ValueError("a closed source trade needs exit_reason and exit_phase OPEN|INTRAMINUTE_STOP|CLOSE")

        side = int(row["side"])
        entry_price = float(row["entry_price"])
        source_price = float(row["exit_price"])
        margin = balance
        notional = leverage * margin
        entry_fee = notional * cost_bps / 20_000.0
        cashflows = _funding_cashflows(funding, side, notional, entry, scheduled_exit)
        cumulative_funding = 0.0
        initial_liq = liquidation_price(entry_price, side, margin, notional,
                                        maintenance_margin_rate, cashflows.get(entry, 0.0))
        worst_pnl = -entry_fee
        current_liq = initial_liq
        left = int(market_times.searchsorted(entry.value, side="left"))
        right = int(market_times.searchsorted(scheduled_exit.value, side="left" if active else "right"))
        held = market.iloc[left:right]
        outcome = None                      # "LIQUIDATED" or "EXIT" once decided inside the held minutes
        for k, minute in enumerate(held.itertuples(index=False)):
            # r2_52a_exit_freeze.json paper_rollout.leverage_execution_order
            stamp = pd.Timestamp(minute.open_time)
            cumulative_funding += cashflows.get(stamp, 0.0)
            current_liq = liquidation_price(entry_price, side, margin, notional,
                                            maintenance_margin_rate, cumulative_funding)
            crossed = (lambda price: price <= current_liq) if side > 0 else (lambda price: price >= current_liq)
            exit_minute = not active and stamp == scheduled_exit
            opened = float(minute.open)
            adverse = float(minute.low if side > 0 else minute.high)
            worst_pnl = min(worst_pnl, notional * side * (adverse / entry_price - 1.0)
                            + cumulative_funding - entry_fee)
            if k and crossed(opened):
                outcome = "LIQUIDATED"
            elif exit_minute and phase == "OPEN":
                outcome = "EXIT"
            elif exit_minute and phase == "INTRAMINUTE_STOP":       # first adverse barrier from the open; tie -> LIQ
                first = crossed(adverse) and abs(opened - current_liq) <= abs(opened - source_price)
                outcome = "LIQUIDATED" if first else "EXIT"
            elif crossed(adverse):
                outcome = "LIQUIDATED"
            elif exit_minute:               # CLOSE executes after the intraminute liquidation test
                outcome = "EXIT"
            if outcome == "LIQUIDATED":
                liquidation_time = stamp
                balance = 0.0
                status = "LIQUIDATED"
                observe(stamp, 0.0)
                closed_rows.append({
                    "book": book_name, "source_book": source_book,
                    "candidate": row.get("candidate"), "entry_time": entry,
                    "exit_time": stamp, "side": side, "entry_price": entry_price,
                    "exit_price": current_liq, "notional_usd": notional,
                    "margin_usd": margin, "initial_liquidation_price": initial_liq,
                    "liquidation_price": current_liq,
                    "max_adverse_pnl_usd": worst_pnl, "liquidated": 1,
                    "gross_pnl_usd": -margin - cumulative_funding + entry_fee,
                    "cost_usd": entry_fee + notional * liquidation_fee_rate,
                    "funding_usd": cumulative_funding, "pnl_usd": -margin,
                    "balance_before_usd": margin, "balance_after_usd": 0.0,
                    "hold_minutes": float((stamp - entry) / pd.Timedelta(minutes=1)),
                    "exit_reason": "LIQUIDATED"})
                break
            if outcome == "EXIT":
                break
            observe(stamp, max(0.0, margin + notional * side * (adverse / entry_price - 1.0)
                               + cumulative_funding - entry_fee))
            observe(stamp, max(0.0, margin + notional * side * (float(minute.close) / entry_price - 1.0)
                               + cumulative_funding - entry_fee))

        if outcome == "LIQUIDATED":
            continue
        cumulative_funding = sum(cashflows.values())
        current_liq = liquidation_price(entry_price, side, margin, notional,
                                        maintenance_margin_rate, cumulative_funding)
        if active:
            latest = held.iloc[-1] if len(held) else None
            mark = entry_price if latest is None else float(latest.close)
            unrealized = (notional * side * (mark / entry_price - 1.0)
                          + cumulative_funding - entry_fee)
            distance = abs(mark - current_liq) / mark * 100.0
            position = {"book": book_name, "source_book": source_book, "side": side,
                        "candidate": row.get("candidate"), "entry_time": entry,
                        "entry_price": entry_price, "mark_price": mark,
                        "notional_usd": notional,
                        "margin_usd": margin, "liquidation_price": current_liq,
                        "liquidation_distance_pct": distance,
                        "unrealized_pnl_usd": unrealized, "balance_usd": balance,
                        "updated_at": end}
            break

        gross = notional * side * (source_price / entry_price - 1.0)
        cost = notional * cost_bps / 10_000.0
        pnl = gross + cumulative_funding - cost
        before = balance
        balance += pnl
        observe(scheduled_exit, max(0.0, balance))
        closed_rows.append({
            "book": book_name, "source_book": source_book,
            "candidate": row.get("candidate"), "entry_time": entry,
            "exit_time": scheduled_exit, "side": side, "entry_price": entry_price,
            "exit_price": source_price, "notional_usd": notional, "margin_usd": margin,
            "initial_liquidation_price": initial_liq, "liquidation_price": current_liq,
            "max_adverse_pnl_usd": worst_pnl, "liquidated": 0,
            "gross_pnl_usd": gross, "cost_usd": cost,
            "funding_usd": cumulative_funding, "pnl_usd": pnl,
            "balance_before_usd": before, "balance_after_usd": balance,
            "hold_minutes": float((scheduled_exit - entry) / pd.Timedelta(minutes=1)),
            "exit_reason": row["exit_reason"]})
        if balance < minimum_balance_usd:
            status = "STOPPED_BUDGET"

    if end > start:
        observations.append((end - pd.Timedelta(nanoseconds=1), max(0.0, balance)))
    equity = pd.DataFrame(observations, columns=["time", "equity"]).sort_values(
        "time", kind="stable")
    equity["date"] = equity.time.dt.strftime("%Y-%m-%d")
    equity["peak"] = equity.equity.cummax()
    equity["drawdown"] = equity.peak - equity.equity
    dates = pd.date_range(start.floor("D"), (end - pd.Timedelta(nanoseconds=1)).floor("D"),
                          freq="D", tz="UTC")
    daily_rows = []
    previous = budget_usd
    for day in dates:
        part = equity.loc[equity.date.eq(day.strftime("%Y-%m-%d"))]
        day_balance = previous if part.empty else float(part.equity.iloc[-1])
        drawdown = 0.0 if part.empty else float(part.drawdown.max())
        peak = budget_usd if part.empty else float(part.peak.max())
        daily_rows.append({"book": book_name, "date": day.strftime("%Y-%m-%d"),
                           "balance_usd": day_balance,
                           "day_pnl_usd": day_balance - previous,
                           "max_drawdown_usd": drawdown,
                           "max_drawdown_pct": 0.0 if peak <= 0 else drawdown / peak * 100.0})
        previous = day_balance
    state = {"book": book_name, "source_book": source_book, "status": status,
             "balance_usd": balance, "cumulative_pnl_usd": balance - budget_usd,
             "cumulative_return_pct": (balance / budget_usd - 1.0) * 100.0,
             "max_drawdown_usd": max_drawdown,
             "max_drawdown_pct": max_drawdown_pct,
             "liquidated_at": liquidation_time, "updated_at": end}
    return LeverageResult(pd.DataFrame(closed_rows), pd.DataFrame(daily_rows),
                          pd.DataFrame(skip_rows), state, position)


__all__ = ["LeverageResult", "PHASES", "exit_phases", "liquidation_price", "simulate_book"]
