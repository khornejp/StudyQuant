"""Randomized differential checks for the published per-side label contract.

The oracle in this file deliberately does not call any production triple-barrier
function.  Set ``STUDYQUANT_PROPERTY_CASES`` to run a larger soak (the normal
suite uses 2,048 cases); set ``STUDYQUANT_PROPERTY_REPORT=1`` to print coverage.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import random

from btcusdt_quant import data, dataset


FIXED_SEEDS = (0x14_0001, 0x14_0002, 0x14_0003, 0x14_0004, 0x14_0005, 0x14_0006, 0x14_0007, 0x14_0008)
DEFAULT_CASES = 2_048
STRUCTURES = (
    "exact_touch",
    "dual_touch",
    "flat",
    "single_tick",
    "no_touch_run",
    "gap_up",
    "gap_down",
    "random_walk",
)


def _candle(offset: int, open_: float, high: float, low: float, close: float) -> data.Candle:
    return data.Candle(
        open_time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=offset),
        open=open_, high=high, low=low, close=close, volume=1.0,
        quote_volume=max(close, 1e-12), number_of_trades=1,
        taker_buy_base_volume=0.5, taker_buy_quote_volume=max(close / 2, 1e-12),
    )


def _oracle_side(candles: list[data.Candle], horizon: int, tp: float, sl: float, side: str) -> tuple[int, str]:
    entry = candles[0].close
    tp_level = entry * (1.0 + tp) if side == "long" else entry * (1.0 - tp)
    sl_level = entry * (1.0 - sl) if side == "long" else entry * (1.0 + sl)
    for candle in candles[1:horizon + 1]:
        tp_hit = candle.high >= tp_level if side == "long" else candle.low <= tp_level
        sl_hit = candle.low <= sl_level if side == "long" else candle.high >= sl_level
        if tp_hit and sl_hit:
            # Published contract: candle direction decides.  A flat candle has
            # no favorable direction, so the conservative, explicit tie rule
            # is SL-first for both sides.
            favorable = candle.close > candle.open if side == "long" else candle.close < candle.open
            return (1, f"{side}_tp_first") if favorable else (0, f"{side}_sl_first")
        if tp_hit:
            return 1, f"{side}_tp_first"
        if sl_hit:
            return 0, f"{side}_sl_first"
    return 0, f"{side}_timeout"


def _oracle_all(candles: list[data.Candle], horizon: int, threshold: float, long_tp: float, long_sl: float, short_tp: float, short_sl: float) -> dict[str, tuple[int, str]]:
    long, long_reason = _oracle_side(candles, horizon, long_tp, long_sl, "long")
    short, short_reason = _oracle_side(candles, horizon, short_tp, short_sl, "short")
    future_return = (candles[horizon].close - candles[0].close) / candles[0].close
    if long_reason == "long_timeout":
        label, label_reason = (1 if future_return > threshold else 0), "timeout_no_tp"
    else:
        label, label_reason = long, long_reason.removeprefix("long_")
    if short_reason == "short_timeout":
        short_profit, short_profit_reason = (1 if -future_return > threshold else 0), "short_timeout_return"
    else:
        short_profit, short_profit_reason = short, short_reason
    return {
        "long_success": (long, long_reason),
        "short_success": (short, short_reason),
        "short_profitability": (short_profit, short_profit_reason),
        "label": (label, label_reason),
    }


def _geometry(rng: random.Random) -> tuple[float, float, float, float, float]:
    base = 10.0 ** rng.uniform(-2, 5)
    # Near-equal and widely separated barriers both occur naturally here.
    values = [10.0 ** rng.uniform(-6, -0.25) for _ in range(4)]
    if rng.random() < 0.25:
        values[1] = values[0] * (1.0 + rng.uniform(-1e-10, 1e-10))
    if rng.random() < 0.25:
        values[3] = values[2] * (1.0 + rng.uniform(-1e-10, 1e-10))
    return base, *values


def _case(seed: int, structure: str) -> tuple[list[data.Candle], int, float, float, float, float, float]:
    rng = random.Random(seed)
    base, long_tp, long_sl, short_tp, short_sl = _geometry(rng)
    horizon = rng.randint(1, 240)
    threshold = 10.0 ** rng.uniform(-6, -1)
    candles = [_candle(0, base, base, base, base)]
    price = base
    for i in range(1, horizon + 1):
        open_ = price
        close = max(base * 1e-8, open_ * (1.0 + rng.uniform(-0.012, 0.012)))
        high, low = max(open_, close) * (1.0 + rng.random() * 0.004), min(open_, close) * (1.0 - rng.random() * 0.004)
        candles.append(_candle(i, open_, high, low, close))
        price = close

    # Put one deliberately constructed bar at the first future position, so a
    # failure reduces to entry + one bar regardless of the random horizon.
    entry = candles[0].close
    if structure == "exact_touch":
        candles[1] = _candle(1, entry, entry * (1.0 + long_tp), entry, entry)
    elif structure == "dual_touch":
        candles[1] = _candle(1, entry * 0.999, entry * (1.0 + max(long_tp, short_sl)), entry * (1.0 - max(long_sl, short_tp)), entry * 1.001)
    elif structure == "flat":
        # Flat dual-touch deliberately verifies the explicit SL-first policy.
        candles[1] = _candle(1, entry, entry * (1.0 + max(long_tp, short_sl)), entry * (1.0 - max(long_sl, short_tp)), entry)
    elif structure == "single_tick":
        tick = max(entry * 1e-12, 1e-12)
        candles[1] = _candle(1, entry, entry + tick, entry - tick, entry + tick)
    elif structure == "no_touch_run":
        # Make all barriers unreachable and retain a long, genuinely no-touch scan.
        long_tp = long_sl = short_tp = short_sl = 0.49
        for i in range(1, horizon + 1):
            candles[i] = _candle(i, entry, entry * 1.000001, entry * 0.999999, entry)
    elif structure == "gap_up":
        candles[1] = _candle(1, entry * 1.2, entry * 1.21, entry * 1.19, entry * 1.2)
    elif structure == "gap_down":
        candles[1] = _candle(1, entry * 0.8, entry * 0.81, entry * 0.79, entry * 0.8)
    return candles, horizon, threshold, long_tp, long_sl, short_tp, short_sl


def test_randomized_per_side_labels_match_independent_contract() -> None:
    cases = int(os.environ.get("STUDYQUANT_PROPERTY_CASES", DEFAULT_CASES))
    assert cases >= len(STRUCTURES)
    coverage = {name: 0 for name in STRUCTURES}
    compared_rows = 0
    for case_number in range(cases):
        seed = FIXED_SEEDS[case_number % len(FIXED_SEEDS)] + case_number * 1_000_003
        structure = STRUCTURES[case_number % len(STRUCTURES)]
        coverage[structure] += 1
        candles, horizon, threshold, long_tp, long_sl, short_tp, short_sl = _case(seed, structure)
        row = dataset.FeatureRow(0, candles[0].open_time, {}, 0, False, False)
        actual_rows = dataset.attach_labels([row], candles, horizon, threshold, long_tp_pct=long_tp, long_sl_pct=long_sl, short_tp_pct=short_tp, short_sl_pct=short_sl)
        assert len(actual_rows) == 1
        actual, expected = actual_rows[0], _oracle_all(candles, horizon, threshold, long_tp, long_sl, short_tp, short_sl)
        for target, (want_label, want_reason) in expected.items():
            got_label = actual.label if target == "label" else actual.targets[target]
            got_reason = actual.label_reason if target == "label" else actual.target_reasons[target]
            assert (got_label, got_reason) == (want_label, want_reason), (
                f"seed={seed} case={case_number} structure={structure} horizon={horizon} target={target}; "
                f"pipeline={(got_label, got_reason)} independent={(want_label, want_reason)}; "
                f"minimal_series={[ (c.open, c.high, c.low, c.close) for c in candles[:2] ]}"
            )
        assert actual.targets["profitability"] == actual.label
        assert actual.target_reasons["profitability"] == actual.label_reason
        compared_rows += 1
    assert all(coverage.values()), f"missing adversarial structures: {coverage}"
    if os.environ.get("STUDYQUANT_PROPERTY_REPORT") == "1":
        print(f"randomized label contract: cases={cases:,} rows={compared_rows:,} coverage={coverage}")
