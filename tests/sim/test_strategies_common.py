import dataclasses, numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import schema
from btcusdt_quant.sim.strategies import CATALOG, Context, apply_gate, build_variant

START, END = pd.Timestamp("2022-10-01", tz="UTC"), pd.Timestamp("2023-02-01", tz="UTC")
CUTS = [pd.Timestamp(x, tz="UTC") for x in ("2023-01-10 13:07", "2023-01-20 00:00", "2023-01-31 07:30")]

@pytest.fixture(scope="module")
def ctx():
    return Context.load(end=END, start=START)

def _rows(table, t):
    part = schema.validate(table)
    return part.loc[part.decision_time <= t].reset_index(drop=True)

@pytest.mark.parametrize("spec_id", sorted(k for k, v in CATALOG.items() if v.simulator == "core"))
def test_no_lookahead_all_strategies(ctx, spec_id):
    full = CATALOG[spec_id].build(ctx)
    for t in CUTS:
        cut = CATALOG[spec_id].build(ctx.truncate(t))
        pd.testing.assert_frame_equal(_rows(full, t), _rows(cut, t), check_dtype=False)

@pytest.mark.parametrize("spec_id", sorted(k for k, v in CATALOG.items() if v.cadence_min > 0 and v.simulator == "core"))
def test_one_row_per_cadence(ctx, spec_id):
    times = pd.DatetimeIndex(CATALOG[spec_id].build(ctx).decision_time.unique())
    step = np.diff(times.asi8) // 60_000_000_000
    assert len(times) > 100 and (step == CATALOG[spec_id].cadence_min).all()

def test_gate_missing_blocks_entry_only(ctx):
    regime = ctx.regime.copy()
    gap = (regime.timestamp >= pd.Timestamp("2023-01-15", tz="UTC")) & (regime.timestamp < pd.Timestamp("2023-01-16", tz="UTC"))
    regime.loc[gap, "M"] = np.nan                     # a stage-1 segment's empty last day
    holed = dataclasses.replace(ctx, regime=regime, _bars={})
    table = CATALOG["K09"].build(holed).assign(exit_long=True, allow_entry=True)
    gated = apply_gate(table, holed, "LOW")
    inside = gated.decision_time.between(pd.Timestamp("2023-01-15 00:15", tz="UTC"), pd.Timestamp("2023-01-15 23:45", tz="UTC"))
    assert inside.sum() > 90 and not gated.allow_entry[inside].any() and gated.exit_long.all()

def test_build_variant_configs(ctx):
    _, k01 = build_variant(ctx, "K01", False, "NATIVE")
    _, k09 = build_variant(ctx, "K09", True, "DETEXIT")
    assert k01.reentry == "stop_and_reverse" and k09.reentry == "strict" and k09.exit_style == "DETEXIT"
    with pytest.raises(ValueError, match="no gate axis"):
        build_variant(ctx, "B1", True, "NATIVE")
