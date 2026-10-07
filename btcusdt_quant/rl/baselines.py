"""Comparators for the RL policy (plan 3 Task 7): C17 baseline 2, C14 supervised policy, C15 trade relocation,
C16 shuffled state. Test-window replays go through evaluation.replay_window (C18 boundaries)."""
from __future__ import annotations
import dataclasses, json, math, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd, torch
from ..sim import costs
from ..sim.rolling import END, TRAIN_START, WINDOWS, Window
from ..sim.strategies import CATALOG, Context, build_variant
from . import state
from .evaluation import _minutes, replay_window
from .models import TemporalActorCritic
from .state import StateStore
from .vec_env import replay

HORIZON_MIN = 240           # C14
COST_BPS = 4.0              # nominal round trip (C14 label cost, C15 relocation cost, switch threshold)
CALENDAR = ("dow_sin", "dow_cos", "hour_sin", "hour_cos", "min_to_settlement")   # clock, not exogenous state (C16)
DAY_NS = pd.Timedelta(days=1).value


# ---------------------------------------------------------------- C17 baseline 2
def baseline2_all(paths: list[Path]) -> pd.DataFrame:
    """Per window, the catalog combination (B1-B3 excluded) with the best validation net at 4 bps across all frozen
    windows.parquet files (ties: lowest name, as Plan 2). Validation nets are Plan 2's continuous-run values."""
    w = pd.concat([pd.read_parquet(Path(p) / "windows.parquet") for p in paths], ignore_index=True)
    if w.duplicated(["combo", "window", "part"]).any():
        raise ValueError("a combination appears in two catalog runs")
    val = w[(w.part == "val") & ~w.combo.str.match(r"B[123]__")]
    best = val.sort_values(["window", "net_4bps", "combo"], ascending=[True, False, True]).groupby("window").head(1)
    out = best[["window", "combo", "net_4bps"]].rename(columns={"net_4bps": "val_net_4bps"}).reset_index(drop=True)
    spans = {x.name: (x.test_start, x.test_end) for x in WINDOWS}
    out["test_start"], out["test_end"] = zip(*out.window.map(spans))
    out["n_candidates"] = val.groupby("window").combo.nunique().reindex(out.window).to_numpy()
    return out


def combo_daily(combo: str, windows: list[Window], ctx: Context) -> pd.Series:
    """A catalog combination's test windows replayed with C18 boundaries (used for 1 = K01__NONE__NATIVE and 2)."""
    spec_id, gate, style = combo.split("__")
    if CATALOG[spec_id].simulator != "core":
        raise ValueError(f"{combo}: only core signal tables replay per window")
    table, config = build_variant(ctx, spec_id, gate == "GATED", style)
    return pd.concat([replay_window(table, w, minutes=ctx.minutes, config=config) for w in windows])


# ---------------------------------------------------------------- C15 random baseline
def relocate(lengths: np.ndarray, n: int, reps: int, rng: np.random.Generator) -> np.ndarray:
    """Uniform non-overlapping starts in [0, n) for trades of the given minute lengths (order shuffled per rep):
    k distinct cut points among free + k slots, minus their rank, are uniform gap compositions."""
    k = len(lengths)
    free = n - int(lengths.sum())
    if free < 0:
        raise ValueError("trades do not fit in the window")
    out = np.empty((reps, k), np.int64)
    for r in range(reps):
        order = rng.permutation(k)
        gaps = np.sort(rng.choice(free + k, k, replace=False)) - np.arange(k)
        out[r, order] = gaps + np.cumsum(lengths[order]) - lengths[order]
    return out


def relocation_mc(trades: pd.DataFrame, window: Window, reps: int = 1000, seed: int = 0, minutes=None,
                  detail: bool = False):
    """C15: the window's trades keep count, side and holding minutes and move to uniform random non-overlapping
    starts in the test window. Each trade: market entry at its start minute's open, exit at the open of its exit
    minute (a forced close = the last minute's close), 4 bps, PESS funding as in the action replay. -> net per rep."""
    m = _minutes() if minutes is None else minutes
    m = m[(m.open_time >= window.test_start) & (m.open_time < window.test_end)]
    t = pd.DatetimeIndex(m.open_time).as_unit("ns").asi8
    n = len(t)
    t_ext = np.r_[t, t[-1] + 1]                                   # forced close: funding to the last minute + 1 ns
    price = np.r_[m.open.to_numpy(float), m.close.to_numpy(float)[-1]]
    entry = np.searchsorted(t, pd.DatetimeIndex(trades.entry_time).as_unit("ns").asi8)
    exit_ = np.searchsorted(t, pd.DatetimeIndex(trades.exit_time).as_unit("ns").asi8) \
        + (trades.exit_reason == "data_end").to_numpy()
    lengths, side = (exit_ - entry).astype(np.int64), trades.side.to_numpy(np.int64)
    units = trades.units.to_numpy(float)
    starts = relocate(lengths, n, reps, np.random.default_rng(seed))
    e0, e1 = starts, starts + lengths
    gross = side * np.log(price[e1] / price[e0]) * 1e4
    s_ns, s_rate = costs._settlement_arrays()
    cum = np.r_[0.0, np.cumsum(s_rate)]
    a_ns, b_ns = t_ext[e0], t_ext[e1]
    interior = cum[np.searchsorted(s_ns, b_ns, "left")] - cum[np.searchsorted(s_ns, a_ns, "right")]
    fund = -side * interior * 1e4
    for edge in (a_ns, b_ns):                                     # PESS: a settlement at a fill minute only if paid
        k = np.minimum(np.searchsorted(s_ns, edge, "left"), len(s_ns) - 1)
        cash = -side * s_rate[k] * 1e4
        fund = fund + np.where((s_ns[k] == edge) & (cash < 0), cash, 0.0)
    nets = ((gross - COST_BPS + fund) * units).sum(axis=1)
    return (len(trades), lengths, side, starts, nets) if detail else nets


# ---------------------------------------------------------------- C16 shuffled control
def shuffled_store(store: StateStore, train_end, seed: int) -> StateStore:
    """C16: whole UTC days with TRAIN_START <= T < train_end trade places as blocks (seq, static except the clock
    channels, missing mask); minute prices are not in the store, so the execution path stays real. Rows outside the
    train range (and a partial day) are untouched, so validation, test and the normalizer statistics are unchanged."""
    t = store.times
    rows = np.flatnonzero((t >= TRAIN_START.value) & (t < pd.Timestamp(train_end).value))
    day = t[rows] // DAY_NS
    days, first, count = np.unique(day, return_index=True, return_counts=True)
    whole = count == DAY_NS // (15 * 60 * 10 ** 9)
    blocks = [rows[first[i]:first[i] + count[i]] for i in np.flatnonzero(whole)]
    perm = np.random.default_rng(seed).permutation(len(blocks))
    dst = np.concatenate(blocks) if blocks else np.zeros(0, np.int64)
    src = np.concatenate([blocks[p] for p in perm]) if blocks else dst
    seq, static, missing = store.seq.copy(), store.static.copy(), store.mask_missing.copy()
    cols = np.array([name not in CALENDAR for name in store.feature_names])
    seq[dst], missing[dst] = store.seq[src], store.mask_missing[src]
    static[np.ix_(dst, np.flatnonzero(cols))] = store.static[np.ix_(src, np.flatnonzero(cols))]
    return dataclasses.replace(store, seq=seq, static=static, mask_missing=missing)


# ---------------------------------------------------------------- C14 supervised baseline
def supervised_labels(times: np.ndarray, minutes: pd.DataFrame) -> np.ndarray:
    """[n, 2] net bps of holding long / short from the T+1 open to the T+1+240 open, minus 4 bps (NaN if absent)."""
    t = pd.DatetimeIndex(minutes.open_time).as_unit("ns").asi8
    o = minutes.open.to_numpy(float)

    def open_at(ns):
        k = np.minimum(np.searchsorted(t, ns), len(t) - 1)
        return np.where(t[k] == ns, o[k], np.nan)
    first = np.asarray(times, np.int64) + 60 * 10 ** 9
    r = np.log(open_at(first + HORIZON_MIN * 60 * 10 ** 9) / open_at(first)) * 1e4
    return np.column_stack([r - COST_BPS, -r - COST_BPS])


def supervised_policy(pred: np.ndarray, missing: np.ndarray) -> np.ndarray:
    """Values flat 0, long pred[:,0], short pred[:,1]; move to the best allowed side only if it beats the current
    side's value by >= 4 bps. C7: with the detector missing only flat or hold are allowed."""
    out, cur = np.zeros(len(pred), np.int64), 0
    for i, (vl, vs) in enumerate(pred):
        value = {0: 0.0, 1: vl, -1: vs}
        allowed = (0, cur) if missing[i] else (0, 1, -1)
        best = max(allowed, key=lambda s: (value[s], s == cur))
        if value[best] - value[cur] >= COST_BPS:
            cur = best
        out[i] = cur
    return out


def _predict(model, store: StateStore, rows: np.ndarray, device) -> np.ndarray:
    with torch.inference_mode():
        out = [model(torch.as_tensor(store.seq[c], device=device), torch.as_tensor(store.static[c], device=device),
                     torch.ones(len(c), 3, dtype=torch.bool, device=device))[0][:, 1:].cpu().numpy()
               for c in np.array_split(rows, max(1, len(rows) // 8192))] if len(rows) else [np.zeros((0, 2))]
    return np.concatenate(out) * 100.0                             # trained in percent


def supervised_actions(model, store: StateStore, start, end, device="cpu") -> pd.Series:
    rows = np.flatnonzero((store.times >= pd.Timestamp(start).value) & (store.times < pd.Timestamp(end).value))
    sides = supervised_policy(_predict(model, store, rows, device), store.mask_missing[rows])
    return pd.Series(sides, index=pd.DatetimeIndex(store.times[rows], tz="UTC"))


def load_supervised(path) -> TemporalActorCritic:
    ck = torch.load(path, map_location="cpu", weights_only=False)
    model = TemporalActorCritic(**ck["model_args"])
    model.load_state_dict(ck["model"])
    return model.eval()


def fit_supervised(store: StateStore, minutes: pd.DataFrame, window: Window, out, seed: int = 0, device="cpu",
                   max_samples: int = 5_000_000, eval_every: int = 80, minibatch: int = 4096, patience: int = 5,
                   lr: float = 3e-4) -> dict:
    """C14 on a normalized store: conv encoder, MSE on the long / short values (outputs 1 and 2 of the actor head;
    in percent, as the PPO learner), AdamW wd 1e-4. Train rows TRAIN_START <= T <= train_end and T < val_start - 240
    min (purge). C12: every eval_every minibatches (80 x 4096 = 327,680 samples) the nominal validation net; best.pt
    keeps the best; stop after `patience` evaluations without improvement or at max_samples."""
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(seed)
    y_all = supervised_labels(store.times, minutes)
    t = store.times
    rows = np.flatnonzero((t >= TRAIN_START.value) & (t <= pd.Timestamp(window.train_end).value)
                          & (t < (window.val_start - pd.Timedelta(minutes=HORIZON_MIN)).value)
                          & np.isfinite(y_all).all(1))
    if not len(rows):
        raise ValueError(f"{window.name}: no supervised train rows")
    seq = torch.as_tensor(store.seq[rows], device=device)
    static = torch.as_tensor(store.static[rows], device=device)
    y = torch.as_tensor(y_all[rows] / 100.0, dtype=torch.float32, device=device)
    model = TemporalActorCritic(store.seq.shape[2], store.static.shape[1], "conv").to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    mask = torch.ones(min(minibatch, len(rows)), 3, dtype=torch.bool, device=device)

    def val_net() -> float:
        acts = supervised_actions(model, store, window.val_start, window.val_end, device)
        net = float(np.sum(replay(acts, minutes, window.val_start, window.val_end, COST_BPS, 1, 0.0).minute_pnl))
        if not math.isfinite(net):
            raise RuntimeError(f"non-finite validation value {net}")
        return net

    mb, samples, updates, best, bad, trace = len(mask), 0, 0, -math.inf, 0, []
    while samples < max_samples and bad < patience:
        perm = torch.randperm(len(rows), device=device)
        for i in range(0, len(rows) - mb + 1, mb):
            idx = perm[i:i + mb]
            pred = model(seq[idx], static[idx], mask)[0][:, 1:]
            loss = torch.nn.functional.mse_loss(pred, y[idx])
            opt.zero_grad(); loss.backward(); opt.step()
            samples += mb; updates += 1
            if updates % eval_every == 0 or samples >= max_samples:
                model.eval(); v = val_net(); model.train()
                trace.append({"update": updates, "samples": samples, "val_net_bps": v})
                if v > best:
                    best, bad = v, 0
                    torch.save({"model": model.state_dict(), "model_args": model.model_args, "update": updates,
                                "val": v}, out / "best.pt")
                else:
                    bad += 1
            if samples >= max_samples or bad >= patience:
                break
    return {"window": window.name, "seed": seed, "val_net_bps": best, "train_rows": int(len(rows)),
            "samples": samples, "checkpoint": str(out / "best.pt"), "selection_trace": trace}


def train_supervised(window: Window, out, variant: str = "S1", seed: int = 0) -> dict:
    """C14 for one rolling window on the cached full state store (normalizer fit on the train rows, C9)."""
    t0, out = time.time(), Path(out)
    ctx = Context.load(end=END)
    full = state.cached_state_store(ctx, TRAIN_START, END, variant)
    store = state.fit_normalizer(full, window.train_end).apply(full)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    res = fit_supervised(store, ctx.minutes, window, out, seed=seed, device=device)
    res.update(variant=variant, wall_seconds=time.time() - t0)
    manifest = {**res, "source": "Binance USD-M BTCUSDT futures, local data (sim.strategies.Context)",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(), "data_cutoff": "2026-01-01",
                "baseline": "C14 supervised", "input_hashes": state._input_hash(ctx),
                "split": {"train": [str(TRAIN_START), str(window.train_end)],
                          "validation": [str(window.val_start), str(window.val_end)]}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8")
    return res
