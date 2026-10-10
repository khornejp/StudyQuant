"""R2-56: single continuous-ledger replay of 6 existing candidates (no model fits).

Window 2026-01-01 .. 2026-10-07 23:59 UTC (R2-54 FINAL snapshot) plus each rule's native 2023-2025 window as
reference. Costs: maker flat 4 bps round trip, no slippage, PESS funding; 8 bps report-only.

  1 B3_AXC0, 2 K04_AXC0  - scripts/sim_r2_55.py path (R2-52A AXC0 tables, causal_guard=True, W10 k from
                           r2_55/selection/selected_k.csv); parity vs r2_55/test/run_01 report.
  3 C1 F_V5+E_V1a, 4 C1 F_V5r+E_V1a, 5 C4 F_V0+E_V1a - out/run_k45_decision_cadence_r2_37.py path; one continuous
                           ledger 2020..2026-10-07; October LS from futures_global_ls_5m, October funding from the
                           snapshot funding_live_table (REST rows). Parity vs R2-37 HOLD_B/HOLD_A cells.
  6 SWITCH               - per entry decision time: R2-44 w730_raw causal M rank (30 d trailing, strictly earlier)
                           M >= 2/3 -> C4 legs (F3-w30/V0 + E1/V1a) else C1 legs (F3/V5 + E1/V1a); single book FIRST.

Usage: venv_btcusdt\\Scripts\\python.exe scripts\\sim_r2_56_replay.py
"""
from __future__ import annotations
import importlib.util, json, math, sys, time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from btcusdt_quant.sim import provenance, registry, rolling  # noqa: E402
from btcusdt_quant.sim.strategies import Context  # noqa: E402
import sim_adaptive_exit as ax  # noqa: E402
import sim_strategy_rolling as plan2  # noqa: E402
import sim_r2_55 as r255  # noqa: E402
from out import run_k45_decision_cadence_r2_37 as r237  # noqa: E402
from out import run_k45_ls_ratio_timing_r2_35 as r235  # noqa: E402
from out import run_k45_single_book_combo_r2_24 as r224  # noqa: E402

O = ROOT / "out/k45_rl_r2_48_20261007"
OUT = O / "r2_56"
SNAP = O / "r2_54/stageb_snapshot"
STAGE_A = O / "r2_54/stage_a_2026/stage_a_2026.parquet"
R237 = ROOT / "out/k45_decision_cadence_r2_37_20261006"
PRED_ROOT = ROOT / "out/k45_vol_detector_r2_44_window_20261006/folds/w730_raw"
REGISTRY = ROOT / "out/sim_registry.jsonl"
A, B = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-10-08", tz="UTC")
NA, NB = pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2026-01-01", tz="UTC")
AX_NATIVE_A = pd.Timestamp("2023-09-01", tz="UTC")
PARITY = {"B3": 2347.842551706386, "K04": 2587.292719709675}
C_SPECS = {"C1_F_V5+E_V1a": ("C1", "F_V5+E_V1a", "F3", "V5"), "C1_F_V5r+E_V1a": ("C1", "F_V5r+E_V1a", "F3", "V5r"),
           "C4_F_V0+E_V1a": ("C4", "F_V0+E_V1a", "F3-w30", "V0")}
HI = 2 / 3
LOG: list[str] = []


def log(message: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {message}"
    print(line, flush=True); LOG.append(line)


r237.log = log          # never append to the R2-37 run.log


def U(x) -> pd.Series:
    return pd.to_datetime(x, utc=True, format="ISO8601").astype("datetime64[ns, UTC]")


def dd(values: np.ndarray) -> float:
    path = np.r_[0.0, np.cumsum(values)]
    return float(np.max(np.maximum.accumulate(path) - path))


def monthly(minute: pd.Series) -> dict:
    g = minute.groupby(minute.index.strftime("%Y-%m")).sum()
    return {k: float(v) for k, v in g.items()}


# ---------------------------------------------------------------- 1,2 AXC0
def axc0_runs() -> dict:
    sel = pd.read_csv(O / "r2_55/selection/selected_k.csv")
    out = {}
    run = r255.stageb_runner()
    snapshot = run.verify_snapshot(read_frames=False)
    ctx, _, settle = run.test_context()
    times = pd.DatetimeIndex(ctx.minutes.open_time)
    for i in ("B3", "K04"):
        k = float(sel.loc[(sel.id == i) & (sel.window == r255.LAST_WINDOW), "k"].iloc[0])
        table = r255.ax_table(ctx, i, True)
        e, e_min = ax.e_matrix(ctx.regime, times, ax.heads(i))
        res = {}
        with run.sb.ledger_settlements(settle):
            for fee, tag in ((r255.FEE4, "4bps"), (r255.FEE8, "8bps")):
                cfg = replace(ax.CONFIG, close_at_end=True, fee_per_side=fee, causal_guard=True)
                res[tag] = ax.run_ax(table, ctx.minutes, e, e_min, A, B, cfg, np.full(len(ctx.minutes), k))
        out[i] = {"k": k, "res": res}
        log(f"AXC0 {i} 2026 k={k} net4={res['4bps'].minute_pnl.sum():.6f}")
    out["_snapshot"] = snapshot["manifest_sha256"]
    # native reference: R2-52A stitched rolling test 2023-09..2025-12 with the R2-55 per-window AXC0 k
    nctx = Context.load(end=rolling.END)
    ntimes = pd.DatetimeIndex(nctx.minutes.open_time)
    windows = [w for w in rolling.WINDOWS if w.test_start >= AX_NATIVE_A]
    for i in ("B3", "K04"):
        picks = sel.loc[sel.id == i].set_index("window").k.to_dict()
        table = r255.ax_table(nctx, i, True)
        e, e_min = ax.e_matrix(nctx.regime, ntimes, ax.heads(i))
        kmin = ax.k_schedule(ntimes, picks, windows)
        a, b = windows[0].test_start, windows[-1].test_end
        res = {}
        for fee, tag in ((r255.FEE4, "4bps"), (r255.FEE8, "8bps")):
            cfg = replace(ax.CONFIG, close_at_end=True, fee_per_side=fee, causal_guard=True)
            res[tag] = ax.run_ax(table, nctx.minutes, e, e_min, a, b, cfg, kmin)
        out[i]["native"] = {"res": res, "window": [str(a), str(b)], "k": {w.name: picks[w.name] for w in windows}}
        log(f"AXC0 {i} native net4={res['4bps'].minute_pnl.sum():.3f}")
    return out


def ax_summary(res4, res8, a, b) -> tuple[dict, pd.DataFrame]:
    m4 = res4.minute_pnl
    pos = plan2.positions(res4.trades)
    by_side = pos.groupby("side").net_bps.agg(["sum", "size"])
    s = {"net_4bps": float(m4.sum()), "net_8bps": float(res8.minute_pnl.sum()), "trades": int(len(pos)),
         "win_rate": float((pos.net_bps > 0).mean()) if len(pos) else None,
         "long_net_4bps": float(by_side["sum"].get(1, 0.0)), "short_net_4bps": float(by_side["sum"].get(-1, 0.0)),
         "long_trades": int(by_side["size"].get(1, 0)), "short_trades": int(by_side["size"].get(-1, 0)),
         "side_split_basis": "position net (fees+funding); sum may differ from minute ledger by data_end marks",
         "max_drawdown_bps": dd(m4.to_numpy()), "worst_position_bps": float(pos.net_bps.min()) if len(pos) else None,
         "monthly_net_4bps": monthly(m4), "exit_reasons": res4.trades.exit_reason.value_counts().to_dict(),
         "window": [str(a), str(b)]}
    return s, pos


# ---------------------------------------------------------------- 3,4,5,6 C1/C4
def oct_extension(all_market: pd.DataFrame, all_features: pd.DataFrame, funding: pd.DataFrame):
    start = all_market.open_time.iloc[-1] + pd.Timedelta(minutes=1)
    sm = pd.read_parquet(SNAP / "market_1m.parquet")
    sm["open_time"] = U(sm.open_time)
    # snapshot vs original sources on the overlap must be identical (checked on OHLCV)
    j = all_market.merge(sm, on="open_time", suffixes=("", "_s"))
    check = {c: float((j[c] - j[c + "_s"]).abs().max()) for c in ("open", "high", "low", "close", "volume")}
    if max(check.values()) != 0.0:
        raise SystemExit(f"snapshot market differs from R2-37 sources: {check}")
    om = sm.loc[(sm.open_time >= start) & (sm.open_time < B), list(all_market.columns.intersection(sm.columns))]
    for c in all_market.columns.difference(om.columns):
        om[c] = np.nan
    om = om[all_market.columns]
    g = pd.read_parquet(SNAP / "futures_global_ls_5m.parquet")
    # feature-cache rule (verified on 2026-07..09, max |diff| 1.2e-7): value at minute t = latest create_time <= t-6m
    ls = pd.DataFrame({"t": U(g.create_time).dt.floor("5min") + pd.Timedelta(minutes=6),
                       "global_ls_account": g.long_short_ratio.astype(float)}).sort_values("t")
    ref = all_features.loc[all_features.open_time >= pd.Timestamp("2026-07-01", tz="UTC"), ["open_time", "global_ls_account"]]
    chk = pd.merge_asof(ref, ls, left_on="open_time", right_on="t", suffixes=("", "_s"))
    ls_diff = float((chk.global_ls_account - chk.global_ls_account_s).abs().max())
    if ls_diff > 1e-6:
        raise SystemExit(f"LS reconstruction mismatch {ls_diff}")
    of = pd.merge_asof(om[["open_time"]], ls, left_on="open_time", right_on="t")[["open_time", "global_ls_account"]]
    if of.global_ls_account.isna().any():
        raise SystemExit("October LS gap")
    ft = pd.read_parquet(SNAP / "funding_live_table.parquet")
    ft["raw"] = U(ft.time)
    ft = ft.loc[(ft.raw >= start) & (ft.raw < B)]
    ns, step = ft.raw.astype("int64").to_numpy(), pd.Timedelta(hours=8).value
    sched = ((ns + step // 2) // step) * step
    if len(ft) != 21 or np.abs(ns - sched).max() > pd.Timedelta(seconds=60).value:
        raise SystemExit("October funding rows/schedule")
    oct_f = pd.DataFrame({"time": pd.to_datetime(sched, utc=True), "rate": ft.rate.to_numpy(float),
                          "raw_calc_time": ft.raw.to_numpy()})
    market = pd.concat([all_market, om], ignore_index=True)
    features = pd.concat([all_features[["open_time", "global_ls_account"]], of], ignore_index=True)
    fund = pd.concat([funding[["time", "rate", "raw_calc_time"]], oct_f], ignore_index=True).sort_values("time")
    fund = fund.reset_index(drop=True)
    if (market.open_time.diff().dropna() != pd.Timedelta(minutes=1)).any() or fund.time.duplicated().any():
        raise SystemExit("extended market not contiguous or funding duplicated")
    return market, features, fund, {"snapshot_vs_source_ohlcv_max_abs": check, "ls_rule_max_abs_diff_q3": ls_diff,
                                    "oct_minutes": int(len(om)), "oct_funding_rows": 21,
                                    "oct_funding_source": "snapshot funding_live_table (source=rest)"}


def legs(signals: dict, market: pd.DataFrame) -> dict:
    hold = {"F3": 24, "F3-w30": 12, "E1": 20}
    need = {("F3", "V5"), ("F3", "V5r"), ("F3-w30", "V0"), ("E1", "V1a")}
    return {key: r237.simulate(signals[key], market, hold[key[0]], f"{key[0]}/{key[1]}") for key in need}


def build_books(leg: dict) -> dict:
    books = {}
    for name, (_, _, fs, fv) in C_SPECS.items():
        books[name] = r237.combo_book(leg[(fs, fv)], leg[("E1", "V1a")], f"{fs}/{fv}", "E1/V1a")
    return books


def regime_m() -> pd.DataFrame:
    spec = importlib.util.spec_from_file_location("r245", ROOT / "out/run_k45_vol_gated_backtest_r2_45.py")
    r245 = importlib.util.module_from_spec(spec); sys.modules["r245"] = r245; spec.loader.exec_module(r245)
    cols = [f"prediction_{t}" for t in r245.TARGETS]
    parts = [pd.read_parquet(p, columns=["timestamp", *cols]) for s in ("DEV_FRONT", "DEV_BACK")
             for p in sorted((PRED_ROOT / s).glob("fold_*_predictions.parquet"))]
    st = pd.read_parquet(STAGE_A)
    if not (st.prediction_ts == st.logical_available_at).all():
        raise SystemExit("stage-A prediction_ts != logical_available_at")
    parts.append(st.rename(columns={"prediction_ts": "timestamp"})[["timestamp", *cols]])
    f = pd.concat(parts, ignore_index=True)
    f["timestamp"] = U(f.timestamp)
    f = f.sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)
    t = pd.DatetimeIndex(f.timestamp)
    for target in r245.TARGETS:
        f[f"rank_{target}"] = r245.causal_percentile(f[f"prediction_{target}"], t)
    f["M"] = f[[f"rank_{x}" for x in r245.M_TARGETS]].mean(axis=1, skipna=False)
    f["L"] = f[[f"rank_{x}" for x in r245.L_TARGETS]].mean(axis=1, skipna=False)
    return f[["timestamp", "M", "L"]]


def state_at(times: pd.Series, reg: pd.DataFrame) -> np.ndarray:
    """M as of the decision (entry) minute: latest prediction with logical_available_at <= t, age <= 15 min."""
    q = pd.DataFrame({"t": U(times).to_numpy()}).reset_index()
    m = pd.merge_asof(q.sort_values("t"), reg.rename(columns={"timestamp": "ts"}), left_on="t", right_on="ts",
                      tolerance=pd.Timedelta(minutes=15)).sort_values("index")
    return m.M.to_numpy(float)


def switch_book(leg: dict, reg: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    pool = []
    for key, gate in (((("F3", "V5")), "C1"), ((("F3-w30", "V0")), "C4"), ((("E1", "V1a")), "both")):
        tr = leg[key].copy()
        mval = state_at(tr.entry_time, reg)
        route = np.where(np.isfinite(mval) & (mval >= HI), "C4", "C1")
        keep = np.ones(len(tr), bool) if gate == "both" else route == gate
        pool.append(tr.assign(candidate=f"{key[0]}/{key[1]}", M=mval, route=route).loc[keep])
    signals = pd.concat(pool, ignore_index=True)
    book = r224.run_single_book(signals, ["F3/V5", "F3-w30/V0", "E1/V1a"], "FIRST")[0]
    m = state_at(book.entry_time, reg)
    info = {"book_trades_M_nan": int(np.isnan(m).sum()),
            "book_trades_route_C4": int((np.isfinite(m) & (m >= HI)).sum()), "book_trades": int(len(book))}
    return book, info


def c_ledger(trades: pd.DataFrame, market: pd.DataFrame, fund: pd.DataFrame, a, b, tag: str) -> dict:
    pnl0, units = r237.fast_ledger(trades, market, fund, "PESS")
    t = market.open_time.array.asi8
    lo, hi = int(np.searchsorted(t, a.value)), int(np.searchsorted(t, b.value))
    idx = pd.DatetimeIndex(market.open_time.iloc[lo:hi])
    m4 = pd.Series(pnl0[lo:hi] - 4.0 * units[lo:hi], index=idx)
    m8 = pnl0[lo:hi] - 8.0 * units[lo:hi]
    sel = trades.loc[(trades.entry_time < b) & (trades.exit_time >= a)]
    net = r237.trade_net(sel, fund, "PESS", 4.0) if len(sel) else np.array([])
    side_net = {}
    for side, label in ((1, "long"), (-1, "short")):
        sub = trades.loc[trades.side == side]
        p, u = r237.fast_ledger(sub, market, fund, "PESS")
        side_net[label] = float((p[lo:hi] - 4.0 * u[lo:hi]).sum())
    comp = {}
    if "candidate" in trades:
        for c in sorted(trades.candidate.unique()):
            sub = trades.loc[trades.candidate == c]
            p, u = r237.fast_ledger(sub, market, fund, "PESS")
            comp[c] = {"net_4bps": float((p[lo:hi] - 4.0 * u[lo:hi]).sum()),
                       "trades": int(((sub.entry_time < b) & (sub.exit_time >= a)).sum())}
    return {"net_4bps": float(m4.sum()), "net_8bps": float(m8.sum()), "trades": int(len(sel)),
            "trades_entered_in_window": int(((sel.entry_time >= a)).sum()),
            "win_rate": float((net > 0).mean()) if len(net) else None,
            "long_net_4bps": side_net["long"], "short_net_4bps": side_net["short"],
            "long_trades": int((sel.side == 1).sum()), "short_trades": int((sel.side == -1).sum()),
            "side_split_basis": "minute ledger of side subset (exact additive)",
            "max_drawdown_bps": dd(m4.to_numpy()), "worst_position_bps": float(net.min()) if len(net) else None,
            "worst_position_basis": "full-trade net incl. pre-window part for carried trades",
            "monthly_net_4bps": monthly(m4), "components": comp,
            "exit_reasons": sel.exit_reason.value_counts().to_dict(), "window": [str(a), str(b)]}


def c_parity(hist_market, hist_features, hist_funding, all_market, all_features, all_funding) -> dict:
    """Reproduce R2-37 HOLD_B (history ledger) and HOLD_A (force_window on full) PESS 4 bps exactly."""
    bars = r237.hourly_bars(all_market)
    f3f, _ = r237.build_f3_signals(all_market, all_features, bars)
    e1f, _ = r237.build_e1_signals(all_market, bars)
    sig = {**f3f, **e1f}
    hist, full = legs(sig, hist_market), legs(sig, all_market)
    hb, fb = build_books(hist), build_books(full)
    ref = pd.read_parquet(R237 / "backtest_metrics.parquet")
    out = {}
    for name, (strategy, variant, _, _) in C_SPECS.items():
        row = {}
        for seg in ("HOLD_B", "HOLD_A"):
            s, e = r235.SEGMENTS[seg]
            if seg == "HOLD_B":
                tr, mk, fu = hb[name], hist_market, hist_funding
            else:
                tr, mk, fu = r237.force_window(fb[name], all_market, s, e), all_market, all_funding
            pnl0, units = r237.fast_ledger(tr, mk, fu, "PESS")
            daily, _ = r237.segment_daily(pnl0, units, mk, s, e, 4.0)
            want = float(ref.loc[(ref.strategy == strategy) & (ref.variant == variant) & (ref.segment == seg)
                                 & (ref.boundary == "PESS") & (ref.cost_bps == 4.0), "total_net_bps"].iloc[0])
            row[seg] = {"replay": float(daily.sum()), "reference": want, "abs_diff": abs(float(daily.sum()) - want)}
        out[name] = row
        log(f"C parity {name}: {row}")
    return out


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"experiment": "R2-56 continuous-ledger replay of 6 existing candidates", "created_utc": None,
                    "window": [str(A), str(B)], "costs": "4 bps round trip maker flat, no slippage, PESS funding; "
                    "8 bps report-only", "candidates": {}, "native": {}, "parity": {}, "deviations": []}
    # 1,2
    axr = axc0_runs()
    report["snapshot_manifest_sha256"] = axr.pop("_snapshot")
    ax_entries = {}
    for i in ("B3", "K04"):
        s, pos = ax_summary(axr[i]["res"]["4bps"], axr[i]["res"]["8bps"], A, B)
        s["k"] = axr[i]["k"]
        report["candidates"][f"{i}_AXC0"] = s
        pos.to_parquet(OUT / f"{i}_AXC0_positions_2026.parquet")
        ax_entries[i] = set(pd.DatetimeIndex(pos.entry_time))
        n = axr[i]["native"]
        ns, _ = ax_summary(n["res"]["4bps"], n["res"]["8bps"], *map(pd.Timestamp, n["window"]))
        report["native"][f"{i}_AXC0"] = {**ns, "k_per_window": n["k"]}
        report["parity"][f"{i}_AXC0"] = {"replay": s["net_4bps"], "reference": PARITY[i],
                                         "abs_diff": abs(s["net_4bps"] - PARITY[i]),
                                         "match": abs(s["net_4bps"] - PARITY[i]) < 1e-6}
    # 3,4,5
    log("load R2-37 inputs")
    hist_market, hist_features, hist_funding, all_market, all_features, all_funding = r235.load_inputs()
    for frame in (hist_market, hist_features, all_market, all_features):
        frame["open_time"] = pd.to_datetime(frame.open_time, utc=True).astype("datetime64[ns, UTC]")
    report["parity"]["C_R2_37"] = c_parity(hist_market, hist_features, hist_funding, all_market, all_features,
                                           all_funding)
    market, features, fund, ext = oct_extension(all_market, all_features, all_funding)
    report["oct_extension"] = ext
    bars = r237.hourly_bars(market)
    f3f, _ = r237.build_f3_signals(market, features, bars)
    e1f, _ = r237.build_e1_signals(market, bars)
    leg = legs({**f3f, **e1f}, market)
    books = build_books(leg)
    c_entries = {}
    for name, book in books.items():
        report["candidates"][name] = c_ledger(book, market, fund, A, B, name)
        report["native"][name] = c_ledger(book, market, fund, NA, NB, name)
        book.to_parquet(OUT / f"{name}_trades_2020_2026.parquet")
        c_entries[name] = set(pd.DatetimeIndex(book.loc[book.entry_time >= A, "entry_time"]))
        sub = report["candidates"][name]
        h1 = sum(v for k, v in sub["monthly_net_4bps"].items() if k <= "2026-06")
        q3 = sum(v for k, v in sub["monthly_net_4bps"].items() if "2026-07" <= k <= "2026-09")
        ref = report["parity"]["C_R2_37"][name]
        sub["continuous_vs_segmented"] = {"H1_continuous": h1, "H1_R2_37": ref["HOLD_B"]["reference"],
                                          "Q3_continuous": q3, "Q3_R2_37": ref["HOLD_A"]["reference"]}
    # 6
    log("R2-44 M state")
    reg = regime_m()
    sw, info = switch_book(leg, reg)
    report["candidates"]["SWITCH_C1C4"] = {**c_ledger(sw, market, fund, A, B, "SWITCH"), "routing": info}
    report["native"]["SWITCH_C1C4"] = c_ledger(sw, market, fund, NA, NB, "SWITCH")
    sw.to_parquet(OUT / "SWITCH_C1C4_trades_2020_2026.parquet")
    # mapping check on 2023-2025 (report-only): per-trade 4 bps net of C1/C4 books by M state at entry
    mcheck = {}
    for name in ("C1_F_V5+E_V1a", "C4_F_V0+E_V1a"):
        bk = books[name]
        bk = bk.loc[(bk.entry_time >= NA) & (bk.entry_time < NB)]
        net = r237.trade_net(bk, fund, "PESS", 4.0)
        m = state_at(bk.entry_time, reg)
        hi = np.isfinite(m) & (m >= HI)
        mcheck[name] = {"M_ge_2/3": {"trades": int(hi.sum()), "net_4bps": float(net[hi].sum())},
                        "else": {"trades": int((~hi).sum()), "net_4bps": float(net[~hi].sum())}}
    report["switch_mapping_2023_2025_by_state"] = mcheck
    report["regime_M_coverage"] = {"first": str(reg.timestamp.min()), "last": str(reg.timestamp.max()),
                                   "rows": int(len(reg)), "M_nan_rows_2023_on": int(reg.loc[reg.timestamp >= NA, "M"]
                                                                                      .isna().sum())}
    # overlaps (shared entry minutes in 2026)
    def ov(x, y):
        return {"a": len(x), "b": len(y), "shared": len(x & y)}
    report["overlap_2026"] = {"B3_vs_K04": ov(ax_entries["B3"], ax_entries["K04"]),
                              "C1_V5_vs_C4_V0": ov(c_entries["C1_F_V5+E_V1a"], c_entries["C4_F_V0+E_V1a"]),
                              "C1_V5r_vs_C4_V0": ov(c_entries["C1_F_V5r+E_V1a"], c_entries["C4_F_V0+E_V1a"])}
    report["causality"] = {
        "B3_AXC0/K04_AXC0": "R2-55 path: decision rows from predictions with logical_available_at <= decision, delay 1 "
                            "min fill, SimConfig causal_guard=True, k fixed from pre-2026 W10 selection, flat start "
                            "2026-01-01; funding settlements from snapshot (Oct REST rows).",
        "C1/C4": "F3 V0: LS value with archive create_time+5m strictly before T (feature cache rule t-6m). V5: LS "
                 "event evaluated at create_time+5m (here feature open_time+5m), baseline = previous full-hour "
                 "rolling quantile. V5r: event-level rolling quantile of past events. E1 V1a: partial-hour volume "
                 "and close through the closed minute, prior 19 completed bars, prior 20-bar high; entry at next "
                 "minute open. October LS rebuilt from snapshot with the same t-6m rule (verified exact on Q3).",
        "SWITCH": "M = mean of 9 M-target causal percentile ranks vs strictly earlier 30 d predictions (min 7 d); "
                  "predictions logical_available_at = prediction_ts <= entry minute (asof, age <= 15 min); "
                  "missing M -> C1 (mapping else-branch); mapping M>=2/3 -> C4 fixed, not fit on 2026.",
    }
    report["deviations"] += [
        "C1/C4 2026 is one continuous ledger (no reset at 07-01/10-01); R2-37 segmented H1/Q3 closes differ at "
        "boundaries (see continuous_vs_segmented).",
        "C trade counts follow R2-37 (entry < end and exit >= start, includes carried trades); win rate/worst "
        "position use full-trade net. AXC0 counts positions opened in-window (flat start).",
        "AXC0 native window = R2-52A stitched test 2023-09-01..2026-01-01 with per-window R2-55 AXC0 k "
        "(causal_guard=True); C/SWITCH native = 2023-01-01..2026-01-01 on the same continuous ledger.",
        "R2-44 fold predictions miss 2025-12-31 (and 2023-12-31); those decisions have M=NaN -> C1.",
    ]
    report["created_utc"] = datetime.now(timezone.utc).isoformat()
    report["runtime_seconds"] = round(time.time() - started, 1)
    report["code_sha256"] = provenance.file_sha256(Path(__file__).resolve())
    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                                     encoding="utf-8")
    write_md(report)
    registry.record(REGISTRY, {
        "experiment": "R2-56 continuous-ledger replay of 6 existing candidates 2026-01-01..2026-10-07",
        "n_trials": 6,
        "config": {"candidates": list(report["candidates"]), "window": report["window"], "costs": report["costs"],
                   "switch": "M>=2/3 -> C4 (F3-w30/V0+E1/V1a) else C1 (F3/V5+E1/V1a)", "no_model_fits": True},
        "input_hashes": {"snapshot_manifest": report["snapshot_manifest_sha256"],
                         "stage_a_2026": provenance.file_sha256(STAGE_A), "code": report["code_sha256"]},
        "result_summary": {k: {"net_4bps": v["net_4bps"], "net_8bps": v["net_8bps"], "trades": v["trades"]}
                           for k, v in report["candidates"].items()}})
    (OUT / "run.log").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    log("done")


def write_md(r: dict) -> None:
    months = [f"2026-{m:02d}" for m in range(1, 11)]
    head = ["candidate", "net4", "net8", "trades", "win", "long4", "short4", "L/S n", "MDD", "worst"]
    lines = ["# R2-56 continuous-ledger replay", "", f"window {r['window'][0]} .. {r['window'][1]} (exclusive); "
             f"{r['costs']}", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    f = lambda v: "NA" if v is None else f"{v:.1f}"
    for name, s in r["candidates"].items():
        lines.append(f"| {name} | {f(s['net_4bps'])} | {f(s['net_8bps'])} | {s['trades']} | "
                     f"{s['win_rate']:.3f} | {f(s['long_net_4bps'])} | {f(s['short_net_4bps'])} | "
                     f"{s['long_trades']}/{s['short_trades']} | {f(s['max_drawdown_bps'])} | {f(s['worst_position_bps'])} |")
    lines += ["", "## monthly net 4 bps", "", "| candidate | " + " | ".join(months) + " |", "|" + "---|" * 11]
    for name, s in r["candidates"].items():
        lines.append(f"| {name} | " + " | ".join(f(s["monthly_net_4bps"].get(m, 0.0)) for m in months) + " |")
    lines += ["", "## components (4 bps)", ""]
    for name, s in r["candidates"].items():
        if s.get("components"):
            lines.append(f"- {name}: " + ", ".join(f"{c} {f(v['net_4bps'])} ({v['trades']})"
                                                   for c, v in s["components"].items()))
    lines += ["", "## native reference", "", "| candidate | window | net4 | net8 | trades | MDD | worst |",
              "|---|---|---|---|---|---|---|"]
    for name, s in r["native"].items():
        lines.append(f"| {name} | {s['window'][0][:10]}..{s['window'][1][:10]} | {f(s['net_4bps'])} | "
                     f"{f(s['net_8bps'])} | {s['trades']} | {f(s['max_drawdown_bps'])} | {f(s['worst_position_bps'])} |")
    lines += ["", "## parity", "", "```", json.dumps(r["parity"], indent=1), "```", "", "## overlap 2026", "",
              "```", json.dumps(r["overlap_2026"], indent=1), "```", "", "## switch", "", "```",
              json.dumps({"routing": r["candidates"]["SWITCH_C1C4"]["routing"],
                          "mapping_2023_2025": r["switch_mapping_2023_2025_by_state"],
                          "M_coverage": r["regime_M_coverage"]}, indent=1), "```", "", "## causality", ""]
    lines += [f"- {k}: {v}" for k, v in r["causality"].items()]
    lines += ["", "## deviations", ""] + [f"- {d}" for d in r["deviations"]]
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
