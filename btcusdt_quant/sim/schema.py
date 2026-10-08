from __future__ import annotations
import pandas as pd

SIGNAL_COLUMNS = ["decision_time", "side", "entry", "upper", "lower", "expiry_min", "max_hold_min",
                  "stop_bps", "take_bps", "exit_long", "exit_short", "allow_entry"]
# Optional `component` (int, default 0): an opposite-side signal reverses a position only when it comes from the
# component that opened it (R2-39 lets F3 reverse F3 but never E1). All rows 0 = any opposite signal reverses.
OPTIONAL_COLUMNS = {"component": 0}
# R2-52A (SimConfig.exit_policy="R2_52A") float columns, passed through only when present (BASE tables unchanged):
# e0_bps = E known at the decision (market entries; NaN = NO_ENTRY_E), k = risk multiple (R0 = min(k*E0, 300)),
# anchor_upper / anchor_lower = levels stored in the position at fill, anchor_price = completed-cadence value on a
# held-component row: long exits when anchor_price <= stored anchor_upper, short when >= stored anchor_lower.
ADAPTIVE_COLUMNS = ("e0_bps", "k", "anchor_upper", "anchor_lower", "anchor_price")

def validate(signals: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in SIGNAL_COLUMNS if c not in signals]
    if missing:
        raise ValueError(f"signal columns missing: {missing}")
    out = signals[SIGNAL_COLUMNS].copy()
    for name, default in OPTIONAL_COLUMNS.items():
        out[name] = signals[name].astype(int).to_numpy() if name in signals else default
    for name in ADAPTIVE_COLUMNS:
        if name in signals:
            out[name] = signals[name].to_numpy(float)
    out["decision_time"] = pd.to_datetime(out.decision_time, utc=True)
    out = out.sort_values("decision_time", kind="stable").reset_index(drop=True)   # row order within T = priority
    if out.duplicated(["decision_time", "component"]).any():
        raise ValueError("duplicate decision: same decision_time and component")
    if not out.side.isin([-1, 0, 1]).all() or not out.entry.isin(["market", "oco"]).all():
        raise ValueError("bad side or entry type")
    for c in ("exit_long", "exit_short", "allow_entry"):
        out[c] = out[c].astype(bool)
    out["side"] = out.side.astype(int)
    return out
