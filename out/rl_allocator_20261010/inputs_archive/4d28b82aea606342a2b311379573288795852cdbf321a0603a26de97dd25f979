"""LONG-CAP-RECOVERY (2026-10-10): sequential capitulation -> recovery long sleeve (LCR).

Spec: scratchpad codex_newlong.md section "2) 단일 배치 명세" (Codex session 01a12515-36a1-7400-a078-adf4cce7e936).
Comparator: Batch-5 run NM-B5-20261010T080025Z-c55285f2 LONG_DEV_PICK = G5-S180-c+0.0-W180-P65 long sleeve
(re-simulated long-only, exact parity with the stored primary trades / daily / 6 cells / bootstrap asserted).
Frozen hypothesis: a strong price dislocation with falling OI and concentrated taker selling, followed within 8-16h by
a recovery of price, SVI and taker flow, gives a long rebound that is profitable after a 4 bps maker round trip, and it
adds positive-P&L days in periods where S180 is inactive.
Engine: Batch-2 simulate/Book/stationary_boot_p05/asof_values/load_all, Batch-1 trailing_robust_z, Batch-3
window_bounds, Batch-4 prefix_market, Batch-5 build_state (score/SVI/W180-P65 weight/strict funding fz) are imported
unchanged via importlib (file hashes recorded as inputs).
Times: dec4 = 239 + 240k; bar_time = market_time[dec4]; T = bar_time + 1m. Every input has available_time <= T.
Features (all robust baselines exclude the current value; MAD <= 0 / stale / missing -> NaN):
  r4 = log(C_t / C_{t-1}); gap = (logC_t - median(logC_{t-42..t-1})) / (1.4826 MAD(r4_{t-180..t-1}) sqrt(42)), both
  windows must be fully finite; zr4 = robust z vs previous 1080 decisions (>= 540 finite); OI_T / OI_24 = latest OI with
  available_time <= T (resp. <= T-24h) and age <= 10m, dOI24 = log(OI_T/OI_24), zOI24 robust z 1080/540;
  taker = latest log(taker_lsr) (available_time <= T, age <= 10m), ztaker robust z 1080/540; prem4 = mean premium with
  T-4h < available_time <= T, valid only with >= 216 finite rows, zprem robust z 1080/540; zfund = Batch-5 strict fz
  (event j = max{ft < T}, robust z over events j-90..j-1, >= 30); SVI42 = Batch-5 G svi[42], dSVI = SVI42_t -
  SVI42_{t-1}, zdSVI robust z 1080/540.
State machine (per logical config; NaN comparisons are False -> a missing input never arms, recovers or exits):
  shock = gap <= gap_cut & zOI24 <= -0.5 & ztaker <= -1.0 & discount (NONE / FUND zfund <= -0.5 / PREM zprem <= -1.0).
  FLAT + shock -> ARMED (arm = t, min_gap = gap_t, min_ztaker = ztaker_t); no entry at a shock decision.
  ARMED + shock -> re-arm (arm time and minima reset to the new shock; old episode outcome REARMED).
  ARMED, 1 <= t-arm <= arm_bars, first decision with zr4 >= 0 & zdSVI >= 0 & gap - min_gap >= 0.50 &
  ztaker - min_ztaker >= 0.50 & gap < 0 & weight finite > 0 -> target 1 (activation, weight frozen = W180-P65 at t).
  Minima are running minima from the arm decision through t-1 (NaN ignored). No recovery by t-arm = arm_bars ->
  EXPIRED (FLAT). HOLD: target 0 at the first later decision with gap >= exit_gap or t - activation >= max_hold_bars
  (activation-based, not fill-based); shocks during HOLD are ignored and the exit decision never re-arms, so every
  new entry needs a new shock after the exit decision.
Execution: Batch-2 'state' simulator, offset {2,5} bps x penetration {0.5,1,2} bp, entry TTL 60m (target stays 1 ->
the simulator re-quotes at the next held-target decision with the frozen activation weight), exit quote 2 bps re-quoted
every 60m, maker 4 bps rt, 0 slippage, real funding PESS; net8 report-only. One continuous simulation
[2020-01-01, 2026-10-08); windows are MTM cuts (no forced exit at a boundary).
Selection (DEV-only; TEST columns dropped before the call, TEST tamper invariance asserted): eligible = DEV-A and
DEV-B long net4 > 0 in 6/6 cells, DEV-FULL primary closed >= 40 and fill >= 0.10, combined-long (S180 + new, primary
cell) positive days > S180 positive days in DEV-A and DEV-B. Sort: min(DEV-A/B positive-day delta) desc, dev_score
(min DEV-A/B primary boot p05 over 20/60/120) desc, min(DEV-A/B x 6 cells net4/day) desc, |DEV-FULL primary daily
Pearson(new, S180)| asc, combined-long DEV-FULL MDD asc, config id. No eligible -> LCR_DEV_BEST_INELIGIBLE (same sort
over all 48) and the batch is FAIL.
PASS: selected eligible & DEV-A/DEV-B/TEST 6/6 cells long net4 > 0 & TEST primary boot p05 20/60/120 > 0
(10,000 resamples, seed 20261010). COMPLEMENT_PASS (separate): [2026-01-01, 2026-08-01) new net4 6/6 > 0 and
combined-long positive days > S180 positive days there (primary cell).
Combined-long = S180 long minute P&L + new minute P&L of the same exec cell; no rescale; each sleeve weight <= 1,
gross <= 2 asserted.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, itertools, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.sim import provenance, registry  # noqa: E402
from btcusdt_quant.sim.store import canonical  # noqa: E402


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(s)
    s.loader.exec_module(mod)
    return mod


B2_PATH = ROOT / "out/run_new_model_batch2_20261010.py"
B5_PATH = ROOT / "out/run_new_model_batch5_20261010.py"
b5 = _load("nm_b5", B5_PATH)
b2, b3, b4 = b5.b2, b5.b3, b5.b4
assert Path(b2.__file__).resolve() == B2_PATH.resolve()
OUT_BASE = ROOT / "out/long_cap_recovery_20261010"
PARENT = "NM-B5-20261010T080025Z-c55285f2"
PARENT_DIR = ROOT / "out/new_model_batch5_20261010" / PARENT
REGISTRY = b2.REGISTRY
MIN, HOUR, DAY, TS = b2.MIN, b2.HOUR, b2.DAY, b2.TS
WINDOWS, BLOCKS, OFFSETS, PENS, PRIMARY = b2.WINDOWS, b2.BLOCKS, b5.OFFSETS, b5.PENS, b5.PRIMARY
CELLS = [(o, p) for o in OFFSETS for p in PENS]
AUG, OCT = TS("2026-08-01"), TS("2026-10-01")
SUBWIN = {"TEST-JanJul": (b2.SPLIT, AUG), "TEST-AugSep": (AUG, OCT), "TEST-Oct": (OCT, b2.END)}
ALLWIN = {**WINDOWS, **SUBWIN}
COMP_WIN = "TEST-JanJul"                       # [2026-01-01, 2026-08-01)
VOL, S180_PICK = "W180-P65", dict(struct="S180", c=0.0, vol="W180-P65")
S180_ID = "G5-S180-c+0.0-W180-P65"
ZN, ZMIN, AGE, PREM_MIN = 1080, 540, 10 * MIN, 216
OI_CUT, TAKER_CUT, FUND_CUT, PREM_CUT, REC_DELTA = -0.5, -1.0, -0.5, -1.0, 0.50
GAP_CUTS, DISCS, ARMS, EXIT_GAPS, HOLDS = (-1.5, -2.0), ("NONE", "FUND", "PREM"), (2, 4), (-0.5, 0.0), (3, 6)
GRID = list(itertools.product(GAP_CUTS, DISCS, ARMS, EXIT_GAPS, HOLDS))
FEAT = ("gap", "zr4", "zOI24", "ztaker", "zfund", "zprem", "SVI42", "zdSVI")


def cid(g) -> str:
    gc, d, a, x, h = g
    return f"LCR-g{gc:+.1f}-{d}-a{a}-x{x:+.1f}-h{h}"


def sid(c: str, o, p) -> str:
    return f"{c}|offset={o}|pen={p}"


def cell_tag(o, p) -> str:
    return f"o{o}_p{p}"


# ---------------- causal features ----------------
def rz(x: np.ndarray, n: int = ZN, mn: int = ZMIN) -> np.ndarray:
    return b2.b1.trailing_robust_z(x, n, mn)


def asof_src(av: np.ndarray, vals: np.ndarray, T: np.ndarray, age: int = AGE):
    """Latest value with available_time <= T and age <= `age` (NaN otherwise) and its available time (int64 min)."""
    v = b2.asof_values(av, vals, T, age)
    p = np.searchsorted(av, T, "right") - 1
    a = np.where(np.isfinite(v), av[np.maximum(p, 0)], np.iinfo(np.int64).min)
    assert np.all(a <= T), "as-of input after decision"
    return v, a


def gap_feature(lc: np.ndarray, r4: np.ndarray) -> np.ndarray:
    med = b2.shift(b2.roll(lc, 42, "median"), 1)                       # median logC_{t-42..t-1}
    pad = np.concatenate([np.full(180, np.nan), r4])
    win = np.lib.stride_tricks.sliding_window_view(pad, 180)[:len(r4)]   # row t = r4_{t-180..t-1}
    ok = np.isfinite(win).all(1)
    mad = np.full(len(r4), np.nan)
    wm = win[ok]
    mad[ok] = np.median(np.abs(wm - np.median(wm, 1, keepdims=True)), 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sc = 1.4826 * mad * np.sqrt(42)
        return np.where(sc > 0, (lc - med) / sc, np.nan)


def features(m, dec4: np.ndarray, st: dict, met: pd.DataFrame, prem: pd.DataFrame) -> dict:
    T = st["T"]
    lc = np.log(m.c[dec4])
    r4 = np.diff(lc, prepend=np.nan)
    f = {"T": T, "r4": r4, "gap": gap_feature(lc, r4), "zr4": rz(r4)}
    av = met.available_time.array.asi8
    assert np.all(np.diff(av) > 0), "metrics available_time not strictly increasing"
    oi = met.oi.to_numpy(float)
    oi = np.where(oi > 0, oi, np.nan)
    f["oi_T"], f["oi_T_avail"] = asof_src(av, oi, T)
    f["oi_24"], f["oi_24_avail"] = asof_src(av, oi, T - DAY)
    assert np.all(f["oi_24_avail"] <= T - DAY), "OI lag after T-24h"
    f["dOI24"] = np.log(f["oi_T"] / f["oi_24"])
    f["zOI24"] = rz(f["dOI24"])
    tk = met.taker_lsr.to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        tk = np.where(tk > 0, np.log(tk), np.nan)
    f["taker"], f["taker_avail"] = asof_src(av, tk, T)
    f["ztaker"] = rz(f["taker"])
    pa = prem.available_time.array.asi8
    assert np.all(np.diff(pa) > 0), "premium available_time not strictly increasing"
    pv = prem.premium.to_numpy(float)
    fin = np.isfinite(pv)
    cs, cn = np.concatenate([[0.0], np.cumsum(np.where(fin, pv, 0.0))]), np.concatenate([[0], np.cumsum(fin)])
    lo, hi = np.searchsorted(pa, T - 4 * HOUR, "right"), np.searchsorted(pa, T, "right")
    assert np.all(pa[hi[hi > 0] - 1] <= T[hi > 0]) and np.all(pa[lo[lo < len(pa)]] > T[lo < len(pa)] - 4 * HOUR)
    f["prem_n"] = cn[hi] - cn[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        f["prem4"] = np.where(f["prem_n"] >= PREM_MIN, (cs[hi] - cs[lo]) / f["prem_n"], np.nan)
    f["prem_last_avail"] = np.where(hi > lo, pa[np.maximum(hi - 1, 0)], np.iinfo(np.int64).min)
    f["zprem"] = rz(f["prem4"])
    f["fund"], f["zfund"], f["fund_time"] = st["fund"], st["fz"], st["ftime"]
    assert np.all(f["fund_time"] < T), "funding not strictly before T"
    f["SVI42"] = st["svi"][42]
    f["dSVI"] = np.diff(f["SVI42"], prepend=np.nan)
    f["zdSVI"] = rz(f["dSVI"])
    f["w"] = st["w"][VOL]
    return f


# ---------------- state machine ----------------
def lcr_signal(f: dict, g) -> dict:
    gc, disc, arm_bars, exit_gap, max_hold = g
    gap, zt, wv = f["gap"], f["ztaker"], f["w"]
    with np.errstate(invalid="ignore"):
        shock = (gap <= gc) & (f["zOI24"] <= OI_CUT) & (zt <= TAKER_CUT)
        if disc == "FUND":
            shock &= f["zfund"] <= FUND_CUT
        elif disc == "PREM":
            shock &= f["zprem"] <= PREM_CUT
        rec_base = (f["zr4"] >= 0) & (f["zdSVI"] >= 0) & (gap < 0) & np.isfinite(wv) & (wv > 0)
    n = len(gap)
    side, w = np.zeros(n, int), np.zeros(n)
    ev, state, arm, mg, mt, act, wf, cur = [], 0, -1, np.nan, np.nan, -1, 0.0, None
    for k in range(n):
        if state == 2:                                            # HOLD
            if (gap[k] >= exit_gap) or (k - act >= max_hold):
                state, cur["exit_idx"] = 0, k                       # exit decision never re-arms
                continue
            side[k], w[k] = 1, wf
            continue
        if shock[k]:
            if state == 1:
                cur.update(end_idx=k, outcome="REARMED")
            state, arm, mg, mt = 1, k, gap[k], zt[k]
            cur = {"arm_idx": k, "rearm": bool(ev and ev[-1]["outcome"] == "REARMED" and ev[-1]["end_idx"] == k)}
            ev.append(cur)
            cur.update(end_idx=-1, outcome="OPEN", exit_idx=-1, min_gap=mg, min_ztaker=mt)
            continue
        if state != 1:
            continue
        d = k - arm
        with np.errstate(invalid="ignore"):
            rec = rec_base[k] and (gap[k] - mg >= REC_DELTA) and (zt[k] - mt >= REC_DELTA)
        if 1 <= d <= arm_bars and rec:
            state, act, wf = 2, k, float(wv[k])
            cur.update(end_idx=k, outcome="RECOVERY", min_gap=mg, min_ztaker=mt)
            side[k], w[k] = 1, wf
            continue
        if np.isfinite(gap[k]):
            mg = min(mg, gap[k])
        if np.isfinite(zt[k]):
            mt = min(mt, zt[k])
        cur.update(min_gap=mg, min_ztaker=mt)
        if d >= arm_bars:
            state = 0
            cur.update(end_idx=k, outcome="EXPIRED")
    return {"side": side, "w": w, "shock": shock, "events": ev}


def check_signal(f: dict, sig: dict, g) -> dict:
    """Structural asserts: recovery after arm, no re-entry without a new shock, hold cap, fail-closed shocks."""
    ev, side, shock = sig["events"], sig["side"], sig["shock"]
    rec = [e for e in ev if e["outcome"] == "RECOVERY"]
    starts = np.flatnonzero((side == 1) & (np.concatenate([[0], side[:-1]]) == 0))
    assert len(starts) == len(rec) and all(e["end_idx"] == s for e, s in zip(rec, starts)), "activation != recovery"
    prev_exit = -1
    for e in rec:
        assert e["end_idx"] > e["arm_idx"] and e["end_idx"] - e["arm_idx"] <= g[2], "recovery_idx <= arm_idx"
        assert e["arm_idx"] > prev_exit, "re-entry without a new shock"
        assert shock[e["arm_idx"]] and side[e["arm_idx"]] == 0, "arm without shock / entry at shock"
        prev_exit = e["exit_idx"] if e["exit_idx"] >= 0 else len(side)
    runs = np.diff(np.concatenate([[0], side, [0]]))
    assert np.all(np.flatnonzero(runs == -1) - np.flatnonzero(runs == 1) <= g[4]), "hold > max_hold"
    with np.errstate(invalid="ignore"):
        assert not shock[~np.isfinite(f["gap"]) | ~np.isfinite(f["zOI24"]) | ~np.isfinite(f["ztaker"])].any()
    assert np.all(sig["w"][side == 1] > 0) and np.all(sig["w"] <= 1) and np.all(sig["w"][side == 0] == 0)
    return {"shocks": int(shock.sum()), "arms": int(sum(not e["rearm"] for e in ev)),
            "rearms": int(sum(e["rearm"] for e in ev)), "recoveries": len(rec),
            "expired": int(sum(e["outcome"] == "EXPIRED" for e in ev)),
            "rearmed_episodes": int(sum(e["outcome"] == "REARMED" for e in ev)),
            "target1_decisions": int(side.sum()), "reentry_without_new_shock": 0}


def s180_signal(st: dict) -> dict:
    ref = b5.core_signal(st, S180_PICK)
    side = (ref["side"] == 1).astype(int)
    return {"side": side, "w": np.where(side == 1, ref["w"], 0.0)}


# ---------------- metrics ----------------
def trade_part(book, a: int, b: int) -> np.ndarray:
    if not len(book.s):
        return np.zeros(0)
    legs = ((book.j0 >= a) & (book.j0 < b)).astype(float) + ((book.jx >= a) & (book.jx < b))
    fm = (book.f_min >= a) & (book.f_min < b)
    fund = np.bincount(book.f_tid[fm], book.f_cf[fm], minlength=len(book.s))
    return book.gross_upto(b) - book.gross_upto(a) + fund - 2 * book.w * legs


def top_share(part: np.ndarray, net: float, k: int) -> float:
    return float(np.sort(part)[::-1][:k].sum() / net) if net != 0 and len(part) else np.nan


def run_cells(m, dec4, wb: dict, sig: dict) -> tuple[dict, dict, dict]:
    R, books_tr = {}, {}
    pb = None
    for o, p in CELLS:
        tr, od = b2.simulate(m, "state", dec4, sig["side"], sig["w"], o, b2.TTL_TREND, p, 0, m.N)
        bk = b2.Book(m, tr, od, 0, m.N)
        ev = {k: bk.window(a, b) for k, (a, b) in wb.items()}
        assert all(abs(e["short_net4"]) < 1e-12 and e["short_closed"] == 0 for e in ev.values()), "long-only"
        R[(o, p)] = ev
        books_tr[(o, p)] = (tr, bk.daily(0, m.N))
        if (o, p) == PRIMARY:
            pb = bk
    return R, pb, books_tr


def corr(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x, y) -> float:
    return corr(pd.Series(x).rank().to_numpy(), pd.Series(y).rank().to_numpy())


def days_count(d: np.ndarray, pre: str = "") -> dict:
    return {f"{pre}pos_days": int((d > 0).sum()), f"{pre}neg_days": int((d < 0).sum()),
            f"{pre}zero_days": int((d == 0).sum()), f"{pre}nonzero_days": int((d != 0).sum())}


def config_row(c: str, R: dict, pb, s_pb, wb: dict) -> tuple[dict, dict]:
    """Per-config DEV/TEST metrics (primary cell + 6-cell net4) and new-sleeve bootstrap over the 4 main windows."""
    row, boot = {"config_id": c}, {}
    daily, sdaily = pb.daily(0, pb.m.N), s_pb.daily(0, pb.m.N)
    comb = pb.pnl + s_pb.pnl
    for k in WINDOWS:
        a, b = wb[k]
        e = R[PRIMARY][k]
        dw, sw = daily[a // 1440:b // 1440], sdaily[a // 1440:b // 1440]
        row.update({f"{k}_{x}": e[f"long_{x}"] for x in ("net4", "net8", "closed", "entries", "win", "exp_days")})
        row.update({f"{k}_mdd": e["mdd_1m"], f"{k}_sharpe": e["sharpe"], f"{k}_fill": e["fill_notional_rate"]})
        row.update({f"{k}_{x}": v for x, v in days_count(dw).items()})
        row[f"{k}_comb_pos_delta"] = int(((dw + sw) > 0).sum() - (sw > 0).sum())
        row[f"{k}_pearson_s180"] = corr(dw, sw)
        row[f"{k}_comb_mdd"] = b5.pnl_stats(comb, a, b)["mdd_1m"]
        for o, p in CELLS:
            row[f"{k}_{cell_tag(o, p)}"] = R[(o, p)][k]["long_net4"]
            row[f"{k}_{cell_tag(o, p)}_pd"] = R[(o, p)][k]["long_per_day"]
        row[f"{k}_cells_pos"] = int(sum(R[cl][k]["long_net4"] > 0 for cl in CELLS))
        row[f"{k}_worst_cell"] = min(R[cl][k]["long_net4"] for cl in CELLS)
        for bl in BLOCKS:
            boot[(k, bl)] = b2.stationary_boot_p05(dw, bl)
            row[f"{k}_boot{bl}"] = boot[(k, bl)]
    row["dev_score"] = min(boot[(w, bl)] for w in ("DEV-A", "DEV-B") for bl in BLOCKS)
    row["dev_pos_delta"] = min(row["DEV-A_comb_pos_delta"], row["DEV-B_comb_pos_delta"])
    row["dev_cell_floor_pd"] = min(R[cl][w]["long_per_day"] for cl in CELLS for w in ("DEV-A", "DEV-B"))
    row["dev_abs_pearson"] = abs(row["DEV-FULL_pearson_s180"])
    row["dev_elig_cells"] = bool(row["DEV-A_cells_pos"] == 6 and row["DEV-B_cells_pos"] == 6)
    row["dev_elig_closed"] = bool(row["DEV-FULL_closed"] >= 40)
    row["dev_elig_fill"] = bool(row["DEV-FULL_fill"] >= 0.10)
    row["dev_elig_posdays"] = bool(row["DEV-A_comb_pos_delta"] > 0 and row["DEV-B_comb_pos_delta"] > 0)
    row["dev_eligible"] = bool(row["dev_elig_cells"] and row["dev_elig_closed"] and row["dev_elig_fill"]
                               and row["dev_elig_posdays"])
    return row, boot


SORT = (["dev_pos_delta", "dev_score", "dev_cell_floor_pd", "dev_abs_pearson", "DEV-FULL_comb_mdd", "config_id"],
        [False, False, False, True, True, True])


def dev_view(cm: pd.DataFrame) -> pd.DataFrame:
    v = cm.drop(columns=[c for c in cm if "TEST" in c])
    assert not any("TEST" in c for c in v), "TEST column reached selection"
    return v


def select(dev: pd.DataFrame) -> tuple[str, bool, pd.DataFrame]:
    assert not any("TEST" in c for c in dev), "TEST column reached selection"
    el = dev[dev.dev_eligible]
    pool = el if len(el) else dev
    ranked = pool.sort_values(SORT[0], ascending=SORT[1], na_position="last")
    return ranked.iloc[0].config_id, bool(len(el)), ranked


def tamper_invariance(cm: pd.DataFrame, pick: str) -> dict:
    t = cm.copy()
    rng = np.random.default_rng(7)
    cols = [c for c in t if "TEST" in c and pd.api.types.is_numeric_dtype(t[c])]
    for c in cols:
        t[c] = rng.normal(0, 1e6, len(t))
    p2, _, _ = select(dev_view(t))
    assert p2 == pick, "selection depends on TEST"
    return {"tampered_test_columns": len(cols), "pick_unchanged": True}


# ---------------- selected-config analysis ----------------
def held_minutes(bk) -> np.ndarray:
    return b5.held_weight(bk)


def pair_rows(c, cell, nb, sb, hn, hs, wb) -> tuple[list, list]:
    """Correlation/overlap + combined-long rows per window for one exec cell."""
    corr_rows, comb_rows = [], []
    s_dec = sb.tr.decision_idx.to_numpy()
    for k, (a, b) in wb.items():
        dn, ds = nb.daily(a, b), sb.daily(a, b)
        dc = dn + ds
        hdn, hds = nb.held_day[a // 1440:b // 1440], sb.held_day[a // 1440:b // 1440]
        mn, ms = hn[a:b] > 0, hs[a:b] > 0
        both, union = int((mn & ms).sum()), int((mn | ms).sum())
        ne = (nb.j0 >= a) & (nb.j0 < b)
        n_dec = nb.tr.decision_idx.to_numpy()[ne]
        near = np.array([np.any(np.abs(s_dec - d) <= 240) for d in n_dec], bool)
        en, es = nb.window(a, b), sb.window(a, b)
        part = trade_part(nb, a, b)
        r = {"config_id": c, "cell": cell, "window": k, "pearson": corr(dn, ds), "spearman": spearman(dn, ds),
             "pearson_both_active": corr(dn[hdn & hds], ds[hdn & hds]), "both_active_days": int((hdn & hds).sum()),
             "s180_exposure_min": int(ms.sum()), "new_exposure_min": int(mn.sum()), "both_exposure_min": both,
             "both_over_new": both / mn.sum() if mn.sum() else np.nan,
             "both_over_s180": both / ms.sum() if ms.sum() else np.nan,
             "jaccard": both / union if union else np.nan,
             "new_entries": int(ne.sum()), "new_entry_while_s180_open": int((hs[nb.j0[ne]] > 0).sum()),
             "entry_decision_pm4h_overlap": float(near.mean()) if len(near) else np.nan,
             "new_positive_days_when_s180_nonpositive": int(((dn > 0) & (ds <= 0)).sum()),
             **days_count(dn, "new_"), **days_count(ds, "s180_"), **days_count(dc, "comb_"),
             "new_top1_share": top_share(part, en["long_net4"], 1), "new_top3_share": top_share(part, en["long_net4"], 3)}
        corr_rows.append(r)
        pc = nb.pnl + sb.pnl
        ps = b5.pnl_stats(pc, a, b)
        cr = {"config_id": c, "cell": cell, "window": k, "net4": en["long_net4"] + es["long_net4"],
              "net8": en["long_net8"] + es["long_net8"], "funding": en["long_funding"] + es["long_funding"],
              "closed": en["long_closed"] + es["long_closed"], "entries": en["long_entries"] + es["long_entries"],
              "mdd": ps["mdd_1m"], "sharpe": ps["sharpe"], **days_count(dc),
              "s180_net4": es["long_net4"], "s180_mdd": es["mdd_1m"], "s180_sharpe": es["sharpe"],
              "new_net4": en["long_net4"]}
        assert abs(pc[a:b].sum() - cr["net4"]) < 1e-6 * max(1, abs(cr["net4"])), "combined net4 != sum"
        cr.update({"delta_net4": cr["net4"] - es["long_net4"], "delta_mdd": cr["mdd"] - es["mdd_1m"],
                   "delta_positive_days": r["comb_pos_days"] - r["s180_pos_days"],
                   "delta_nonzero_days": r["comb_nonzero_days"] - r["s180_nonzero_days"]})
        if cell == cell_tag(*PRIMARY):
            for bl in BLOCKS:
                cr[f"boot{bl}"] = b2.stationary_boot_p05(dc, bl)
                cr[f"s180_boot{bl}"] = b2.stationary_boot_p05(ds, bl)
        comb_rows.append(cr)
    return corr_rows, comb_rows


def window_metrics(e: dict, d: np.ndarray, part: np.ndarray) -> dict:
    return {"net4": e["long_net4"], "net8": e["long_net8"], "gross": e["long_gross"], "funding": e["long_funding"],
            "entries": e["long_entries"], "closed": e["long_closed"], "open_n": e["long_open_n"],
            "open_mtm": e["long_open_mtm"], "win": e["long_win"], "fill": e["fill_notional_rate"],
            "mdd": e["mdd_1m"], "sharpe": e["sharpe"], "exposure_days": e["long_exp_days"],
            "turnover": e["turnover"], **{f"pnl_days_{k.split('_')[0]}": v for k, v in days_count(d).items()},
            "top1": top_share(part, e["long_net4"], 1), "top3": top_share(part, e["long_net4"], 3),
            "active_months": e["active_months"], "pos_month_ratio": e["pos_month_ratio"]}


def funding_hand_check(m, bk) -> float:
    """Independent per-trade PESS funding + 4 bps x entry_weight_frozen cost identity; returns max abs diff."""
    end = m.t[-1] + MIN
    worst = 0.0
    for k in range(len(bk.s)):
        t0 = m.t[bk.j0[k]]
        t1 = m.t[bk.j1[k]] if bk.closed[k] else end
        f = 0.0
        for ft, fr in zip(m.ft, m.fr):
            cf = -bk.s[k] * fr * 1e4 * bk.w[k]
            if cf < 0 and t0 <= ft < (t1 + MIN if bk.closed[k] else end):
                f += cf
            elif cf >= 0 and t0 + MIN <= ft < t1:
                f += cf
        worst = max(worst, abs(f - bk.fund_full[k]))
        cost = bk.net4_full[k] - bk.gross_full[k] - bk.fund_full[k]
        worst = max(worst, abs(cost + 4 * bk.w[k]))
    return worst


# ---------------- parity / prefix ----------------
def parity_s180(R: dict, pb, wb: dict) -> dict:
    old = json.loads((PARENT_DIR / "selected_long.json").read_text(encoding="utf-8"))["LONG_DEV_PICK"]
    assert old["config_id"] == S180_ID
    cells = max(abs(R[(o, p)][w]["long_net4"] - old["cells_net4"][w][f"o{o}_p{p}"]["long"])
                for o, p in CELLS for w in WINDOWS)
    daily = pb.daily(0, pb.m.N)
    bt = max(abs(b2.stationary_boot_p05(daily[wb[w][0] // 1440:wb[w][1] // 1440], bl) - x)
             for w in WINDOWS for bl, x in zip(BLOCKS, old["bootstrap_p05"][w]["long"]))
    ot = pd.read_parquet(PARENT_DIR / "trades/LONG_DEV_PICK.parquet")
    ot = ot[ot.side > 0].reset_index(drop=True)
    nt = pb.tr.reset_index(drop=True)
    cols = ["side", "entry_weight_frozen", "decision_idx", "entry_idx", "entry_px", "exit_decision_idx", "exit_idx",
            "exit_px", "open_at_end"]
    tr_eq = len(ot) == len(nt) and all(np.array_equal(ot[c].to_numpy(), nt[c].to_numpy(), equal_nan=True)
                                                       for c in cols)
    tr_net = float(np.max(np.abs(ot.net4_full.to_numpy() - pb.net4_full))) if tr_eq else np.inf
    od = pd.read_parquet(PARENT_DIR / "daily/LONG_DEV_PICK.parquet")
    dd = float(np.max(np.abs(od.net4_long.to_numpy() - daily))) if len(od) == len(daily) else np.inf
    out = {"cells_max_abs_diff": cells, "boot_max_abs_diff": bt, "trades_equal": bool(tr_eq), "n_trades": len(nt),
           "trades_net4_max_abs_diff": tr_net, "daily_max_abs_diff": dd}
    assert cells == 0 and bt == 0 and tr_eq and tr_net == 0 and dd == 0, out
    return out


def tamper_inputs(m, met, prem, cut):
    """x1.7 on every future market price, metrics, premium and funding rate (strictly after the cut's last input)."""
    n = m.idx(cut)
    end = cut.value
    k = lambda x: np.concatenate([x[:n], x[n:] * 1.7])  # noqa: E731
    mt = b2.Market(m.t, k(m.o), k(m.h), k(m.l), k(m.c), m.v, m.tb, m.ft, np.where(m.ft >= end, m.fr * 1.7, m.fr))
    met2, prem2 = met.copy(), prem.copy()
    fm, fp = met2.available_time.array.asi8 > end, prem2.available_time.array.asi8 > end
    met2.loc[fm, ["oi", "taker_lsr"]] *= 1.7
    prem2.loc[fp, "premium"] *= 1.7
    return mt, met2, prem2


def prefix_check(m, dec4, met, prem, f: dict, sigs: dict, trades: dict, cut=b5.CUT) -> dict:
    """Truncated and future-tampered inputs: prefix features, targets and closed trades equal the full run."""
    mp = b4.prefix_market(m, cut)
    d = dec4[dec4 < mp.N]
    kk = len(d)
    end = cut.value
    assert m.t[mp.N - 1] + MIN == end
    fp = features(mp, d, b5.build_state(mp, d), met[met.available_time.array.asi8 <= end].reset_index(drop=True),
                  prem[prem.available_time.array.asi8 <= end].reset_index(drop=True))
    mt, met2, prem2 = tamper_inputs(m, met, prem, cut)
    ft = features(mt, dec4, b5.build_state(mt, dec4), met2, prem2)
    keys = [x for x in f if isinstance(f[x], np.ndarray)]
    for f2 in (fp, ft):
        for x in keys:
            assert np.array_equal(f[x][:kk], f2[x][:kk], equal_nan=True), f"prefix feature {x}"
    out, n_closed = {}, 0
    for g in GRID:
        c = cid(g)
        sp, stt = lcr_signal(fp, g), lcr_signal(ft, g)
        for s2 in (sp, stt):
            assert np.array_equal(sigs[c]["side"][:kk], s2["side"][:kk]), f"prefix target {c}"
            assert np.array_equal(sigs[c]["w"][:kk], s2["w"][:kk]), f"prefix weight {c}"
        tf = trades[c]
        tp, _ = b2.simulate(mp, "state", d, sp["side"], sp["w"], *_prim_args(), 0, mp.N)
        cl = tp[~tp.open_at_end].reset_index(drop=True)
        assert cl.equals(tf.iloc[:len(cl)].reset_index(drop=True)), f"prefix trades {c}"
        if tp.open_at_end.any():
            r0, r1 = tp[tp.open_at_end].iloc[0], tf.iloc[len(cl)]
            assert all(r0[x] == r1[x] for x in ("side", "decision_idx", "entry_idx", "entry_px")), f"prefix open {c}"
        tt, _ = b2.simulate(mt, "state", dec4, stt["side"], stt["w"], *_prim_args(), 0, m.N)
        done = tf[(~tf.open_at_end) & (tf.exit_idx < mp.N)].reset_index(drop=True)
        assert done.equals(tt.iloc[:len(done)].reset_index(drop=True)), f"tamper trades {c}"
        n_closed += len(cl)
        out[c] = int(len(cl))
    return {"cut": str(cut), "decisions_compared": int(kk), "features_compared": keys,
            "tamper": "x1.7 future o/h/l/c, oi, taker_lsr, premium, funding rate", "configs_checked": len(out),
            "closed_trades_compared": int(n_closed)}


def _prim_args():
    return PRIMARY[0], b2.TTL_TREND, PRIMARY[1]


# ---------------- registry ----------------
def write_registry(fold: pd.DataFrame, sel: dict, hashes: dict, run_id: str, path: Path = REGISTRY) -> dict:
    have = b2.registry_keys(path)
    ih = hashlib.sha256(canonical(hashes).encode()).hexdigest()
    added = skipped = 0
    base = {"run_id": run_id, "parent_run_id": PARENT, "data_cutoff": str(b2.END),
            "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()},
            "costs": "4 bps rt maker flat, 0 slip, PESS funding; 8 bps report-only", "hypothesis": "LONG-CAP-RECOVERY"}

    def put(key_obj, entry):
        nonlocal added, skipped
        key = hashlib.sha256(canonical({"batch": "LCR", **key_obj, "inputs": ih}).encode()).hexdigest()
        if key in have:
            skipped += 1
            return
        registry.record(path, {**entry, "idempotency_key": key, "input_hashes": hashes})
        have.add(key)
        added += 1

    for s, g in fold[fold.window.isin(list(WINDOWS))].groupby("sim_id", sort=False):
        put({"sim_id": s}, {"experiment": f"LCR {s}", "role": "trial", "config": {"sim_id": s, **base},
                            "n_trials": 1, "n_simulations": 1,
                            "result_summary": {f"{r.window}_{x}": getattr(r, x) for r in g.itertuples()
                                               for x in ("net4", "net8", "closed", "fill")}})
    put({"selection": True}, {"experiment": "LCR DEV-only selection", "role": "selection", "config": base,
                              "n_trials": 0, "n_simulations": 0, "result_summary": sel})
    return {"added": added, "skipped": skipped}


# ---------------- report ----------------
def fmt(x, d=1):
    if isinstance(x, (bool, np.bool_)):
        return str(bool(x))
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    try:
        return "nan" if not np.isfinite(x) else f"{x:.{d}f}"
    except TypeError:
        return str(x)


def md_table(df: pd.DataFrame, d=1) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(fmt(v, d) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(out)


def write_report(run_dir: Path, man: dict, wm: pd.DataFrame, cm: pd.DataFrame, comb: pd.DataFrame,
                 co: pd.DataFrame, mon: pd.DataFrame, ranked: pd.DataFrame) -> None:
    pick, P = man["pick"], cm.set_index("config_id").loc[man["pick"]]
    L = [f"# LONG-CAP-RECOVERY {man['run_id']}", "", f"Pick `{pick}` ({man['pick_label']}). "
         f"PASS={man['decision']['PASS']} COMPLEMENT_PASS={man['decision']['COMPLEMENT_PASS']}. "
         f"Eligible {man['n_dev_eligible']}/48. Sims {man['counts']['sims']}. Runtime {man['runtime_sec']}s.", "",
         "## Selected, primary cell (offset 2 / pen 0.5) per window", "",
         md_table(wm[wm.cell == cell_tag(*PRIMARY)].drop(columns=["config_id", "cell"])), "",
         "## Selected, 6 cells net4 per window", "",
         md_table(wm.pivot(index="window", columns="cell", values="net4").reindex(list(ALLWIN)).reset_index()), "",
         "## Bootstrap p05 mean/day (selected, primary)", "",
         md_table(pd.DataFrame([{"window": w, **{f"boot{bl}": P.get(f"{w}_boot{bl}", np.nan) for bl in BLOCKS}}
                                for w in WINDOWS]), 3), "",
         "## Eligibility counts", "", json.dumps(man["eligibility_counts"]), "",
         "## Top 5 by DEV sort (eligible pool if any)", "",
         md_table(ranked.head(5)[["config_id", "dev_eligible", "dev_pos_delta", "dev_score", "dev_cell_floor_pd",
                                  "dev_abs_pearson", "DEV-FULL_comb_mdd"]].merge(
             cm[["config_id", "TEST_net4", "TEST_worst_cell", "TEST_boot60"]], on="config_id"), 3), "",
         "## Top 5 by TEST worst cell (report only)", "",
         md_table(cm.sort_values("TEST_worst_cell", ascending=False).head(5)[
             ["config_id", "dev_eligible", "dev_score", "TEST_worst_cell", "TEST_net4", "TEST_closed",
              "TEST_boot20", "TEST_boot60", "TEST_boot120"]], 3), "",
         "## Combined-long vs S180 (primary)", "",
         md_table(comb[comb.cell == cell_tag(*PRIMARY)][
             ["window", "net4", "s180_net4", "delta_net4", "mdd", "s180_mdd", "delta_mdd", "sharpe", "s180_sharpe",
              "closed", "funding", "pos_days", "delta_positive_days", "delta_nonzero_days", "boot20", "boot60",
              "boot120"]], 2), "",
         "## Correlation / overlap (primary)", "",
         md_table(co[co.cell == cell_tag(*PRIMARY)][
             ["window", "pearson", "spearman", "pearson_both_active", "new_exposure_min", "s180_exposure_min",
              "both_exposure_min", "jaccard", "new_entries", "new_entry_while_s180_open",
              "entry_decision_pm4h_overlap", "new_positive_days_when_s180_nonpositive"]], 3), "",
         "## Monthly net4 (primary, months with new exposure or P&L)", "",
         md_table(mon[(mon.cell == cell_tag(*PRIMARY)) & (mon.new_net4 != 0)][
             ["month", "new_net4", "s180_net4", "combined_net4"]]), "",
         "## Events (selected)", "", json.dumps(man["event_counts"][pick]), "",
         "## Checks", "", "```", json.dumps({k: man[k] for k in ("parity_s180", "prefix_check", "selection_tamper",
                                                                 "funding_hand_check_max_abs", "gross_max",
                                                                 "boundary_crossing_trades")}, indent=1,
                                            default=str), "```"]
    (run_dir / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------- main ----------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-registry", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    code_hash = provenance.file_sha256(Path(__file__))
    run_id = f"LCR-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{code_hash[:8]}"
    run_dir = OUT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=False)          # write-once
    (run_dir / "trades").mkdir()
    (run_dir / "daily").mkdir()
    minutes, met, prem, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes
    wb_main = b3.window_bounds(m)
    wb = {**wb_main, **{k: (m.idx(a), m.idx(b)) for k, (a, b) in SUBWIN.items()}}
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    f = features(m, dec4, st, met, prem)
    print(f"[feat] {time.time()-t0:.0f}s", flush=True)

    assert len(GRID) == 48 and len({cid(g) for g in GRID}) == 48
    sims = [sid(cid(g), o, p) for g in GRID for o, p in CELLS]
    assert len(sims) == 288 and len(set(sims)) == 288
    # S180 comparator, 6 cells, exact parity
    s_sig = s180_signal(st)
    sR, s_pb, s_tr = run_cells(m, dec4, wb, s_sig)
    parity = parity_s180({k: v for k, v in sR.items()}, s_pb, wb_main)
    print(f"[s180] parity {parity} {time.time()-t0:.0f}s", flush=True)

    sigs, ev_counts, rows, boot_rows, fold, R_all, trades, ev_rows = {}, {}, [], [], [], {}, {}, []
    bar = pd.to_datetime(m.t[dec4], utc=True)
    for g in GRID:
        c = cid(g)
        sg = lcr_signal(f, g)
        sigs[c], ev_counts[c] = sg, check_signal(f, sg, g)
        for e in sg["events"]:
            rec = e["outcome"] == "RECOVERY"
            ev_rows.append({"config_id": c, "arm_time": bar[e["arm_idx"]], "rearm": e["rearm"],
                            "recovery_time": bar[e["end_idx"]] if rec else pd.NaT,
                            "expiry_time": bar[e["end_idx"]] if e["outcome"] in ("EXPIRED", "REARMED") else pd.NaT,
                            "exit_target_time": bar[e["exit_idx"]] if e["exit_idx"] >= 0 else pd.NaT,
                            "outcome": e["outcome"], "min_gap": e["min_gap"], "min_ztaker": e["min_ztaker"],
                            "target": int(rec)})
        R, pb, cdaily = run_cells(m, dec4, wb, sg)
        R_all[c] = R
        trades[c] = pb.tr
        row, boot = config_row(c, R, pb, s_pb, wb_main)
        gc, disc, ab, xg, mh = g
        row.update(gap_cut=gc, discount=disc, arm_bars=ab, exit_gap=xg, max_hold_bars=mh, **ev_counts[c],
                   TEST_cells_6of6=bool(row["TEST_cells_pos"] == 6),
                   TEST_boot_all_pos=bool(all(boot[("TEST", bl)] > 0 for bl in BLOCKS)))
        rows.append(row)
        boot_rows += [{"config_id": c, "window": w, "scope": "new_primary", "block_days": bl, "p05_mean_day": x}
                      for (w, bl), x in boot.items()]
        for o, p in CELLS:
            for w in ALLWIN:
                e = R[(o, p)][w]
                fold.append({"sim_id": sid(c, o, p), "config_id": c, "offset": o, "pen": p, "window": w,
                             "net4": e["long_net4"], "net8": e["long_net8"], "gross": e["long_gross"],
                             "funding": e["long_funding"], "entries": e["long_entries"], "closed": e["long_closed"],
                             "open_n": e["long_open_n"], "open_mtm": e["long_open_mtm"], "win": e["long_win"],
                             "fill": e["fill_notional_rate"], "mdd": e["mdd_1m"], "sharpe": e["sharpe"],
                             "exposure_days": e["long_exp_days"], "turnover": e["turnover"],
                             **{f"pnl_days_{x.split('_')[0]}": v for x, v in days_count(
                                 cdaily[(o, p)][1][wb[w][0] // 1440:wb[w][1] // 1440]).items()}})
        print(f"[sim] {c} DEV-A {row['DEV-A_net4']:.0f} DEV-B {row['DEV-B_net4']:.0f} closed "
              f"{row['DEV-FULL_closed']} elig {row['dev_eligible']} {time.time()-t0:.0f}s", flush=True)
    cm = pd.DataFrame(rows)
    fold = pd.DataFrame(fold)
    assert len(fold) == 288 * len(ALLWIN) and fold.sim_id.nunique() == 288

    # selection (DEV-only)
    dev = dev_view(cm)
    sel_hash = hashlib.sha256(pd.util.hash_pandas_object(dev, index=False).values.tobytes()).hexdigest()
    pick, elig, ranked = select(dev)
    tamper = tamper_invariance(cm, pick)
    label = "LCR_DEV_PICK" if elig else "LCR_DEV_BEST_INELIGIBLE"
    gp = next(g for g in GRID if cid(g) == pick)
    print(f"[select] {pick} {label} {time.time()-t0:.0f}s", flush=True)

    # selected config: re-simulate 6 cells, keep books
    sg = sigs[pick]
    wm_rows, corr_rows, comb_rows, mon_rows, boot_sel = [], [], [], [], []
    hs_cache = {}
    gross_max, fund_hand, crossing = 0.0, None, {}
    days = pd.date_range(b2.START, periods=m.N // 1440, freq="D")
    for o, p in CELLS:
        tag = cell_tag(o, p)
        tr, od = b2.simulate(m, "state", dec4, sg["side"], sg["w"], o, b2.TTL_TREND, p, 0, m.N)
        nb = b2.Book(m, tr, od, 0, m.N)
        str_, sod = b2.simulate(m, "state", dec4, s_sig["side"], s_sig["w"], o, b2.TTL_TREND, p, 0, m.N)
        sb = b2.Book(m, str_, sod, 0, m.N)
        for w in ALLWIN:
            assert same(nb.window(*wb[w]), R_all[pick][(o, p)][w]), "re-simulation != first pass"
        hn, hs = held_minutes(nb), held_minutes(sb)
        assert hn.max(initial=0) <= 1 + 1e-12 and hs.max(initial=0) <= 1 + 1e-12
        gm = float((hn + hs).max())
        assert gm <= 2 + 1e-12, "gross > 2"
        gross_max = max(gross_max, gm)
        cnt = np.zeros(m.N + 1, int)
        np.add.at(cnt, nb.j0, 1)
        np.add.at(cnt, np.where(nb.closed, nb.j1 + 1, m.N), -1)
        assert np.cumsum(cnt).max(initial=0) <= 1, "more than one position"
        crossing[tag] = int(sum(((nb.j0 < b_) & (np.where(nb.closed, nb.j1, m.N) >= b_)).sum()
                                for _, (a_, b_) in wb_main.items() if b_ < m.N))
        cr, cb = pair_rows(pick, tag, nb, sb, hn, hs, wb)
        corr_rows += cr
        comb_rows += cb
        dn, ds = nb.daily(0, m.N), sb.daily(0, m.N)
        assert np.array_equal(nb.daily(0, m.N) + sb.daily(0, m.N), dn + ds)
        cmb = (nb.pnl + sb.pnl).reshape(-1, 1440).sum(1)
        assert np.allclose(cmb, dn + ds, rtol=0, atol=1e-9), "combined minute sum != daily sum"
        pd.DataFrame({"day": days, "new_net4": dn, "s180_net4": ds, "combined_net4": dn + ds,
                      "new_held": nb.held_day, "s180_held": sb.held_day}).to_parquet(
            run_dir / f"daily/SELECTED_{tag}.parquet", index=False)
        t2 = tr.assign(config_id=pick, cell=tag, net4_full=nb.net4_full, gross_full=nb.gross_full,
                       funding_full=nb.fund_full)
        t2["decision_time"] = pd.to_datetime(m.t[t2.decision_idx], utc=True)
        t2["entry_time"] = pd.to_datetime(m.t[t2.entry_idx], utc=True)
        t2["exit_time"] = pd.to_datetime(np.where(t2.exit_idx >= 0, m.t[np.maximum(t2.exit_idx, 0)],
                                                  np.iinfo(np.int64).min), utc=True)
        t2.to_parquet(run_dir / f"trades/SELECTED_{tag}.parquet", index=False)
        for w, (a, b) in wb.items():
            e = nb.window(a, b)
            wm_rows.append({"config_id": pick, "cell": tag, "window": w,
                            **window_metrics(e, nb.daily(a, b), trade_part(nb, a, b))})
            if (o, p) == PRIMARY:
                for bl in BLOCKS:
                    x = b2.stationary_boot_p05(nb.daily(a, b), bl)
                    boot_sel.append({"config_id": pick, "window": w, "scope": "selected_new_primary",
                                     "block_days": bl, "p05_mean_day": x})
                    wm_rows[-1][f"boot{bl}"] = x
        ms = days.strftime("%Y-%m")
        mon = pd.DataFrame({"m": ms, "n": dn, "s": ds}).groupby("m").sum()
        mon_rows += [{"config_id": pick, "cell": tag, "month": k, "new_net4": r.n, "s180_net4": r.s,
                      "combined_net4": r.n + r.s} for k, r in mon.iterrows()]
        if (o, p) == PRIMARY:
            fund_hand = funding_hand_check(m, nb)
            assert fund_hand < 1e-9, f"funding hand parity {fund_hand}"
    wm, co, comb, mon = (pd.DataFrame(x) for x in (wm_rows, corr_rows, comb_rows, mon_rows))
    for cb in comb_rows:
        if cb["cell"] == cell_tag(*PRIMARY):
            boot_sel += [{"config_id": pick, "window": cb["window"], "scope": sc, "block_days": bl,
                          "p05_mean_day": cb[f"{pre}boot{bl}"]} for bl in BLOCKS
                         for sc, pre in (("combined_primary", ""), ("s180_primary", "s180_"))]
    pre = prefix_check(m, dec4, met, prem, f, sigs, trades)
    print(f"[prefix] {pre['closed_trades_compared']} trades {time.time()-t0:.0f}s", flush=True)

    # decision
    P = cm.set_index("config_id").loc[pick]
    cell_pos = lambda w: all(R_all[pick][cl][w]["long_net4"] > 0 for cl in CELLS)  # noqa: E731
    pw = {r["window"]: r for r in co_rows_primary(corr_rows)}
    flags = {"dev_eligible_pool": elig, "DEV-A_6of6": cell_pos("DEV-A"), "DEV-B_6of6": cell_pos("DEV-B"),
             "TEST_6of6": cell_pos("TEST"), "TEST_boot_all_pos": bool(P["TEST_boot_all_pos"])}
    cflags = {"JanJul_6of6": cell_pos(COMP_WIN),
              "JanJul_comb_pos_days_gt_s180": bool(pw[COMP_WIN]["comb_pos_days"] > pw[COMP_WIN]["s180_pos_days"])}
    decision = {"pick": pick, "label": label, **flags, "PASS": all(flags.values()), **cflags,
                "COMPLEMENT_PASS": all(cflags.values()),
                "verdict": ("PASS" if all(flags.values()) else "FAIL") + (
                    "" if elig else " (LCR_DEV_BEST_INELIGIBLE)"),
                "test_boot": {bl: float(P[f"TEST_boot{bl}"]) for bl in BLOCKS}}
    elig_counts = {k: int(cm[k].sum()) for k in ("dev_elig_cells", "dev_elig_closed", "dev_elig_fill",
                                                 "dev_elig_posdays", "dev_eligible")}

    hashes = {"batch5_code": provenance.file_sha256(B5_PATH), "batch2_code": provenance.file_sha256(B2_PATH),
              "batch5_selected_long": provenance.file_sha256(PARENT_DIR / "selected_long.json"),
              "batch5_trades_long": provenance.file_sha256(PARENT_DIR / "trades/LONG_DEV_PICK.parquet"),
              "batch5_daily_long": provenance.file_sha256(PARENT_DIR / "daily/LONG_DEV_PICK.parquet"),
              **{k: v for k, v in b5.input_hashes().items() if k != "code"}, "code": code_hash}
    nat = lambda x: pd.to_datetime(np.where(x > np.iinfo(np.int64).min, x, np.iinfo(np.int64).min), utc=True)  # noqa
    fs = pd.DataFrame({"bar_time": bar, "T": pd.to_datetime(f["T"], utc=True), **{x: f[x] for x in FEAT},
                       "r4": f["r4"], "dOI24": f["dOI24"], "taker": f["taker"], "prem4": f["prem4"],
                       "prem_n": f["prem_n"], "fund": f["fund"], "dSVI": f["dSVI"], "w": f["w"],
                       "oi_T_available_time": nat(f["oi_T_avail"]), "oi_24_available_time": nat(f["oi_24_avail"]),
                       "taker_available_time": nat(f["taker_avail"]),
                       "prem_last_available_time": nat(f["prem_last_avail"]), "funding_time": nat(f["fund_time"]),
                       **{f"target|{c}": s["side"] for c, s in sigs.items()}})
    fs.to_parquet(run_dir / "feature_state.parquet", index=False)
    pd.DataFrame(ev_rows).to_parquet(run_dir / "events.parquet", index=False)
    fold.to_parquet(run_dir / "fold_metrics.parquet", index=False)
    cm.to_parquet(run_dir / "config_metrics.parquet", index=False)
    pd.DataFrame(boot_rows + boot_sel).to_parquet(run_dir / "bootstrap.parquet", index=False)
    co.to_parquet(run_dir / "correlation_overlap.parquet", index=False)
    comb.to_parquet(run_dir / "combined_long_metrics.parquet", index=False)
    mon.to_parquet(run_dir / "monthly.parquet", index=False)
    wm.to_parquet(run_dir / "selected_window_metrics.parquet", index=False)
    sel = {"pick": pick, "label": label, "eligible_pool": elig, "pre_selection_dev_frame_sha256": sel_hash,
           "sort_keys": dict(zip(SORT[0], SORT[1])), "eligibility_counts": elig_counts,
           "ranked": ranked.head(10)[["config_id", "dev_eligible"] + SORT[0][:-1]].to_dict("records"),
           "pick_dev_values": {k: P[k] for k in SORT[0][:-1] + ["dev_eligible", "dev_elig_cells", "dev_elig_closed",
                                                                "dev_elig_fill", "dev_elig_posdays"]},
           "tamper": tamper}
    (run_dir / "selection.json").write_text(json.dumps(sel, indent=2, default=str), encoding="utf-8")
    (run_dir / "decision.json").write_text(json.dumps(decision, indent=2, default=str), encoding="utf-8")
    with (run_dir / "runs.jsonl").open("w", encoding="utf-8") as fh:
        for s, g in fold[fold.window.isin(list(WINDOWS))].groupby("sim_id", sort=False):
            fh.write(json.dumps({"sim_id": s, **{f"{r.window}_net4": r.net4 for r in g.itertuples()},
                                 "selected": s.startswith(pick + "|")}) + "\n")
    man = {"run_id": run_id, "parent_run_id": PARENT, "created_utc": datetime.now(timezone.utc).isoformat(),
           "spec": "scratchpad codex_newlong.md section 2 (Codex 01a12515-36a1-7400-a078-adf4cce7e936)",
           "name": "LONG-CAP-RECOVERY", "frozen_hypothesis_and_interpretations": __doc__,
           "source": "Binance USD-M BTCUSDT local: artifacts DEV (<2026-01-01) + r2_54 stageb_snapshot TEST",
           "windows": {k: [str(a), str(b)] for k, (a, b) in ALLWIN.items()}, "data_cutoff": str(b2.END),
           "counts": {"logical": len(GRID), "sims": len(sims), "n_trials": len(sims), "s180_comparator_sims": 6},
           "max_hold_basis": "target activation decision (not fill)", "pick": pick, "pick_label": label,
           "pick_params": dict(zip(("gap_cut", "discount", "arm_bars", "exit_gap", "max_hold_bars"), gp)),
           "n_dev_eligible": int(cm.dev_eligible.sum()), "eligibility_counts": elig_counts, "decision": decision,
           "event_counts": ev_counts, "parity_s180": parity, "prefix_check": pre, "selection_tamper": tamper,
           "funding_hand_check_max_abs": fund_hand, "gross_max": gross_max, "boundary_crossing_trades": crossing,
           "feature_coverage": {x: int(np.isfinite(f[x]).sum()) for x in FEAT} | {"decisions": int(len(dec4))},
           "input_sha256": hashes, "git": b2.git_state(), "runtime_sec": None}
    man["runtime_sec"] = round(time.time() - t0, 1)
    write_report(run_dir, man, wm, cm, comb, co, mon, ranked)
    if not args.no_registry:
        man["registry"] = write_registry(fold, {"pick": pick, "label": label, "batch_trials": 288,
                                                "batch_logical": 48, "PASS": decision["PASS"],
                                                "COMPLEMENT_PASS": decision["COMPLEMENT_PASS"]}, hashes, run_id)
        print(f"[registry] {man['registry']}", flush=True)
    man["runtime_sec"] = round(time.time() - t0, 1)
    (run_dir / "manifest.json").write_text(json.dumps(man, indent=2, default=str), encoding="utf-8")
    print(f"[done] {run_id} pick={pick} PASS={decision['PASS']} COMP={decision['COMPLEMENT_PASS']} "
          f"{man['runtime_sec']}s", flush=True)
    return run_dir


def same(a: dict, b: dict) -> bool:
    return a.keys() == b.keys() and all(x == y or (x != x and y != y) for x, y in zip(a.values(), b.values()))


def co_rows_primary(rows: list) -> list:
    return [r for r in rows if r["cell"] == cell_tag(*PRIMARY)]


if __name__ == "__main__":
    main()
