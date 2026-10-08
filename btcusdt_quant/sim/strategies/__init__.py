"""Technique catalog (R2-47 BRIEF §2, spec §3): each entry turns a Context into a signal table."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import numpy as np, pandas as pd
from .. import regime, schema
from ..reference import SimConfig
from .context import Context

STYLES = ("NATIVE", "DETEXIT")


@dataclass(frozen=True)
class Spec:
    id: str
    family: str
    cadence_min: int
    hold_min: int
    e_head: str
    gate: str | None            # "HIGH", "LOW" or None (no gate axis)
    build: Callable[[Context], pd.DataFrame]
    reentry: str = "strict"
    simulator: str = "core"     # "core" or "grid"
    ax_rows: Callable[[Context, pd.DataFrame], pd.DataFrame] | None = None   # R2-52A inert state rows (K01, K14)


CATALOG: dict[str, Spec] = {}


def register(spec: Spec) -> Spec:
    if spec.id in CATALOG:
        raise ValueError(f"duplicate catalog id {spec.id}")
    CATALOG[spec.id] = spec
    return spec


def make_table(decisions, side, component: int, max_hold_min, **columns) -> pd.DataFrame:
    """Signal rows in schema form; columns not given take the schema defaults."""
    n = len(decisions)
    frame = pd.DataFrame({"decision_time": pd.DatetimeIndex(decisions), "side": np.asarray(side, int),
                          "component": component, "entry": "market", "upper": np.nan, "lower": np.nan,
                          "expiry_min": 0, "max_hold_min": max_hold_min, "stop_bps": np.nan, "take_bps": np.nan,
                          "exit_long": False, "exit_short": False, "allow_entry": True}, index=range(n))
    for name, value in columns.items():
        frame[name] = value
    return frame


def apply_gate(table: pd.DataFrame, ctx: Context, gate: str | None) -> pd.DataFrame:
    if gate is None:
        return table
    out = table.copy()
    out["allow_entry"] = out.allow_entry & regime.gate_mask(ctx.regime, pd.DatetimeIndex(out.decision_time), gate)
    return out


def apply_exit(table: pd.DataFrame, ctx: Context, spec: Spec, style: str) -> pd.DataFrame:
    if style not in STYLES:
        raise ValueError(f"bad exit style {style}")
    if style == "NATIVE":
        return table
    out = table.copy()
    times = pd.DatetimeIndex(out.decision_time)
    if "e_head" in out:     # composite books: each component keeps its own E head
        e = np.full(len(out), np.nan)
        for head, rows in out.groupby("e_head").groups.items():
            index = out.index.get_indexer(rows)
            e[index] = regime.e_bps(ctx.regime, times[index], head)
    else:
        e = regime.e_bps(ctx.regime, times, spec.e_head)
    out["stop_bps"] = e
    out["take_bps"] = e
    with np.errstate(invalid="ignore"):
        out["allow_entry"] = out.allow_entry & np.isfinite(e) & (e > 0)
    return out


# R2-52A family state columns (r2_52a_exit_freeze.json family_state_exits) and their no-exit defaults
AX_DEFAULTS = {"ax_exit_long": False, "ax_exit_short": False, "anchor_upper": np.nan, "anchor_lower": np.nan,
               "anchor_price": np.nan}


def build_variant(ctx: Context, spec_id: str, gated: bool, style: str,
                  ax: bool = False) -> tuple[pd.DataFrame, SimConfig]:
    """ax=True (R2-52A): also the side-0 rows a family needs for its state checks, and every state column. The
    default output keeps the pre-R2-52A rows (RL state and paper read it); state columns ride along either way."""
    spec = CATALOG[spec_id]
    if gated and spec.gate is None:
        raise ValueError(f"{spec_id} has no gate axis")
    table = spec.build(ctx)
    if ax:
        if spec.ax_rows is not None:
            table = pd.concat([table, spec.ax_rows(ctx, table)], ignore_index=True)
        table = table.assign(**{c: v for c, v in AX_DEFAULTS.items() if c not in table})
    table = apply_gate(table, ctx, spec.gate if gated else None)
    table = apply_exit(table, ctx, spec, style)
    return schema.validate(table), SimConfig(reentry=spec.reentry, exit_style=style)


from . import legacy, volatility, grid, trend, reversion, futures, levels  # noqa: E402,F401  register the catalog
