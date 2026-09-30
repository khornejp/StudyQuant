"""Fast-entry/slow-regime short research with fair model tuning."""
from __future__ import annotations

import argparse
import gc
import json
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .gru import GRU_FEATURE_NAMES, SEQUENCE_LENGTH
from .short_sequence import COST, _indices, _status, _trade_metrics, _write_json, build_features, walk_forward_folds
from .short_target_diagnostic import add_trend_features, short_gross_return


RUN_ROOT = Path("artifacts/short_fast_regime_experiment_20260828")
HORIZONS = (15, 30)
QUANTILES = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.975, 0.98)
ADDED_FAST_FEATURE_NAMES = (
    "close_zscore_10", "close_zscore_20", "close_zscore_30",
    "ema_gap_10", "ema_gap_20", "voladj_return_10",
)
MODEL_FEATURE_NAMES = tuple(GRU_FEATURE_NAMES) + ADDED_FAST_FEATURE_NAMES
SLOW_REGIME_FEATURE_NAMES = ("ema_gap_15m", "return_24h")
REGIME_FEATURE_NAMES = (*SLOW_REGIME_FEATURE_NAMES, "rv_60")
REGIME_NAMES = tuple(f"{direction}_{volatility}" for direction in ("down", "neutral", "up")
                     for volatility in ("low_vol", "high_vol"))


def add_fast_regime_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add causal fast entry features and slow context features."""
    frame = add_trend_features(frame)
    close = frame["close"].astype(float)
    one_minute_return = close.pct_change()
    for window in (10, 20, 30):
        mean = close.rolling(window, min_periods=window).mean()
        std = close.rolling(window, min_periods=window).std(ddof=0)
        frame[f"close_zscore_{window}"] = (close - mean) / std.where(std != 0.0)
    for span in (10, 20):
        ema = close.ewm(span=span, adjust=False, min_periods=span).mean()
        frame[f"ema_gap_{span}"] = (close - ema) / close.where(close != 0.0)
    volatility = one_minute_return.rolling(10, min_periods=10).std(ddof=0) * math.sqrt(10.0)
    frame["voladj_return_10"] = close.pct_change(10) / volatility.where(volatility != 0.0)
    return frame


def fit_regime_thresholds(frame: pd.DataFrame, train_indices: Sequence[int]) -> dict[str, float]:
    indices = np.asarray(train_indices, dtype=np.int64)
    ema = frame.iloc[indices]["ema_gap_15m"].to_numpy(float)
    returns = frame.iloc[indices]["return_24h"].to_numpy(float)
    volatility = frame.iloc[indices]["rv_60"].to_numpy(float)
    ema, returns, volatility = (
        values[np.isfinite(values)] for values in (ema, returns, volatility)
    )
    if not len(ema) or not len(returns) or not len(volatility):
        raise ValueError("training fold has no finite slow-regime observations")
    return {
        "ema_gap_15m_q33": float(np.quantile(ema, 1.0 / 3.0)),
        "ema_gap_15m_q67": float(np.quantile(ema, 2.0 / 3.0)),
        "return_24h_q33": float(np.quantile(returns, 1.0 / 3.0)),
        "return_24h_q67": float(np.quantile(returns, 2.0 / 3.0)),
        "rv_60_median": float(np.quantile(volatility, 0.5)),
    }


def assign_regimes(frame: pd.DataFrame, thresholds: Mapping[str, float]) -> np.ndarray:
    ema = frame["ema_gap_15m"].to_numpy(float)
    returns = frame["return_24h"].to_numpy(float)
    volatility = frame["rv_60"].to_numpy(float)
    result = np.full(len(frame), "unknown", dtype=object)
    finite = np.isfinite(ema) & np.isfinite(returns) & np.isfinite(volatility)
    ema_direction = np.where(
        ema <= float(thresholds["ema_gap_15m_q33"]), -1,
        np.where(ema >= float(thresholds["ema_gap_15m_q67"]), 1, 0),
    )
    return_direction = np.where(
        returns <= float(thresholds["return_24h_q33"]), -1,
        np.where(returns >= float(thresholds["return_24h_q67"]), 1, 0),
    )
    combined = ema_direction + return_direction
    direction = np.where(combined < 0, "down", np.where(combined > 0, "up", "neutral"))
    vol = np.where(volatility >= float(thresholds["rv_60_median"]), "high_vol", "low_vol")
    result[finite] = np.char.add(np.char.add(direction[finite], "_"), vol[finite])
    return result


def _safe_ic(predictions: np.ndarray, targets: np.ndarray) -> float:
    if len(predictions) < 3:
        return 0.0
    value = float(spearmanr(predictions, targets).statistic)
    return value if math.isfinite(value) else 0.0


def feature_diagnostics(frame: pd.DataFrame, gross: np.ndarray, horizon: int) -> dict[str, object]:
    """Report annual IC and smoothness; never use these values for model selection."""
    year_values = frame.open_time.dt.year.to_numpy()
    report: dict[str, object] = {}
    for name in (*ADDED_FAST_FEATURE_NAMES, *REGIME_FEATURE_NAMES):
        values = frame[name].to_numpy(float)
        finite = np.isfinite(values) & np.isfinite(gross)
        changes = np.abs(np.diff(values)) > 1e-15
        valid_pairs = np.isfinite(values[:-1]) & np.isfinite(values[1:])
        yearly = {}
        for year in range(2021, 2026):
            indices = np.flatnonzero(finite & (year_values == year))[::horizon]
            yearly[str(year)] = _safe_ic(values[indices], gross[indices] - COST)
        report[name] = {
            "annual_spearman_ic": yearly,
            "mean_annual_ic": float(np.mean(list(yearly.values()))),
            "minute_change_rate": float(changes[valid_pairs].mean()) if valid_pairs.any() else 0.0,
            "lag1_autocorrelation": _safe_ic(values[:-1][valid_pairs], values[1:][valid_pairs]),
        }
    return report


def _candidate_params(family: str, trials: int, seed: int = 42) -> list[dict[str, object]]:
    if trials < 1:
        raise ValueError("trials must be positive")
    spaces: dict[str, dict[str, Sequence[object]]] = {
        "catboost": {
            "iterations": (250, 400, 600), "learning_rate": (0.02, 0.05, 0.10),
            "depth": (4, 6, 8), "l2_leaf_reg": (1.0, 3.0, 10.0),
            "random_strength": (0.0, 1.0, 2.0),
        },
        "lightgbm": {
            "n_estimators": (250, 400, 600), "learning_rate": (0.02, 0.05, 0.10),
            "num_leaves": (15, 31, 63), "min_child_samples": (50, 100, 200),
            "colsample_bytree": (0.7, 0.85, 1.0), "reg_lambda": (0.0, 1.0, 10.0),
        },
        "gru": {
            "hidden_size": (32, 64, 128), "num_layers": (1, 2),
            "learning_rate": (3e-4, 1e-3, 3e-3), "weight_decay": (0.0, 1e-5, 1e-4),
            "dropout": (0.0, 0.1, 0.2), "batch_size": (512, 1024),
        },
    }
    if family not in spaces:
        raise ValueError(f"unsupported model family: {family}")
    defaults = {
        "catboost": {"iterations": 400, "learning_rate": 0.05, "depth": 6, "l2_leaf_reg": 3.0,
                     "random_strength": 1.0},
        "lightgbm": {"n_estimators": 400, "learning_rate": 0.05, "num_leaves": 31,
                     "min_child_samples": 100, "colsample_bytree": 0.85, "reg_lambda": 1.0},
        "gru": {"hidden_size": 64, "num_layers": 1, "learning_rate": 1e-3,
                "weight_decay": 1e-5, "dropout": 0.0, "batch_size": 1024},
    }
    rng = random.Random(seed + {"catboost": 1, "lightgbm": 2, "gru": 3}[family])
    candidates = [defaults[family]]
    keys = tuple(spaces[family])
    seen = {tuple(defaults[family][key] for key in keys)}
    while len(candidates) < trials:
        candidate = {key: rng.choice(spaces[family][key]) for key in keys}
        marker = tuple(candidate[key] for key in keys)
        if marker not in seen:
            seen.add(marker)
            candidates.append(candidate)
    return candidates


def _fit_tabular(
    family: str, params: Mapping[str, object], train_x: np.ndarray, train_y: np.ndarray,
    validation_x: np.ndarray, validation_y: np.ndarray,
):
    if family == "lightgbm":
        import lightgbm as lgb

        model = lgb.LGBMRegressor(
            objective="regression_l1", random_state=42, n_jobs=-1, verbosity=-1, **params,
        )
        model.fit(
            train_x, train_y, eval_set=[(validation_x, validation_y)], eval_metric="l1",
            callbacks=[lgb.early_stopping(30, verbose=False)],
        )
        return model
    if family != "catboost":
        raise ValueError(f"not a tabular model: {family}")
    from catboost import CatBoostRegressor

    common = {
        "loss_function": "MAE", "random_seed": 42, "verbose": False,
        "allow_writing_files": False, "od_type": "Iter", "od_wait": 30, **params,
    }
    test_cpu = os.environ.get("STUDYQUANT_TEST_CATBOOST_DEFAULT_DEVICE") == "CPU"
    if not test_cpu:
        common.update(task_type="GPU", devices="0")
    try:
        model = CatBoostRegressor(**common)
        model.fit(train_x, train_y, eval_set=(validation_x, validation_y), use_best_model=True)
        return model
    except Exception:
        if test_cpu:
            raise
        common.pop("task_type", None)
        common.pop("devices", None)
        model = CatBoostRegressor(**common)
        model.fit(train_x, train_y, eval_set=(validation_x, validation_y), use_best_model=True)
        return model


@dataclass
class _GRUFitted:
    model: object
    mean: np.ndarray
    std: np.ndarray
    device: object
    training_audit: dict[str, object] | None = None


def _sequence_batch(values: np.ndarray, endpoints: Sequence[int]) -> np.ndarray:
    ends = np.asarray(endpoints, dtype=np.int64)
    if not len(ends):
        return np.empty((0, SEQUENCE_LENGTH, values.shape[1]), dtype=np.float32)
    if ends.min() < SEQUENCE_LENGTH - 1 or ends.max() >= len(values):
        raise ValueError("sequence endpoint outside causal history")
    return np.stack([values[end - SEQUENCE_LENGTH + 1:end + 1] for end in ends]).astype(np.float32)


def _fit_gru(
    params: Mapping[str, object], values: np.ndarray, targets: np.ndarray,
    train_endpoints: np.ndarray, validation_endpoints: np.ndarray,
    *, loss_name: str = "smooth_l1", network_factory=None,
) -> _GRUFitted:
    import torch
    import torch.nn as nn

    if loss_name not in {"smooth_l1", "mse"}:
        raise ValueError(f"unsupported GRU regression loss: {loss_name}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_rows = values[train_endpoints]
    mean = train_rows.mean(axis=0, dtype=np.float64).astype(np.float32)
    std = train_rows.std(axis=0, dtype=np.float64).astype(np.float32)
    std[std == 0.0] = 1.0
    scaled = np.clip((values - mean) / std, -10.0, 10.0).astype(np.float32)
    train_x = _sequence_batch(scaled, train_endpoints)
    validation_x = _sequence_batch(scaled, validation_endpoints)
    train_y = targets[train_endpoints].astype(np.float32)
    validation_y = targets[validation_endpoints].astype(np.float32)

    class Network(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            layers = int(params["num_layers"])
            dropout = float(params["dropout"]) if layers > 1 else 0.0
            self.gru = nn.GRU(
                values.shape[1], int(params["hidden_size"]), num_layers=layers,
                dropout=dropout, batch_first=True,
            )
            self.head = nn.Linear(int(params["hidden_size"]), 1)

        def forward(self, batch):
            output, _ = self.gru(batch)
            return self.head(output[:, -1]).squeeze(1)

    torch.manual_seed(42)
    np.random.seed(42)
    model = (Network() if network_factory is None else network_factory(values.shape[1])).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=float(params["learning_rate"]), weight_decay=float(params["weight_decay"]),
    )
    loss_fn = nn.SmoothL1Loss() if loss_name == "smooth_l1" else nn.MSELoss()
    data = torch.utils.data.TensorDataset(torch.from_numpy(train_x), torch.from_numpy(train_y))
    loader = torch.utils.data.DataLoader(
        data, batch_size=int(params["batch_size"]), shuffle=True,
        generator=torch.Generator().manual_seed(42), pin_memory=device.type == "cuda",
    )
    validation_tensor = torch.from_numpy(validation_x)
    validation_target = torch.from_numpy(validation_y)
    best_loss, best_state, stale = float("inf"), None, 0
    history, best_epoch = [], None
    for epoch in range(15):
        model.train()
        for batch_x, batch_y in loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimizer.zero_grad()
            loss = loss_fn(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()
        model.eval()
        total, count = 0.0, 0
        with torch.no_grad():
            for start in range(0, len(validation_tensor), 4096):
                batch_x = validation_tensor[start:start + 4096].to(device)
                batch_y = validation_target[start:start + 4096].to(device)
                total += float(loss_fn(model(batch_x), batch_y)) * len(batch_y)
                count += len(batch_y)
        validation_loss = total / max(count, 1)
        if not math.isfinite(validation_loss):
            raise ValueError(f"nonfinite {loss_name} validation loss at epoch {epoch + 1}")
        history.append({"epoch": epoch + 1, "validation_loss": validation_loss})
        if validation_loss < best_loss - 1e-6:
            best_loss, stale = validation_loss, 0
            best_epoch = epoch + 1
            best_state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
        else:
            stale += 1
            if stale >= 3:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return _GRUFitted(model, mean, std, device, {
        "loss": loss_name, "best_epoch": best_epoch, "epochs_trained": len(history),
        "best_validation_loss": best_loss, "history": history,
    })


def _predict_gru(fitted: _GRUFitted, values: np.ndarray, endpoints: Sequence[int]) -> np.ndarray:
    import torch

    scaled = np.clip((values - fitted.mean) / fitted.std, -10.0, 10.0).astype(np.float32)
    result: list[float] = []
    ends = np.asarray(endpoints, dtype=np.int64)
    with torch.no_grad():
        for start in range(0, len(ends), 4096):
            batch = torch.from_numpy(_sequence_batch(scaled, ends[start:start + 4096])).to(fitted.device)
            result.extend(fitted.model(batch).detach().cpu().numpy().tolist())
    return np.asarray(result, dtype=float)


def tune_fold(
    family: str, values: np.ndarray, target_bps: np.ndarray, train: np.ndarray,
    validation: np.ndarray, trials: int,
) -> tuple[object, np.ndarray, dict[str, object]]:
    candidates = _candidate_params(family, trials)
    validation_score_indices = np.arange(0, len(validation), max(1, len(validation) // 3_000 + 1))
    reports, best_key, best_model, best_predictions = [], (-float("inf"), -float("inf")), None, None
    for number, params in enumerate(candidates):
        if family == "gru":
            model = _fit_gru(params, values, target_bps, train, validation)
            predictions = _predict_gru(model, values, validation)
        else:
            model = _fit_tabular(
                family, params, values[train], target_bps[train], values[validation], target_bps[validation],
            )
            predictions = np.asarray(model.predict(values[validation]), dtype=float)
        sampled = validation_score_indices
        ic = _safe_ic(predictions[sampled], target_bps[validation[sampled]])
        mae = float(np.mean(np.abs(predictions[sampled] - target_bps[validation[sampled]])))
        key = (ic, -mae)
        reports.append({"trial": number, "params": dict(params), "validation_ic": ic, "validation_mae_bps": mae})
        if key > best_key:
            best_key, best_model, best_predictions = key, model, predictions
        elif family == "gru":
            del model
        gc.collect()
    assert best_model is not None and best_predictions is not None
    best_number = max(range(len(reports)), key=lambda index: (reports[index]["validation_ic"], -reports[index]["validation_mae_bps"]))
    reports[best_number]["selected"] = True
    return best_model, best_predictions, {
        "objective": "validation_spearman_ic_then_mae", "trials": reports,
        "best_params": reports[best_number]["params"], "best_validation_ic": reports[best_number]["validation_ic"],
        "best_validation_mae_bps": reports[best_number]["validation_mae_bps"],
    }


def _prediction(model: object, family: str, values: np.ndarray, endpoints: np.ndarray) -> np.ndarray:
    if family == "gru":
        return _predict_gru(model, values, endpoints)  # type: ignore[arg-type]
    return np.asarray(getattr(model, "predict")(values[endpoints]), dtype=float)


def _quantile_key(quantile: float) -> str:
    return f"q{quantile * 100:g}"


def fold_signal_masks(
    validation_times: Sequence[pd.Timestamp], validation_scores: np.ndarray, validation_gross: np.ndarray,
    validation_regimes: np.ndarray, test_scores: np.ndarray, test_regimes: np.ndarray, horizon: int,
    validation_gates: Mapping[str, np.ndarray] | None = None,
    test_gates: Mapping[str, np.ndarray] | None = None,
    *, quantiles: Sequence[float] = QUANTILES,
) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, object]]:
    if len(quantiles) == 0 or any(not 0 < q < 1 for q in quantiles):
        raise ValueError("quantiles must be a nonempty sequence strictly between zero and one")
    validation_gates, test_gates = validation_gates or {}, test_gates or {}
    if set(validation_gates) != set(test_gates):
        raise ValueError("validation and test gates must have identical names")
    masks: dict[str, dict[str, np.ndarray]] = {}
    audit: dict[str, object] = {}
    for quantile in quantiles:
        key = _quantile_key(quantile)
        global_threshold = float(np.quantile(validation_scores, quantile))
        raw = test_scores >= global_threshold
        gated = np.zeros(len(test_scores), dtype=bool)
        regime_masks: dict[str, np.ndarray] = {}
        regime_audit: dict[str, object] = {}
        for regime in REGIME_NAMES:
            validation_mask = validation_regimes == regime
            test_mask = test_regimes == regime
            if not validation_mask.any():
                regime_masks[regime] = np.zeros(len(test_scores), dtype=bool)
                regime_audit[regime] = {"allowed": False, "threshold": None, "validation_trades": 0}
                continue
            threshold = float(np.quantile(validation_scores[validation_mask], quantile))
            selected_validation = validation_mask & (validation_scores >= threshold)
            validation_metrics = _trade_metrics(
                validation_times, selected_validation.astype(float), validation_gross, 1.0,
                holding_minutes=horizon,
            )
            allowed = float(validation_metrics["net_return"]) > 0.0
            selected_test = test_mask & (test_scores >= threshold)
            regime_masks[regime] = selected_test
            if allowed:
                gated |= selected_test
            regime_audit[regime] = {
                "allowed": allowed, "threshold": threshold,
                "validation_trades": validation_metrics["trades"],
                "validation_mean_net_bps": validation_metrics["mean_net_bps"],
                "validation_net_return": validation_metrics["net_return"],
            }
        external_masks, external_audit = {}, {}
        for name, validation_gate in validation_gates.items():
            validation_gate = np.asarray(validation_gate, dtype=bool)
            test_gate = np.asarray(test_gates[name], dtype=bool)
            selected_validation = (validation_scores >= global_threshold) & validation_gate
            validation_metrics = _trade_metrics(
                validation_times, selected_validation.astype(float), validation_gross, 1.0,
                holding_minutes=horizon,
            )
            external_masks[name] = raw & test_gate
            external_audit[name] = {
                "validation_trades": validation_metrics["trades"],
                "validation_mean_net_bps": validation_metrics["mean_net_bps"],
                "validation_eligible_share": float(validation_gate.mean()),
                "test_eligible_share": float(test_gate.mean()),
            }
        masks[key] = {
            "regime_unfiltered": raw, "regime_filtered": gated,
            **external_masks, **regime_masks,
        }
        audit[key] = {
            "global_threshold": global_threshold, "regimes": regime_audit,
            "external_gates": external_audit,
        }
    return masks, audit


def _enhanced_metrics(
    times: Sequence[pd.Timestamp], selected: np.ndarray, gross: np.ndarray, horizon: int,
) -> dict[str, object]:
    metrics = _trade_metrics(times, selected.astype(float), gross, 1.0, holding_minutes=horizon)
    indices = np.asarray(metrics.pop("selected_indices"), dtype=np.int64)
    net = gross[indices] - COST if len(indices) else np.asarray([], dtype=float)
    gross_values = gross[indices] if len(indices) else np.asarray([], dtype=float)
    equity = np.cumsum(net)
    peak = np.maximum.accumulate(np.r_[0.0, equity])[-len(equity):] if len(equity) else np.asarray([])
    losses = -net[net < 0.0].sum()
    standard_error = float(net.std(ddof=1) / math.sqrt(len(net)) * 1e4) if len(net) > 1 else None
    metrics.update({
        "mean_gross_bps": float(gross_values.mean() * 1e4) if len(gross_values) else 0.0,
        "win_rate_after_cost": float(np.mean(net > 0.0)) if len(net) else 0.0,
        "profit_factor": float(net[net > 0.0].sum() / losses) if losses else None,
        "mdd": float((equity - peak).min()) if len(equity) else 0.0,
        "mean_net_bps_ci95": (
            [float(metrics["mean_net_bps"] - 1.96 * standard_error),
             float(metrics["mean_net_bps"] + 1.96 * standard_error)] if standard_error is not None else None
        ),
        "trend_continuation_rate": float(np.mean(gross_values < 0.0)) if len(gross_values) else 0.0,
        "sample_note": "low_sample" if len(net) < 30 else "reported_without_trade_count_filter",
    })
    return metrics


def run_experiment(
    input_path: Path, metrics_dir: Path, funding_dir: Path, premium_dir: Path,
    output: Path = RUN_ROOT, trials: int = 12, horizons: Sequence[int] = HORIZONS,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing experiment directory: {output}")
    output.mkdir(parents=True)
    try:
        _status(output, "running", "features", "rebuilding source features and separating fast entry from slow regime")
        frame = add_fast_regime_features(build_features(input_path, metrics_dir, funding_dir, premium_dir))
        values = frame.loc[:, list(MODEL_FEATURE_NAMES)].to_numpy(np.float32)
        finite_features = np.isfinite(values).all(axis=1)
        sequence_valid = pd.Series(finite_features).rolling(
            SEQUENCE_LENGTH, min_periods=SEQUENCE_LENGTH,
        ).sum().eq(SEQUENCE_LENGTH).to_numpy()
        feature_report = {
            "model_feature_names": list(MODEL_FEATURE_NAMES),
            "added_fast_feature_names": list(ADDED_FAST_FEATURE_NAMES),
            "slow_regime_feature_names": list(SLOW_REGIME_FEATURE_NAMES),
            "regime_feature_names": list(REGIME_FEATURE_NAMES),
            "slow_features_excluded_from_model": not bool(set(SLOW_REGIME_FEATURE_NAMES) & set(MODEL_FEATURE_NAMES)),
            "feature_cache_used": False,
        }
        _write_json(output / "features.json", feature_report)
        results: dict[str, object] = {
            "designation": "posthoc_fast_feature_regime_research", "live_approval_eligible": False,
            "training_target": "signed_short_horizon_return_minus_4bps", "trials_per_family_per_fold": trials,
            "quantiles": list(QUANTILES), "trade_count_filter": None, "features": feature_report, "horizons": {},
        }
        for horizon in horizons:
            gross = short_gross_return(frame, int(horizon))
            target_bps = (gross - COST) * 1e4
            valid = sequence_valid & np.isfinite(gross)
            folds = walk_forward_folds(purge_bars=int(horizon))
            horizon_result: dict[str, object] = {
                "feature_diagnostics": feature_diagnostics(frame, gross, int(horizon)), "models": {},
            }
            for family in ("catboost", "lightgbm", "gru"):
                _status(output, "running", f"h{horizon}_{family}", f"tuning {family} on H{horizon}")
                all_times: list[pd.Timestamp] = []
                all_gross: list[float] = []
                selections = {
                    _quantile_key(q): {name: [] for name in ("regime_unfiltered", "regime_filtered", *REGIME_NAMES)}
                    for q in QUANTILES
                }
                fold_reports = []
                for fold in folds:
                    train_all = _indices(frame.open_time, fold.train_start, fold.train_end, valid)
                    validation_all = _indices(frame.open_time, fold.validation_start, fold.validation_end, valid)
                    test = _indices(frame.open_time, fold.test_start, fold.test_end, valid)
                    train = train_all[::int(horizon)]
                    validation_tune = validation_all[::int(horizon)]
                    if min(len(train), len(validation_tune), len(validation_all), len(test)) == 0:
                        continue
                    thresholds = fit_regime_thresholds(frame, train_all)
                    regimes = assign_regimes(frame, thresholds)
                    model, _, tuning = tune_fold(
                        family, values, target_bps, train, validation_tune, trials,
                    )
                    validation_scores = _prediction(model, family, values, validation_all)
                    test_scores = _prediction(model, family, values, test)
                    fold_masks, threshold_audit = fold_signal_masks(
                        frame.iloc[validation_all].open_time.tolist(), validation_scores, gross[validation_all],
                        regimes[validation_all], test_scores, regimes[test], int(horizon),
                    )
                    all_times.extend(frame.iloc[test].open_time.tolist())
                    all_gross.extend(gross[test].tolist())
                    for quantile_key, modes in fold_masks.items():
                        for mode, mask in modes.items():
                            selections[quantile_key][mode].extend(mask.tolist())
                    fold_reports.append({
                        "fold": fold.index, "test_start": fold.test_start.isoformat(),
                        "test_end": fold.test_end.isoformat(), "train_rows": len(train),
                        "validation_rows": len(validation_all), "test_rows": len(test),
                        "regime_thresholds_from_train_only": thresholds, "tuning": tuning,
                        "thresholds_and_validation_gates": threshold_audit,
                    })
                    del model
                    gc.collect()
                    _status(output, "running", f"h{horizon}_{family}",
                            f"completed fold {fold.index + 1}/{len(folds)} for {family} H{horizon}")
                gross_oof = np.asarray(all_gross, dtype=float)
                model_quantiles = {}
                for quantile_key, modes in selections.items():
                    model_quantiles[quantile_key] = {
                        mode: _enhanced_metrics(all_times, np.asarray(mask, dtype=bool), gross_oof, int(horizon))
                        for mode, mask in modes.items()
                    }
                model_result = {
                    "model_family": "pytorch_gru" if family == "gru" else family,
                    "sequence_length": SEQUENCE_LENGTH if family == "gru" else None,
                    "folds": fold_reports, "quantiles": model_quantiles,
                }
                horizon_result["models"][family] = model_result  # type: ignore[index]
                _write_json(output / f"h{horizon}_{family}.json", model_result)
            results["horizons"][str(horizon)] = horizon_result  # type: ignore[index]
        _write_json(output / "fast_regime_results.json", results)
        _status(output, "complete", "complete", "fast-feature regime experiment completed")
        return results
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
    parser.add_argument("--trials", type=int, default=12)
    parser.add_argument("--horizons", type=int, nargs="+", choices=HORIZONS, default=list(HORIZONS))
    args = parser.parse_args(argv)
    run_experiment(
        args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir,
        trials=args.trials, horizons=args.horizons,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
