"""Rolling orchestrator (plan 3 Task 8): validation-only selection, resumable test stage, report on synthetic data."""
import importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd, pytest, torch
from btcusdt_quant.sim import guard
from btcusdt_quant.sim.rolling import Window
from btcusdt_quant.rl import evaluation as E
from btcusdt_quant.rl.models import TemporalActorCritic
from tests.rl.test_vec_env import NO_FUNDING, T0, make_store, market

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("rl_rolling", ROOT / "scripts/rl_rolling.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
DAY = pd.Timedelta(days=1)
WINS = [Window("WA", T0, T0, T0, T0 + DAY, T0 + DAY, T0 + 5 * DAY),       # >= 8 test days: Hansen SPA needs log log t > 0
        Window("WB", T0, T0, T0, T0 + DAY, T0 + 5 * DAY, T0 + 9 * DAY)]


def fake_runs(root, w, state="S1", vals=None, skip=()):
    """20 runs (4 hparams x 5 seeds) with random-init checkpoints and given validation nets."""
    for k, (enc, lr) in enumerate(R.HPARAMS):
        for s in R.SEEDS:
            d = R.run_dir(root, w, state, enc, lr, s)
            if (enc, lr, s) in skip:
                continue
            d.mkdir(parents=True, exist_ok=True)
            torch.manual_seed(100 * k + s)
            m = TemporalActorCritic(4, 3 + 7, enc)
            torch.save({"model_args": m.model_args, "model": m.state_dict()}, d / "best.pt")
            v = (vals or {}).get((enc, lr), [0.0] * 5)[s]
            (d / "manifest.json").write_text(json.dumps({"val_net_bps": v, "reward": "net", "smoke": False}))


def test_select_best_median_validation_and_missing(tmp_path):
    vals = {("conv", 1e-4): [9, 9, -50, -50, -50], ("conv", 3e-4): [1, 2, 3, 4, 5],
            ("gru", 1e-4): [0, 0, 0, 0, 0], ("gru", 3e-4): [3, 3, 3, 100, -50]}
    fake_runs(tmp_path, "WA", vals=vals)
    sel = R.select(tmp_path, "WA", "S1")
    assert (sel["encoder"], sel["lr"], sel["median"]) == ("conv", 3e-4, 3.0)      # median (gru 3e-4 wins on mean/max); tie -> first
    assert len(sel["candidates"]) == 4 and sel["candidates"][3]["val_nets"] == [3, 3, 3, 100, -50]
    fake_runs(tmp_path, "WB", skip={("gru", 3e-4, 4)})
    assert R.select(tmp_path, "WB", "S1") is None
    assert R.missing_runs(tmp_path, "WB", "S1") == [str(R.run_dir(tmp_path, "WB", "S1", "gru", 3e-4, 4))]
    fake_runs(tmp_path, "WC")                                       # all-flat validation: first hparam, recorded
    assert (R.select(tmp_path, "WC", "S1")["encoder"], R.select(tmp_path, "WC", "S1")["lr"]) == ("conv", 1e-4)


def test_test_stage_report_end_to_end(tmp_path):
    store, m = make_store(T0, T0 + 9 * DAY), market(0, days=9, gaps=0)
    for w in WINS:
        fake_runs(tmp_path, w.name, vals={("gru", 1e-4): [5, 5, 5, 5, 5]})
    done = R.stage_test(tmp_path, WINS[:1], ["S1"], lambda s, w: store, m, NO_FUNDING)
    assert done == {"done": ["WA/S1"], "missing": {}}
    acts = pd.read_parquet(R.eval_path(tmp_path, "WA", "S1", "actions"))
    assert {"ensemble", *(f"seed{s}" for s in R.SEEDS), *R.cand_names()} <= set(acts.columns)
    models = [R.load_model(R.run_dir(tmp_path, "WA", "S1", "gru", 1e-4, s) / "best.pt") for s in R.SEEDS]
    ref = E.ensemble_actions(models, store, m, NO_FUNDING, WINS[0].test_start, WINS[0].test_end)
    np.testing.assert_array_equal(acts.ensemble.to_numpy(), ref.to_numpy())
    np.testing.assert_array_equal(acts.ensemble.to_numpy(), acts["cand_gru_0.0001"].to_numpy())
    sel = json.loads(R.eval_path(tmp_path, "WA", "S1", "selection").read_text())
    assert sel["encoder"] == "gru" and "importance" in sel
    # resumable: a finished window is not recomputed; a window with a missing run is skipped and listed
    R.run_dir(tmp_path, "WB", "S1", "conv", 3e-4, 2).joinpath("manifest.json").unlink()
    again = R.stage_test(tmp_path, WINS, ["S1"], lambda s, w: store, m, NO_FUNDING)
    assert again["done"] == ["WA/S1"] and list(again["missing"]) == ["WB/S1"]
    fake_runs(tmp_path, "WB", vals={("gru", 1e-4): [5, 5, 5, 5, 5]})
    assert R.stage_test(tmp_path, WINS, ["S1"], lambda s, w: store, m, NO_FUNDING)["done"] == ["WA/S1", "WB/S1"]
    # supervised and shuffled-control actions (stand-ins for the training stages)
    rng = np.random.default_rng(0)
    for w in WINS:
        idx = pd.read_parquet(R.eval_path(tmp_path, w.name, "S1", "actions")).index
        pd.DataFrame({"supervised": np.zeros(len(idx), np.int8)}, index=idx).to_parquet(
            R.eval_path(tmp_path, w.name, "S1", "supervised"))
        pd.DataFrame({f"seed{s}": rng.choice([-1, 0, 1], len(idx)).astype(np.int8) for s in R.SHUFFLE_SEEDS},
                     index=idx).to_parquet(R.eval_path(tmp_path, w.name, "S1", "shuffled"))
    days = pd.date_range(T0 + DAY, periods=8, freq="D")
    common = {k: pd.Series(rng.normal(0, 50, 8), index=days) for k in ("C1_X", "baseline2", "buy_hold")}
    common["flat"] = pd.Series(0.0, index=days)
    rep = R.build_report(tmp_path, WINS, ["S1"], m, {"S1": store}, common, rng.normal(0, .05, 150), reps=50)
    s1 = rep["states"]["S1"]
    assert set(s1["pass_report"]["criteria"]) == {f"c{k}" for k in range(1, 8)}
    assert s1["pass_report"]["n_trials"] == E.N_TRIALS["net"] == 5297
    assert s1["pass_report"]["criteria"]["c7"]["detail"]["n_null"] == 20
    net = sum(float(E.replay_window(pd.read_parquet(R.eval_path(tmp_path, w.name, "S1", "actions")).ensemble, w,
                                    minutes=m).sum()) for w in WINS)
    assert s1["pass_report"]["criteria"]["c1"]["value"] == pytest.approx(net, abs=1e-9)
    assert s1["random"]["reps"] == 50 and len(s1["per_window"]) == 2 and s1["selection"][0]["encoder"] == "gru"
    assert rep["final"] is True and rep["n_trials_registered"] == 12
    guard.check(rep)
    md = R.render(rep)
    assert "S1" in md and all(f"| c{k} |" in md for k in range(1, 8)) and "WB" in md
    # registry: once, only when final
    reg = tmp_path / "reg.jsonl"
    R.register(rep, reg); R.register(rep, reg)
    rows = [json.loads(x) for x in reg.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["n_trials"] == 12 and rows[0]["experiment"] == R.EXPERIMENT
    assert rows[0]["result_summary"]["S1"]["trial_sharpes_sha256"]
