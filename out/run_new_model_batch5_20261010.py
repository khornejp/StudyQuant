"""Batch-5 (2026-10-10): G3-NORM-ADAPT.

Spec: scratchpad codex_batch5.md section 3 (Codex session 01a124c5-ad76-7d91-a832-42fbf0b4d6b7). Parent run
NM-B4-20261010T073851Z-ec7d5409 (strict-control parity source).
Frozen hypothesis: already-normalised score (+-0.50) / SVI (+-0.10) keep their fixed boundaries; the raw funding
percentile is replaced by a robust-z raw boundary over the previous 90 funding events
(raw_thr = median90 + c*1.4826*MAD90, c in {-0.5, 0}); only the target vol adapts (trailing quantile of sigma_ann);
a 50/50 F42 + S180 long ensemble dilutes long profit concentration. Maker round trip 4 bps fixed.

Engine: Batch-2 simulate/Book/bootstrap/G features, Batch-3 eligible/dev_score/adapt_score/verdict/diagnostics/
window_bounds, Batch-4 trailing_q/prefix_market/window_checks are imported unchanged (importlib; file hashes = inputs).
All main results use strict funding semantics: an event is usable only if funding_time < T (controls included).
Interpretations (spec silent or ambiguous; most causal reading chosen):
  * T = market_time[dec4] + 1m, dec4 = 239 + 240k; score/SVI/sigma = Batch-2 G features (sigma = previous 180 4h
    log returns, current excluded; SVI includes the bar closing at T).
  * funding: j_t = max{j: ft_j < T}; median90/MAD90 over events j-90..j-1 (event j excluded), min 30 finite
    (same sample as Batch-1 trailing_robust_z); raw_thr_j(c) = median90 + c*1.4826*MAD90; gate = fr_j >= raw_thr_j.
    MAD90 == 0 keeps the formula (thr = median); strict controls keep Batch-3 fz (MAD 0 -> NaN -> short blocked).
  * tv_t(W,q) = linear quantile of sigma_ann over the previous 6W 4h decisions (= [T-W, T), current excluded),
    NaN unless all 6W finite. V-ENS weight = mean of the four (W,q) weights; NaN (flat) unless all four finite.
  * long needs score/SVI/weight ready; short additionally funding ready. Not ready -> flat, weight 0.
  * long pool de-duplication over c: long legs differ across c (the short gate changes path timing in state_flat),
    so the c=0.0 sim is the representative (difference reported in manifest 'long_c_dedupe').
  * LONG_ENS_{V}: daily/1m long P&L = 0.5 x F42(c=0) long + 0.5 x S180(c=0) long, every exec cell; closed and entries
    = sum of both sleeves' counts; exposure/turnover/fill weights x0.5; MDD/Sharpe from the combined 1m P&L.
  * side eligibility = Batch-3 rule restricted to one side: offset 2/5 pen 0.5 DEV-FULL/A/B side net4 > 0; primary
    DEV-FULL side closed >= 20 or side exposure >= 180d; primary DEV-FULL side fill_notional_rate >= 0.10 (orders of
    that side). Side ties: lower primary DEV-FULL side MDD, lower side turnover, config id.
  * RESELECTED pools: eligible (or side-eligible) configs; whole pool only if none is eligible (flagged).
  * side verdicts (side labels; Batch-3 rule restricted to one side): S_PROFIT_PASS, S_LOW_N (primary TEST side
    closed < 10), S_STRONG (TEST side boot60 p05 > 0), S_ROBUST_PASS (4 windows x 6 cells side net4 > 0),
    S_ROBUST_STRONG. Core picks also carry the Batch-3 two-side verdict.
  * combined book (derived, no simulation): LONG_DEV_PICK long sleeve + SHORT_DEV_PICK short sleeve, P&L summed;
    each sleeve weight <= 1, gross up to 2 when both sleeves are open at once (overlap minutes reported).
  * prefix checks run on the real data at cut 2026-01-01: state on a truncated market and on a future-tampered
    market must equal the full state; closed trades of a truncated simulation must equal the full-run rows.
  * picks' trades/daily come from the stored primary trades (no re-simulation).
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
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
B3_PATH = ROOT / "out/run_new_model_batch3_20261010.py"
B4_PATH = ROOT / "out/run_new_model_batch4_20261010.py"
b4 = _load("nm_b4", B4_PATH)
b3, b2 = b4.b3, b4.b2
OUT_BASE = ROOT / "out/new_model_batch5_20261010"
PARENT = "NM-B4-20261010T073851Z-ec7d5409"
PARENT_DIR = ROOT / "out/new_model_batch4_20261010" / PARENT
REGISTRY = b2.REGISTRY
MIN, DAY = b2.MIN, b2.DAY
WINDOWS, SIDES, SEED, NBOOT, BLOCKS = b2.WINDOWS, b2.SIDES, b2.SEED, b2.NBOOT, b2.BLOCKS
OFFSETS, PENS, PRIMARY, WIN_DAYS = b3.OFFSETS, b3.PENS, b3.PRIMARY, b3.WIN_DAYS
DEV3 = ("DEV-FULL", "DEV-A", "DEV-B")
DB, G_SVI, NF, MINF = 0.50, 0.10, 90, 30
STRUCTS = {"F42": ((6, 18, 42), 42), "F180": ((6, 18, 42), 180), "S42": ((42, 168, 504), 42),
           "S180": ((42, 168, 504), 180)}
CS = (-0.5, 0.0)
INNER = ((180, 0.50), (180, 0.65), (365, 0.50), (365, 0.65))
VPOL = tuple(f"W{W}-P{int(round(q * 100))}" for W, q in INNER) + ("V-ENS",)
CORE = [dict(struct=s, c=c, vol=v) for s in STRUCTS for c in CS for v in VPOL]
CONTROLS = {"CONTROL_B3_DEV_PICK_STRICT": dict(struct="F180", c=0.0, tv=0.40, b3_gate="fz>=0"),
            "CONTROL_B3_RESELECTED_STRICT": dict(struct="S180", c=-0.5, tv=0.40, b3_gate="fz>=-0.5")}
CONTROL_REF = {"CONTROL_B3_DEV_PICK_STRICT": (15416.5733, 4069.5464, 2589.6337),
               "CONTROL_B3_RESELECTED_STRICT": (24046.9657, 6227.0510, 4288.2397)}   # DEV-FULL, DEV-B, TEST (spec)
ENS = {f"LONG_ENS_{v}": v for v in VPOL}
ENS_LEGS, ENS_C = ("F42", "S180"), 0.0
TEST_FLAG = "TEST-selected; never independent OOS"
CUT = pd.Timestamp("2026-01-01", tz="UTC")


def cid(p: dict) -> str:
    return f"G5-{p['struct']}-c{p['c']:+.1f}-{p['vol']}"


def sid(c: str, off, pen) -> str:
    return f"{c}|offset={off}|pen={pen}"


# ---------------- causal state ----------------
def fund_idx(m, T: np.ndarray) -> np.ndarray:
    """Single funding accessor for candidates and controls: j_t = max{j: funding_time_j < T} (strict)."""
    j = np.searchsorted(m.ft, T, "left") - 1
    assert np.all(m.ft[j[j >= 0]] < T[j >= 0]), "assert3: funding event not strictly before T"
    return j


def funding_stats(fr: np.ndarray, n: int = NF, min_obs: int = MINF):
    """median / MAD of fr[j-n:j] (event j excluded), NaN unless >= min_obs finite samples."""
    med, mad = np.full(len(fr), np.nan), np.full(len(fr), np.nan)
    for j in range(len(fr)):
        s = fr[max(0, j - n):j]
        s = s[np.isfinite(s)]
        if len(s) >= min_obs:
            med[j] = np.median(s)
            mad[j] = np.median(np.abs(s - med[j]))
    return med, mad


def raw_thr(med, mad, c: float) -> np.ndarray:
    return med + c * 1.4826 * mad


def vol_weights(sig: np.ndarray) -> tuple[dict, dict]:
    """tv_t(W,q) over the previous 6W decisions and weight min(1, tv/sigma); V-ENS = mean of the four."""
    tv, w = {}, {}
    with np.errstate(invalid="ignore", divide="ignore"):
        for (W, q), v in zip(INNER, VPOL):
            tv[v] = b4.trailing_q(sig, 6 * W, q)
            w[v] = np.where(np.isfinite(tv[v]) & np.isfinite(sig) & (sig > 0), np.minimum(1.0, tv[v] / sig), np.nan)
    w["V-ENS"] = np.mean([w[v] for v in VPOL[:4]], axis=0)        # NaN unless all four finite
    return tv, w


def build_state(m, dec4) -> dict:
    T = m.t[dec4] + MIN
    nx = dec4 + 1 < m.N
    assert np.all(m.t[dec4[nx] + 1] == T[nx]), "assert1: T != close bar + 1m"                       # 1
    assert np.all(np.diff(T) == 4 * 60 * MIN), "4h decisions not contiguous"
    assert np.all(np.diff(m.ft) > 0), "funding times not strictly increasing"
    fe = SimpleNamespace(m=m, h4=dec4)
    b2.Features.g_prep(fe)
    G = fe.G
    sig = G["sig_ann"]
    j = fund_idx(m, T)                                                                               # 3
    med, mad = funding_stats(m.fr)
    jj, ok = np.maximum(j, 0), j >= 0
    tv, w = vol_weights(sig)
    fz90 = b2.b1.trailing_robust_z(m.fr, NF, MINF)
    return dict(T=T, j=j, score={k: G["score"][k] for k in ((6, 18, 42), (42, 168, 504))}, svi=dict(G["svi"]),
                sig=sig, fund=np.where(ok, m.fr[jj], np.nan), ftime=np.where(ok, m.ft[jj], np.iinfo(np.int64).min),
                med=np.where(ok, med[jj], np.nan), mad=np.where(ok, mad[jj], np.nan),
                fz=np.where(ok, fz90[jj], np.nan), tv=tv, w=w, ev_med=med, ev_mad=mad, fz90=fz90)


def core_signal(st: dict, p: dict) -> dict:
    trend, sw = STRUCTS[p["struct"]]
    sc, svi, wv = st["score"][trend], st["svi"][sw], st["w"][p["vol"]]
    thr = raw_thr(st["med"], st["mad"], p["c"])
    with np.errstate(invalid="ignore"):
        r4 = np.isfinite(sc) & np.isfinite(svi) & np.isfinite(wv)
        lng = r4 & (sc >= DB) & (svi >= G_SVI)
        base_s = r4 & (sc <= -DB) & (svi <= -G_SVI)
        rf = (st["j"] >= 0) & np.isfinite(st["fund"]) & np.isfinite(thr)
        gate = rf & (st["fund"] >= thr)
    sht = base_s & gate
    assert not (lng & sht).any(), "assert10: simultaneous long/short"                                # 10
    side = np.where(lng, 1, np.where(sht, -1, 0))
    w = np.where(side != 0, wv, 0.0)
    assert np.all(side[~r4] == 0) and np.all(w[~r4] == 0) and np.all(side[~rf] >= 0), "assert9"    # 9
    assert np.all(np.isfinite(w)) and np.all(w[side != 0] > 0) and np.all(w <= 1)
    return dict(side=side, w=w, des=np.where(lng, 1, np.where(base_s, -1, 0)), gate=gate, thr=thr)


def control_signal(st: dict, p: dict) -> dict:
    """Batch-3 fixed G3 (tv .40, fz gate, state_flat) on the same strict accessor j_t."""
    trend, sw = STRUCTS[p["struct"]]
    des = b3.base_side(st["score"][trend], st["svi"][sw])
    with np.errstate(invalid="ignore"):
        gate = st["fz"] >= p["c"]
        w = np.nan_to_num(np.minimum(1.0, p["tv"] / st["sig"]))
    side, ok = b3.g3_signal(des, gate, "state_flat")
    assert ok is None
    return dict(side=side, w=w, des=des, gate=gate)


def check_identities(m, dec4, st: dict, check: int = 300) -> dict:
    """assert 2/5/6/7: sample windows, manual raw funding threshold, score/SVI raw-unit identities."""
    T, rng = st["T"], np.random.default_rng(0)
    # 2: score/sigma/SVI inputs are closes with index <= dec4 (close time <= T); sigma excludes the current return
    c4 = m.c[dec4]
    lr = np.diff(np.log(c4), prepend=np.nan)
    sig4 = st["sig"] / np.sqrt(6 * 365)
    i = rng.choice(np.flatnonzero(np.isfinite(sig4)), check, replace=False)
    for k in i:
        assert np.isclose(sig4[k], np.std(lr[k - 180:k], ddof=1), rtol=1e-9), "assert2 sigma sample"
    # 7: score >= db  <=> mean_L clip(r_L/(sig sqrt L)) >= db ; unclipped rows: score*sig == mean(r_L/sqrt L)
    n7 = 0
    for trend, sc in st["score"].items():
        r = np.array([np.log(c4 / b2.shift(c4, L)) / np.sqrt(L) for L in trend])
        z = r / sig4
        unc = np.all(np.abs(z) < 3, axis=0) & np.isfinite(sc)
        assert np.allclose(sc[unc] * sig4[unc], r[:, unc].mean(0), rtol=1e-9, atol=1e-15), "assert7 score hurdle"
        n7 += int(unc.sum())
    for W, svi in st["svi"].items():
        r2 = lr ** 2
        P, N = b2.roll(np.where(lr > 0, r2, 0.0), W, "sum"), b2.roll(np.where(lr < 0, r2, 0.0), W, "sum")
        f = np.isfinite(svi)
        assert np.allclose(svi[f] * (P[f] + N[f] + 1e-12), P[f] - N[f], rtol=1e-9, atol=1e-18), "assert7 SVI"
        with np.errstate(invalid="ignore"):
            assert np.array_equal(svi[f] >= G_SVI, (P[f] - N[f]) >= G_SVI * (P[f] + N[f] + 1e-12)) or \
                np.mean((svi[f] >= G_SVI) != ((P[f] - N[f]) >= G_SVI * (P[f] + N[f] + 1e-12))) < 1e-4
    # 5: vol quantile sample = previous 6W decisions = [T-W, T)
    for (W, q), v in zip(INNER, VPOL):
        n = 6 * W
        ri = np.flatnonzero(np.isfinite(st["tv"][v]))
        assert np.all(ri >= n) and np.all(T[ri - n] >= T[ri] - W * DAY) and np.all(T[ri - 1] < T[ri]), "assert5"
        for k in rng.choice(ri, 100, replace=False):
            assert np.isclose(st["tv"][v][k], np.quantile(st["sig"][k - n:k], q), rtol=0, atol=1e-12), "assert5 q"
    # 3/4/6: funding sample excludes event j and every event at/after T; manual threshold
    j = st["j"]
    ok = np.flatnonzero((j >= 0) & np.isfinite(st["med"]))
    for k in rng.choice(ok, check, replace=False):
        jj = j[k]
        s = m.fr[max(0, jj - NF):jj]
        assert m.ft[jj] < T[k] and np.all(m.ft[max(0, jj - NF):jj] < m.ft[jj]), "assert4"
        med, mad = np.median(s), np.median(np.abs(s - np.median(s)))
        for c in CS:
            assert np.isclose(raw_thr(st["med"][k], st["mad"][k], c), med + c * 1.4826 * mad, rtol=0, atol=1e-15)
    em, ea = st["ev_med"], st["ev_mad"]
    f = np.isfinite(em) & (ea > 0)
    assert np.allclose((m.fr[f] - em[f]) / (1.4826 * ea[f]), st["fz90"][f], rtol=1e-9, atol=1e-9), "fz identity"
    return {"assert7_unclipped_rows": n7, "funding_events_mad0": int(np.sum(np.isfinite(em) & (ea == 0))),
            "decisions_mad0": int(np.sum(st["mad"] == 0))}


def prefix_checks(m, dec4, st: dict, sigs: dict, cut=CUT) -> dict:
    """asserts 13/14: future tamper leaves the prefix state unchanged; truncated simulation == full-run prefix."""
    mp = b4.prefix_market(m, cut)
    d = dec4[dec4 < mp.N]
    k = len(d)
    stp = build_state(mp, d)
    tamp_c, tamp_fr = m.c.copy(), m.fr.copy()
    tamp_c[mp.N:] *= 1.7
    tamp_fr[m.ft >= cut.value] = -0.05
    mt = b2.Market(m.t, m.o, m.h, m.l, tamp_c, m.v, m.tb, m.ft, tamp_fr)
    stt = build_state(mt, dec4)
    keys = ("fund", "med", "mad", "fz", "sig")
    for s2 in (stp, stt):
        for x in keys:
            assert np.array_equal(st[x][:k], s2[x][:k], equal_nan=True), f"assert13 {x}"
        for x in ("score", "svi", "tv", "w"):
            for y in st[x]:
                assert np.array_equal(st[x][y][:k], s2[x][y][:k], equal_nan=True), f"assert13 {x} {y}"
    out = {}
    for c, (fn, p) in sigs.items():
        full, pre = fn(st, p), fn(stp, p)
        for x in ("side", "w"):
            assert np.array_equal(full[x][:k], pre[x], equal_nan=True), f"assert13 signal {c} {x}"
        tf, _ = b2.simulate(m, "state", dec4, full["side"], full["w"], 2, b2.TTL_TREND, 0.5, 0, m.N)
        tp, _ = b2.simulate(mp, "state", d, pre["side"], pre["w"], 2, b2.TTL_TREND, 0.5, 0, mp.N)
        cl = tp[~tp.open_at_end].reset_index(drop=True)
        assert len(cl) and cl.equals(tf.iloc[:len(cl)].reset_index(drop=True)), f"assert14 trades {c}"      # 14
        if tp.open_at_end.any():
            r0, r1 = tp[tp.open_at_end].iloc[0], tf.iloc[len(cl)]
            assert all(r0[x] == r1[x] for x in ("side", "decision_idx", "entry_idx", "entry_px")), f"assert14 open {c}"
        out[c] = {"prefix_closed_trades_equal": int(len(cl)), "prefix_open": int(tp.open_at_end.sum())}
    return {"cut": str(cut), "decisions_compared": int(k), "configs": out}


# ---------------- metrics helpers ----------------
def side_fill(od: pd.DataFrame, a: int, b: int, s: int) -> float:
    mk = (od.decision_idx >= a) & (od.decision_idx < b) & (np.sign(od.side) == s)
    n = float(od.weight[mk].sum())
    return float(od.weight[mk & od.filled].sum()) / n if n > 0 else np.nan


def held_weight(bk) -> np.ndarray:
    dif = np.zeros(bk.m.N + 1)
    np.add.at(dif, bk.j0, bk.w)
    np.add.at(dif, np.where(bk.closed, bk.j1 + 1, bk.hi), -bk.w)
    return np.cumsum(dif)[:bk.m.N]


def pnl_stats(pnl: np.ndarray, a: int, b: int) -> dict:
    eq = np.concatenate([[0.0], np.cumsum(pnl[a:b])])
    daily = pnl[a:b].reshape(-1, 1440).sum(1)
    sd = daily.std(ddof=1)
    return {"mdd_1m": float((np.maximum.accumulate(eq) - eq).max()),
            "sharpe": float(daily.mean() / sd * np.sqrt(365)) if sd > 0 else np.nan}


def side_eligible(R: dict, s: str, sw: dict, fill: float) -> bool:
    p = sw["DEV-FULL"]
    ok = all(R[(o, 0.5)][w][f"{s}_net4"] > 0 for o in OFFSETS for w in DEV3)
    ok &= p[f"{s}_closed"] >= 20 or p[f"{s}_exp_days"] >= 180
    return bool(ok and fill >= 0.10)


def side_dev_score(R: dict, s: str) -> float:
    return min(R[(o, 0.5)][w][f"{s}_per_day"] for o in OFFSETS for w in ("DEV-A", "DEV-B"))


def side_test_score(R: dict, s: str) -> float:
    return min(R[(o, p)]["TEST"][f"{s}_per_day"] for o in OFFSETS for p in PENS)


def side_verdict(R: dict, s: str, elig: bool, boot60: float) -> dict:
    profit = elig and all(R[(o, 0.5)]["TEST"][f"{s}_net4"] > 0 for o in OFFSETS)
    low_n = R[PRIMARY]["TEST"][f"{s}_closed"] < 10
    strong = profit and not low_n and boot60 > 0
    robust = all(R[(o, p)][w][f"{s}_net4"] > 0 for o in OFFSETS for p in PENS for w in WINDOWS)
    f = {"S_PROFIT_PASS": profit, "S_LOW_N": low_n, "S_STRONG": strong, "S_ROBUST_PASS": robust,
         "S_ROBUST_STRONG": robust and boot60 > 0}
    return {**{k: bool(v) for k, v in f.items()}, "side_verdict": "+".join(k for k, v in f.items() if v) or "FAIL"}


def rank(df: pd.DataFrame, key: str, mdd: str, turn: str) -> pd.DataFrame:
    return df.sort_values([key, mdd, turn, "config_id"], ascending=[False, True, True, True])


def ensemble_R(Ra: dict, Rb: dict) -> dict:
    """0.5/0.5 long sleeves: additive long fields x0.5, counts summed."""
    out = {}
    for cell in Ra:
        out[cell] = {}
        for w in WINDOWS:
            a, b = Ra[cell][w], Rb[cell][w]
            e = {"days": a["days"]}
            for x in ("net4", "net8", "gross", "funding", "exp_days", "per_day", "open_mtm"):
                e[f"long_{x}"] = 0.5 * (a[f"long_{x}"] + b[f"long_{x}"])
            for x in ("closed", "entries", "open_n"):
                e[f"long_{x}"] = int(a[f"long_{x}"] + b[f"long_{x}"])
            out[cell][w] = e
    return out


# ---------------- registry / hashes ----------------
def input_hashes() -> dict:
    h = b2.input_hashes()
    h["batch2_code"] = h.pop("code")
    h["batch3_code"] = provenance.file_sha256(B3_PATH)
    h["batch4_code"] = provenance.file_sha256(B4_PATH)
    h["batch4_manifest"] = provenance.file_sha256(PARENT_DIR / "manifest.json")
    h["batch4_controls_strict"] = provenance.file_sha256(PARENT_DIR / "controls_strict.parquet")
    h["code"] = provenance.file_sha256(Path(__file__))
    return h


def write_registry(g: pd.DataFrame, ens: pd.DataFrame, sel: dict, hashes: dict, run_id: str,
                   path: Path = REGISTRY) -> dict:
    have = b2.registry_keys(path)
    ih = hashlib.sha256(canonical(hashes).encode()).hexdigest()
    added = skipped = 0
    base = {"run_id": run_id, "parent_run_id": PARENT, "data_cutoff": str(b2.END),
            "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()},
            "costs": "4 bps rt maker flat, 0 slip, PESS funding; 8 bps report-only",
            "hypothesis": "G3-NORM-ADAPT", "funding_semantics": "strict funding_time < T"}

    def put(key_obj, entry):
        nonlocal added, skipped
        key = hashlib.sha256(canonical({"batch": "NM-B5", **key_obj, "inputs": ih}).encode()).hexdigest()
        if key in have:
            skipped += 1
            return
        registry.record(path, {**entry, "idempotency_key": key, "input_hashes": hashes})
        have.add(key)
        added += 1

    for r in g.to_dict("records"):
        ctl = r["config_id"].startswith("CONTROL")
        put({"sim_id": r["sim_id"]}, {
            "experiment": f"NM-B5 G3-NORM-ADAPT {r['sim_id']}", "role": "control_strict" if ctl else "trial",
            "config": {"sim_id": r["sim_id"], **base}, "n_trials": 0 if ctl else 1, "n_simulations": 1,
            "result_summary": {f"{w}_{k}": r[f"{w}_{k}"] for w in WINDOWS
                               for k in ("net4", "net8", "long_net4", "short_net4", "closed", "fill_notional_rate")}})
    for r in ens.to_dict("records"):
        if r["window"] != "TEST":
            continue
        put({"ensemble": r["config_id"]}, {
            "experiment": f"NM-B5 derived long ensemble {r['config_id']}", "role": "trial_derived",
            "config": {"config_id": r["config_id"], "legs": "0.5 F42(c=0) long + 0.5 S180(c=0) long", **base},
            "n_trials": 1, "n_simulations": 0,
            "result_summary": {"TEST_long_net4": r["long_net4"], "TEST_long_closed": r["long_closed"]}})
    put({"selection": True}, {"experiment": "NM-B5 selection (DEV_PICK x3 + RESELECTED x3)", "role": "selection",
                              "config": base, "n_trials": 0, "n_simulations": 0,
                              "result_summary": {"batch_trials": 245, "batch_simulations": 252,
                                                 "picks": {k: v["config_id"] for k, v in sel.items()}}})
    return {"added": added, "skipped": skipped}


# ---------------- main ----------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-registry", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    code_hash = provenance.file_sha256(Path(__file__))
    run_id = f"NM-B5-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{code_hash[:8]}"
    run_dir = OUT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=False)          # write-once
    minutes, met, prem, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes, met, prem
    wb = b3.window_bounds(m)                                                                          # 19
    dec4, d1 = np.arange(239, m.N, 240), np.arange(1439, m.N, 1440)
    st = build_state(m, dec4)
    ident = check_identities(m, dec4, st)
    print(f"[load] N={m.N} dec4={len(dec4)} funding={len(m.ft)} {ident} {time.time()-t0:.0f}s", flush=True)

    configs, sig = {}, {}
    for p in CORE:
        assert set(p) == {"struct", "c", "vol"}, "assert8: raw-unit cutoff in adaptive config"         # 8
        configs[cid(p)] = p
        sig[cid(p)] = core_signal(st, p)
    masks = b3.gate_masks(*b4.gate_inputs_strict(m, dec4, d1))
    for lab, p in CONTROLS.items():
        configs[lab] = p
        sig[lab] = control_signal(st, p)
        assert np.array_equal(sig[lab]["gate"], masks[p["b3_gate"]]), "assert11: control accessor != B4 strict"  # 11
    assert len(configs) == 42
    pre = prefix_checks(m, dec4, st, {c: ((core_signal if c.startswith("G5") else control_signal), configs[c])
                                      for c in (cid(CORE[0]), cid(CORE[-1]), *CONTROLS)})
    print(f"[prefix] {pre} {time.time()-t0:.0f}s", flush=True)

    # simulations
    rows, fold, diag, R_all, prim, SW, SF, dly = [], [], [], {}, {}, {}, {}, {}
    for n_, (c, p) in enumerate(configs.items()):
        s = sig[c]
        R = {}
        for off in OFFSETS:
            for pen in PENS:
                tr, od = b2.simulate(m, "state", dec4, s["side"], s["w"], off, b2.TTL_TREND, pen, 0, m.N)
                book = b2.Book(m, tr, od, 0, m.N)
                ev = {k: book.window(a, b) for k, (a, b) in wb.items()}
                for k in WINDOWS:
                    assert abs(ev[k]["net4"] - ev[k]["long_net4"] - ev[k]["short_net4"]) < 1e-6 * max(1, abs(ev[k]["net4"])), "assert16"
                R[(off, pen)] = ev
                s_id = sid(c, off, pen)
                row = {"sim_id": s_id, "config_id": c, "struct": p["struct"], "c": p["c"], "vol": p.get("vol", "tv0.40"),
                       "role": "control_strict" if c.startswith("CONTROL") else "trial", "offset": off, "pen_bps": pen}
                for k, d in ev.items():
                    row.update({f"{k}_{x}": v for x, v in d.items()})
                    fold.append({"sim_id": s_id, "config_id": c, "offset": off, "pen_bps": pen, "window": k, **d})
                for k, d in b3.diagnostics(tr, dec4, s["des"], s["gate"], wb).items():
                    mk = (dec4 >= wb[k][0]) & (dec4 < wb[k][1])
                    side = s["side"]
                    diag.append({"sim_id": s_id, "config_id": c, "offset": off, "pen_bps": pen, "window": k, **d,
                                 "long_dec": int(((side > 0) & mk).sum()), "short_dec": int(((side < 0) & mk).sum()),
                                 "flat_dec": int(((side == 0) & mk).sum()),
                                 "short_entries": ev[k]["short_entries"], "short_closed": ev[k]["short_closed"],
                                 "long_entries": ev[k]["long_entries"], "long_closed": ev[k]["long_closed"]})
                if (off, pen) == PRIMARY:
                    b4.window_checks(book, wb, m)                                                   # 15
                    prim[c] = (tr, od)
                    bks = b3.side_books(m, book)
                    SW[c] = {sd: {k: bks[sd].window(a, b) for k, (a, b) in wb.items()} for sd in SIDES}
                    SF[c] = {sd: {k: side_fill(od, a, b, 1 if sd == "long" else -1) for k, (a, b) in wb.items()}
                             for sd in SIDES}
                    dly[c] = {sd: bk.daily(0, m.N) for sd, bk in bks.items()}
                    assert np.allclose(dly[c]["all"], dly[c]["long"] + dly[c]["short"]), "assert16 daily"
                    if c.startswith("G5") and p["c"] == ENS_C and p["struct"] in ENS_LEGS:
                        dly[c]["long_pnl"] = bks["long"].pnl.copy()
                        dly[c]["long_held"] = held_weight(bks["long"])
                    del bks
                rows.append(row)
                del book
        R_all[c] = R
        print(f"[sim] {n_+1}/42 {c} {time.time()-t0:.0f}s", flush=True)
    g = pd.DataFrame(rows)
    for k in WINDOWS:
        g[f"{k}_worst"] = g[[f"{k}_long_net4", f"{k}_short_net4"]].min(axis=1)

    # strict control parity (assert 21)
    old = pd.read_parquet(PARENT_DIR / "controls_strict.parquet").set_index("sim_id")
    parity = {}
    gi = g.set_index("sim_id")
    for lab in CONTROLS:
        n_cmp, bad = 0, {}
        for off in OFFSETS:
            for pen in PENS:
                o, nw = old.loc[sid(lab, off, pen)], gi.loc[sid(lab, off, pen)]
                for k in WINDOWS:
                    for x in R_all[lab][(off, pen)][k]:
                        col = f"{k}_{x}"
                        a_, b_ = float(nw[col]), float(o[col])
                        n_cmp += 1
                        if not ((np.isnan(a_) and np.isnan(b_)) or abs(a_ - b_) <= 1e-6):
                            bad[f"o{off}_p{pen}_{col}"] = (a_, b_)
        got = [R_all[lab][PRIMARY][w]["net4"] for w in ("DEV-FULL", "DEV-B", "TEST")]
        parity[lab] = {"n_compared_vs_b4_strict": n_cmp, "n_diff_atol_1e-6": len(bad), "diffs": bad,
                       "net4_DEV-FULL/DEV-B/TEST": got, "spec_ref": CONTROL_REF[lab],
                       "max_abs_diff_vs_spec_4dp": max(abs(x - y) for x, y in zip(got, CONTROL_REF[lab]))}
        assert not bad and parity[lab]["max_abs_diff_vs_spec_4dp"] <= 5e-5, f"assert21 {lab} {parity[lab]}"
    print(f"[parity] {[(k, v['n_compared_vs_b4_strict'], v['n_diff_atol_1e-6']) for k, v in parity.items()]}", flush=True)

    # long de-dup over c + ensembles (no simulation)
    dedupe = {}
    for s_ in STRUCTS:
        for v in VPOL:
            a, b = (R_all[cid(dict(struct=s_, c=c, vol=v))] for c in CS)
            dedupe[f"{s_}-{v}"] = {"max_abs_long_net4_diff_c": max(abs(a[x][w]["long_net4"] - b[x][w]["long_net4"])
                                                                   for x in a for w in WINDOWS)}
    ens_rows, ens_R, ens_pnl, ens_info = [], {}, {}, {}
    for e, v in ENS.items():
        ca, cb = (cid(dict(struct=s_, c=ENS_C, vol=v)) for s_ in ENS_LEGS)
        ens_R[e] = ensemble_R(R_all[ca], R_all[cb])
        pnl = 0.5 * dly[ca]["long_pnl"] + 0.5 * dly[cb]["long_pnl"]
        hw = 0.5 * dly[ca]["long_held"] + 0.5 * dly[cb]["long_held"]
        assert hw.max() <= 1 + 1e-12 and hw.min() >= -1e-12, "assert18 ensemble weight"               # 18
        d_e = pnl[:len(pnl) // 1440 * 1440].reshape(-1, 1440).sum(1)
        assert np.allclose(d_e, 0.5 * dly[ca]["long"] + 0.5 * dly[cb]["long"]), "assert17 ensemble daily"  # 17
        ens_pnl[e] = (pnl, hw, d_e, ca, cb)
        odA, odB = prim[ca][1], prim[cb][1]
        for k, (a, b) in wb.items():
            r = {"config_id": e, "vol": v, "legs": f"0.5*{ca} long + 0.5*{cb} long", "window": k,
                 **ens_R[e][PRIMARY][k],
                 "long_turnover": 0.5 * (SW[ca]["long"][k]["turnover"] + SW[cb]["long"][k]["turnover"]),
                 **pnl_stats(pnl, a, b), "max_sleeve_weight": float(hw[a:b].max())}
            fa = [(od.weight[(od.decision_idx >= a) & (od.decision_idx < b) & (od.side > 0)],
                   od.filled[(od.decision_idx >= a) & (od.decision_idx < b) & (od.side > 0)]) for od in (odA, odB)]
            den = 0.5 * sum(float(x.sum()) for x, _ in fa)
            r["long_fill_notional_rate"] = 0.5 * sum(float(x[f].sum()) for x, f in fa) / den if den > 0 else np.nan
            for o in OFFSETS:
                for q in PENS:
                    r[f"long_net4_o{o}_p{q}"] = ens_R[e][(o, q)][k]["long_net4"]
            ens_rows.append(r)
    ens = pd.DataFrame(ens_rows)
    assert len(ens) == 20

    # bootstrap: 42 configs + 5 ensembles
    boot_rows, boots = [], {}
    for c in configs:
        for k, (a, b) in wb.items():
            for sc_ in ("all", "long", "short"):
                x = dly[c][sc_][a // 1440:b // 1440]
                for bl in BLOCKS:
                    v = b2.stationary_boot_p05(x, bl)
                    boots[(c, k, sc_, bl)] = v
                    boot_rows.append({"config_id": c, "window": k, "scope": sc_, "block_days": bl, "p05_mean_day": v,
                                      "n_days": len(x), "n_boot": NBOOT, "seed": SEED})
        print(f"[boot] {c} {time.time()-t0:.0f}s", flush=True)
    eboot_rows = []
    for e, (_, _, d_e, _, _) in ens_pnl.items():
        for k, (a, b) in wb.items():
            for bl in BLOCKS:
                v = b2.stationary_boot_p05(d_e[a // 1440:b // 1440], bl)
                boots[(e, k, "long", bl)] = v
                eboot_rows.append({"config_id": e, "window": k, "scope": "long", "block_days": bl, "p05_mean_day": v,
                                   "n_days": (b - a) // 1440, "n_boot": NBOOT, "seed": SEED})

    # config metrics + selection pools
    cm_rows, info = [], {}
    for c, p in configs.items():
        R = R_all[c]
        el = b3.eligible(R)
        vd = b3.verdict(R, el, {s_: boots[(c, "TEST", s_, 60)] for s_ in ("all", "long", "short")})
        sd = {}
        for s_ in SIDES:
            se = side_eligible(R, s_, SW[c][s_], SF[c][s_]["DEV-FULL"])
            sd[s_] = {"eligible": se, "dev_score": side_dev_score(R, s_), "test_score": side_test_score(R, s_),
                      **side_verdict(R, s_, se, boots[(c, "TEST", s_, 60)])}
        info[c] = {"config_id": c, "params": p, "dev_eligible": bool(el), "dev_score": float(b3.dev_score(R)),
                   "adapt_score": float(b3.adapt_score(R)), **vd, "side": sd}
        cm_rows.append({"config_id": c, "role": "control_strict" if c.startswith("CONTROL") else "trial", **p,
                        "DEV_eligible": bool(el), "DEV_score": b3.dev_score(R), "ADAPT_score": b3.adapt_score(R),
                        **{k: v for k, v in vd.items()},
                        **{f"{s_}_{x}": sd[s_][x] for s_ in SIDES for x in ("eligible", "dev_score", "test_score",
                                                                              "side_verdict")},
                        **{f"{s_}_mdd_DEV-FULL": SW[c][s_]["DEV-FULL"]["mdd_1m"] for s_ in SIDES},
                        **{f"{s_}_turnover_DEV-FULL": SW[c][s_]["DEV-FULL"]["turnover"] for s_ in SIDES},
                        **{f"{s_}_fill_DEV-FULL": SF[c][s_]["DEV-FULL"] for s_ in SIDES},
                        **{f"{w}_{x}": v for w in WINDOWS for x, v in R[PRIMARY][w].items()},
                        **{f"boot60_{w}_{s_}": boots[(c, w, s_, 60)] for w in WINDOWS for s_ in ("all", "long", "short")}})
    cm = pd.DataFrame(cm_rows)
    assert len(cm) == 42
    for e in ENS:
        R = ens_R[e]
        p0 = ens[(ens.config_id == e) & (ens.window == "DEV-FULL")].iloc[0]
        sw = {"DEV-FULL": {"long_closed": p0.long_closed, "long_exp_days": p0.long_exp_days}}
        se = side_eligible(R, "long", sw, p0.long_fill_notional_rate)
        info[e] = {"config_id": e, "params": {"legs": p0.legs, "vol": ENS[e]}, "side": {"long": {
            "eligible": se, "dev_score": side_dev_score(R, "long"), "test_score": side_test_score(R, "long"),
            **side_verdict(R, "long", se, boots[(e, "TEST", "long", 60)])}}}
    core = cm[cm.role == "trial"].copy()
    core["mdd"], core["turn"] = core["DEV-FULL_mdd_1m"], core["DEV-FULL_turnover"]
    picks, pool_note = {}, {}
    el = core[core.DEV_eligible]
    picks["G5_DEV_PICK" if len(el) else "G5_DEV_BEST_INELIGIBLE"] = rank(el if len(el) else core, "DEV_score", "mdd",
                                                                          "turn").iloc[0].config_id
    rp = el if len(el) else core
    pool_note["G5_RESELECTED"] = "eligible" if len(el) else "no eligible config; whole pool"
    picks["G5_RESELECTED"] = rp.sort_values(["ADAPT_score", "DEV_score", "config_id"],
                                            ascending=[False, False, True]).iloc[0].config_id
    long_pool = [cid(p) for p in CORE if p["c"] == ENS_C] + list(ENS)
    short_pool = [cid(p) for p in CORE]
    assert len(long_pool) == 25 and len(short_pool) == 40
    for s_, pool, LAB in (("long", long_pool, "LONG"), ("short", short_pool, "SHORT")):
        df = pd.DataFrame([{"config_id": c, "eligible": info[c]["side"][s_]["eligible"],
                            "dev": info[c]["side"][s_]["dev_score"], "test": info[c]["side"][s_]["test_score"],
                            "mdd": (SW[c][s_]["DEV-FULL"]["mdd_1m"] if c in SW else
                                    float(ens[(ens.config_id == c) & (ens.window == "DEV-FULL")].mdd_1m.iloc[0])),
                            "turn": (SW[c][s_]["DEV-FULL"]["turnover"] if c in SW else
                                     float(ens[(ens.config_id == c) & (ens.window == "DEV-FULL")].long_turnover.iloc[0]))}
                           for c in pool])
        e_ = df[df.eligible]
        picks[f"{LAB}_DEV_PICK" if len(e_) else f"{LAB}_DEV_BEST_INELIGIBLE"] = \
            rank(e_ if len(e_) else df, "dev", "mdd", "turn").iloc[0].config_id
        pool_note[f"{LAB}_RESELECTED"] = "side-eligible" if len(e_) else "no side-eligible config; whole pool"
        picks[f"{LAB}_RESELECTED"] = (e_ if len(e_) else df).sort_values(["test", "dev", "config_id"],
                                                                          ascending=[False, False, True]).iloc[0].config_id
        pool_note[f"{LAB}_n_eligible"] = int(len(e_))
    pool_note["G5_n_eligible"] = int(len(el))
    for lab in CONTROLS:
        picks[lab] = lab

    # per-label report blocks + trades/daily
    (run_dir / "trades").mkdir()
    (run_dir / "daily").mkdir()
    day_index = pd.date_range(pd.Timestamp(m.t[0], tz="UTC"), periods=m.N // 1440, freq="D")
    sel, side_pnl = {}, {}

    def window_block(c):
        if c in ENS:
            return {k: {**{x: v for x, v in r.items() if x not in ("config_id", "vol", "legs", "window")}}
                    for k, r in ((r_["window"], r_) for r_ in ens[ens.config_id == c].to_dict("records"))}
        R = R_all[c]
        out = {}
        for k in WINDOWS:
            e = R[PRIMARY][k]
            out[k] = {x: e[x] for x in ("net4", "net8", "funding", "closed", "long_net4", "long_closed", "short_net4",
                                        "short_closed", "long_funding", "short_funding", "mdd_1m", "sharpe",
                                        "fill_notional_rate", "exp_days", "turnover")}
            for s_ in SIDES:
                out[k][f"{s_}_mdd_1m"], out[k][f"{s_}_sharpe"] = SW[c][s_][k]["mdd_1m"], SW[c][s_][k]["sharpe"]
                out[k][f"{s_}_fill"] = SF[c][s_][k]
        return out

    def cells(c):
        R = R_all[c] if c in R_all else ens_R[c]
        sides = SIDES if c in R_all else ("long",)
        return {k: {f"o{o}_p{q}": {s_: R[(o, q)][k][f"{s_}_net4"] for s_ in sides} for o in OFFSETS for q in PENS}
                for k in WINDOWS}

    for lab, c in picks.items():
        blk = {**info[c], "label": lab, "windows_primary": window_block(c), "cells_net4": cells(c),
               "bootstrap_p05": {k: {s_: [boots.get((c, k, s_, bl)) for bl in BLOCKS] for s_ in ("all", "long", "short")}
                                 for k in WINDOWS}}
        if "RESELECTED" in lab and not lab.startswith("CONTROL"):
            blk["selection_flag"] = TEST_FLAG
            blk["pool"] = pool_note[lab]
        sel[lab] = blk
        if c in ENS:
            pnl, hw, d_e, ca, cb = ens_pnl[c]
            ts = []
            for leg in (ca, cb):
                t = prim[leg][0]
                t = t[t.side > 0].copy()
                t["sleeve"], t["sleeve_mult"] = leg, 0.5
                ts.append(t)
            t = pd.concat(ts, ignore_index=True)
            dd = pd.DataFrame({"day": day_index, "net4_all": d_e, "net4_long": d_e, "net4_short": 0.0})
            side_pnl[lab] = {"long": (pnl, hw)}
        else:
            tr, od = prim[c]
            book = b2.Book(m, tr, od, 0, m.N)
            t = book.tr.copy()
            if len(t):
                t["net4_full"], t["gross_full"], t["funding_full"] = book.net4_full, book.gross_full, book.fund_full
            dd = pd.DataFrame({"day": day_index, "net4_all": dly[c]["all"], "net4_long": dly[c]["long"],
                               "net4_short": dly[c]["short"], "held": book.held_day})
            if lab in ("LONG_DEV_PICK", "SHORT_DEV_PICK", "LONG_DEV_BEST_INELIGIBLE", "SHORT_DEV_BEST_INELIGIBLE"):
                bks = b3.side_books(m, book)
                side_pnl[lab] = {s_: (bks[s_].pnl.copy(), held_weight(bks[s_])) for s_ in SIDES}
                del bks
            del book
        if len(t):
            for col in ("decision_idx", "entry_idx", "exit_idx", "exit_decision_idx"):
                ix = t[col].to_numpy().astype(int)
                t[col.replace("idx", "time")] = pd.Series(pd.to_datetime(m.t[np.maximum(ix, 0)], utc=True)).where(ix >= 0)
        t.to_parquet(run_dir / "trades" / f"{lab}.parquet", index=False)
        dd.to_parquet(run_dir / "daily" / f"{lab}.parquet", index=False)
        print(f"[select] {lab} {c} {time.time()-t0:.0f}s", flush=True)

    # combined book (derived): long sleeve of LONG pick + short sleeve of SHORT pick
    lk = next(k for k in picks if k.startswith("LONG_DEV"))
    sk = next(k for k in picks if k.startswith("SHORT_DEV"))
    (pl, hl), (ps, hs) = side_pnl[lk]["long"], side_pnl[sk]["short"]
    pnl = pl + ps
    dcomb = pnl.reshape(-1, 1440).sum(1)
    Rl = R_all[picks[lk]] if picks[lk] in R_all else ens_R[picks[lk]]
    Rs = R_all[picks[sk]]
    comb = {"label": "COMBINED_LONG_SHORT_DEV_PICK", "long_sleeve": f"{lk}={picks[lk]} long",
            "short_sleeve": f"{sk}={picks[sk]} short", "derived": "sum of sleeve P&L; no new simulation",
            "double_exposure_rule": "each sleeve weight <= 1 on its own capital unit; when both sleeves are open the "
                                    "book holds long and short at once (gross = wL + wS <= 2, net = wL - wS); "
                                    "metrics are the plain sum, not re-scaled",
            "windows_primary": {}, "cells_net4": {}, "bootstrap_p05": {}}
    both = (hl > 1e-12) & (hs > 1e-12)
    for k, (a, b) in wb.items():
        L, S = Rl[PRIMARY][k], Rs[PRIMARY][k]
        comb["windows_primary"][k] = {
            "net4": L["long_net4"] + S["short_net4"], "net8": L["long_net8"] + S["short_net8"],
            "funding": L["long_funding"] + S["short_funding"], "closed": L["long_closed"] + S["short_closed"],
            "long_net4": L["long_net4"], "long_closed": L["long_closed"], "short_net4": S["short_net4"],
            "short_closed": S["short_closed"], **pnl_stats(pnl, a, b),
            "long_fill": (sel[lk]["windows_primary"][k].get("long_fill", sel[lk]["windows_primary"][k].get(
                "long_fill_notional_rate"))), "short_fill": SF[picks[sk]]["short"][k],
            "overlap_minutes": int(both[a:b].sum()), "overlap_days": float(both[a:b].sum() / 1440),
            "max_gross_weight": float((hl + hs)[a:b].max())}
        comb["cells_net4"][k] = {f"o{o}_p{q}": {"long": Rl[(o, q)][k]["long_net4"], "short": Rs[(o, q)][k]["short_net4"],
                                                "all": Rl[(o, q)][k]["long_net4"] + Rs[(o, q)][k]["short_net4"]}
                                 for o in OFFSETS for q in PENS}
        comb["bootstrap_p05"][k] = {"all": [b2.stationary_boot_p05(dcomb[a // 1440:b // 1440], bl) for bl in BLOCKS],
                                    "long": [boots[(picks[lk], k, "long", bl)] for bl in BLOCKS],
                                    "short": [boots[(picks[sk], k, "short", bl)] for bl in BLOCKS]}
    cw = comb["windows_primary"]
    comb["flags"] = {"TEST_all_cells_positive": all(v["all"] > 0 for v in comb["cells_net4"]["TEST"].values()),
                     "TEST_boot60_all_p05": comb["bootstrap_p05"]["TEST"]["all"][1],
                     "LOW_N_any_side_TEST_closed_lt10": cw["TEST"]["long_closed"] < 10 or cw["TEST"]["short_closed"] < 10}

    # adaptive state table (one row per 4h decision)
    T = st["T"]
    state = pd.DataFrame({"T": pd.to_datetime(T, utc=True),
                          "funding_time": pd.Series(pd.to_datetime(st["ftime"].clip(0), utc=True)).where(st["j"] >= 0),
                          "funding_rate": st["fund"], "fund_median90": st["med"], "fund_mad90": st["mad"],
                          "funding_z90": st["fz"], **{f"fund_thr_c{c:+.1f}": raw_thr(st["med"], st["mad"], c) for c in CS},
                          "score_F": st["score"][(6, 18, 42)], "score_S": st["score"][(42, 168, 504)],
                          "svi42": st["svi"][42], "svi180": st["svi"][180], "sigma_ann": st["sig"],
                          "score_raw_hurdle_per_sqrtL": DB * st["sig"] / np.sqrt(6 * 365),
                          **{f"tv_{v}": st["tv"][v] for v in VPOL[:4]}, **{f"w_{v}": st["w"][v] for v in VPOL},
                          "w_tv0.40": np.nan_to_num(np.minimum(1.0, 0.4 / st["sig"])),
                          **{f"ready_{v}": np.isfinite(st["w"][v]) for v in VPOL},
                          "ready_funding": (st["j"] >= 0) & np.isfinite(st["med"])})
    assert len(state) == 14832

    # outputs
    hashes = input_hashes()
    assert len(g) == 252 and g.sim_id.is_unique and len(fold) == 1008 and len(diag) == 1008
    assert len(boot_rows) == 1512 and len(eboot_rows) == 60                                         # 22
    g.to_parquet(run_dir / "grid.parquet", index=False)
    pd.DataFrame(fold).to_parquet(run_dir / "fold_metrics.parquet", index=False)
    cm.to_parquet(run_dir / "config_metrics.parquet", index=False)
    state.to_parquet(run_dir / "adaptive_state.parquet", index=False)
    pd.DataFrame(diag).to_parquet(run_dir / "signal_diagnostics.parquet", index=False)
    pd.DataFrame(boot_rows).to_parquet(run_dir / "bootstrap.parquet", index=False)
    ens.to_parquet(run_dir / "long_ensemble_metrics.parquet", index=False)
    pd.DataFrame(eboot_rows).to_parquet(run_dir / "long_ensemble_bootstrap.parquet", index=False)
    dump = lambda o, f: (run_dir / f).write_text(json.dumps(o, indent=2, default=str), encoding="utf-8")  # noqa: E731
    grab = lambda pre: {k: v for k, v in sel.items() if k.startswith(pre)}  # noqa: E731
    dump({k: v for k, v in grab("G5_").items() if "RESELECTED" not in k}, "selected_overall.json")
    dump({k: v for k, v in grab("LONG_").items() if "RESELECTED" not in k}, "selected_long.json")
    dump({k: v for k, v in grab("SHORT_").items() if "RESELECTED" not in k}, "selected_short.json")
    dump(sel["G5_RESELECTED"], "reselected_overall.json")
    dump(sel["LONG_RESELECTED"], "reselected_long.json")
    dump(sel["SHORT_RESELECTED"], "reselected_short.json")
    dump({k: {**sel[k], "parity": parity[k], "semantics": "strict funding_time < T"} for k in CONTROLS}, "controls.json")
    dump(comb, "combined_book.json")
    for lab, v in sel.items():                                                                      # 23
        assert ("RESELECTED" not in lab or lab.startswith("CONTROL")) or v.get("selection_flag") == TEST_FLAG
    counts = {"core_logical": 40, "control_logical": 2, "logical": 42, "sims_core": 240, "sims_control": 12,
              "sims": 252, "derived_ensembles": 5, "n_trials": 245, "state_rows": len(state),
              "dev_eligible_core": int(el.shape[0]), **pool_note}
    manifest = {
        "run_id": run_id, "parent_run_id": PARENT, "created_utc": datetime.now(timezone.utc).isoformat(),
        "spec": "scratchpad codex_batch5.md section 3 (Codex session 01a124c5-ad76-7d91-a832-42fbf0b4d6b7)",
        "name": "G3-NORM-ADAPT",
        "frozen_hypothesis": "normalised score/SVI keep fixed boundaries; funding gate uses previous-90-event robust-z "
                             "raw boundary median90 + c*1.4826*MAD90 (c in {-0.5,0}); only target vol adapts "
                             "(trailing sigma_ann quantile or V-ENS mean); 0.5 F42 + 0.5 S180 long ensemble "
                             "dilutes long profit concentration; maker 4 bps rt",
        "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()}, "window_days": WIN_DAYS,
        "data_cutoff": str(b2.END), "cutoff_note": "2026-10-08 exclusive",
        "sources": {"dev_market": str(b2.DEV_MARKET), "test_market": str(b2.SNAP / "market_1m.parquet"),
                    "dev_funding": str(b2.DEV_FUNDING), "test_funding": str(b2.SNAP / "funding_model_input.parquet"),
                    "engine_batch2": str(B2_PATH), "batch3": str(B3_PATH), "batch4": str(B4_PATH),
                    "batch4_run": str(PARENT_DIR)},
        "input_sha256": hashes, "code_sha256": code_hash, "git": b2.git_state(), "counts": counts,
        "structures": {k: {"trend": v[0], "svi_w": v[1]} for k, v in STRUCTS.items()}, "funding_c": CS,
        "vol_policies": {**{v: dict(W=W, q=q) for (W, q), v in zip(INNER, VPOL)}, "V-ENS": "mean of 4 weights"},
        "controls": CONTROLS, "control_parity": parity, "picks": picks, "pool_notes": pool_note,
        "test_selection_flags": {k: TEST_FLAG for k in picks if "RESELECTED" in k and not k.startswith("CONTROL")},
        "long_c_dedupe": {"representative_c": ENS_C, "diffs": dedupe},
        "identity_checks": ident, "prefix_checks": pre,
        "execution": {"tick": b2.TICK, "offsets_bps": OFFSETS, "penetration_bps": PENS, "ttl_min": b2.TTL_TREND,
                      "exit_quote_bps": b2.EXIT_QUOTE_BPS, "requote_min": b2.REQUOTE_MIN, "cost_bps_rt": 4,
                      "report_only_bps_rt": 8, "slippage": 0, "terminal_open": "MTM + reserved 2 bps exit",
                      "funding": "PESS", "action": "state_flat", "weight": "entry_weight_frozen"},
        "selection": {"G5_DEV_PICK": "Batch-3 eligible/DEV_score over core 40; ties DEV-FULL mdd, turnover, id",
                      "LONG_DEV_PICK": "pool 20 core (c=0) + 5 ensembles; side eligibility; offset 2/5 x DEV-A/B "
                                       "long per-day min", "SHORT_DEV_PICK": "pool 40 core; same on short",
                      "G5_RESELECTED": f"ADAPT_score (TEST 12 cells min) max; {TEST_FLAG}",
                      "LONG_RESELECTED": f"TEST long 6 cells min max; {TEST_FLAG}",
                      "SHORT_RESELECTED": f"TEST short 6 cells min max; {TEST_FLAG}"},
        "verdict_rules": "Batch-3 verdict() unchanged (PROFIT_PASS, LOW_N, STRONG, ROBUST_PASS, SIDE_STRONG); side "
                         "analogues S_* for side labels",
        "bootstrap": {"type": "stationary", "blocks_days": BLOCKS, "n": NBOOT, "seed": SEED,
                      "stat": "mean daily 1m-MTM net4 (bps/day)"},
        "excluded": ["raw score/SVI/funding quantiles", "WF/bandit", "regime-conditional thresholds"],
        "interpretations": __doc__, "runtime_sec": round(time.time() - t0, 1)}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    picked = set(picks.values())
    with (run_dir / "runs.jsonl").open("x", encoding="utf-8") as fh:      # write-once
        for r in g.to_dict("records"):
            fh.write(canonical({"run_id": run_id, "parent_run_id": PARENT, "sim_id": r["sim_id"],
                                "config_id": r["config_id"], "role": r["role"], "selected": r["config_id"] in picked,
                                "data_cutoff": str(b2.END), "code_sha256": code_hash,
                                **{k: v for k, v in r.items() if k.endswith(("net4", "net8", "_closed"))}}) + "\n")
    if not args.no_registry:
        print(f"[registry] {write_registry(g, ens, sel, hashes, run_id)}", flush=True)
    print(f"[done] {run_id} {time.time()-t0:.0f}s", flush=True)
    return run_dir


if __name__ == "__main__":
    main()
