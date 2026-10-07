"""Hash-keyed parquet feature store (spec C3)."""
from __future__ import annotations
import hashlib, json, os
from pathlib import Path
from typing import Callable
import pandas as pd


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def key(name: str, params: dict, inputs: dict) -> str:
    return hashlib.sha256(canonical({"name": name, "params": params, "inputs": inputs}).encode()).hexdigest()


def _atomic_write(path: Path, write: Callable[[Path], None]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    write(tmp)
    os.replace(tmp, path)


def get_or_build(root: Path, name: str, params: dict, inputs: dict, build: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    folder = Path(root) / name
    k = key(name, params, inputs)
    target = folder / f"{k}.parquet"
    if target.exists():
        return pd.read_parquet(target)
    frame = build()
    folder.mkdir(parents=True, exist_ok=True)
    _atomic_write(folder / f"{k}.json",
                  lambda p: p.write_text(canonical({"name": name, "params": params, "inputs": inputs}), encoding="utf-8"))
    _atomic_write(target, lambda p: frame.to_parquet(p))
    return frame
