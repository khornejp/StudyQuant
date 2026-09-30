import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from out import run_unsigned_volatility_abstention_backtest as audit


def test_stop_only_deciles_and_duplicate_cuts_are_retained():
    stop = np.r_[np.zeros(90), np.ones(10)]
    cuts_a, cells_a = audit.decile_from_stop(stop, np.array([-1.0, 0.0, 1.0, 2.0]))
    cuts_b, _ = audit.decile_from_stop(stop, np.array([1e9]))
    np.testing.assert_array_equal(cuts_a, cuts_b)
    assert len(cuts_a) == 9 and len(np.unique(cuts_a)) < 9
    np.testing.assert_array_equal(cells_a, [1, 9, 10, 10])


def test_deployed_gate_uses_stop_median_and_ties_pass():
    threshold, selected = audit.median_gate(np.array([1.0, 2.0, 2.0, 9.0]),
                                            np.array([1.99, 2.0, 99.0]))
    assert threshold == 2.0
    np.testing.assert_array_equal(selected, [False, True, True])


def test_exact_cost_and_abstentions_are_calendar_zeros():
    actual = audit.calendar_net(np.array([10.0, 20.0, 30.0]),
                                np.array([True, True, False]),
                                np.array([True, False, True]))
    np.testing.assert_array_equal(actual, [6.0, 0.0, 0.0])


def test_short_and_long_metrics_are_separate():
    frame = pd.DataFrame({
        "direction": [-1, 1, 0],
        "gross_short_bps": [8.0, -5.0, 2.0],
        "gross_long_bps": [-8.0, 5.0, -2.0],
        "source_bps": [1.0, 2.0, 3.0],
        "excursion_bps": [4.0, 5.0, 6.0],
        "terminal_bps": [-8.0, 5.0, -2.0],
        "passes_deployed_gate": [True, True, False],
    })
    short, long = audit._cell(frame, "short"), audit._cell(frame, "long")
    assert short["directional_signal_count"] == long["directional_signal_count"] == 1
    assert short["mean_gross_bps"] == 8.0
    assert long["mean_gross_bps"] == 5.0
    assert short["mean_net_bps"] == 4.0
    assert long["mean_net_bps"] == 1.0


def test_sequential_non_overlap_contract():
    audit.assert_sequential(np.array([15, 30, 45]))
    with pytest.raises(AssertionError, match="at least 15"):
        audit.assert_sequential(np.array([15, 29]))


def test_market_alignment_is_causal_and_exact(monkeypatch, tmp_path):
    times = pd.date_range("2024-01-01", periods=61, freq="min", tz="UTC")
    market = pd.DataFrame({"open_time": times, "open": np.arange(61) + 100.0,
                           "close": np.arange(61) + 100.5})
    path = tmp_path / "market.parquet"
    market.to_parquet(path, index=False)
    monkeypatch.setattr(audit, "MARKET", path)
    ensemble = pd.DataFrame({"signal_index": [15, 30, 45],
                             "open_time": times[[15, 30, 45]]})
    result = audit._load_test_market(ensemble)
    assert result.direction.tolist() == [-1, -1, -1]
    np.testing.assert_allclose(result.terminal_bps, [
        (130.5 / 116.0 - 1) * 1e4,
        (145.5 / 131.0 - 1) * 1e4,
        (160.5 / 146.0 - 1) * 1e4,
    ])
    np.testing.assert_allclose(result.reference_gap_bps, [
        (116.0 / 115.5 - 1) * 1e4,
        (131.0 / 130.5 - 1) * 1e4,
        (146.0 / 145.5 - 1) * 1e4,
    ])
    bad = ensemble.copy()
    bad.loc[1, "open_time"] += pd.Timedelta(minutes=1)
    with pytest.raises(AssertionError, match="alignment"):
        audit._load_test_market(bad)


def test_oracle_is_explicitly_noncausal():
    assert "realised_excursion_oracle" in audit.SOURCES
    assert audit.SOURCES["realised_excursion_oracle"] == "excursion_bps"
    assert audit.ORACLE_LABEL.startswith("realised H15 excursion")


@pytest.mark.parametrize(
    ("oracle", "model", "expected"),
    [
        ({"no_trade": 0, "range_60": 1, "direction_only": 1},
         {"no_trade": 1, "range_60": 1, "direction_only": 1},
         "SIZE_POLICY_NO_HEADROOM"),
        ({"no_trade": 1, "range_60": 1, "direction_only": 1},
         {"no_trade": 1, "range_60": 0, "direction_only": 1},
         "FORECAST_DOES_NOT_HELP"),
        ({"no_trade": 1, "range_60": 1, "direction_only": 1},
         {"no_trade": 1, "range_60": 1, "direction_only": 1},
         "FORECAST_HELPS"),
    ],
)
def test_verdict_falsifiers(oracle, model, expected):
    assert audit.verdict(oracle, model) == expected


def test_manifest_hash_validation_refuses_mutation(monkeypatch, tmp_path):
    source = tmp_path / "tests" / audit.TEST_SOURCE.name
    source.parent.mkdir()
    source.write_bytes(b"frozen")
    plan, market = tmp_path / "plan.md", tmp_path / "market.parquet"
    plan.write_bytes(b"plan")
    market.write_bytes(b"market")
    forecast_root = tmp_path / "forecast"
    forecast_root.mkdir()
    (forecast_root / "manifest.json").write_bytes(b"forecast")
    monkeypatch.setattr(audit, "PLAN", plan)
    monkeypatch.setattr(audit, "MARKET", market)
    monkeypatch.setattr(audit, "FORECAST_ROOT", forecast_root)
    monkeypatch.setattr(audit, "validate_forecast_tree", lambda: None)
    manifest = {
        "plan_sha256": audit.sha256(plan),
        "source_sha256": {str(source): audit.sha256(source)},
        "market_sha256": audit.sha256(market),
        "forecast_artifact_sha256": {"manifest.json": audit.sha256(forecast_root / "manifest.json")},
    }
    audit.validate_manifest(manifest)
    source.write_bytes(b"mutated")
    with pytest.raises(AssertionError, match="source hash mismatch"):
        audit.validate_manifest(manifest)


def test_verify_reconstructs_with_zero_fits(monkeypatch, tmp_path):
    frame = pd.DataFrame({"x": [1.0]})
    report = {"new_model_fits": 0, "aggregate_pnl_computations": 0}
    frame.to_parquet(tmp_path / "ordering_audit.parquet", index=False)
    (tmp_path / "ordering_audit.json").write_text(json.dumps(report), encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    hashes = {
        name: audit.sha256(tmp_path / name)
        for name in ("ordering_audit.parquet", "ordering_audit.json")
    }
    (tmp_path / "ordering_audit_sha256.json").write_text(json.dumps(hashes), encoding="utf-8")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "validate_manifest", lambda manifest: None)
    monkeypatch.setattr(audit, "peak_rss", lambda block: 0)
    monkeypatch.setattr(audit.forecast, "fit", lambda *args, **kwargs: pytest.fail("fit called"))
    monkeypatch.setattr(audit.forecast, "split_indices", lambda data, fold, phase: np.array([0, 1]))
    fit_missing_values = []

    def load_or_fit(data, fold, seed, train, stop, fit_missing):
        fit_missing_values.append(fit_missing)
        return object()

    monkeypatch.setattr(audit.forecast, "load_or_fit", load_or_fit)
    monkeypatch.setattr(audit.forecast, "predict",
                        lambda fitted, data, stop: np.ones((len(stop), 2)))
    data = SimpleNamespace(range_60=np.array([2.0, 3.0]),
                           targets=np.array([[4.0, 5.0], [6.0, 7.0]]))

    def reconstruct():
        sources = audit._stop_sources(data, 406)
        assert set(sources) == set(audit.SOURCES)
        return frame, report

    monkeypatch.setattr(audit, "build_ordering_audit", reconstruct)
    result = audit.execute(verify=True)
    assert fit_missing_values == [False, False, False]
    assert result["fit_calls"] == result["new_model_fits"] == 0
    assert result["aggregate_pnl_computations"] == 0
