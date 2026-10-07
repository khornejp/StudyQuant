"""Live paper books for the R2-48 technique catalog on btcusdt_quant.sim (computed by scripts/paper_catalog.py).

Book name = technique id + variant suffix: "" (no gate, NATIVE), "_G" (gate), "_D" (DETEXIT), "_GD".
Inputs: the collector's 1 m klines, global long/short ratio, premium and funding, plus the live R2-44 PatchTST
predictions (btcusdt_quant.paper.detector). OI-, top-trader- and taker-LSR-based techniques (K20, K23, K24) have no
live input; K01 is the existing C1 book.
"""
from __future__ import annotations
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
import numpy as np, pandas as pd
from btcusdt_quant.sim import core, data, regime
from btcusdt_quant.sim.exit_overlay import overlay
from btcusdt_quant.sim.reference import SimResult, TRADE_COLUMNS
import json
from btcusdt_quant.sim.strategies import CATALOG, Context, apply_exit, apply_gate, build_variant, grid
from . import book

LIVE_IDS = ("K02", "K03", "K04", "K05", "K06_k0.5", "K06_k1.0", "K07_k0.5", "K07_k1.0", "K08", "K09", "K10",
            "K11_15m", "K11_1h", "K12_30m", "K12_1h", "K13", "K14", "K15", "K16", "K17_N5", "K17_N7", "K18", "K19",
            "K21_A", "K21_B", "K22", "B1", "B2", "B3")
SUFFIX = {(False, "NATIVE"): "", (True, "NATIVE"): "_G", (False, "DETEXIT"): "_D", (True, "DETEXIT"): "_GD"}
Q3_PREMIUM = Path(__file__).resolve().parents[2] / "artifacts/hold_a_2026q3/premium_index"


def _variants() -> dict[str, tuple[str, bool, str]]:
    out = {}
    for spec_id in LIVE_IDS:
        spec = CATALOG[spec_id]
        for (gated, style), suffix in SUFFIX.items():
            if (gated and spec.gate is None) or (style == "DETEXIT" and spec.simulator == "grid"):
                continue
            out[spec_id + suffix] = (spec_id, gated, style)
    return out


BOOKS = _variants()
OVERLAY_RULES = {"K03_TRAIL": "R2_TRAIL", "K03_S150": "S150",
                 "B2_BE": "R1_BREAKEVEN", "B2_S150": "S150"}
BOOKS.update({"K03_TRAIL": ("K03", False, "NATIVE"), "K03_S150": ("K03", False, "NATIVE"),
              "B2_BE": ("B2", False, "NATIVE"), "B2_S150": ("B2", False, "NATIVE")})
OVERLAY_LABELS = {"K03_TRAIL": "K03 추적 손절(비교)", "K03_S150": "K03 고정 손절 -150(비교)",
                  "B2_BE": "B2 본전 이동(비교)", "B2_S150": "B2 고정 손절 -150(비교)"}


DEFINITIONS = {
    "K02": "F3-30: 30분마다 global LS가 90일 q90 이상 숏 / q10 이하 롱, 4시간 보유, 반대 신호 반전",
    "K03": "F3W-30: 30분마다 global LS가 30일 q80 이상 숏 / q20 이하 롱, 12시간 보유, 반대 신호 반전",
    "K04": "E1-15: 15분봉 거래량 z(20) > 3 이고 종가가 직전 20봉 고가 돌파 → 롱, 5시간 보유",
    "K05": "A2-30: 30분봉 종가가 직전 55봉 고가 돌파 롱 / 저가 이탈 숏, 반대쪽 10봉 채널 이탈 시 청산",
    "K06_k0.5": "VB: 매시 종가±0.5×예측 range_1h에 양방향 역지정가, 1시간 만료, 4시간 보유",
    "K06_k1.0": "VB: 매시 종가±1.0×예측 range_1h에 양방향 역지정가, 1시간 만료, 4시간 보유",
    "K07_k0.5": "STRADDLE: 15분마다 종가±0.5×예측 exc_1h 양방향 역지정가, 1시간 만료, 4시간 보유",
    "K07_k1.0": "STRADDLE: 15분마다 종가±1.0×예측 exc_1h 양방향 역지정가, 1시간 만료, 4시간 보유",
    "K08": "SQUEEZE: 15분 BB(20,2)가 KC(20,1.5) 안에 6봉 이상 후 해제 봉, 종가 vs BB 중앙 방향, 반대 KC 이탈 청산, 8시간",
    "K09": "LOWVOL_MR: 15분 종가 BB 하단 아래+RSI<30 롱 / 상단 위+RSI>70 숏, BB 중앙 도달 청산, 4시간",
    "K10": "GRID: 기준가±(0.5×예측 range_1h) 간격 위아래 3단 지정가, 1단 이익 청산, ±4단 이탈 전량 손절, 4시간 창",
    "K11_15m": "EMA_X 15분: EMA9가 EMA21 상향 교차 롱 / 하향 숏, 반대 교차 반전, 12시간",
    "K11_1h": "EMA_X 1시간: EMA9가 EMA21 상향 교차 롱 / 하향 숏, 반대 교차 반전, 12시간",
    "K12_30m": "SUPERTREND(10,3) 30분: 방향 전환 시 진입·반전, 12시간",
    "K12_1h": "SUPERTREND(10,3) 1시간: 방향 전환 시 진입·반전, 12시간",
    "K13": "MTF_MOM: 직전 15분·1시간·4시간 봉 수익률 부호가 모두 같으면 그 방향, 하나라도 다르면 청산, 12시간",
    "K14": "SESSION_ORB: UTC 00:00·07:00·13:30 첫 30분 고저 돌파 역지정가, 손절 반대편, 세션 시작+8시간 청산",
    "K15": "VWAP_MR: UTC 일 VWAP 괴리 z(30일) > 2 숏 / < -2 롱, VWAP 도달 청산, 4시간",
    "K16": "WICK_REV: 5분 꼬리 > 3×ATR(14)이고 반대 꼬리 < ATR → 꼬리 반대 방향, 1시간",
    "K17_N5": "STREAK_REV: 15분 같은 색 5봉 연속 후 반대 진입, 2시간",
    "K17_N7": "STREAK_REV: 15분 같은 색 7봉 연속 후 반대 진입, 2시간",
    "K18": "FUNDING_EXT: 정산 직후 funding이 직전 90일 상위 5% 숏 / 하위 5% 롱, 8시간",
    "K19": "PREMIUM_MR: 1시간 premium 평균 z(30일) > 2 숏 / < -2 롱, 4시간",
    "K21_A": "TAKER_IMB A: 15분 taker 매수 비중 z(30일) > 2 롱 / < -2 숏, 2시간",
    "K21_B": "TAKER_IMB B: 15분 taker 매수 비중 z(30일) > 2 숏 / < -2 롱, 2시간",
    "K22": "CVD_DIV: 15분 종가 20봉 신고가인데 CVD가 직전 고점보다 낮으면 숏, 대칭 롱, 4시간",
    "B1": "B1: A2-30 > E1-15 > F3-30 > F3W-30 우선순위 합성, 관문 없음",
    "B2": "B2: B1과 같은 우선순위, 탐지기 M ≥ 2/3일 때만 진입",
    "B3": "B3: M ≥ 2/3이면 A2·E1, M ≤ 1/3이고 L < 2/3이면 F3·F3W만 진입",
}
GATE_TEXT = {"HIGH": "관문: 탐지기 M ≥ 2/3", "LOW": "관문: 탐지기 M ≤ 1/3"}


def definition(name: str) -> str:
    spec_id, gated, style = BOOKS[name]
    parts = [DEFINITIONS[spec_id]]
    if gated:
        parts.append(GATE_TEXT[CATALOG[spec_id].gate])
    if style == "DETEXIT":
        parts.append("DETEXIT: 절반 진입+다음 판단 같은 방향이면 절반 추가, 손절·익절 = 예측 이탈폭 E, 익절 시 절반 청산 후 본전 손절")
    return " · ".join(parts)


def signal_rows(name: str, ctx: Context, since: pd.Timestamp) -> pd.DataFrame:
    """Recent decisions of a book for the dashboard condition panel."""
    spec_id, gated, style = BOOKS[name]
    if CATALOG[spec_id].simulator == "grid":
        plan = grid.grid_plan(ctx, gated)
        table = pd.DataFrame({"decision_time": plan.decision_time, "side": 0, "entry": "grid",
                              "upper": plan.base * np.exp(plan.g / 1e4), "lower": plan.base * np.exp(-plan.g / 1e4),
                              "stop_bps": np.nan, "allow_entry": True, "exit_long": False, "exit_short": False,
                              "expiry_min": grid.WINDOW_MIN,
                              "ind_grid_step_bps": plan.g, "ind_base": plan.base})
    else:
        spec = CATALOG[spec_id]
        table = apply_exit(apply_gate(_build(spec_id, ctx), ctx, spec.gate if gated else None), ctx, spec, style)
        table["decision_time"] = pd.to_datetime(table.decision_time, utc=True)
        table = table.loc[table.decision_time >= since]
        if table.decision_time.duplicated().any():      # composite: one row per decision, priority order kept
            table = _merge_components(table)
    table = table.loc[table.decision_time >= since].copy()
    times = pd.DatetimeIndex(table.decision_time)
    table["M"] = regime._asof(ctx.regime, times, "M", pd.Timedelta(minutes=14)) if "M" in ctx.regime else np.nan
    closes = ctx.minutes.set_index("open_time").close
    table["close"] = closes.reindex(times - pd.Timedelta(minutes=1)).to_numpy()
    if needs_model(name) and "M" in ctx.regime:
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


MODEL_IDS = {"K06_k0.5", "K06_k1.0", "K07_k0.5", "K07_k1.0", "K10", "B2", "B3"}
BIND_AGE = pd.Timedelta(minutes=14)     # the prediction bound to signal time T: latest origin <= T, at most 14 min old
MAX_WAIT = pd.Timedelta(minutes=60)     # a signal waits for its prediction at most until the next signal (<= 60 min)
DECISION_COLUMNS = ["book", "signal_time", "decision_time", "status", "prediction_ts", "available_at", "decided_at",
                    "model_id"]


def needs_model(name: str) -> bool:
    spec_id, gated, style = BOOKS[name]
    return gated or style == "DETEXIT" or spec_id in MODEL_IDS


_BUILDS: dict[str, tuple[Context, pd.DataFrame]] = {}


def _build(spec_id: str, ctx: Context) -> pd.DataFrame:
    """One technique build per context (several books share it)."""
    cached = _BUILDS.get(spec_id)
    if cached is None or cached[0] is not ctx:
        cached = (ctx, CATALOG[spec_id].build(ctx))
        _BUILDS[spec_id] = cached
    return cached[1].copy()


def raw_table(name: str, ctx: Context) -> pd.DataFrame:
    """Signal rows at their signal time T (before any live decision shift); grid books: one row per candidate grid."""
    spec_id, gated, style = BOOKS[name]
    spec = CATALOG[spec_id]
    if spec.simulator == "grid":
        plan = grid.grid_plan(ctx, gated)
        return pd.DataFrame({"decision_time": pd.to_datetime(plan.decision_time, utc=True), "side": 0, "entry": "grid",
                             "base": plan.base.to_numpy(), "g": plan.g.to_numpy(), "exit_long": False,
                             "exit_short": False, "allow_entry": True, "component": 1})
    table = apply_exit(apply_gate(_build(spec_id, ctx), ctx, spec.gate if gated else None), ctx, spec, style)
    table["decision_time"] = pd.to_datetime(table.decision_time, utc=True)
    return table


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


def live_table(table: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    """Opening rows move to their confirmed decision time; undecided or expired ones cannot open. Exit flags stay at T."""
    decided = (decisions.loc[decisions.status == "decided"].set_index("signal_time").decision_time
               if len(decisions) else pd.Series(dtype="datetime64[ns, UTC]"))
    opening = _opens(table)
    keep = table.loc[~opening].copy()
    exits = table.loc[opening & (table.exit_long | table.exit_short)].copy()
    exits["side"] = 0; exits["allow_entry"] = False; exits["entry"] = "market"
    moved = table.loc[opening & table.decision_time.isin(decided.index)].copy()
    moved["decision_time"] = moved.decision_time.map(decided)
    moved["exit_long"] = False; moved["exit_short"] = False
    out = pd.concat([keep, exits, moved], ignore_index=True)
    return out.sort_values("decision_time", kind="stable").reset_index(drop=True)


def label(name: str) -> str:
    if name in OVERLAY_LABELS:
        return OVERLAY_LABELS[name]
    spec_id, gated, style = BOOKS[name]
    return f"{spec_id} {CATALOG[spec_id].family}" + (" 관문" if gated else "") + (" DETEXIT" if style == "DETEXIT" else "")


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


def _overlay_result(result: SimResult, minutes: pd.DataFrame, rule: str) -> SimResult:
    """Apply the frozen minute overlay without changing the native entry sequence."""
    trades = result.trades.copy()
    times = pd.DatetimeIndex(minutes.open_time)
    t_ns = times.as_unit("ns").asi8
    o, h, l = (minutes[column].to_numpy(float) for column in ("open", "high", "low"))
    reason = "stop" if rule.startswith("S") else "breakeven" if rule == "R1_BREAKEVEN" else "trail"
    for index, trade in trades.iterrows():
        i0 = int(np.searchsorted(t_ns, pd.Timestamp(trade.entry_time).value))
        i_exit = int(np.searchsorted(t_ns, pd.Timestamp(trade.exit_time).value))
        hit = overlay(int(trade.side), float(trade.entry_price), i0, i_exit, o, h, l, rule, np.nan)
        if hit is None:
            continue
        exit_index, exit_price = hit
        gross = int(trade.side) * np.log(exit_price / float(trade.entry_price)) * 1e4 * float(trade.units)
        trades.loc[index, ["exit_time", "exit_price", "exit_reason", "gross_bps", "net_bps"]] = [
            times[exit_index], exit_price, reason, gross, gross - float(trade.fee_bps)]

    held = result.open_position
    if held is not None:
        i0 = int(np.searchsorted(t_ns, pd.Timestamp(held["entry_time"]).value))
        hit = overlay(int(held["side"]), float(held["avg_price"]), i0, len(times), o, h, l, rule, np.nan)
        if hit is not None:
            exit_index, exit_price = hit
            closed = []
            for leg in held["legs"]:
                gross = int(leg["side"]) * np.log(exit_price / float(leg["entry_price"])) * 1e4 * float(leg["units"])
                fee = 4.0 * float(leg["units"])
                closed.append({**leg, "exit_time": times[exit_index], "exit_price": exit_price,
                               "exit_reason": reason, "gross_bps": gross, "fee_bps": fee,
                               "funding_bps": 0.0, "net_bps": gross - fee})
            trades = pd.concat([trades, pd.DataFrame(closed, columns=TRADE_COLUMNS)], ignore_index=True)
            held = None
    return SimResult(trades, result.minute_pnl, held)


def _closed_minute_pnl(trades: pd.DataFrame, minutes: pd.DataFrame) -> pd.Series:
    """Rebuild realized minute PnL after an overlay moved native exits."""
    times = pd.DatetimeIndex(minutes.open_time)
    t_ns = times.as_unit("ns").asi8
    closes = minutes.close.to_numpy(float)
    pnl = np.zeros(len(minutes))
    for trade in trades.itertuples(index=False):
        entry = int(np.searchsorted(t_ns, pd.Timestamp(trade.entry_time).value))
        exit_ = int(np.searchsorted(t_ns, pd.Timestamp(trade.exit_time).value))
        units, side = float(trade.units), int(trade.side)
        if entry == exit_:
            pnl[exit_] += float(trade.gross_bps) - float(trade.fee_bps)
            continue
        pnl[entry] += side * np.log(closes[entry] / float(trade.entry_price)) * 1e4 * units
        pnl[entry] -= float(trade.fee_bps) / 2
        if exit_ > entry + 1:
            pnl[entry + 1:exit_] += side * np.log(closes[entry + 1:exit_] / closes[entry:exit_ - 1]) * 1e4 * units
        pnl[exit_] += side * np.log(float(trade.exit_price) / closes[exit_ - 1]) * 1e4 * units
        pnl[exit_] -= float(trade.fee_bps) / 2
    return pd.Series(pnl, index=times)


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


def run_book(name: str, ctx: Context, funding: pd.DataFrame, book_start: pd.Timestamp, end: pd.Timestamp,
             decisions: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict | None]:
    """(trades, daily, open position) in the paper tables' shape for both funding boundaries. Model-dependent books
    replay only their confirmed decision events (`decisions`), never a re-decided history."""
    spec_id, gated, style = BOOKS[name]
    model = needs_model(name)
    if model:
        table = live_table(raw_table(name, ctx), decisions if decisions is not None else pd.DataFrame())
        table = table.loc[table.decision_time >= book_start].reset_index(drop=True)
    if CATALOG[spec_id].simulator == "grid":
        minutes = ctx.minutes.loc[ctx.minutes.open_time >= book_start].reset_index(drop=True)
        plan = table.loc[table.entry == "grid", ["decision_time", "base", "g"]] if model else None
        result = grid.simulate_grid(replace(ctx, minutes=minutes), book_start, end, gated,
                                    grid.SimConfig(include_funding=False), plan=plan)
    else:
        if model:
            from btcusdt_quant.sim import schema
            from btcusdt_quant.sim.reference import SimConfig
            table = schema.validate(table)
            config = SimConfig(reentry=CATALOG[spec_id].reentry, exit_style=style)
        else:
            table, config = build_variant(ctx, spec_id, gated, style)
            table = table.loc[table.decision_time >= book_start].reset_index(drop=True)
        result = core.simulate(table, ctx.minutes, book_start, end, replace(config, include_funding=False))
    overlay_rule = OVERLAY_RULES.get(name)
    if overlay_rule:
        result = _overlay_result(result, ctx.minutes, overlay_rule)
    legs = result.trades
    fills = (legs[["decision_time", "entry_time", "side", "entry_price"]].drop_duplicates().copy()
             if len(legs) else pd.DataFrame(columns=["decision_time", "entry_time", "side", "entry_price"]))
    trade_rows, daily_rows = [], []
    fees = pd.concat([pd.Series(legs.units.to_numpy() * 2.0, index=legs.entry_time.dt.floor("D")),
                      pd.Series(legs.units.to_numpy() * 2.0, index=legs.exit_time.dt.floor("D"))]).groupby(level=0).sum() \
        if len(legs) else pd.Series(dtype=float)
    closes = ctx.minutes.set_index("open_time").close
    realized = (_closed_minute_pnl(legs, ctx.minutes).reindex(result.minute_pnl.index) if overlay_rule else
                _realized_minute_pnl(result, closes))
    pnl_ex_funding = realized.groupby(realized.index.floor("D")).sum()
    for boundary in ("PESS", "OPT"):
        if len(legs):
            priced = book.reprice(legs[["entry_time", "exit_time", "side", "entry_price", "exit_price"]],
                                  funding, boundary, 0.0)
            leg = legs.assign(funding_bps=priced.funding_bps.to_numpy() * legs.units.to_numpy())
            leg["net_bps"] = leg.gross_bps - leg.fee_bps + leg.funding_bps
            values = dict(decision_time=("decision_time", "first"), exit_time=("exit_time", "max"),
                          entry_price=("entry_price", "first"), exit_price=("exit_price", "last"),
                          gross_bps=("gross_bps", "sum"), cost_bps=("fee_bps", "sum"),
                          funding_bps=("funding_bps", "sum"), net_bps=("net_bps", "sum"),
                          exit_reason=("exit_reason", lambda x: "+".join(x.str.upper())))
            if CATALOG[spec_id].simulator == "grid":
                merged = leg.groupby("position_id", as_index=False).agg(
                    entry_time=("entry_time", "min"), side=("side", "first"), **values)
            else:
                merged = leg.groupby(["entry_time", "side"], as_index=False).agg(**values)
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
    trades.attrs["fills"] = fills
    return trades, pd.concat(daily_rows, ignore_index=True), result.open_position


__all__ = ["BOOKS", "LIVE_IDS", "fill_rows", "label", "live_context", "run_book"]
