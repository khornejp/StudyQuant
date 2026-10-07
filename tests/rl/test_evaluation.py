"""Evaluation (plan 3 Task 7): C18 window replays, C19 HAC alpha, C13 ensemble vote, spec §6 pass report."""
import math
import numpy as np, pandas as pd, pytest, torch
from btcusdt_quant.sim import analytics, costs, guard, schema
from btcusdt_quant.sim.reference import TRADE_COLUMNS
from btcusdt_quant.sim.rolling import Window
from btcusdt_quant.rl import evaluation as E
from tests.rl.test_vec_env import MIN, NO_FUNDING, T0, make_store, market

DAY = pd.Timedelta(days=1)
WIN = Window("WX", T0, T0, T0, T0 + DAY, T0 + DAY, T0 + 2 * DAY)


def signal_rows(times, sides):
    n = len(times)
    return schema.validate(pd.DataFrame({
        "decision_time": times, "side": sides, "entry": "market", "upper": np.nan, "lower": np.nan,
        "expiry_min": 0, "max_hold_min": 0, "stop_bps": np.nan, "take_bps": np.nan, "exit_long": False,
        "exit_short": False, "allow_entry": True}))


def held_long_net(m, entry, last):
    """One long from entry's open to last's close at 4 bps, PESS funding to the last minute."""
    o, c = m.set_index("open_time").open, m.set_index("open_time").close
    funding = sum(v for _, v in costs.funding_events(1, entry, last + pd.Timedelta(1, "ns")))
    return math.log(c[last] / o[entry]) * 1e4 - 4 + funding


def test_replay_window_flat_start_forced_close():
    m = market(1, gaps=0)
    a, b, last = WIN.test_start, WIN.test_end, WIN.test_end - MIN
    # action series: long everywhere, also before the window; the window still starts flat
    acts = pd.Series(1, index=pd.date_range(T0, T0 + 3 * DAY, freq="15min", inclusive="left"))
    r = E.window_result(acts, WIN, minutes=m)
    assert len(r.trades) == 1 and r.trades.entry_time[0] == a + MIN and r.trades.exit_time[0] == last
    assert r.trades.exit_reason[0] == "data_end"
    daily = E.replay_window(acts, WIN, minutes=m)
    assert list(daily.index) == [a] and daily.iloc[0] == pytest.approx(held_long_net(m, a + MIN, last), abs=1e-9)
    # signal table: a pre-window long is not carried in, an in-window long is force-closed at the last close,
    # a decision in the last 15 minutes is dropped (the action replay's dropped last step)
    sig = signal_rows([a - pd.Timedelta(hours=2), a + pd.Timedelta(hours=2), b - pd.Timedelta(minutes=10)], [1, 1, -1])
    rs = E.window_result(sig, WIN, minutes=m)
    assert len(rs.trades) == 1 and rs.trades.exit_time[0] == last and rs.trades.side[0] == 1
    sd = E.replay_window(sig, WIN, minutes=m)
    assert sd.sum() == pytest.approx(held_long_net(m, a + pd.Timedelta(hours=2) + MIN, last), abs=1e-9)
    # the same targets as an action series give the same daily net (to the minute)
    acts2 = pd.Series(0, index=pd.date_range(a, b, freq="15min", inclusive="left"))
    acts2[acts2.index >= a + pd.Timedelta(hours=2)] = 1
    assert E.replay_window(acts2, WIN, minutes=m).sum() == pytest.approx(sd.sum(), abs=1e-9)
    with pytest.raises(ValueError, match="15-minute grid"):
        E.replay_window(acts, Window("bad", T0, T0, T0, T0, a, b - pd.Timedelta(minutes=5)), minutes=m)


def test_hac_alpha_known_example():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 10, 1000)
    y = 2 + 0.5 * x + rng.normal(0, 1, 1000)
    r = analytics.hac_alpha(y, x, lag=7)
    assert r["reason"] == "ok" and r["lower"] < 2 < r["upper"] and abs(r["beta"] - 0.5) < 0.01
    assert r["upper"] - r["lower"] < 0.3
    flat = analytics.hac_alpha(np.zeros(50), x[:50])
    assert flat["alpha"] == 0 and flat["lower"] == 0 and flat["reason"] == "zero_variance"
    assert math.isnan(analytics.hac_alpha(y[:50], np.ones(50))["alpha"])


class Fixed(torch.nn.Module):
    """Stub policy: always prefers one action index (masked entries stay -inf)."""
    def __init__(self, a):
        super().__init__(); self.a = a

    def forward(self, seq, static, mask):
        logits = torch.zeros(len(seq), 3); logits[:, self.a] = 1.0
        return logits.masked_fill(~mask, float("-inf")), torch.zeros(len(seq))


@pytest.mark.parametrize("votes, side", [((1, 1, 2, 2, 0), 0), ((1, 2, 0, 0, 1), 0), ((1, 1, 1, 2, 0), 1),
                                         ((2, 2, 1, 0, 0), 0), ((2, 2, 2, 1, 1), -1), ((2, 2, 0, 1, 1), 0)])
def test_ensemble_tie_is_flat(votes, side):
    assert E.vote(np.array(votes)) == {0: 0, 1: 1, -1: 2}[side]
    store = make_store(T0, T0 + DAY)
    m = market(0, days=1, gaps=0)
    acts = E.ensemble_actions([Fixed(v) for v in votes], store, m, NO_FUNDING, T0, T0 + DAY)
    assert len(acts) == 96 and acts.index[0] == T0 and (acts == side).all()


def flat_inputs(days=120, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-09-01", periods=days, freq="D", tz="UTC")
    zero = pd.Series(0.0, index=idx)
    comps = {k: pd.Series(rng.normal(0, 50, days), index=idx)
             for k in ("C1_X", "baseline2", "supervised", "random", "flat", "buy_hold")}
    comps["flat"] = zero
    return zero, [zero.copy() for _ in range(5)], comps, rng.normal(0, 300, 20), rng.normal(0, 0.05, 200)


def test_pass_report_all_flat_policy():
    zero, seeds, comps, null, sharpes = flat_inputs()
    rep = E.pass_report(zero, seeds, comps, null, 5285, sharpes, rl_trades=pd.DataFrame(columns=TRADE_COLUMNS), experiment="frozen")
    assert set(rep["criteria"]) == {f"c{k}" for k in range(1, 8)} and rep["pass"] is False
    for c in rep["criteria"].values():
        assert c["pass"] is False and c["zero_reason"] and {"value", "threshold"} <= set(c)
    assert rep["strategies"][0]["trade_n"] == 0 and rep["n_trials"] == 5285
    guard.check(rep)
    acts = pd.Series(0, index=pd.date_range(T0, T0 + DAY, freq="15min", inclusive="left"))
    minute = pd.Series(0.0, index=pd.date_range(T0, T0 + DAY, freq="1min", inclusive="left"))
    store = make_store(T0, T0 + DAY)
    diag = E.diagnostics(acts, [acts] * 5, minute, pd.DataFrame(columns=TRADE_COLUMNS), store,
                         [Window("WX", T0, T0, T0, T0, T0, T0 + DAY)], pd.DataFrame({"a": comps["C1_X"], "b": comps["random"]}), comps["C1_X"],
                         minutes=market(0, days=1, gaps=0))
    assert diag["action_ratios"]["flat"] == 1.0 and diag["seed_agreement"]["mean"] == 1.0
    assert diag["costs"]["12"] == 0.0 and diag["delays"]["5"] == 0.0
    guard.check({**rep, "diagnostics": diag})


def test_pass_report_counts_trades_and_seeds():
    zero, _, comps, null, sharpes = flat_inputs()
    rl = comps["C1_X"] + 100
    trades = pd.DataFrame({"net_bps": [500.0, 400.0, 10.0], "units": [1.0, 1.0, 1.0]})
    seeds = [rl + s for s in (-1e4, 1, 2, 3, 4)]
    rep = E.pass_report(rl, seeds, comps, null, 5285, sharpes, rl_trades=trades, experiment="frozen")
    c = rep["criteria"]
    assert c["c1"]["value"] == pytest.approx(rl.sum()) and c["c6"]["value"] == 4 and c["c6"]["pass"]
    assert c["c5"]["detail"] == pytest.approx({"top2_removed": rl.sum() - 900, "net_8bps": rl.sum() - 12})
    assert c["c7"]["threshold"] == pytest.approx(np.quantile(null, .95))
    assert c["c2"]["detail"].keys() == {"C1_X", "baseline2", "supervised"}
    guard.check(rep)


def test_input_importance_constant_policy_has_zero_drop():
    store = make_store(T0, T0 + 2 * DAY)
    store = type(store)(store.times, store.seq, store.static, store.mask_missing, ["M", "K01_event_side", "h1_ret"],
                        "S1")
    assert [E.feature_group(n) for n in ("pred_x__nan", "K11_15m_age", "hour_sin", "s3_rv_24h", "premium_bps")] \
        == ["detector", "signals", "time", "summaries", "market"]
    imp = E.input_importance([Fixed(1)], store, market(0, gaps=0), NO_FUNDING, [WIN])
    assert set(imp) == {"base_net", "detector", "signals", "summaries", "seq"}
    assert all(v["drop"] == 0 for k, v in imp.items() if k != "base_net") and imp["base_net"] != 0


def test_pass_report_dsr_audit_and_n_trials_guard():
    import hashlib
    zero, seeds, comps, null, sharpes = flat_inputs()
    no_trades = pd.DataFrame(columns=TRADE_COLUMNS)
    with pytest.raises(ValueError, match="n_trials 100 != 5285"):
        E.pass_report(zero, seeds, comps, null, 100, sharpes, rl_trades=no_trades, experiment="frozen")
    rep = E.pass_report(zero, seeds, comps, null, 5285, sharpes[::-1], rl_trades=no_trades, experiment="frozen")
    d = rep["criteria"]["c4"]["detail"]
    assert d["n_trial_sharpes"] == 200 and d["n_trials"] == 5285
    assert d["trial_sharpes_sha256"] == hashlib.sha256(np.sort(sharpes.astype(np.float64)).tobytes()).hexdigest()
    other = E.pass_report(zero, seeds, comps, null, 100, sharpes, rl_trades=no_trades, experiment="frozen", n_trials_override="smoke")
    assert other["n_trials"] == 100 and other["n_trials_override"] == "smoke"
    assert rep["n_trials_override"] is None
    guard.check(other)


def test_n_trials_guard_per_experiment():
    zero, seeds, comps, null, sharpes = flat_inputs()
    nt = pd.DataFrame(columns=TRADE_COLUMNS)
    assert E.N_TRIALS == {"frozen": 5285, "net": 5293}
    with pytest.raises(ValueError, match="n_trials 5285 != 5293"):
        E.pass_report(zero, seeds, comps, null, 5285, sharpes, rl_trades=nt, experiment="net")
    with pytest.raises(ValueError, match="n_trials 5293 != 5285"):
        E.pass_report(zero, seeds, comps, null, 5293, sharpes, rl_trades=nt, experiment="frozen")
    assert E.pass_report(zero, seeds, comps, null, 5293, sharpes, rl_trades=nt, experiment="net")["n_trials"] == 5293
