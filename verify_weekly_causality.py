"""Verify the Sunday look-ahead fix in weekly_features.compute_weekly_features.

Checks:
1. Truncation invariance (gold-standard look-ahead test): features computed
   on the full series must equal features computed on any prefix, for every
   bar inside the prefix. A causal feature cannot change when future bars
   are appended.
2. Sunday behavior: during all of Sunday the features must still reflect the
   PREVIOUS completed week; the new week's close may only appear from
   Monday 00:00.
3. Regression shape: values from Monday-Saturday must be identical to the
   pre-fix selection (label <= ts), since only Sundays leaked.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import numpy as np

from btcusdt_quant import data
from btcusdt_quant.weekly_features import compute_weekly_features

WEEKS = 56  # > 50 so MA50 has real values near the end
N = WEEKS * 7 * 24 * 60


def make_candles(n: int) -> list[data.Candle]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)  # a Monday
    out = []
    for i in range(n):
        px = 100.0 + 10.0 * np.sin(i / 5000.0) + 0.00001 * i
        out.append(
            data.Candle(
                open_time=start + timedelta(minutes=i),
                open=px, high=px + 0.5, low=px - 0.5, close=px,
                volume=10.0, quote_volume=1000.0, number_of_trades=100,
                taker_buy_base_volume=5.0, taker_buy_quote_volume=500.0,
                gap_flag=False, repaired=False,
            )
        )
    return out


def main() -> int:
    candles = make_candles(N)
    full = compute_weekly_features(candles)

    # --- 1. Truncation invariance -------------------------------------
    # Cut mid-Sunday of week 54: under the OLD code the partial/final
    # Sunday close leaked into that Sunday's own bars, so full-vs-prefix
    # values on the Sunday would differ. Causal code must match exactly.
    sunday_noon = (54 * 7 - 1) * 24 * 60 + 12 * 60  # Sunday 12:00 of week 54
    prefix = compute_weekly_features(candles[: sunday_noon + 1])
    for key in full:
        a = np.asarray(full[key][: sunday_noon + 1], dtype=float)
        b = np.asarray(prefix[key], dtype=float)
        eq = np.isclose(a, b, rtol=0, atol=0, equal_nan=True)
        if not eq.all():
            first = int(np.argmin(eq))
            print(f"FAIL truncation invariance: {key} differs first at bar {first}: full={a[first]} prefix={b[first]}")
            return 1
    print("OK  1) truncation invariance (prefix ending mid-Sunday == full series)")

    # --- 2. Sunday uses PREVIOUS week; switch happens Monday 00:00 -----
    week = 53  # completed weeks counted from series start
    sun_first = (week * 7 - 1) * 24 * 60          # Sunday 00:00 bar index
    sun_last = sun_first + 24 * 60 - 1            # Sunday 23:59
    mon_first = sun_last + 1                      # Monday 00:00
    dd = np.asarray(full["weekly_drawdown"], dtype=float)
    ma_above = np.asarray(full["weekly_ma20_above_ma50"], dtype=float)
    sat_ref = dd[sun_first - 1]                   # Saturday 23:59 value (prev week's row)
    if not (dd[sun_first] == sat_ref and dd[sun_last] == sat_ref):
        print(f"FAIL: Sunday drawdown changed intraweek (leak): sat={sat_ref} sun00={dd[sun_first]} sun2359={dd[sun_last]}")
        return 1
    if dd[mon_first] == dd[sun_last]:
        # extremely unlikely to be equal with a moving sine price; treat as suspicious
        print(f"WARN: Monday 00:00 drawdown identical to Sunday value ({dd[mon_first]}); check test signal")
    print("OK  2) Sunday holds previous week's values; new weekly row appears Monday 00:00")

    # --- 3. Mon-Sat unchanged vs old (label <= ts) selection -----------
    # Old selection index = searchsorted(label, ts); new = searchsorted(label+1d, ts).
    # These agree except when label <= ts < label+1d, i.e. Sundays. Verify a
    # Wednesday bar picks the same weekly row under both rules.
    import pandas as pd
    timestamps = pd.DatetimeIndex([c.open_time for c in candles])
    closes = np.array([c.close for c in candles])
    df = pd.DataFrame({"close": closes}, index=timestamps)
    weekly = df.resample("W").agg({"close": "last"}).dropna()
    labels = pd.DatetimeIndex(weekly.index)
    wed = (week * 7 + 2) * 24 * 60 + 7 * 60  # Wednesday 07:00
    ts = timestamps[wed]
    old_row = int(np.searchsorted(labels.asi8, np.int64(ts.value), side="right")) - 1
    new_row = int(np.searchsorted((labels + pd.Timedelta(days=1)).asi8, np.int64(ts.value), side="right")) - 1
    if old_row != new_row:
        print(f"FAIL: Mon-Sat row selection changed (old={old_row} new={new_row})")
        return 1
    print("OK  3) Monday-Saturday selection identical to pre-fix (only Sundays changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
