"""Fixed regime/event/payoff redesign; exploratory, never a live approval."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from .short_direction import (
    SHORT_ORIENTED_WITH_MAGNITUDE_FEATURE_NAMES, add_short_horizon_funding_features,
    add_short_oriented_features, add_signed_direction_features,
)
from .short_fast_regime import add_fast_regime_features
from .short_sequence import COST, _status, _write_json, build_features, walk_forward_folds
from .short_target_diagnostic import _fit_regressor


RUN_ROOT = Path("artifacts/short_regime_payoff_20260907")
POLICIES = {"trend_pullback": 60, "range_rejection": 15}
BASE_FEATURES = tuple(SHORT_ORIENTED_WITH_MAGNITUDE_FEATURE_NAMES)
STATE_FEATURES = ("ema_gap_15m", "return_24h", "efficiency_60", "close_zscore_60", "rv_60")
MODEL_FEATURES = (*BASE_FEATURES, *STATE_FEATURES, "sigma_h", "policy_code")
SCORE_FLOOR_BPS = 2.0
ARMS = ("rules_only", "calibrated_score", "validated_score")


def add_policy_state(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    # The shared historical helper's hourly shift(23) spans 23 hours.
    # This redesign explicitly uses 1,440 completed one-minute intervals.
    frame["return_24h"] = frame.close.pct_change(1440)
    travel = frame.close.diff().abs().rolling(60, min_periods=60).sum()
    frame["efficiency_60"] = frame.close.diff(60).abs() / travel.where(travel > 0)
    return frame


def fit_policy_thresholds(frame: pd.DataFrame) -> dict[str, float]:
    finite = frame[list(STATE_FEATURES)].replace([np.inf, -np.inf], np.nan).dropna()
    if finite.empty:
        raise ValueError("no finite training regime observations")
    return {"abs_ema_median": float(finite.ema_gap_15m.abs().median()),
            "efficiency_q33": float(finite.efficiency_60.quantile(1 / 3)),
            "efficiency_q67": float(finite.efficiency_60.quantile(2 / 3)),
            "rv60_q99": float(finite.rv_60.quantile(0.99))}


def eligible_events(events: pd.DataFrame, thresholds: dict[str, float]) -> np.ndarray:
    strong = events.ema_gap_15m.abs() > thresholds["abs_ema_median"]
    veto = strong & (((events.ema_gap_15m > 0) & (events.return_24h > 0))
                     | (events.ema_gap_15m * events.return_24h < 0))
    trend = ((events.policy == "trend_pullback") & (events.ema_gap_15m < -thresholds["abs_ema_median"])
             & (events.return_24h < 0) & (events.efficiency_60 >= thresholds["efficiency_q67"]))
    ranging = ((events.policy == "range_rejection") & ~strong
               & (events.efficiency_60 <= thresholds["efficiency_q33"]))
    return ((trend | ranging) & ~veto & (events.rv_60 <= thresholds["rv60_q99"])
            & (events.sigma_h >= 3 * COST)).to_numpy(bool)


def policy_payoffs(frame: pd.DataFrame, indices: np.ndarray, horizon: int, sigma: np.ndarray) -> pd.DataFrame:
    """Next-open price proxy, frozen barriers, adverse-first intrabar ambiguity."""
    indices, sigma = np.asarray(indices, dtype=np.int64), np.asarray(sigma, dtype=float)
    if horizon < 1 or sigma.shape != indices.shape:
        raise ValueError("positive horizon and one volatility per entry required")
    if len(indices) and (indices.min() < 0 or indices.max() + horizon >= len(frame)):
        raise ValueError("incomplete forward price window")
    if not np.isfinite(sigma).all() or (sigma <= 0).any() or (1.5 * sigma >= 1).any():
        raise ValueError("volatility must imply finite positive barrier prices")
    opens, highs, lows, closes = (frame[name].to_numpy(float) for name in ("open", "high", "low", "close"))
    future = indices[:, None] + np.arange(1, horizon + 1)
    entry = opens[indices + 1]
    if not np.isfinite(entry).all() or (entry <= 0).any():
        raise ValueError("entry prices must be finite and positive")
    if any(not np.isfinite(values[future]).all() or (values[future] <= 0).any()
           for values in (opens, highs, lows, closes)):
        raise ValueError("forward prices must be finite and positive")
    if ((highs[future] < np.maximum(opens[future], closes[future]))
            | (lows[future] > np.minimum(opens[future], closes[future]))).any():
        raise ValueError("forward candle range must contain its open and close")
    tp, sl = entry * (1 - 1.5 * sigma), entry * (1 + sigma)
    hit_tp, hit_sl = lows[future] <= tp[:, None], highs[future] >= sl[:, None]
    hit = hit_tp | hit_sl
    touched = hit.any(axis=1)
    first = hit.argmax(axis=1)
    row = np.arange(len(indices))
    stopped = touched & hit_sl[row, first]
    reason = np.where(touched, np.where(stopped, "SL", "TP"), "TIMEOUT")
    exit_index = indices + np.where(touched, first + 1, horizon)
    exit_price = np.where(touched, np.where(stopped, np.maximum(sl, opens[exit_index]), tp), closes[exit_index])
    gross = (1 - exit_price / entry) * 1e4
    return pd.DataFrame({
        "signal_index": indices, "entry_index": indices + 1, "exit_index": exit_index,
        "open_time": frame.iloc[indices].open_time.to_numpy(),
        "exit_time": (frame.iloc[exit_index].open_time + pd.Timedelta(minutes=1)).to_numpy(),
        "horizon": horizon, "sigma_h": sigma, "tp_bps": 1.5 * sigma * 1e4,
        "sl_bps": sigma * 1e4, "entry_price": entry, "exit_price": exit_price,
        "exit_reason": reason, "gross_bps": gross, "net_bps": gross - COST * 1e4,
    })


def build_events(frame: pd.DataFrame) -> pd.DataFrame:
    finite = np.isfinite(frame[[*BASE_FEATURES, *STATE_FEATURES]]).all(axis=1).to_numpy()
    rejection = frame.close < frame.low.shift(1)
    triggers = {"trend_pullback": rejection & (frame.short_return_5.shift(1) < 0),
                "range_rejection": rejection & (frame.close_zscore_60.shift(1) >= 1)}
    parts = []
    for code, (policy, horizon) in enumerate(POLICIES.items()):
        sigma = frame.rv_60.to_numpy(float) * np.sqrt(horizon)
        valid = finite & triggers[policy].to_numpy(bool) & (sigma > 0) & (1.5 * sigma < 1)
        valid &= np.arange(len(frame)) + horizon < len(frame)
        indices = np.flatnonzero(valid)
        labels = policy_payoffs(frame, indices, horizon, sigma[indices])
        inputs = frame.iloc[indices][[*BASE_FEATURES, *STATE_FEATURES]].reset_index(drop=True)
        part = pd.concat([labels, inputs], axis=1)
        part["policy"], part["policy_code"] = policy, code
        parts.append(part)
    return pd.concat(parts, ignore_index=True).sort_values("signal_index").reset_index(drop=True)


def nonoverlap(rows: pd.DataFrame) -> pd.DataFrame:
    """Signal on an exit bar may enter next open; no concurrent positions."""
    rows = rows.sort_values("signal_index")
    chosen, available = [], -1
    for position, (signal, end) in enumerate(zip(rows.signal_index, rows.exit_index)):
        if signal >= available:
            chosen.append(position)
            available = int(end)
    return rows.iloc[chosen].copy()


def trade_summary(rows: pd.DataFrame) -> dict[str, object]:
    if rows.empty:
        return {"trades": 0, "mean_net_bps": None, "mean_gross_bps": None, "mean_net_ci95": None,
                "positive_years": 0, "by_year": {}, "by_policy": {}}
    net = rows.net_bps.to_numpy(float)
    mean = float(net.mean())
    days = pd.to_datetime(rows.open_time, utc=True).dt.floor("D")
    daily = pd.DataFrame({"day": days.to_numpy(), "net": net}).groupby("day").net.agg(["sum", "count"])
    groups = len(daily)
    interval = None
    if groups > 1:
        se = np.sqrt(groups / (groups - 1) * np.square(daily["sum"] - daily["count"] * mean).sum()) / len(net)
        width = float(student_t.ppf(0.975, groups - 1) * se)
        interval = [mean - width, mean + width]
    loss = -net[net < 0].sum()
    yearly = {}
    for year, subset in rows.groupby(pd.to_datetime(rows.open_time, utc=True).dt.year):
        yearly[str(year)] = {"trades": len(subset), "mean_gross_bps": float(subset.gross_bps.mean()),
                            "mean_net_bps": float(subset.net_bps.mean())}
    equity = np.cumsum(net)
    return {
        "trades": len(net), "mean_net_bps": mean, "mean_gross_bps": float(rows.gross_bps.mean()),
        "mean_net_ci95": interval, "cluster_trade_days": groups,
        "profit_factor": float(net[net > 0].sum() / loss) if loss > 0 else None,
        "net_win_rate": float((net > 0).mean()),
        "sum_net_bps": float(net.sum()),
        "max_drawdown_bps_fixed_notional": float((equity - np.maximum.accumulate(np.r_[0, equity])[1:]).min()),
        "mean_holding_minutes": float((rows.exit_index - rows.entry_index + 1).mean()),
        "exit_counts": {str(k): int(v) for k, v in rows.exit_reason.value_counts().items()},
        "cost_stress_mean_net_bps": {str(c): float(rows.gross_bps.mean() - c) for c in (4, 6, 8)},
        "positive_years": sum(v["mean_net_bps"] > 0 for v in yearly.values()), "by_year": yearly,
        "by_policy": {str(k): {"trades": len(v), "mean_net_bps": float(v.net_bps.mean())}
                      for k, v in rows.groupby("policy")},
    }


def period(rows: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    # Eligibility at the boundary uses the known maximum holding, never a future early exit.
    complete = rows.open_time + pd.to_timedelta(rows.horizon + 1, unit="min") <= end
    return rows.loc[(rows.open_time >= start) & (rows.open_time < end) & complete].copy()


def run_experiment(input_path: Path, metrics_dir: Path, funding_dir: Path, premium_dir: Path,
                   output: Path = RUN_ROOT) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite regime-payoff directory: {output}")
    output.mkdir(parents=True)
    try:
        _status(output, "running", "features", "building fixed regime/event/payoff inputs")
        frame = build_features(input_path, metrics_dir, funding_dir, premium_dir)
        frame = frame.loc[frame.open_time < pd.Timestamp("2026-01-01", tz="UTC")].reset_index(drop=True)
        frame = add_policy_state(add_short_oriented_features(add_short_horizon_funding_features(
            add_signed_direction_features(add_fast_regime_features(frame)))))
        events = build_events(frame)
        events.to_parquet(output / "candidate_events.parquet", index=False)
        reports, scores, trades = [], [], {arm: [] for arm in ARMS}
        for fold in walk_forward_folds(purge_bars=max(POLICIES.values())):
            _status(output, "running", "folds", f"evaluating fixed design fold {fold.index + 1}/19")
            calibration_start = fold.train_end - pd.Timedelta(days=90)
            fit_rows = frame.loc[(frame.open_time >= fold.train_start) & (frame.open_time < calibration_start)]
            thresholds = fit_policy_thresholds(fit_rows)
            eligible = events.loc[eligible_events(events, thresholds)]
            train = period(eligible, fold.train_start, calibration_start)
            calibration = period(eligible, calibration_start, fold.train_end)
            validation = period(eligible, fold.validation_start, fold.validation_end)
            test = period(eligible, fold.test_start, fold.test_end)
            audit = {"fold": fold.index, "train_start": str(fold.train_start),
                     "calibration_start": str(calibration_start), "train_end": str(fold.train_end),
                     "validation_start": str(fold.validation_start), "validation_end": str(fold.validation_end),
                     "test_start": str(fold.test_start), "test_end": str(fold.test_end),
                     "thresholds_from_model_train_only": thresholds,
                     "event_counts": {"train": len(train), "calibration": len(calibration),
                                      "validation": len(validation), "test": len(test)}}
            if len(train) < 2:
                audit["state"] = "no_training_sample"
                reports.append(audit)
                trades["rules_only"].append(nonoverlap(test))
                continue
            model = _fit_regressor(train[list(MODEL_FEATURES)].to_numpy(np.float32), train.net_bps.to_numpy(float))
            model.booster_.save_model(str(output / f"fold_{fold.index}_model.txt"))
            for rows in (calibration, validation, test):
                rows["raw_prediction_bps"] = (model.booster_.predict(rows[list(MODEL_FEATURES)].to_numpy(np.float32))
                                              if len(rows) else np.array([], dtype=float))
            calibration_trades = nonoverlap(calibration)
            offsets = {str(k): float((v.net_bps - v.raw_prediction_bps).mean())
                       for k, v in calibration_trades.groupby("policy")}
            for rows in (validation, test):
                rows["predicted_net_bps"] = rows.raw_prediction_bps + rows.policy.map(offsets)
            validation_trades = nonoverlap(validation.loc[validation.predicted_net_bps >= SCORE_FLOOR_BPS])
            gates = {}
            for policy in POLICIES:
                metrics = trade_summary(validation_trades.loc[validation_trades.policy == policy])
                ci = metrics["mean_net_ci95"]
                gates[policy] = {"allowed": ci is not None and ci[0] > 0, "validation": metrics}
            test["validation_allowed"] = test.policy.map({p: g["allowed"] for p, g in gates.items()})
            test["fold"] = fold.index
            scores.append(test)
            for arm in ARMS:
                allowed = np.ones(len(test), dtype=bool)
                if arm != "rules_only":
                    allowed &= (test.predicted_net_bps >= SCORE_FLOOR_BPS).to_numpy(bool)
                if arm == "validated_score":
                    allowed &= test.validation_allowed.to_numpy(bool)
                trades[arm].append(nonoverlap(test.loc[allowed]))
            audit.update(state="complete", calibration_offsets_bps=offsets, validation_gates=gates,
                         calibration_nonoverlap_counts=calibration_trades.policy.value_counts().to_dict())
            reports.append(audit)
            _write_json(output / "folds.json", reports)
            print(f"fold {fold.index + 1}/19: train={len(train)}, test={len(test)}, "
                  f"allowed={[p for p, g in gates.items() if g['allowed']]}", flush=True)
        summaries = {}
        for arm, chunks in trades.items():
            selected = pd.concat(chunks, ignore_index=True) if chunks else events.iloc[:0]
            selected.to_parquet(output / f"{arm}_trades.parquet", index=False)
            summaries[arm] = trade_summary(selected)
        if scores:
            pd.concat(scores, ignore_index=True).to_parquet(output / "oof_scores.parquet", index=False)
        primary = summaries["validated_score"]
        ci = primary["mean_net_ci95"]
        result = {
            "designation": "posthoc_regime_event_payoff_redesign_v1", "live_approval_eligible": False,
            "primary_arm": "validated_score", "cost_bps": COST * 1e4,
            "model_family": "lightgbm_l2_fixed", "feature_names": list(MODEL_FEATURES),
            "policy_horizons": POLICIES, "score_floor_net_bps": SCORE_FLOOR_BPS,
            "selection": "fixed score >= 2 net bps and validation day-cluster CI lower > 0",
            "folds": reports, "arms": summaries,
            "research_candidate": bool(ci is not None and ci[0] > 0 and primary["positive_years"] >= 3),
            "limitations": ["Reused 2020-2025 history; exploratory, no fresh OOS claim.",
                            "Next-open/first-touch OHLC proxy under fixed 4bps maker-fee premise; not a post-only execution replay.",
                            "No actual funding cash flows or account fill data.",
                            "Day-cluster intervals do not correct for repeated historical research selection.",
                            "Rule and calibrated-score arms are diagnostics, not posthoc replacements for the primary policy."],
        }
        _write_json(output / "regime_payoff_results.json", result)
        _status(output, "complete", "complete", "fixed regime payoff redesign evaluated")
        return result
    except BaseException as error:
        _status(output, "failed", "failed", str(error))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("artifacts/btcusdt_2020_2026h1.parquet"))
    parser.add_argument("--metrics-dir", type=Path, default=Path("artifacts/metrics"))
    parser.add_argument("--funding-dir", type=Path, default=Path("artifacts/funding_2020_2026h1"))
    parser.add_argument("--premium-index-dir", type=Path, default=Path("artifacts/premium_index_2020_2026h1"))
    parser.add_argument("--output", type=Path, default=RUN_ROOT)
    args = parser.parse_args()
    run_experiment(args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir, args.output)


if __name__ == "__main__":
    main()
