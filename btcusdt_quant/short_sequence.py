"""Pre-registered short-signal model experiments."""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from . import funding_source, metrics_source, models, premium_index_source
from .backtest import RollingQuantileThreshold
from .gru import GRUAdapter, GRU_FEATURE_NAMES, SEQUENCE_LENGTH


RUN_ROOT = Path("artifacts/short_sequence_experiment_20260826")
LIGHTGBM_RUN_ROOT = Path("artifacts/short_sequence_lightgbm_experiment_20260827")
LIGHTGBM_TUNED_RUN_ROOT = Path("artifacts/short_sequence_lightgbm_tuned_experiment_20260827")
HORIZON, TP_PCT, SL_PCT, COST = 45, 0.006, 0.012, 0.0004
VOL_GATE = 0.0020254026


def _utc_ns(values: object) -> pd.Series:
    return pd.Series(pd.to_datetime(values, utc=True)).astype("datetime64[ns, UTC]")


@dataclass(frozen=True)
class Fold:
    index: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str, allow_nan=False), encoding="utf-8")


def _status(root: Path, state: str, stage: str, message: str, **extra: object) -> None:
    previous: dict[str, object] = {}
    path = root / "status.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8-sig"))
    stages = dict(previous.get("stages", {}))
    stages[stage] = {"state": state, "message": message, "updated_at": datetime.now(timezone.utc).isoformat()}
    _write_json(path, {
        "state": state, "stage": stage, "message": message, "stages": stages,
        "started_at": previous.get("started_at", datetime.now(timezone.utc).isoformat()),
        "updated_at": datetime.now(timezone.utc).isoformat(), **extra,
    })
    with (root / "experiment.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now(timezone.utc).isoformat()} {state} {stage}: {message}\n")


def walk_forward_folds(
    start: str = "2020-01-01", end: str = "2026-01-01", purge_bars: int = HORIZON,
) -> list[Fold]:
    cursor, stop, folds = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC"), []
    while True:
        train_end = cursor + pd.Timedelta(days=365)
        validation_start = train_end + pd.Timedelta(minutes=purge_bars)
        validation_end = validation_start + pd.Timedelta(days=30)
        test_start = validation_end + pd.Timedelta(minutes=purge_bars)
        test_end = test_start + pd.Timedelta(days=90)
        if test_end > stop:
            break
        folds.append(Fold(len(folds), cursor, train_end, validation_start, validation_end, test_start, test_end))
        cursor += pd.Timedelta(days=90)
    return folds


def _ratio_to_mean(values: pd.Series, window: int) -> pd.Series:
    mean = values.rolling(window, min_periods=window).mean()
    return values / mean.where(mean != 0.0) - 1.0


def _zscore(values: pd.Series, window: int) -> pd.Series:
    mean = values.rolling(window, min_periods=window).mean()
    std = values.rolling(window, min_periods=window).std(ddof=0)
    return ((values - mean) / std.where(std != 0.0)).fillna(0.0)


def build_features(
    input_path: Path,
    metrics_dir: Path,
    funding_dir: Path,
    premium_dir: Path,
) -> pd.DataFrame:
    """Build only the 28 registered inputs from source artifacts; no feature cache."""
    frame = pd.read_parquet(input_path).sort_values("open_time").reset_index(drop=True)
    required = {"open_time", "open", "high", "low", "close", "volume", "quote_volume",
                "number_of_trades", "taker_buy_base_volume", "taker_buy_quote_volume"}
    if missing := required - set(frame):
        raise ValueError(f"source candles missing columns: {sorted(missing)}")
    frame["open_time"] = _utc_ns(frame["open_time"])
    if frame["open_time"].duplicated().any() or not frame["open_time"].is_monotonic_increasing:
        raise ValueError("source candle times must be unique and increasing")
    if len(frame) > 1 and (frame["open_time"].diff().iloc[1:] != pd.Timedelta(minutes=1)).any():
        raise ValueError("source candle timeline contains gaps; canonicalize raw data before this experiment")

    close, high, low, op = frame["close"], frame["high"], frame["low"], frame["open"]
    one = close.pct_change()
    for period in (1, 3, 5):
        frame[f"return_{period}"] = close.pct_change(period).fillna(0.0)
    frame["log_return_1"] = np.log(close / close.shift(1)).fillna(0.0)
    frame["high_low_range"] = (high - low) / close
    frame["body_pct"] = (close - op).abs() / close
    frame["upper_shadow"] = (high - pd.concat([op, close], axis=1).max(axis=1)).clip(lower=0.0) / close
    frame["lower_shadow"] = (pd.concat([op, close], axis=1).min(axis=1) - low).clip(lower=0.0) / close
    raw_range = high - low
    frame["close_location_value"] = (((close - low) - (high - close)) / raw_range.where(raw_range != 0.0)).fillna(0.0)
    frame["volume_sma_20_ratio"] = _ratio_to_mean(frame["volume"], 20).fillna(0.0)
    frame["volume_zscore_20"] = _zscore(frame["volume"], 20)
    frame["quote_volume_sma_20_ratio"] = _ratio_to_mean(frame["quote_volume"], 20).fillna(0.0)
    frame["taker_ratio"] = (frame["taker_buy_base_volume"] / frame["volume"].where(frame["volume"] != 0.0)).fillna(0.0)
    frame["taker_imbalance"] = ((2.0 * frame["taker_buy_base_volume"] - frame["volume"]) / frame["volume"].where(frame["volume"] != 0.0)).fillna(0.0)
    frame["taker_quote_ratio"] = (frame["taker_buy_quote_volume"] / frame["quote_volume"].where(frame["quote_volume"] != 0.0)).fillna(0.0)
    trades = frame["number_of_trades"].astype(float)
    frame["trade_count_ratio"] = _ratio_to_mean(trades, 20).fillna(0.0)
    frame["trade_count_zscore_20"] = _zscore(trades, 20)
    for window in (5, 15, 30, 60):
        frame[f"rv_{window}"] = one.fillna(0.0).rolling(window, min_periods=window).std(ddof=0).fillna(0.0)
    previous_close = close.shift(1).fillna(close)
    true_range = pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    frame["atr_pct"] = (true_range.rolling(14, min_periods=14).mean() / close).fillna(0.0)

    funding = funding_source.load_funding_dir(funding_dir)
    funding_frame = pd.DataFrame({"open_time": [row.funding_time for row in funding], "funding_rate": [row.funding_rate for row in funding]})
    premium = premium_index_source.load_premium_index_dir(premium_dir)
    premium_frame = pd.DataFrame({
        "open_time": [row.close_time for row in premium],
        "premium_observed_time": [row.close_time for row in premium],
        "premium_index": [row.close for row in premium],
    })
    metric_rows = metrics_source.load_metrics_dir(metrics_dir)
    # The archive omitted taker-LS during early 2022. Rebuild exactly the
    # documented five completed 1m bars, while archive values always win.
    buy = frame["taker_buy_base_volume"].rolling(5, min_periods=5).sum().shift(1)
    sell = (frame["volume"] - frame["taker_buy_base_volume"]).rolling(5, min_periods=5).sum().shift(1)
    reconstructed = pd.Series((buy / sell.where(sell > 0.0)).to_numpy(), index=frame["open_time"])
    repaired_rows = []
    for row in metric_rows:
        values = dict(row.values)
        if ("sum_taker_long_short_vol_ratio" not in values
                and metrics_source.TAKER_RECONSTRUCTION_START <= row.create_time < metrics_source.TAKER_RECONSTRUCTION_END):
            value = reconstructed.get(row.create_time)
            if value is not None and math.isfinite(float(value)):
                values["sum_taker_long_short_vol_ratio"] = float(value)
        repaired_rows.append(metrics_source.MetricsRow(row.create_time, values))
    metric_values = metrics_source.compute_metrics_features(repaired_rows)
    metrics_frame = pd.DataFrame([{"open_time": at, **values} for at, values in metric_values.items()])
    for source_frame in (funding_frame, premium_frame, metrics_frame):
        source_frame["open_time"] = _utc_ns(source_frame["open_time"])
    premium_frame["premium_observed_time"] = _utc_ns(premium_frame["premium_observed_time"])
    frame = pd.merge_asof(frame, funding_frame.sort_values("open_time"), on="open_time", direction="backward")
    frame = pd.merge_asof(frame, premium_frame.sort_values("open_time"), on="open_time", direction="backward")
    frame["premium_stale_minutes"] = (
        (frame["open_time"] - frame["premium_observed_time"]).dt.total_seconds() / 60.0
    )
    frame = pd.merge_asof(
        frame, metrics_frame.sort_values("open_time"), on="open_time", direction="backward",
        tolerance=pd.Timedelta(minutes=40),
    )
    return frame


def independent_short_labels(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized, independently implemented 45-bar short label and payoff."""
    close = frame["close"].to_numpy(float)
    op, high, low = (frame[name].to_numpy(float) for name in ("open", "high", "low"))
    n = len(frame)
    labels = np.zeros(n, dtype=np.int8)
    payoff = np.full(n, np.nan, dtype=np.float64)
    reasons = np.full(n, "unlabeled", dtype=object)
    unresolved = np.arange(n) + HORIZON < n
    future = np.full(n, np.nan)
    future[:-HORIZON] = close[HORIZON:]
    timeout_payoff = -(future - close) / close
    for step in range(1, HORIZON + 1):
        valid = np.arange(n) + step < n
        future_high = np.full(n, np.nan); future_high[valid] = high[step:]
        future_low = np.full(n, np.nan); future_low[valid] = low[step:]
        future_open = np.full(n, np.nan); future_open[valid] = op[step:]
        future_close = np.full(n, np.nan); future_close[valid] = close[step:]
        tp = future_low <= close * (1.0 - TP_PCT)
        sl = future_high >= close * (1.0 + SL_PCT)
        hit = unresolved & (tp | sl)
        tp_first = hit & tp & (~sl | (future_close < future_open))
        sl_first = hit & ~tp_first
        labels[tp_first], payoff[tp_first], reasons[tp_first] = 1, TP_PCT, "short_tp_first"
        labels[sl_first], payoff[sl_first], reasons[sl_first] = 0, -SL_PCT, "short_sl_first"
        unresolved[hit] = False
    timeout = unresolved & np.isfinite(timeout_payoff)
    labels[timeout] = timeout_payoff[timeout] > COST
    payoff[timeout], reasons[timeout] = timeout_payoff[timeout], "short_timeout_return"
    return labels, payoff, reasons


def audit_labels(frame: pd.DataFrame, labels: np.ndarray, reasons: np.ndarray) -> dict[str, object]:
    """Compare every valid row with a separate scalar barrier implementation."""
    close = frame["close"].to_numpy(float); op = frame["open"].to_numpy(float)
    high = frame["high"].to_numpy(float); low = frame["low"].to_numpy(float)
    mismatches = 0
    for index in range(len(frame) - HORIZON):
        expected, expected_reason = None, None
        for future in range(index + 1, index + HORIZON + 1):
            tp = low[future] <= close[index] * (1.0 - TP_PCT)
            sl = high[future] >= close[index] * (1.0 + SL_PCT)
            if tp or sl:
                expected = int(tp and (not sl or close[future] < op[future]))
                expected_reason = "short_tp_first" if expected else "short_sl_first"
                break
        if expected is None:
            expected = int(-(close[index + HORIZON] - close[index]) / close[index] > COST)
            expected_reason = "short_timeout_return"
        mismatches += int(expected != labels[index] or expected_reason != reasons[index])
    return {"rows_checked": max(0, len(frame) - HORIZON), "mismatches": mismatches, "passed": mismatches == 0}


def _average_precision(labels: np.ndarray, probabilities: np.ndarray) -> float:
    positives = int(labels.sum())
    if positives == 0:
        return 0.0
    order = np.argsort(-probabilities, kind="stable")
    ordered = labels[order]
    return float((np.cumsum(ordered)[ordered == 1] / (np.flatnonzero(ordered == 1) + 1)).sum() / positives)


def _calibration(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    brier = float(np.mean((probabilities - labels) ** 2))
    bins = np.minimum((probabilities * 10).astype(int), 9)
    ece = sum(np.sum(bins == index) / len(labels) * abs(probabilities[bins == index].mean() - labels[bins == index].mean())
              for index in range(10) if np.any(bins == index))
    return {"brier": brier, "ece": float(ece), "pr_auc": _average_precision(labels, probabilities), "base_rate": float(labels.mean())}


def _trade_metrics(
    times: Sequence[pd.Timestamp], probabilities: np.ndarray, payoffs: np.ndarray, threshold: float,
    eligible: np.ndarray | None = None, holding_minutes: int = HORIZON,
) -> dict[str, object]:
    allowed = np.ones(len(probabilities), dtype=bool) if eligible is None else np.asarray(eligible, dtype=bool)
    selected, next_time = [], None
    for index, when in enumerate(times):
        if allowed[index] and probabilities[index] >= threshold and (next_time is None or when >= next_time):
            selected.append(index)
            next_time = when + pd.Timedelta(minutes=holding_minutes)
    net = payoffs[selected] - COST if selected else np.asarray([], dtype=float)
    by_year: dict[str, dict[str, float]] = {}
    for year in range(2021, 2026):
        values = net[[times[index].year == year for index in selected]] if selected else np.asarray([])
        by_year[str(year)] = {"trades": int(len(values)), "mean_net_bps": float(values.mean() * 1e4) if len(values) else 0.0,
                              "net_return": float(values.sum())}
    by_month: dict[str, dict[str, float]] = {}
    for month in sorted({when.strftime("%Y-%m") for when in times}):
        values = net[[times[index].strftime("%Y-%m") == month for index in selected]] if selected else np.asarray([])
        by_month[month] = {"trades": int(len(values)), "mean_net_bps": float(values.mean() * 1e4) if len(values) else 0.0,
                           "net_return": float(values.sum())}
    return {
        "threshold": float(threshold), "trades": len(selected),
        "mean_net_bps": float(net.mean() * 1e4) if len(net) else 0.0,
        "net_return": float(net.sum()), "positive_years": sum(value["net_return"] > 0.0 for value in by_year.values()),
        "by_year": by_year, "by_month": by_month, "selected_indices": selected,
    }


def _feature_ic(frame: pd.DataFrame, payoffs: np.ndarray) -> dict[str, object]:
    report, qualified = {}, []
    for feature in GRU_FEATURE_NAMES:
        yearly = {}
        for year in range(2021, 2026):
            mask = (frame["open_time"].dt.year.to_numpy() == year) & np.isfinite(frame[feature]) & np.isfinite(payoffs)
            value = float(spearmanr(frame.loc[mask, feature], payoffs[mask]).statistic) if mask.sum() > 2 else 0.0
            yearly[str(year)] = 0.0 if not math.isfinite(value) else value
        positive = sum(value >= 0.01 for value in yearly.values())
        negative = sum(value <= -0.01 for value in yearly.values())
        stable = max(positive, negative)
        report[feature] = {"by_year": yearly, "qualifying_years": stable}
        if stable >= 4:
            qualified.append(feature)
    return {"features": report, "qualified_features": qualified, "qualified_count": len(qualified)}


def _indices(times: pd.Series, start: pd.Timestamp, end: pd.Timestamp, sequence_valid: np.ndarray | None = None) -> np.ndarray:
    mask = (times >= start) & (times < end)
    if sequence_valid is not None:
        mask &= sequence_valid
    return np.flatnonzero(mask.to_numpy() if hasattr(mask, "to_numpy") else mask)


def _fit_catboost(features: np.ndarray, labels: np.ndarray) -> models.CatBoostAdapter:
    adapter = models.CatBoostAdapter(feature_names=GRU_FEATURE_NAMES)
    adapter.fit(features.tolist(), labels.tolist())
    return adapter


def _fit_lightgbm(
    features: np.ndarray, labels: np.ndarray, model_params: Mapping[str, object] | None = None,
) -> models.LightGBMAdapter:
    adapter = models.LightGBMAdapter(feature_names=GRU_FEATURE_NAMES, model_params=model_params)
    adapter.fit(features.tolist(), labels.tolist())
    return adapter


def _tune_lightgbm(
    train_features: np.ndarray, train_labels: np.ndarray,
    validation_features: np.ndarray, validation_labels: np.ndarray,
) -> tuple[dict[str, object], dict[str, object]]:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 400, step=50),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.12, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 127),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 200),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.65, 1.0),
            "subsample": trial.suggest_float("subsample", 0.65, 1.0),
            "subsample_freq": 1,
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
        }
        model = _fit_lightgbm(train_features, train_labels, params)
        probabilities = np.asarray(model.predict_proba(validation_features.tolist()))
        return _average_precision(validation_labels, probabilities)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=8, show_progress_bar=False)
    return dict(study.best_params, subsample_freq=1), {
        "objective": "validation_pr_auc", "trials": len(study.trials),
        "best_validation_pr_auc": float(study.best_value), "best_params": dict(study.best_params, subsample_freq=1),
    }


def _fold_predictions(
    frame: pd.DataFrame, labels: np.ndarray, payoffs: np.ndarray, folds: Sequence[Fold], family: str,
) -> tuple[list[pd.Timestamp], np.ndarray, np.ndarray, np.ndarray, list[dict[str, object]]]:
    values = frame.loc[:, list(GRU_FEATURE_NAMES)].to_numpy(np.float32)
    finite = np.isfinite(values).all(axis=1) & np.isfinite(payoffs)
    sequence_valid = pd.Series(finite).rolling(SEQUENCE_LENGTH, min_periods=SEQUENCE_LENGTH).sum().eq(SEQUENCE_LENGTH).to_numpy()
    all_times, all_probs, all_payoffs, all_gate, reports = [], [], [], [], []
    for fold in folds:
        train = _indices(frame["open_time"], fold.train_start, fold.train_end, sequence_valid if family == "gru" else finite)
        validation = _indices(frame["open_time"], fold.validation_start, fold.validation_end, sequence_valid if family == "gru" else finite)
        test = _indices(frame["open_time"], fold.test_start, fold.test_end, sequence_valid if family == "gru" else finite)
        if min(len(train), len(validation), len(test)) == 0:
            continue
        tuning = None
        if family in {"catboost", "lightgbm", "lightgbm_tuned"}:
            if family == "catboost":
                model = _fit_catboost(values[train], labels[train])
            else:
                params, tuning = _tune_lightgbm(
                    values[train], labels[train], values[validation], labels[validation],
                ) if family == "lightgbm_tuned" else (None, None)
                model = _fit_lightgbm(values[train], labels[train], params)
            validation_prob = np.asarray(model.predict_proba(values[validation].tolist()))
            test_prob = np.asarray(model.predict_proba(values[test].tolist()))
        elif family == "gru":
            model = GRUAdapter().fit_rows(values, labels, train)
            validation_prob = np.asarray(model.predict_endpoints(values, validation))
            test_prob = np.asarray(model.predict_endpoints(values, test))
        else:
            raise ValueError(f"unsupported short-sequence family: {family}")
        threshold = float(np.quantile(validation_prob, 0.75))
        calibration = _calibration(labels[test], test_prob)
        report = {"fold": fold.index, "test_start": fold.test_start.isoformat(), "test_end": fold.test_end.isoformat(),
                  "rows": len(test), "q75": threshold, **calibration}
        if tuning is not None:
            report["tuning"] = tuning
        reports.append(report)
        all_times.extend(frame.iloc[test]["open_time"].tolist())
        all_probs.extend(test_prob.tolist()); all_payoffs.extend(payoffs[test].tolist())
        all_gate.extend((values[test, GRU_FEATURE_NAMES.index("rv_60")] >= VOL_GATE).tolist())
        report["threshold_repeated_rows"] = len(test)
        report["threshold"] = threshold
    # Preserve the fold-specific q75 without searching another quantile.
    return all_times, np.asarray(all_probs), np.asarray(all_payoffs), np.asarray(all_gate), reports


def _score_oof(times, probabilities, payoffs, gate, reports, force_gate: bool | None = None) -> tuple[dict[str, object], dict[str, object]]:
    thresholds = np.concatenate([np.full(report["threshold_repeated_rows"], report["threshold"]) for report in reports]) if reports else np.array([])
    # _trade_metrics accepts one threshold; fold q75 is represented by filtering first.
    selected_probability = np.where(probabilities >= thresholds, 1.0, 0.0)
    ungated = _trade_metrics(times, selected_probability, payoffs, 1.0)
    gated = _trade_metrics(times, selected_probability, payoffs, 1.0, gate)
    measured_keep = gated["net_return"] > ungated["net_return"] and float(np.mean(gate)) >= 0.05
    keep_gate = measured_keep if force_gate is None else bool(force_gate)
    chosen = gated if keep_gate else ungated
    chosen["gate"] = {"kept": keep_gate, "cutoff": VOL_GATE if keep_gate else None, "eligible_share": float(np.mean(gate))}
    return chosen, {"ungated": ungated, "fixed_gate": gated, "measured_keep": measured_keep,
                    "selected": "fixed_gate" if keep_gate else "none"}


def run_experiment(
    input_path: Path,
    metrics_dir: Path,
    funding_dir: Path,
    premium_dir: Path,
    output: Path = RUN_ROOT,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing experiment directory: {output}")
    output.mkdir(parents=True)
    try:
        _status(output, "running", "diagnostics", "regenerating 28 features and independently checking labels")
        frame = build_features(input_path, metrics_dir, funding_dir, premium_dir)
        labels, payoffs, reasons = independent_short_labels(frame)
        audit = audit_labels(frame, labels, reasons)
        finite = np.isfinite(frame.loc[:, list(GRU_FEATURE_NAMES)]).all(axis=1).to_numpy() & np.isfinite(payoffs)
        coverage = {str(year): {"rows": int(((frame.open_time.dt.year == year) & finite).sum()),
                                "positive_rate": float(labels[(frame.open_time.dt.year == year) & finite].mean())}
                    for year in range(2020, 2026)}
        monthly = frame.loc[finite & (frame.open_time < pd.Timestamp("2026-01-01", tz="UTC")), ["open_time"]].copy()
        monthly["label"] = labels[monthly.index]
        month_rates = {
            str(month): {"count": int(values["count"]), "positive_rate": float(values["mean"])}
            for month, values in monthly.groupby(monthly.open_time.dt.strftime("%Y-%m")).label.agg(["count", "mean"]).to_dict("index").items()
        }
        ic = _feature_ic(frame, payoffs)
        diagnostics = {"label_audit": audit, "yearly_positive_rate": coverage, "monthly_positive_rate": month_rates,
                       "feature_ic": ic, "feature_names": list(GRU_FEATURE_NAMES), "feature_cache_used": False}
        _write_json(output / "diagnostics.json", diagnostics)
        if not audit["passed"] or not finite.any():
            _status(output, "failed", "failed", "data or label consistency check failed")
            return json.loads((output / "status.json").read_text())

        _status(output, "running", "baseline", "running fixed CatBoost walk-forward q75 baseline")
        folds = walk_forward_folds()
        cat_times, cat_prob, cat_pay, cat_gate, cat_reports = _fold_predictions(frame, labels, payoffs, folds, "catboost")
        cat_oof, gate_comparison = _score_oof(cat_times, cat_prob, cat_pay, cat_gate, cat_reports)
        baseline = {"model_family": "catboost", "folds": cat_reports, "oof": cat_oof,
                    "gate_comparison": gate_comparison, "q75_only": True}
        _write_json(output / "baseline.json", baseline)
        cat_pass = cat_oof["mean_net_bps"] > 0.0 and cat_oof["trades"] >= 1000 and cat_oof["positive_years"] >= 3
        ic_pass = ic["qualified_count"] >= 3
        if not (cat_pass or ic_pass):
            _status(output, "stopped_no_edge", "stopped_no_edge", "pre-registered edge criteria failed; GRU not built")
            return json.loads((output / "status.json").read_text())

        _status(output, "running", "gru", "running fixed 60-bar GRU on identical folds")
        gru_times, gru_prob, gru_pay, gru_gate, gru_reports = _fold_predictions(frame, labels, payoffs, folds, "gru")
        gru_oof, gru_gate_comparison = _score_oof(
            gru_times, gru_prob, gru_pay, gru_gate, gru_reports, force_gate=bool(cat_oof["gate"]["kept"]),
        )
        gru_pass = (gru_oof["mean_net_bps"] > 0.0 and gru_oof["mean_net_bps"] >= cat_oof["mean_net_bps"] + 2.0
                    and gru_oof["trades"] >= 500 and gru_oof["positive_years"] >= 3)
        gru_result = {"model_family": "pytorch_gru", "folds": gru_reports, "oof": gru_oof,
                      "gate_comparison": gru_gate_comparison, "research_advantage_passed": gru_pass}
        _write_json(output / "gru.json", gru_result)
        if not gru_pass:
            _status(output, "stopped_no_edge", "stopped_no_edge", "GRU did not beat CatBoost by the pre-registered margin")
            return json.loads((output / "status.json").read_text())

        _status(output, "running", "h1_backtest", "refitting through 2025 and running development_reuse H1 comparison")
        h1 = final_h1_backtest(frame, labels, payoffs, bool(cat_oof["gate"]["kept"]), output)
        _write_json(output / "h1_backtest.json", h1)
        _status(output, "complete", "complete", "all pre-registered stages completed", designation="development_reuse")
        return json.loads((output / "status.json").read_text())
    except BaseException as error:
        _write_json(output / "failure.json", {"type": type(error).__name__, "message": str(error)})
        _status(output, "failed", "failed", str(error))
        raise


def run_lightgbm_experiment(
    input_path: Path,
    metrics_dir: Path,
    funding_dir: Path,
    premium_dir: Path,
    output: Path = LIGHTGBM_RUN_ROOT,
    catboost_baseline: Path = RUN_ROOT / "baseline.json",
    tuned: bool = False,
) -> dict[str, object]:
    """Run the post-hoc LightGBM challenger on the registered OOF contract."""
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing experiment directory: {output}")
    output.mkdir(parents=True)
    try:
        _status(output, "running", "diagnostics", "regenerating features and independently checking short labels")
        frame = build_features(input_path, metrics_dir, funding_dir, premium_dir)
        labels, payoffs, reasons = independent_short_labels(frame)
        audit = audit_labels(frame, labels, reasons)
        finite = np.isfinite(frame.loc[:, list(GRU_FEATURE_NAMES)]).all(axis=1).to_numpy() & np.isfinite(payoffs)
        _write_json(output / "diagnostics.json", {
            "label_audit": audit, "feature_names": list(GRU_FEATURE_NAMES), "feature_cache_used": False,
        })
        if not audit["passed"] or not finite.any():
            _status(output, "failed", "failed", "data or label consistency check failed")
            return json.loads((output / "status.json").read_text())

        family = "lightgbm_tuned" if tuned else "lightgbm"
        _status(output, "running", family, f"running {family} walk-forward q75 challenger")
        times, probabilities, fold_payoffs, gate, reports = _fold_predictions(
            frame, labels, payoffs, walk_forward_folds(), family,
        )
        oof, gate_comparison = _score_oof(times, probabilities, fold_payoffs, gate, reports)
        baseline = json.loads(catboost_baseline.read_text(encoding="utf-8-sig"))
        catboost_oof = baseline["oof"]
        result = {
            "designation": "posthoc_challenger", "live_approval_eligible": False,
            "model_family": "lightgbm", "tuned": tuned, "folds": reports, "oof": oof,
            "gate_comparison": gate_comparison, "q75_only": True,
            "comparison_to_catboost": {
                "catboost_mean_net_bps": catboost_oof["mean_net_bps"],
                "mean_net_bps_delta": oof["mean_net_bps"] - catboost_oof["mean_net_bps"],
            },
        }
        _write_json(output / "lightgbm.json", result)
        _status(output, "complete", "complete", f"{family} post-hoc challenger completed")
        return json.loads((output / "status.json").read_text())
    except BaseException as error:
        _write_json(output / "failure.json", {"type": type(error).__name__, "message": str(error)})
        _status(output, "failed", "failed", str(error))
        raise


def _rolling_backtest(times, probabilities, payoffs, gate) -> dict[str, object]:
    quantile = RollingQuantileThreshold(0.75, window=43_200, warmup=1_000)
    selected, funnel, next_time = [], {"bars": len(times), "warmup_blocked": 0, "gate_eligible": 0, "q75_eligible": 0}, None
    for index, (when, probability) in enumerate(zip(times, probabilities)):
        threshold = quantile.resolve(float(probability))
        if threshold is None:
            funnel["warmup_blocked"] += 1
            continue
        if not gate[index]:
            continue
        funnel["gate_eligible"] += 1
        if probability >= threshold:
            funnel["q75_eligible"] += 1
            if next_time is None or when >= next_time:
                selected.append(index); next_time = when + pd.Timedelta(minutes=HORIZON)
    net = payoffs[selected] - COST if selected else np.asarray([])
    monthly = {}
    for month in sorted({when.strftime("%Y-%m") for when in times}):
        values = net[[times[index].strftime("%Y-%m") == month for index in selected]] if selected else np.asarray([])
        monthly[month] = {"trades": len(values), "win_rate": float(np.mean(values > 0.0)) if len(values) else 0.0,
                          "net_return": float(values.sum())}
    equity = np.cumsum(net) if len(net) else np.asarray([])
    drawdown = equity - np.maximum.accumulate(np.r_[0.0, equity])[-len(equity):] if len(equity) else np.asarray([])
    wins, losses = net[net > 0.0].sum(), -net[net < 0.0].sum()
    return {"monthly": monthly, "trades": len(selected), "profit_factor": float(wins / losses) if losses else None,
            "mdd": float(drawdown.min()) if len(drawdown) else 0.0, "net_return": float(net.sum()),
            "entry_funnel": funnel, "gate_eligible_share": float(np.mean(gate))}


def final_h1_backtest(frame: pd.DataFrame, labels: np.ndarray, payoffs: np.ndarray, gate_kept: bool, output: Path) -> dict[str, object]:
    values = frame.loc[:, list(GRU_FEATURE_NAMES)].to_numpy(np.float32)
    finite = np.isfinite(values).all(axis=1) & np.isfinite(payoffs)
    sequence_valid = pd.Series(finite).rolling(SEQUENCE_LENGTH, min_periods=SEQUENCE_LENGTH).sum().eq(SEQUENCE_LENGTH).to_numpy()
    label_cutoff = pd.Timestamp("2026-01-01", tz="UTC") - pd.Timedelta(minutes=HORIZON)
    train = _indices(frame.open_time, pd.Timestamp("2020-01-01", tz="UTC"), label_cutoff, finite)
    train_seq = _indices(frame.open_time, pd.Timestamp("2020-01-01", tz="UTC"), label_cutoff, sequence_valid)
    test = _indices(frame.open_time, pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-07-01", tz="UTC"), finite)
    # H1 is a fresh backtest stream: do not seed its GRU with December history.
    test_seq = _indices(
        frame.open_time, pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(minutes=SEQUENCE_LENGTH - 1),
        pd.Timestamp("2026-07-01", tz="UTC"), sequence_valid,
    )
    cat = _fit_catboost(values[train], labels[train])
    gru = GRUAdapter().fit_rows(values, labels, train_seq)
    _write_json(output / "catboost_final" / "model.json", {**cat.as_dict(), "train_target": "short_profitability"})
    _write_json(output / "gru_final" / "model.json", gru.as_dict())
    cat_probability = np.asarray(cat.predict_proba(values[test].tolist()))
    gru_probability = np.asarray(gru.predict_endpoints(values, test_seq))
    gate_cat = (values[test, GRU_FEATURE_NAMES.index("rv_60")] >= VOL_GATE) if gate_kept else np.ones(len(test), bool)
    gate_gru = (values[test_seq, GRU_FEATURE_NAMES.index("rv_60")] >= VOL_GATE) if gate_kept else np.ones(len(test_seq), bool)
    return {"designation": "development_reuse", "live_approval_eligible": False, "q75_window": 43_200,
            "warmup": 1000, "catboost": _rolling_backtest(frame.iloc[test].open_time.tolist(), cat_probability, payoffs[test], gate_cat),
            "pytorch_gru": _rolling_backtest(frame.iloc[test_seq].open_time.tolist(), gru_probability, payoffs[test_seq], gate_gru)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("artifacts/btcusdt_2020_2026h1.parquet"))
    parser.add_argument("--metrics-dir", type=Path, default=Path("artifacts/metrics"))
    parser.add_argument("--funding-dir", type=Path, default=Path("artifacts/funding_2020_2026h1"))
    parser.add_argument("--premium-index-dir", type=Path, default=Path("artifacts/premium_index_2020_2026h1"))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--lightgbm-only", action="store_true")
    group.add_argument("--lightgbm-tuned-only", action="store_true")
    args = parser.parse_args(argv)
    if args.lightgbm_tuned_only:
        run_lightgbm_experiment(
            args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir,
            output=LIGHTGBM_TUNED_RUN_ROOT, tuned=True,
        )
    else:
        runner = run_lightgbm_experiment if args.lightgbm_only else run_experiment
        runner(args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
