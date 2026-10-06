from __future__ import annotations

import pandas as pd

from btcusdt_quant.paper.reconcile import reconcile_frame
from btcusdt_quant.paper.store import PaperStore


def test_reconcile_records_revision_without_overwrite(tmp_path) -> None:
    live = pd.DataFrame({"open_time": ["2026-01-01T00:00:00Z"], "close": [1.0]})
    archive = pd.DataFrame({"open_time": ["2026-01-01T00:00:00Z"], "close": [2.0]})
    with PaperStore(tmp_path / "live.sqlite") as store:
        result = reconcile_frame(store, "klines_1m", live, archive, "open_time", ["close"])
        assert result["revisions"] == 1
        assert store.frame("revisions").iloc[0].live_value == "1.0"


def test_ls_reconcile_matches_archive_start_to_rest_end_label(tmp_path) -> None:
    live = pd.DataFrame({"timestamp": pd.to_datetime(["2026-01-01T00:05:00Z"]),
                         "global_ls_account": [1.25]})
    archive = pd.DataFrame({"timestamp": pd.to_datetime(["2026-01-01T00:00:00Z"]),
                            "global_ls_account": [1.25]})
    with PaperStore(tmp_path / "live.sqlite") as store:
        result = reconcile_frame(store, "ls_ratio_5m", live, archive, "timestamp",
                                 ["global_ls_account"])
    assert result == {"common": 1, "revisions": 0,
                      "missing_live": 0, "missing_archive": 0}
