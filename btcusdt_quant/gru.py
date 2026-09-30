"""Fixed 60-bar GRU used by the short-sequence research experiment."""
from __future__ import annotations

import io
from collections import deque
from typing import Mapping, Sequence

import numpy as np
import torch
import torch.nn as nn

from . import models


SEQUENCE_LENGTH = 60
GRU_FEATURE_NAMES: tuple[str, ...] = (
    "return_1", "return_3", "return_5", "log_return_1",
    "high_low_range", "body_pct", "upper_shadow", "lower_shadow", "close_location_value",
    "volume_sma_20_ratio", "volume_zscore_20", "quote_volume_sma_20_ratio",
    "taker_ratio", "taker_imbalance", "taker_quote_ratio",
    "trade_count_ratio", "trade_count_zscore_20",
    "rv_5", "rv_15", "rv_30", "rv_60", "atr_pct",
    "funding_rate", "premium_index", "oi_change_rate_5m", "oi_change_rate_15m",
    "global_ls_account_change_5m", "taker_ls_ratio_change_5m",
)


class _GRU(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.gru = nn.GRU(input_dim, 64, num_layers=1, batch_first=True)
        self.head = nn.Linear(64, 1)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        output, _ = self.gru(values)
        return self.head(output[:, -1]).squeeze(1)


class GRUAdapter(models.ModelAdapter):
    """One fixed GRU; hyperparameters intentionally have no public knobs."""

    def __init__(
        self,
        feature_names: Sequence[str] = GRU_FEATURE_NAMES,
        scaler_mean: Sequence[float] | None = None,
        scaler_std: Sequence[float] | None = None,
        train_target: str = "short_profitability",
    ) -> None:
        self.feature_names = tuple(feature_names)
        if self.feature_names != GRU_FEATURE_NAMES:
            raise ValueError("pytorch_gru requires the fixed 28-feature order")
        self.scaler_mean = None if scaler_mean is None else np.asarray(scaler_mean, dtype=np.float32)
        self.scaler_std = None if scaler_std is None else np.asarray(scaler_std, dtype=np.float32)
        self.train_target = str(train_target)
        self._model = _GRU(len(self.feature_names))
        self._history: deque[list[float]] = deque(maxlen=SEQUENCE_LENGTH)

    @property
    def model_family(self) -> str:
        return "pytorch_gru"

    @property
    def ready(self) -> bool:
        return len(self._history) == SEQUENCE_LENGTH

    def reset_history(self) -> None:
        self._history.clear()

    @staticmethod
    def fit_scaler(training_rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        rows = np.asarray(training_rows, dtype=np.float32)
        if rows.ndim != 2 or rows.shape[1] != len(GRU_FEATURE_NAMES):
            raise ValueError("training_rows must have shape (rows, 28)")
        if not np.isfinite(rows).all():
            raise ValueError("GRU training features contain NaN or infinity")
        mean = rows.mean(axis=0, dtype=np.float64).astype(np.float32)
        std = rows.std(axis=0, dtype=np.float64).astype(np.float32)
        std[std == 0.0] = 1.0
        return mean, std

    def _scaled(self, sequences: np.ndarray) -> np.ndarray:
        if self.scaler_mean is None or self.scaler_std is None:
            raise RuntimeError("GRU scaler is not fitted")
        values = np.asarray(sequences, dtype=np.float32)
        if values.ndim != 3 or values.shape[1:] != (SEQUENCE_LENGTH, len(self.feature_names)):
            raise ValueError("GRU input must have shape (rows, 60, 28)")
        if not np.isfinite(values).all():
            raise ValueError("GRU input contains NaN or infinity")
        return np.clip((values - self.scaler_mean) / self.scaler_std, -10.0, 10.0)

    def fit(
        self,
        feature_matrix: models.FeatureMatrix,
        labels: Sequence[int],
        sample_weight: Sequence[float] | None = None,
    ) -> "GRUAdapter":
        sequences = np.asarray(feature_matrix, dtype=np.float32)
        if sequences.ndim != 3:
            raise ValueError("pytorch_gru needs explicit 60-bar sequences; use the short-sequence experiment runner")
        if len(sequences) != len(labels) or len(sequences) < 2:
            raise ValueError("GRU sequences and labels must have equal non-trivial length")
        if sample_weight is not None:
            raise ValueError("pytorch_gru does not use sample weights")
        self.scaler_mean, self.scaler_std = self.fit_scaler(sequences.reshape(-1, sequences.shape[-1]))
        scaled = self._scaled(sequences)
        y = np.asarray(labels, dtype=np.float32)
        split = min(len(y) - 1, max(1, int(len(y) * 0.9)))

        torch.manual_seed(42)
        np.random.seed(42)
        self._model = _GRU(len(self.feature_names))
        optimizer = torch.optim.AdamW(self._model.parameters(), lr=1e-3, weight_decay=1e-5)
        loss_fn = nn.BCEWithLogitsLoss()
        best_loss, best_state, stale = float("inf"), None, 0
        generator = torch.Generator().manual_seed(42)
        train_data = torch.utils.data.TensorDataset(torch.from_numpy(scaled[:split]), torch.from_numpy(y[:split]))
        loader = torch.utils.data.DataLoader(train_data, batch_size=1024, shuffle=True, generator=generator)
        valid_x, valid_y = torch.from_numpy(scaled[split:]), torch.from_numpy(y[split:])
        for _ in range(15):
            self._model.train()
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                loss = loss_fn(self._model(batch_x), batch_y)
                loss.backward()
                optimizer.step()
            self._model.eval()
            with torch.no_grad():
                validation_loss = float(loss_fn(self._model(valid_x), valid_y))
            if validation_loss < best_loss - 1e-6:
                best_loss, stale = validation_loss, 0
                best_state = {name: tensor.detach().clone() for name, tensor in self._model.state_dict().items()}
            else:
                stale += 1
                if stale >= 3:
                    break
        if best_state is not None:
            self._model.load_state_dict(best_state)
        self._model.eval()
        return self

    def fit_rows(
        self,
        rows: np.ndarray,
        labels: Sequence[int],
        endpoints: Sequence[int] | None = None,
    ) -> "GRUAdapter":
        """Fit from chronological rows without materialising overlapping sequences."""
        values = np.asarray(rows, dtype=np.float32)
        y = np.asarray(labels, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != len(self.feature_names) or len(values) != len(y):
            raise ValueError("GRU rows must have shape (rows, 28) and one label per row")
        if len(values) <= SEQUENCE_LENGTH:
            raise ValueError("GRU needs more than 60 chronological rows")
        endpoint_values = np.asarray(
            list(endpoints) if endpoints is not None else range(SEQUENCE_LENGTH - 1, len(values)),
            dtype=np.int64,
        )
        if len(endpoint_values) < 2 or endpoint_values.min() < SEQUENCE_LENGTH - 1 or endpoint_values.max() >= len(values):
            raise ValueError("GRU endpoints must identify at least two complete in-range sequences")
        scaler_slice = values[max(0, int(endpoint_values.min()) - SEQUENCE_LENGTH + 1):int(endpoint_values.max()) + 1]
        scaler_rows = scaler_slice[np.isfinite(scaler_slice).all(axis=1)]
        self.scaler_mean, self.scaler_std = self.fit_scaler(scaler_rows)
        scaled = np.clip((values - self.scaler_mean) / self.scaler_std, -10.0, 10.0)
        split = min(len(endpoint_values) - 1, max(1, int(len(endpoint_values) * 0.9)))

        class _Windows(torch.utils.data.Dataset):
            def __init__(self, end: np.ndarray) -> None:
                self.end = end
            def __len__(self) -> int:
                return len(self.end)
            def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
                stop = int(self.end[index]) + 1
                return torch.from_numpy(scaled[stop - SEQUENCE_LENGTH:stop]), torch.tensor(y[stop - 1])

        torch.manual_seed(42)
        np.random.seed(42)
        self._model = _GRU(len(self.feature_names))
        optimizer = torch.optim.AdamW(self._model.parameters(), lr=1e-3, weight_decay=1e-5)
        loss_fn = nn.BCEWithLogitsLoss()
        loader = torch.utils.data.DataLoader(
            _Windows(endpoint_values[:split]), batch_size=1024, shuffle=True,
            generator=torch.Generator().manual_seed(42),
        )
        valid_loader = torch.utils.data.DataLoader(_Windows(endpoint_values[split:]), batch_size=4096)
        best_loss, best_state, stale = float("inf"), None, 0
        for _ in range(15):
            self._model.train()
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                loss = loss_fn(self._model(batch_x), batch_y)
                loss.backward()
                optimizer.step()
            self._model.eval()
            total, count = 0.0, 0
            with torch.no_grad():
                for batch_x, batch_y in valid_loader:
                    total += float(loss_fn(self._model(batch_x), batch_y)) * len(batch_y)
                    count += len(batch_y)
            validation_loss = total / max(count, 1)
            if validation_loss < best_loss - 1e-6:
                best_loss, stale = validation_loss, 0
                best_state = {name: tensor.detach().clone() for name, tensor in self._model.state_dict().items()}
            else:
                stale += 1
                if stale >= 3:
                    break
        if best_state is not None:
            self._model.load_state_dict(best_state)
        self._model.eval()
        return self

    def predict_rows(self, rows: np.ndarray) -> list[float]:
        """Score every causal 60-row window in a chronological context."""
        values = np.asarray(rows, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != len(self.feature_names):
            raise ValueError("GRU rows must have shape (rows, 28)")
        if not np.isfinite(values).all():
            raise ValueError("GRU input contains NaN or infinity")
        if len(values) < SEQUENCE_LENGTH:
            return []
        scaled = np.clip((values - self.scaler_mean) / self.scaler_std, -10.0, 10.0)
        probabilities: list[float] = []
        self._model.eval()
        with torch.no_grad():
            for start in range(SEQUENCE_LENGTH - 1, len(scaled), 4096):
                stops = range(start, min(len(scaled), start + 4096))
                batch = np.stack([scaled[stop - SEQUENCE_LENGTH + 1:stop + 1] for stop in stops])
                probabilities.extend(torch.sigmoid(self._model(torch.from_numpy(batch))).tolist())
        return [float(value) for value in probabilities]

    def predict_endpoints(self, rows: np.ndarray, endpoints: Sequence[int]) -> list[float]:
        values = np.asarray(rows, dtype=np.float32)
        ends = [int(value) for value in endpoints]
        if not ends:
            return []
        if min(ends) < SEQUENCE_LENGTH - 1 or max(ends) >= len(values):
            raise ValueError("GRU endpoint is outside the available causal context")
        sequences = np.stack([values[end - SEQUENCE_LENGTH + 1:end + 1] for end in ends])
        return self.predict_proba(sequences)

    def predict_proba(self, feature_matrix: models.FeatureMatrix) -> list[float]:
        scaled = self._scaled(np.asarray(feature_matrix, dtype=np.float32))
        self._model.eval()
        probabilities: list[float] = []
        with torch.no_grad():
            for start in range(0, len(scaled), 4096):
                probabilities.extend(torch.sigmoid(self._model(torch.from_numpy(scaled[start:start + 4096]))).tolist())
        if not all(0.0 <= value <= 1.0 for value in probabilities):
            raise RuntimeError("GRU produced an invalid probability")
        return probabilities

    def probability(self, values: Mapping[str, float]) -> float:
        row = [float(values[name]) for name in self.feature_names]
        if not np.isfinite(row).all():
            raise ValueError("GRU input contains NaN or infinity")
        self._history.append(row)
        if not self.ready:
            return 0.5
        return self.predict_proba(np.asarray([self._history], dtype=np.float32))[0]

    def as_dict(self) -> dict[str, object]:
        if self.scaler_mean is None or self.scaler_std is None:
            raise RuntimeError("cannot save an unfitted GRU")
        buffer = io.BytesIO()
        torch.save(self._model.state_dict(), buffer)
        return {
            "model_family": self.model_family,
            "sequence_length": SEQUENCE_LENGTH,
            "feature_names": list(self.feature_names),
            "scaler_mean": self.scaler_mean.tolist(),
            "scaler_std": self.scaler_std.tolist(),
            "state_dict": buffer.getvalue().hex(),
            "train_target": self.train_target,
            "label_tp_pct": 0.006,
            "label_sl_pct": 0.012,
            "label_horizon": 45,
            "label_geometry": {"short": {"tp_pct": 0.006, "sl_pct": 0.012}},
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "GRUAdapter":
        if int(payload.get("sequence_length", 0)) != SEQUENCE_LENGTH:
            raise ValueError("pytorch_gru artifact must use 60 bars")
        adapter = cls(
            feature_names=tuple(str(value) for value in payload.get("feature_names", ())),
            scaler_mean=tuple(float(value) for value in payload.get("scaler_mean", ())),
            scaler_std=tuple(float(value) for value in payload.get("scaler_std", ())),
            train_target=str(payload.get("train_target", "short_profitability")),
        )
        if adapter.scaler_mean.shape != (len(GRU_FEATURE_NAMES),) or adapter.scaler_std.shape != (len(GRU_FEATURE_NAMES),):
            raise ValueError("pytorch_gru artifact has invalid scaler statistics")
        state_hex = str(payload.get("state_dict", ""))
        if not state_hex:
            raise ValueError("pytorch_gru artifact is missing state_dict")
        state = torch.load(io.BytesIO(bytes.fromhex(state_hex)), map_location="cpu", weights_only=True)
        adapter._model.load_state_dict(state)
        adapter._model.eval()
        for name in ("label_tp_pct", "label_sl_pct", "label_horizon", "label_geometry"):
            if name in payload:
                object.__setattr__(adapter, name, payload[name])
        return adapter
