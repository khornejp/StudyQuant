from __future__ import annotations

import pandas as pd
import pytest

from btcusdt_quant.paper.config import PaperConfig, credential_status, load_config
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper.store import PaperStore


def _minute(stamp: str, closed: bool = True) -> dict[str, object]:
    return {"open_time": pd.Timestamp(stamp), "open": 1.0, "high": 2.0, "low": .5,
            "close": 1.5, "volume": 2.0, "closed": closed}


def test_engine_closed_only_gap_and_restart(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    with PaperStore(path) as store:
        engine = PaperEngine(store)
        with pytest.raises(ValueError, match="in-progress"):
            engine.process_closed_minute(_minute("2026-07-01T00:00Z", False))
        assert engine.process_closed_minute(_minute("2026-07-01T00:00Z"))
    with PaperStore(path) as store:
        engine = PaperEngine(store)
        assert not engine.process_closed_minute(_minute("2026-07-01T00:00Z"))
        assert engine.process_closed_minute(_minute("2026-07-01T00:02Z"))
        assert engine.process_closed_minute(_minute("2026-07-01T00:01Z"), source="rest")
        health = store.frame("collector_health")
        assert sorted(health.gaps.tolist()) == [0, 0, 1]
        assert len(store.frame("klines_1m")) == 3


def test_live_mode_fails_closed(tmp_path) -> None:
    path = tmp_path / "paper.toml"
    path.write_text('[paper]\nmode="live"\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="live mode is disabled"):
        load_config(path)
    with PaperStore(tmp_path / "x.sqlite") as store:
        with pytest.raises(RuntimeError, match="live mode is disabled"):
            PaperEngine(store, PaperConfig(mode="live"))


def test_credentials_are_masked(tmp_path) -> None:
    path = tmp_path / ".env"
    path.write_text("BINANCE_API_KEY=abcdefgh12345678\nBINANCE_API_SECRET=ijklmnop87654321\n",
                    encoding="utf-8")
    status = credential_status(path)
    assert status == {"loaded": True, "api_key": "abcd...5678", "api_secret": "ijkl...4321"}
