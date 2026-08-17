import hashlib
import json
from datetime import timedelta

import pytest

from btcusdt_quant import backtest, barrier_screen, cli, data, dataset, training


def _candle(i, op, hi, lo, close):
    return data.Candle(data.utc_minute(2024, 1, 1, 0, 0) + timedelta(minutes=i), op, hi, lo, close, 1, 1, 1, 1, 1)


def _write_cli_candles(path, count=240):
    lines = ["open_time,open,high,low,close,volume"]
    for i in range(count):
        price = 100.0 + i * 0.02
        lines.append(f"2024-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00,{price},{price + 0.1},{price - 0.1},{price + 0.02},1")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_barrier_screen_cli_sweep_runs_from_argv_and_writes_report(tmp_path, capsys):
    """Exercise the documented CLI route, not just the screen_horizons API."""
    input_path = tmp_path / "candles.csv"
    output = tmp_path / "horizon_screen"
    _write_cli_candles(input_path)

    code = cli.main([
        "barrier-screen", "--input", str(input_path), "--output", str(output),
        "--training-start", "2024-01-01", "--training-end", "2024-01-01",
        "--gate-feature", "rv_60", "--gate-quantile", "0.8",
        "--horizons",
    ])

    assert code == 0
    report = json.loads((output / "barrier_screen_report.json").read_text(encoding="utf-8"))
    assert report["screen_type"] == "training_barrier_horizon_sweep"
    assert report["horizons"] == [15, 30, 45, 60, 90, 120, 180]
    assert "Barrier screen complete" in capsys.readouterr().out


def test_barrier_screen_cli_single_horizon_runs_from_argv_and_writes_report(tmp_path, capsys):
    """Keep the historical --horizon 45 command covered at the CLI boundary."""
    input_path = tmp_path / "candles.csv"
    output = tmp_path / "single_horizon_screen"
    _write_cli_candles(input_path)

    code = cli.main([
        "barrier-screen", "--input", str(input_path), "--output", str(output),
        "--training-start", "2024-01-01", "--training-end", "2024-01-01",
        "--gate-feature", "rv_60", "--gate-quantile", "0.8",
        "--horizon", "45", "--candidates", "0.01:0.01",
    ])

    assert code == 0
    report = json.loads((output / "barrier_screen_report.json").read_text(encoding="utf-8"))
    assert report["screen_type"] == "training_barrier_geometry"
    assert report["unresolved_reconciliation"]["horizon"] == 45
    assert "Barrier screen complete" in capsys.readouterr().out


def test_screen_uses_production_labeller_for_known_touch_order_and_same_bar_tie(monkeypatch):
    # The next candle gives, in order: TP only, SL only, both/bullish (TP),
    # both/bearish (SL), and timeout.  This makes all touch orders observable.
    candles = [_candle(0, 100, 100, 100, 100), _candle(1, 100, 101.2, 100, 101),
               _candle(2, 101, 101, 99.5, 100), _candle(3, 100, 101.5, 98.5, 101),
               _candle(4, 101, 102.5, 99.5, 100), _candle(5, 100, 100, 100, 100)]
    expected = [dataset.triple_barrier_label_long(i, candles, 1, .01, .01) for i in range(5)]

    class Row:
        warmup_invalid = False
        def __init__(self): self.features = {"rv_60": 1.0}
    monkeypatch.setattr(dataset, "build_feature_rows", lambda _: [Row() for _ in candles])
    report = barrier_screen.screen(candles, training_start=None, training_end=None,
                                   gate_feature="rv_60", gate_quantile=0.0, horizon=1,
                                   candidates=((.01, .01),))
    result = report["results"][0]
    assert expected == [(1, "long_tp_first"), (0, "long_sl_first"), (1, "long_tp_first"),
                        (0, "long_sl_first"), (0, "long_timeout")]
    assert result["tp_rows"] == 2
    assert result["sl_rows"] == 2
    assert result["unresolved_rows"] == 1
    assert result["resolved_share"] == 4 / 5
    assert result["conditional_tp_share"] == 1 / 2
    assert result["whole_population_tp_share"] == 2 / 5
    assert result["random_walk_tp_share"] == 1 / 2
    assert result["break_even_tp_share"] == 0.52


def test_timeout_settlement_is_identical_for_label_scoring_and_execution():
    # No barrier is touched; the label is still binary class 0, but that must
    # never be reinterpreted as an SL.  Its reason settles at the horizon close.
    candles = [_candle(0, 100, 100, 100, 100), _candle(1, 100, 100.5, 99.5, 100.3)]
    label, reason = dataset.triple_barrier_label_long(0, candles, 1, .01, .01)
    assert (label, reason) == (0, "long_timeout")

    outcome, execution_gross = backtest._barrier_outcome_after_run(
        candles, 0, "BUY", 101.0, 99.0, horizon=1, min_hold_bars=0,
    )
    assert outcome == "TIMEOUT"
    assert abs(execution_gross - 0.003) < 1e-12

    # This assertion fails if threshold selection falls back to class-0 == SL.
    net = training._trading_pnl([0.9], [label], .5, tp_pct=.01, sl_pct=.01,
                                round_trip_cost=.0004, realized_payoffs=[execution_gross])
    assert abs(net[0] - 0.0026) < 1e-12

    # A shortened settlement vector must not silently revive the former
    # class-0-is-SL fallback (-1.04% net here instead of +0.26%).
    with pytest.raises(ValueError, match="exactly one executable settlement"):
        training._trading_pnl([0.9], [label], .5, tp_pct=.01, sl_pct=.01,
                              round_trip_cost=.0004, realized_payoffs=[])


def test_screen_reports_ungated_reconciliation_on_the_same_training_rows(monkeypatch):
    candles = [_candle(i, 100, 100, 100, 100) for i in range(4)]

    class Row:
        features = {"rv_60": 1.0}

    monkeypatch.setattr(dataset, "build_feature_rows", lambda _: [Row() for _ in candles])
    monkeypatch.setattr(dataset, "triple_barrier_label_long", lambda index, *_: (
        1, "long_tp_first") if index == 0 else (0, "long_timeout"))
    report = barrier_screen.screen(candles, training_start=None, training_end=None,
                                   gate_feature="rv_60", gate_quantile=0.0, horizon=1,
                                   candidates=((.008, .004),))

    reconciliation = report["unresolved_reconciliation"]
    assert reconciliation["training_rows"] == 3
    assert reconciliation["gate_off_unresolved_share"] == 2 / 3
    assert reconciliation["gated_unresolved_share"] == 2 / 3


def test_default_candidates_and_report_identify_the_historical_geometry(monkeypatch):
    expected = ((.004, .002), (.006, .003), (.008, .004), (.010, .005), (.012, .006),
                (.006, .006), (.008, .008), (.010, .010), (.004, .004), (.012, .012))
    candles = [_candle(i, 100, 100, 100, 100) for i in range(11)]

    class Row:
        warmup_invalid = False
        features = {"rv_60": 1.0}

    monkeypatch.setattr(dataset, "build_feature_rows", lambda _: [Row() for _ in candles])
    report = barrier_screen.screen(candles, training_start=None, training_end=None,
                                   gate_feature="rv_60", gate_quantile=0.0, horizon=1,
                                   candidates=barrier_screen.parse_candidates(None))

    assert barrier_screen.parse_candidates(None) == expected
    assert report["candidate_source"] == "historical_default"
    assert report["candidate_sets"]["historical"] == [
        {"tp_pct": tp, "sl_pct": sl} for tp, sl in expected
    ]
    assert report["candidate_sets"]["additions"] == []
    assert [(row["tp_pct"], row["sl_pct"], row["category"]) for row in report["candidates"]] == [
        (tp, sl, "historical") for tp, sl in expected
    ]


def test_gate_fingerprint_matches_the_pre_streaming_json_digest():
    feature, lo, label_hi = 'rv_60/"quoted"', 3, 17
    values = [-0.0, 0.000961841, 1.0e20, 1.2345678901234567]
    legacy_payload = json.dumps({
        "feature": feature, "training_indices": [lo, label_hi], "finite_values": values,
    }, separators=(",", ":"))

    assert barrier_screen._gate_input_fingerprint(feature, lo, label_hi, values) == hashlib.sha256(legacy_payload.encode("utf-8")).hexdigest()


def test_horizon_sweep_uses_the_production_labeller_and_derives_each_tail_trimmed_gate(monkeypatch):
    candles = [_candle(i, 100, 100, 100, 100) for i in range(7)]

    class Row:
        warmup_invalid = False
        def __init__(self, value): self.features = {"rv_60": value}

    calls = []
    monkeypatch.setattr(dataset, "build_feature_rows", lambda _: [Row(float(i)) for i in range(len(candles))])
    monkeypatch.setattr(dataset, "triple_barrier_label_long", lambda index, _, horizon, tp, sl: (
        calls.append((index, horizon, tp, sl)) or (0, "long_timeout")))

    report = barrier_screen.screen_horizons(
        candles, training_start=None, training_end=None, gate_feature="rv_60",
        gate_quantile=0.75, horizons=(1, 2), candidates=((.01, .01),),
    )

    first, second = report["horizon_reports"]
    assert report["touch_resolver"] == "dataset.triple_barrier_label_long"
    assert report["horizons"] == [1, 2]
    assert first["training_slice"]["label_end_index_exclusive"] == 6
    assert second["training_slice"]["label_end_index_exclusive"] == 5
    assert first["gate"]["cutoff"] == 4.0
    assert second["gate"]["cutoff"] == 3.0
    assert first["results"][0]["unresolved_rows"] == first["results"][0]["screened_rows"]
    assert second["results"][0]["unresolved_rows"] == second["results"][0]["screened_rows"]
    assert {call[1] for call in calls} == {1, 2}
    assert all(index < (6 if horizon == 1 else 5) for index, horizon, _, _ in calls)


def test_parse_horizons_has_recommended_sweep_and_rejects_duplicates():
    assert barrier_screen.parse_horizons("default") == (15, 30, 45, 60, 90, 120, 180)
    assert barrier_screen.parse_horizons("30,45,90") == (30, 45, 90)
    try:
        barrier_screen.parse_horizons("45,45")
    except ValueError as exc:
        assert "duplicates" in str(exc)
    else:
        raise AssertionError("duplicate horizons must be rejected")
