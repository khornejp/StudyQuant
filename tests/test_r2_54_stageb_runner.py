"""R2-54 Task 4 runner (out/run_r2_54_stageb.py): one-shot unlock refusals and the 2026 snapshot merge, offline."""
import importlib.util, json, sys
from pathlib import Path

import numpy as np, pandas as pd, pytest

from btcusdt_quant.sim import data

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r2_54_stageb_runner", ROOT / "out/run_r2_54_stageb.py")
run = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = run; SPEC.loader.exec_module(run)
utc = lambda s: pd.Timestamp(s, tz="UTC")


def test_unlock_refuses_without_every_recorded_hash_and_the_confirmation():
    problems = run.unlock_preconditions({}, None)
    for text in ("freeze hash", "snapshot hash", "selection trace", "no side passed", "registry", "confirmation"):
        assert any(text in p for p in problems), text
    assert not any("unlocked" in p for p in run.unlock_preconditions({"test_runs": [{"run_id": 1}]}, run.CONFIRM))
    m = {"opened_sides": ["long"], "final_fit": {"long": {"checkpoint": {"path": "missing.bin", "sha256": "0"}}}}
    assert any("long final checkpoint" in p for p in run.unlock_preconditions(m, run.CONFIRM))
    assert not any("confirmation" in p for p in run.unlock_preconditions(m, run.CONFIRM))


def test_unlock_command_refuses_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "OUT", tmp_path)
    with pytest.raises(SystemExit, match="refused"):
        run.unlock(type("A", (), {"confirm": run.CONFIRM})())
    (tmp_path / "manifest.json").write_text(json.dumps({"opened_sides": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="refused"):
        run.unlock(type("A", (), {"confirm": None})())
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == {"opened_sides": []}


def _minutes(start, n):
    t = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    p = np.full(n, 100.0)
    return pd.DataFrame({"open_time": t, "open": p, "high": p, "low": p, "close": p, "volume": 1.0, "quote_volume": 1.0,
                         "number_of_trades": 1, "taker_buy_base_volume": .5})


def test_snapshot_merge_keeps_2026_rows_and_rounds_settlements():
    end = utc("2026-01-03")
    pre_m = _minutes(utc("2025-12-30"), 2 * 1440)
    snap_m = _minutes(utc("2026-01-01"), 2 * 1440)
    stamp = lambda ts: pd.DatetimeIndex(ts)
    pre_metrics = pd.DataFrame({"available_time": stamp([utc("2025-12-31 23:55"), utc("2026-01-01 00:00")]),
                                "global_ls": [1.0, 1.1], "top_ls": 1.0, "oi": 1.0, "oi_value": 1.0, "taker_lsr": 1.0})
    tm = pd.DataFrame({"available_time": stamp([utc("2026-01-01 00:00"), utc("2026-01-01 00:05")]),
                       "global_ls": [1.2, 1.3], "top_ls": 1.0, "oi": 1.0, "oi_value": 1.0, "taker_lsr": 1.0})
    pre_premium = pd.DataFrame({"available_time": stamp([utc("2025-12-31 23:59")]), "premium": [1e-4]})
    tp = pd.DataFrame({"available_time": stamp([utc("2026-01-01 00:01")]), "premium": [2e-4]})
    settle = pd.DataFrame({"time": stamp([utc("2025-12-31 16:00"), utc("2026-01-01")]), "rate": [1e-4, 9e-4],
                           "raw_calc_time": stamp([utc("2025-12-31 16:00"), utc("2026-01-01")])})
    events = pd.DataFrame({"funding_time": ["2026-01-01T00:00:00.008000+00:00", "2026-01-01T08:00:00+00:00"],
                           "funding_rate": [2e-4, 3e-4]})
    live = pd.DataFrame({"time": ["2026-01-01T08:00:00+00:00", "2026-01-01T16:00:00.003000+00:00"], "rate": [3e-4, 4e-4]})
    fmi = pd.DataFrame({"publish_time": stamp([utc("2026-01-01 00:00:00.008"), utc("2026-01-01 08:00")]),
                        "rate": [2e-4, 3e-4], "interval_hours": [8.0, np.nan], "interval_missing": [0, 1]})
    stamps = pd.date_range(utc("2025-12-30"), utc("2026-01-01"), freq="15min", tz="UTC", inclusive="left")
    targets = {f"prediction_{k}": 50.0 for k in data.TARGETS}
    pre_p = pd.DataFrame({"timestamp": stamps, "retrain_time": stamps[0], "segment": "DEV_BACK", **targets})
    s2 = pd.date_range(utc("2026-01-01"), end, freq="15min", tz="UTC", inclusive="left")
    sa = pd.DataFrame({"prediction_ts": s2, "retrain_time": s2[0], "model_id": "m", "logical_available_at": s2,
                       "written_at": utc("2026-10-09"), "source": "r2_54_stage_a_2026", **targets})
    snap = {"market_1m": snap_m, "technique_metrics": tm, "technique_premium": tp, "funding_events": events,
            "funding_live_table": live, "funding_model_input": fmi, "stage_a_2026": sa}
    ctx, funding, ledger = run.combine_context(pre_m, pre_metrics, pre_premium, settle, pre_p, snap, end)
    assert ctx.minutes.open_time.iloc[-1] == end - pd.Timedelta(minutes=1) and len(ctx.minutes) == 4 * 1440
    assert ctx.metrics.global_ls.tolist() == [1.0, 1.2, 1.3]                 # snapshot wins on a shared time
    assert ledger.time.tolist() == [utc("2025-12-31 16:00"), utc("2026-01-01 00:00:00.008"), utc("2026-01-01 08:00"),
                                    utc("2026-01-01 16:00:00.003")]          # actual fundingTime, 2026 from the snapshot
    assert ctx.funding.time.tolist() == [utc("2025-12-31 16:00"), utc("2026-01-01"), utc("2026-01-01 08:00"),
                                         utc("2026-01-01 16:00")]            # technique inputs: sim minute buckets
    assert ledger.rate.tolist() == [1e-4, 2e-4, 3e-4, 4e-4]
    assert funding.interval_missing.tolist() == [0, 0, 1] and np.isnan(funding.interval_hours.iloc[-1])
    assert funding.rate.tolist() == [1e-4, 2e-4, 3e-4]                      # pre-2026 settle row at 2026-01-01 dropped
    assert (ctx.regime.timestamp.diff().dropna() == pd.Timedelta("15min")).all() and "M" in ctx.regime
    with pytest.raises(RuntimeError):
        run.combine_context(pre_m, pre_metrics, pre_premium, settle, pre_p, {**snap, "market_1m": snap_m.iloc[:-1]}, end)


def test_unlock_refuses_when_code_differs_from_the_frozen_manifest():
    assert any("code hashes" in p for p in run.unlock_preconditions({"code_sha256": {"x": "0"}}, run.CONFIRM))
    assert not any("code hashes" in p for p in run.unlock_preconditions({"code_sha256": run.code_hashes()}, run.CONFIRM))


@pytest.mark.parametrize("stage", ["snapshot", "refit"])
def test_snapshot_and_refit_checks_refuse_before_the_one_shot_flag(tmp_path, monkeypatch, stage):
    monkeypatch.setattr(run, "OUT", tmp_path)
    m = {"opened_sides": ["long"], "test_runs": []}
    (tmp_path / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    monkeypatch.setattr(run, "unlock_preconditions", lambda m, c: [])
    calls = []

    def snapshot(read_frames=False):
        calls.append(read_frames)
        if stage == "snapshot":
            raise SystemExit("snapshot manifest sha256 changed")
        return {}
    monkeypatch.setattr(run, "verify_snapshot", snapshot)
    monkeypatch.setattr(run, "refit_check", lambda m: {"long": {"equal": False}})
    monkeypatch.setattr(run, "test_context", lambda: pytest.fail("2026 data read before the checks"))
    with pytest.raises(SystemExit):
        run.unlock(type("A", (), {"confirm": run.CONFIRM})())
    assert calls == [False]                                   # only the bytes-only check ran
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == m   # no one-shot flag recorded


def test_rest_taker_swap_and_trade_comparison():
    t = pd.DatetimeIndex([utc("2026-09-30 23:55"), utc("2026-10-01 00:05"), utc("2026-10-01 00:10")])
    metrics = pd.DataFrame({"available_time": t, "taker_lsr": [1.0, 1.1, 1.2]})
    rest = pd.DataFrame({"create_time": ["2026-10-01T00:00:00+00:00"], "buy_sell_ratio": [2.0]})
    out = run.rest_taker_metrics(metrics, rest, utc("2026-10-01"), utc("2026-10-08"))
    assert out.taker_lsr.tolist()[:2] == [1.0, 2.0] and np.isnan(out.taker_lsr.iloc[2])   # no REST row: missing
    a = pd.DataFrame({"position_id": [1, 2], "entry_time": [utc("2026-10-01 01:01"), utc("2026-10-02")],
                      "exit_time": [utc("2026-10-01 05:00"), utc("2026-10-02 03:00")], "net_bps": [5.0, -1.0]})
    r = pd.DataFrame({"position_id": [1, 2], "entry_time": [utc("2026-10-01 01:01"), utc("2026-10-03")],
                      "exit_time": [utc("2026-10-01 06:00"), utc("2026-10-03 01:00")], "net_bps": [4.0, 2.0]})
    c = run.compare_trades(a, r)
    assert c["matched_entry_times"] == 1 and c["only_archive_entry_times"] == [str(utc("2026-10-02"))]
    assert c["only_rest_entry_times"] == [str(utc("2026-10-03"))] and len(c["matched_with_different_exit"]) == 1


def test_test_runs_are_appended_and_counted(tmp_path):
    log = tmp_path / "test_runs.jsonl"
    a = run.append_run(log, {"code": "x", "result": {"long": 1}})
    b = run.append_run(log, {"code": "y", "result": {"long": 2}})
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert (a["run_id"], b["run_id"]) == (1, 2) and [r["run_id"] for r in rows] == [1, 2]
    assert rows[0]["result"] == {"long": 1} and "utc" in rows[1]


def test_snapshot_freeze_chain_through_a4():
    assert run.SNAPSHOT_FREEZE_SHA == run.sb.amendment("A4")["freeze_sha256_before"]
