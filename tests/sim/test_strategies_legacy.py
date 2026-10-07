"""K01-K05 and B1-B3 against the frozen R2-39 / R2-45 code (real data, slow)."""
import importlib.util, sys
from pathlib import Path
import pandas as pd, pytest
from btcusdt_quant.sim import core, reference
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant, legacy

ROOT = Path(__file__).resolve().parents[2]
LO, HI = pd.Timestamp("2022-03-01", tz="UTC"), pd.Timestamp("2026-01-01", tz="UTC")
BOOKS = {"B1": "B1_FAST_NONE", "B2": "B2_HIGH_ONLY", "B3": "B3_FIXED_ROUTE"}

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module

@pytest.fixture(scope="module")
def env():
    r245 = _load("r245", "out/run_k45_vol_gated_backtest_r2_45.py")
    market, funding = r245.r239.load_market(), r245.r239.load_funding()
    return {"ctx": Context.load(), "r245": r245, "market": market, "funding": funding,
            "fast": r245.build_fast_signals(market, r245.r239.load_metrics()), "regimes": r245.load_regimes(),
            "parity": _load("parity", "scripts/sim_c1x_parity.py")}

@pytest.mark.slow
def test_k01_matches_parity_table(env):
    r239 = env["parity"].load_r239()
    bars = r239.hourly_frame(env["market"], r239.load_metrics(), r239.load_premium(), env["funding"])
    signals, _ = r239.build_signals(bars, env["funding"])
    ref = env["parity"].c1x_signals(bars, signals)
    k01 = CATALOG["K01"].build(env["ctx"])
    cols = ["decision_time", "side", "component", "max_hold_min"]
    pick = lambda t: t.loc[(t.side != 0) & t.decision_time.between(LO, HI, inclusive="left"), cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(pick(ref), pick(k01), check_dtype=False)

@pytest.mark.slow
def test_k02_k05_match_r245_signals(env):
    ours = legacy.fast_signals(env["ctx"])
    m = env["fast"].merge(ours, on="decision_time", suffixes=("_ref", ""))
    m = m.loc[m.decision_time.between(LO, HI, inclusive="left")]
    for c in ("E1-15", "A2-30", "F3-30", "F3W-30", "a2_exit_long", "a2_exit_short"):
        assert (m[c + "_ref"].astype(int) == m[c].astype(int)).all(), c

@pytest.mark.slow
@pytest.mark.parametrize("book", sorted(BOOKS))
def test_composite_books_match_r245_with_same_minute_reentry(env, book):
    ref = env["r245"].simulate_fast(BOOKS[book], env["fast"], env["regimes"], env["market"], env["funding"])
    ref = ref.loc[(ref.entry_time >= LO) & (ref.exit_time < HI)].reset_index(drop=True)
    table, _ = build_variant(env["ctx"], book, False, "NATIVE")
    ours = core.simulate(table, env["ctx"].minutes, LO, HI, reference.SimConfig(reentry="stop_and_reverse")).trades
    ours = ours.loc[(ours.entry_time >= LO) & (ours.exit_time < HI)].reset_index(drop=True)
    keys = ["entry_time", "exit_time", "side", "entry_price", "exit_price"]
    pd.testing.assert_frame_equal(ref[keys], ours[keys], check_dtype=False)
    assert abs(ref.net_bps.sum() - ours.net_bps.sum()) < 1e-6
