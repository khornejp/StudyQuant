import numpy as np, pandas as pd
from hypothesis import given, settings, strategies as st
from btcusdt_quant.sim import core, reference
from tests.sim.test_core_differential import random_case

@settings(max_examples=60, deadline=None)
@given(seed=st.integers(0, 10_000), exit_style=st.sampled_from(["NATIVE", "DETEXIT"]),
       reentry=st.sampled_from(["strict", "stop_and_reverse"]))
def test_invariants(seed, exit_style, reentry):
    s, m = random_case(seed)
    cfg = reference.SimConfig(include_funding=False, exit_style=exit_style, reentry=reentry)
    r = core.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1] + pd.Timedelta(minutes=1), cfg)
    if len(r.trades):
        # ledger identity
        assert np.isclose(r.minute_pnl.sum(), r.trades.net_bps.sum(), atol=1e-6)
        # never entry before its decision + delay
        assert (r.trades.entry_time >= r.trades.decision_time + pd.Timedelta(minutes=1)).all()
        assert (r.trades.exit_time >= r.trades.entry_time).all()
        # never more than one unit open at any minute
        open_units = pd.concat([pd.Series(r.trades.units.to_numpy(), index=r.trades.entry_time),
                                pd.Series(-r.trades.units.to_numpy(), index=r.trades.exit_time)])
        assert open_units.groupby(level=0).sum().sort_index().cumsum().max() <= 1 + 1e-9
        # strict: no new position decided while another position was open at that decision time
        if reentry == "strict":
            spans = r.trades.groupby("decision_time").agg(start=("entry_time", "min"), end=("exit_time", "max"),
                                                          side=("side", "first"))
            for decision, row in spans.iterrows():
                others = spans.drop(index=decision)
                overlap = (others.start <= decision) & (decision < others.end)
                add_on = overlap & (others.side == row.side) & (others.start < row.start)
                if exit_style == "DETEXIT" and add_on.any():
                    continue   # DETEXIT add-on leg decided inside its own position
                assert not overlap.any(), f"entry decided at {decision} while held"
