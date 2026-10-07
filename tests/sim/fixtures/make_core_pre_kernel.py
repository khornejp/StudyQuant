"""Freeze core.simulate outputs from before the R2-48 transition kernel (Ruling P1). Generated at commit 6b17dda;
rerunning it after the refactor would only compare core with itself, so do not regenerate.
Action cases run as plain signal rows (flat/opposite targets set exit flags), the only form the old engine had.
Run: venv_btcusdt\\Scripts\\python.exe -m tests.sim.fixtures.make_core_pre_kernel"""
import pandas as pd
from btcusdt_quant.sim import core
from tests.sim.test_transition_kernel import FIXTURE, MIN, as_signals, fixture_cases

out = {}
for name, signals, m, cfg in fixture_cases():
    rows = as_signals(signals) if name.startswith("action") else signals
    r = core.simulate(rows, m, m.open_time.iloc[0], m.open_time.iloc[-1] + MIN, cfg)
    out[name] = (r.trades, r.minute_pnl, r.open_position)
FIXTURE.parent.mkdir(exist_ok=True)
pd.to_pickle(out, FIXTURE)
print(len(out), "cases ->", FIXTURE)
