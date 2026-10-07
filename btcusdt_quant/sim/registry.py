"""Experiment registry: one JSON line per run (spec D1)."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from .store import canonical
import hashlib

FIELDS = ("experiment", "timestamp_utc", "config_hash", "input_hashes", "n_trials", "result_summary")


def record(path: Path, entry: dict) -> None:
    row = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "config_hash": None, "input_hashes": {},
           "n_trials": 0, "result_summary": {}, **entry}
    if "config" in row and row["config_hash"] is None:
        row["config_hash"] = hashlib.sha256(canonical(row["config"]).encode()).hexdigest()
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(row) + "\n")


def cumulative_trials(path: Path, base: int = 5125) -> int:
    path = Path(path)
    if not path.exists():
        return base
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return base + sum(int(row.get("n_trials", 0)) for row in lines)
