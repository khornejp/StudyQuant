"""RL allocator state store (btcusdt_quant/rl/allocator_state.py) and the observation contract: availability,
funding < T, metrics available_time <= T, minute-T row exclusion, future tamper, train-only normalizer, allowlist,
TEST unlock, native signal timelines. Synthetic data only."""
import importlib.util
import sys
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import allocator_state as ast
from btcusdt_quant.rl import sleeve_precompute as sp

ROOT = Path(__file__).resolve().parents[2]
MIN, HOUR = sp.MIN, ast.HOUR
T0 = pd.Timestamp("2024-01-01", tz="UTC").value
DAYS = 40
N = DAYS * 1440


def load_script():
    spec = importlib.util.spec_from_file_location("precompute_rl_allocator_t", ROOT / "scripts/precompute_rl_allocator.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def world(seed=0):
    rng = np.random.default_rng(seed)
    t = T0 + np.arange(N, dtype=np.int64) * MIN
    c = 40_000 * np.exp(np.cumsum(rng.normal(0, 6e-4, N)))
    o = np.r_[c[0], c[:-1]]
    mk = {"t": t, "o": o, "h": np.maximum(o, c) * 1.0003, "l": np.minimum(o, c) * 0.9997, "c": c,
          "v": rng.uniform(1, 9, N), "tb": rng.uniform(0, 1, N)}
    t5 = t[::5]
    met = pd.DataFrame({"available_time": t5 + 5 * MIN, "oi": 1e5 * np.exp(np.cumsum(rng.normal(0, 1e-3, len(t5)))),
                        "global_ls": rng.uniform(.8, 2, len(t5)), "top_ls": rng.uniform(.8, 2, len(t5)),
                        "taker_lsr": rng.uniform(.5, 1.5, len(t5))})
    prem = pd.DataFrame({"available_time": t + MIN, "premium": rng.normal(0, 3e-4, N)})
    ft = t[::480].copy()
    fr = rng.normal(0, 2e-4, len(ft))
    # one sleeve: trades opp 0 [100, 400], opp 1 [2000, 9000], opp 2 [20000, 20500]
    side = np.zeros(N, np.int8)
    opp = np.full(N, -1, np.int32)
    openm = np.zeros(N, bool)
    closed = np.full(N, -1, np.int32)
    led = []
    for q, (a, b) in enumerate(((100, 400), (2000, 9000), (20000, 20500))):
        side[a - 10:b + 1] = 1
        opp[a:b + 1] = q
        openm[a:b + 1] = True
        closed[b] = q
        led.append(pd.DataFrame({"minute_idx": np.arange(a, b + 1), "entry_opportunity_id": q,
                                 "net4": rng.normal(0, 3, b - a + 1)}))
    led = pd.concat(led, ignore_index=True)
    led["minute_time"] = t[led.minute_idx]
    led["available_time"] = led.minute_time + MIN
    for col in ("gross_pnl", "fee", "funding"):
        led[col] = 0.0
    net = np.bincount(led.minute_idx, led.net4, minlength=N)
    grid = pd.DataFrame({"minute_time": t, "available_time": t + MIN, "available": t >= T0 + 1440 * MIN,
                         "base_side": side, "base_weight": (side != 0).astype(np.float32), "signal_active": side != 0,
                         "pending": np.zeros(N, bool), "open": openm, "exit_pending": np.zeros(N, bool),
                         "entry_opportunity_id": opp, "base_mandatory_exit_time": np.full(N, -1, np.int64),
                         "R0_bps": np.float32(np.nan), "R_t_bps": np.float32(np.nan), "stop_level": np.float32(np.nan),
                         "trail_armed": np.zeros(N, np.int8), "gross_pnl": net, "fee": 0.0, "funding": 0.0,
                         "net4": net, "feature_snapshot_id": np.zeros(N, np.int32),
                         "snapshot_id_aux": np.full(N, -1, np.int32), "closed_opp_id": closed})
    return mk, met, prem, ft, fr, grid, led


def build(mk, met, prem, ft, fr, grid, led, T):
    return pd.concat([ast.common_channels(mk, met, prem, ft, fr, T),
                      ast.sleeve_channels("S", grid, led, mk["c"], T)], axis=1)


T_GRID = ast.hour_grid(pd.Timestamp(T0 + 2 * 86400 * 10**9, tz="UTC"), pd.Timestamp(T0 + 39 * 86400 * 10**9, tz="UTC"))


def test_future_tamper_and_minute_T_row_excluded():
    mk, met, prem, ft, fr, grid, led = world()
    base = build(mk, met, prem, ft, fr, grid, led, T_GRID)
    cut = int(T_GRID[300])
    mk2 = {k: (np.where(mk["t"] >= cut, v * 1.7, v) if k != "t" else v) for k, v in mk.items()}   # incl. minute T
    met2, prem2 = met.copy(), prem.copy()
    met2.loc[met2.available_time > cut, ["oi", "global_ls", "top_ls", "taker_lsr"]] *= 1.7
    prem2.loc[prem2.available_time > cut, "premium"] *= 1.7
    fr2 = np.where(ft >= cut, fr * 1.7 + 1e-4, fr)
    g2, l2 = grid.copy(), led.copy()
    m = g2.available_time > cut
    g2.loc[m, "net4"] = 99.0
    g2.loc[m, "open"] = ~g2.loc[m, "open"]
    g2.loc[m, "closed_opp_id"] = 7
    l2.loc[l2.available_time > cut, "net4"] = 55.0
    tam = build(mk2, met2, prem2, ft, fr2, g2, l2, T_GRID)
    pre = T_GRID <= cut
    for c in base.columns:
        assert np.array_equal(base[c].to_numpy()[pre], tam[c].to_numpy()[pre], equal_nan=True), c
    assert any(not np.array_equal(base[c].to_numpy()[~pre], tam[c].to_numpy()[~pre], equal_nan=True)
               for c in base.columns)
    # truncation (prefix) gives the same rows too
    keep = mk["t"] + MIN <= cut
    mk3 = {k: v[keep] for k, v in mk.items()}
    tr = build(mk3, met[met.available_time <= cut], prem[prem.available_time <= cut], ft[ft < cut], fr[ft < cut],
               grid[grid.available_time <= cut].reset_index(drop=True), led[led.available_time <= cut], T_GRID[pre])
    for c in base.columns:
        assert np.array_equal(base[c].to_numpy()[pre], tr[c].to_numpy(), equal_nan=True), c


def test_funding_strictly_before_T_and_metrics_at_or_before_T():
    mk, met, prem, ft, fr, grid, led = world()
    T = ft[10:12].copy()                                   # T exactly at a settlement time
    a = ast.common_channels(mk, met, prem, ft, fr, T)
    fr2 = fr.copy()
    fr2[10] += 5e-3                                        # settlement at T itself: invisible at T
    b = ast.common_channels(mk, met, prem, ft, fr2, T)
    assert a.funding_rate_last[0] == b.funding_rate_last[0] == fr[9] * 1e4
    assert b.funding_rate_last[1] == fr2[10] * 1e4          # visible from the next T
    # metrics: row with available_time == T is used, a row 1 ns later is not
    Tm = met.available_time.to_numpy()[[3000]]
    m2 = met.copy()
    m2.loc[3000, "global_ls"] = 9.0
    m2.loc[3001, "global_ls"] = 5.0
    m2.loc[3001, "available_time"] = Tm[0] + 1
    m2 = m2.sort_values("available_time").reset_index(drop=True)
    x = ast.common_channels(mk, m2, prem, ft, fr, Tm)
    assert np.isclose(x.global_ls_log[0], np.log(9.0))


def test_availability_and_sleeve_values():
    mk, met, prem, ft, fr, grid, led = world()
    T = np.array([T0 + 600 * MIN, T0 + 1500 * MIN, T0 + 5000 * MIN, T0 + 9002 * MIN], np.int64)
    s = ast.sleeve_channels("S", grid, led, mk["c"], T)
    assert s.S_available.tolist() == [0, 1, 1, 1]          # unavailable during the first day
    assert s.S_open.tolist() == [0, 0, 1, 0]
    assert s.S_closed_n.tolist() == [1, 1, 1, 2]
    ln = led.set_index("minute_idx").net4
    assert np.isclose(s.S_unrealized_net4[2], ln.loc[2000:4999].sum())
    assert np.isclose(s.S_closed20_mean[3], (ln.loc[100:400].sum() + ln.loc[2000:9000].sum()) / 2)
    assert s.S_hold_age_h[2] == (4999 - 2000 + 1) / 60


def test_allowlist_blocks_private_columns(tmp_path):
    mk, met, prem, ft, fr, grid, led = world()
    with pytest.raises(PermissionError):
        ast.sleeve_channels("S", grid.assign(exit_px=1.0), led, mk["c"], T_GRID[:3])
    with pytest.raises(PermissionError):
        ast.sleeve_channels("S", grid, led.assign(exit_reason="stop"), mk["c"], T_GRID[:3])
    with pytest.raises(PermissionError):
        sp.obs_columns("decisions", ["entry_opportunity_id", "filled"])
    pd.DataFrame({"decision_time": [T0], "entry_opportunity_id": [0], "exit_px": [1.0]}).to_parquet(
        tmp_path / "outcomes_2024.parquet")
    with pytest.raises(PermissionError):
        sp.read_observation(tmp_path, "outcomes", T0 + HOUR)
    lf = led.assign(tid=0)
    lf.to_parquet(tmp_path / "ledger_2024.parquet")
    r = sp.read_observation(tmp_path, "ledger", int(led.available_time.iloc[50]))
    assert "tid" not in r and len(r) == 51 and (r.available_time <= led.available_time.iloc[50]).all()
    for c in sp.OBS_COLUMNS["decisions"] + sp.OBS_COLUMNS["grid"]:
        assert c not in ("filled", "tid", "entry_idx", "entry_px", "exit_idx", "exit_px", "exit_reason",
                         "exit_decision_idx", "open_at_end", "net4_full")


def test_train_only_normalizer():
    mk, met, prem, ft, fr, grid, led = world()
    f = build(mk, met, prem, ft, fr, grid, led, T_GRID)
    split = pd.Timestamp(int(T_GRID[400]), tz="UTC")
    n1 = ast.fit_normalizer(f, pd.Timestamp(T0, tz="UTC"), split)
    g = f.copy()
    late = g["T"] >= split.value
    g.loc[late, "rv_1h"] = 1e9
    assert ast.fit_normalizer(g, pd.Timestamp(T0, tz="UTC"), split) == n1
    g.loc[~late, "rv_1h"] = g.loc[~late, "rv_1h"] * 3
    assert ast.fit_normalizer(g, pd.Timestamp(T0, tz="UTC"), split)["rv_1h"] != n1["rv_1h"]
    a = ast.apply_normalizer(f, n1)
    assert "hour_sin" not in n1 and np.isfinite(a.rv_1h).all()


def test_history_window():
    f = pd.DataFrame({"a": np.arange(40, dtype=float), "b": -np.arange(40, dtype=float)})
    h = ast.history(f, ["a", "b"], 32)
    assert h.shape == (40, 32, 2)
    assert h[35, -1, 0] == 35 and h[35, 0, 0] == 4 and np.isnan(h[0, 0, 0]) and h[0, -1, 1] == 0


def test_precompute_refuses_without_test_unlock():
    mod = load_script()
    with pytest.raises(sp.TestAccessError):
        mod.main(["precompute"])
    with pytest.raises(sp.TestAccessError):
        sp.require_unlock(False, "x")


def test_native_signal_timelines():
    mod = load_script()
    t = T0 + np.arange(200, dtype=np.int64) * MIN
    # AXC0: 15m groups, first enterable row wins; pending only at the decision minute while flat
    tb = pd.DataFrame({"decision_time": pd.to_datetime(np.repeat(t[[15, 30, 45]], 2), utc=True),
                       "side": [0, -1, 1, 1, 0, 0], "allow_entry": [True, True, False, True, True, True],
                       "e0_bps": [50.0, 50.0, 50.0, np.nan, 50.0, 50.0]})
    tr = pd.DataFrame({"e": [16], "x": [40]})
    s = mod.ax_signal(t, {"table": tb}, tr)
    assert s["side"][14] == 0 and s["side"][15] == -1 and s["side"][30] == 0 and s["side"][45] == 0
    assert s["pending"].tolist().count(True) == 1 and s["pending"][15]
    assert s["snap"][15] == 0 and s["snap"][31] == 2 and s["snap"][10] == -1
    # C: F leg priority over E1, each leg's latest decision <= minute open
    full = {("F3", "V5"): (pd.to_datetime(t[[10, 50]], utc=True), np.array([1, 0])),
            ("E1", "V1a"): (pd.to_datetime(t[[5, 60]], utc=True), np.array([-1, 0]))}
    c = mod.c_signal(t, full, "C1v2")
    assert c["side"][4] == 0 and c["side"][5] == -1 and c["side"][10] == 1 and c["side"][55] == -1
    assert c["side"][60] == 0 and not c["pending"].any() and c["snap"][49] == 0 and c["aux"][61] == 1
