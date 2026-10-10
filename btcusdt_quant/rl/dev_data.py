"""DEV-only market / funding loader (Codex review 2026-10-11): never opens a TEST path.

  * market: artifacts/btcusdt_2020_2026h1.parquet read with a predicate (open_time < 2026-01-01) pushed down; rows
    are re-checked. The file itself also stores 2026 H1 rows (single mixed artifact); only DEV row groups are
    decoded. The R2-54 stage-B snapshot (the TEST source) is refused outright.
  * funding: only the monthly archives BTCUSDT-fundingRate-YYYY-MM.zip with YYYY-MM < 2026-01 are opened.
Every opened file is hashed (sha256) and returned with the frames so experiments can record their exact inputs."""
from __future__ import annotations
import hashlib, re
from pathlib import Path
import numpy as np, pandas as pd
from ..funding_source import _funding_csv_text_from_zip, parse_funding_csv_text
from ..sim import data
from . import sleeve_precompute as sp

ROOT = Path(__file__).resolve().parents[2]
DEV_MARKET = ROOT / "artifacts/btcusdt_2020_2026h1.parquet"
DEV_FUNDING = ROOT / "artifacts/funding_2020_2026h1"
FORBIDDEN = ("stageb_snapshot", "r2_54", "TEST")
_MONTH = re.compile(r"(\d{4})-(\d{2})\.zip$")


def assert_dev_path(path: Path) -> Path:
    """Refuse any TEST source: the stage-B snapshot tree, TEST-named files, funding months >= 2026-01."""
    p = Path(path)
    s = str(p).replace("\\", "/")
    if any(x in s for x in FORBIDDEN):
        raise sp.TestAccessError(f"TEST source refused: {s}")
    m = _MONTH.search(p.name)
    if m and (int(m.group(1)), int(m.group(2))) >= (sp.TEST_START.year, sp.TEST_START.month):
        raise sp.TestAccessError(f"TEST-period funding archive refused: {p.name}")
    return p


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def dev_funding_files(funding_dir: Path = DEV_FUNDING) -> list[Path]:
    out = []
    for p in sorted(Path(funding_dir).glob("*.zip")):
        m = _MONTH.search(p.name)
        if m and (int(m.group(1)), int(m.group(2))) < (sp.TEST_START.year, sp.TEST_START.month):
            out.append(assert_dev_path(p))
    return out


def load_dev(market: Path = DEV_MARKET, funding_dir: Path = DEV_FUNDING):
    """-> minutes frame (open_time < 2026-01-01), funding frame (time, rate; time < 2026-01-01), input hashes."""
    assert_dev_path(market)
    minutes = data.load_minutes(market, end=sp.TEST_START)
    sp.guard_times(minutes.open_time.array.asi8, False, "dev market")
    rows = []
    files = dev_funding_files(funding_dir)
    for p in files:
        rows.extend(parse_funding_csv_text(_funding_csv_text_from_zip(p.read_bytes())))
    f = pd.DataFrame({"time": pd.to_datetime([r.funding_time for r in rows], utc=True),
                      "rate": np.array([r.funding_rate for r in rows], float)})
    f = f[f.time < sp.TEST_START].sort_values("time").drop_duplicates("time").reset_index(drop=True)
    f["time"] = f.time.astype("datetime64[ns, UTC]")
    sp.guard_times(f.time.array.asi8, False, "dev funding")
    hashes = {"market": {"path": str(market.relative_to(ROOT)).replace("\\", "/"), "sha256": _sha(market),
                         "rows": int(len(minutes)), "last": str(minutes.open_time.iloc[-1])},
              "funding": {p.name: _sha(p) for p in files}, "funding_rows": int(len(f))}
    return minutes, f, hashes
