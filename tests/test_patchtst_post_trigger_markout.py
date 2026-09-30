import numpy as np
import pandas as pd
import pytest

from out import run_patchtst_post_trigger_markout as audit


def test_stop_deciles_keep_duplicates_and_q90_ties_pass():
    stop = np.r_[np.zeros(90), np.ones(10)]
    cuts, cells = audit.decile_from_stop(stop, np.array([-1.0, 0.0, 1.0, 2.0]))
    assert len(np.unique(cuts)) < 9
    np.testing.assert_array_equal(cells, [1, 9, 10, 10])
    q90 = np.quantile(np.array([1.0, 2.0, 2.0, 2.0]), 0.9, method="linear")
    np.testing.assert_array_equal(np.array([1.99, 2.0, 99.0]) >= q90,
                                  [False, True, True])


def test_close_only_trigger_tau_side_and_final_bar_zero_markout():
    close = np.full(50, 100.0)
    close[17] = 100.0 * np.exp(0.0011)
    close[30] = 100.0 * np.exp(0.0031)
    states = audit.event_states(close, np.array([15]))
    assert states.loc[0, "triggered_10"]
    assert states.loc[0, "tau_10"] == 2
    assert states.loc[0, "cross_side_10"] == 1
    assert states.loc[0, "triggered_30"]
    assert states.loc[0, "tau_30"] == 15
    assert not states.loc[0, "triggered_50"]

    frame = pd.DataFrame({"signal_index": [15], **states.to_dict("list")})
    marked = audit.add_markouts(frame, close)
    assert marked.loc[0, "z_bps_10"] == pytest.approx(20.0)
    assert marked.loc[0, "z_bps_30"] == pytest.approx(0.0)
    assert marked.loc[0, "z_bps_50"] == 0.0


def test_rate_only_selection_uses_band_target_and_larger_exact_tie():
    rows = pd.DataFrame([
        {"trigger_bps": 10, "q90_origin_count": 100, "q90_trigger_count": 25,
         "q90_realised_rate": 0.25},
        {"trigger_bps": 20, "q90_origin_count": 100, "q90_trigger_count": 45,
         "q90_realised_rate": 0.45},
        {"trigger_bps": 30, "q90_origin_count": 100, "q90_trigger_count": 61,
         "q90_realised_rate": 0.61},
    ])
    assert audit.choose_trigger(rows) == 20
    rows["q90_realised_rate"] = 0.1
    assert audit.choose_trigger(rows) is None


def test_fold_fixed_effect_clustered_trend_recovers_slope():
    fold = np.repeat([1, 2, 3], 10)
    decile = np.tile(np.arange(1, 11), 3)
    intercept = np.repeat([10.0, -5.0, 3.0], 10)
    noise = np.tile(np.array([1, -1, 1, -1, 1, -1, 1, -1, 1, -1]) * 0.1, 3)
    y = intercept + 2.0 * (decile - 5.5) + noise
    result = audit.clustered_trend(y, decile, fold)
    assert result["fold_clusters"] == 3
    assert result["beta_bps_per_decile"] == pytest.approx(1.9939393939)
    assert result["ci95_lower"] <= result["beta_bps_per_decile"] <= result["ci95_upper"]


def test_baselines_share_selected_trigger_and_patch_gate():
    frame = pd.DataFrame({
        "pilot_fold": [1, 1, 2, 2],
        "triggered_10": [True, False, True, True],
        "post_return_bps_10": [2.0, 0.0, -3.0, 4.0],
        "z_bps_10": [2.0, 0.0, 3.0, -4.0],
        "patchtst_q90_gate": [True, True, False, False],
        "range_60_q90_gate": [False, False, True, True],
        "oracle_q90_gate": [True, False, True, False],
        "fade_15m_side": [-1, 1, -1, 1],
        "continuation_1m_side": [1, 1, 1, -1],
        "ema5_over_ema20_side": [1, -1, -1, -1],
    })
    rows, origins = audit._baseline_reports(frame, 10)
    by_name = {row["name"]: row for row in rows}
    assert by_name["patchtst"]["mean_calendar_markout_bps"] == pytest.approx(0.5)
    assert by_name["always_armed"]["realised_trigger_rate"] == pytest.approx(0.75)
    assert by_name["matched_prior_1m_continuation"]["gate_rate"] == 0.5
    assert "baseline_y_matched_ema5_over_ema20_bps" in origins


def test_stop_reconstruction_never_authorizes_fit(monkeypatch):
    monkeypatch.setattr(audit.forecast, "split_indices",
                        lambda data, fold, phase: np.array([0, 1]))
    calls = []

    def checked_loader(data, fold, seed, train, stop, fit_missing=False):
        calls.append(fit_missing)
        return object()

    monkeypatch.setattr(audit.forecast, "load_or_fit", checked_loader)
    monkeypatch.setattr(audit.forecast, "predict",
                        lambda fitted, data, stop: np.ones((len(stop), 2)))
    data = type("Data", (), {
        "range_60": np.array([2.0, 3.0]),
        "targets": np.array([[4.0, 5.0], [6.0, 7.0]]),
    })()
    audit.FIT_CALLS = audit.forecast.FIT_CALLS = 0
    assert set(audit._stop_sources(data, 406)) == {
        "patchtst", "range_60", "realised_excursion_oracle"
    }
    assert calls == [False, False, False]
    assert audit.FIT_CALLS == audit.forecast.FIT_CALLS == 0


def test_manifest_refuses_source_mutation(monkeypatch, tmp_path):
    source, plan, market = tmp_path / "source.py", tmp_path / "plan.md", tmp_path / "market"
    forecast_file = tmp_path / "forecast"
    for path, value in ((source, b"source"), (plan, b"plan"),
                        (market, b"market"), (forecast_file, b"forecast")):
        path.write_bytes(value)
    monkeypatch.setattr(audit, "PLAN", plan)
    monkeypatch.setattr(audit, "MARKET", market)
    monkeypatch.setattr(audit, "FORECAST_ROOT", tmp_path)
    monkeypatch.setattr(audit, "validate_hashes", lambda root, hashes: None)
    manifest = {
        "phase_authorization": "exploration_only",
        "plan_sha256": audit.sha256(plan),
        "source_sha256": {str(source): audit.sha256(source)},
        "market_sha256": audit.sha256(market),
        "forecast_artifact_sha256": {forecast_file.name: audit.sha256(forecast_file)},
        "forecast_checkpoint_sha256": {"x": "0" * 64},
        "forecast_imported_source_sha256": {},
        "forecast_input_sha256": {},
    }
    audit.validate_manifest(manifest)
    source.write_bytes(b"mutated")
    with pytest.raises(AssertionError, match="source hash mismatch"):
        audit.validate_manifest(manifest)


def test_confirmation_phase_is_refused_before_work():
    with pytest.raises(ValueError, match="not authorized"):
        audit.execute(phase="confirmation")
