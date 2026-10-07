"""Spec §5 rolling schedule: expanding train from 2022-03-01, 3-month validation, 3-month test, 1-day gap."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

TRAIN_START = pd.Timestamp("2022-03-01", tz="UTC")
FIRST_TEST = pd.Timestamp("2023-09-01", tz="UTC")
END = pd.Timestamp("2026-01-01", tz="UTC")       # 2026H1 is the one-shot final check; never inside a window
STEP = pd.DateOffset(months=3)


@dataclass(frozen=True)
class Window:
    name: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def _windows() -> list[Window]:
    out, start = [], FIRST_TEST
    while start < END:
        val_start = start - STEP
        out.append(Window(f"W{len(out) + 1:02d}", TRAIN_START, val_start - pd.Timedelta(days=1), val_start, start,
                          start, min(start + STEP, END)))
        start = start + STEP
    return out


WINDOWS = _windows()
