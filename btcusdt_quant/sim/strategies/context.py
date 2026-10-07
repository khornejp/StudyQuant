"""Inputs a strategy may read, all with their availability times, plus cached complete bars."""
from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd
from .. import bars as bars_module, costs, data, regime

DEFAULT_END = pd.Timestamp("2026-01-01", tz="UTC")


@dataclass(frozen=True)
class Context:
    minutes: pd.DataFrame          # 1 m market, open_time < end
    metrics: pd.DataFrame          # available_time, global_ls, top_ls, oi, oi_value, taker_lsr
    premium: pd.DataFrame          # available_time, premium (1 m premium index close)
    funding: pd.DataFrame          # time (settlement = publish), rate
    regime: pd.DataFrame           # timestamp, M, L, prediction_<target>
    end: pd.Timestamp = DEFAULT_END
    _bars: dict = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def load(cls, end: pd.Timestamp = DEFAULT_END, start: pd.Timestamp | None = None) -> "Context":
        minutes = data.load_minutes(end=end)                # cutoff-aware: later rows are never read
        if start is not None:
            minutes = minutes.loc[minutes.open_time >= start]
        funding = costs._settlements()[["time", "rate"]]
        return cls(minutes=minutes.reset_index(drop=True), metrics=data.load_metrics(end=end),
                   premium=data.load_premium(end=end), funding=funding.loc[funding.time < end].copy(),
                   regime=regime.load_regime(data.load_predictions(end=end)), end=end).truncate(end)

    def bars(self, minutes_per_bar: int) -> pd.DataFrame:
        if minutes_per_bar not in self._bars:
            self._bars[minutes_per_bar] = bars_module.aggregate(self.minutes, minutes_per_bar)
        return self._bars[minutes_per_bar]

    def truncate(self, t: pd.Timestamp) -> "Context":
        """Everything knowable before time t (a prediction stamped t is usable at t)."""
        return Context(minutes=self.minutes.loc[self.minutes.open_time < t].reset_index(drop=True),
                       metrics=self.metrics.loc[self.metrics.available_time < t].reset_index(drop=True),
                       premium=self.premium.loc[self.premium.available_time <= t].reset_index(drop=True),   # close_time + 1 ms
                       funding=self.funding.loc[self.funding.time < t].reset_index(drop=True),
                       regime=self.regime.loc[self.regime.timestamp <= t].reset_index(drop=True), end=t)
