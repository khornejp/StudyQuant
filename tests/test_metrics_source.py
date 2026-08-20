from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from btcusdt_quant import metrics_source as metrics


def _row(at: datetime, scale: float) -> metrics.MetricsRow:
    return metrics.MetricsRow(
        create_time=at,
        values={
            "sum_open_interest": 100.0 + scale,
            "sum_open_interest_value": 1_000.0 + scale,
            "count_toptrader_long_short_ratio": 2.0 + scale,
            "sum_toptrader_long_short_ratio": 4.0 + scale,
            "count_long_short_ratio": 8.0 + scale,
            "sum_taker_long_short_vol_ratio": 16.0 + scale,
        },
    )


def test_metrics_alignment_uses_create_time_as_the_first_visible_minute() -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    at_t = base + timedelta(minutes=5)
    rows = [_row(base, 1.0), _row(at_t, 2.0)]
    minutes = [base + timedelta(minutes=offset) for offset in range(10)]

    raw = metrics.align_metrics_to_minutes(rows, minutes)
    derived = metrics.metrics_features_to_minutes(rows, minutes)

    # The new row is not visible one minute before its create_time, is visible
    # at create_time, and remains the active value for the next four minutes.
    assert raw[at_t - timedelta(minutes=1)]["sum_open_interest"] == 101.0
    assert raw[at_t]["sum_open_interest"] == 102.0
    assert raw[at_t + timedelta(minutes=4)]["sum_open_interest"] == 102.0
    assert derived[at_t - timedelta(minutes=1)]["global_ls_account"] == 9.0
    assert derived[at_t]["global_ls_account"] == 10.0
    assert derived[at_t + timedelta(minutes=4)]["global_ls_account"] == 10.0


def test_new_metrics_features_are_causal_and_forward_fill_from_their_tick() -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [_row(base + timedelta(minutes=5 * tick), float(tick)) for tick in range(8)]
    features = metrics.compute_metrics_features(rows)
    at_t = base + timedelta(minutes=30)
    row = features[at_t]

    assert row["global_ls_account_change_15m"] == (14.0 - 11.0) / 11.0
    assert row["global_ls_account_change_30m"] == (14.0 - 8.0) / 8.0
    assert row["taker_ls_ratio_change_15m"] == (22.0 - 19.0) / 19.0
    assert row["taker_ls_ratio_change_30m"] == (22.0 - 16.0) / 16.0
    assert row["global_ls_account_taker_ls_ratio_gap"] == math.log(14.0) - math.log(22.0)

    # Altering a future tick cannot change any feature at T. The same feature
    # vector first becomes visible at T and remains active through T+4.
    future_changed = rows[:-1] + [_row(rows[-1].create_time, 10_000.0)]
    changed_features = metrics.compute_metrics_features(future_changed)
    assert changed_features[at_t] == row
    minutes = [at_t - timedelta(minutes=1), at_t, at_t + timedelta(minutes=4)]
    aligned = metrics.metrics_features_to_minutes(rows, minutes)
    assert aligned[at_t - timedelta(minutes=1)] != row
    assert aligned[at_t] == row
    assert aligned[at_t + timedelta(minutes=4)] == row


def test_csv_keeps_rows_and_fields_that_parse_when_other_fields_are_blank() -> None:
    parsed = metrics.parse_metrics_csv_text(
        "create_time,symbol,sum_open_interest,sum_open_interest_value,count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
        "2022-01-01 00:00:00,BTCUSDT,10,20,,,3,4\n"
    )
    assert len(parsed) == 1
    assert parsed[0].values == {
        "sum_open_interest": 10.0,
        "sum_open_interest_value": 20.0,
        "count_long_short_ratio": 3.0,
        "sum_taker_long_short_vol_ratio": 4.0,
    }


def test_missing_field_clears_feature_and_staleness_cap_ends_forward_fill() -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    complete = _row(base, 1.0)
    missing_taker = metrics.MetricsRow(base + timedelta(minutes=5), {
        name: value for name, value in _row(base, 2.0).values.items()
        if name != "sum_taker_long_short_vol_ratio"
    })
    derived = metrics.metrics_features_to_minutes(
        [complete, missing_taker],
        [base + timedelta(minutes=4), base + timedelta(minutes=5), base + timedelta(minutes=46)],
    )
    assert "taker_ls_ratio" in derived[base + timedelta(minutes=4)]
    assert "taker_ls_ratio" not in derived[base + timedelta(minutes=5)]
    assert base + timedelta(minutes=46) not in derived


def test_change_rate_uses_timestamp_not_row_position() -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [_row(base + timedelta(minutes=5 * tick), float(tick)) for tick in range(6)]
    # The sixth row is an hour later: six rows back is not a 30-minute input.
    rows.append(_row(base + timedelta(minutes=85), 6.0))
    values = metrics.compute_metrics_features(rows)
    assert math.isnan(values[rows[-1].create_time]["oi_change_rate_30m"])


def test_change_rate_refuses_a_30m_seam_after_a_multimonth_gap() -> None:
    base = datetime(2022, 1, 1, tzinfo=timezone.utc)
    before = _row(base, 1.0)
    after = _row(datetime(2022, 5, 12, tzinfo=timezone.utc), 2.0)
    assert math.isnan(metrics.compute_metrics_features([before, after])[after.create_time]["taker_ls_ratio_change_30m"])


def test_log_gap_is_unavailable_not_zero_when_an_input_is_missing_or_nonpositive() -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    missing = metrics.MetricsRow(base, {"count_long_short_ratio": 2.0})
    zero = metrics.MetricsRow(base + timedelta(minutes=5), {
        "count_long_short_ratio": 2.0,
        "sum_taker_long_short_vol_ratio": 0.0,
    })
    equal = metrics.MetricsRow(base + timedelta(minutes=10), {
        "count_long_short_ratio": 2.0,
        "sum_taker_long_short_vol_ratio": 2.0,
    })
    values = metrics.compute_metrics_features([missing, zero, equal])
    assert math.isnan(values[base]["global_ls_account_taker_ls_ratio_gap"])
    assert math.isnan(values[zero.create_time]["global_ls_account_taker_ls_ratio_gap"])
    assert values[equal.create_time]["global_ls_account_taker_ls_ratio_gap"] == 0.0


def test_taker_splice_uses_prior_five_klines_and_marks_its_provenance() -> None:
    from btcusdt_quant.data import Candle

    at = datetime(2022, 1, 1, 0, 5, tzinfo=timezone.utc)
    candles = [Candle(at - timedelta(minutes=i), 1, 1, 1, 1, 10.0, 10.0, 1, 6.0, 6.0) for i in range(1, 6)]
    missing = metrics.MetricsRow(at, {"count_long_short_ratio": 2.0})
    preserved = metrics.MetricsRow(at + timedelta(minutes=5), {"count_long_short_ratio": 2.0, "sum_taker_long_short_vol_ratio": 9.0})
    rows, reconstructed = metrics.splice_taker_ratio_from_klines([missing, preserved], candles)
    assert rows[0].values["sum_taker_long_short_vol_ratio"] == 1.5
    assert rows[1] == preserved
    assert reconstructed == {at}
    minute = metrics.metrics_features_to_minutes(rows, [at], reconstructed)[at]
    assert minute[metrics.TAKER_PROVENANCE_KEY] == metrics.TAKER_RECONSTRUCTED_PROVENANCE
