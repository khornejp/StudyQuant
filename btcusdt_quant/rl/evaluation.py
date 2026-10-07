"""RL evaluation (plan 3 Task 7): C13 ensemble, C18 per-window replays, spec §6 pass criteria and diagnostics.
Every test-window P&L goes through window_result: action series via vec_env.replay (Ruling P3), signal tables via
core.simulate with the same boundaries."""
from __future__ import annotations
import dataclasses, hashlib, itertools, math
from dataclasses import replace
from functools import lru_cache
import numpy as np, pandas as pd, torch
from ..sim import analytics, core, data
from ..sim.reference import SimConfig, SimResult
from ..sim.rolling import END, Window
from .state import StateStore
from .vec_env import SIDES, STEP_MIN, STEP_NS, EnvConfig, VecTradingEnv, replay

STEP = pd.Timedelta(minutes=STEP_MIN)
VS = ("C1_X", "baseline2", "supervised")       # criterion 2: comparators 1, 2, 3
DSR_MIN, SEEDS_MIN, N_SEEDS = 0.95, 4, 5
N_TRIALS = {"frozen": 5285, "net": 5293}       # 5277 prior trials + 8 candidate policies; the net-reward variant adds 8 more


@lru_cache(maxsize=1)
def _minutes() -> pd.DataFrame:
    return data.load_minutes(end=END)


def _span(window: Window, part: str):
    a, b = (window.test_start, window.test_end) if part == "test" else (window.val_start, window.val_end)
    if a != a.floor("15min") or b != b.floor("15min"):
        raise ValueError(f"{window.name} {part} [{a}, {b}) is not on the 15-minute grid")
    return a, b


def window_result(actions_or_signals, window: Window, part: str = "test", minutes=None, config: SimConfig = None,
                  cost_bps: float = 4.0, delay: int = 1, slip: float = 0.0) -> SimResult:
    """C18: flat at the window start, forced close at the last minute's close (exit fee), nominal costs by default.
    pd.Series of target sides -> vec_env.replay (last 15-minute step dropped). Signal table (build_variant output,
    with its SimConfig) -> core.simulate on decisions in [start, end - 15 min) and close_at_end: the same decision
    cut and the same close minute, price and fee. Difference: signal close_at_end books no market slippage on the
    forced close (0 at nominal)."""
    a, b = _span(window, part)
    minutes = _minutes() if minutes is None else minutes
    if isinstance(actions_or_signals, pd.Series):
        return replay(actions_or_signals, minutes, a, b, cost_bps, delay, slip)
    s = actions_or_signals
    rows = s[(s.decision_time >= a) & (s.decision_time < b - STEP)].reset_index(drop=True)
    m = minutes[(minutes.open_time >= a) & (minutes.open_time < b)].reset_index(drop=True)
    cfg = replace(config or SimConfig(), close_at_end=True, fee_per_side=cost_bps / 2, delay_min=int(delay),
                  market_slippage_bps=float(slip))
    return core.simulate(rows, m, a, b, cfg)


def _daily(pnl: pd.Series) -> pd.Series:
    return pnl.groupby(pnl.index.floor("D")).sum()


def replay_window(actions_or_signals, window: Window, part: str = "test", **kw) -> pd.Series:
    """Daily net bps of window_result (UTC days)."""
    return _daily(window_result(actions_or_signals, window, part, **kw).minute_pnl)


# ---------------------------------------------------------------- C13 ensemble
def vote(votes: np.ndarray) -> int:
    """Majority action index; any tie for the top count (2-2-1, 1-1-1...) -> flat (index 0)."""
    counts = np.bincount(np.asarray(votes, np.int64), minlength=3)
    return int(np.argmax(counts)) if (counts == counts.max()).sum() == 1 else 0


def ensemble_actions(models, store: StateStore, minutes: pd.DataFrame, funding, start, end, device="cpu") -> pd.Series:
    """C13 target sides indexed by decision time for [start, end). The ensemble trades one account: each step every
    model sees the shared observation (its account channels are the ensemble's position) and votes its masked argmax.
    One model = that seed's own policy (criterion 6). Same nominal env as validation (train.make_val_fn)."""
    steps = int(((store.times >= pd.Timestamp(start).value) & (store.times < pd.Timestamp(end).value)).sum())
    env = VecTradingEnv(store, minutes, funding, start, end, 1, EnvConfig(episode_steps=steps, randomize=False), 0)
    obs, out = env.reset(), np.zeros(steps, np.int64)
    t0 = store.times[env.k0[0]]
    with torch.inference_mode():
        for t in range(steps):
            x = [torch.as_tensor(v, device=device) for v in obs]
            out[t] = vote(np.array([int(m(*x)[0].argmax(1)[0]) for m in models]))
            obs = env.step(out[t:t + 1].astype(np.int8))[:3]
    return pd.Series(SIDES[out], index=pd.DatetimeIndex(t0 + STEP_NS * np.arange(steps), tz="UTC"))


# ---------------------------------------------------------------- spec §6 criteria
def _criterion(value, threshold, passed, zero, reason="ok", detail=None) -> dict:
    out = {"value": value, "threshold": threshold, "pass": bool(passed) and zero is None, "zero_reason": zero,
           "reason": reason}
    return out if detail is None else {**out, "detail": detail}


def pass_report(rl_daily: pd.Series, seed_dailies: list[pd.Series], comparators: dict[str, pd.Series],
                null_nets: np.ndarray, n_trials: int, trial_sharpes, rl_trades: pd.DataFrame,
                experiment: str, n_trials_override: str | None = None) -> dict:
    """Criteria 1-7 for one state variant. rl_daily / rl_trades: the C13 ensemble's stitched test windows (C18);
    seed_dailies: the 5 seeds (criterion 6); comparators: daily nets keyed C1_X, baseline2, supervised, buy_hold
    (others, e.g. random / flat, are reported only); null_nets: C16 stitched shuffled-control nets.
    No trades -> every criterion fails with zero_reason (spec review focus 5)."""
    if n_trials != N_TRIALS[experiment] and not n_trials_override:
        raise ValueError(f"n_trials {n_trials} != {N_TRIALS[experiment]} ({experiment}); pass n_trials_override=<reason> to use another value")
    if len(seed_dailies) != N_SEEDS:
        raise ValueError(f"criterion 6 needs {N_SEEDS} seeds")
    d = rl_daily.astype(float)
    n_tr = len(rl_trades)
    zero = None if n_tr else "no trades in the test windows (all-flat policy)"
    net4 = float(d.sum())
    net8 = net4 - 4.0 * float(rl_trades.units.sum()) if n_tr else net4      # +2 bps per side per unit
    top2 = net4 - float(rl_trades.net_bps.nlargest(2).sum()) if n_tr else net4
    diff = {k: analytics.pw_mean_ci(d.sub(comparators[k], fill_value=0.0).to_numpy()) for k in VS}
    low2 = min(v["lower"] for v in diff.values())
    bh = comparators["buy_hold"].reindex(d.index, fill_value=0.0)
    alpha = analytics.hac_alpha(d.to_numpy(), bh.to_numpy())
    dsr = analytics.deflated_sharpe(d.to_numpy(), trial_sharpes, n_trials)
    ts = np.sort(np.asarray(trial_sharpes, np.float64).ravel())     # audit trail of the DSR null
    dsr = {**dsr, "n_trials": int(n_trials),
            "n_trials_override": n_trials_override, "n_trial_sharpes": int(len(ts)),
           "trial_sharpes_sha256": hashlib.sha256(ts.tobytes()).hexdigest()}
    seeds = [float(s.sum()) for s in seed_dailies]
    q95 = float(np.quantile(null_nets, 0.95)) if len(null_nets) else math.nan
    criteria = {
        "c1": _criterion(net4, 0.0, net4 > 0, zero),
        "c2": _criterion(low2, 0.0, low2 > 0, zero, detail=diff),
        "c3": _criterion(alpha["lower"], 0.0, alpha["lower"] > 0, zero, alpha["reason"], alpha),
        "c4": _criterion(dsr["dsr"], DSR_MIN, dsr["dsr"] >= DSR_MIN, zero, dsr["reason"], dsr),
        "c5": _criterion(min(top2, net8), 0.0, top2 > 0 and net8 > 0, zero,
                         detail={"top2_removed": top2, "net_8bps": net8}),
        "c6": _criterion(sum(s > 0 for s in seeds), SEEDS_MIN, sum(s > 0 for s in seeds) >= SEEDS_MIN, zero,
                         detail={"seed_nets": seeds}),
        "c7": _criterion(net4, q95, net4 > q95, zero, "ok" if len(null_nets) else "no shuffled-control results",
                         {"n_null": int(len(null_nets))}),
    }
    comps = {k: {"net_4bps": float(s.sum()), "diff": analytics.pw_mean_ci(d.sub(s, fill_value=0.0).to_numpy())}
             for k, s in comparators.items()}
    return {"criteria": criteria, "pass": all(c["pass"] for c in criteria.values()), "n_trials": int(n_trials),
            "n_trials_override": n_trials_override,
            "strategies": [{"id": "rl_ensemble", "trade_n": n_tr, "zero_reason": zero, "net_4bps": net4}],
            "comparators": comps}


# ---------------------------------------------------------------- diagnostics (reported only)
def _ratios(a: pd.Series) -> dict:
    n = len(a)
    if not n:
        return {"n": 0, "flat": math.nan, "long": math.nan, "short": math.nan, "reason": "no steps"}
    return {"n": n, "flat": float((a == 0).mean()), "long": float((a == 1).mean()), "short": float((a == -1).mean()),
            "reason": "ok"}


def _sums(values: pd.Series, keys: pd.Series) -> dict:
    g = values.groupby(keys.to_numpy())
    return {str(k): {"n": int(len(v)), "net": float(v.sum())} for k, v in g}


def _reward_parts(pnl: pd.Series, windows: list[Window]) -> dict:
    """The frozen reward on the evaluation path: per 15-minute step net, 2 max(0, -net), and dMDD of the minute
    equity (each window is one episode)."""
    net = loss = dd = 0.0
    for w in windows:
        p = pnl[(pnl.index >= w.test_start) & (pnl.index < w.test_end)]
        step = p.groupby(p.index.floor("15min")).sum()
        eq = p.cumsum()
        net += float(step.sum()); loss += float((2 * np.maximum(0.0, -step)).sum())
        dd += float((eq.cummax().clip(lower=0) - eq).max()) if len(eq) else 0.0
    return {"net": net, "loss_penalty": loss, "dd_penalty": dd, "reward": net - loss - dd}


def diagnostics(actions: pd.Series, seed_actions: list[pd.Series], minute_pnl: pd.Series, trades: pd.DataFrame,
                store: StateStore, windows: list[Window], candidates: pd.DataFrame, benchmark: pd.Series,
                minutes=None, importance: dict | None = None) -> dict:
    """Spec §6 diagnostics for the stitched test windows. store: the raw (not normalized) state store, for regime M
    and technique sides; candidates: daily nets of the trial policies (PBO, White, SPA against the benchmark);
    importance: input_importance output (computed separately, expensive)."""
    daily = _daily(minute_pnl)
    units = float(trades.units.sum()) if len(trades) else 0.0
    net4 = float(minute_pnl.sum())
    tr = trades.copy()
    if len(tr):
        tr["hold"] = (pd.to_datetime(tr.exit_time) - pd.to_datetime(tr.entry_time)).dt.total_seconds() / 60
    holds = tr.hold if len(tr) else pd.Series(dtype=float)
    k = np.searchsorted(store.times, actions.index.as_unit("ns").asi8)
    k = np.minimum(k, len(store.times) - 1)
    names = list(store.feature_names)
    regime = {}
    if "M" in names:
        m = pd.Series(store.static[k, names.index("M")].astype(float), index=actions.index)
        cuts = np.nanquantile(m, [1 / 3, 2 / 3]) if np.isfinite(m).any() else [math.nan, math.nan]
        terc = pd.Series(np.where(~np.isfinite(m), "missing", np.where(m <= cuts[0], "low",
                                  np.where(m <= cuts[1], "mid", "high"))), index=actions.index)
        regime = {t: _ratios(actions[terc == t]) for t in ("low", "mid", "high", "missing")}
        if len(tr):
            at = terc.reindex(pd.to_datetime(tr.decision_time), method="ffill")
            regime["trade_net"] = _sums(tr.net_bps.reset_index(drop=True), at.fillna("missing").reset_index(drop=True))
    by_signal = {}
    for col in (c for c in names if c.endswith("_event_side")):
        side = store.static[k, names.index(col)]
        on = side != 0
        a = actions.to_numpy()
        by_signal[col[:-len("_event_side")]] = {
            "n": int(on.sum()), "same": float((a[on] == side[on]).mean()) if on.any() else math.nan,
            "opposite": float((a[on] == -side[on]).mean()) if on.any() else math.nan,
            "flat": float((a[on] == 0).mean()) if on.any() else math.nan, "reason": "ok" if on.any() else "never active"}
    pairs = [float((x.to_numpy() == y.to_numpy()).mean()) for x, y in itertools.combinations(seed_actions, 2)]
    per_window = lambda s: [s[(s.index >= w.test_start) & (s.index < w.test_end)] for w in windows]
    delays = {str(dl): float(sum(replay_window(a, w, minutes=minutes, delay=dl).sum()
                                 for a, w in zip(per_window(actions), windows))) for dl in (1, 2, 5)}
    excess = candidates.sub(benchmark, axis=0).dropna()
    return {
        "reward_components": _reward_parts(minute_pnl, windows),
        "action_ratios": _ratios(actions),
        "switches": {"n": int(sum((a.diff().fillna(0) != 0).sum() for a in per_window(actions))),
                     "trades_per_month": float(tr.groupby(pd.to_datetime(tr.entry_time).dt.strftime("%Y-%m")).size()
                                               .mean()) if len(tr) else 0.0},
        "hold_minutes": {"n": int(len(holds)), "mean": float(holds.mean()) if len(holds) else math.nan,
                         "median": float(holds.median()) if len(holds) else math.nan,
                         "q90": float(holds.quantile(.9)) if len(holds) else math.nan,
                         "reason": "ok" if len(holds) else "no trades"},
        "last16": _ratios(pd.concat([a.iloc[-16:] for a in per_window(actions)])),
        "mask_triggers": {"missing_steps": int(store.mask_missing[k].sum()), "steps": int(len(k))},
        "half_year": _sums(daily, pd.Series(daily.index.year.astype(str) + np.where(daily.index.month <= 6, "H1", "H2"))),
        "side": _sums(tr.net_bps, tr.side) if len(tr) else {},
        "hour": _sums(tr.net_bps, pd.to_datetime(tr.entry_time).dt.hour) if len(tr) else {},
        "regime_M_tercile": regime,
        "signal": by_signal,
        "costs": {str(c): net4 + (4 - c) * units for c in (0, 4, 8, 12)},
        "delays": delays,
        "pbo": analytics.cscv_pbo(candidates),
        "white": analytics.white_rc(excess.to_numpy()),
        "hansen_spa": analytics.hansen_spa(excess.to_numpy()),
        "input_importance": importance or {"value": math.nan, "reason": "not computed"},
        "seed_agreement": {"mean": float(np.mean(pairs)) if pairs else math.nan,
                           "min": float(np.min(pairs)) if pairs else math.nan,
                           "reason": "ok" if pairs else "fewer than 2 seeds"},
    }


def feature_group(name: str) -> str:
    base = name.removesuffix("__nan")
    if base.startswith("pred_") or base in ("M", "L", "missing"):
        return "detector"
    if base[:1] == "K" and base[1:3].isdigit():
        return "signals"
    if base.startswith(("dow_", "hour_", "min_to")):
        return "time"
    if base.startswith(("h1_", "h4_", "s3_ret", "s3_rv", "s3_pos", "s3_volratio")):
        return "summaries"
    return "market"


def input_importance(models, store: StateStore, minutes, funding, windows: list[Window], seed: int = 0,
                     device="cpu") -> dict:
    """Permutation importance on the test windows (reported only): per feature group (and the 15m sequence), rows
    are permuted inside each test window; drop = ensemble net - permuted net."""
    def net(s):
        return float(sum(replay_window(ensemble_actions(models, s, minutes, funding, w.test_start, w.test_end, device),
                                       w, minutes=minutes).sum() for w in windows))
    rng = np.random.default_rng(seed)
    base = net(store)
    groups = np.array([feature_group(n) for n in store.feature_names])
    out = {"base_net": base}
    for g in sorted(set(groups)) + ["seq"]:
        seq, static = store.seq.copy(), store.static.copy()
        for w in windows:
            rows = np.flatnonzero((store.times >= w.test_start.value) & (store.times < w.test_end.value))
            p = rng.permutation(rows)
            if g == "seq":
                seq[rows] = store.seq[p]
            else:
                cols = np.flatnonzero(groups == g)
                static[np.ix_(rows, cols)] = store.static[np.ix_(p, cols)]
        v = net(dataclasses.replace(store, seq=seq, static=static))
        out[g] = {"net": v, "drop": base - v}
    return out
