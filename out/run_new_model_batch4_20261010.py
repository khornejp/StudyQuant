"""Batch-4 (2026-10-10): G3-ADAPT = Batch-3 G3 structure with every decision boundary a trailing quantile.

Spec: scratchpad codex_batch4_spec.md (Codex thread 01a124b2-450d-7912-9bf7-9dc192b924f6). Parent run
NM-B3-20261010T071709Z-7760a0d9 (control parity source).
Frozen hypothesis: G3 is more stable when every decision boundary (score / SVI / funding / target-vol) is a trailing
quantile of the recent market distribution (past data only), not an absolute constant. Walk-forward periodically
reselects the quantile meta-setting (W, q) by recent two-sided net.

Engine: Batch-2 simulate/Book/bootstrap/G features and Batch-3 eligible/dev_score/adapt_score/verdict/gate_inputs/
g3_signal are imported unchanged (importlib); their file hashes are input hashes.
Interpretations (spec silent or ambiguous; most causal reading chosen):
  * 4h history H_t(W) = the 6*W previous 4h decisions (positions i-6W .. i-1); with contiguous 4h bars their decision
    times are exactly [T-W, T) (asserted). Quantile = numpy/pandas 'linear'. Ready = all 6W samples finite and the
    current score/SVI/sigma finite; long needs 4h-ready, short needs 4h-ready AND funding-ready.
  * funding sample = events with time in [ft[j_t]-W, ft[j_t]) (searchsorted 'left' on both ends, so an event with
    the same timestamp as j_t is excluded too); funding-ready = ft[j_t]-W >= first funding event time and >= 1 sample.
  * 'ready' column in adaptive_thresholds = 4h-ready AND funding-ready; ready_4h / ready_funding also stored.
  * WF tie 'all-side net4/day mean' = mean over offset 2/5 (pen 0.5) of all-side net4/day in [R-H, R);
    tie mdd_1m / turnover = offset 2 pen 0.5 all-side in [R-H, R).
  * WF applied to decisions with T in [R, next_R) (last next_R = cutoff); T before the first refit -> side 0.
  * runtime assert 9: for every refit anchor R the four inner paths are re-simulated on a market truncated at R
    (minutes < R, funding events < R); window gross/funding/entries/closed must match the full run and net4 must
    match after adding back the reserved 2 bps exit fee of positions still open at R (the only prefix-run artefact).
  * funding causality (coordinator correction from Codex Batch-3 review): an event is usable only if
    funding_time < T (strict); j_t = max{j: ft_j < T}; DEV funding_time is the archive settlement time. Controls run
    twice: original Batch-3 semantics (publish <= T, parity check, in grid/registry as the 12 control sims) and
    strict semantics (report-only replay CONTROL_*_STRICT: controls_strict.parquet, bootstrap_controls_strict.parquet,
    registry role control_strict n_trials 0).
  * signal diagnostics: des = score/SVI side without the funding condition, gate = funding-ready & fund >= thr
    (adaptive) or the Batch-3 mask (controls); Batch-3 diagnostics() reused.
  * bootstrap for all 10 logical configs (primary offset 2 pen 0.5): 4 windows x all/long/short x 3 blocks = 360.
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
b3 = _load("nm_b3", B3_PATH)
b2 = b3.b2
OUT_BASE = ROOT / "out/new_model_batch4_20261010"
PARENT = "NM-B3-20261010T071709Z-7760a0d9"
PARENT_DIR = ROOT / "out/new_model_batch3_20261010" / PARENT
REGISTRY = b2.REGISTRY
MIN, DAY = b2.MIN, b2.DAY
WINDOWS, SIDES, SEED, NBOOT, BLOCKS = b2.WINDOWS, b2.SIDES, b2.SEED, b2.NBOOT, b2.BLOCKS
OFFSETS, PENS, PRIMARY, WIN_DAYS = b3.OFFSETS, b3.PENS, b3.PRIMARY, b3.WIN_DAYS
TREND, SVI_W = (6, 18, 42), 180
INNER = ((180, 0.50), (180, 0.65), (365, 0.50), (365, 0.65))          # (W days, q)
HS, CS, WARM = (365, 730), (3, 6), 365
QCFG = [dict(style="Q", W=W, q=q) for W, q in INNER]
WFCFG = [dict(style="WF", H=H, C=C) for H in HS for C in CS]
CONTROLS = {"CONTROL_B3_DEV_PICK": dict(base=8, svi_w=180, trend="(6, 18, 42)", tv=0.4, gate="fz>=0",
                                        action="state_flat"),
            "CONTROL_B3_RESELECTED": dict(base=4, svi_w=180, trend="(42, 168, 504)", tv=0.4, gate="fz>=-0.5",
                                          action="state_flat")}
CONTROL_NET4 = {"CONTROL_B3_DEV_PICK": (15853.6464, 4391.6443, 2687.1584),
                "CONTROL_B3_RESELECTED": (24175.5691, 6440.8493, 4271.6089)}     # DEV-FULL, DEV-B, TEST (spec)
CONTROL_STRICT_REF = {"CONTROL_B3_DEV_PICK_STRICT": (15416.6, 11347.0, 4069.5, 2589.6),
                      "CONTROL_B3_RESELECTED_STRICT": (24047.0, 17819.9, 6227.1, 4288.2)}   # Codex, DEV-FULL/A/B/TEST
STRICT = "CONTROL_STRICT"
NUMERIC_CUTOFF_KEYS = ("db", "g", "tv", "fund", "funding_z", "fz", "fr", "gate")


def cid(p: dict) -> str:
    if p["style"] == "Q":
        return f"Q-W{p['W']}-P{int(round(p['q'] * 100))}"
    return f"WF-H{p['H']}-C{p['C']}"


def a_id(a) -> str:
    return cid(dict(style="Q", W=a[0], q=a[1]))


# ---------------- adaptive boundaries ----------------
def adaptive_inputs(m, dec4) -> dict:
    """Batch-2 G features (trend (6,18,42), SVI 180, sigma 180) + latest funding event as-of each decision."""
    fe = SimpleNamespace(m=m, h4=dec4)
    b2.Features.g_prep(fe)
    T = m.t[dec4] + MIN
    nx = dec4 + 1 < m.N
    assert np.all(m.t[dec4[nx] + 1] == T[nx]), "assert1: T != close bar time + 1m"               # 1
    assert np.all(np.diff(T) == 4 * 60 * MIN), "4h decisions not contiguous"
    j = np.searchsorted(m.ft, T, "left") - 1                     # strict: funding_time < T (publish == T excluded)
    assert np.all(m.ft[j[j >= 0]] < T[j >= 0]), "assert4: funding event not strictly before T"     # 4
    return dict(T=T, score=fe.G["score"][TREND], svi=fe.G["svi"][SVI_W], sig=fe.G["sig_ann"], j=j)


def trailing_q(x: np.ndarray, n: int, q: float) -> np.ndarray:
    """Q_q of x[i-n:i] (current excluded); NaN unless all n samples finite."""
    return pd.Series(x).rolling(n, min_periods=n).quantile(q, interpolation="linear").shift(1).to_numpy()


def funding_thr(m, W: int, qs) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per funding event j: Q_q of rates with time in [ft_j - W, ft_j) (event j and same-time events excluded)."""
    lo = np.searchsorted(m.ft, m.ft - W * DAY, "left")
    hi = np.searchsorted(m.ft, m.ft, "left")
    assert np.all(hi <= np.arange(len(m.ft))), "assert5: funding sample reaches j_t"                 # 5
    ready = (m.ft - W * DAY >= m.ft[0]) & (hi > lo)
    out = np.full((len(m.ft), len(qs)), np.nan)
    for k in np.flatnonzero(ready):
        out[k] = np.quantile(m.fr[lo[k]:hi[k]], qs)
    r = np.flatnonzero(ready)
    assert np.all(m.ft[hi[r] - 1] < m.ft[r]) and np.all(m.ft[lo[r]] >= m.ft[r] - W * DAY), "assert6"  # 6
    return out, lo, hi


def thresholds(inp: dict, m, W: int, q: float, fthr=None, check=200) -> dict:
    n = 6 * W
    T, sc, svi, sig, j = inp["T"], inp["score"], inp["svi"], inp["sig"], inp["j"]
    db, g, tv = trailing_q(np.abs(sc), n, q), trailing_q(np.abs(svi), n, q), trailing_q(sig, n, q)
    r4 = np.isfinite(db) & np.isfinite(g) & np.isfinite(tv) & np.isfinite(sc) & np.isfinite(svi) & np.isfinite(sig) \
        & (sig > 0)
    ri = np.flatnonzero(r4)
    assert np.all(ri >= n) and np.all(T[ri - n] >= T[ri] - W * DAY) and np.all(T[ri - 1] < T[ri]), "assert2"   # 2
    rng = np.random.default_rng(0)
    for i in (rng.choice(ri, min(check, len(ri)), replace=False) if len(ri) else []):     # 3: sample = [i-n, i)
        assert np.isclose(db[i], np.quantile(np.abs(sc[i - n:i]), q), rtol=0, atol=1e-12), "assert3 score"
        assert np.isclose(g[i], np.quantile(np.abs(svi[i - n:i]), q), rtol=0, atol=1e-12), "assert3 svi"
        assert np.isclose(tv[i], np.quantile(sig[i - n:i], q), rtol=0, atol=1e-12), "assert3 sigma"
    if fthr is None:
        fthr = funding_thr(m, W, (q,))[0][:, 0]
    jj = np.maximum(j, 0)
    fund = np.where(j >= 0, m.fr[jj], np.nan)
    fth = np.where(j >= 0, fthr[jj], np.nan)
    rf = (j >= 0) & np.isfinite(fund) & np.isfinite(fth)
    with np.errstate(invalid="ignore", divide="ignore"):
        lng = r4 & (sc >= db) & (svi >= g)
        base_s = r4 & (sc <= -db) & (svi <= -g)
        fgate = rf & (fund >= fth)
        sht = base_s & fgate
        assert not (lng & sht).any(), "assert14: simultaneous long/short"                          # 14
        side = np.where(lng, 1, np.where(sht, -1, 0))
        w = np.where(side != 0, np.minimum(1.0, tv / sig), 0.0)
    assert np.all(side[~r4] == 0) and np.all(w[~r4] == 0) and np.all(side[~rf] >= 0), "assert13"     # 13
    assert np.all(np.isfinite(w)) and np.all(w[side != 0] > 0)
    return dict(db=db, g=g, tv=tv, fund=fund, fthr=fth, ready_4h=r4, ready_f=rf, side=side, w=w,
                des=np.where(lng, 1, np.where(base_s, -1, 0)), gate=fgate,
                ftime=np.where(j >= 0, m.ft[jj], np.iinfo(np.int64).min))


def all_thresholds(m, dec4, inp=None) -> dict:
    inp = inp or adaptive_inputs(m, dec4)
    out = {}
    for W in sorted({a[0] for a in INNER}):
        qs = tuple(q for w_, q in INNER if w_ == W)
        ft, _, _ = funding_thr(m, W, qs)
        for k, q in enumerate(qs):
            out[(W, q)] = thresholds(inp, m, W, q, ft[:, k])
    return inp, out


def gate_inputs_strict(m, dec4, d1):
    """Batch-3 gate_inputs with funding usable only if funding_time < T (as-of T - 1ns)."""
    T = m.t[dec4] + MIN
    fz90 = b2.b1.trailing_robust_z(m.fr, 90, 30)
    fz = b2.asof_values(m.ft, fz90, T - 1, None)
    fr = b2.asof_values(m.ft, m.fr, T - 1, None)
    ds, _ = b2.tsmom_score(m.c[d1], (30, 90, 180, 360), 30)
    p = b2.asof_bars(d1, dec4)
    return fz, fr, b2.take(ds, p)


# ---------------- walk-forward ----------------
def anchors(H: int, C: int, start=b2.START, end=b2.END, warm: int = WARM) -> list:
    months = (1, 4, 7, 10) if C == 3 else (1, 7)
    R = [pd.Timestamp(year=y, month=mo, day=1, tz="UTC") for y in range(start.year, end.year + 1) for mo in months]
    return [r for r in R if r - pd.Timedelta(days=H) >= start + pd.Timedelta(days=warm) and r < end]


def wf_rank(rows: list) -> list:
    """Order inner candidates: score desc, all-side mean desc, mdd asc, turnover asc, W asc, q asc."""
    return sorted(rows, key=lambda r: (-r["score"], -r["all_mean_per_day"], r["mdd_1m"], r["turnover"], r["W"], r["q"]))


def wf_rows(books: dict, m, R, H: int, fee_adj: dict | None = None) -> list:
    """WF_score_R(a) from the counterfactual Style-Q books over [R-H, R) (denominator H days)."""
    a_, b_ = m.idx(R - pd.Timedelta(days=H)), m.idx(R)
    assert (b_ - a_) // 1440 == H and (b_ - a_) % 1440 == 0 and m.t[b_ - 1] < R.value, "assert7: train window"  # 7
    out = []
    for a in INNER:
        ev = {o: books[(a, o)].window(a_, b_) for o in OFFSETS}
        r = {"R": R, "H": H, "W": a[0], "q": a[1], "inner_id": a_id(a), "train_start": R - pd.Timedelta(days=H),
             "train_end": R}
        for o in OFFSETS:
            for s in SIDES:
                v = ev[o][f"{s}_net4"] + (fee_adj or {}).get((a, o, s), 0.0)
                r[f"o{o}_{s}_net4"] = v
                r[f"o{o}_{s}_per_day"] = v / H
                for k in ("gross", "funding", "entries", "closed"):
                    r[f"o{o}_{s}_{k}"] = ev[o][f"{s}_{k}"]
            r[f"o{o}_all_per_day"] = sum(r[f"o{o}_{s}_net4"] for s in SIDES) / H
        r["score"] = min(r[f"o{o}_{s}_per_day"] for o in OFFSETS for s in SIDES)
        r["all_mean_per_day"] = float(np.mean([r[f"o{o}_all_per_day"] for o in OFFSETS]))
        r["mdd_1m"], r["turnover"] = ev[2]["mdd_1m"], ev[2]["turnover"]
        out.append(r)
    best = wf_rank(out)[0]
    for r in out:
        r["chosen"] = r is best
    return out


def prefix_market(m, R):
    n, f = m.idx(R), m.ft < R.value
    return b2.Market(m.t[:n], m.o[:n], m.h[:n], m.l[:n], m.c[:n], m.v[:n], m.tb[:n], m.ft[f], m.fr[f])


def inner_books(m, dec4, th: dict) -> dict:
    out = {}
    for a in INNER:
        for o in OFFSETS:
            tr, od = b2.simulate(m, "state", dec4, th[a]["side"], th[a]["w"], o, b2.TTL_TREND, 0.5, 0, m.N)
            out[(a, o)] = b2.Book(m, tr, od, 0, m.N)
    return out


def prefix_check(m, dec4, th_full: dict, full_rows: dict, R) -> None:
    """assert 9: re-run inner paths on data < R only; thresholds, window P&L and the choice must match."""
    mp = prefix_market(m, R)
    d = dec4[dec4 < mp.N]
    _, thp = all_thresholds(mp, d)
    k_ = int(np.sum(mp.t[d] + MIN < R.value))      # decisions with T < R (T == R is never simulated in the prefix)
    for a in INNER:
        for k in ("db", "g", "tv", "fthr", "side", "w"):
            assert np.array_equal(thp[a][k][:k_], th_full[a][k][:k_], equal_nan=True), f"assert9 threshold {k} {a}"
    bp = inner_books(mp, d, thp)
    adj = {(a, o, s): 2.0 * bk.w[~bk.closed & ((bk.s > 0) if s == "long" else (bk.s < 0))].sum()
           for (a, o), bk in bp.items() for s in SIDES}       # reserved terminal exit fee of positions open at R
    for H, rows in full_rows.items():
        pr = wf_rows(bp, mp, R, H, adj)
        for x, y in zip(rows, pr):
            for k in x:
                if k.startswith("o") and not k.endswith(("mdd_1m", "turnover")):
                    tol = 1e-6 * max(1.0, abs(x[k]))
                    assert abs(x[k] - y[k]) <= tol, f"assert9 {R} H{H} {x['inner_id']} {k} {x[k]} {y[k]}"
            assert x["chosen"] == y["chosen"] or abs(x["score"] - y["score"]) < 1e-9, f"assert9 choice {R}"


def wf_signal(th: dict, T: np.ndarray, Rs: list, choices: list, end=b2.END):
    side, w = np.zeros(len(T), int), np.zeros(len(T))
    des, gate = np.zeros(len(T), int), np.zeros(len(T), bool)
    nxt = list(Rs[1:]) + [end]
    for R, R2, a in zip(Rs, nxt, choices):
        mk = (T >= R.value) & (T < R2.value)
        assert mk.any()
        side[mk], w[mk], des[mk], gate[mk] = th[a]["side"][mk], th[a]["w"][mk], th[a]["des"][mk], th[a]["gate"][mk]
    assert np.all(side[T < Rs[0].value] == 0) and np.all(w[side == 0] == 0), "assert8: applied outside [R, next_R)"  # 8
    return side, w, des, gate


# ---------------- outputs ----------------
def sid(c: str, off, pen) -> str:
    return f"{c}|offset={off}|pen={pen}"


def write_registry(g: pd.DataFrame, sel: dict, hashes: dict, run_id: str, path: Path = REGISTRY,
                   g_strict: pd.DataFrame | None = None) -> dict:
    have = b2.registry_keys(path)
    ih = hashlib.sha256(canonical(hashes).encode()).hexdigest()
    added = skipped = 0
    recs = g.to_dict("records") + ([] if g_strict is None else g_strict.to_dict("records"))
    for r in recs:
        key = hashlib.sha256(canonical({"batch": "NM-B4", "sim_id": r["sim_id"], "inputs": ih}).encode()).hexdigest()
        if key in have:
            skipped += 1
            continue
        ctl = r["style"].startswith("CONTROL")
        role = "control_strict" if r["style"] == STRICT else "control" if ctl else "trial"
        registry.record(path, {
            "experiment": f"NM-B4 G3-ADAPT {r['sim_id']}", "idempotency_key": key, "role": role,
            "config": {"sim_id": r["sim_id"], "run_id": run_id, "parent_run_id": PARENT,
                       "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()},
                       "costs": "4 bps rt maker flat, 0 slip, PESS funding; 8 bps report-only"},
            "input_hashes": hashes, "n_trials": 0 if ctl else 1,
            "result_summary": {f"{w}_{k}": r[f"{w}_{k}"] for w in WINDOWS
                               for k in ("net4", "net8", "long_net4", "short_net4", "closed", "fill_notional_rate")}})
        added += 1
    key = hashlib.sha256(canonical({"batch": "NM-B4", "selection": True, "inputs": ih}).encode()).hexdigest()
    if key in have:
        skipped += 1
    else:
        registry.record(path, {"experiment": "NM-B4 G3-ADAPT selection (Q/WF/G3_ADAPT DEV picks + RESELECTED)",
                               "idempotency_key": key, "role": "selection",
                               "config": {"run_id": run_id, "parent_run_id": PARENT}, "input_hashes": hashes,
                               "n_trials": 0, "result_summary": {"batch_trials": 48, "batch_simulations": 60,
                                                                 "picks": {k: v["config_id"] for k, v in sel.items()}}})
        added += 1
    return {"added": added, "skipped": skipped}


def input_hashes() -> dict:
    h = b2.input_hashes()
    h["batch2_code"] = h.pop("code")
    h["batch3_code"] = provenance.file_sha256(B3_PATH)
    h["batch3_manifest"] = provenance.file_sha256(PARENT_DIR / "manifest.json")
    h["batch3_grid"] = provenance.file_sha256(PARENT_DIR / "grid.parquet")
    h["code"] = provenance.file_sha256(Path(__file__))
    return h


def window_checks(book, wb: dict, m) -> None:
    """assert 10: DEV/TEST are cuts of one stream (no reset, no extra cost)."""
    ev = {k: book.window(a, b) for k, (a, b) in wb.items()}
    assert wb["DEV-FULL"][1] == wb["TEST"][0] and wb["DEV-A"][1] == wb["DEV-B"][0]
    assert abs(ev["DEV-A"]["net4"] + ev["DEV-B"]["net4"] - ev["DEV-FULL"]["net4"]) < 1e-6 * max(1, abs(ev["DEV-FULL"]["net4"]))
    tot = ev["DEV-FULL"]["net4"] + ev["TEST"]["net4"]
    assert abs(tot - book.net4_full.sum()) < 1e-6 * max(1.0, abs(tot)), "assert10"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-registry", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    code_hash = provenance.file_sha256(Path(__file__))
    run_id = f"NM-B4-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{code_hash[:8]}"
    run_dir = OUT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=False)          # write-once
    minutes, met, prem, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes, met, prem
    wb = b3.window_bounds(m)
    dec4, d1 = np.arange(239, m.N, 240), np.arange(1439, m.N, 1440)
    inp, th = all_thresholds(m, dec4)
    T = inp["T"]
    print(f"[load] N={m.N} dec4={len(dec4)} funding={len(m.ft)} {time.time()-t0:.0f}s", flush=True)

    # signals: Style Q, Style WF, controls
    configs, sig = {}, {}
    for p in QCFG:
        assert not any(k in p for k in NUMERIC_CUTOFF_KEYS), "assert12"                              # 12
        a = (p["W"], p["q"])
        configs[cid(p)] = p
        sig[cid(p)] = (th[a]["side"], th[a]["w"], th[a]["des"], th[a]["gate"])
    qbooks = inner_books(m, dec4, th)
    wf_score_rows, wf_choice_rows = [], []
    rows_by_R: dict = {}
    for p in WFCFG:
        assert not any(k in p for k in NUMERIC_CUTOFF_KEYS), "assert12"
        Rs, ch = anchors(p["H"], p["C"]), []
        for k, R in enumerate(Rs):
            rows = wf_rows(qbooks, m, R, p["H"])
            rows_by_R.setdefault(R, {})[p["H"]] = rows
            best = next(r for r in rows if r["chosen"])
            a = (best["W"], best["q"])
            ch.append(a)
            nxt = Rs[k + 1] if k + 1 < len(Rs) else b2.END
            wf_score_rows += [{"config_id": cid(p), "C": p["C"], **r} for r in rows]
            wf_choice_rows.append({"config_id": cid(p), "H": p["H"], "C": p["C"], "R": R, "next_R": nxt,
                                   "chosen": a_id(a), "W": a[0], "q": a[1], "score": best["score"],
                                   "all_mean_per_day": best["all_mean_per_day"],
                                   "n_tied_score": sum(abs(r["score"] - best["score"]) < 1e-12 for r in rows)})
        configs[cid(p)] = p
        sig[cid(p)] = wf_signal(th, T, Rs, ch)
    for R, d in sorted(rows_by_R.items()):
        prefix_check(m, dec4, th, d, R)                                                             # 9
    print(f"[wf] refits {len(wf_choice_rows)} prefix-checked {len(rows_by_R)} anchors {time.time()-t0:.0f}s", flush=True)
    fe = SimpleNamespace(m=m, h4=dec4)
    b2.Features.g_prep(fe)
    for style, suffix, gi in (("CONTROL", "", b3.gate_inputs), (STRICT, "_STRICT", gate_inputs_strict)):
        masks = b3.gate_masks(*gi(m, dec4, d1))
        for lab, p in CONTROLS.items():
            G = fe.G
            des = b3.base_side(G["score"][eval(p["trend"])], G["svi"][p["svi_w"]])
            w = np.nan_to_num(np.minimum(1.0, p["tv"] / G["sig_ann"]))
            side, ok = b3.g3_signal(des, masks[p["gate"]], p["action"])
            assert ok is None
            configs[lab + suffix] = dict(style=style, **p)
            sig[lab + suffix] = (side, w, des, masks[p["gate"]])

    # simulations
    rows, fold, diag, R_all, books = [], [], [], {}, {}
    for c, p in configs.items():
        side, w, des, gate = sig[c]
        assert not ((side > 0) & (side < 0)).any()
        R = {}
        for off in OFFSETS:
            for pen in PENS:
                tr, od = b2.simulate(m, "state", dec4, side, w, off, b2.TTL_TREND, pen, 0, m.N)
                book = b2.Book(m, tr, od, 0, m.N)
                ev = {k: book.window(a, b) for k, (a, b) in wb.items()}
                if (off, pen) == PRIMARY:
                    window_checks(book, wb, m)
                    books[c] = book
                R[(off, pen)] = ev
                s_id = sid(c, off, pen)
                row = {"sim_id": s_id, "config_id": c, "style": p["style"], "W": p.get("W"), "q": p.get("q"),
                       "H": p.get("H"), "C": p.get("C"), "control_params": canonical(p) if p["style"].startswith("CONTROL")
                       else None, "offset": off, "pen_bps": pen}
                for k, d in ev.items():
                    row.update({f"{k}_{x}": v for x, v in d.items()})
                    fold.append({"sim_id": s_id, "config_id": c, "style": p["style"], "offset": off, "pen_bps": pen,
                                 "window": k, **d})
                for k, d in b3.diagnostics(tr, dec4, des, gate, wb).items():
                    mk = (dec4 >= wb[k][0]) & (dec4 < wb[k][1])
                    diag.append({"sim_id": s_id, "config_id": c, "style": p["style"], "offset": off, "pen_bps": pen,
                                 "window": k, **d, "long_dec": int(((side > 0) & mk).sum()),
                                 "short_dec": int(((side < 0) & mk).sum()), "flat_dec": int(((side == 0) & mk).sum()),
                                 "short_entries": ev[k]["short_entries"], "short_closed": ev[k]["short_closed"],
                                 "long_entries": ev[k]["long_entries"], "long_closed": ev[k]["long_closed"]})
                rows.append(row)
        R_all[c] = R
        print(f"[sim] {c} {time.time()-t0:.0f}s", flush=True)
    g = pd.DataFrame(rows)
    for k in WINDOWS:
        g[f"{k}_worst"] = g[[f"{k}_long_net4", f"{k}_short_net4"]].min(axis=1)
    cfg = pd.DataFrame([{"config_id": c, "style": configs[c]["style"], "DEV_eligible": b3.eligible(R),
                         "DEV_score": b3.dev_score(R), "ADAPT_score": b3.adapt_score(R)} for c, R in R_all.items()])
    g = g.merge(cfg.drop(columns="style"), on="config_id")
    assert len(g) == 72 and g.sim_id.is_unique and len(cfg) == 12
    g_strict, g = g[g["style"] == STRICT].reset_index(drop=True), g[g["style"] != STRICT].reset_index(drop=True)
    assert len(g) == 60 and len(g_strict) == 12
    strict_ref = {c: {"batch4": [R_all[c][PRIMARY][w]["net4"] for w in WINDOWS], "codex_ref": ref,
                      "max_abs_diff": max(abs(R_all[c][PRIMARY][w]["net4"] - x) for w, x in zip(WINDOWS, ref)),
                      "TEST_long_short": [R_all[c][PRIMARY]["TEST"][f"{s}_net4"] for s in SIDES]}
                  for c, ref in CONTROL_STRICT_REF.items()}
    print(f"[strict controls] {strict_ref}", flush=True)

    # control parity vs Batch-3 grid (6 exec x 4 windows, every window metric)
    old = pd.read_parquet(PARENT_DIR / "grid.parquet").set_index("sim_id")
    parity = {}
    for lab, p in CONTROLS.items():
        n_cmp, bad = 0, {}
        for off in OFFSETS:
            for pen in PENS:
                o = old.loc[b3.sid(p, off, pen)]
                nw = g.set_index("sim_id").loc[sid(lab, off, pen)]
                for k in WINDOWS:
                    for x in R_all[lab][(off, pen)][k]:
                        col = f"{k}_{x}"
                        a_, b_ = float(nw[col]), float(o[col])
                        n_cmp += 1
                        if not ((np.isnan(a_) and np.isnan(b_)) or abs(a_ - b_) <= 1e-9):
                            bad[f"o{off}_p{pen}_{col}"] = (a_, b_)
        prim = R_all[lab][PRIMARY]
        parity[lab] = {"batch3_config_id": b3.cid(p), "n_compared": n_cmp, "n_diff": len(bad), "diffs": bad,
                       "net4_DEV-FULL/DEV-B/TEST": [prim[w]["net4"] for w in ("DEV-FULL", "DEV-B", "TEST")]}
        assert np.allclose(parity[lab]["net4_DEV-FULL/DEV-B/TEST"], CONTROL_NET4[lab], atol=1e-4), lab
    print(f"[parity] {[(k, v['n_compared'], v['n_diff']) for k, v in parity.items()]}", flush=True)

    # bootstrap (10 logical configs, primary) + verdicts
    boot_rows, boots, side_dly = [], {}, {}
    for c, book in books.items():
        bks = b3.side_books(m, book)
        dl = {s: bk.daily(0, m.N) for s, bk in bks.items()}
        assert np.allclose(dl["all"], dl["long"] + dl["short"]), "assert11"                         # 11
        side_dly[c] = dl
        for k, (a, b) in wb.items():
            for s, bk in bks.items():
                dly = bk.daily(a, b)
                for bl in BLOCKS:
                    v = b2.stationary_boot_p05(dly, bl)
                    boots[(c, k, s, bl)] = v
                    boot_rows.append({"config_id": c, "style": configs[c]["style"], "window": k, "scope": s,
                                      "block_days": bl, "p05_mean_day": v, "n_days": len(dly), "n_boot": NBOOT,
                                      "seed": SEED})
        print(f"[boot] {c} {time.time()-t0:.0f}s", flush=True)
    cm_rows, info = [], {}
    for _, r in cfg.iterrows():
        c, R = r.config_id, R_all[r.config_id]
        vd = b3.verdict(R, bool(r.DEV_eligible), {s: boots[(c, "TEST", s, 60)] for s in ("all", "long", "short")})
        info[c] = {"config_id": c, "style": r["style"], "params": configs[c], "dev_eligible": bool(r.DEV_eligible),
                   "dev_score": float(r.DEV_score), "adapt_score": float(r.ADAPT_score), **vd,
                   "metrics_primary": R[PRIMARY],
                   "cells": {k: {f"o{o}_p{q}": {s: R[(o, q)][k][f"{s}_net4"] for s in SIDES} for o in OFFSETS
                                 for q in PENS} for k in WINDOWS},
                   "bootstrap_p05": {k: {s: [boots[(c, k, s, bl)] for bl in BLOCKS] for s in ("all", "long", "short")}
                                     for k in WINDOWS}}
        cm_rows.append({"config_id": c, "style": r["style"], "DEV_eligible": bool(r.DEV_eligible),
                        "DEV_score": r.DEV_score, "ADAPT_score": r.ADAPT_score,
                        **{k: v for k, v in vd.items()},
                        **{f"{w}_{x}": v for w in WINDOWS for x, v in R[PRIMARY][w].items()},
                        **{f"boot60_{w}_{s}": boots[(c, w, s, 60)] for w in WINDOWS for s in ("all", "long", "short")}})

    # selection (adaptive 8 only)
    prim = g[(g.offset == 2) & (g.pen_bps == 0.5)].set_index("config_id")
    ad = cfg[cfg["style"].isin(["Q", "WF"])].merge(prim[["DEV-FULL_mdd_1m", "DEV-FULL_turnover"]], left_on="config_id",
                                              right_index=True)
    order = dict(by=["DEV_score", "DEV-FULL_mdd_1m", "DEV-FULL_turnover", "config_id"],
                 ascending=[False, True, True, True])
    picks = {}
    for lab, pool in (("Q", ad[ad["style"] == "Q"]), ("WF", ad[ad["style"] == "WF"]), ("G3_ADAPT", ad)):
        el = pool[pool.DEV_eligible]
        picks[f"{lab}_DEV_PICK" if len(el) else f"{lab}_DEV_BEST_INELIGIBLE"] = \
            (el if len(el) else pool).sort_values(**order).iloc[0].config_id
    el = ad[ad.DEV_eligible]
    if len(el):
        picks["G3_ADAPT_RESELECTED"] = el.sort_values(["ADAPT_score", "DEV_score", "config_id"],
                                                      ascending=[False, False, True]).iloc[0].config_id
    sel = {lab: {**info[c], "n_eligible_adaptive": int(len(el))} for lab, c in picks.items()}
    if "G3_ADAPT_RESELECTED" in sel:
        sel["G3_ADAPT_RESELECTED"]["label"] = "G3_ADAPT_RESELECTED (chosen on TEST; never independent OOS)"
    labels = {**picks, **{k: k for k in CONTROLS}, **{k + "_STRICT": k + "_STRICT" for k in CONTROLS}}

    (run_dir / "trades").mkdir()
    (run_dir / "daily").mkdir()
    comp = []
    for lab, c in labels.items():
        book = books[c]
        t = book.tr.copy()
        if len(t):
            t["net4_full"], t["gross_full"], t["funding_full"] = book.net4_full, book.gross_full, book.fund_full
            for col in ("decision_idx", "entry_idx", "exit_idx", "exit_decision_idx"):
                ix = t[col].to_numpy().astype(int)
                t[col.replace("idx", "time")] = pd.Series(pd.to_datetime(m.t[np.maximum(ix, 0)], utc=True)).where(ix >= 0)
        t.to_parquet(run_dir / "trades" / f"{lab}.parquet", index=False)
        dl = side_dly[c]
        pd.DataFrame({"day": pd.date_range(pd.Timestamp(m.t[0], tz="UTC"), periods=len(dl["all"]), freq="D"),
                      "net4_all": dl["all"], "net4_long": dl["long"], "net4_short": dl["short"],
                      "held": book.held_day}).to_parquet(run_dir / "daily" / f"{lab}.parquet", index=False)
        for w in WINDOWS:
            e = R_all[c][PRIMARY][w]
            comp.append({"label": lab, "config_id": c, "window": w, "net4": e["net4"], "long_net4": e["long_net4"],
                         "short_net4": e["short_net4"], "closed": e["closed"], "long_closed": e["long_closed"],
                         "short_closed": e["short_closed"], "exp_days": e["exp_days"], "mdd_1m": e["mdd_1m"],
                         "sharpe": e["sharpe"], **{f"boot{bl}_{s}": boots[(c, w, s, bl)] for bl in BLOCKS
                                                    for s in ("all", "long", "short")}})

    # threshold table (Style Q)
    tt = []
    for a in INNER:
        x = th[a]
        tt.append(pd.DataFrame({"T": pd.to_datetime(T, utc=True), "config_id": a_id(a), "W": a[0], "q": a[1],
                                "score": inp["score"], "SVI": inp["svi"], "sigma_ann": inp["sig"],
                                "funding_time": pd.Series(pd.to_datetime(x["ftime"].clip(0), utc=True)).where(
                                    inp["j"] >= 0),
                                "funding_rate": x["fund"], "db_t": x["db"], "g_t": x["g"], "tv_t": x["tv"],
                                "fund_thr_t": x["fthr"], "ready": x["ready_4h"] & x["ready_f"],
                                "ready_4h": x["ready_4h"], "ready_funding": x["ready_f"], "side": x["side"],
                                "weight": x["w"]}))
    tt = pd.concat(tt, ignore_index=True)

    hashes = input_hashes()
    g.to_parquet(run_dir / "grid.parquet", index=False)
    g_strict.to_parquet(run_dir / "controls_strict.parquet", index=False)
    split = lambda rs: (pd.DataFrame([r for r in rs if r["style"] != STRICT]),  # noqa: E731
                        pd.DataFrame([r for r in rs if r["style"] == STRICT]))
    split(fold)[0].to_parquet(run_dir / "fold_metrics.parquet", index=False)
    cm, cm_s = split(cm_rows)
    cm.to_parquet(run_dir / "config_metrics.parquet", index=False)
    cm_s.to_parquet(run_dir / "controls_strict_config_metrics.parquet", index=False)
    bt, bt_s = split(boot_rows)
    dg, dg_s = split(diag)
    assert len(cm) == 10 and len(bt) == 360 and len(dg) == 240 and len(bt_s) == 72
    tt.to_parquet(run_dir / "adaptive_thresholds.parquet", index=False)
    pd.DataFrame(wf_score_rows).to_parquet(run_dir / "walkforward_scores.parquet", index=False)
    pd.DataFrame(wf_choice_rows).to_parquet(run_dir / "walkforward_choices.parquet", index=False)
    dg.to_parquet(run_dir / "signal_diagnostics.parquet", index=False)
    dg_s.to_parquet(run_dir / "signal_diagnostics_controls_strict.parquet", index=False)
    bt.to_parquet(run_dir / "bootstrap.parquet", index=False)
    bt_s.to_parquet(run_dir / "bootstrap_controls_strict.parquet", index=False)
    pd.DataFrame(comp).to_parquet(run_dir / "style_comparison.parquet", index=False)
    dump = lambda o, f: (run_dir / f).write_text(json.dumps(o, indent=2, default=str), encoding="utf-8")  # noqa: E731
    pick = lambda pre: {k: v for k, v in sel.items() if k.startswith(pre) and "RESELECTED" not in k}  # noqa: E731
    dump(pick("Q_"), "selected_quantile.json")
    dump(pick("WF_"), "selected_walkforward.json")
    dump(pick("G3_ADAPT_DEV"), "selected_adaptive.json")
    dump(sel.get("G3_ADAPT_RESELECTED"), "reselected_adaptive.json")
    dump({**{k: {**info[k], "parity_vs_batch3": parity[k]} for k in CONTROLS},
          **{k: {**info[k], "semantics": "strict funding_time < T", "codex_reference": strict_ref[k]}
             for k in CONTROL_STRICT_REF}}, "controls.json")
    counts = {"adaptive_logical": 8, "style_Q": 4, "style_WF": 4, "control_logical": 2, "logical": 10,
              "sims_adaptive": 48, "sims_control": 12, "sims": 60,
              "sims_control_strict_report_only": 12, "threshold_rows": len(tt),
              "refits": {cid(p): len(anchors(p["H"], p["C"])) for p in WFCFG}, "wf_score_rows": len(wf_score_rows),
              "dev_eligible_adaptive": int(ad.DEV_eligible.sum())}
    manifest = {
        "run_id": run_id, "parent_run_id": PARENT, "created_utc": datetime.now(timezone.utc).isoformat(),
        "spec": "scratchpad codex_batch4_spec.md (Codex thread 01a124b2-450d-7912-9bf7-9dc192b924f6, 2026-10-10)",
        "frozen_hypothesis": "G3 is more stable when every decision boundary (score/SVI/funding/target-vol) is a "
                             "trailing quantile of recent market distribution (past data only), not an absolute "
                             "constant; walk-forward periodically reselects the quantile meta-setting by recent "
                             "two-sided net",
        "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()}, "window_days": WIN_DAYS,
        "data_cutoff": str(b2.END),
        "sources": {"dev_market": str(b2.DEV_MARKET), "test_market": str(b2.SNAP / "market_1m.parquet"),
                    "dev_funding": str(b2.DEV_FUNDING), "test_funding": str(b2.SNAP / "funding_model_input.parquet"),
                    "engine_batch2": str(B2_PATH), "batch3": str(B3_PATH), "batch3_run": str(PARENT_DIR)},
        "input_sha256": hashes, "code_sha256": code_hash, "git": b2.git_state(), "counts": counts,
        "adaptive_defs": {"trend": TREND, "svi_w": SVI_W, "sigma_bars": 180, "inner_grid_W_q": INNER,
                          "style_Q": [cid(p) for p in QCFG], "style_WF": {cid(p): p for p in WFCFG},
                          "wf_warm_days": WARM, "wf_anchors": {cid(p): [str(r) for r in anchors(p["H"], p["C"])]
                                                               for p in WFCFG},
                          "boundaries": "db=Q_q|score|, g=Q_q|SVI|, tv=Q_q sigma_ann over previous 6W 4h decisions; "
                                        "fund_thr=Q_q funding rates in [ft_j-W, ft_j); no numeric cutoffs"},
        "controls": {k: {"params": v, "role": "control (excluded from selection)", "batch3_net4": CONTROL_NET4[k]}
                     for k, v in CONTROLS.items()},
        "control_vs_adaptive": "controls replay Batch-3 fixed-threshold G3; CONTROL_B3_RESELECTED was TEST-selected",
        "test_selection_flag": {"G3_ADAPT_RESELECTED": "chosen on TEST; never independent OOS"},
        "control_parity": parity, "control_strict_vs_codex": strict_ref, "picks": picks,
        "funding_rule": "strict: funding event usable only if funding_time < T (coordinator correction, Codex "
                        "Batch-3 review HIGH); controls also replayed in original Batch-3 semantics for parity",
        "execution": {"tick": b2.TICK, "offsets_bps": OFFSETS, "penetration_bps": PENS, "ttl_min": b2.TTL_TREND,
                      "exit_quote_bps": b2.EXIT_QUOTE_BPS, "requote_min": b2.REQUOTE_MIN, "cost_bps_rt": 4,
                      "report_only_bps_rt": 8, "slippage": 0, "terminal_open": "MTM + reserved 2 bps exit",
                      "funding": "PESS", "weight": "entry_weight_frozen min(1, tv_t/sigma_ann_t)"},
        "selection": "Batch-3 eligible()/dev_score()/adapt_score()/verdict() unchanged; adaptive 8 only",
        "bootstrap": {"type": "stationary", "blocks_days": BLOCKS, "n": NBOOT, "seed": SEED,
                      "stat": "mean daily 1m-MTM net4 (bps/day)"},
        "causality_asserts": "1-14 per spec section 13 (runtime)", "interpretations": __doc__,
        "runtime_sec": round(time.time() - t0, 1)}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    picked = set(picks.values())
    with (run_dir / "runs.jsonl").open("x", encoding="utf-8") as fh:      # write-once
        for r in g.to_dict("records"):
            fh.write(canonical({"run_id": run_id, "parent_run_id": PARENT, "sim_id": r["sim_id"],
                                "config_id": r["config_id"], "style": r["style"], "selected": r["config_id"] in picked,
                                **{k: v for k, v in r.items() if k.endswith(("net4", "net8", "_closed"))}}) + "\n")
    if not args.no_registry:
        print(f"[registry] {write_registry(g, sel, hashes, run_id, g_strict=g_strict)}", flush=True)
    print(f"[done] {run_id} {time.time()-t0:.0f}s", flush=True)
    return run_dir


if __name__ == "__main__":
    main()
