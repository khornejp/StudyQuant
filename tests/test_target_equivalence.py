import math
from pathlib import Path

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pyarrow as pa
import pyarrow.parquet as pq

import btcusdt_quant.target_equivalence as target_equivalence
from btcusdt_quant.target_equivalence import (
    BOUNCE_MIN_PAIRS,
    Trades,
    bbo_reference,
    bounce_estimate,
    ceil_tick,
    completed_parquet,
    epoch_ms,
    first_fill,
    floor_tick,
    pair_events,
    process_origins,
    trade_endpoint_reference,
    trade_origin_reference,
    _required_hours,
)


def hand_trades(pairs=BOUNCE_MIN_PAIRS):
    count = pairs + 1
    times = np.arange(count, dtype=np.int64) * 50 + 10_000
    signs = np.where(np.arange(count) % 2, 1, -1).astype(np.int8)
    prices = np.where(signs == 1, 100.01, 99.99)
    pair_times, pair_values = pair_events(times, prices, signs)
    return Trades(times, np.arange(count), prices, signs, pair_times, pair_values)


def test_bounce_estimator_on_hand_built_opposite_pairs():
    trades = hand_trades()
    query = int(trades.times[-1] + 1)
    spread, count = bounce_estimate(trades.pair_times, trades.pair_values, query)
    reference, reference_count = trade_origin_reference(trades, query, corrected=True)
    assert count == BOUNCE_MIN_PAIRS == reference_count
    assert 1.999 < spread < 2.001
    assert abs(reference - 100.0) < 1e-8


def test_tick_rounding_is_outward_and_stable_on_tick():
    assert ceil_tick(100.1) == 100.1
    assert floor_tick(100.1) == 100.1
    assert ceil_tick(100.1000001) == 100.2
    assert floor_tick(100.1999999) == 100.1


def test_datetime_grid_converts_to_epoch_milliseconds():
    grid = pd.date_range("2023-05-16 11:49", periods=2, freq="min", tz="UTC")
    assert epoch_ms(grid).tolist() == [1684237740000, 1684237800000]


def test_fill_rule_handles_both_sides_and_window_edges():
    times = np.array([1_001, 2_000, 3_000, 4_000], dtype=np.int64)
    prices = np.array([102.0, 102.1, 99.0, 98.9])
    signs = np.array([1, 1, -1, -1], dtype=np.int8)
    assert first_fill(times, prices, signs, 1_000, 102.0, "short") == 2_000
    assert first_fill(times, prices, signs, 1_000, 99.0, "long") == 4_000


def test_bbo_origin_excludes_update_exactly_at_t():
    times = np.array([999, 1_000], dtype=np.int64)
    mids = np.array([99.0, 100.0])
    assert bbo_reference(times, mids, 1_000, inclusive=False) == 99.0
    assert bbo_reference(times, mids, 1_000, inclusive=True) == 100.0


def test_midnight_context_keeps_pairs_fill_and_endpoint():
    origin = 86_400_000
    pair_times = origin - 1_000 + np.arange(21, dtype=np.int64) * 40
    pair_signs = np.where(np.arange(21) % 2, 1, -1).astype(np.int8)
    pair_prices = np.where(pair_signs == 1, 100.01, 99.99)
    post_times = origin + 2_000 + np.arange(21, dtype=np.int64) * 100
    post_signs = np.where(np.arange(21) % 2, 1, -1).astype(np.int8)
    post_prices = np.where(post_signs == 1, 100.01, 99.99)
    times = np.r_[pair_times, origin + 1_000, post_times, origin + 61_000]
    prices = np.r_[pair_prices, 100.2, post_prices, 100.0]
    signs = np.r_[pair_signs, 1, post_signs, -1].astype(np.int8)
    event_times, event_values = pair_events(times, prices, signs)
    trades = Trades(times, np.arange(len(times)), prices, signs, event_times, event_values)
    bbo_times = np.array([origin - 1, origin + 61_000], dtype=np.int64)
    origins, outcomes = process_origins(
        np.array([origin], dtype=np.int64), bbo_times, np.array([100.0, 100.0]), trades)
    assert origins.loc[0, "bounce_pair_count"] >= BOUNCE_MIN_PAIRS
    row = outcomes.query("side == 'short' and offset_bps == 1.0").iloc[0]
    assert row.bounce_fill
    assert np.isfinite(row.bounce_endpoint)


def test_sharded_processing_matches_monolithic_fixture():
    times = np.arange(0, 181_001, 40, dtype=np.int64)
    signs = np.where(np.arange(len(times)) % 2, 1, -1).astype(np.int8)
    prices = np.where(signs == 1, 100.2, 99.8)
    pair_times, pair_values = pair_events(times, prices, signs)
    trades = Trades(times, np.arange(len(times)), prices, signs, pair_times, pair_values)
    bbo_times = times.copy()
    bbo_mids = np.full(len(times), 100.0)
    grid = np.array([60_000, 120_000], dtype=np.int64)
    mono_origins, mono_outcomes = process_origins(grid, bbo_times, bbo_mids, trades)
    shard_parts = [process_origins(grid[i:i + 1], bbo_times, bbo_mids, trades)
                   for i in range(len(grid))]
    shard_origins = pd.concat([part[0] for part in shard_parts], ignore_index=True)
    shard_outcomes = pd.concat([part[1] for part in shard_parts], ignore_index=True)
    pdt.assert_frame_equal(mono_origins, shard_origins)
    pdt.assert_frame_equal(mono_outcomes, shard_outcomes)


def test_partial_parquet_is_never_complete(tmp_path: Path):
    final = tmp_path / "part-00000.parquet"
    partial = final.with_suffix(final.suffix + ".partial")
    pq.write_table(pa.table({"x": [1]}), partial)
    (tmp_path / "_SUCCESS").write_text("ok\n", encoding="ascii")
    assert not completed_parquet(final)
    partial.replace(final)
    assert completed_parquet(final)


def test_partial_edge_hours_do_not_request_unrelated_hour_context():
    for kind in ("bbo", "trade"):
        hours = _required_hours(kind)
        assert str(hours[0]) == "2023-05-16 11:00:00+00:00"
        assert str(hours[-1]) == "2024-04-01 06:00:00+00:00"


def test_empty_market_block_is_completed_not_missing(tmp_path: Path):
    work = tmp_path / "work"
    destination = tmp_path / "run" / "staging" / "bbo" / "date=2023-05-16" / "hour=22"
    work.mkdir()
    target_equivalence._finalize_stage_hour(work, destination, "bbo", tmp_path / "run")
    part = destination / "part-00000.parquet"
    assert completed_parquet(part)
    assert pq.ParquetFile(part).metadata.num_rows == 0


def test_endpoint_cache_is_shared_for_an_origin(monkeypatch):
    origin = 60_000
    times = np.arange(0, 181_001, 40, dtype=np.int64)
    signs = np.where(np.arange(len(times)) % 2, 1, -1).astype(np.int8)
    prices = np.where(signs == 1, 102.0, 98.0)
    pair_times, pair_values = pair_events(times, prices, signs)
    trades = Trades(times, np.arange(len(times)), prices, signs, pair_times, pair_values)
    calls = {"trade": 0}
    real = target_equivalence.trade_endpoint_reference

    def counted(*args, **kwargs):
        calls["trade"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(target_equivalence, "trade_endpoint_reference", counted)
    process_origins(np.array([origin]), times, np.full(len(times), 100.0), trades)
    assert calls["trade"] <= 4


def test_bbo_and_trade_staleness_guards():
    assert bbo_reference(np.array([1_000]), np.array([100.0]), 2_000,
                         inclusive=False) == 100.0
    assert math.isnan(bbo_reference(np.array([1_000]), np.array([100.0]), 2_001,
                                    inclusive=False))

    trades = hand_trades()
    last = int(trades.times[-1])
    assert np.isfinite(trade_origin_reference(trades, last + 1_000, False)[0])
    assert math.isnan(trade_origin_reference(trades, last + 1_001, False)[0])
    assert trade_endpoint_reference(trades, int(trades.times[0]), False) == trades.prices[0]
    assert math.isnan(trade_endpoint_reference(trades, last + 1_001, False))


def test_drop_rule_has_no_fallback_below_twenty_pairs():
    trades = hand_trades(BOUNCE_MIN_PAIRS - 1)
    query = int(trades.times[-1] + 1)
    reference, count = trade_origin_reference(trades, query, corrected=True)
    raw, _ = trade_origin_reference(trades, query, corrected=False)
    assert count == BOUNCE_MIN_PAIRS - 1
    assert math.isnan(reference)
    assert np.isfinite(raw)
