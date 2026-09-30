from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from out import run_patchtst_down_breakout_long_confirmation as confirmation


def test_calendar_extension_and_fixed_fit_budget():
    first = confirmation.fold_spec(606)
    last = confirmation.fold_spec(666)
    assert first["test_start"] == pd.Timestamp("2026-01-01T00:00:00Z")
    assert first["test_end"] == pd.Timestamp("2026-01-03T00:00:00Z")
    assert last["test_start"] == pd.Timestamp("2026-06-29T00:00:00Z")
    assert last["test_end"] == pd.Timestamp("2026-07-01T00:00:00Z")
    assert len(confirmation.FOLDS) * len(confirmation.SEEDS) == 183


def test_stop_q90_ties_pass():
    threshold, gate = confirmation.q90_gate(
        np.array([1.0, 2.0, 2.0, 2.0]), np.array([1.99, 2.0, 99.0]))
    assert threshold == 2.0
    np.testing.assert_array_equal(gate, [False, True, True])


def test_completed_close_trigger_uses_overshoot_for_both_arms(monkeypatch, tmp_path):
    close = np.full(50, 100.0)
    close[17] = 100.0 * np.exp(-0.006)
    close[30] = close[17] * np.exp(0.001)
    close[34] = 100.0 * np.exp(0.006)
    close[47] = close[34] * np.exp(-0.001)
    market = pd.DataFrame({
        "open_time": pd.date_range("2025-12-31T23:45:00Z", periods=50, freq="min"),
        "close": close,
    })
    path = tmp_path / "market.parquet"
    market.to_parquet(path, index=False)
    monkeypatch.setattr(confirmation, "MARKET", path)
    monkeypatch.setattr(confirmation, "WINDOW_START", pd.Timestamp("2026-01-01T00:00:00Z"))
    monkeypatch.setattr(confirmation, "WINDOW_END", pd.Timestamp("2026-07-01T00:00:00Z"))
    ensemble = pd.DataFrame({
        "pilot_fold": [606, 607], "signal_index": [15, 32],
        "open_time": [market.open_time.iloc[15], market.open_time.iloc[32]],
        "passes_q90": [True, True],
    })
    arm_a, arm_b, population = confirmation.trade_ledgers(ensemble)
    assert arm_a.loc[0, "tau_50"] == arm_b.loc[0, "tau_50"] == 2
    assert arm_a.loc[0, "breakout_side"] == -1
    assert arm_b.loc[0, "breakout_side"] == 1
    assert arm_a.loc[0, "position"] == "long"
    assert arm_b.loc[0, "position"] == "short"
    assert arm_a.loc[0, "gross_bps"] == pytest.approx(10.0)
    assert arm_b.loc[0, "gross_bps"] == pytest.approx(10.0)
    assert arm_a.loc[0, "net_bps"] == pytest.approx(6.0)
    assert arm_b.loc[0, "net_bps"] == pytest.approx(6.0)
    assert arm_a.loc[0, "pnl_usd"] == pytest.approx(0.06)
    assert arm_b.loc[0, "pnl_usd"] == pytest.approx(0.06)
    assert population["realised_trigger_rate"] == 1.0
    assert population["arm_a_down_trigger_rate"] == 0.5
    assert population["arm_b_up_trigger_rate"] == 0.5


def test_clustered_mean_and_separate_arm_verdicts():
    clustered = confirmation.clustered_mean(
        np.array([1.0, 3.0, 2.0, 4.0]), np.array([1, 1, 2, 2]))
    assert clustered["available"]
    assert clustered["mean_net_bps"] == pytest.approx(2.5)
    arm = {"trade_count": 4, "mean_net_bps": 2.5,
           "clustered_mean": {"available": True, "ci95_lower_bps": 0.1}}
    assert confirmation.arm_verdict(arm, 0.3) == "CONFIRMED"
    assert confirmation.arm_verdict(arm, 0.1) == "POPULATION_MISMATCH"
    arm["clustered_mean"]["ci95_lower_bps"] = 0.0
    assert confirmation.arm_verdict(arm, 0.3) == "CONFIRMATION_FAIL"
    assert confirmation.joint_interpretation("CONFIRMED", "CONFIRMED", True) == \
        "BOTH_ARMS_CONFIRMED_WINDOW_EFFECT"
    assert confirmation.joint_interpretation("CONFIRMED", "CONFIRMATION_FAIL", False) == \
        "ARM_A_CONFIRMED_ARM_B_NOT_CONFIRMED"


def test_only_pre_outcome_running_manifest_can_adopt_amendment(monkeypatch, tmp_path):
    monkeypatch.setattr(confirmation, "ROOT", tmp_path)
    old = {"plan_sha256": confirmation.PRE_AMENDMENT_PLAN_SHA256}
    amended = {"plan_sha256": "amended"}
    confirmation.write_json(tmp_path / "manifest.json", old)
    confirmation.write_json(tmp_path / "status.json", {"status": "running"})
    confirmation.adopt_amended_manifest(tmp_path / "manifest.json", amended)
    assert (tmp_path / "manifest_pre_arm_b_amendment.json").exists()
    assert (tmp_path / "manifest.json").read_text(encoding="utf-8").find("amended") > 0


def test_checkpoint_path_never_uses_prior_or_archive_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(confirmation, "ROOT", tmp_path / "confirmation")
    path = confirmation.checkpoint(606, 42)
    assert path.parent == tmp_path / "confirmation"
    assert "_archive_pre_meta" not in str(path)
    assert "patchtst_excursion_range_20260928" not in str(path)


def test_plan_hash_is_frozen_before_fit():
    expected = confirmation.PLAN_HASH.read_text(encoding="utf-8").split()[0]
    assert confirmation.sha256(confirmation.PLAN) == expected
