"""PyTorch multitask neural network adapter."""
from __future__ import annotations

import io
import json
import math
from typing import Any, Mapping, Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from . import models


class _MultitaskBackbone(nn.Module):
    """Shared feature extractor."""

    def __init__(self, input_dim: int, hidden_dims: tuple[int, ...] = (128, 64)) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        prev = input_dim
        for hidden in hidden_dims:
            layers.append(nn.Linear(prev, hidden))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            prev = hidden
        self.net = nn.Sequential(*layers)
        self.output_dim = prev

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class _MultitaskHead(nn.Module):
    """Single binary classification head."""

    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.linear = nn.Linear(input_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)


class MultitaskNN(nn.Module):
    """Shared backbone with direction and profitability heads."""

    def __init__(self, input_dim: int, hidden_dims: tuple[int, ...] = (128, 64)) -> None:
        super().__init__()
        self.backbone = _MultitaskBackbone(input_dim, hidden_dims)
        self.direction_head = _MultitaskHead(self.backbone.output_dim)
        self.profitability_head = _MultitaskHead(self.backbone.output_dim)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        shared = self.backbone(x)
        direction_logit = self.direction_head(shared)
        profitability_logit = self.profitability_head(shared)
        return direction_logit, profitability_logit


class MultitaskNNAdapter(models.ModelAdapter):
    """Adapter for MultitaskNN to fit ModelAdapter protocol.

    ``task`` controls which head's probability is returned by ``probability()``:
    ``direction`` or ``profitability``.
    """

    def __init__(
        self,
        input_dim: int = 0,
        hidden_dims: tuple[int, ...] = (128, 64),
        task: str = "profitability",
        feature_names: tuple[str, ...] = (),
        epochs: int = 100,
        batch_size: int = 256,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        early_stopping_patience: int = 10,
        device: str = "cpu",
    ) -> None:
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.task = task
        self.feature_names = tuple(feature_names)
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.early_stopping_patience = early_stopping_patience
        self.device = device
        self._model: MultitaskNN | None = None
        if input_dim > 0:
            self._model = MultitaskNN(input_dim, hidden_dims).to(device)

    @property
    def model_family(self) -> str:
        return "pytorch_multitask"

    def _ensure_model(self) -> MultitaskNN:
        if self._model is None:
            raise RuntimeError("MultitaskNNAdapter has no model. Call fit() or load from dict first.")
        return self._model

    def fit(
        self,
        feature_matrix: models.FeatureMatrix,
        labels: Sequence[int],
        sample_weight: Sequence[float] | None = None,
    ) -> "MultitaskNNAdapter":
        import numpy as np

        X = np.array(feature_matrix, dtype=np.float32)
        y = np.array(labels, dtype=np.float32)
        if len(X) == 0:
            raise ValueError("empty feature matrix")
        self.input_dim = X.shape[1]
        self._model = MultitaskNN(self.input_dim, self.hidden_dims).to(self.device)
        self._train(X, y, sample_weight)
        return self

    def _train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_weight: Sequence[float] | None = None,
    ) -> None:
        model = self._ensure_model()
        optimizer = torch.optim.AdamW(model.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

        # Prepare direction and profitability labels from sample_weight if available,
        # otherwise fall back to using ``y`` for both tasks.
        direction_labels = torch.tensor(y, dtype=torch.float32, device=self.device)
        profitability_labels = torch.tensor(y, dtype=torch.float32, device=self.device)

        dataset = torch.utils.data.TensorDataset(
            torch.tensor(X, dtype=torch.float32, device=self.device),
            direction_labels,
            profitability_labels,
        )
        loader = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        best_loss = float("inf")
        patience_counter = 0

        for epoch in range(self.epochs):
            model.train()
            epoch_losses: list[float] = []
            for batch_X, batch_dir, batch_prof in loader:
                optimizer.zero_grad()
                dir_logit, prof_logit = model(batch_X)
                dir_loss = F.binary_cross_entropy_with_logits(dir_logit.squeeze(1), batch_dir)
                prof_loss = F.binary_cross_entropy_with_logits(prof_logit.squeeze(1), batch_prof)
                loss = dir_loss + prof_loss
                loss.backward()
                optimizer.step()
                epoch_losses.append(float(loss.item()))

            avg_loss = float(np.mean(epoch_losses))
            scheduler.step(avg_loss)

            if avg_loss < best_loss - 1e-6:
                best_loss = avg_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= self.early_stopping_patience:
                    break

    def predict_proba(self, feature_matrix: models.FeatureMatrix) -> list[float]:
        model = self._ensure_model()
        model.eval()
        X = torch.tensor(np.array(feature_matrix, dtype=np.float32), device=self.device)
        with torch.no_grad():
            dir_logit, prof_logit = model(X)
        if self.task == "direction":
            probs = torch.sigmoid(dir_logit).cpu().numpy().flatten().tolist()
        else:
            probs = torch.sigmoid(prof_logit).cpu().numpy().flatten().tolist()
        return [float(p) for p in probs]

    def probability(self, values: Mapping[str, float]) -> float:
        row = [float(values.get(name, 0.0)) for name in self.feature_names]
        probs = self.predict_proba([row])
        return probs[0] if probs else 0.5

    def as_dict(self) -> dict[str, object]:
        model = self._ensure_model()
        buffer = io.BytesIO()
        torch.save(model.state_dict(), buffer)
        return {
            "model_family": self.model_family,
            "input_dim": self.input_dim,
            "hidden_dims": list(self.hidden_dims),
            "task": self.task,
            "feature_names": list(self.feature_names),
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "early_stopping_patience": self.early_stopping_patience,
            "state_dict": buffer.getvalue().hex(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "MultitaskNNAdapter":
        adapter = cls(
            input_dim=int(payload.get("input_dim", 0)),
            hidden_dims=tuple(int(v) for v in payload.get("hidden_dims", [128, 64])),
            task=str(payload.get("task", "profitability")),
            feature_names=tuple(str(v) for v in payload.get("feature_names", [])),
            epochs=int(payload.get("epochs", 100)),
            batch_size=int(payload.get("batch_size", 256)),
            learning_rate=float(payload.get("learning_rate", 1e-3)),
            weight_decay=float(payload.get("weight_decay", 1e-5)),
            early_stopping_patience=int(payload.get("early_stopping_patience", 10)),
        )
        state_hex = str(payload.get("state_dict", ""))
        if state_hex:
            buffer = io.BytesIO(bytes.fromhex(state_hex))
            state = torch.load(buffer, map_location=adapter.device, weights_only=True)
            adapter._model = MultitaskNN(adapter.input_dim, adapter.hidden_dims).to(adapter.device)
            adapter._model.load_state_dict(state)
        return adapter
