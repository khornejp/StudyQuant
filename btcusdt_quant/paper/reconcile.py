"""Read-only archive comparison; live originals are never overwritten."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .store import PaperStore


def reconcile_frame(store: PaperStore, dataset: str, live: pd.DataFrame,
                    archive: pd.DataFrame, key: str, columns: list[str]) -> dict[str, int]:
    left = live.set_index(key)
    archive_values = archive.copy()
    if dataset in {"ls_ratio", "ls_ratio_5m"}:
        archive_values[key] = pd.to_datetime(archive_values[key], utc=True) + pd.Timedelta(minutes=5)
    right = archive_values.set_index(key)
    common = left.index.intersection(right.index)
    missing_live = len(right.index.difference(left.index))
    missing_archive = len(left.index.difference(right.index))
    revisions = 0
    detected = datetime.now(timezone.utc).isoformat()
    for column in columns:
        different = ~left.loc[common, column].eq(right.loc[common, column])
        for event_time in common[different]:
            store.insert("revisions", {"dataset": dataset, "event_time": str(event_time),
                         "column_name": column, "live_value": str(left.at[event_time, column]),
                         "archive_value": str(right.at[event_time, column]),
                         "detected_at": detected})
            revisions += 1
    return {"common": len(common), "revisions": revisions,
            "missing_live": missing_live, "missing_archive": missing_archive}


__all__ = ["reconcile_frame"]
