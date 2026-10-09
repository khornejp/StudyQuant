"""R2-52A AX paper books on btcusdt_quant.sim (computed by scripts/paper_catalog.py).

Frozen spec: out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json paper_rollout. Exactly 27 hidden 1x source books
(ungated NATIVE signal table, build_variant(..., ax=True), core exit_policy="R2_52A", k from the last pre-cutoff
validation window) and their 27 visible x3 overlays "<source>_x3". C1_AX maps to K01. Every other paper book is
retired: its rows stay in the database as the record and are never processed again.
"""
from __future__ import annotations
import json
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np, pandas as pd
from btcusdt_quant.sim import core, data, regime, schema
from btcusdt_quant.sim.reference import SimConfig
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant
from . import book, leverage

ROOT = Path(__file__).resolve().parents[2]
Q3_PREMIUM = ROOT / "artifacts/hold_a_2026q3/premium_index"
SELECTED_K = ROOT / "out/k45_rl_r2_48_20261007/r2_52a/selected_k.csv"
K_WINDOW = (pd.Timestamp("2025-09-01T00:00Z"), pd.Timestamp("2025-12-01T00:00Z"))    # paper_rollout.initial_k
CONFIG = SimConfig(exit_policy="R2_52A", include_funding=False)      # funding is repriced per boundary below

AX_BOOKS = ("C1_AX", "B1_AX", "B2_AX", "B3_AX", "K02_AX", "K03_AX", "K04_AX", "K05_AX", "K06_k0.5_AX",
            "K06_k1.0_AX", "K07_k0.5_AX", "K07_k1.0_AX", "K08_AX", "K09_AX", "K11_15m_AX", "K11_1h_AX", "K12_30m_AX",
            "K12_1h_AX", "K13_AX", "K14_AX", "K15_AX", "K19_AX", "K21_A_AX", "K21_B_AX", "K26_AX", "K29_AX", "K30_AX")
BOOKS = {name: ("K01" if name == "C1_AX" else name[:-3], False, "NATIVE") for name in AX_BOOKS}
X3_BOOKS = tuple(f"{name}_x3" for name in AX_BOOKS)
# C1_FLIP_AX (Codex 2026-10-09, user-approved): added after the frozen 27-book rollout; runs only when configured.
# Source K01_FLIP (F3 side flipped + E1), k from its own rolling selection (sim_adaptive_exit.py --flip).
FLIP_SELECTED_K = ROOT / "out/k45_rl_r2_48_20261007/r2_52a_flip/selected_k.csv"
FLIP_BOOKS = ("C1_FLIP_AX",)
FLIP_X3_BOOKS = tuple(f"{name}_x3" for name in FLIP_BOOKS)
BOOKS["C1_FLIP_AX"] = ("K01_FLIP", False, "NATIVE")
FLIP_NAMES = {"C1_FLIP_AX": "롱숏비율 극단 방향 추종 + 거래량 급증 상단 돌파 · 추세추종"}
K_SOURCES = {"K01_FLIP": FLIP_SELECTED_K}       # research id -> its selected_k.csv (default SELECTED_K)
# presentation_addendum_2026-10-08.name_list (verbatim): the visible x3 book's plain Korean label
NAMES = {
    "C1_AX": "롱숏비율 역추세 + 거래량 급증 돌파",
    "K02_AX": "롱숏비율 역추세 (30분)",
    "K03_AX": "롱숏비율 역추세 (30일 기준)",
    "K04_AX": "거래량 급증 돌파 (15분)",
    "K05_AX": "채널 돌파 (30분)",
    "K06_k0.5_AX": "변동성 돌파 (예측폭 0.5배)",
    "K06_k1.0_AX": "변동성 돌파 (예측폭 1배)",
    "K07_k0.5_AX": "양방향 돌파 주문 (예측폭 0.5배)",
    "K07_k1.0_AX": "양방향 돌파 주문 (예측폭 1배)",
    "K08_AX": "변동성 수축 후 돌파",
    "K09_AX": "저변동성 평균회귀 (볼린저)",
    "K11_15m_AX": "이동평균 교차 (15분)",
    "K11_1h_AX": "이동평균 교차 (1시간)",
    "K12_30m_AX": "추세선 전환 (30분)",
    "K12_1h_AX": "추세선 전환 (1시간)",
    "K13_AX": "다중 시간대 추세 일치",
    "K14_AX": "장 시작 범위 돌파",
    "K15_AX": "VWAP 평균회귀",
    "K19_AX": "선물 프리미엄 평균회귀",
    "K26_AX": "피벗 지지·저항 반전",
    "K29_AX": "지지·저항 필터 반전",
    "K30_AX": "돌파 후 되돌림",
    "B1_AX": "채널·거래량 돌파와 롱숏비율 극단값 반전 종합",
    "B2_AX": "단기 변동 확대 예상 때만 돌파·롱숏비율 반전 종합",
    "B3_AX": "단기 변동 확대 때 돌파, 단기 변동 축소·장기 변동 상위권 제외 때 롱숏비율 반전",
    "K21_A_AX": "테이커 매수 비중 극단값 추세추종 (15분·30일 기준)",
    "K21_B_AX": "테이커 매수 비중 극단값 역추세 (15분·30일 기준)",
}


def _adaptive():
    """scripts/sim_adaptive_exit.py helpers (E, E-min, heads, E0): paper uses exactly the research construction."""
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import sim_adaptive_exit
    return sim_adaptive_exit


def source_of(name: str) -> str:
    return name[:-3] if name.endswith("_x3") else name


def label(name: str) -> str:
    """Plain Korean label of a visible x3 book (or its hidden source); no internal code, no 3x suffix."""
    source = source_of(name)
    return NAMES[source] if source in NAMES else FLIP_NAMES[source]


@lru_cache(maxsize=4)
def paper_k(path: Path = SELECTED_K) -> dict[str, float]:
    """k per research id from the last completed validation window inside K_WINDOW (4 bps, tie -> 2.0 applied by
    the research run that wrote the file)."""
    frame = pd.read_csv(path)
    for column in ("val_start", "val_end"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    inside = frame.loc[(frame.val_start >= K_WINDOW[0]) & (frame.val_end <= K_WINDOW[1])]
    last = inside.sort_values("val_end", kind="stable").groupby("id").tail(1)
    return {row.id: float(row.k) for row in last.itertuples(index=False)}


def book_k(spec_id: str) -> float:
    """Paper k of a research id, read from that id's own selection file (K_SOURCES, else SELECTED_K)."""
    return paper_k(K_SOURCES.get(spec_id, SELECTED_K))[spec_id]


def needs_model(name: str) -> bool:
    return name in BOOKS        # AX needs E for every entry: always model-dependent


_TABLES: dict[str, tuple[Context, pd.DataFrame]] = {}


def raw_table(name: str, ctx: Context) -> pd.DataFrame:
    """AX signal rows at their signal time T (before any live decision shift); one build per context."""
    spec_id = BOOKS[name][0]
    cached = _TABLES.get(spec_id)
    if cached is None or cached[0] is not ctx:
        table, _ = build_variant(ctx, spec_id, False, "NATIVE", ax=True)
        table["decision_time"] = pd.to_datetime(table.decision_time, utc=True)
        cached = (ctx, table)
        _TABLES[spec_id] = cached
    return cached[1].copy()


def signal_rows(name: str, ctx: Context, since: pd.Timestamp) -> pd.DataFrame:
    """Recent decisions of a book for the dashboard condition panel."""
    spec_id = BOOKS[name][0]
    table = raw_table(name, ctx)
    table = table.loc[table.decision_time >= since]
    if table.decision_time.duplicated().any():      # composite: one row per decision, priority order kept
        table = _merge_components(table)
    table = table.loc[table.decision_time >= since].copy()
    times = pd.DatetimeIndex(table.decision_time)
    table["M"] = regime._asof(ctx.regime, times, "M", pd.Timedelta(minutes=14)) if "M" in ctx.regime else np.nan
    closes = ctx.minutes.set_index("open_time").close
    table["close"] = closes.reindex(times - pd.Timedelta(minutes=1)).to_numpy()
    if "M" in ctx.regime:
        L = regime._asof(ctx.regime, times, "L", BIND_AGE)
        E = regime.e_bps(ctx.regime, times, CATALOG[spec_id].e_head)
        bound = bind_predictions(ctx.regime if "available_at" in ctx.regime else None, times)
        table["model"] = [json.dumps({"M": None if pd.isna(m) else round(float(m), 4),
                                      "L": None if pd.isna(x) else round(float(x), 4),
                                      "E_bps": None if pd.isna(e) else round(float(e), 2), "E_head": CATALOG[spec_id].e_head,
                                      "prediction_ts": None if pd.isna(p) else p.isoformat(),
                                      "available_at": None if pd.isna(a) else a.isoformat()})
                          for m, x, e, p, a in zip(table.M, L, E, bound.prediction_ts, bound.available_at)]
    else:
        table["model"] = None
    indicator_columns = [c for c in table if c.startswith("ind_")]
    table["indicators"] = [json.dumps({c[4:]: (None if pd.isna(v) else round(float(v), 6)) for c, v in zip(indicator_columns, values)})
                           for values in table[indicator_columns].itertuples(index=False, name=None)] if indicator_columns else "{}"
    if "expiry_min" not in table:
        table["expiry_min"] = 0
    keep = ["decision_time", "side", "entry", "upper", "lower", "stop_bps", "expiry_min",
            "allow_entry", "exit_long", "exit_short",
            "M", "close", "indicators", "model"]
    return table[keep].assign(book=name).reset_index(drop=True)


COMPONENT_NAMES = {1: "A2", 2: "E1", 3: "F3", 4: "F3W"}


def _merge_components(table: pd.DataFrame) -> pd.DataFrame:
    """Composite books: the first allowed non-zero component decides; every component's side is an indicator."""
    rows = []
    for decision, group in table.groupby("decision_time", sort=True):
        chosen = group.loc[(group.side != 0) & group.allow_entry]
        signalled = group.loc[group.side != 0]
        first = (chosen if len(chosen) else signalled if len(signalled) else group).iloc[0]
        row = first.to_dict()
        row["side"] = int(first.side)
        row["allow_entry"] = bool(len(chosen))
        for _, part in group.iterrows():
            row[f"ind_{COMPONENT_NAMES.get(int(part.component), part.component)}_side"] = int(part.side)
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.drop(columns=[c for c in out if c.startswith("ind_") and not c.endswith("_side")])


BIND_AGE = pd.Timedelta(minutes=14)     # the prediction bound to signal time T: latest origin <= T, at most 14 min old
MAX_WAIT = pd.Timedelta(minutes=60)     # a signal waits for its prediction at most until the next signal (<= 60 min)
DECISION_COLUMNS = ["book", "signal_time", "decision_time", "status", "prediction_ts", "available_at", "decided_at",
                    "model_id"]


def _opens(table: pd.DataFrame) -> pd.Series:
    """Rows that can open a position, i.e. the model-dependent part of a signal."""
    return (table.side != 0) | table.entry.isin(["oco", "grid"])


def bind_predictions(predictions: pd.DataFrame, times: pd.DatetimeIndex) -> pd.DataFrame:
    """Prediction bound to each signal time T (fixed at T, never re-chosen later)."""
    out = pd.DataFrame({"prediction_ts": pd.Series(pd.NaT, index=range(len(times)), dtype="datetime64[ns, UTC]"),
                        "available_at": pd.Series(pd.NaT, index=range(len(times)), dtype="datetime64[ns, UTC]"),
                        "model_id": pd.Series(None, index=range(len(times)), dtype=object)})
    if predictions is None or not len(predictions):
        return out
    minute = predictions.attrs.get("minute")
    if minute is not None and len(minute):
        minute = minute.loc[~minute.timestamp.isin(set(predictions.timestamp))]
        predictions = pd.concat([predictions, minute], ignore_index=True).sort_values("timestamp", kind="stable")
    ts = pd.DatetimeIndex(predictions.timestamp).as_unit("ns")
    pos = np.searchsorted(ts.asi8, pd.DatetimeIndex(times).as_unit("ns").asi8, side="right") - 1
    ok = (pos >= 0)
    ok[ok] = (pd.DatetimeIndex(times)[ok] - ts[pos[ok]]) <= BIND_AGE
    out.loc[ok, "prediction_ts"] = ts[pos[ok]]
    out.loc[ok, "available_at"] = pd.DatetimeIndex(predictions.available_at).as_unit("ns")[pos[ok]]
    out.loc[ok, "model_id"] = predictions.model_id.to_numpy()[pos[ok]]
    return out


def fill_rows(name: str, trades: pd.DataFrame, held: dict | None,
              decisions: pd.DataFrame | None = None) -> pd.DataFrame:
    """Filled entry legs linked back to the dashboard's original signal time."""
    columns = ["book", "signal_time", "fill_time", "side", "fill_price"]
    source = trades.attrs.get("fills") if trades is not None else None
    if source is None:
        source = (trades.loc[trades.boundary.eq("PESS"),
                             ["decision_time", "entry_time", "side", "entry_price"]]
                  if trades is not None and len(trades) else pd.DataFrame())
    else:
        source = source.copy()
    legs = [] if held is None else held.get("legs", [])
    if legs:
        source = pd.concat([source, pd.DataFrame(legs).rename(columns={"fill_time": "entry_time",
                                                                      "fill_price": "entry_price"})],
                           ignore_index=True, sort=False)
    if source.empty:
        return pd.DataFrame(columns=columns)
    source = source.rename(columns={"entry_time": "fill_time", "entry_price": "fill_price"})
    source["decision_time"] = pd.to_datetime(source.decision_time, utc=True)
    source["fill_time"] = pd.to_datetime(source.fill_time, utc=True)
    mapping = {}
    if decisions is not None and len(decisions):
        decided = decisions.loc[decisions.status.eq("decided") & decisions.decision_time.notna()]
        mapping = dict(zip(pd.to_datetime(decided.decision_time, utc=True),
                           pd.to_datetime(decided.signal_time, utc=True)))
    source["signal_time"] = source.decision_time.map(lambda value: mapping.get(value, value))
    source.insert(0, "book", name)
    return (source[columns].drop_duplicates().sort_values(["signal_time", "fill_time"], kind="stable")
            .reset_index(drop=True))


def decide(name: str, table: pd.DataFrame, predictions: pd.DataFrame, known: set, now: pd.Timestamp,
           book_start: pd.Timestamp) -> list[dict]:
    """New terminal decision events for signals at or after book_start: decided once (when the bound prediction is
    first observed) or expired (prediction too late / missing past the next signal). Pending signals return nothing."""
    times = pd.DatetimeIndex(table.decision_time.drop_duplicates().sort_values())
    next_time = pd.Series(times[1:].append(pd.DatetimeIndex([pd.NaT])), index=times)
    opening = table.loc[_opens(table)]
    signal_times = pd.DatetimeIndex(opening.decision_time.drop_duplicates())
    signal_times = signal_times[(signal_times >= book_start) & (signal_times <= now)]
    signal_times = signal_times[[t.isoformat() not in known for t in signal_times]]
    bound = bind_predictions(predictions, signal_times)
    events = []
    for k, t in enumerate(signal_times):
        nxt = next_time.get(t)
        valid_until = min(t + MAX_WAIT, nxt) if pd.notna(nxt) else t + MAX_WAIT
        available = bound.available_at.iloc[k]
        event = {"book": name, "signal_time": t, "decision_time": None, "status": None,
                 "prediction_ts": bound.prediction_ts.iloc[k], "available_at": available, "decided_at": None,
                 "model_id": bound.model_id.iloc[k]}
        if pd.notna(available) and available <= now:
            decided_at = max(now, available, t)
            decision_time = decided_at.ceil("min")
            if decision_time + pd.Timedelta(minutes=1) >= valid_until:
                event.update(status="expired_late", decided_at=decided_at)
            else:
                event.update(status="decided", decided_at=decided_at, decision_time=decision_time)
        elif now >= valid_until:
            event.update(status="expired_missing")
        else:
            continue
        events.append(event)
    return events


STATE_FLAGS = ("exit_long", "exit_short", "ax_exit_long", "ax_exit_short")


def live_table(table: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    """Opening rows move to their confirmed decision time; undecided or expired ones cannot open. Exit and state
    values (native flags, family state flags, the state-check price) stay at their signal time T."""
    decided = (decisions.loc[decisions.status == "decided"].set_index("signal_time").decision_time
               if len(decisions) else pd.Series(dtype="datetime64[ns, UTC]"))
    flags = [c for c in STATE_FLAGS if c in table]
    opening = _opens(table)
    keep = table.loc[~opening].copy()
    state = table[flags].any(axis=1) | (table.anchor_price.notna() if "anchor_price" in table else False)
    exits = table.loc[opening & state].copy()
    exits["side"] = 0; exits["allow_entry"] = False; exits["entry"] = "market"
    moved = table.loc[opening & table.decision_time.isin(decided.index)].copy()
    moved["decision_time"] = moved.decision_time.map(decided)
    moved[flags] = False
    if "anchor_price" in moved:
        moved["anchor_price"] = np.nan
    out = pd.concat([keep, exits, moved], ignore_index=True)
    return out.sort_values("decision_time", kind="stable").reset_index(drop=True)


@lru_cache(maxsize=1)
def _archive_premium() -> pd.DataFrame:
    return data.load_premium(Q3_PREMIUM) if Q3_PREMIUM.exists() else pd.DataFrame(columns=["available_time", "premium"])


def live_context(market: pd.DataFrame, features: pd.DataFrame, premium: pd.DataFrame, funding: pd.DataFrame,
                 predictions: pd.DataFrame | None = None) -> Context:
    """Paper tables -> sim Context with the research availability rules."""
    minutes = market[data.MINUTE_COLUMNS].copy()
    minutes["open_time"] = pd.to_datetime(minutes.open_time, utc=True).astype("datetime64[ns, UTC]")
    ls = features.copy()
    ls["open_time"] = pd.to_datetime(ls.open_time, utc=True).astype("datetime64[ns, UTC]")
    archive = ls.source.ne("rest") if "source" in ls else pd.Series(True, index=ls.index)
    available = ls.open_time + pd.to_timedelta(np.where(archive, 5, 0), unit="min")   # paper rules.py
    metrics = pd.DataFrame({"available_time": available, "global_ls": ls.global_ls_account.astype(float),
                            "top_ls": np.nan, "oi": np.nan, "oi_value": np.nan, "taker_lsr": np.nan})
    metrics = metrics.sort_values("available_time").drop_duplicates("available_time", keep="last")
    live_premium = pd.DataFrame({"available_time": pd.to_datetime(premium.open_time, utc=True) + pd.Timedelta(minutes=1),
                                 "premium": premium.premium_index.astype(float)})
    prem = pd.concat([_archive_premium(), live_premium], ignore_index=True)
    prem = prem.sort_values("available_time").drop_duplicates("available_time", keep="last").reset_index(drop=True)
    fund = funding[["time", "rate"]].copy()
    fund["time"] = pd.to_datetime(fund.time, utc=True, format="mixed")
    if predictions is not None and len(predictions):
        reg = regime.load_regime(predictions)
        minute = predictions.attrs.get("minute")
        if minute is not None and len(minute):
            minute = minute.loc[~minute.timestamp.isin(set(predictions.timestamp))]     # the 15 m row wins on the grid
            reg = pd.concat([reg, regime.rank_against(predictions, minute)], ignore_index=True)
            reg = reg.sort_values("timestamp", kind="stable").reset_index(drop=True)
    else:
        reg = pd.DataFrame({"timestamp": pd.Series(dtype="datetime64[ns, UTC]"), "M": pd.Series(dtype=float),
                            "L": pd.Series(dtype=float)})
    return Context(minutes=minutes.sort_values("open_time").reset_index(drop=True), metrics=metrics.reset_index(drop=True),
                   premium=prem, funding=fund.sort_values("time").reset_index(drop=True), regime=reg,
                   end=minutes.open_time.max() + pd.Timedelta(minutes=1))


def e_frame(ctx: Context) -> pd.DataFrame:
    """E source = the immutable 15-minute prediction grid with its logical available_at (research E updates every
    15 min; the per-minute mixed rows are dashboard-only and are pruned after 3 days)."""
    reg = ctx.regime
    if not len(reg) or "timestamp" not in reg:
        return reg
    stamp = pd.DatetimeIndex(reg.timestamp)
    return reg.loc[(stamp.minute % 15 == 0) & (stamp.second == 0)].reset_index(drop=True)


def row_e0(table: pd.DataFrame, frame: pd.DataFrame, spec_id: str) -> np.ndarray:
    """Market-entry E0 bound to each row's (effective) decision time; NaN when no causal E (NO_ENTRY_E)."""
    if not len(frame) or not any(c.startswith("prediction_exc_") for c in frame):
        return np.full(len(table), np.nan)
    return _adaptive().row_e0(table, frame, spec_id)


def _e_inputs(frame: pd.DataFrame, minutes: pd.DataFrame, spec_id: str) -> tuple[np.ndarray, np.ndarray]:
    helpers = _adaptive()
    names = helpers.heads(spec_id)
    if not len(frame) or not all(f"prediction_exc_{h}" in frame for h in names):
        empty = np.full((len(minutes), len(names)), np.nan)
        return empty, empty.copy()
    return helpers.e_matrix(frame, pd.DatetimeIndex(minutes.open_time), names)


def _realized_minute_pnl(result, closes: pd.Series) -> pd.Series:
    """Remove still-open legs from simulator MTM so daily_pnl remains a closed ledger."""
    out = result.minute_pnl.copy()
    legs = [] if result.open_position is None else result.open_position.get("legs", [])
    for leg in legs:
        index = out.index[out.index >= pd.Timestamp(leg["entry_time"])]
        if not len(index):
            continue
        prices = closes.reindex(index).to_numpy(float)
        previous = np.r_[float(leg["entry_price"]), prices[:-1]]
        contribution = float(leg["side"]) * np.log(prices / previous) * 1e4 * float(leg["units"])
        contribution[0] -= 2.0 * float(leg["units"])
        out.loc[index] -= contribution
    return out


def _funding_by_day(legs: pd.DataFrame, funding: pd.DataFrame, boundary: str) -> pd.Series:
    """Funding cashflows by settlement day, scaled by each simulator leg's units."""
    if legs.empty or funding.empty:
        return pd.Series(dtype=float)
    times, rates = book._funding_arrays(funding)
    values: dict[pd.Timestamp, float] = {}
    for leg in legs.itertuples(index=False):
        entry, exit_ = pd.Timestamp(leg.entry_time).value, pd.Timestamp(leg.exit_time).value
        lo = int(np.searchsorted(times, entry, side="left"))
        hi = int(np.searchsorted(times, exit_, side="right"))
        for when, rate in zip(times[lo:hi], rates[lo:hi]):
            cashflow = -float(leg.side) * float(rate) * 1e4 * float(leg.units)
            edge = when == entry or when == exit_
            if edge and not ((boundary == "PESS" and cashflow < 0) or
                             (boundary == "OPT" and cashflow > 0)):
                continue
            day = pd.Timestamp(int(when), tz="UTC").floor("D")
            values[day] = values.get(day, 0.0) + cashflow
    return pd.Series(values, dtype=float).sort_index()


def ax_table(name: str, ctx: Context, decisions: pd.DataFrame | None, book_start: pd.Timestamp) -> pd.DataFrame:
    """Live AX rows: decided openings at their effective decision time with E0 bound there, the head column of the
    opening component (composites) and the paper k."""
    spec_id = BOOKS[name][0]
    table = live_table(raw_table(name, ctx), decisions if decisions is not None else pd.DataFrame())
    table = schema.validate(table.loc[table.decision_time >= book_start].reset_index(drop=True))
    return table.assign(e0_bps=row_e0(table, e_frame(ctx), spec_id),
                        e_col=_adaptive().e_cols(table, spec_id).astype(float), k=book_k(spec_id))


def run_book(name: str, ctx: Context, funding: pd.DataFrame, book_start: pd.Timestamp, end: pd.Timestamp,
             decisions: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict | None]:
    """(trades, daily, open position) in the paper tables' shape for both funding boundaries; replays only the
    confirmed decision events (`decisions`), never a re-decided history. trades.attrs: "legs" (core trades),
    "source" (the x3 input: accepted fills, source exits with phase, the open position as _active) and "fills"."""
    spec_id = BOOKS[name][0]
    table = ax_table(name, ctx, decisions, book_start)
    e, e_min = _e_inputs(e_frame(ctx), ctx.minutes, spec_id)
    result = core.simulate(table, ctx.minutes, book_start, end, CONFIG, e_bps=e, e_min_bps=e_min)
    legs = result.trades
    fills = (legs[["decision_time", "entry_time", "side", "entry_price"]].drop_duplicates().copy()
             if len(legs) else pd.DataFrame(columns=["decision_time", "entry_time", "side", "entry_price"]))
    trade_rows, daily_rows = [], []
    fees = pd.concat([pd.Series(legs.units.to_numpy() * 2.0, index=legs.entry_time.dt.floor("D")),
                      pd.Series(legs.units.to_numpy() * 2.0, index=legs.exit_time.dt.floor("D"))]).groupby(level=0).sum() \
        if len(legs) else pd.Series(dtype=float)
    closes = ctx.minutes.set_index("open_time").close
    realized = _realized_minute_pnl(result, closes)
    pnl_ex_funding = realized.groupby(realized.index.floor("D")).sum()
    for boundary in ("PESS", "OPT"):
        if len(legs):
            priced = book.reprice(legs[["entry_time", "exit_time", "side", "entry_price", "exit_price"]],
                                  funding, boundary, 0.0)
            leg = legs.assign(funding_bps=priced.funding_bps.to_numpy() * legs.units.to_numpy())
            leg["net_bps"] = leg.gross_bps - leg.fee_bps + leg.funding_bps
            merged = leg.groupby(["entry_time", "side"], as_index=False).agg(
                decision_time=("decision_time", "first"), exit_time=("exit_time", "max"),
                entry_price=("entry_price", "first"), exit_price=("exit_price", "last"),
                gross_bps=("gross_bps", "sum"), cost_bps=("fee_bps", "sum"),
                funding_bps=("funding_bps", "sum"), net_bps=("net_bps", "sum"),
                exit_reason=("exit_reason", lambda x: "+".join(x.str.upper())))
            merged["hold_minutes"] = (merged.exit_time - merged.entry_time) / pd.Timedelta(minutes=1)
            trade_rows.append(merged.assign(book=name, boundary=boundary, candidate=spec_id))
            funding_day = _funding_by_day(legs, funding, boundary)
        else:
            funding_day = pd.Series(dtype=float)
        days = pd.DatetimeIndex(pnl_ex_funding.index.union(funding_day.index))
        net_ex = pnl_ex_funding.reindex(days, fill_value=0.0)
        cost = fees.reindex(days, fill_value=0.0)
        fund = funding_day.reindex(days, fill_value=0.0)
        daily_rows.append(pd.DataFrame({"book": name, "boundary": boundary, "date": days.strftime("%Y-%m-%d"),
                                        "gross_bps": (net_ex + cost).to_numpy(), "cost_bps": cost.to_numpy(),
                                        "funding_bps": fund.to_numpy(), "net_bps": (net_ex + fund).to_numpy()}))
    trades = pd.concat(trade_rows, ignore_index=True) if trade_rows else pd.DataFrame()
    source = legs[["entry_time", "exit_time", "side", "entry_price", "exit_price"]].assign(
        exit_reason=legs.exit_reason.str.upper(), candidate=spec_id, _active=False)
    source["exit_phase"] = leverage.exit_phases(source, ctx.minutes) if len(source) else pd.Series(dtype=object)
    held = result.open_position
    if held is not None:
        source = pd.concat([source, pd.DataFrame([{
            "entry_time": held["entry_time"], "exit_time": end, "side": held["side"], "entry_price": held["avg_price"],
            "exit_price": float(closes.iloc[-1]), "exit_reason": None, "candidate": spec_id, "_active": True,
            "exit_phase": None}])], ignore_index=True)
    trades.attrs.update(fills=fills, legs=legs, source=source)
    return trades, pd.concat(daily_rows, ignore_index=True), held


def ax_state(name: str, held: dict, ctx: Context, end: pd.Timestamp) -> dict:
    """Dashboard state of the open AX position: E0, E_t, k, R0, R_t, hard stop, trail, best price, anchors."""
    spec_id, side = BOOKS[name][0], int(held["side"])
    helpers = _adaptive()
    names = helpers.heads(spec_id)
    head = names[0] if len(names) == 1 else helpers.legacy_heads().get(int(held["component"]))
    frame = e_frame(ctx)
    e_t = (float(helpers.e_at(frame, pd.DatetimeIndex([end]), head)[0])
           if head is not None and len(frame) and f"prediction_exc_{head}" in frame else None)
    entry, r = float(held["avg_price"]), float(held["r_bps"])
    hard = entry * np.exp(-side * r / 1e4)
    trail = float(held["best_price"]) * np.exp(-side * 0.5 * r / 1e4) if held["trail_armed"] else None
    clean = lambda v: None if v is None or not np.isfinite(v) else float(v)
    return {"book": name, "position_id": int(held["position_id"]), "status": "OPEN", "side": side,
            "entry_time": pd.Timestamp(held["entry_time"]).isoformat(), "entry_price": entry,
            "k": float(held["k"]), "e_head": head, "e0_bps": float(held["e0_bps"]), "e_t_bps": clean(e_t),
            "r0_bps": float(held["r0_bps"]), "r_bps": r, "hard_stop": hard,
            "trail_armed": int(bool(held["trail_armed"])), "best_price": float(held["best_price"]),
            "trail_stop": clean(trail), "anchor_upper": clean(held.get("anchor_upper")),
            "anchor_lower": clean(held.get("anchor_lower")), "updated_at": pd.Timestamp(end).isoformat()}


__all__ = ["AX_BOOKS", "BOOKS", "FLIP_BOOKS", "FLIP_NAMES", "FLIP_X3_BOOKS", "NAMES", "X3_BOOKS", "ax_state",
           "book_k", "fill_rows", "label", "live_context", "paper_k", "run_book"]
