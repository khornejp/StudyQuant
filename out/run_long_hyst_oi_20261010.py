"""LONG-HYST-OI (2026-10-10): long-only S180 exit hysteresis x 24h open-interest entry gate.

Spec: scratchpad codex_long_fix.md section "(c) 정확한 grid·구현 명세" (Codex session
01a124f0-445a-7381-96d0-b192e0cd0daa). Skeleton: out/run_long_breadth_20261010.py (copied, not edited).
Parent run NM-B5-20261010T080025Z-c55285f2 (LONG_DEV_PICK = G5-S180-c+0.0-W180-P65, long sleeve parity source).
Frozen hypothesis: (1) keeping entry at score >= 0.50 AND SVI180 >= 0.10 but exiting only at a lower boundary merges
the short loss/re-entry cycles into one regime position; (2) requiring 24h OI growth (robust z) for new entries keeps
only rallies backed by new futures positions. Either should raise the DEV bootstrap floor and make TEST boot p05 > 0.
Fixed: long-only, trend (42,168,504), SVI 180, vol W180-P65, maker 4 bps rt, real funding PESS, offset {2,5} x pen
{0.5,1,2}, TTL 60m, exit quote 2 bps, requote 60m, continuous 2020-01-01..2026-10-08 (exclusive) sim.
Grid: exit (score_exit, svi_exit) {(0.50,0.10),(0.25,0.05),(0.00,0.00)} x OI gate {OFF, zOI24>=-0.5, zOI24>=0}
= 9 logical, 54 sims.
Engine: Batch-5 build_state/core_signal/prefix_checks + Batch-2 simulate/Book/bootstrap/asof_values + Batch-1
trailing_robust_z + Batch-3 window_bounds + Batch-4 prefix_market imported unchanged via importlib.
Times: bar_time = market_time[dec4] (open of the 4h bar's last 1m bar, = stored 'decision_time' of earlier runs);
decision_available_time T = bar_time + 1m. All inputs available_time <= T.
OI: OI_T = latest met.oi with available_time <= T and T - available_time <= 10m; OI_24 = same at T-24h;
dOI24 = log(OI_T / OI_24); zOI24 = robust z over the previous 1080 decisions (current excluded, >= 540 finite,
MAD <= 0 or missing -> NaN). Gate fails closed on NaN.
Signal (target state per decision): ready = score, SVI, weight finite. flat: target 1 iff ready & score >= 0.50 &
SVI >= 0.10 & OI gate. target 1: stays 1 until not-ready OR score < score_exit OR SVI < svi_exit. The OI gate is
evaluated only on flat->1 target transitions; a held target never drops because of OI. Interpretation: like
Batch-5 the state lives on the target; if the entry order expires unfilled the simulator re-quotes while the target
stays 1 without re-checking OI (count of such entries reported as gate_fail_fills).
DEV-only selection: (1) DEV-A and DEV-B 6/6 exec cells long net4 > 0; (2) DEV-FULL primary closed >= 40 and fill
>= 0.10; (3) dev_score = min DEV-A/DEV-B long boot p05 over 20/60/120; drop if < baseline -0.329384 (the
(0.50,0.10,OFF) value, asserted); (4) maximise dev_score; (5) ties: DEV-B net4 desc, DEV-A net4 desc, DEV-FULL MDD
asc, config id; (6) TEST columns never used. No eligible config -> LH_DEV_BEST_INELIGIBLE (rules 4-5 on all 9).
TEST success: pick 6/6 cells TEST long net4 > 0 and TEST boot p05 20/60/120 all > 0 (no closed cutoff).
top1/top3 share: per-trade window net4 contribution (Book.window partition), largest k / window net4.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.sim import provenance, registry  # noqa: E402
from btcusdt_quant.sim.store import canonical  # noqa: E402

B5_PATH = ROOT / "out/run_new_model_batch5_20261010.py"
_s = importlib.util.spec_from_file_location("nm_b5", B5_PATH)
b5 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(b5)
b2, b3, b4 = b5.b2, b5.b3, b5.b4
OUT_BASE = ROOT / "out/long_hyst_oi_20261010"
PARENT = "NM-B5-20261010T080025Z-c55285f2"
PARENT_DIR = ROOT / "out/new_model_batch5_20261010" / PARENT
REGISTRY = b2.REGISTRY
MIN, DAY = b2.MIN, b2.DAY
WINDOWS, BLOCKS, OFFSETS, PENS, PRIMARY = b2.WINDOWS, b2.BLOCKS, b5.OFFSETS, b5.PENS, b5.PRIMARY
TREND, SW, VOL = (42, 168, 504), 180, "W180-P65"
ENTRY = (0.50, 0.10)
EXITS = ((0.50, 0.10), (0.25, 0.05), (0.00, 0.00))
OIS = (None, -0.5, 0.0)
GRID = [(se, ve, g) for se, ve in EXITS for g in OIS]
BASE = (0.50, 0.10, None)
OI_N, OI_MIN, OI_AGE = 1080, 540, 10 * MIN
BASE_DEV_SCORE = -0.329384
B5_PICK = dict(struct="S180", c=0.0, vol=VOL)


def cid(se: float, ve: float, g) -> str:
    return f"LH-S180-W180P65-x{se:.2f}-{ve:.2f}-oi" + ("OFF" if g is None else f"{g:+.1f}")


def oi_state(met: pd.DataFrame, T: np.ndarray) -> dict:
    """dOI24 / zOI24 per decision from OI with available_time <= T (and <= T-24h), age <= 10m."""
    av, oi = met.available_time.array.asi8, met.oi.to_numpy(float)
    assert np.all(np.diff(av) > 0), "metrics available_time not strictly increasing"
    oi = np.where(oi > 0, oi, np.nan)
    o_t, o_24 = b2.asof_values(av, oi, T, OI_AGE), b2.asof_values(av, oi, T - DAY, OI_AGE)
    p_t, p_24 = np.searchsorted(av, T, "right") - 1, np.searchsorted(av, T - DAY, "right") - 1
    a_t = np.where(np.isfinite(o_t), av[np.maximum(p_t, 0)], np.iinfo(np.int64).min)
    a_24 = np.where(np.isfinite(o_24), av[np.maximum(p_24, 0)], np.iinfo(np.int64).min)
    assert np.all(a_t <= T) and np.all(a_24 <= T - DAY), "OI input after decision"
    d = np.log(o_t / o_24)
    return dict(oi_t=o_t, oi_24=o_24, avail_t=a_t, avail_24=a_24, doi=d, zoi=b2.b1.trailing_robust_z(d, OI_N, OI_MIN))


def long_hysteresis_signal(st: dict, zoi, score_exit: float, svi_exit: float, oi_cut) -> dict:
    sc, svi, wv = st["score"][TREND], st["svi"][SW], st["w"][VOL]
    with np.errstate(invalid="ignore"):
        ready = np.isfinite(sc) & np.isfinite(svi) & np.isfinite(wv)
        ent = ready & (sc >= ENTRY[0]) & (svi >= ENTRY[1])
        if oi_cut is not None:
            ent &= zoi >= oi_cut                       # NaN -> False (fail-closed)
        ext = ~ready | (sc < score_exit) | (svi < svi_exit)
    side, t = np.zeros(len(sc), int), 0
    for k in range(len(sc)):
        t = int(ent[k]) if t == 0 else int(not ext[k])
        side[k] = t
    return dict(side=side, w=np.where(side == 1, wv, 0.0), ent=ent, ext=ext)


def trade_part(book, a: int, b: int) -> np.ndarray:
    """Per-trade window net4 contribution (same partition as Book.window part4)."""
    if not len(book.s):
        return np.zeros(0)
    legs = ((book.j0 >= a) & (book.j0 < b)).astype(float) + ((book.jx >= a) & (book.jx < b))
    fm = (book.f_min >= a) & (book.f_min < b)
    fund = np.bincount(book.f_tid[fm], book.f_cf[fm], minlength=len(book.s))
    return book.gross_upto(b) - book.gross_upto(a) + fund - 2 * book.w * legs


def top_share(part: np.ndarray, net: float, k: int) -> float:
    return float(np.sort(part)[::-1][:k].sum() / net) if net != 0 and len(part) else np.nan


def dev_eligible(R: dict) -> bool:
    ok = all(R[(o, p)][w]["long_net4"] > 0 for o in OFFSETS for p in PENS for w in ("DEV-A", "DEV-B"))
    p = R[PRIMARY]["DEV-FULL"]
    return bool(ok and p["long_closed"] >= 40 and p["fill_notional_rate"] >= 0.10)


def select(cm: pd.DataFrame, base_score: float) -> tuple[str, bool]:
    """DEV-only pick (rules 1-6); returns (config_id, eligible_pool)."""
    el = cm[cm.dev_eligible & (cm.dev_score >= base_score)]
    pool = el if len(el) else cm
    return pool.sort_values(["dev_score", "DEV-B_net4", "DEV-A_net4", "DEV-FULL_mdd", "config_id"],
                            ascending=[False, False, False, True, True]).iloc[0].config_id, bool(len(el))


def test_success(R: dict, boot: dict) -> dict:
    f = {"cells_6of6": all(R[(o, p)]["TEST"]["long_net4"] > 0 for o in OFFSETS for p in PENS),
         "boot_all_pos": all(boot[("TEST", bl)] > 0 for bl in BLOCKS)}
    return {**f, "SUCCESS": all(f.values())}


def run_cells(m, dec4, wb, sig: dict):
    """6 exec cells; returns R[(off,pen)][window], primary book."""
    R, pb = {}, None
    for off in OFFSETS:
        for pen in PENS:
            tr, od = b2.simulate(m, "state", dec4, sig["side"], sig["w"], off, b2.TTL_TREND, pen, 0, m.N)
            bk = b2.Book(m, tr, od, 0, m.N)
            ev = {k: bk.window(a, b) for k, (a, b) in wb.items()}
            assert all(abs(e["short_net4"]) < 1e-12 and e["short_closed"] == 0 for e in ev.values()), "long-only"
            R[(off, pen)] = ev
            if (off, pen) == PRIMARY:
                pb = bk
    return R, pb


def config_row(c, R, pb, wb):
    row, boot = {"config_id": c}, {}
    daily = pb.daily(0, pb.m.N)
    for k, (a, b) in wb.items():
        e = R[PRIMARY][k]
        part = trade_part(pb, a, b)
        assert abs(part.sum() - e["long_net4"]) < 1e-6 * max(1, abs(e["long_net4"])), "trade partition"
        row.update({f"{k}_{x}": e[f"long_{x}"] for x in ("net4", "net8", "closed", "entries", "open_n", "win",
                                                           "exp_days")})
        row.update({f"{k}_mdd": e["mdd_1m"], f"{k}_sharpe": e["sharpe"], f"{k}_fill": e["fill_notional_rate"],
                    f"{k}_top1": top_share(part, e["long_net4"], 1), f"{k}_top3": top_share(part, e["long_net4"], 3)})
        dw = daily[a // 1440:b // 1440]
        row.update({f"{k}_days_pos": int((dw > 0).sum()), f"{k}_days_neg": int((dw < 0).sum()),
                    f"{k}_days_zero": int((dw == 0).sum())})
        for o in OFFSETS:
            for p in PENS:
                for x in ("net4", "entries", "closed", "open_n"):
                    row[f"{k}_o{o}_p{p}" + ("" if x == "net4" else f"_{x}")] = R[(o, p)][k][f"long_{x}"]
        for bl in BLOCKS:
            boot[(k, bl)] = b2.stationary_boot_p05(dw, bl)
            row[f"{k}_boot{bl}"] = boot[(k, bl)]
    return row, boot


def no_forced_exit(off: dict, gated: dict) -> dict:
    """OI gate only delays entries: gated target <= OFF target, and once gated is 1 it follows OFF exactly."""
    a, b = off["side"], gated["side"]
    assert np.all(b <= a), "gated target above OFF target"
    k = np.flatnonzero(b[:-1] == 1) + 1
    assert np.array_equal(b[k], a[k]), "OI gate changed a held target"
    return {"held_decisions_checked": int(len(k)), "gate_delayed_decisions": int((a != b).sum())}


def parity_b5(R: dict, pb, row: dict, boot: dict, wb: dict) -> dict:
    """(0.50,0.10,OFF) vs stored Batch-5 LONG_DEV_PICK long sleeve: 6 cells, trades, daily, bootstrap."""
    old = json.loads((PARENT_DIR / "selected_long.json").read_text(encoding="utf-8"))["LONG_DEV_PICK"]
    cells = max(abs(R[(o, p)][w]["long_net4"] - old["cells_net4"][w][f"o{o}_p{p}"]["long"])
                for o in OFFSETS for p in PENS for w in WINDOWS)
    bt = max(abs(boot[(w, bl)] - x) for w in WINDOWS for bl, x in zip(BLOCKS, old["bootstrap_p05"][w]["long"]))
    ot = pd.read_parquet(PARENT_DIR / "trades/LONG_DEV_PICK.parquet")
    ot = ot[ot.side > 0].reset_index(drop=True)
    nt = pb.tr.reset_index(drop=True)
    cols = ["side", "entry_weight_frozen", "decision_idx", "entry_idx", "entry_px", "exit_decision_idx", "exit_idx",
            "exit_px", "open_at_end"]
    tr_eq = len(ot) == len(nt) and all(np.array_equal(ot[c].to_numpy(), nt[c].to_numpy(), equal_nan=True)
                                       for c in cols)
    tr_net = float(np.max(np.abs(ot.net4_full.to_numpy() - pb.net4_full))) if tr_eq else np.inf
    od = pd.read_parquet(PARENT_DIR / "daily/LONG_DEV_PICK.parquet")
    nd = pb.daily(0, pb.m.N)
    daily = float(np.max(np.abs(od.net4_long.to_numpy() - nd))) if len(od) == len(nd) else np.inf
    out = {"cells_max_abs_diff": cells, "boot_max_abs_diff": bt, "trades_equal": bool(tr_eq), "n_trades": len(nt),
           "trades_net4_max_abs_diff": tr_net, "daily_max_abs_diff": daily,
           "TEST_net4": row["TEST_net4"], "DEV-FULL_net4": row["DEV-FULL_net4"], "TEST_closed": row["TEST_closed"]}
    assert cells <= 1e-6 and bt <= 1e-9 and tr_eq and tr_net <= 1e-6 and daily <= 1e-6, out
    return out


def oi_prefix_check(m, dec4, met, st, oi, cut=b5.CUT) -> dict:
    """OI future tamper / cutoff prefix: zOI, gated targets and truncated simulations equal the full-run prefix."""
    mp = b4.prefix_market(m, cut)
    d = dec4[dec4 < mp.N]
    k = len(d)
    end = m.t[mp.N - 1] + MIN
    mt = met.copy()
    mt.loc[mt.available_time.array.asi8 > end, "oi"] *= 1.7
    ot = oi_state(mt, st["T"])
    stp = b5.build_state(mp, d)
    op = oi_state(met.loc[met.available_time.array.asi8 <= end].reset_index(drop=True), stp["T"])
    for o2 in (ot, op):
        for x in ("doi", "zoi", "avail_t", "avail_24"):
            assert np.array_equal(oi[x][:k], o2[x][:k], equal_nan=True), f"OI prefix {x}"
    out = {}
    for se, ve, g in GRID:
        if g is None:
            continue
        c = cid(se, ve, g)
        full, pre = long_hysteresis_signal(st, oi["zoi"], se, ve, g), long_hysteresis_signal(stp, op["zoi"], se, ve, g)
        for x in ("side", "w"):
            assert np.array_equal(full[x][:k], pre[x], equal_nan=True), f"OI prefix signal {c} {x}"
        tf, _ = b2.simulate(m, "state", dec4, full["side"], full["w"], 2, b2.TTL_TREND, 0.5, 0, m.N)
        tp, _ = b2.simulate(mp, "state", d, pre["side"], pre["w"], 2, b2.TTL_TREND, 0.5, 0, mp.N)
        cl = tp[~tp.open_at_end].reset_index(drop=True)
        assert cl.equals(tf.iloc[:len(cl)].reset_index(drop=True)), f"OI prefix trades {c}"
        if tp.open_at_end.any():
            r0, r1 = tp[tp.open_at_end].iloc[0], tf.iloc[len(cl)]
            assert all(r0[x] == r1[x] for x in ("side", "decision_idx", "entry_idx", "entry_px")), f"OI open {c}"
        out[c] = {"prefix_closed_trades_equal": int(len(cl)), "prefix_open": int(tp.open_at_end.sum())}
    return {"cut": str(cut), "decisions_compared": int(k), "tamper": "oi x1.7 for available_time > cut",
            "configs": out}


def write_registry(cm: pd.DataFrame, parity: dict, pick: str, hashes: dict, run_id: str, path: Path = REGISTRY) -> dict:
    have = b2.registry_keys(path)
    ih = hashlib.sha256(canonical(hashes).encode()).hexdigest()
    added = skipped = 0
    base = {"run_id": run_id, "parent_run_id": PARENT, "data_cutoff": str(b2.END),
            "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()},
            "costs": "4 bps rt maker flat, 0 slip, PESS funding; 8 bps report-only", "hypothesis": "LONG-HYST-OI"}

    def put(key_obj, entry):
        nonlocal added, skipped
        key = hashlib.sha256(canonical({"batch": "LH", **key_obj, "inputs": ih}).encode()).hexdigest()
        if key in have:
            skipped += 1
            return
        registry.record(path, {**entry, "idempotency_key": key, "input_hashes": hashes})
        have.add(key)
        added += 1

    for r in cm.to_dict("records"):
        put({"config_id": r["config_id"]}, {
            "experiment": f"LH {r['config_id']}", "role": "trial", "config": {"config_id": r["config_id"], **base},
            "n_trials": 1, "n_simulations": 6, "selected": r["config_id"] == pick,
            "result_summary": {f"{w}_{x}": r[f"{w}_{x}"] for w in WINDOWS for x in ("net4", "net8", "closed")}})
    put({"parity": True}, {"experiment": "LH parity: (0.50,0.10,OFF) vs Batch-5 LONG_DEV_PICK long sleeve",
                           "role": "control", "config": base, "n_trials": 0, "n_simulations": 0,
                           "result_summary": parity})
    return {"added": added, "skipped": skipped}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-registry", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    code_hash = provenance.file_sha256(Path(__file__))
    run_id = f"LH-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{code_hash[:8]}"
    run_dir = OUT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=False)          # write-once
    minutes, met, prem, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes, prem
    wb = b3.window_bounds(m)
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    oi = oi_state(met, st["T"])
    sigs = {cid(*g): long_hysteresis_signal(st, oi["zoi"], *g) for g in GRID}
    ref = b5.core_signal(st, B5_PICK)
    assert np.array_equal(sigs[cid(*BASE)]["side"] == 1, ref["side"] == 1), "baseline long decisions != Batch-5"
    nfe = {cid(*g): no_forced_exit(sigs[cid(g[0], g[1], None)], sigs[cid(*g)]) for g in GRID if g[2] is not None}
    pre = b5.prefix_checks(m, dec4, st, {cid(*g): (lambda st_, p: long_hysteresis_signal(st_, None, *p), g)
                                         for g in GRID if g[2] is None})
    pre_oi = oi_prefix_check(m, dec4, met, st, oi)
    print(f"[state] {time.time()-t0:.0f}s prefix ok", flush=True)

    rows, boot_rows, R_all, trades = [], [], {}, []
    for (se, ve, g), (c, sg) in zip(GRID, sigs.items()):
        R, pb = run_cells(m, dec4, wb, sg)
        R_all[c] = R
        row, boot = config_row(c, R, pb, wb)
        ent_gate = np.ones(len(dec4), bool) if g is None else (oi["zoi"] >= g)
        di = np.searchsorted(dec4, pb.tr.decision_idx.to_numpy())
        row.update({"score_exit": se, "svi_exit": ve, "oi_gate": "OFF" if g is None else f"zOI24>={g}",
                    "long_decisions": int(sg["side"].sum()), "gate_fail_fills": int((~ent_gate[di]).sum()),
                    "dev_eligible": dev_eligible(R),
                    "dev_score": min(boot[(w, bl)] for w in ("DEV-A", "DEV-B") for bl in BLOCKS),
                    **{f"TEST_{k}": x for k, x in test_success(R, boot).items()}})
        rows.append(row)
        if (se, ve, g) == BASE:
            parity = parity_b5(R, pb, row, boot, wb)
        tr = pb.tr.assign(config_id=c, net4_full=pb.net4_full)
        tr["bar_time"] = pd.to_datetime(m.t[tr.decision_idx], utc=True)
        tr["decision_available_time"] = tr.bar_time + pd.Timedelta(minutes=1)
        tr["entry_time"] = pd.to_datetime(m.t[tr.entry_idx], utc=True)
        tr["zOI24_at_decision"] = oi["zoi"][di]
        trades.append(tr)
        boot_rows += [{"config_id": c, "window": w, "block_days": bl, "p05_mean_day": x} for (w, bl), x in boot.items()]
        print(f"[sim] {c} {time.time()-t0:.0f}s", flush=True)
    cm = pd.DataFrame(rows)
    cm["DEV-FULL_mdd"] = cm["DEV-FULL_mdd"].astype(float)
    base_score = float(cm.set_index("config_id").loc[cid(*BASE), "dev_score"])
    assert abs(base_score - BASE_DEV_SCORE) < 1e-6, base_score
    pick, elig_pool = select(cm.drop(columns=[c for c in cm if c.startswith("TEST")]), base_score)
    print(f"[parity] {parity}", flush=True)

    hashes = {"batch5_code": provenance.file_sha256(B5_PATH), "batch5_selected_long": provenance.file_sha256(
        PARENT_DIR / "selected_long.json"), "batch5_trades_long": provenance.file_sha256(
        PARENT_DIR / "trades/LONG_DEV_PICK.parquet"), "batch5_daily_long": provenance.file_sha256(
        PARENT_DIR / "daily/LONG_DEV_PICK.parquet"),
        **{k: v for k, v in b5.input_hashes().items() if k != "code"}, "code": code_hash}
    cm.to_parquet(run_dir / "config_metrics.parquet", index=False)
    pd.DataFrame(boot_rows).to_parquet(run_dir / "bootstrap.parquet", index=False)
    pd.concat(trades, ignore_index=True).to_parquet(run_dir / "trades_primary.parquet", index=False)
    bar = pd.to_datetime(m.t[dec4], utc=True)
    nat = lambda x: pd.to_datetime(np.where(x > 0, x, np.iinfo(np.int64).min), utc=True)  # noqa: E731
    pd.DataFrame({"bar_time": bar, "decision_available_time": pd.to_datetime(st["T"], utc=True),
                  "oi_T_available_time": nat(oi["avail_t"]), "oi_24_available_time": nat(oi["avail_24"]),
                  "oi_T": oi["oi_t"], "oi_24": oi["oi_24"], "dOI24": oi["doi"], "zOI24": oi["zoi"],
                  "score": st["score"][TREND], "svi": st["svi"][SW], "w": st["w"][VOL],
                  **{f"target|{c}": s["side"] for c, s in sigs.items()}}).to_parquet(run_dir / "decisions.parquet",
                                                                                   index=False)
    pd.DataFrame([{"sim_id": f"{c}|offset={o}|pen={p}", "config_id": c, "offset": o, "pen_bps": p, "window": w,
                   **R_all[c][(o, p)][w]} for c in R_all for o in OFFSETS for p in PENS for w in WINDOWS]
                 ).to_parquet(run_dir / "fold_metrics.parquet", index=False)
    pk = cm.set_index("config_id").loc[pick]
    manifest = {"run_id": run_id, "parent_run_id": PARENT, "created_utc": datetime.now(timezone.utc).isoformat(),
                "spec": "scratchpad codex_long_fix.md (c) (Codex 01a124f0-445a-7381-96d0-b192e0cd0daa)",
                "name": "LONG-HYST-OI", "frozen_hypothesis_and_interpretations": __doc__,
                "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()}, "data_cutoff": str(b2.END),
                "counts": {"logical": len(GRID), "sims": len(GRID) * 6, "n_trials": len(GRID)},
                "pick": pick, "pick_label": "LH_DEV_PICK" if elig_pool else "LH_DEV_BEST_INELIGIBLE",
                "base_dev_score": base_score, "n_dev_eligible": int(cm.dev_eligible.sum()),
                "n_pass_rule3": int((cm.dev_eligible & (cm.dev_score >= base_score)).sum()),
                "pick_TEST": {k: bool(pk[f"TEST_{k}"]) for k in ("cells_6of6", "boot_all_pos", "SUCCESS")},
                "all_runs": cm[["config_id", "dev_eligible", "dev_score"] + [f"{w}_{x}" for w in WINDOWS for x in (
                    "net4", "closed", "boot20", "boot60", "boot120")] + ["TEST_SUCCESS"]].to_dict("records"),
                "parity_b5_long_sleeve": parity, "prefix_checks_market": pre, "prefix_checks_oi": pre_oi,
                "oi_no_forced_exit": nfe,
                "oi_coverage": {"decisions": int(len(dec4)), "doi_finite": int(np.isfinite(oi["doi"]).sum()),
                                "zoi_finite": int(np.isfinite(oi["zoi"]).sum()),
                                "first_zoi": str(bar[np.isfinite(oi["zoi"])][0])},
                "input_sha256": hashes, "git": b2.git_state(), "runtime_sec": round(time.time() - t0, 1)}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    if not args.no_registry:
        print(f"[registry] {write_registry(cm, parity, pick, hashes, run_id)}", flush=True)
    print(f"[done] {run_id} pick={pick} {time.time()-t0:.0f}s", flush=True)
    return run_dir


if __name__ == "__main__":
    main()
