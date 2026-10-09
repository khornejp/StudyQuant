"""C1_FLIP_AX research id K01_FLIP (Codex 2026-10-09): K01 rows with the F3 component side flipped (trend-following),
its R2-52A F3 state exit mirrored, E1 unchanged; outside the frozen 29-id R2-52A scope."""
import json
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant, legacy
from tests.sim.test_strategies_state_exits import BASELINE, END, START, _hourly_g, ax, same

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ctx():
    return Context.load(end=END, start=START)


def test_k01_flip_is_registered_outside_the_frozen_scope():
    spec, base = CATALOG["K01_FLIP"], CATALOG["K01"]
    assert spec.post_freeze and not base.post_freeze
    assert (spec.family, spec.cadence_min, spec.hold_min, spec.e_head, spec.gate, spec.reentry) == \
        (base.family, base.cadence_min, base.hold_min, base.e_head, base.gate, base.reentry)
    assert "K01_FLIP" not in BASELINE and len(BASELINE) == 29
    assert not [k for k, s in CATALOG.items() if s.post_freeze and k != "K01_FLIP"]


def test_k01_flip_negates_only_the_f3_side(ctx):
    flip, base = CATALOG["K01_FLIP"].build(ctx), CATALOG["K01"].build(ctx)
    same(flip.decision_time, base.decision_time); same(flip.component, base.component)
    same(flip.max_hold_min, base.max_hold_min)
    f3 = (base.component == legacy.F3).to_numpy()
    same(flip.side[f3], -base.side[f3])
    same(flip.side[~f3], base.side[~f3])                              # E1 rows: same long-only breakout
    assert (base.side[f3] == 1).any() and (base.side[f3] == -1).any() and (base.side[~f3] == 1).any()
    same(flip.anchor_upper, base.anchor_upper); same(flip.anchor_price, base.anchor_price)
    same(flip.anchor_once, base.anchor_once)


def test_k01_flip_state_exit_is_mirrored_and_e1_anchor_unchanged(ctx):
    h, g = _hourly_g(ctx)
    q50 = g.rolling(2160, min_periods=720).quantile(.5)
    t, base = ax(ctx, "K01_FLIP"), ax(ctx, "K01")
    assert len(t) == len(base) == 2 * len(h)
    f3, e1 = t.loc[t.component == legacy.F3], t.loc[t.component == legacy.E1]
    same(f3.ax_exit_long, g <= q50); same(f3.ax_exit_short, g >= q50)  # long entered at >= q90 exits at <= q50
    b3 = base.loc[base.component == legacy.F3]
    same(f3.ax_exit_long, b3.ax_exit_short); same(f3.ax_exit_short, b3.ax_exit_long)
    e1_cols = ["decision_time", "ax_exit_long", "ax_exit_short", "anchor_upper", "anchor_lower", "anchor_price",
               "anchor_once"]
    pd.testing.assert_frame_equal(e1[e1_cols].reset_index(drop=True),
                                  base.loc[base.component == legacy.E1, e1_cols].reset_index(drop=True))
    assert (g <= q50).any() and (g >= q50).any()


def test_k01_flip_base_variant_has_no_state_columns(ctx):
    table, config = build_variant(ctx, "K01_FLIP", gated=False, style="NATIVE")
    base, base_config = build_variant(ctx, "K01", gated=False, style="NATIVE")
    assert list(table.columns) == list(base.columns) and repr(config) == repr(base_config)


def test_post_freeze_ids_stay_out_of_catalog_sweeps():
    from btcusdt_quant.rl import state
    assert "K01_FLIP" not in state.SIGNAL_IDS + state.OCO_IDS
    freeze = json.loads((ROOT / "out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json").read_text(encoding="utf-8")) \
        if (ROOT / "out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json").exists() else None
    if freeze is not None:
        assert "K01_FLIP" not in freeze["scope"]["included_ids"]
