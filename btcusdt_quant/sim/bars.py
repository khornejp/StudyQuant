from __future__ import annotations
import pandas as pd

def aggregate(minutes: pd.DataFrame, minutes_per_bar: int) -> pd.DataFrame:
    rule = f"{minutes_per_bar}min"
    g = minutes.set_index("open_time").resample(rule, origin="epoch", label="left", closed="left")
    out = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                volume=("volume", "sum"), taker_buy=("taker_buy_base_volume", "sum"), n=("close", "size"))
    out = out.loc[out.n == minutes_per_bar].reset_index().rename(columns={"open_time": "bar_start"})
    out["decision_time"] = out.bar_start + pd.Timedelta(minutes=minutes_per_bar)
    return out.reset_index(drop=True)
