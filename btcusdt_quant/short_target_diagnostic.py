"""Post-hoc diagnostic for short targets and missing trend features."""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .gru import GRU_FEATURE_NAMES
from .short_sequence import COST, _indices, _status, _trade_metrics, _write_json, build_features, walk_forward_folds


RUN_ROOT = Path("artifacts/short_target_trend_diagnostic_20260828")
HORIZONS = (15, 30, 45, 60)
TREND_FEATURE_NAMES = (
    "return_15", "return_30", "return_60", "close_sma_60_ratio", "close_zscore_60",
    "rsi_14", "ema_gap_15m", "rsi_15m", "return_24h",
)
MODEL_FEATURE_NAMES = tuple(GRU_FEATURE_NAMES) + TREND_FEATURE_NAMES


def _rsi(values: pd.Series, period: int = 14) -> pd.Series:
    delta = values.diff()
    gain = delta.clip(lower=0.0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0.0)).rolling(period, min_periods=period).mean()
    result = 100.0 - 100.0 / (1.0 + gain / loss.where(loss != 0.0))
    result = result.where(~((loss == 0.0) & (gain > 0.0)), 100.0)
    return result.where(~((loss == 0.0) & (gain == 0.0)), 50.0)


def add_trend_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the document's causal mean-reversion/trend inputs."""
    frame = frame.copy()
    close = frame["close"].astype(float)
    for period in (15, 30, 60):
        frame[f"return_{period}"] = close.pct_change(period)
    mean60 = close.rolling(60, min_periods=60).mean()
    std60 = close.rolling(60, min_periods=60).std(ddof=0)
    frame["close_sma_60_ratio"] = close / mean60 - 1.0
    frame["close_zscore_60"] = (close - mean60) / std60.where(std60 != 0.0)
    frame["rsi_14"] = _rsi(close)

    minute_close = pd.Series(close.to_numpy(), index=pd.DatetimeIndex(frame["open_time"]), name="close")
    close15 = minute_close.resample("15min", origin="epoch", label="right", closed="left").last().dropna()
    ema15 = close15.ewm(span=20, adjust=False, min_periods=20).mean()
    mtf15 = pd.DataFrame({
        "open_time": close15.index,
        "ema_gap_15m": (close15 - ema15) / close15,
        "rsi_15m": _rsi(close15),
    }).reset_index(drop=True)
    close1h = minute_close.resample("1h", origin="epoch", label="right", closed="left").last().dropna()
    mtf1h = pd.DataFrame({
        "open_time": close1h.index, "return_24h": close1h / close1h.shift(23) - 1.0,
    }).reset_index(drop=True)
    frame = pd.merge_asof(frame, mtf15, on="open_time", direction="backward")
    return pd.merge_asof(frame, mtf1h, on="open_time", direction="backward")


def short_gross_return(frame: pd.DataFrame, horizon: int) -> np.ndarray:
    close = frame["close"].to_numpy(float)
    target = np.full(len(close), np.nan)
    target[:-horizon] = -(close[horizon:] / close[:-horizon] - 1.0)
    return target


def _select_trading_threshold(
    times: Sequence[pd.Timestamp], predictions: np.ndarray, gross_payoffs: np.ndarray, horizon: int,
) -> tuple[float | None, dict[str, object]]:
    quantiles = (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95, 0.975, 0.99)
    candidates = sorted({0.0, *(float(np.quantile(predictions, q)) for q in quantiles)})
    best_threshold, best_score, audit = None, (0.0, 0.0, 0), []
    for threshold in candidates:
        metrics = _trade_metrics(times, predictions, gross_payoffs, threshold, holding_minutes=horizon)
        score = (float(metrics["net_return"]), float(metrics["mean_net_bps"]), int(metrics["trades"]))
        eligible = metrics["trades"] >= 100
        audit.append({"threshold": threshold, "eligible": eligible, "trades": metrics["trades"],
                      "mean_net_bps": metrics["mean_net_bps"], "net_return": metrics["net_return"]})
        if eligible and score > best_score:
            best_threshold, best_score = threshold, score
    return best_threshold, {"objective": "validation_trading_pnl", "min_nonoverlap_trades": 100,
                            "selected_threshold": best_threshold, "candidates": audit}


def _fit_regressor(features: np.ndarray, targets: np.ndarray):
    import lightgbm as lgb

    model = lgb.LGBMRegressor(
        objective="regression", n_estimators=300, learning_rate=0.03, num_leaves=31,
        min_child_samples=100, random_state=42, n_jobs=-1, verbosity=-1,
    )
    return model.fit(features, targets)


def _safe_spearman(left: np.ndarray, right: np.ndarray) -> float:
    value = float(spearmanr(left, right).statistic) if len(left) > 2 else 0.0
    return value if math.isfinite(value) else 0.0


def _feature_ic(frame: pd.DataFrame, gross: np.ndarray, horizon: int) -> dict[str, object]:
    report, stable = {}, []
    for feature in TREND_FEATURE_NAMES:
        yearly = {}
        for year in range(2021, 2026):
            valid = np.flatnonzero(
                (frame.open_time.dt.year.to_numpy() == year)
                & np.isfinite(frame[feature].to_numpy(float)) & np.isfinite(gross)
            )[::horizon]
            yearly[str(year)] = _safe_spearman(frame.iloc[valid][feature].to_numpy(float), gross[valid] - COST)
        signs = max(sum(value >= 0.01 for value in yearly.values()), sum(value <= -0.01 for value in yearly.values()))
        report[feature] = {"by_year": yearly, "qualifying_years": signs}
        if signs >= 4:
            stable.append(feature)
    return {"sampling_stride": horizon, "features": report, "stable_features": stable}


def _run_horizon(frame: pd.DataFrame, values: np.ndarray, horizon: int) -> dict[str, object]:
    gross = short_gross_return(frame, horizon)
    finite = np.isfinite(values).all(axis=1) & np.isfinite(gross)
    all_times, all_gross, all_selected, all_q90, all_predictions, reports = [], [], [], [], [], []
    for fold in walk_forward_folds(purge_bars=horizon):
        train = _indices(frame.open_time, fold.train_start, fold.train_end, finite)
        validation = _indices(frame.open_time, fold.validation_start, fold.validation_end, finite)
        test = _indices(frame.open_time, fold.test_start, fold.test_end, finite)
        train = train[train % horizon == 0]
        if min(len(train), len(validation), len(test)) == 0:
            continue
        model = _fit_regressor(values[train], gross[train] - COST)
        validation_predictions = np.asarray(model.predict(values[validation]), dtype=float)
        test_predictions = np.asarray(model.predict(values[test]), dtype=float)
        threshold, threshold_audit = _select_trading_threshold(
            frame.iloc[validation].open_time.tolist(), validation_predictions, gross[validation], horizon,
        )
        q90 = float(np.quantile(validation_predictions, 0.90))
        all_times.extend(frame.iloc[test].open_time.tolist())
        all_gross.extend(gross[test].tolist())
        all_predictions.extend(test_predictions.tolist())
        all_selected.extend((test_predictions >= threshold).tolist() if threshold is not None else [False] * len(test))
        all_q90.extend((test_predictions >= q90).tolist())
        reports.append({
            "fold": fold.index, "train_rows_after_stride": len(train), "validation_rows": len(validation),
            "test_rows": len(test), "threshold_selection": threshold_audit, "validation_q90": q90,
            "test_spearman": _safe_spearman(test_predictions, gross[test] - COST),
            "test_mae": float(np.mean(np.abs(test_predictions - (gross[test] - COST)))),
        })
    times, payoffs = all_times, np.asarray(all_gross)
    selected = _trade_metrics(times, np.asarray(all_selected, float), payoffs, 1.0, holding_minutes=horizon)
    q90 = _trade_metrics(times, np.asarray(all_q90, float), payoffs, 1.0, holding_minutes=horizon)
    prediction_ic = {}
    years = np.asarray([when.year for when in times])
    predictions = np.asarray(all_predictions)
    for year in range(2021, 2026):
        mask = years == year
        prediction_ic[str(year)] = _safe_spearman(predictions[mask], payoffs[mask] - COST)
    return {
        "horizon": horizon, "target": "signed_short_horizon_return_minus_round_trip_cost",
        "training_stride": horizon, "folds": reports, "trading_pnl_oof": selected, "q90_oof": q90,
        "prediction_ic_by_year": prediction_ic, "feature_ic": _feature_ic(frame, gross, horizon),
    }


def run_diagnostic(
    input_path: Path, metrics_dir: Path, funding_dir: Path, premium_dir: Path, output: Path = RUN_ROOT,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing diagnostic directory: {output}")
    output.mkdir(parents=True)
    try:
        _status(output, "running", "features", "rebuilding source features and causal trend inputs")
        frame = add_trend_features(build_features(input_path, metrics_dir, funding_dir, premium_dir))
        values = frame.loc[:, list(MODEL_FEATURE_NAMES)].to_numpy(np.float32)
        _status(output, "running", "horizons", "testing continuous short payoff targets at 15/30/45/60 minutes")
        horizons = {str(horizon): _run_horizon(frame, values, horizon) for horizon in HORIZONS}
        edge_horizons = [
            horizon for horizon, result in horizons.items()
            if result["q90_oof"]["mean_net_bps"] > 0.0 and result["q90_oof"]["positive_years"] >= 3
            and result["q90_oof"]["trades"] >= 500
        ]
        result = {
            "designation": "posthoc_target_diagnostic", "live_approval_eligible": False,
            "model_family": "lightgbm_regressor", "feature_names": list(MODEL_FEATURE_NAMES),
            "horizons": horizons, "edge_horizons": edge_horizons, "edge_detected": bool(edge_horizons),
        }
        _write_json(output / "target_trend_diagnostic.json", result)
        _status(output, "complete", "complete", "target and trend diagnostic completed", edge_horizons=edge_horizons)
        return result
    except BaseException as error:
        _write_json(output / "failure.json", {"type": type(error).__name__, "message": str(error)})
        _status(output, "failed", "failed", str(error))
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("artifacts/btcusdt_2020_2026h1.parquet"))
    parser.add_argument("--metrics-dir", type=Path, default=Path("artifacts/metrics"))
    parser.add_argument("--funding-dir", type=Path, default=Path("artifacts/funding_2020_2026h1"))
    parser.add_argument("--premium-index-dir", type=Path, default=Path("artifacts/premium_index_2020_2026h1"))
    args = parser.parse_args(argv)
    run_diagnostic(args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
