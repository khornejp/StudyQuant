from __future__ import annotations
import hashlib
from pathlib import Path

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()

def tree_sha256(root: Path, pattern: str) -> dict:
    files = sorted(Path(root).glob(pattern))
    digest = hashlib.sha256()
    listing = {}
    for item in files:
        value = file_sha256(item)
        listing[item.name] = value
        digest.update(item.name.encode()); digest.update(value.encode())
    return {"files": listing, "sha256": digest.hexdigest()}

def verify(recorded: dict, current: dict) -> None:
    problems = []
    for key, value in recorded.items():
        now = current.get(key)
        if now is None:
            problems.append(f"{key}: missing")
        elif isinstance(value, dict) and "files" in value:
            for name in sorted(set(value["files"]) | set(now["files"])):
                if value["files"].get(name) != now["files"].get(name):
                    problems.append(f"{key}/{name}: sha256 changed")
        elif value != now:
            problems.append(f"{key}: sha256 changed")
    if problems:
        raise ValueError("provenance mismatch: " + "; ".join(problems))
