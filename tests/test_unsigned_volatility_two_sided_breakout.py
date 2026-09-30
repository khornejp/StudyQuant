import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from out import run_unsigned_volatility_two_sided_breakout as audit


def _bars(size=40, price=100.0):
    open_ = np.full(size, price)
    high = np.full(size, price)
    low = np.full(size, price)
    close = np.full(size, price)
    return open_, high, low, close


def test_stop_only_deciles_keep_duplicate_cuts_and_q90_ties_pass():
    stop = np.r_[np.zeros(90), np.ones(10)]
    cuts_a, cells = audit.decile_from_stop(stop, np.array([-1.0, 0.0, 1.0, 2.0]))
    cuts_b, _ = audit.decile_from_stop(stop, np.array([1e9]))
    np.testing.assert_array_equal(cuts_a, cuts_b)
    assert len(np.unique(cuts_a)) < 9
    np.testing.assert_array_equal(cells, [1, 9, 10, 10])
    threshold, selected = audit.q90_gate(np.array([1.0, 2.0, 2.0, 2.0]),
                                         np.array([1.99, 2.0, 99.0]))
    assert threshold == 2.0
    np.testing.assert_array_equal(selected, [False, True, True])


def test_breakout_timing_symmetry_wicks_next_open_and_final_bar():
    up = _bars()
    up[1][16] = 100.05
    up[3][16] = 100.05
    up[0][17] = up[1][17] = up[2][17] = up[3][17] = 100.07
    upper = audit.resolve_breakouts(*up, np.array([15])).iloc[0]
    assert upper.conservative_side == 1
    assert upper.first_confirmation_bar == 1
    assert upper.conservative_entry_bar == 2
    assert upper.conservative_entry_price == 100.07

    down = _bars()
    down[2][16] = 99.95
    down[3][16] = 99.95
    down[0][17] = down[1][17] = down[2][17] = down[3][17] = 99.93
    lower = audit.resolve_breakouts(*down, np.array([15])).iloc[0]
    assert lower.conservative_side == -1
    assert lower.first_confirmation_bar == 1
    assert lower.conservative_entry_price == 99.93

    wick = _bars()
    wick[1][16] = 100.05
    wick_only = audit.resolve_breakouts(*wick, np.array([15])).iloc[0]
    assert wick_only.optimistic_touch and wick_only.wick_only
    assert not wick_only.conservative_confirmation

    final = _bars()
    final[1][30] = final[3][30] = 100.05
    final_bar = audit.resolve_breakouts(*final, np.array([15])).iloc[0]
    assert final_bar.final_bar_first_touch and final_bar.final_bar_close_confirmation
    assert not final_bar.conservative_confirmation


def test_optimistic_dual_touch_uses_future_favourable_terminal_side():
    bars = _bars()
    bars[1][16], bars[2][16] = 100.05, 99.95
    bars[0][30] = bars[1][30] = bars[2][30] = bars[3][30] = 101.0
    result = audit.resolve_breakouts(*bars, np.array([15])).iloc[0]
    assert result.optimistic_dual_touch
    assert result.optimistic_side == 1


def test_exact_one_cost_debit_abstention_and_matched_fade():
    assert audit.single_trade_net_bps(100.0, 100.1, 1) == pytest.approx(6.0)
    assert audit.single_trade_net_bps(100.0, 99.9, -1) == pytest.approx(6.0)
    assert audit.single_trade_net_bps(100.0, 100.1, 0) == 0.0
    assert audit.matched_fade_side(99.0, 100.0) == -1
    assert audit.matched_fade_side(101.0, 100.0) == 1
    assert audit.matched_fade_side(100.0, 100.0) == 0


def test_sequential_non_overlap_and_unauthorized_phase_refusal():
    audit.assert_sequential(np.array([15, 30, 45]))
    with pytest.raises(AssertionError, match="at least 15"):
        audit.assert_sequential(np.array([15, 29]))
    with pytest.raises(ValueError, match="not authorized"):
        audit.execute(phase=2)


def test_oracle_is_explicitly_noncausal():
    assert audit.SOURCES["realised_excursion_oracle"] == "excursion_bps"
    assert audit.ORACLE_LABEL.startswith("noncausal")


def test_ordering_falsifier_is_frozen():
    rows = []
    for decile in range(1, 11):
        rows.append({
            "source": "patchtst", "scope": "pooled", "stop_decile": decile,
            "mean_realised_excursion_bps": float(decile),
            "conservative_confirmation_rate": decile / 10,
        })
    verdict, checks = audit._ordering_verdict(pd.DataFrame(rows))
    assert verdict == "TRAVEL_ORDERING_PASS" and all(checks.values())
    rows[5]["mean_realised_excursion_bps"] = 0.0
    assert audit._ordering_verdict(pd.DataFrame(rows))[0] == "TRAVEL_ORDERING_FAIL"


def test_manifest_hash_validation_refuses_mutation(monkeypatch, tmp_path):
    source = tmp_path / "source.py"
    plan, market = tmp_path / "plan.md", tmp_path / "market.parquet"
    forecast_root = tmp_path / "forecast"
    forecast_root.mkdir()
    for path, value in ((source, b"source"), (plan, b"plan"), (market, b"market"),
                        (forecast_root / "manifest.json", b"forecast")):
        path.write_bytes(value)
    monkeypatch.setattr(audit, "PLAN", plan)
    monkeypatch.setattr(audit, "MARKET", market)
    monkeypatch.setattr(audit, "FORECAST_ROOT", forecast_root)
    monkeypatch.setattr(audit, "validate_forecast_tree", lambda: None)
    manifest = {
        "phase_authorization": "stage1_only",
        "plan_sha256": audit.sha256(plan),
        "source_sha256": {str(source): audit.sha256(source)},
        "market_sha256": audit.sha256(market),
        "forecast_artifact_sha256": {
            "manifest.json": audit.sha256(forecast_root / "manifest.json")
        },
    }
    audit.validate_manifest(manifest)
    source.write_bytes(b"mutated")
    with pytest.raises(AssertionError, match="source hash mismatch"):
        audit.validate_manifest(manifest)


def test_verify_reconstructs_with_zero_fits(monkeypatch, tmp_path):
    frame = pd.DataFrame({"x": [1.0]})
    report = {"new_model_fits": 0, "aggregate_strategy_pnl_computations": 0}
    frame.to_parquet(tmp_path / "ordering_audit.parquet", index=False)
    (tmp_path / "ordering_audit.json").write_text(json.dumps(report), encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    hashes = {name: audit.sha256(tmp_path / name)
              for name in ("ordering_audit.parquet", "ordering_audit.json")}
    (tmp_path / "ordering_audit_sha256.json").write_text(json.dumps(hashes), encoding="utf-8")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "validate_manifest", lambda manifest: None)
    monkeypatch.setattr(audit, "peak_rss", lambda block: 0)
    monkeypatch.setattr(audit.forecast, "fit", lambda *args, **kwargs: pytest.fail("fit called"))
    monkeypatch.setattr(audit.forecast, "split_indices",
                        lambda data, fold, phase: np.array([0, 1]))
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
        assert set(audit._stop_sources(data, 406)) == set(audit.SOURCES)
        return frame, report

    monkeypatch.setattr(audit, "build_ordering_audit", reconstruct)
    result = audit.execute(verify=True)
    assert fit_missing_values == [False, False, False]
    assert result["fit_calls"] == result["new_model_fits"] == 0
    assert result["aggregate_strategy_pnl_computations"] == 0
