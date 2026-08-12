import hashlib
import json
from datetime import timedelta

from btcusdt_quant import barrier_screen, data, dataset


def _candle(i, op, hi, lo, close):
    return data.Candle(data.utc_minute(2024, 1, 1, 0, 0) + timedelta(minutes=i), op, hi, lo, close, 1, 1, 1, 1, 1)


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
