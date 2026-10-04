import pandas as pd
import pytest

from out import run_k45_validation_r2_19 as R


def test_audit_funding_flags_mismatch_and_missing():
    t = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 08:00", "2024-01-01 16:00"], utc=True)
    ours = pd.DataFrame({"time": t[:2], "rate": [0.0001, 0.0002]})
    arch = pd.DataFrame({"time": t, "rate": [0.0001, 0.0003, 0.0001]})
    out = R.audit_funding(ours, arch)
    assert out.set_index("time").loc[t[0], "match"]
    assert not out.set_index("time").loc[t[1], "match"]
    assert out.set_index("time").loc[t[2], "only_in"] == "archive"


def test_ls_feature_uses_only_past_create_time():
    create = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:05"], utc=True)
    decision = pd.Timestamp("2024-01-01 00:05", tz="UTC")
    used = R.asof_value_time(create, decision)
    assert used == create[0]


def test_ls_audit_allows_storage_precision_and_stale_fallback():
    metrics = pd.DataFrame({"create_time": pd.to_datetime(["2024-01-01 00:00"], utc=True),
                            "global_ls_account": [1.23456789]})
    registry = pd.DataFrame({
        "open_time": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:41"], utc=True),
        "global_ls_account": [1.2345679, 0.0]})
    out = R.audit_ls_asof(registry, metrics)
    assert out["value_mismatches"] == 0
    assert out["stale_fallback_rows"] == 1


def test_reproduction_matches_r2_14_for_e1():
    rep = R.reproduce(["E1|1h|3|signal|L"])
    row = rep.set_index(["cell_id", "segment"]).loc[("E1|1h|3|signal|L", "DEV")]
    assert row.n_new == row.n_r214
    manifest = R.R214_ALL_CELLS.parent / "manifest.json"
    corrected = "archive calc_time normalized" in manifest.read_text(encoding="utf-8")
    assert abs(row.net_new - row.net_r214) < 1e-6 if corrected else row.net_new != row.net_r214


def test_matched_random_keeps_hold_distribution():
    holds = pd.Series([60, 120, 1200], dtype=float)
    draws = R.matched_random_holds(holds, n_draws=5, seed=7)
    for d in draws:
        assert sorted(d) == sorted(holds.tolist())


def test_e1_breakout_excludes_current_bar():
    bars = R.toy_bars_for_e1()          # 21봉, 마지막 봉 high가 신고가지만 close는 직전 20봉 고가 아래
    assert R.e1_entries(bars, zcut=0.0)[-1] == 0
