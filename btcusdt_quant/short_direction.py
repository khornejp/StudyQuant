"""Direct H15 short-direction experiment using symmetric first-touch classes."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from .funding_source import estimate_funding_rate_minutes
from .gru import SEQUENCE_LENGTH
from .short_fast_ablation import FAST_DERIVATIVE_FEATURES, REFERENCE, _reference_params
from .short_fast_regime import (
    QUANTILES,
    REGIME_NAMES,
    _enhanced_metrics,
    _fit_gru,
    _predict_gru,
    _quantile_key,
    _safe_ic,
    _sequence_batch,
    add_fast_regime_features,
    assign_regimes,
    fit_regime_thresholds,
)
from .short_sequence import COST, _indices, _status, _trade_metrics, _write_json, build_features, walk_forward_folds


RUN_ROOT = Path("artifacts/short_direction_experiment_20260830")
HORIZON = 15
BARRIER = 0.002
UP, NEUTRAL, DOWN = 0, 1, 2
SIGNED_FEATURE_NAMES = (
    "signed_body_pct",
    "taker_imbalance_3m", "taker_imbalance_5m", "taker_imbalance_10m", "taker_imbalance_15m",
    "taker_imbalance_impulse_3_15",
    "return_5_x_oi_change_5m", "return_15_x_oi_change_15m",
    "premium_change_5m", "premium_zscore_20",
)
SIGNED_DIRECTION_FEATURES = (*FAST_DERIVATIVE_FEATURES, *SIGNED_FEATURE_NAMES)
FUNDING_FEATURE_NAMES = (
    "funding_rate",
    "estimated_funding_rate_capped",
    "estimated_funding_pressure_uncapped",
    "funding_cap_excess",
    "funding_pressure_change_15m",
    "minutes_to_funding",
)
FUNDING_DIRECTION_FEATURES = (*SIGNED_DIRECTION_FEATURES, *FUNDING_FEATURE_NAMES)
SHORT_HORIZON_FUNDING_FEATURE_NAMES = (
    "funding_rate",
    "estimated_funding_pressure_uncapped",
    "funding_pressure_change_5m",
    "funding_pressure_change_15m",
    "funding_pressure_change_30m",
    "funding_pressure_change_60m",
    "funding_pressure_acceleration_15m",
    "funding_pressure_zscore_8h",
    "funding_pressure_zscore_24h",
    "minutes_to_funding",
)
SHORT_HORIZON_DIRECTION_FEATURES = (*SIGNED_DIRECTION_FEATURES, *SHORT_HORIZON_FUNDING_FEATURE_NAMES)
SHORT_ORIENTED_FEATURE_NAMES = (
    "short_return_1", "short_return_3", "short_return_5", "short_return_10", "short_return_15",
    "short_body", "short_close_location", "short_shadow_rejection",
    "short_ema_gap_5", "short_ema_gap_10", "short_ema_gap_15",
    "short_close_zscore_5", "short_close_zscore_10", "short_close_zscore_15",
    "short_voladj_return_5",
    "taker_sell_imbalance_1m", "taker_sell_imbalance_3m", "taker_sell_imbalance_5m",
    "taker_sell_imbalance_15m", "taker_sell_impulse_3_15", "signed_sell_volume_intensity_5m",
    "short_return_5_x_oi_change_5m", "short_return_15_x_oi_change_15m",
    "long_crowding_change_5m", "taker_sell_ls_change_5m", "premium_short_pressure_change_5m",
    "estimated_funding_pressure_uncapped", "funding_pressure_change_5m",
    "funding_pressure_change_15m", "funding_pressure_acceleration_15m",
)
MAGNITUDE_CONTEXT_FEATURE_NAMES = ("high_low_range", "body_pct", "rv_5", "rv_15", "atr_pct")
SHORT_ORIENTED_WITH_MAGNITUDE_FEATURE_NAMES = (*SHORT_ORIENTED_FEATURE_NAMES, *MAGNITUDE_CONTEXT_FEATURE_NAMES)


def add_signed_direction_features(frame: pd.DataFrame) -> pd.DataFrame:
    close = frame["close"].astype(float)
    volume = frame["volume"].astype(float)
    signed_taker_volume = 2.0 * frame["taker_buy_base_volume"].astype(float) - volume
    frame["signed_body_pct"] = (close - frame["open"].astype(float)) / close.where(close != 0.0)
    for window in (3, 5, 10, 15):
        total_volume = volume.rolling(window, min_periods=window).sum()
        frame[f"taker_imbalance_{window}m"] = (
            signed_taker_volume.rolling(window, min_periods=window).sum()
            / total_volume.where(total_volume != 0.0)
        ).fillna(0.0)
    frame["taker_imbalance_impulse_3_15"] = frame["taker_imbalance_3m"] - frame["taker_imbalance_15m"]
    frame["return_5_x_oi_change_5m"] = frame["return_5"] * frame["oi_change_rate_5m"]
    frame["return_15_x_oi_change_15m"] = close.pct_change(15).fillna(0.0) * frame["oi_change_rate_15m"]
    premium = frame["premium_index"].astype(float)
    frame["premium_change_5m"] = premium.diff(5).fillna(0.0)
    premium_mean = premium.rolling(20, min_periods=20).mean()
    premium_std = premium.rolling(20, min_periods=20).std(ddof=0)
    frame["premium_zscore_20"] = ((premium - premium_mean) / premium_std.where(premium_std != 0.0)).fillna(0.0)
    return frame


def add_funding_direction_features(frame: pd.DataFrame) -> pd.DataFrame:
    uncapped = estimate_funding_rate_minutes(frame["premium_index"], frame["funding_rate"])
    capped = np.clip(uncapped, -0.003, 0.003)
    frame["estimated_funding_rate_capped"] = capped
    frame["estimated_funding_pressure_uncapped"] = uncapped
    frame["funding_cap_excess"] = uncapped - capped
    frame["funding_pressure_change_15m"] = pd.Series(uncapped, index=frame.index).diff(15).fillna(0.0)
    minute = frame["open_time"].dt.hour.to_numpy() * 60 + frame["open_time"].dt.minute.to_numpy()
    remainder = minute % 480
    frame["minutes_to_funding"] = np.where(remainder == 0, 480, 480 - remainder)
    return frame


def add_short_horizon_funding_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add funding changes for H15, with z-score baselines ending at t-1."""
    frame = add_funding_direction_features(frame)
    pressure = frame["estimated_funding_pressure_uncapped"].astype(float)
    for lag in (5, 30, 60):
        frame[f"funding_pressure_change_{lag}m"] = pressure.diff(lag)
    change_15m = frame["funding_pressure_change_15m"].astype(float)
    frame["funding_pressure_acceleration_15m"] = change_15m - change_15m.shift(15)
    prior = pressure.shift(1)
    for hours in (8, 24):
        window = hours * 60
        mean = prior.rolling(window, min_periods=window).mean()
        std = prior.rolling(window, min_periods=window).std(ddof=0)
        frame[f"funding_pressure_zscore_{hours}h"] = (pressure - mean) / std.where(std > 0.0)
    return frame


def add_short_oriented_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build signed relative H15 inputs, oriented so positive means short pressure."""
    close = frame["close"].astype(float)
    for lag in (1, 3, 5):
        frame[f"short_return_{lag}"] = -frame[f"return_{lag}"].astype(float)
    for lag in (10, 15):
        frame[f"short_return_{lag}"] = -close.pct_change(lag)
    frame["short_body"] = (frame["open"].astype(float) - close) / close.where(close != 0.0)
    frame["short_close_location"] = -frame["close_location_value"].astype(float)
    frame["short_shadow_rejection"] = (
        frame["upper_shadow"].astype(float) - frame["lower_shadow"].astype(float)
    )
    for span in (5, 10, 15):
        ema = close.ewm(span=span, adjust=False, min_periods=span).mean()
        frame[f"short_ema_gap_{span}"] = (ema - close) / close.where(close != 0.0)
        mean = close.rolling(span, min_periods=span).mean()
        std = close.rolling(span, min_periods=span).std(ddof=0)
        frame[f"short_close_zscore_{span}"] = (mean - close) / std.where(std > 0.0)
    rv_5 = close.pct_change().rolling(5, min_periods=5).std(ddof=0) * np.sqrt(5.0)
    frame["short_voladj_return_5"] = frame["short_return_5"] / rv_5.where(rv_5 > 0.0)
    frame["taker_sell_imbalance_1m"] = -frame["taker_imbalance"].astype(float)
    for lag in (3, 5, 15):
        frame[f"taker_sell_imbalance_{lag}m"] = -frame[f"taker_imbalance_{lag}m"].astype(float)
    frame["taker_sell_impulse_3_15"] = (
        frame["taker_sell_imbalance_3m"] - frame["taker_sell_imbalance_15m"]
    )
    volume = frame["volume"].astype(float)
    volume_ratio_5m = volume / volume.rolling(5, min_periods=5).mean().where(lambda values: values > 0.0)
    frame["signed_sell_volume_intensity_5m"] = frame["taker_sell_imbalance_5m"] * volume_ratio_5m
    frame["short_return_5_x_oi_change_5m"] = frame["short_return_5"] * frame["oi_change_rate_5m"]
    frame["short_return_15_x_oi_change_15m"] = frame["short_return_15"] * frame["oi_change_rate_15m"]
    frame["long_crowding_change_5m"] = frame["global_ls_account_change_5m"].astype(float)
    frame["taker_sell_ls_change_5m"] = -frame["taker_ls_ratio_change_5m"].astype(float)
    frame["premium_short_pressure_change_5m"] = frame["premium_change_5m"].astype(float)
    return frame


def _direction_score(probabilities: np.ndarray, mode: str) -> np.ndarray:
    if mode == "margin":
        return probabilities[:, DOWN] - probabilities[:, UP]
    if mode == "conditional":
        touched = probabilities[:, DOWN] + probabilities[:, UP]
        return np.divide(
            probabilities[:, DOWN], touched,
            out=np.full(len(probabilities), 0.5), where=touched > 0.0,
        ) - 0.5
    raise ValueError(f"unknown direction score mode: {mode}")


def _two_stage_probabilities(
    movement_probability: np.ndarray, down_given_touch_probability: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    down = movement_probability * down_given_touch_probability
    up = movement_probability * (1.0 - down_given_touch_probability)
    combined = np.column_stack((up, 1.0 - movement_probability, down))
    score = down_given_touch_probability - 0.5
    score = np.where(movement_probability >= 0.5, score, -0.5)
    return combined, score


def direction_labels(frame: pd.DataFrame, horizon: int = HORIZON, barrier: float = BARRIER):
    """Classify which symmetric barrier touches first; unresolved rows are neutral."""
    close = frame.close.to_numpy(float)
    opens = frame.open.to_numpy(float)
    highs = frame.high.to_numpy(float)
    lows = frame.low.to_numpy(float)
    labels = np.full(len(frame), NEUTRAL, dtype=np.int8)
    gross = np.full(len(frame), np.nan, dtype=float)
    unresolved = np.arange(len(frame)) + horizon < len(frame)
    for step in range(1, horizon + 1):
        valid = np.arange(len(frame)) + step < len(frame)
        future_high = np.full(len(frame), np.nan); future_high[valid] = highs[step:]
        future_low = np.full(len(frame), np.nan); future_low[valid] = lows[step:]
        future_open = np.full(len(frame), np.nan); future_open[valid] = opens[step:]
        future_close = np.full(len(frame), np.nan); future_close[valid] = close[step:]
        down_hit = future_low <= close * (1.0 - barrier)
        up_hit = future_high >= close * (1.0 + barrier)
        hit = unresolved & (down_hit | up_hit)
        down_first = hit & down_hit & (~up_hit | (future_close < future_open))
        up_first = hit & ~down_first
        labels[down_first], gross[down_first] = DOWN, barrier
        labels[up_first], gross[up_first] = UP, -barrier
        unresolved[hit] = False
    timeout = unresolved & (np.arange(len(frame)) + horizon < len(frame))
    future_close = np.full(len(frame), np.nan); future_close[:-horizon] = close[horizon:]
    gross[timeout] = -(future_close[timeout] / close[timeout] - 1.0)
    gross[-horizon:] = np.nan
    return labels, gross


def close_short_return(frame: pd.DataFrame, horizon: int = HORIZON) -> np.ndarray:
    close = frame["close"].to_numpy(float)
    gross = np.full(len(frame), np.nan, dtype=float)
    gross[:-horizon] = -(close[horizon:] / close[:-horizon] - 1.0)
    return gross


def close_direction_labels(
    frame: pd.DataFrame, horizon: int = HORIZON, deadzone_bps: float = COST * 1e4,
) -> tuple[np.ndarray, np.ndarray]:
    gross = close_short_return(frame, horizon)
    gross_bps = gross * 1e4
    labels = np.full(len(frame), NEUTRAL, dtype=np.int8)
    labels[gross_bps > deadzone_bps] = DOWN
    labels[gross_bps < -deadzone_bps] = UP
    return labels, gross


@dataclass
class _DirectionGRU:
    model: object
    mean: np.ndarray
    std: np.ndarray
    device: object
    classes: int


def _fit_direction_gru(
    params: Mapping[str, object], values: np.ndarray, labels: np.ndarray,
    train: np.ndarray, validation: np.ndarray, classes: int = 3,
) -> _DirectionGRU:
    import torch
    import torch.nn as nn

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    mean = values[train].mean(axis=0, dtype=np.float64).astype(np.float32)
    std = values[train].std(axis=0, dtype=np.float64).astype(np.float32)
    std[std == 0.0] = 1.0
    scaled = np.clip((values - mean) / std, -10.0, 10.0).astype(np.float32)
    train_x = _sequence_batch(scaled, train)
    validation_x = _sequence_batch(scaled, validation)
    train_y, validation_y = labels[train].astype(np.int64), labels[validation].astype(np.int64)

    class Network(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            layers = int(params["num_layers"])
            dropout = float(params["dropout"]) if layers > 1 else 0.0
            self.gru = nn.GRU(
                values.shape[1], int(params["hidden_size"]), num_layers=layers,
                dropout=dropout, batch_first=True,
            )
            self.head = nn.Linear(int(params["hidden_size"]), classes)

        def forward(self, batch):
            output, _ = self.gru(batch)
            return self.head(output[:, -1])

    torch.manual_seed(42)
    np.random.seed(42)
    model = Network().to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=float(params["learning_rate"]), weight_decay=float(params["weight_decay"]),
    )
    loss_fn = nn.CrossEntropyLoss()
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(torch.from_numpy(train_x), torch.from_numpy(train_y)),
        batch_size=int(params["batch_size"]), shuffle=True,
        generator=torch.Generator().manual_seed(42), pin_memory=device.type == "cuda",
    )
    validation_x = torch.from_numpy(validation_x)
    validation_y = torch.from_numpy(validation_y)
    best_loss, best_state, stale = float("inf"), None, 0
    for _ in range(15):
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
            for start in range(0, len(validation_x), 4096):
                batch_x = validation_x[start:start + 4096].to(device)
                batch_y = validation_y[start:start + 4096].to(device)
                total += float(loss_fn(model(batch_x), batch_y)) * len(batch_y)
                count += len(batch_y)
        validation_loss = total / max(count, 1)
        if validation_loss < best_loss - 1e-6:
            best_loss, stale = validation_loss, 0
            best_state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
        else:
            stale += 1
            if stale >= 3:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return _DirectionGRU(model, mean, std, device, classes)


def _predict_direction(fitted: _DirectionGRU, values: np.ndarray, endpoints: Sequence[int]) -> np.ndarray:
    import torch

    scaled = np.clip((values - fitted.mean) / fitted.std, -10.0, 10.0).astype(np.float32)
    ends = np.asarray(endpoints, dtype=np.int64)
    probabilities = []
    with torch.no_grad():
        for start in range(0, len(ends), 4096):
            batch = torch.from_numpy(_sequence_batch(scaled, ends[start:start + 4096])).to(fitted.device)
            probabilities.append(torch.softmax(fitted.model(batch), dim=1).cpu().numpy())
    return np.concatenate(probabilities) if probabilities else np.empty((0, fitted.classes), dtype=float)


def direction_signal_masks(
    validation_times: Sequence[pd.Timestamp], validation_margin: np.ndarray, validation_gross: np.ndarray,
    validation_regimes: np.ndarray, test_margin: np.ndarray, test_regimes: np.ndarray,
) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, object]]:
    masks, audit = {}, {}
    for quantile in QUANTILES:
        key = _quantile_key(quantile)
        global_threshold = max(0.0, float(np.quantile(validation_margin, quantile)))
        raw = (test_margin > 0.0) & (test_margin >= global_threshold)
        gated = np.zeros(len(test_margin), dtype=bool)
        regime_audit = {}
        for regime in REGIME_NAMES:
            validation_mask = validation_regimes == regime
            if not validation_mask.any():
                regime_audit[regime] = {"allowed": False, "threshold": None, "validation_trades": 0}
                continue
            threshold = max(0.0, float(np.quantile(validation_margin[validation_mask], quantile)))
            selected_validation = validation_mask & (validation_margin > 0.0) & (validation_margin >= threshold)
            metrics = _trade_metrics(
                validation_times, selected_validation.astype(float), validation_gross, 1.0,
                holding_minutes=HORIZON,
            )
            allowed = float(metrics["net_return"]) > 0.0
            if allowed:
                gated |= (test_regimes == regime) & (test_margin > 0.0) & (test_margin >= threshold)
            regime_audit[regime] = {
                "allowed": allowed, "threshold": threshold, "validation_trades": metrics["trades"],
                "validation_mean_net_bps": metrics["mean_net_bps"], "validation_net_return": metrics["net_return"],
            }
        masks[key] = {"regime_unfiltered": raw, "regime_filtered": gated}
        audit[key] = {"global_threshold": global_threshold, "regimes": regime_audit}
    return masks, audit


def _classification_metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, object]:
    predicted = probabilities.argmax(axis=1)
    down_predicted = predicted == DOWN
    down_actual = labels == DOWN
    return {
        "accuracy": float(np.mean(predicted == labels)),
        "down_base_rate": float(np.mean(down_actual)),
        "up_base_rate": float(np.mean(labels == UP)),
        "neutral_base_rate": float(np.mean(labels == NEUTRAL)),
        "down_precision": float(np.mean(down_actual[down_predicted])) if down_predicted.any() else 0.0,
        "down_recall": float(np.mean(down_predicted[down_actual])) if down_actual.any() else 0.0,
    }


def run_direction_experiment(
    input_path: Path, metrics_dir: Path, funding_dir: Path, premium_dir: Path,
    output: Path = RUN_ROOT, reference: Path = REFERENCE, score_mode: str = "margin",
    two_stage_signed: bool = False, payoff_regression: bool = False,
    close_return_regression: bool = False, close_direction_funding: bool = False,
) -> dict[str, object]:
    if sum((two_stage_signed, payoff_regression, close_return_regression, close_direction_funding)) > 1:
        raise ValueError("two-stage classification and regression modes are separate experiments")
    regression = payoff_regression or close_return_regression
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing direction experiment directory: {output}")
    output.mkdir(parents=True)
    try:
        feature_names = (
            FUNDING_DIRECTION_FEATURES if close_direction_funding else
            (SIGNED_DIRECTION_FEATURES if (two_stage_signed or regression) else FAST_DERIVATIVE_FEATURES)
        )
        _status(output, "running", "features", f"rebuilding H15 {len(feature_names)}-feature directional source data")
        frame = add_fast_regime_features(build_features(input_path, metrics_dir, funding_dir, premium_dir))
        if two_stage_signed or regression or close_direction_funding:
            frame = add_signed_direction_features(frame)
        if close_direction_funding:
            frame = add_funding_direction_features(frame)
        values = frame.loc[:, list(feature_names)].to_numpy(np.float32)
        labels, gross = direction_labels(frame)
        if close_return_regression:
            gross = close_short_return(frame)
        elif close_direction_funding:
            labels, gross = close_direction_labels(frame)
        finite = np.isfinite(values).all(axis=1) & np.isfinite(gross)
        valid = pd.Series(finite).rolling(
            SEQUENCE_LENGTH, min_periods=SEQUENCE_LENGTH,
        ).sum().eq(SEQUENCE_LENGTH).to_numpy()
        params_by_fold = _reference_params(reference)
        selections = {
            _quantile_key(q): {"regime_unfiltered": [], "regime_filtered": []} for q in QUANTILES
        }
        all_times, all_gross, all_labels, all_probabilities, all_predictions = [], [], [], [], []
        fold_reports = []
        folds = walk_forward_folds(purge_bars=HORIZON)
        _status(output, "running", "oof", (
            "training H15 cost-dead-zone close-direction GRU with 1m funding estimates"
            if close_direction_funding else (
                "training signed-feature H15 close-return regression GRU"
                if close_return_regression else (
                "training signed-feature direct payoff regression GRU"
                if payoff_regression else (
                "training signed-feature two-stage movement/direction GRUs"
                if two_stage_signed else "training symmetric first-touch direction GRU"
                )
                )
            )
        ))
        for fold in folds:
            train_all = _indices(frame.open_time, fold.train_start, fold.train_end, valid)
            validation_all = _indices(frame.open_time, fold.validation_start, fold.validation_end, valid)
            test = _indices(frame.open_time, fold.test_start, fold.test_end, valid)
            train, validation_train = train_all[::HORIZON], validation_all[::HORIZON]
            thresholds = fit_regime_thresholds(frame, train_all)
            regimes = assign_regimes(frame, thresholds)
            stage_metrics = None
            if regression:
                target_bps = gross * 1e4
                model = _fit_gru(
                    params_by_fold[fold.index], values, target_bps, train, validation_train,
                )
                validation_prediction = _predict_gru(model, values, validation_all)
                test_prediction = _predict_gru(model, values, test)
                validation_margin = validation_prediction - COST * 1e4
                test_margin = test_prediction - COST * 1e4
                stage_metrics = {
                    "test_spearman_ic": _safe_ic(test_prediction, target_bps[test]),
                    "test_mae_bps": float(np.mean(np.abs(test_prediction - target_bps[test]))),
                    "cost_hurdle_bps": COST * 1e4,
                }
                test_probability = None
                del model
            elif two_stage_signed:
                movement_labels = (labels != NEUTRAL).astype(np.int8)
                down_labels = (labels == DOWN).astype(np.int8)
                touched_train = train[movement_labels[train] == 1]
                touched_validation = validation_train[movement_labels[validation_train] == 1]
                if not len(touched_train) or not len(touched_validation):
                    raise ValueError(f"fold {fold.index} has no touched rows for direction training")
                movement_model = _fit_direction_gru(
                    params_by_fold[fold.index], values, movement_labels, train, validation_train, classes=2,
                )
                direction_model = _fit_direction_gru(
                    params_by_fold[fold.index], values, down_labels,
                    touched_train, touched_validation, classes=2,
                )
                validation_movement = _predict_direction(movement_model, values, validation_all)[:, 1]
                test_movement = _predict_direction(movement_model, values, test)[:, 1]
                validation_down = _predict_direction(direction_model, values, validation_all)[:, 1]
                test_down = _predict_direction(direction_model, values, test)[:, 1]
                validation_probability, validation_margin = _two_stage_probabilities(validation_movement, validation_down)
                test_probability, test_margin = _two_stage_probabilities(test_movement, test_down)
                touched_test = movement_labels[test] == 1
                stage_metrics = {
                    "movement_base_rate": float(np.mean(touched_test)),
                    "movement_accuracy": float(np.mean((test_movement >= 0.5) == touched_test)),
                    "direction_down_base_rate_on_touched": float(np.mean(down_labels[test][touched_test])),
                    "direction_accuracy_on_touched": float(np.mean(
                        (test_down[touched_test] >= 0.5) == down_labels[test][touched_test]
                    )),
                    "touch_probability_gate": 0.5,
                }
                del movement_model, direction_model
            else:
                model = _fit_direction_gru(params_by_fold[fold.index], values, labels, train, validation_train)
                validation_probability = _predict_direction(model, values, validation_all)
                test_probability = _predict_direction(model, values, test)
                validation_margin = _direction_score(validation_probability, score_mode)
                test_margin = _direction_score(test_probability, score_mode)
                del model
            masks, audit = direction_signal_masks(
                frame.iloc[validation_all].open_time.tolist(), validation_margin, gross[validation_all],
                regimes[validation_all], test_margin, regimes[test],
            )
            for quantile, modes in selections.items():
                for mode in modes:
                    modes[mode].extend(masks[quantile][mode].tolist())
            classification = None if regression else _classification_metrics(labels[test], test_probability)
            fold_reports.append({
                "fold": fold.index, "params": params_by_fold[fold.index], "classification": classification,
                "two_stage_metrics": stage_metrics,
                "regime_thresholds_from_train_only": thresholds, "thresholds_and_validation_gates": audit,
            })
            all_times.extend(frame.iloc[test].open_time.tolist())
            all_gross.extend(gross[test].tolist())
            all_labels.extend(labels[test].tolist())
            if regression:
                all_predictions.extend(test_prediction.tolist())
            else:
                all_probabilities.extend(test_probability.tolist())
            _status(output, "running", "oof", f"completed fold {fold.index + 1}/{len(folds)}")
        gross_oof = np.asarray(all_gross, dtype=float)
        summaries, comparison = {}, []
        for quantile, modes in selections.items():
            summaries[quantile] = {}
            for mode, mask in modes.items():
                metrics = _enhanced_metrics(all_times, np.asarray(mask, dtype=bool), gross_oof, HORIZON)
                summaries[quantile][mode] = metrics
                comparison.append({"quantile": quantile, "regime_mode": mode, **metrics})
        comparison.sort(key=lambda row: float(row["mean_net_bps"]), reverse=True)
        result = {
            "designation": (
                "posthoc_close_direction_funding_diagnostic" if close_direction_funding else
                ("posthoc_close_return_diagnostic" if close_return_regression else
                ("posthoc_direct_payoff_diagnostic" if payoff_regression else "posthoc_direction_target_diagnostic")
                )
            ),
            "live_approval_eligible": False,
            "target": (
                {"name": "H15_cost_dead_zone_close_direction",
                 "classes": {"0": "long_edge_below_-4bps", "1": "neutral_within_4bps", "2": "short_edge_above_4bps"},
                 "deadzone_bps": COST * 1e4, "horizon": HORIZON}
                if close_direction_funding else (
                {"name": "H15_close_to_close_short_return_bps", "horizon": HORIZON}
                if close_return_regression else (
                {"name": "realized_short_gross_payoff_bps", "down_touch_bps": BARRIER * 1e4,
                 "up_touch_bps": -BARRIER * 1e4, "timeout": "H15 close-to-close short return",
                 "horizon": HORIZON}
                if payoff_regression else
                {"classes": {"0": "up_first", "1": "neutral_timeout", "2": "down_first"},
                 "barrier_bps": BARRIER * 1e4, "horizon": HORIZON}
                )
                )
            ),
            "score": (
                "P(H15 short edge above 4bps)-P(H15 long edge below -4bps)"
                if close_direction_funding else (
                "predicted H15 close-to-close gross short return bps - 4 bps round-trip cost"
                if close_return_regression else (
                    "predicted gross short payoff bps - 4 bps round-trip cost"
                    if payoff_regression else (
                    "P(down_first|touch)-0.5, with P(touch)>=0.5"
                    if two_stage_signed else (
                    "P(down_first)/(P(down_first)+P(up_first))-0.5"
                    if score_mode == "conditional" else "P(down_first)-P(up_first)"
                    )
                    )
                )
                )
            ),
            "score_mode": (
                "cost_dead_zone_close_direction" if close_direction_funding else
                ("close_return_minus_cost" if close_return_regression else
                ("direct_payoff_minus_cost" if payoff_regression else
                ("two_stage_conditional" if two_stage_signed else score_mode)
                )
                )
            ),
            "model": (
                "close_direction_funding_gru" if close_direction_funding else
                ("close_return_regression_gru" if close_return_regression else
                ("payoff_regression_gru" if payoff_regression else
                ("two_stage_gru" if two_stage_signed else "three_class_gru")
                )
                )
            ),
            "positive_margin_required": True,
            "trade_count_filter": None, "feature_names": list(feature_names),
            "folds": fold_reports,
            "oof_classification": None if regression else _classification_metrics(
                np.asarray(all_labels, dtype=np.int8), np.asarray(all_probabilities, dtype=float)),
            "oof_regression": ({
                "spearman_ic": _safe_ic(np.asarray(all_predictions), gross_oof * 1e4),
                "mae_bps": float(np.mean(np.abs(np.asarray(all_predictions) - gross_oof * 1e4))),
            } if regression else None),
            "quantiles": summaries, "comparison": comparison,
        }
        result_name = (
            "h15_close_direction_funding_results.json" if close_direction_funding else
            ("h15_close_return_results.json" if close_return_regression else
            ("h15_payoff_results.json" if payoff_regression else "h15_direction_results.json")
            )
        )
        _write_json(output / result_name, result)
        _status(output, "complete", "complete", (
            "H15 close-direction funding experiment completed" if close_direction_funding else
            ("H15 close-return experiment completed" if close_return_regression else
            ("H15 direct-payoff experiment completed" if payoff_regression else "H15 direct-direction experiment completed")
            )
        ))
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
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--output", type=Path, default=RUN_ROOT)
    parser.add_argument("--score-mode", choices=("margin", "conditional"), default="margin")
    parser.add_argument("--two-stage-signed", action="store_true")
    parser.add_argument("--payoff-regression", action="store_true")
    parser.add_argument("--close-return-regression", action="store_true")
    parser.add_argument("--close-direction-funding", action="store_true")
    args = parser.parse_args(argv)
    run_direction_experiment(
        args.input, args.metrics_dir, args.funding_dir, args.premium_index_dir,
        output=args.output, reference=args.reference, score_mode=args.score_mode,
        two_stage_signed=args.two_stage_signed, payoff_regression=args.payoff_regression,
        close_return_regression=args.close_return_regression,
        close_direction_funding=args.close_direction_funding,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
