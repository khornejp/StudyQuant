"""DEV-only market / funding loader (Codex review 2026-10-11): never opens a TEST path.

  * market: artifacts/btcusdt_2020_2026h1.parquet read with a predicate (open_time < 2026-01-01); rows are re-checked.
    The file is a single mixed artifact (2026 H1 rows included) whose last row group straddles 2025-12-24..2026-06-30:
    those 2026 rows are decoded by the reader and dropped before any use. The R2-54 stage-B snapshot (the TEST
    source) is refused outright.
  * funding: only the monthly archives BTCUSDT-fundingRate-YYYY-MM.zip with YYYY-MM < 2026-01 are opened.
Funding archives are hashed by file bytes; the market input is hashed over its decoded DEV rows (frame_sha), so no
2026 bytes of the mixed parquet are read for hashing."""
from __future__ import annotations
import hashlib, re
from pathlib import Path
import numpy as np, pandas as pd
from ..funding_source import _funding_csv_text_from_zip, parse_funding_csv_text
from ..sim import data
from . import sleeve_precompute as sp

ROOT = Path(__file__).resolve().parents[2]
MIXED_MARKET = ROOT / "artifacts/btcusdt_2020_2026h1.parquet"   # 2020..2026H1 in one file (last row group mixed)
DAILY_ARCHIVE = ROOT / "artifacts/archive"                        # BTCUSDT-1m-YYYY-MM-DD.zip, one file per UTC day
DEV_MARKET = ROOT / "out/rl_allocator_20261010/dev_market/btcusdt_1m_dev_2020_2025.parquet"   # built from DEV days only
_DAY = re.compile(r"BTCUSDT-1m-(\d{4})-(\d{2})-(\d{2})\.zip$")
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


def frame_sha(f: pd.DataFrame) -> str:
    """sha256 over the decoded rows (open_time ns + every numeric column, in column order)."""
    h = hashlib.sha256()
    h.update(f.open_time.array.asi8.astype("<i8").tobytes())
    for c in f.columns:
        if c != "open_time":
            h.update(c.encode())
            h.update(np.ascontiguousarray(f[c].to_numpy(float)).astype("<f8").tobytes())
    return h.hexdigest()


def dev_funding_files(funding_dir: Path = DEV_FUNDING) -> list[Path]:
    out = []
    for p in sorted(Path(funding_dir).glob("*.zip")):
        m = _MONTH.search(p.name)
        if m and (int(m.group(1)), int(m.group(2))) < (sp.TEST_START.year, sp.TEST_START.month):
            out.append(assert_dev_path(p))
    return out


def dev_day_files(archive: Path = DAILY_ARCHIVE) -> list[Path]:
    """Daily kline zips strictly before 2026-01-01, selected by file name before any I/O."""
    out = []
    for p in sorted(Path(archive).glob("BTCUSDT-1m-*.zip")):
        m = _DAY.search(p.name)
        if m and pd.Timestamp(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", tz="UTC") < sp.TEST_START:
            out.append(assert_dev_path(p))
    return out


def build_dev_market(out: Path = DEV_MARKET) -> dict:
    """DEV-only physical market file from the daily archives (no 2026 byte is opened)."""
    import zipfile
    cols = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count",
            "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
    frames = []
    for p in dev_day_files():
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            f = pd.read_csv(z.open(names[0]), header=None, names=cols)
        if str(f.iloc[0, 0]) == "open_time":
            f = f.iloc[1:]
        frames.append(f)
    raw = pd.concat(frames, ignore_index=True)
    t = pd.to_numeric(raw.open_time).astype(np.int64)
    t = np.where(t > 10**14, t // 1000, t)                       # microsecond stamps -> ms
    m = pd.DataFrame({"open_time": pd.to_datetime(t, unit="ms", utc=True).astype("datetime64[ns, UTC]"),
                      "open": raw.open.astype(float), "high": raw.high.astype(float), "low": raw.low.astype(float),
                      "close": raw.close.astype(float), "volume": raw.volume.astype(float),
                      "quote_volume": raw.quote_volume.astype(float), "number_of_trades": raw["count"].astype(float),
                      "taker_buy_base_volume": raw.taker_buy_volume.astype(float)})
    m = m.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)
    sp.guard_times(m.open_time.array.asi8, False, "dev market build")
    m = data.validate_minutes(m)
    out.parent.mkdir(parents=True, exist_ok=True)
    m.to_parquet(out, index=False)
    return {"days": len(frames), "rows": int(len(m)), "first": str(m.open_time.iloc[0]), "last": str(m.open_time.iloc[-1]),
            "frame_sha256": frame_sha(m), "file_sha256": _sha(out)}


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
    hashes = {"market": {"path": str(market.relative_to(ROOT)).replace("\\", "/"),
                         "dev_slice_sha256": frame_sha(minutes), "rows": int(len(minutes)),
                         "last": str(minutes.open_time.iloc[-1]), "file_sha256": _sha(market),
                         "note": "DEV-only physical file built from the daily archives dated < 2026-01-01 "
                                 "(build_dev_market); no 2026 file or row is opened"},
              "funding": {p.name: _sha(p) for p in files}, "funding_rows": int(len(f))}
    return minutes, f, hashes
