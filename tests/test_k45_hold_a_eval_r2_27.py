from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from out import k45_funding
from out import run_k45_hold_a_eval_r2_27 as runner
from out import run_k45_gate_direction_r2_10 as r210
from out import run_k45_mtf_tail_r2_20 as r220


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fold_schedule_stop_and_rolling_train():
    first = runner.fold_spec(667)
    last = runner.fold_spec(697)
    assert first["test_start"] == pd.Timestamp("2026-07-01T00:00:00Z")
    assert first["test_end"] == pd.Timestamp("2026-07-04T00:00:00Z")
    assert last["test_start"] == pd.Timestamp("2026-09-29T00:00:00Z")
    assert last["test_end"] == pd.Timestamp("2026-10-01T00:00:00Z")
    assert len(runner.FOLDS) == 31
    for fold in runner.FOLDS:
        spec = runner.fold_spec(fold)
        assert spec["test_start"] - spec["stop_start"] == pd.Timedelta(days=3)
        assert spec["train_end"] - spec["train_start"] == pd.Timedelta(days=180)
    assert runner.REHEARSAL_WINDOW.folds == tuple(range(636, 667))
    assert runner.HOLD_WINDOW.folds == tuple(range(667, 698))
    assert runner.fold_spec(636, runner.REHEARSAL_WINDOW)["test_start"] == pd.Timestamp(
        "2026-03-31T00:00:00Z")


def test_purge_requires_label_end_strictly_before_stop():
    frame = pd.DataFrame({"time": pd.to_datetime([
        "2026-06-27T21:59Z", "2026-06-27T22:00Z", "2026-06-27T22:01Z"
    ])})
    result = runner.purge_before_stop(
        frame, pd.Timestamp("2026-06-28T00:00Z"), "time", 120)
    assert result.time.tolist() == [pd.Timestamp("2026-06-27T21:59Z")]


def test_tail_history_uses_only_previous_fold_scores():
    frame = pd.DataFrame({
        "pilot_fold": [1, 1, 2, 2],
        "decision_time": pd.to_datetime([
            "2025-01-01T00:00Z", "2025-01-01T01:00Z",
            "2025-01-04T00:00Z", "2025-01-04T01:00Z",
        ]),
        "edge_long": [1.0, 3.0, 999.0, -999.0],
        "edge_short": [2.0, 4.0, 888.0, -888.0],
    })
    cutoff = r220.causal_cutoffs(frame, "ROLLING_180D", min_expanding=1)
    fold2 = cutoff.loc[cutoff.pilot_fold.eq(2)]
    assert fold2.history_n.tolist() == [2, 2]
    assert fold2.reference_max_fold.tolist() == [1, 1]
    assert fold2.edge_long_cutoff_q01.nunique() == 1
    assert fold2.edge_long_cutoff_q01.iloc[0] == pytest.approx(np.quantile([1.0, 3.0], .99))


def test_prediction_schema_rejects_realized_label_column():
    columns = list(runner.PREDICTION_COLUMNS["patchtst"])
    valid = pd.DataFrame(columns=columns)
    runner.validate_prediction_schema(valid, "patchtst")
    with pytest.raises(runner.ContractError, match="schema differs"):
        runner.validate_prediction_schema(valid.assign(target=[1.0]), "patchtst")
    bad = valid.rename(columns={"pred_excursion_bps": "excursion_bps"})
    with pytest.raises(runner.ContractError):
        runner.validate_prediction_schema(bad, "patchtst")


def _signals() -> pd.DataFrame:
    return pd.DataFrame({
        "candidate": ["low", "high", "low", "low"],
        "entry_time": pd.to_datetime([
            "2025-01-01T00:00Z", "2025-01-01T00:00Z",
            "2025-01-01T00:30Z", "2025-01-01T01:00Z",
        ]),
        "exit_time": pd.to_datetime([
            "2025-01-01T01:00Z", "2025-01-01T00:45Z",
            "2025-01-01T01:30Z", "2025-01-01T02:00Z",
        ]),
        "side": [1, -1, 1, -1],
        "entry_price": [100.0, 100.0, 101.0, 102.0],
        "exit_price": [101.0, 99.0, 102.0, 101.0],
    })


def test_first_priority_holding_drop_and_exit_equal_entry_is_free():
    accepted, dropped = runner.first_book(_signals(), ["high", "low"], ["high", "low"])
    assert accepted.candidate.tolist() == ["high", "low"]
    assert accepted.entry_time.iloc[1] == accepted.exit_time.iloc[0] + pd.Timedelta(minutes=15)
    assert dropped.reason.value_counts().to_dict() == {"simultaneous": 1, "holding": 1}

    exact_boundary = _signals().iloc[[0, 3]].copy()
    accepted, _ = runner.first_book(exact_boundary, ["low"], ["low"])
    assert accepted.entry_time.iloc[1] == accepted.exit_time.iloc[0]


def test_first_rejects_trade_with_nonpositive_own_holding_time():
    signal = _signals().iloc[[0]].copy()
    signal["exit_time"] = signal.entry_time
    with pytest.raises(runner.ContractError, match="exit_time <= entry_time"):
        runner.first_book(signal, ["low"], ["low"])


def test_classic_carry_in_and_october_first_forced_exit():
    trades = pd.DataFrame({
        "entry_time": pd.to_datetime(["2026-06-30T23:00Z", "2026-09-30T23:00Z"]),
        "exit_time": pd.to_datetime(["2026-07-01T01:00Z", "2026-10-01T03:00Z"]),
        "side": [1, -1], "entry_price": [100.0, 110.0], "exit_price": [101.0, 100.0],
        "gross_bps": [0.0, 0.0],
    })
    result = runner.force_classic_window(trades, 105.0)
    assert result.carry_in.tolist() == [True, False]
    assert result.forced_exit.tolist() == [False, True]
    assert result.exit_time.iloc[1] == runner.HOLD_END
    assert result.exit_price.iloc[1] == 105.0


def test_classic_context_uses_registry_copy_for_duplicate_q3_premium(monkeypatch):
    times = pd.date_range("2026-07-01", periods=2, freq="min", tz="UTC")
    market = pd.DataFrame({"open_time": times, "premium_index": [99.0, 99.0]})
    features = pd.DataFrame({name: ([1.0, 2.0] if name != "open_time" else times)
                             for name in runner.r214.REGISTRY_COLUMNS})
    monkeypatch.setattr(runner.r214, "prepare_bars", lambda frame: {})

    _, merged = runner._classic_context(market, features, pd.DataFrame())

    assert merged.premium_index.tolist() == [1.0, 2.0]
    assert not {"premium_index_x", "premium_index_y"} & set(merged)


def test_model_fold_boundary_discards_equal_and_later_exit():
    times = pd.Series(pd.to_datetime([
        "2026-07-03T21:59Z", "2026-07-03T22:00Z", "2026-07-03T22:01Z"
    ]))
    mask = runner.model_boundary_mask(times, 120, pd.Timestamp("2026-07-04T00:00Z"))
    assert mask.tolist() == [True, False, False]


def test_hold_r20_uses_last_historical_patch_gate_as_strict_prior_bridge():
    source = inspect.getsource(runner._r20_dataset)
    assert 'PATCH_ROOT / "ensemble_predictions.parquet"' in source
    assert "historical_gate.open_time.lt(window.start)" in source
    assert ".tail(1)" in source
    historical = pd.read_parquet(
        runner.PATCH_ROOT / "ensemble_predictions.parquet",
        columns=["pilot_fold", "open_time"])
    bridge = historical.loc[historical.open_time.lt(runner.HOLD_START)].tail(1)
    assert bridge[["pilot_fold", "open_time"]].to_dict("records") == [{
        "pilot_fold": 666,
        "open_time": pd.Timestamp("2026-06-30T23:30:00Z"),
    }]


def test_funding_combine_and_pess_opt_edges(tmp_path: Path):
    old_times = pd.date_range("2020-01-01", periods=7_119, freq="8h", tz="UTC")
    old = pd.DataFrame({"time": old_times, "rate": np.zeros(len(old_times)),
                        "raw_calc_time": old_times})
    q3_times = pd.date_range(old_times[-1] + pd.Timedelta(hours=8), periods=276, freq="8h", tz="UTC")
    q3_times = q3_times.to_series(index=range(len(q3_times)))
    q3_times.iloc[0] += pd.Timedelta(milliseconds=7)
    q3 = pd.DataFrame({"funding_time": q3_times, "funding_rate": np.full(276, .001)})
    path = tmp_path / "funding.parquet"
    q3.to_parquet(path, index=False)
    combined = runner.combine_funding(old, path)
    assert len(combined) == 7_395
    assert not combined.time.duplicated().any()
    assert combined.time.iloc[len(old)] == old_times[-1] + pd.Timedelta(hours=8)
    assert combined.raw_calc_time.iloc[len(old)] == q3_times.iloc[0]

    event = pd.DataFrame({"time": pd.to_datetime(["2026-07-01T08:00Z"]), "rate": [.001]})
    entry = exit_ = pd.Timestamp("2026-07-01T08:00Z")
    assert k45_funding.trade_funding(1, entry, exit_, event, "PESS") == (0.0, -10.0)
    assert k45_funding.trade_funding(1, entry, exit_, event, "OPT") == (0.0, 0.0)
    assert k45_funding.trade_funding(-1, entry, exit_, event, "PESS") == (0.0, 0.0)
    assert k45_funding.trade_funding(-1, entry, exit_, event, "OPT") == (0.0, 10.0)


def test_hypothesis_zero_boundary_and_unmeasurable():
    assert runner.hypothesis_truth(0.0) is False
    assert runner.hypothesis_truth(1.0, None) is None
    assert runner.hypothesis_truth(1.0, np.nan) is None
    assert runner.hypothesis_truth(np.inf, 0.0) is None
    assert runner.hypothesis_verdict(False, False) == "REJECTED"
    assert runner.hypothesis_verdict(True, False) == "BOUNDARY_DEPENDENT"
    assert runner.hypothesis_verdict(True, True) == "CONFIRMED"
    assert runner.hypothesis_verdict(None, True) == "UNMEASURABLE"
    assert runner.daily_sharpe(np.zeros(92)) is None


def test_h_a4_nonfinite_comparator_is_unmeasurable():
    rows = []
    for book in ("H1", "H2", "H3", "H4", "H5"):
        for boundary in runner.BOUNDARIES:
            rows.append({"book": book, "boundary": boundary, "cost_bps": 4.0,
                         "fold": np.nan, "total_net_bps": 1.0,
                         "mtm_daily_sharpe": np.nan if book == "H1" else 1.0})
    verdicts = {row["hypothesis"]: row for row in runner._hypotheses(pd.DataFrame(rows))}
    assert verdicts["H-A4"] == {
        "hypothesis": "H-A4", "PESS": None, "OPT": None, "verdict": "UNMEASURABLE"}


def test_fold_rows_count_actual_carry_in_and_forced_exit():
    window = runner.EvaluationWindow(
        "TEST", pd.Timestamp("2025-01-02T00:00Z"), pd.Timestamp("2025-01-05T00:00Z"),
        pd.Timestamp("2025-01-02T00:00Z"), 1, pd.Timestamp("2025-01-02T00:00Z"), 1)
    stamps = pd.date_range("2025-01-01T23:59Z", "2025-01-05T00:00Z", freq="min")
    market = pd.DataFrame({"open_time": stamps, "close": np.linspace(100.0, 101.0, len(stamps))})
    trade = pd.DataFrame({
        "entry_time": [stamps[0]], "exit_time": [stamps[-1]], "side": [1],
        "entry_price": [100.0], "exit_price": [101.0],
        "carry_in": [True], "forced_exit": [True],
    })
    funding = pd.DataFrame({"time": pd.DatetimeIndex([], tz="UTC"), "rate": []})
    metrics, _, _ = runner._evaluate_books(window, {"H1": trade}, market, funding)
    folds = metrics.loc[metrics.fold.notna()]
    assert folds.carry_in_n.eq(1).all()
    assert folds.forced_exit_n.eq(1).all()


def test_evaluation_report_has_numeric_tables_before_mechanical_verdicts():
    table = pd.DataFrame({"n": [1]})
    names = ("summary", "historical", "monthly", "concentration", "pw", "random",
             "stages", "blocking", "boundary", "parity", "fold_net", "direction",
             "holding", "fold_audit", "feature_sets", "tail_history", "technical_history")
    report = runner._render_evaluation_report(
        runner.REHEARSAL_WINDOW, {name: table for name in names},
        [{"hypothesis": "H-A1", "verdict": "REJECTED"}])
    assert report.index("## numeric candidate grid") < report.index("## hypothesis verdicts mechanical")
    for heading in ("matched random 1000", "signal gate tail fold boundary stages",
                    "daily trade ledger parity", "DEV_COMMON HOLD_B side by side",
                    "technical failures and reruns"):
        assert f"## {heading}" in report


def test_current_metric_labels_distinguish_hold_a_from_rehearsal():
    current = pd.DataFrame({
        "book": ["H1"], "boundary": ["PESS"], "cost_bps": [4.0],
        "trade_n": [1], "exposure_ratio": [.5], "total_net_bps": [2.0],
        "net_per_trade_bps": [2.0],
    })
    hold = runner._label_current_metrics(current, "HOLD_A")
    rehearsal = runner._label_current_metrics(current, "REHEARSAL")
    assert "HOLD_A_net_bps" in hold and "REHEARSAL_net_bps" not in hold
    assert "REHEARSAL_net_bps" in rehearsal and "HOLD_A_net_bps" not in rehearsal


def _contract_files(tmp_path: Path, state: str = "FROZEN"):
    runner_path = tmp_path / "runner.py"
    test_path = tmp_path / "test.py"
    manifest_path = tmp_path / "manifest.json"
    runner_path.write_text("runner", encoding="utf-8")
    test_path.write_text("test", encoding="utf-8")
    manifest_path.write_text("{}", encoding="utf-8")
    freeze = tmp_path / "freeze.md"
    freeze.write_text(
        f"상태: **{state}**\n"
        f"전용 평가 러너 SHA256: `{_sha(runner_path)}`\n"
        f"전용 테스트 SHA256 및 통과 명령: `{_sha(test_path)}` pytest\n"
        f"입력/환경 manifest SHA256: `{_sha(manifest_path)}`\n",
        encoding="utf-8",
    )
    return freeze, runner_path, test_path, manifest_path


def test_predict_evaluate_guard_rejects_draft(tmp_path: Path):
    paths = _contract_files(tmp_path, "DRAFT")
    with pytest.raises(runner.ContractError, match="not FROZEN"):
        runner.guard_frozen_contract(*paths)
    bypass = runner.guard_frozen_contract(*paths, allow_draft_user_2026_10_05=True)
    assert bypass["freeze_status"] == "DRAFT"
    assert bypass["freeze_guard_bypassed"] is True
    assert bypass["freeze_guard_bypass_reason"] == "user decision 2026-10-05"


def test_predict_evaluate_guard_rejects_sha_mismatch(tmp_path: Path):
    freeze, runner_path, test_path, manifest_path = _contract_files(tmp_path)
    runner_path.write_text("changed", encoding="utf-8")
    with pytest.raises(runner.ContractError, match="SHA256 mismatch"):
        runner.guard_frozen_contract(freeze, runner_path, test_path, manifest_path)


def test_execution_ready_guard_rejects_documented_blocker(tmp_path: Path):
    manifest = tmp_path / "input_environment_manifest.json"
    runner.write_json(manifest, {"execution_ready": False, "blockers": ["exact parity"]})
    with pytest.raises(runner.DecisionRequiredError, match="exact parity"):
        runner.guard_execution_ready(manifest)
    runner.write_json(manifest, {"execution_ready": True, "blockers": []})
    runner.guard_execution_ready(manifest)


def test_closed_prediction_manifest_sha_guard(tmp_path: Path):
    output = tmp_path / "fold.parquet"
    pd.DataFrame({"x": [1]}).to_parquet(output, index=False)
    manifest = tmp_path / "predictions_manifest.json"
    runner.write_json(manifest, {"status": "CLOSED", "folds": list(runner.FOLDS),
                                 "outputs": [{"path": str(output), "sha256": _sha(output)}]})
    (tmp_path / "predictions_manifest.sha256").write_text(_sha(manifest), encoding="ascii")
    runner.verify_closed_prediction_manifest(tmp_path)
    output.write_bytes(b"changed")
    with pytest.raises(runner.ContractError, match="output SHA256 mismatch"):
        runner.verify_closed_prediction_manifest(tmp_path)


def test_source_exact_runtime_settings():
    runner.configure_determinism()
    assert runner.patch_forecast.DEVICE.type == "cuda"
    assert runner._catboost_params({"thread_count": 8})["thread_count"] == -1


def test_cuda_absence_is_contract_error(monkeypatch):
    monkeypatch.setattr(runner.torch.cuda, "is_available", lambda: False)
    with pytest.raises(runner.ContractError, match="CUDA"):
        runner.configure_determinism()


def test_environment_records_device_cuda_and_cudnn():
    runner.configure_determinism()
    record = runner.environment_record()
    assert record["device"] == "cuda"
    assert record["cuda_available"] is True
    assert record["device_name"]
    assert record["cuda_version"]
    assert record["cudnn_version"]


def test_predict_has_no_deliberate_mid_fold_abort_and_uses_staging():
    source = inspect.getsource(runner.predict_window)
    assert "DecisionRequiredError" not in source
    assert 'root / ".staging"' in source
    assert source.index("preflight(") < source.index("_load_combined_inputs(")
    assert source.index("source.replace(target)") < source.index('"status": "CLOSED"')


def test_hold_and_rehearsal_share_predict_evaluate_functions(monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "predict_window", lambda window, root: calls.append(("predict", window)))
    monkeypatch.setattr(runner, "evaluate_window", lambda window, root: calls.append(("evaluate", window)) or {})
    monkeypatch.setattr(runner, "rehearsal_exact", lambda root, result:
                        pd.DataFrame({"exact": [True]}))
    monkeypatch.setattr(runner, "write_completion_artifacts", lambda exact: None)
    runner.run_predict()
    runner.run_evaluate()
    runner.run_rehearse()
    assert calls == [("predict", runner.HOLD_WINDOW), ("evaluate", runner.HOLD_WINDOW),
                     ("predict", runner.REHEARSAL_WINDOW),
                     ("evaluate", runner.REHEARSAL_WINDOW)]


def test_q3_micro_join_has_exact_frozen_universe():
    names = {f"m_{name}" for path in runner.Q3_MICRO
             for name in runner.pq.read_schema(path).names if name != "open_time"}
    assert len(names) == 17
    assert {runner.pq.ParquetFile(path).metadata.num_rows for path in runner.Q3_MICRO} == {132_480}
    runner._q3_schema_preflight()


def test_bookticker_features_are_permanently_excluded_from_r29_candidates():
    columns = ["f_x", "m_book_depth_total", *runner.BOOKTICKER_EXCLUDED_FEATURES]
    candidates = runner.r29_feature_candidates(pd.DataFrame(columns=columns))
    assert candidates == ["f_x", "m_book_depth_total"]
    assert runner.BOOKTICKER_EXCLUDED_FEATURES.isdisjoint(candidates)
    original = r210.feature_candidates(columns)
    filtered = r210.feature_candidates(columns, runner.BOOKTICKER_EXCLUDED_FEATURES)
    assert set(runner.BOOKTICKER_EXCLUDED_FEATURES).issubset(original)
    assert runner.BOOKTICKER_EXCLUDED_FEATURES.isdisjoint(filtered)


def _input_manifest(tmp_path: Path, monkeypatch, **override):
    import json
    monkeypatch.setattr(runner, "environment_record", lambda: {"device": "cuda"})
    monkeypatch.setattr(runner, "dependency_hashes", lambda: {"out/k45_ledger.py": "a" * 64})
    source = tmp_path / "input.bin"
    source.write_bytes(b"x")
    payload = {"inputs": {source.as_posix(): hashlib.sha256(b"x").hexdigest()},
               "environment": {"device": "cuda"},
               "dependency_sources": {"out/k45_ledger.py": "a" * 64}}
    payload.update(override)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_input_manifest_accepts_exact_match(tmp_path: Path, monkeypatch):
    runner.verify_input_manifest_hashes(_input_manifest(tmp_path, monkeypatch))


@pytest.mark.parametrize("override, message", [
    ({"inputs": {"missing.parquet": "b" * 64}}, "missing"),
    ({"environment": {"device": "cpu"}}, "environment"),
    ({"dependency_sources": {"out/k45_ledger.py": "c" * 64}}, "dependency"),
])
def test_input_manifest_rejects_missing_env_or_dependency_drift(tmp_path: Path, monkeypatch,
                                                                 override, message):
    with pytest.raises(runner.ContractError, match=message):
        runner.verify_input_manifest_hashes(_input_manifest(tmp_path, monkeypatch, **override))


def test_dependency_hashes_cover_imported_rule_sources():
    hashes = runner.dependency_hashes()
    for name in ("out/k45_funding.py", "out/k45_ledger.py", "out/run_k45_classic_rules_r2_14.py",
                 "out/run_k45_single_book_combo_r2_24.py", "out/run_patchtst_excursion_range.py"):
        assert name in hashes
    assert "out/run_k45_hold_a_eval_r2_27.py" not in hashes
