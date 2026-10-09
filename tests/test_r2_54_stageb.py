"""R2-54 Task 4 Stage-B (freeze out/k45_rl_r2_48_20261007/r2_54_stageb_freeze.json): causality, purge/embargo,
label isolation, ranking tie-break, position rule and core-ledger reuse parity. Synthetic data only."""
import importlib.util, json, math, sys
from pathlib import Path

import numpy as np, pandas as pd, pytest

from btcusdt_quant import stageb as sb
from btcusdt_quant.sim import reference, schema
from tests.rl.test_state import synthetic_ctx

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ax_runner_sb", ROOT / "scripts/sim_adaptive_exit.py")
ax = importlib.util.module_from_spec(spec); spec.loader.exec_module(ax)
T0 = pd.Timestamp("2024-01-01", tz="UTC")
M = pd.Timedelta(minutes=1)


def utc(text):
    return pd.Timestamp(text, tz="UTC")


# ---------------------------------------------------------------- freeze constants
def test_constants_match_the_freeze_verbatim():
    f = sb.freeze()
    assert list(sb.HORIZONS) == f["labels"]["horizons"]
    assert list(sb.VIEWS) == f["inputs"]["selectable_views"] == f["selection"]["structural_grid"]["views"]
    assert list(sb.K_VALUES) == f["position_rule"]["k_policy"]["candidates"]
    assert len(sb.folds()) == 10 and sb.folds()[0] == (utc("2023-06-01"), utc("2023-09-01"))
    assert sb.folds()[-1] == (utc("2025-09-01"), utc("2025-12-01"))
    assert sb.n_trials() == {"selectable": 120, "robustness": 7, "new_trials": 127, "registry_base": 5417,
                             "registry_after": 5544}
    assert sb.CATBOOST_PARAMS == {"loss_function": "RMSE", "depth": 4, "iterations": 500, "learning_rate": 0.03,
                                  "l2_leaf_reg": 10, "random_seed": 42}


# ---------------------------------------------------------------- labels, purge, embargo, N_eff
def ramp(n, start=T0):
    t = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    o = 100 * np.exp(np.arange(n) * 1e-4)
    return pd.DataFrame({"open_time": t, "open": o, "high": o, "low": o, "close": o})


def test_label_is_gross_log_bps_from_open_t_plus_1m_to_open_t_plus_1m_plus_h():
    m = ramp(1460)                                                # T=30 exits at minute 1471: beyond the data
    times = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=15 * j) for j in range(3)])
    lab = sb.make_labels(m, times)
    o = m.set_index("open_time").open
    for t in times[:2]:
        row = lab.loc[lab.decision_time == t].iloc[0]
        assert row.g_30m == pytest.approx(1e4 * math.log(o[t + M + pd.Timedelta("30min")] / o[t + M]))
        assert row.exit_24h == t + M + pd.Timedelta("24h")
    assert np.isnan(lab.g_24h.iloc[-1])                          # exit beyond the data: unavailable, not filled
    assert set(lab.columns) == {"decision_time"} | {f"{p}_{h}" for p in ("g", "exit") for h in sb.HORIZONS}


def test_missing_minute_inside_the_data_invalidates_the_run():
    m = ramp(3000).drop(index=100).reset_index(drop=True)
    with pytest.raises(ValueError, match="missing 1-minute price"):
        sb.make_labels(m, pd.DatetimeIndex([T0 + pd.Timedelta(minutes=60)]))


def test_purge_keeps_a_training_sample_only_when_its_label_exits_before_the_boundary():
    b = utc("2023-06-01")
    times = pd.date_range(b - pd.Timedelta("3h"), b, freq="15min", tz="UTC", inclusive="left")
    keep = sb.train_mask(times, 60, b)
    exit_ = times + M + pd.Timedelta("60min")
    assert (keep == (exit_ < b)).all() and keep.any() and not keep.all()
    assert times[keep].max() == b - pd.Timedelta("75min")       # T+1m+60m < B


def test_embargo_drops_the_first_24h_after_every_validation_and_test_boundary():
    times = pd.date_range(utc("2023-08-30"), utc("2023-09-04"), freq="15min", tz="UTC", inclusive="left")
    keep = sb.train_mask(times, 30, utc("2023-09-04"))
    b = utc("2023-09-01")                                         # fold 1 end == fold 2 start
    assert not keep[(times >= b) & (times < b + pd.Timedelta("24h"))].any()
    assert keep[(times >= b + pd.Timedelta("24h")) & (times < utc("2023-09-03"))].all()
    assert utc("2026-01-01") in sb.boundaries() and utc("2025-12-01") in sb.boundaries()


def test_block_membership_needs_entry_after_embargo_and_label_exit_inside_the_block():
    a, b = sb.folds()[0]
    times = pd.date_range(a - pd.Timedelta("1d"), b + pd.Timedelta("1d"), freq="15min", tz="UTC", inclusive="left")
    keep = sb.block_mask(times, 240, a, b)
    assert times[keep].min() == a + pd.Timedelta("24h")
    assert (times[keep] + M + pd.Timedelta("240min") < b).all()
    assert times[keep].max() == b - pd.Timedelta("255min")


def test_n_eff_is_sum_over_contiguous_blocks_of_floor_n_over_q():
    t = pd.date_range(T0, periods=100, freq="15min", tz="UTC")
    mask = np.ones(100, bool); mask[40:45] = False               # blocks of 40 and 55 rows
    assert sb.n_eff(t, mask, 60) == 40 // 4 + 55 // 4
    assert sb.n_eff(t, mask, 1440) == 0 and sb.n_eff(t, mask, 30) == 20 + 27


# ---------------------------------------------------------------- features: causality and isolation
@pytest.fixture(scope="module")
def ctx():
    return synthetic_ctx()


START, END = T0 + pd.Timedelta(days=8), T0 + pd.Timedelta(days=12)


@pytest.fixture(scope="module")
def feats(ctx):
    return sb.build_features(ctx, START, END, sb.funding_frame(ctx.funding))


def test_feature_views_groups_and_technique_ids(feats):
    groups = set(feats.groups.values())
    assert groups == {"V1", "V2", "V3", "V4"}
    v5, v6 = sb.view_columns(feats, "V5_continuous"), sb.view_columns(feats, "V6_full")
    assert set(v6) - set(v5) == {c for c, g in feats.groups.items() if g == "V4"}
    ids = set(feats.tech.values())
    assert {"B1", "B2", "B3", "K01", "K10", "K14", "K30"} <= ids and "K01_FLIP" not in ids
    assert {i for g in sb.REMOVAL_GROUPS.values() for i in g} == ids          # every id in exactly one group
    assert sum(len(g) for g in sb.REMOVAL_GROUPS.values()) == len(ids)
    for name in ("v3_pred_exc_4h", "v3_M", "v3_L", "v3_age", "v3_missing", "v2_taker_lsr", "v2_taker_lsr_missing",
                 "v2_funding_interval_h", "v2_funding_missing", "v1_1h_rsi14", "v1_seq1m_14_ret_bps",
                 "v4_K01_event_side", "v4_K06_k0.5_proposal_active", "v4_K10_proposal_active"):
        assert name in feats.frame
    assert not [c for c in feats.frame if c.startswith(("g_", "exit_"))]


def test_no_feature_row_uses_data_available_after_t(feats):
    t = sb.ns(feats.frame.decision_time)
    assert (feats.avail <= t).all() and (feats.avail > np.iinfo(np.int64).min).any()
    sb.assert_causal(feats)
    bad = sb.Features(feats.frame, feats.groups, feats.tech, feats.avail.copy())
    bad.avail[5] = t[5] + 1
    with pytest.raises(ValueError, match="logical_available_at > T"):
        sb.assert_causal(bad)


@pytest.mark.parametrize("cut", [START + pd.Timedelta(x) for x in ("13h", "1d 2h 45min", "2d 23h 15min")])
def test_features_built_on_a_truncated_context_equal_the_full_build_before_the_cut(ctx, feats, cut):
    part = sb.build_features(ctx.truncate(cut), START, END, sb.funding_frame(ctx.truncate(cut).funding))
    rows = int((feats.frame.decision_time < cut).sum())
    assert list(part.frame.columns) == list(feats.frame.columns)
    pd.testing.assert_frame_equal(part.frame.iloc[:rows], feats.frame.iloc[:rows])


def test_feature_and_label_artifacts_are_isolated(ctx, feats):
    lab = sb.make_labels(ctx.minutes, pd.DatetimeIndex(feats.frame.decision_time))
    sb.assert_isolated(feats.frame, lab)
    with pytest.raises(ValueError, match="target column"):
        sb.assert_isolated(feats.frame.assign(g_1h=lab.g_1h.to_numpy()), lab)
    with pytest.raises(ValueError, match="target column"):
        sb.assert_isolated(feats.frame.assign(leak=lab.g_4h.to_numpy()), lab)   # a copied label is caught by value


def test_scaling_and_imputation_use_train_rows_only():
    x = np.array([[1.0], [3.0], [np.nan], [1000.0]])
    y = np.array([0.0, 1.0, 0.5, 9.0])
    model = sb.fit_model("ridge_1", x[:3], y[:3], ["a"])
    assert model.state["mean"][0] == pytest.approx(2.0) and model.state["std"][0] == pytest.approx(1.0)
    z = sb.fit_model("ridge_1", x, y, ["a"])
    assert z.state["mean"][0] != pytest.approx(2.0)
    assert np.isfinite(sb.predict(model, x)).all()                # NaN imputed at the train mean (z = 0)


def test_models_are_deterministic_and_checkpoint_hash_stable():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(400, 5)).astype(np.float32); x[::7, 2] = np.nan
    y = x[:, 0] * 3 + rng.normal(size=400)
    for name in sb.MODELS:
        a, b = sb.fit_model(name, x, y, list("abcde")), sb.fit_model(name, x, y, list("abcde"))
        np.testing.assert_array_equal(sb.predict(a, x), sb.predict(b, x))
        assert sb.checkpoint_sha256(a) == sb.checkpoint_sha256(b)
        c = sb.load_checkpoint(sb.checkpoint_bytes(a))
        np.testing.assert_array_equal(sb.predict(c, x), sb.predict(a, x))
    with pytest.raises(ValueError):
        sb.fit_model("ridge_5", x, y, list("abcde"))


# ---------------------------------------------------------------- position rule and ledger reuse
def flat(n, price=100.0):
    t = pd.date_range(T0, periods=n, freq="1min", tz="UTC")
    p = np.full(n, price)
    return pd.DataFrame({"open_time": t, "open": p, "high": p, "low": p, "close": p})


def test_position_rule_entry_threshold_exit_and_short_mirror():
    times = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=15 * j) for j in range(6)])
    yhat = np.array([4.0, 4.5, 2.0, 0.0, -4.5, np.nan])
    e0 = np.array([50.0, 50.0, 50.0, np.nan, 50.0, 50.0])
    long = sb.signal_table(times, yhat, 1, e0, 1.5)
    assert long.side.tolist() == [0, 1, 0, 0, 0, 0]               # yhat-4 > 0 strictly
    assert long.exit_long.tolist() == [False, False, False, True, True, False]   # yhat <= 0; NaN never acts
    assert not long.exit_short.any() and (long.k == 1.5).all() and long.max_hold_min.eq(0).all()
    short = sb.signal_table(times, yhat, -1, e0, 2.0)
    assert short.side.tolist() == [0, 0, 0, 0, -1, 0]
    assert short.exit_short.tolist() == [True, True, True, True, False, False]   # -yhat <= 0
    assert not short.exit_long.any()
    assert schema.validate(long).shape[0] == 6


def test_model_exit_entry_no_entry_e_and_no_same_minute_reentry():
    m = flat(200); m.loc[50:, ["open", "high", "low", "close"]] = 100 * math.exp(0.002)
    times = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=x) for x in (15, 30, 45, 60)])
    t = sb.signal_table(times, np.array([10.0, 10.0, -1.0, 10.0]), 1, np.array([np.nan, 100.0, 100.0, 100.0]), 1.0)
    e = np.full(len(m), 100.0)
    r = ax.run_ax(t, m, e, np.full(len(m), np.nan), T0, T0 + pd.Timedelta(minutes=200),
                  reference.SimConfig(include_funding=False, exit_policy="R2_52A", close_at_end=True), np.ones(len(m)))
    tr = r.trades
    assert tr.entry_time.tolist() == [T0 + pd.Timedelta(minutes=31), T0 + pd.Timedelta(minutes=61)]   # 15: NO_ENTRY_E
    assert tr.exit_reason.tolist() == ["flag", "data_end"] and tr.exit_time.iloc[0] == T0 + pd.Timedelta(minutes=46)


def test_fold_ledger_reuses_the_r2_52a_core_and_matches_validation_pnl():
    rng = np.random.default_rng(3)
    n = 3000
    t = pd.date_range(T0, periods=n, freq="1min", tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 8e-4, n))); o = np.r_[c[0], c[:-1]]
    m = pd.DataFrame({"open_time": t, "open": o, "high": np.maximum(o, c) * 1.0004, "low": np.minimum(o, c) * .9996,
                      "close": c})
    times = pd.date_range(T0, periods=n // 15, freq="15min", tz="UTC")
    yhat = rng.normal(0, 8, len(times))
    e = np.full(n, 30.0); e_min = np.where(rng.uniform(size=n) < .05, 20.0, np.nan)
    a, b = T0 + pd.Timedelta(hours=2), T0 + pd.Timedelta(minutes=2900)
    for side in (1, -1):
        for k in sb.K_VALUES:
            table = sb.signal_table(times, yhat, side, np.full(len(times), 30.0), k)
            out = sb.fold_ledger(table, m, e, e_min, a, b, 2.0, k)
            assert out["pnl"] == ax.validation_pnl(table, m, e, e_min, a, b, sb.CONFIG, k)
            assert out["valid"] and out["completed"] == len(out["trades"].position_id.unique())
            ref = reference.simulate(table, m.loc[(m.open_time >= a) & (m.open_time < b)].reset_index(drop=True), a, b,
                                     reference.SimConfig(exit_policy="R2_52A"),
                                     e_bps=e[(m.open_time >= a) & (m.open_time < b)],
                                     e_min_bps=e_min[(m.open_time >= a) & (m.open_time < b)],
                                     k_minute=np.full(int(((m.open_time >= a) & (m.open_time < b)).sum()), k))
            pd.testing.assert_frame_equal(ref.trades, out["trades"], check_dtype=False)
            assert ref.minute_pnl.sum() == pytest.approx(out["result_minute_pnl"], abs=1e-9)
    stressed = sb.fold_ledger(sb.signal_table(times, yhat, 1, np.full(len(times), 30.0), 2.0), m, e, e_min, a, b, 4.0, 2.0)
    assert stressed["pnl"] < sb.fold_ledger(sb.signal_table(times, yhat, 1, np.full(len(times), 30.0), 2.0),
                                            m, e, e_min, a, b, 2.0, 2.0)["pnl"]


# ---------------------------------------------------------------- ranking, tie-break, eligibility
def row(**kw):
    base = {"view": "V5_continuous", "horizon": "1h", "model": "ridge_10", "k": 1.5, "side": "long",
            "net4": 10.0, "median_ic": .02, "net8": 5.0, "folds_valid": 10, "completed": 150}
    return {**base, **kw}


def test_ranking_keys_in_frozen_order_with_1e12_tolerance():
    rank = lambda rows: [(r["view"], r["horizon"], r["model"], r["k"]) for r in sb.rank_candidates(rows)]
    assert rank([row(net4=1.0), row(net4=2.0, k=1.0)])[0][3] == 1.0
    assert rank([row(net4=1.0, median_ic=.1), row(net4=1.0 + 5e-13, k=1.0)])[0][3] == 1.5   # tie -> IC decides
    assert rank([row(net4=1.0, median_ic=.1), row(net4=1.0 + 5e-12, k=1.0)])[0][3] == 1.0   # not a tie
    assert rank([row(k=1.0), row(k=2.0), row(k=1.5)]) == [("V5_continuous", "1h", "ridge_10", k) for k in (2.0, 1.5, 1.0)]
    assert rank([row(view="V6_full"), row()])[0][0] == "V5_continuous"
    assert rank([row(model="catboost"), row(model="ridge_1")])[0][2] == "ridge_1"
    assert [r[2] for r in rank([row(model=m) for m in ("ridge_1", "ridge_100", "ridge_10")])] == \
        ["ridge_100", "ridge_10", "ridge_1"]
    assert [r[1] for r in rank([row(horizon=h) for h in ("24h", "30m", "4h")])] == ["30m", "4h", "24h"]
    assert rank([row(median_ic=float("nan")), row(median_ic=-.5, k=1.0)])[0][3] == 1.0      # NaN ranks last


def test_selection_takes_top_eligible_pair_once_and_never_promotes_a_runner_up():
    rows = [row(net4=50.0, completed=99), row(net4=40.0, k=1.0, folds_valid=9), row(net4=30.0, k=2.0)]
    sel = sb.select_side(rows)
    assert sel["selected"]["k"] == 2.0 and sel["eligible"] == 1
    assert [r["eligible"] for r in sel["trace"]] == [False, False, True]
    assert sb.select_side([row(completed=10)])["selected"] is None


def test_validation_gates():
    ic = [.02] * 7 + [-.01] * 3
    net4 = [5.0] * 7 + [-1.0] * 3
    buckets = {"M": [.01, .02, -.005], "L": [.01, -.002, .03]}
    g = sb.validation_gates(ic, net4, 1.0, buckets)
    assert g["statistical"] and g["stability"] and g["economic"] and g["pass"]
    assert not sb.validation_gates(ic[:6] + [-.01] * 4, net4, 1.0, buckets)["statistical"]
    assert not sb.validation_gates(ic, net4, -0.1, buckets)["economic"]
    assert not sb.validation_gates(ic, net4, 1.0, {"M": [.01, .02, -.02], "L": [.01, .01, .01]})["stability"]
    assert not sb.validation_gates(ic, net4, 1.0, {"M": [.01, -.001, -.002], "L": [.01, .01, .01]})["stability"]
    v6 = sb.v6_gates(full_ic=.02, family_ic=[.01, .01, .01, .01, .01, -.01], top_id_ic=.017,
                     id_shares=[{"K01": .3, "K02": .7}] * 5 + [{"K01": .6, "K02": .4}] * 5)
    assert v6["family"] and v6["top_id"] and v6["single_id"] and v6["pass"]
    assert not sb.v6_gates(.02, [.01] * 4 + [-.01] * 2, .017, [{"K01": .3}] * 10)["family"]
    assert not sb.v6_gates(.02, [.01] * 6, .015, [{"K01": .3}] * 10)["top_id"]
    assert not sb.v6_gates(.02, [.01] * 6, .019, [{"K01": .6}] * 6 + [{"K01": .1}] * 4)["single_id"]


# ---------------------------------------------------------------- statistics
def test_spearman_bootstrap_and_holm():
    rng = np.random.default_rng(1)
    x = rng.normal(size=3000); y = .3 * x + rng.normal(size=3000)
    assert sb.spearman(x, y) == pytest.approx(pd.Series(x).corr(pd.Series(y), method="spearman"))
    out = sb.bootstrap_ic(x, y, block=672, reps=500, seed=20261008)
    again = sb.bootstrap_ic(x, y, block=672, reps=500, seed=20261008)
    assert out == again and out["lower"] > 0 and out["p"] == pytest.approx(1 / 501)
    assert out["method"] == "circular moving-block" and out["block_rows"] == 672
    h = sb.holm({"long": .03, "short": .02})
    assert h["short"]["p_adj"] == pytest.approx(.04) and h["long"]["p_adj"] == pytest.approx(.04)
    h = sb.holm({"long": .03, "short": None})                    # unopened side: p = 1, family stays two
    assert h["long"]["p_adj"] == pytest.approx(.06) and h["short"]["p_adj"] == 1.0


def test_weekly_retrain_schedule_and_fallback_rule():
    s = sb.thursdays(utc("2026-01-01"), utc("2026-10-08"))
    assert len(s) == 40 and s[0] == utc("2026-01-01") and s[-1] == utc("2026-10-01") and all(t.dayofweek == 3 for t in s)
    assert sb.fallback_ok(utc("2026-01-15"), utc("2026-01-08")) and not sb.fallback_ok(utc("2026-01-22"), utc("2026-01-08"))


def test_settlements_round_to_the_scheduled_8h_minute():
    ev = pd.DataFrame({"time": pd.to_datetime(["2026-01-01T00:00:00.008Z", "2026-01-01T08:00:00Z"], format="ISO8601"),
                       "rate": [1e-4, 2e-4]})
    s = sb.settlements(ev)
    assert s.time.tolist() == [utc("2026-01-01"), utc("2026-01-01 08:00")] and s.rate.tolist() == [1e-4, 2e-4]
    with pytest.raises(ValueError):
        sb.settlements(ev.assign(time=pd.to_datetime(["2026-01-01T00:03:00Z", "2026-01-01T08:00:00Z"])))
