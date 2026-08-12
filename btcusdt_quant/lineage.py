from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


LINEAGE_TIMESTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()


@dataclass(frozen=True)
class LineageBinding:
    output_dir: Path
    run_id: str
    params: Mapping[str, object] = field(default_factory=dict)
    metrics: Mapping[str, float | int] = field(default_factory=dict)
    artifacts: Sequence[str] = field(default_factory=tuple)
    model_metadata: Mapping[str, object] = field(default_factory=dict)
    data_hash: str | None = None
    git_commit: str | None = None
    dvc_metadata: Mapping[str, object] = field(default_factory=dict)
    provenance: Mapping[str, object] = field(default_factory=dict)
    experiment_name: str = "btcusdt_quant_offline_training"
    model_name: str = "offline_btcusdt_centroid_linear"


class LineageWriter:
    def __init__(self, output_dir: Path, enabled: bool = True, adapters: Sequence[object] | None = None, fallback: "LocalLineageFallback | None" = None) -> None:
        self.output_dir = output_dir
        self.enabled = enabled
        self.adapters = list(adapters) if adapters is not None else [MLflowLineageAdapter(), DVCLineageAdapter()]
        self.fallback = fallback or LocalLineageFallback(output_dir)

    def write(self, binding: LineageBinding) -> dict[str, object]:
        if not self.enabled:
            return {"run_id": binding.run_id, "enabled": False, "artifacts": [], "adapters": []}
        self.output_dir.mkdir(parents=True, exist_ok=True)
        normalized_binding = _binding_for_output_dir(binding, self.output_dir)
        adapter_results: list[dict[str, object]] = []
        adapter_artifacts: list[str] = []
        for adapter in self.adapters:
            result = self._log_with_adapter(adapter, normalized_binding)
            adapter_results.append(result)
            adapter_artifacts.extend(_string_list(result.get("artifacts", ())))
        fallback_result = self.fallback.write(normalized_binding, adapter_results)
        artifacts = adapter_artifacts + _string_list(fallback_result.get("artifacts", ()))
        return {
            "run_id": normalized_binding.run_id,
            "enabled": True,
            "artifacts": artifacts,
            "adapters": adapter_results,
            "local_manifest": fallback_result.get("manifest_path", "lineage_manifest.json"),
        }

    def log(self, binding: LineageBinding) -> dict[str, object]:
        return self.write(binding)

    def _log_with_adapter(self, adapter: object, binding: LineageBinding) -> dict[str, object]:
        try:
            log_method = getattr(adapter, "log")
            result = log_method(binding)
        except Exception as exc:
            return {"adapter": adapter.__class__.__name__, "available": False, "logged": False, "reason": str(exc)}
        if isinstance(result, Mapping):
            return dict(result)
        return {"adapter": adapter.__class__.__name__, "available": True, "logged": False, "reason": "adapter returned no status"}


class MLflowLineageAdapter:
    def log(self, binding: LineageBinding) -> dict[str, object]:
        mlflow, reason = _import_optional("mlflow")
        if mlflow is None:
            return {"adapter": "mlflow", "available": False, "logged": False, "reason": reason}
        try:
            if hasattr(mlflow, "set_experiment"):
                mlflow.set_experiment(binding.experiment_name)
            with mlflow.start_run(run_name=binding.run_id) as active_run:
                if binding.params and hasattr(mlflow, "log_params"):
                    mlflow.log_params(_mlflow_params(binding.params))
                if binding.metrics and hasattr(mlflow, "log_metrics"):
                    mlflow.log_metrics(_numeric_mapping(binding.metrics))
                for key, value in _mlflow_tags(binding.model_metadata).items():
                    if hasattr(mlflow, "set_tag"):
                        mlflow.set_tag(key, value)
                for relative_path in binding.artifacts:
                    path = binding.output_dir / relative_path
                    if path.exists() and path.is_file() and hasattr(mlflow, "log_artifact"):
                        mlflow.log_artifact(str(path))
                mlflow_run_id = getattr(getattr(active_run, "info", None), "run_id", binding.run_id)
        except Exception as exc:
            return {"adapter": "mlflow", "available": True, "logged": False, "reason": str(exc)}
        return {"adapter": "mlflow", "available": True, "logged": True, "run_id": str(mlflow_run_id)}


class DVCLineageAdapter:
    def log(self, binding: LineageBinding) -> dict[str, object]:
        dvc, reason = _import_optional("dvc")
        if dvc is None:
            return {"adapter": "dvc", "available": False, "logged": False, "reason": reason}
        git_commit = binding.git_commit or _git_commit(Path.cwd())
        metadata = {
            "run_id": binding.run_id,
            "data_hash": binding.data_hash,
            "git_commit": git_commit,
            "dvc_version": str(getattr(dvc, "__version__", "unknown")),
            "dvc_metadata": dict(binding.dvc_metadata),
            "provenance": dict(binding.provenance),
        }
        relative_path = "lineage/dvc_metadata.json"
        _write_json(binding.output_dir, relative_path, metadata)
        return {"adapter": "dvc", "available": True, "logged": True, "git_commit": git_commit, "artifacts": [relative_path]}


class LocalLineageFallback:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def write(self, binding: LineageBinding, adapter_results: Sequence[Mapping[str, object]] | None = None) -> dict[str, object]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        binding_payload = _binding_payload(binding)
        binding_path = "lineage/local_lineage_binding.json"
        model_metadata_path = "lineage/model_version_metadata.json"
        _write_json(self.output_dir, binding_path, binding_payload)
        _write_json(self.output_dir, model_metadata_path, dict(binding.model_metadata))
        local_artifacts = [binding_path, model_metadata_path]
        manifest_payload = {
            "run_id": binding.run_id,
            "created_at": LINEAGE_TIMESTAMP,
            "backend": "local",
            "experiment_name": binding.experiment_name,
            "model_name": binding.model_name,
            "data_hash": binding.data_hash,
            "git_commit": binding.git_commit,
            "params": dict(binding.params),
            "metrics": dict(binding.metrics),
            "model_metadata": dict(binding.model_metadata),
            "dvc_metadata": dict(binding.dvc_metadata),
            "adapters": [dict(result) for result in adapter_results or ()],
            "input_artifacts": _artifact_entries(binding.output_dir, binding.artifacts),
            "local_artifacts": _artifact_entries(binding.output_dir, local_artifacts),
        }
        manifest_path = "lineage_manifest.json"
        _write_json(self.output_dir, manifest_path, manifest_payload)
        return {"run_id": binding.run_id, "manifest_path": manifest_path, "artifacts": [binding_path, model_metadata_path, manifest_path]}


def _binding_for_output_dir(binding: LineageBinding, output_dir: Path) -> LineageBinding:
    if binding.output_dir == output_dir:
        return binding
    return LineageBinding(
        output_dir=output_dir,
        run_id=binding.run_id,
        params=binding.params,
        metrics=binding.metrics,
        artifacts=binding.artifacts,
        model_metadata=binding.model_metadata,
        data_hash=binding.data_hash,
        git_commit=binding.git_commit,
        dvc_metadata=binding.dvc_metadata,
        provenance=binding.provenance,
        experiment_name=binding.experiment_name,
        model_name=binding.model_name,
    )


def _binding_payload(binding: LineageBinding) -> dict[str, object]:
    return {
        "run_id": binding.run_id,
        "created_at": LINEAGE_TIMESTAMP,
        "output_dir": binding.output_dir.as_posix(),
        "experiment_name": binding.experiment_name,
        "model_name": binding.model_name,
        "params": dict(binding.params),
        "metrics": dict(binding.metrics),
        "artifacts": list(binding.artifacts),
        "model_metadata": dict(binding.model_metadata),
        "data_hash": binding.data_hash,
        "git_commit": binding.git_commit,
        "dvc_metadata": dict(binding.dvc_metadata),
        "provenance": dict(binding.provenance),
    }


def _artifact_entries(output_dir: Path, relative_paths: Sequence[str]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for relative_path in relative_paths:
        path = output_dir / relative_path
        if path.exists() and path.is_file():
            entries.append({"path": relative_path, "sha256": _sha256_file(path)})
        else:
            entries.append({"path": relative_path, "missing": True})
    return entries


def _write_json(output_dir: Path, relative_path: str, payload: object) -> Path:
    path = output_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    return path


def _stable_json(payload: object) -> str:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _import_optional(module_name: str) -> tuple[Any | None, str]:
    try:
        return importlib.import_module(module_name), ""
    except Exception as exc:
        return None, str(exc)


def _numeric_mapping(values: Mapping[str, float | int]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for key, value in values.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (float, int)):
            metrics[str(key)] = float(value)
    return metrics


def _mlflow_params(values: Mapping[str, object]) -> dict[str, str | int | float | bool]:
    params: dict[str, str | int | float | bool] = {}
    for key, value in values.items():
        if isinstance(value, (str, int, float, bool)):
            params[str(key)] = value
        else:
            params[str(key)] = _stable_json(value)
    return params


def _mlflow_tags(values: Mapping[str, object]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for key, value in values.items():
        if isinstance(value, (str, int, float, bool)):
            tags[f"model.{key}"] = str(value)
    return tags


def _string_list(values: object) -> list[str]:
    if isinstance(values, (list, tuple)):
        return [str(value) for value in values]
    return []


def _git_commit(cwd: Path) -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(cwd), capture_output=True, text=True, check=False, timeout=5)
    except Exception:
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None
