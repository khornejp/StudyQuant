"""R2-52A Task B: frozen family state / anchor exits (r2_52a_exit_freeze.json family_state_exits) on the NONE/NATIVE
signal tables; BASE tables unchanged versus cfc71e3 (fixture made by .superpowers/sdd/r2_52a/make_b_baseline.py)."""
import hashlib, json
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import core, data, indicators, reference
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant, futures, legacy
from tests.sim.test_adaptive_exit import MODS, at, flat, run, sig

START, END = pd.Timestamp("2022-10-01", tz="UTC"), pd.Timestamp("2023-02-01", tz="UTC")
CUT = pd.Timestamp("2023-01-20 00:07", tz="UTC")
BASELINE = json.loads((Path(__file__).parent / "fixtures" / "r2_52a_b_baseline.json").read_text())
IDS = list(BASELINE)
STATE = ["ax_exit_long", "ax_exit_short", "anchor_upper", "anchor_lower", "anchor_price"]


@pytest.fixture(scope="module")
def ctx():
    return Context.load(end=END, start=START)


def ax(ctx, spec_id):
    return build_variant(ctx, spec_id, gated=False, style="NATIVE", ax=True)[0]


def digest(frame):
    return hashlib.sha256(pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes()).hexdigest()


def same(a, b):
    np.testing.assert_array_equal(np.asarray(a), np.asarray(b))


def test_included_ids_frozen():
    assert len(IDS) == 29


@pytest.mark.parametrize("spec_id", IDS)
def test_base_tables_unchanged(ctx, spec_id):
    base = BASELINE[spec_id]
    table, config = build_variant(ctx, spec_id, gated=False, style="NATIVE")
    raw = CATALOG[spec_id].build(ctx)
    assert len(table) == base["rows"] and repr(config) == base["config"]
    assert digest(table[base["variant_columns"]]) == base["variant"]
    assert digest(raw[base["build_columns"]]) == base["build"]
    # ax=True keeps every pre-existing row and column; extra rows (K01, K14) are inert side-0 rows
    full = ax(ctx, spec_id)
    extra = full.merge(table[["decision_time", "component"]], how="left", indicator=True)._merge == "left_only"
    keep = full.loc[~extra.to_numpy()].reset_index(drop=True)
    pd.testing.assert_frame_equal(keep[base["variant_columns"]], table[base["variant_columns"]])
    assert set(STATE) <= set(full)
    inert = full.loc[extra.to_numpy()]
    assert (inert.side == 0).all() and not inert.allow_entry.any() and not (inert.exit_long | inert.exit_short).any()
    assert extra.any() == (spec_id in ("K01", "K14"))


@pytest.mark.parametrize("spec_id", IDS)
def test_prefix_invariance(ctx, spec_id):
    full, cut = ax(ctx, spec_id), ax(ctx.truncate(CUT), spec_id)
    pd.testing.assert_frame_equal(full.loc[full.decision_time <= CUT].reset_index(drop=True),
                                  cut.loc[cut.decision_time <= CUT].reset_index(drop=True), check_dtype=False)


# ---- dynamic state flags ----
NATIVE_STATE = {"K05", "K08", "K09", "K13", "K15", "K26", "K29"}     # freeze: "retain the existing flags"


@pytest.mark.parametrize("spec_id", sorted(NATIVE_STATE))
def test_native_state_is_the_existing_flags(ctx, spec_id):
    t = ax(ctx, spec_id)
    assert not (t.ax_exit_long | t.ax_exit_short).any() and t[STATE[2:]].isna().all().all()


def test_k09_k15_k26_k29_native_formulas(ctx):
    b = ctx.bars(15)
    bb = indicators.bollinger(b.close, 20, 2.0)
    t = ax(ctx, "K09"); same(t.exit_long, b.close >= bb.middle); same(t.exit_short, b.close <= bb.middle)
    vwap = indicators.vwap_utc(b)
    t = ax(ctx, "K15"); same(t.exit_long, b.close >= vwap); same(t.exit_short, b.close <= vwap)


def _hourly_g(ctx):
    h = ctx.bars(60)
    g = pd.Series(data.asof(pd.DatetimeIndex(ctx.metrics.available_time), ctx.metrics.global_ls.to_numpy(float),
                            pd.DatetimeIndex(h.decision_time), ttl=None))
    return h, g


def test_k01_f3_median_and_e1_anchor(ctx):
    h, g = _hourly_g(ctx)
    q50 = g.rolling(2160, min_periods=720).quantile(.5)
    t = ax(ctx, "K01")
    f3, e1 = t.loc[t.component == legacy.F3], t.loc[t.component == legacy.E1]
    assert len(f3) == len(e1) == len(h)                        # both components on every hour
    same(f3.ax_exit_long, (g >= q50)); same(f3.ax_exit_short, (g <= q50))
    assert f3[STATE[2:]].isna().all().all()
    same(e1.anchor_price, h.close); same(e1.anchor_upper, h.high.rolling(20, min_periods=20).max().shift())
    assert not (e1.ax_exit_long | e1.ax_exit_short).any() and e1.anchor_lower.isna().all()
    assert (g >= q50).any() and (g <= q50).any()


def _fast_g(ctx, window):
    h, g = _hourly_g(ctx)
    q50 = g.rolling(window, min_periods=720).quantile(.5)
    b30 = ctx.bars(30)
    fixed = pd.merge_asof(b30[["decision_time"]], pd.DataFrame({"decision_time": h.decision_time, "q": q50}),
                          on="decision_time", direction="backward").q
    current = data.asof(pd.DatetimeIndex(ctx.metrics.available_time), ctx.metrics.global_ls.to_numpy(float),
                        pd.DatetimeIndex(b30.decision_time), ttl=None)
    return b30, current >= fixed, current <= fixed


@pytest.mark.parametrize("spec_id,window", [("K02", 2160), ("K03", 720)])
def test_f3_f3w_median_at_30m(ctx, spec_id, window):
    b30, long_exit, short_exit = _fast_g(ctx, window)
    t = ax(ctx, spec_id).set_index("decision_time")
    same(t.ax_exit_long.reindex(b30.decision_time), long_exit); same(t.ax_exit_short.reindex(b30.decision_time), short_exit)


def test_k23_top_ls_median(ctx):
    b = ctx.bars(60)
    top = pd.Series(data.asof(pd.DatetimeIndex(ctx.metrics.available_time), ctx.metrics.top_ls.to_numpy(float),
                              pd.DatetimeIndex(b.decision_time), ttl=None))
    q50 = top.rolling(720, min_periods=720).quantile(.5)
    t = ax(ctx, "K23")
    same(t.ax_exit_long, top >= q50); same(t.ax_exit_short, top <= q50)


def test_k04_strict_breakout_flag(ctx):
    b = ctx.bars(15)
    t = ax(ctx, "K04").set_index("decision_time")
    level = b.high.rolling(20, min_periods=20).max().shift()
    same(t.ax_exit_long.reindex(b.decision_time), b.high < level)       # strict '<'; NaN level -> no exit
    assert not t.ax_exit_short.any()                                     # E1 is long only


@pytest.mark.parametrize("spec_id,minutes", [("K11_15m", 15), ("K11_1h", 60)])
def test_k11_ema_diff(ctx, spec_id, minutes):
    b = ctx.bars(minutes)
    diff = indicators.ema(b.close, 9) - indicators.ema(b.close, 21)
    t = ax(ctx, spec_id)
    same(t.ax_exit_long, diff <= 0); same(t.ax_exit_short, diff >= 0)


@pytest.mark.parametrize("spec_id,minutes", [("K12_30m", 30), ("K12_1h", 60)])
def test_k12_supertrend_direction(ctx, spec_id, minutes):
    d = indicators.supertrend(ctx.bars(minutes), 10, 3.0)
    t = ax(ctx, spec_id)
    same(t.ax_exit_long, d != 1); same(t.ax_exit_short, d != -1)


@pytest.mark.parametrize("spec_id,column,entry_sign", [("K19", "ind_premium_z", -1), ("K21_A", "ind_taker_share_z", 1),
                                                       ("K21_B", "ind_taker_share_z", -1), ("K24", None, 1)])
def test_z_sign_exit(ctx, spec_id, column, entry_sign):
    raw = CATALOG[spec_id].build(ctx)
    if column is None:          # K24 publishes no indicator column: recompute its 15 m taker-LSR z
        b = ctx.bars(15)
        z = indicators.zscore_past(pd.Series(futures._metric(ctx, "taker_lsr", b.decision_time)), futures.DAYS30_15M,
                                   futures.DAYS30_15M // 2).to_numpy(float)
    else:
        z = raw[column].to_numpy(float)
    t = ax(ctx, spec_id)
    # a long entered with sign(entry_z) = entry_sign; exit when current_z * entry_z <= 0, both finite
    with np.errstate(invalid="ignore"):
        same(t.ax_exit_long, np.isfinite(z) & (z * entry_sign <= 0))
        same(t.ax_exit_short, np.isfinite(z) & (-z * entry_sign <= 0))
    odd = futures._z_state([np.nan, np.inf, -np.inf, 0.0], 1)          # NaN/inf: no exit; z = 0 exits both
    same(odd["ax_exit_long"], [False, False, False, True]); same(odd["ax_exit_short"], [False, False, False, True])
    entries = raw.side.to_numpy() != 0
    assert entries.any() and (np.sign(z[entries]) == entry_sign * raw.side.to_numpy()[entries]).all()


# ---- frozen anchors ----
@pytest.mark.parametrize("spec_id", ["K06_k0.5", "K06_k1.0", "K07_k0.5", "K07_k1.0"])
def test_oco_band_anchor(ctx, spec_id):
    t = ax(ctx, spec_id)
    same(t.anchor_upper, t.upper); same(t.anchor_lower, t.lower)
    raw = CATALOG[spec_id].build(ctx)
    same(t.anchor_price, raw.ind_close)


def test_k14_range_anchor_on_every_5m_bar(ctx):
    b = ctx.bars(5)
    t = ax(ctx, "K14")
    same(t.decision_time, b.decision_time)
    same(t.anchor_price, b.close)
    oco = t.entry == "oco"
    assert oco.sum() > 100
    same(t.anchor_upper[oco], t.upper[oco]); same(t.anchor_lower[oco], t.lower[oco])
    assert t.loc[~oco, ["anchor_upper", "anchor_lower"]].isna().all().all()


def test_k30_retest_level(ctx):
    b = ctx.bars(15)
    raw = CATALOG["K30"].build(ctx)
    t = ax(ctx, "K30")
    entries = raw.side.to_numpy() != 0
    assert entries.any() and np.isfinite(raw.ind_level[entries]).all() and raw.ind_level[~entries].isna().all()
    same(t.anchor_upper, raw.ind_level); same(t.anchor_lower, raw.ind_level); same(t.anchor_price, b.close)
    close, side = b.close.to_numpy()[entries], raw.side.to_numpy()[entries]
    assert (side * (close - raw.ind_level.to_numpy()[entries]) > 0).all()      # retest bar closed beyond the level


# ---- composites: each component keeps its own state ----
@pytest.mark.parametrize("book", ["B1", "B2", "B3"])
def test_composite_component_state(ctx, book):
    t = ax(ctx, book)
    for component, single in ((legacy.F3_30, "K02"), (legacy.F3W_30, "K03"), (legacy.E1_15, "K04")):
        part = t.loc[t.component == component].set_index("decision_time")
        ref = ax(ctx, single).set_index("decision_time")
        for c in STATE[:2]:
            same(part[c].reindex(ref.index), ref[c])
    a2 = t.loc[t.component == legacy.A2_30]
    assert not (a2.ax_exit_long | a2.ax_exit_short).any() and t[STATE[2:]].isna().all().all()


# ---- engine: R2_52A evaluates ax_exit_* of the held component; BASE ignores them ----
@MODS
@pytest.mark.parametrize("side", [1, -1])
def test_engine_ax_flag(mod, side):
    m = flat()
    key = "ax_exit_long" if side == 1 else "ax_exit_short"
    rows = [{"at": 15, "side": side, key: False, "component": 1},
            {"at": 20, "side": 0, key: True, "component": 2},          # other component: ignored
            {"at": 30, "side": 0, key: True, "component": 1}]
    s = sig([{**r, "ax_exit_long": r.get("ax_exit_long", False), "ax_exit_short": r.get("ax_exit_short", False)}
             for r in rows])
    t = run(mod, s, m).trades.iloc[0]
    assert t.exit_time == at(31) and t.exit_reason == "flag"
    cfg = reference.SimConfig(include_funding=False)
    base = mod.simulate(s, m, m.open_time.iloc[0], m.open_time.iloc[-1] + pd.Timedelta(minutes=1), cfg).trades
    assert base.iloc[0].exit_reason == "max_hold"


@pytest.mark.parametrize("spec_id", ["K01", "K14"])
def test_inert_rows_keep_base_sim(ctx, spec_id):
    table, config = build_variant(ctx, spec_id, gated=False, style="NATIVE")
    full = ax(ctx, spec_id)
    a = core.simulate(table, ctx.minutes, START, END, config).trades
    b = core.simulate(full, ctx.minutes, START, END, config).trades
    assert len(a) > 10
    pd.testing.assert_frame_equal(a, b)
