"""R2-54 Task 3: archive-vs-REST parity, offline-vs-live prediction parity and the immutable Stage-B snapshot.

Freeze: out/k45_rl_r2_48_20261007/r2_54_stageb_freeze.json (data_plan.parity with amendment A1, data_plan.snapshot,
gates.data, manifest). Public GET only, no API key; the live DB is opened read-only and its cursors are never touched.

Parity rule (A1, verbatim): exact normalized timestamps and missing masks. OI and OI value require exact equality.
For global/top ratios, using Decimal ROUND_HALF_UP, derive archive-implied long=Q4(r/(1+r)), short=Q4(1/(1+r)),
ratio=Q4(long/short) and require exact equality with the three REST fields. For taker, require REST
buySellRatio=Q4(buyVol/sellVol) and require archive and REST ratios to match after Q3 quantization; report raw
residuals. Any remaining mismatch fails parity.

Usage:
  python out/run_r2_54_parity_snapshot.py fetch-rest            # public REST window -> staging DB (not live DB)
  python out/run_r2_54_parity_snapshot.py parity                # archive (live DB, ro) vs staging REST
  python out/run_r2_54_parity_snapshot.py prediction-parity     # offline vs live path on the frozen inputs
  python out/run_r2_54_parity_snapshot.py snapshot              # write-once, read-only; refuses unless both pass
"""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, os, sqlite3, stat, subprocess, sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.paper import detector, futures_metrics as fm  # noqa: E402
from btcusdt_quant.paper.collector import PublicBinanceClient  # noqa: E402
from btcusdt_quant.paper.store import PaperStore  # noqa: E402

_SPEC = importlib.util.spec_from_file_location("r2_54_stage_a", ROOT / "out/run_r2_54_stage_a_2026.py")
gen = sys.modules.get(_SPEC.name)
if gen is None:
    gen = importlib.util.module_from_spec(_SPEC); sys.modules[_SPEC.name] = gen; _SPEC.loader.exec_module(gen)

BASE = ROOT / "out/k45_rl_r2_48_20261007/r2_54"
FREEZE = gen.FREEZE
DB = gen.DB
PARITY_DIR = BASE / "parity"
STAGING = PARITY_DIR / "rest_staging.sqlite"
PARITY_REPORT = PARITY_DIR / "parity_report.json"
PREDICTION_REPORT = PARITY_DIR / "prediction_parity.json"
SNAPSHOT_DIR = BASE / "stageb_snapshot"
STAGE_A = BASE / "stage_a_2026/stage_a_2026.parquet"
STAGE_A_SHA = "974feb8f"                                     # prefix recorded in Task 2 (progress.md)
PARITY_START = pd.Timestamp("2026-10-01", tz="UTC")
PARITY_END = pd.Timestamp("2026-10-08", tz="UTC")            # exclusive
SNAP_START = pd.Timestamp("2026-01-01", tz="UTC")
SNAP_END = gen.DATA_END                                      # 2026-10-08 exclusive
PERIOD = fm.PERIOD
RTOL = 1e-6
ENDPOINT = {spec[0]: endpoint for endpoint, spec in fm.REST_SPECS.items()}
SHIFT = {spec[0]: spec[1] for spec in fm.REST_SPECS.values()}   # REST timestamp - create_time
CODE = [Path(__file__).resolve(), ROOT / "out/run_r2_54_stage_a_2026.py", ROOT / "btcusdt_quant/paper/futures_metrics.py",
        ROOT / "btcusdt_quant/paper/detector.py", ROOT / "btcusdt_quant/paper/collector.py"]


# ---------- A1 parity rule ----------

def dec(value) -> Decimal | None:
    """Decimal of a stored REAL via its shortest round-trip repr (= the published decimal string)."""
    if value is None or isinstance(value, Decimal):
        return value
    value = float(value)
    return Decimal(repr(value)) if np.isfinite(value) else None


def _q(value, places: int) -> Decimal:
    return dec(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def q3(value) -> Decimal:
    return _q(value, 3)


def q4(value) -> Decimal:
    return _q(value, 4)


# (archive mask columns, REST mask columns) per table
MASKS = {"futures_global_ls_5m": (["long_short_ratio"], ["long_account", "short_account", "long_short_ratio"]),
         "futures_top_ls_5m": (["long_short_ratio"], ["long_account", "short_account", "long_short_ratio"]),
         "futures_oi_5m": (["sum_open_interest", "sum_open_interest_value"],
                           ["sum_open_interest", "sum_open_interest_value"]),
         "futures_taker_lsr_5m": (["buy_sell_ratio"], ["buy_sell_ratio", "buy_volume", "sell_volume"])}


def _window(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frame = frame.copy()
    frame["t"] = pd.to_datetime(frame.create_time, utc=True, format="mixed")
    return frame.loc[(frame.t >= start) & (frame.t < end)].set_index("t").sort_index()


def _field(rows: list[tuple[pd.Timestamp, object, object, object, float]]) -> dict:
    """rows = (create_time, archive value, REST value, expected value, raw residual); mismatch = expected != REST."""
    bad = [r for r in rows if r[3] != r[2]]
    residuals = [abs(r[4]) for r in rows if r[4] is not None and np.isfinite(r[4])]
    return {"compared": len(rows), "mismatch": len(bad),
            "max_abs_raw_residual": float(max(residuals)) if residuals else None,
            "mean_abs_raw_residual": float(np.mean(residuals)) if residuals else None,
            "examples": [{"create_time": t.isoformat(), "archive": str(a), "rest": str(r), "expected": str(e)}
                         for t, a, r, e, _ in bad[:5]]}


def _fields(table: str, a: pd.DataFrame, r: pd.DataFrame) -> dict[str, dict]:
    times = list(a.index)
    if table in ("futures_global_ls_5m", "futures_top_ls_5m"):
        out = {"long_account": [], "short_account": [], "long_short_ratio": []}
        for t in times:
            ratio = dec(a.at[t, "long_short_ratio"])
            long, short = q4(ratio / (1 + ratio)), q4(1 / (1 + ratio))
            derived = {"long_account": long, "short_account": short, "long_short_ratio": q4(long / short)}
            raw = {"long_account": float(ratio / (1 + ratio)), "short_account": float(1 / (1 + ratio)),
                   "long_short_ratio": float(ratio)}
            for name in out:
                rest = dec(r.at[t, name])
                out[name].append((t, ratio, rest, derived[name], raw[name] - float(rest)))
        return {k: _field(v) for k, v in out.items()}
    if table == "futures_oi_5m":
        return {name: _field([(t, dec(a.at[t, name]), dec(r.at[t, name]), dec(a.at[t, name]),
                               float(a.at[t, name]) - float(r.at[t, name])) for t in times])
                for name in ("sum_open_interest", "sum_open_interest_value")}
    internal, cross = [], []
    for t in times:
        buy, sell, rest = dec(r.at[t, "buy_volume"]), dec(r.at[t, "sell_volume"]), dec(r.at[t, "buy_sell_ratio"])
        internal.append((t, None, rest, q4(buy / sell) if sell else None, float(buy) / float(sell) - float(rest)
                         if sell else None))
        archive = dec(a.at[t, "buy_sell_ratio"])
        cross.append((t, archive, q3(rest), q3(archive), float(archive) - float(rest)))
    result = {"rest_internal_q4": _field(internal), "archive_vs_rest_q3": _field(cross)}
    bad = [abs(c[4]) for c in cross if c[3] != c[2]]
    rel = [abs(c[4]) / abs(float(c[1])) for c in cross if c[1]]
    result["archive_vs_rest_q3"]["diagnostic"] = {      # mandatory report-only diagnostic (amendment A3)
        "mismatch_within_rest_q4_half_tick": sum(b <= 5e-05 + 1e-12 for b in bad),
        "mismatch_beyond_rest_q4_half_tick": sum(b > 5e-05 + 1e-12 for b in bad),
        "rows_beyond_rest_q4_half_tick": sum(abs(c[4]) > 5e-05 + 1e-12 for c in cross),
        "max_rel_raw_residual": float(max(rel)) if rel else None,
        "median_abs_raw_residual": float(np.median([abs(c[4]) for c in cross])) if cross else None}
    return result


REPORT_ONLY = {"archive_vs_rest_q3"}    # amendment A3 (supersedes only A1's taker cross-source Q3 block)


def final_taker(frame: pd.DataFrame) -> pd.DataFrame:
    """A3 source rule for Stage-B training/validation/final-test replay: archive taker only. The frozen snapshot
    window holds no causally received REST taker rows; any REST row there refuses (never blended or filled)."""
    rest = int(frame.source.ne("archive").sum())
    if rest:
        raise RuntimeError(f"{rest} REST taker rows in the final-test window; A3 uses archive taker there")
    return frame.loc[frame.source.eq("archive")].reset_index(drop=True)


def registry(doc: dict) -> dict:
    """Registry counts from amendment A2 (found by id); the trials body values are superseded, not edited."""
    a2 = next(a for a in doc["amendments"] if a["id"] == "A2")
    return {**{k: a2["new"][k] for k in ("registry_base", "registry_after")}, "source": "amendment A2",
            "superseded_body": {k: doc["trials"][k] for k in ("registry_base", "registry_after")}}


def check_table(table: str, archive: pd.DataFrame, rest: pd.DataFrame, start: pd.Timestamp,
                end: pd.Timestamp) -> dict:
    grid = pd.date_range(start, end, freq="5min", inclusive="left")
    a, r = _window(archive, start, end), _window(rest, start, end)
    coverage = {"expected": len(grid), "archive_rows": len(a), "rest_rows": len(r),
                "missing_archive": [t.isoformat() for t in grid.difference(a.index)],
                "missing_rest": [t.isoformat() for t in grid.difference(r.index)],
                "off_grid": int((~a.index.isin(grid)).sum() + (~r.index.isin(grid)).sum()),
                "duplicates": int(a.index.duplicated().sum() + r.index.duplicated().sum())}
    both = grid.intersection(a.index).intersection(r.index)
    a, r = a.loc[both], r.loc[both]
    stamp = lambda s: pd.DatetimeIndex(pd.to_datetime(s, utc=True, format="mixed"))   # noqa: E731
    timestamps = {
        "archive_source_timestamp_mismatch": int((stamp(a.source_timestamp) != a.index).sum()),
        "archive_logical_available_mismatch": int((stamp(a.logical_available_at) != a.index + PERIOD).sum()),
        "rest_source_timestamp_mismatch": int((stamp(r.source_timestamp) != r.index + SHIFT[table]).sum()),
        "rest_available_before_period_end": int((stamp(r.logical_available_at) < r.index + PERIOD).sum())}
    a_cols, r_cols = MASKS[table]
    if table == "futures_oi_5m":           # same field on both sides: per-field mask
        a_missing = a[a_cols].isna().to_numpy()
        r_missing = r[r_cols].isna().to_numpy()
        mask_bad = (a_missing != r_missing).any(axis=1)
        present = ~(a_missing | r_missing).any(axis=1)
    else:
        a_missing, r_missing = a[a_cols].isna().any(axis=1).to_numpy(), r[r_cols].isna().any(axis=1).to_numpy()
        mask_bad, present = a_missing != r_missing, ~(a_missing | r_missing)
    a_any, r_any = a[a_cols].isna().any(axis=1).to_numpy(), r[r_cols].isna().any(axis=1).to_numpy()
    masks = {"mismatch": int(mask_bad.sum()), "both_missing": int((a_any & r_any).sum()),
             "examples": [t.isoformat() for t in both[mask_bad][:5]]}
    fields = _fields(table, a.loc[present], r.loc[present])
    for name, value in fields.items():     # A3: taker archive-vs-REST Q3 is report-only; every other field blocks
        value["blocking"] = name not in REPORT_ONLY
    passed = (not coverage["missing_archive"] and not coverage["missing_rest"] and not coverage["off_grid"]
              and not coverage["duplicates"] and not any(timestamps.values()) and not masks["mismatch"]
              and all(v["mismatch"] == 0 for v in fields.values() if v["blocking"]))
    return {"table": table, "window": [str(start), str(end)], "coverage": coverage, "timestamps": timestamps,
            "masks": masks, "fields": fields, "passed": bool(passed)}


# ---------- REST fetch into a staging DB ----------

def fetch_rest(staging: Path = STAGING, start: pd.Timestamp = PARITY_START, end: pd.Timestamp = PARITY_END,
               client: PublicBinanceClient | None = None) -> dict:
    """Public GET (no key) of the four /futures/data endpoints over [start - 10 m, end + 10 m]; every HTTP attempt
    is persisted raw in the staging futures_raw_audit before parsing. Rows go through fm.normalize_rest and
    put_versioned (a differing re-fetch is a recorded revision, never an overwrite). Live cursors are not used."""
    client = client or PublicBinanceClient()
    store = PaperStore(staging)
    summary = {}
    try:
        for table, endpoint in ENDPOINT.items():
            counts = {"inserted": 0, "same": 0, "revised": 0, "pages": 0, "statuses": []}
            page_start = start - 2 * PERIOD
            while page_start <= end + 2 * PERIOD:
                page_end = min(page_start + 400 * PERIOD, end + 2 * PERIOD)
                params = {"symbol": "BTCUSDT", "period": "5m", "startTime": int(page_start.value // 10**6),
                          "endTime": int(page_end.value // 10**6), "limit": 500}
                responses = []

                def record(status, text, request_utc, params=params):
                    response_utc = pd.Timestamp.now(tz="UTC")
                    store.connection.execute(
                        "INSERT INTO futures_raw_audit(endpoint,params,request_utc,response_utc,status,sha256,payload) "
                        "VALUES(?,?,?,?,?,?,?)", (endpoint, json.dumps(params, sort_keys=True), request_utc.isoformat(),
                                                  response_utc.isoformat(), status,
                                                  hashlib.sha256(text.encode()).hexdigest(), text))
                    store.connection.commit()
                    responses.append(response_utc)

                status, text = client.get_raw(endpoint, params, on_attempt=record)
                counts["statuses"].append(status)
                if status != 200:
                    raise RuntimeError(f"{endpoint} HTTP {status}; parity fails closed")
                _, rows = fm.normalize_rest(endpoint, json.loads(text), responses[-1])
                for key, value in fm.write_rows(store, table, rows).items():
                    counts[key] += value
                counts["pages"] += 1
                page_start = page_end + pd.Timedelta(milliseconds=1)
            counts["statuses"] = sorted(set(counts["statuses"]))
            summary[table] = counts
        store.set_meta("r2_54_parity_fetch", json.dumps({"window": [str(start), str(end)], "tables": summary,
                                                         "fetched_at": pd.Timestamp.now(tz="UTC").isoformat()}))
    finally:
        store.close()
    return summary


# ---------- parity report ----------

def _ro(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)


def _read_table(db: Path, table: str, source: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    with _ro(db) as c:
        return pd.read_sql_query(f"SELECT * FROM {table} WHERE source=? AND create_time>=? AND create_time<?", c,
                                 params=(source, (start - PERIOD).isoformat(), (end + PERIOD).isoformat()))


def archive_files(start: pd.Timestamp = PARITY_START, end: pd.Timestamp = PARITY_END) -> dict:
    """Daily metrics zips needed for [start, end): the day before start (its last row is start 00:00) .. end - 1 d."""
    r = detector.r44().r
    days = pd.date_range(start - pd.Timedelta(days=1), end - pd.Timedelta(days=1), freq="D")
    dirs = [ROOT / "artifacts/metrics", gen.Q3_METRICS, gen.Q4_METRICS]
    out = {}
    for day in days:
        name = f"BTCUSDT-metrics-{day:%Y-%m-%d}.zip"
        path = next((d / name for d in dirs if (d / name).exists()), None)
        out[name] = r.file_record(path) if path else {"missing": True}
    next_day = f"BTCUSDT-metrics-{end:%Y-%m-%d}.zip"
    return {"required": out, "all_present": all("missing" not in v for v in out.values()),
            f"{next_day}_present": any((d / next_day).exists() for d in dirs),
            "note": f"{next_day} is not required: the window ends {end} exclusive and the {end - pd.Timedelta(days=1):%Y-%m-%d} "
                    "file covers 00:05 .. next-day 00:00"}


def parity(staging: Path = STAGING, live_db: Path = DB, start: pd.Timestamp = PARITY_START,
           end: pd.Timestamp = PARITY_END) -> dict:
    r = detector.r44().r
    tables = {t: check_table(t, _read_table(live_db, t, "archive", start, end),
                             _read_table(staging, t, "rest", start, end), start, end) for t in fm.TABLES}
    with _ro(staging) as c:
        audit = c.execute("SELECT COUNT(*), MIN(request_utc), MAX(response_utc), SUM(status!=200) "
                          "FROM futures_raw_audit").fetchone()
        fetch = json.loads((c.execute("SELECT value FROM meta WHERE key='r2_54_parity_fetch'").fetchone() or ["{}"])[0])
        revisions = c.execute("SELECT COUNT(*) FROM futures_revisions").fetchone()[0]
    with _ro(live_db) as c:
        backfill = json.loads(c.execute("SELECT value FROM meta WHERE key='futures_metrics_backfill'").fetchone()[0])
    fields = {}
    for name, table, keys in (("global_ls", "futures_global_ls_5m", None), ("top_ls", "futures_top_ls_5m", None),
                              ("oi", "futures_oi_5m", ["sum_open_interest"]),
                              ("oi_value", "futures_oi_5m", ["sum_open_interest_value"]),
                              ("taker_lsr", "futures_taker_lsr_5m", None)):
        part = tables[table]
        chosen = {k: v for k, v in part["fields"].items() if keys is None or k in keys}
        common_ok = (not part["coverage"]["missing_archive"] and not part["coverage"]["missing_rest"]
                     and not part["coverage"]["off_grid"] and not part["coverage"]["duplicates"]
                     and not any(part["timestamps"].values()) and not part["masks"]["mismatch"])
        fields[name] = {"passed": bool(common_ok and all(v["mismatch"] == 0 for v in chosen.values() if v["blocking"])),
                        "blocking": {k: v["blocking"] for k, v in chosen.items()},
                        "mismatch": {k: v["mismatch"] for k, v in chosen.items()},
                        "compared": {k: v["compared"] for k, v in chosen.items()},
                        "max_abs_raw_residual": {k: v["max_abs_raw_residual"] for k, v in chosen.items()},
                        "missing_archive": len(part["coverage"]["missing_archive"]),
                        "missing_rest": len(part["coverage"]["missing_rest"]),
                        "mask_mismatch": part["masks"]["mismatch"],
                        "timestamp_mismatch": int(sum(part["timestamps"].values()))}
    files = archive_files(start, end)
    report = {
        "kind": "R2-54 archive vs public REST parity", "freeze": r.file_record(FREEZE),
        "rule": "data_plan.parity.metric_tolerance (amendment A1; taker per amendment A3: archive-vs-REST Q3 report-only)", "window": [str(start), str(end)],
        "sources": {"archive": f"live DB {live_db} (read-only) source='archive' rows (data.binance.vision metrics zips, "
                               "normalized by futures_metrics.backfill_metrics)",
                    "rest": {"db": str(staging.relative_to(ROOT)), "base_url": "https://fapi.binance.com",
                             "endpoints": list(ENDPOINT.values()), "auth": "none (public GET)",
                             "raw_audit_rows": audit[0], "first_request_utc": audit[1], "last_response_utc": audit[2],
                             "non_200": audit[3], "staging_revisions": revisions, "fetch": fetch}},
        "archive_coverage": {"zips": files, "live_backfill_missing_days": backfill.get("missing_days"),
                             "live_backfill_range": backfill.get("range"),
                             "live_backfill_received_at": backfill.get("received_at")},
        "fields": fields, "tables": tables,
        "passed": bool(files["all_present"] and all(v["passed"] for v in tables.values())),
        "written_at": r.utc_now()}
    r.write_json(PARITY_REPORT, report)
    return {k: report[k] for k in ("window", "fields", "passed")}


# ---------- prediction parity (offline vs live path, identical frozen inputs) ----------

MASK_COLUMNS = {1: (13, 16), 2: (12, 16)}     # 5m: ls_missing, premium_missing; 1h: premium_missing, funding_missing


def live_connection(frames: tuple[pd.DataFrame, ...], now: pd.Timestamp, days: int = 22) -> sqlite3.Connection:
    """In-memory paper store with the frozen snapshot rows known at `now` (the live tables' formats)."""
    market, metrics, premium, funding = frames
    lo = now - pd.Timedelta(days=days)
    c = sqlite3.connect(":memory:")
    m = market.loc[(market.open_time >= lo) & (market.open_time < now)].copy()
    m["open_time"] = m.open_time.map(lambda t: t.isoformat())
    m.to_sql("klines_1m", c, index=False)
    ls = metrics.loc[(metrics.create_time >= lo) & (metrics.create_time + PERIOD <= now)]
    pd.DataFrame({"timestamp": ls.create_time.map(lambda t: t.isoformat()), "global_ls_account": ls.global_ls,
                  "source": "archive"}).to_sql("ls_ratio", c, index=False)
    p = premium.loc[(premium.open_time >= lo) & (premium.open_time < now)]
    pd.DataFrame({"open_time": p.open_time.map(lambda t: t.isoformat()), "premium_index": p.premium}).to_sql(
        "premium_1m", c, index=False)
    f = funding.loc[funding.publish_time < now]
    stamps = f.publish_time.map(lambda t: t.isoformat())
    pd.DataFrame({"rate": f.rate, "raw_calc_time": stamps}).to_sql("funding", c, index=False)
    pd.DataFrame({"funding_time": stamps, "interval_hours": f.interval_hours.where(f.interval_missing.eq(0))}).to_sql(
        "funding_events", c, index=False)
    return c


def _windows(data, origins: pd.DatetimeIndex) -> list[np.ndarray]:
    r, config = detector.r44().r, detector.r44().CONFIG
    endpoints = r.endpoint_indices(data.bars, origins)
    out = []
    for values, end, lookback in zip(data.arrays, endpoints, config.lookbacks):
        indices = end[:, None] + np.arange(-lookback + 1, 1)
        if (indices < 0).any():
            raise ValueError("live window shorter than the lookback")
        out.append(values[indices])
    return out


def _compare(a: np.ndarray, b: np.ndarray) -> dict:
    nan_a, nan_b = ~np.isfinite(a), ~np.isfinite(b)
    both = ~(nan_a | nan_b)
    diff = np.abs(a[both].astype(float) - b[both].astype(float))
    scale = np.abs(b[both].astype(float))
    ok = diff <= RTOL * scale
    return {"nonfinite_mismatch": int((nan_a != nan_b).sum()), "values": int(both.sum()),
            "rtol_fail": int((~ok).sum()), "max_abs": float(diff.max()) if diff.size else 0.0,
            "max_rel": float((diff / np.where(scale > 0, scale, np.inf)).max()) if diff.size else 0.0}


def prediction_parity(days: list[pd.Timestamp], device_name: str = "cuda:0",
                      snapshot: Path = gen.SNAPSHOT) -> dict:
    import torch
    r = detector.r44().r
    device = torch.device(device_name)
    frames, prov = gen.load_snapshot(snapshot)
    offline = detector.build_data(*frames, with_targets=False)
    stage = gen._read(STAGE_A).set_index("prediction_ts")
    names = [f"prediction_{t}" for t in detector.target_names()]
    retrains = [t for t, _ in gen.schedule()]
    results, passed = {}, True
    for day in days:
        now = min(day + pd.Timedelta(days=1), SNAP_END)
        with live_connection(frames, now) as connection:
            live = detector.recent_data(connection, now)
        grid = stage.index[(stage.index >= day) & (stage.index < now)]
        lo = pd.DatetimeIndex(live.origins)
        off = pd.DatetimeIndex(offline.origins)
        live_o, off_o = lo[(lo >= day) & (lo < now)], off[(off >= day) & (off < now)]
        same_origins = live_o.equals(off_o) and off_o.equals(pd.DatetimeIndex(grid))
        retrain = max(t for t in retrains if t <= day)
        checkpoint = torch.load(gen.fold_paths(gen.OUT, retrain)[0], weights_only=False, map_location="cpu")
        features = {}
        for k, (wl, wo) in enumerate(zip(_windows(live, off_o), _windows(offline, off_o))):
            cmp = _compare(wl, wo)
            cols = MASK_COLUMNS.get(k, ())
            cmp["mask_mismatch"] = int(sum((wl[..., c] != wo[..., c]).sum() for c in cols))
            features[("1m", "5m", "1h")[k]] = cmp
        p_live = detector.predict(live, checkpoint, off_o, device)
        p_off = detector.predict(offline, checkpoint, off_o, device)
        stored = stage.loc[off_o, names].to_numpy(float)
        live_vs_off = _compare(p_live.astype(float), p_off.astype(float))
        # Stage-A predicted each fold in one call (GPU batch composition matters at float32 ulp level): re-predict
        # the whole fold the same way and compare the day's rows; the day-subset diff is kept as a diagnostic.
        fold_end = min(retrain + gen.CADENCE, SNAP_END)
        fold_o = off[(off >= retrain) & (off < fold_end)]
        p_fold = pd.DataFrame(detector.predict(offline, checkpoint, fold_o, device), index=fold_o).loc[off_o]
        off_vs_stage = _compare(p_fold.to_numpy(float), stored)
        off_vs_stage["day_subset_batch_diagnostic"] = _compare(p_off.astype(float), stored)
        ok = (same_origins and all(v["nonfinite_mismatch"] == 0 and v["rtol_fail"] == 0 and v["mask_mismatch"] == 0
                                   for v in features.values())
              and live_vs_off["rtol_fail"] == 0 and live_vs_off["nonfinite_mismatch"] == 0
              and off_vs_stage["rtol_fail"] == 0 and off_vs_stage["nonfinite_mismatch"] == 0)
        passed &= ok
        results[str(day.date())] = {"now": str(now), "retrain_time": str(retrain), "origins": len(off_o),
                                    "same_origins": bool(same_origins), "features": features,
                                    "live_vs_offline": live_vs_off, "offline_vs_stage_a": off_vs_stage,
                                    "passed": bool(ok)}
        print(json.dumps({"day": str(day.date()), "passed": bool(ok), "pred_max_rel": live_vs_off["max_rel"]}),
              flush=True)
    report = {"kind": "R2-54 offline vs live feature/prediction parity", "freeze": r.file_record(FREEZE),
              "rule": "data_plan.parity.prediction_check: exact timestamps and masks, numeric rtol=1e-6, atol=0",
              "offline_path": "detector.build_data(snapshot frames) (= Stage-A generator inputs) + detector.predict",
              "live_path": "in-memory paper tables from the same snapshot rows known at now -> detector.recent_data "
                           "(paper_catalog.update_predictions path) + detector.predict",
              "device": device_name, "snapshot": r.file_record(snapshot / "manifest.json"),
              "stage_a": r.file_record(STAGE_A), "inputs": prov, "days": results, "passed": bool(passed),
              "written_at": r.utc_now()}
    r.write_json(PREDICTION_REPORT, report)
    return {"passed": report["passed"], "days": {k: v["passed"] for k, v in results.items()}}


# ---------- immutable snapshot ----------

def _read_only(path: Path) -> None:
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_artifact(path: Path, frame: pd.DataFrame, time_column: str, source: str) -> dict:
    """Write-once parquet, read back and frame-hash checked, then set read-only. Returns the manifest record."""
    path = Path(path)
    if path.exists():
        raise RuntimeError(f"{path} exists; the snapshot is write-once")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = frame.reset_index(drop=True)
    temporary = path.with_name(path.stem + ".tmp.parquet")
    frame.to_parquet(temporary, index=False)
    back = gen._read(temporary)
    if gen.frame_sha256(back) != gen.frame_sha256(frame):
        temporary.unlink()
        raise RuntimeError(f"{path.name} parquet round trip is not exact")
    temporary.replace(path)
    _read_only(path)
    times = pd.to_datetime(frame[time_column], utc=True, format="mixed") if len(frame) else pd.Series(dtype=object)
    return {"path": _rel(path), "sha256": _sha(path), "bytes": path.stat().st_size, "rows": len(frame),
            "frame_sha256": gen.frame_sha256(frame), "schema": {c: str(t) for c, t in frame.dtypes.items()},
            "time_column": time_column, "min_time": str(times.min()) if len(frame) else None,
            "max_time": str(times.max()) if len(frame) else None, "source": source}


def copy_artifact(source: Path, path: Path, time_column: str, note: str) -> dict:
    """Write-once byte copy (same SHA-256 as the source), set read-only."""
    import shutil
    path = Path(path)
    if path.exists():
        raise RuntimeError(f"{path} exists; the snapshot is write-once")
    shutil.copyfile(source, path)
    if _sha(path) != _sha(source):
        raise RuntimeError(f"{path.name} copy hash differs")
    _read_only(path)
    frame = gen._read(path)
    times = pd.to_datetime(frame[time_column], utc=True)
    return {"path": _rel(path), "sha256": _sha(path), "bytes": path.stat().st_size, "rows": len(frame),
            "frame_sha256": gen.frame_sha256(frame), "schema": {c: str(t) for c, t in frame.dtypes.items()},
            "time_column": time_column, "min_time": str(times.min()), "max_time": str(times.max()),
            "source": note, "copied_from": {"path": _rel(source), "sha256": _sha(source)}}


def _json_artifact(path: Path, value: object, source: str) -> dict:
    if path.exists():
        raise RuntimeError(f"{path} exists; the snapshot is write-once")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _read_only(path)
    return {"path": _rel(path), "sha256": _sha(path), "bytes": path.stat().st_size, "rows": None, "schema": "json",
            "min_time": None, "max_time": None, "source": source}


def _db_table(db: Path, sql: str, params: tuple = ()) -> pd.DataFrame:
    with _ro(db) as c:
        return pd.read_sql_query(sql, c, params=params)


def file_period_start(name: str) -> pd.Timestamp:
    """Start of the period an archive zip covers: ...-YYYY-MM-DD.zip (daily) or ...-YYYY-MM.zip (monthly)."""
    import re
    match = re.search(r"(\d{4}-\d{2})(-\d{2})?\.zip$", name)
    if match is None:
        raise ValueError(f"no period in {name}")
    return pd.Timestamp(match.group(1) + (match.group(2) or "-01"), tz="UTC")


def _subset_tree(root: Path, pattern: str, before: pd.Timestamp | None = None) -> dict:
    files = sorted(Path(root).glob(pattern))
    if before is not None:
        files = [f for f in files if file_period_start(f.name) < before]
    digest, total = hashlib.sha256(), 0
    for f in files:
        digest.update(f.name.encode()); digest.update(_sha(f).encode()); total += f.stat().st_size
    return {"path": _rel(root), "pattern": pattern, "before": None if before is None else str(before),
            "files": len(files), "bytes": total, "tree_sha256": digest.hexdigest(),
            "first": files[0].name if files else None, "last": files[-1].name if files else None}


def _git() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    diff = subprocess.run(["git", "diff", "HEAD"], cwd=ROOT, capture_output=True).stdout
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    return {"commit": head, "dirty_diff_sha256": hashlib.sha256(diff).hexdigest(), "dirty_diff_bytes": len(diff),
            "untracked_or_modified": len(status.splitlines())}


def grid_coverage(times: pd.Series, start: pd.Timestamp, end: pd.Timestamp, freq: str) -> dict:
    grid = pd.date_range(start, end, freq=freq, inclusive="left")
    index = pd.DatetimeIndex(pd.to_datetime(times, utc=True, format="mixed"))
    missing = grid.difference(index)
    return {"expected": len(grid), "present": int(grid.isin(index).sum()), "missing": len(missing),
            "missing_times": [t.isoformat() for t in missing[:200]], "duplicates": int(index.duplicated().sum()),
            "off_grid": int((~index.isin(grid)).sum())}


CANDIDATE_DIR = BASE / "stageb_snapshot_candidate_parity_failed"


def snapshot_status(parity_passed: bool, prediction_passed: bool, out: Path, allow_failed_parity: bool) -> str:
    """FINAL only after both parity checks pass (frozen order). A failed parity may only write a NOT_FINAL
    candidate (hashes for review) outside the final snapshot path; it never unlocks the final test."""
    if parity_passed and prediction_passed:
        return "FINAL"
    if not allow_failed_parity:
        raise RuntimeError("parity not passed: the frozen plan creates the snapshot only after parity passes")
    if Path(out).resolve() == SNAPSHOT_DIR.resolve():
        raise RuntimeError("a failed-parity candidate may not use the final snapshot path")
    return "NOT_FINAL_PARITY_FAILED"


def build_snapshot(out: Path = SNAPSHOT_DIR, live_db: Path = DB, allow_failed_parity: bool = False) -> dict:
    r = detector.r44().r
    parity_report = json.loads(PARITY_REPORT.read_text(encoding="utf-8"))
    prediction_report = json.loads(PREDICTION_REPORT.read_text(encoding="utf-8"))
    status = snapshot_status(parity_report["passed"], prediction_report["passed"], out, allow_failed_parity)
    if out.exists():
        raise RuntimeError(f"{out} exists; the snapshot is write-once, use a new path")
    if not _sha(STAGE_A).startswith(STAGE_A_SHA):
        raise RuntimeError("stage_a_2026.parquet hash differs from the Task 2 record")
    out.mkdir(parents=True)
    lo, hi = SNAP_START.isoformat(), SNAP_END.isoformat()
    frames, prov = gen.load_snapshot(gen.SNAPSHOT)
    market, metrics, premium, funding = frames
    inside = lambda f, c: f.loc[(f[c] >= SNAP_START) & (f[c] < SNAP_END)].reset_index(drop=True)  # noqa: E731
    src = gen.SOURCES
    art = {}
    art["market_1m"] = write_artifact(out / "market_1m.parquet", inside(market, "open_time"), "open_time",
                                      src["market"] + "; via stage_a_2026_inputs/market.parquet (hash-verified)")
    art["premium_1m"] = write_artifact(out / "premium_1m.parquet", inside(premium, "open_time"), "open_time",
                                       src["premium"] + "; via stage_a_2026_inputs/premium.parquet (hash-verified)")
    tables = {}
    for table in fm.TABLES:
        frame = _db_table(live_db, f"SELECT * FROM {table} WHERE create_time>=? AND create_time<? "
                                   "ORDER BY create_time, source", (lo, hi))
        note = "all sources"
        if table == "futures_taker_lsr_5m":       # A3: final-test replay uses archive taker; REST rows here refuse
            frame, note = final_taker(frame), "source=archive only (amendment A3; REST rows in window asserted 0)"
        tables[table] = frame
        art[table] = write_artifact(out / f"{table}.parquet", frame, "create_time",
                                    f"live DB {table} (read-only), {note}; archive = data.binance.vision metrics "
                                    "zips normalized by futures_metrics.backfill_metrics")
    events = _db_table(live_db, "SELECT * FROM funding_events WHERE funding_time>=? AND funding_time<? "
                                "ORDER BY funding_time, source", (lo, hi))
    art["funding_events"] = write_artifact(out / "funding_events.parquet", events, "funding_time",
                                           "live DB funding_events (read-only): actual fundingTime, interval_hours "
                                           "(archive funding_interval_hours), interval_missing")
    legacy = _db_table(live_db, "SELECT * FROM funding WHERE raw_calc_time>=? AND raw_calc_time<? ORDER BY time",
                       (lo, hi))
    art["funding_live_table"] = write_artifact(out / "funding_live_table.parquet", legacy, "raw_calc_time",
                                               "live DB funding (read-only): October REST events absent from "
                                               "funding_events; interval unknown")
    model_funding = inside(funding, "publish_time")
    art["funding_model_input"] = write_artifact(
        out / "funding_model_input.parquet", model_funding, "publish_time",
        src["funding"] + "; via stage_a_2026_inputs/funding.parquet; interval_missing=1 -> masked, never 8 h")
    stage = gen._read(STAGE_A)
    art["stage_a_2026"] = copy_artifact(STAGE_A, out / "stage_a_2026.parquet", "prediction_ts",
                                        f"byte copy of {_rel(STAGE_A)} (single-lineage R2-44 w730_raw)")
    # technique-event inputs: the sim Context metrics/premium frames (btcusdt_quant.sim.data formats)
    merged = None
    for table, columns in (("futures_global_ls_5m", {"long_short_ratio": "global_ls"}),
                           ("futures_top_ls_5m", {"long_short_ratio": "top_ls"}),
                           ("futures_oi_5m", {"sum_open_interest": "oi", "sum_open_interest_value": "oi_value"}),
                           ("futures_taker_lsr_5m", {"buy_sell_ratio": "taker_lsr"})):
        part = tables[table].loc[tables[table].source.eq("archive"), ["create_time", "logical_available_at",
                                                                      *columns]].rename(columns=columns)
        merged = part if merged is None else merged.merge(part, on=["create_time", "logical_available_at"],
                                                          how="outer")
    merged["available_time"] = pd.to_datetime(merged.logical_available_at, utc=True).astype("datetime64[ns, UTC]")
    technique_metrics = merged.sort_values("available_time")[
        ["available_time", "global_ls", "top_ls", "oi", "oi_value", "taker_lsr"]].reset_index(drop=True)
    art["technique_metrics"] = write_artifact(
        out / "technique_metrics.parquet", technique_metrics, "available_time",
        "four futures tables, source='archive', available_time=logical_available_at=create_time+5m "
        "(sim.data.load_metrics format; NaN = missing)")
    p = inside(premium, "open_time")
    technique_premium = pd.DataFrame({"available_time": p.close_time + pd.Timedelta(milliseconds=1),
                                      "premium": p.premium})
    art["technique_premium"] = write_artifact(out / "technique_premium.parquet", technique_premium, "available_time",
                                              "premium_1m, available_time=close_time+1 ms (sim.data.load_premium)")
    # availability and missingness metadata + gates.data checks
    m_in = inside(market, "open_time")
    step = np.diff(market.open_time.array.asi8)
    coverage = {"market_1m": grid_coverage(m_in.open_time, SNAP_START, SNAP_END, "1min"),
                "premium_1m": grid_coverage(inside(premium, "open_time").open_time, SNAP_START, SNAP_END, "1min"),
                **{t: grid_coverage(tables[t].loc[tables[t].source.eq("archive"), "create_time"], SNAP_START, SNAP_END,
                                    "5min") for t in fm.TABLES},
                "stage_a_2026": grid_coverage(stage.prediction_ts, SNAP_START, SNAP_END, "15min")}
    nulls = {t: tables[t].loc[tables[t].source.eq("archive")].isna().sum().to_dict() for t in fm.TABLES}
    late = {}
    for t in fm.TABLES:
        f = tables[t]
        create = pd.to_datetime(f.create_time, utc=True)
        late[t] = int((pd.to_datetime(f.logical_available_at, utc=True, format="mixed") < create + PERIOD).sum())
    stage_manifest = json.loads((STAGE_A.parent / "manifest.json").read_text(encoding="utf-8"))
    trained_past = sum(pd.Timestamp(f["train_cutoff"]) >= pd.Timestamp(f["prediction_start"])
                       for f in stage_manifest["folds"])
    gates = {
        "no_missing_or_duplicate_1m_bars": bool(len(step) and (step == 60_000_000_000).all()
                                                and coverage["market_1m"]["missing"] == 0
                                                and coverage["market_1m"]["duplicates"] == 0),
        "market_checked_interval": [str(market.open_time.iloc[0]), str(market.open_time.iloc[-1])],
        "no_row_available_before_period_end": late,
        "stage_a_logical_available_eq_prediction_ts": bool((stage.logical_available_at == stage.prediction_ts).all()),
        "stage_a_retrain_le_prediction_ts": bool((stage.retrain_time <= stage.prediction_ts).all()),
        "stage_a_checkpoints_trained_past_prediction_ts": int(trained_past),
        "split_crossing_labels": "not applicable to the snapshot (no labels stored); enforced by Stage-B (Task 4)",
        "parity_passed": bool(parity_report["passed"]), "prediction_parity_passed": bool(prediction_report["passed"])}
    availability = {
        "interval": [lo, hi],
        "rules": {"futures_tables": "create_time = interval start; archive logical_available_at = create_time+5m; "
                                    "REST logical_available_at = max(period end, received_at); as-of: create_time<=T "
                                    "and logical_available_at<=T",
                  "market_1m": "bar open_time; usable after open_time+1m",
                  "premium_1m": "open_time; available close_time+1 ms",
                  "funding": "actual fundingTime = logical_available_at; unknown interval -> interval_missing=1, "
                             "never 8 h; future rates never inputs",
                  "stage_a": "prediction_ts<=T and logical_available_at<=T; written_at physical only",
                  "missingness": "missing exogenous rows stay missing (age/missing masks); no backfill/imputation"},
        "coverage": coverage, "archive_null_counts": nulls,
        "funding": {"events_table_rows": len(events), "live_table_rows": len(legacy),
                    "model_input_events": len(model_funding),
                    "model_input_interval_missing": int(model_funding.interval_missing.sum()),
                    "interval_missing_event_times": [str(t) for t in
                                                     model_funding.publish_time[model_funding.interval_missing.eq(1)]],
                    "stage_a_input_funding_coverage": json.loads(
                        (gen.SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))["funding_coverage"]},
        "gates_data": gates}
    art["availability"] = _json_artifact(out / "availability.json", availability,
                                         "derived from the artifacts above (coverage, nulls, availability rules)")
    freeze_doc = json.loads(FREEZE.read_text(encoding="utf-8"))
    pre_2026 = [*r.input_records(),
                _subset_tree(ROOT / "artifacts/metrics", "*.zip", SNAP_START),
                _subset_tree(ROOT / "artifacts/premium_index_2020_2026h1", "*.zip", SNAP_START),
                _subset_tree(ROOT / "artifacts/funding_2020_2026h1", "*.zip", SNAP_START),
                *[_subset_tree(gen.HOLD_B.parent / seg, "*", None) for seg in ("DEV_FRONT", "DEV_BACK")]]
    manifest = {
        "kind": "R2-54 Stage-B immutable snapshot", "status": status, "created_at": r.utc_now(),
        "freeze": {**r.file_record(FREEZE), "frozen_utc": freeze_doc["status"]["frozen_utc"],
                   "amendments": [a["id"] for a in freeze_doc.get("amendments", [])]},
        "git": _git(), "interval": [lo, hi], "data_cutoff_exclusive": hi,
        "registry": registry(freeze_doc),
        "taker_source_rule": next(a["new"] for a in freeze_doc["amendments"] if a["id"] == "A3"),
        "time_structure": freeze_doc["time_structure"],
        "artifacts": art,
        "pre_2026_train_validation": pre_2026,
        "parity": {"report": r.file_record(PARITY_REPORT), "passed": parity_report["passed"],
                   "fields": parity_report["fields"],
                   "rest_staging_db": {"path": _rel(STAGING), "bytes": STAGING.stat().st_size,
                                       "sha256": _sha(STAGING)}},
        "prediction_parity": {"report": r.file_record(PREDICTION_REPORT), "passed": prediction_report["passed"]},
        "stage_a": {"manifest": r.file_record(STAGE_A.parent / "manifest.json"),
                    "inputs_manifest": r.file_record(gen.SNAPSHOT / "manifest.json"),
                    "folds": [{k: f[k] for k in ("model_id", "retrain_time", "train_cutoff", "checkpoint_sha256",
                                                  "predictions_sha256")} for f in stage_manifest["folds"]]},
        "live_db": {"path": str(live_db), "mode": "read-only"},
        "code": [r.file_record(p) for p in CODE],
        "gates_data": gates,
        "use": "Final evaluation reads only this snapshot; pre-2026 artifacts are hashed above.",
        "write_policy": "write-once; every file set read-only after write"}
    path = out / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _read_only(path)
    return {"status": status, "manifest": _rel(path), "sha256": _sha(path), "gates_data": gates}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("fetch-rest", "parity", "prediction-parity", "snapshot"))
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--days", help="comma-separated UTC days for prediction parity")
    parser.add_argument("--allow-failed-parity", action="store_true",
                        help="snapshot: write a NOT_FINAL candidate to --out (never the final path) when parity failed")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.command == "fetch-rest":
        result = fetch_rest()
    elif args.command == "parity":
        result = parity()
    elif args.command == "prediction-parity":
        default = ["2026-01-01", *[f"2026-{m:02d}-15" for m in range(2, 10)],
                   *[f"2026-10-{d:02d}" for d in range(1, 8)]]
        days = [pd.Timestamp(d, tz="UTC") for d in (args.days.split(",") if args.days else default)]
        result = prediction_parity(days, args.device)
    else:
        out = args.out or (CANDIDATE_DIR if args.allow_failed_parity else SNAPSHOT_DIR)
        result = build_snapshot(out, allow_failed_parity=args.allow_failed_parity)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
