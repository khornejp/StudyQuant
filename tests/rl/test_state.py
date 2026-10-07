"""Causal state store (plan 3 Task 2, contract C7-C9): synthetic-data unit tests plus slow real-data checks."""
import dataclasses
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import state
from btcusdt_quant.sim import data, regime
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant

T0 = pd.Timestamp("2024-01-01", tz="UTC")
DAYS = 12
START, END = T0 + pd.Timedelta(days=8), T0 + pd.Timedelta(days=DAYS)
HOLE = (T0 + pd.Timedelta(days=10), T0 + pd.Timedelta(days=11))       # one day without predictions
CUTS = [START + pd.Timedelta(x) for x in ("13h", "1d 2h 45min", "2d 3h", "2d 23h 15min", "3d 23h 45min")]


def synthetic_ctx(seed: int = 0) -> Context:
    rng = np.random.default_rng(seed)
    n = DAYS * 1440
    t = pd.date_range(T0, periods=n, freq="1min", tz="UTC")
    close = 40_000 * np.exp(np.cumsum(rng.normal(0, 8e-4, n)))
    open_ = np.r_[close[0], close[:-1]]
    volume = rng.uniform(1, 10, n)
    minutes = pd.DataFrame({"open_time": t, "open": open_, "high": np.maximum(open_, close) * (1 + rng.uniform(0, 4e-4, n)),
                            "low": np.minimum(open_, close) * (1 - rng.uniform(0, 4e-4, n)), "close": close,
                            "volume": volume, "quote_volume": volume * close, "number_of_trades": 10,
                            "taker_buy_base_volume": volume * rng.uniform(.3, .7, n)})
    t5 = t[::5]
    metrics = pd.DataFrame({"available_time": t5 + pd.Timedelta(minutes=5), "global_ls": rng.uniform(.8, 2.5, len(t5)),
                            "top_ls": rng.uniform(.8, 2.5, len(t5)), "oi": 1e5 * np.exp(np.cumsum(rng.normal(0, 1e-3, len(t5)))),
                            "oi_value": 1.0, "taker_lsr": rng.uniform(.5, 1.5, len(t5))})
    premium = pd.DataFrame({"available_time": t + pd.Timedelta(minutes=1), "premium": rng.normal(0, 3e-4, n)})
    settle = pd.date_range(T0, periods=DAYS * 3, freq="8h", tz="UTC")
    funding = pd.DataFrame({"time": settle, "rate": rng.normal(1e-4, 1e-4, len(settle))})
    stamps = pd.date_range(T0, periods=DAYS * 96, freq="15min", tz="UTC")
    stamps = stamps[(stamps < HOLE[0]) | (stamps >= HOLE[1])]
    predictions = pd.DataFrame({"timestamp": stamps, "retrain_time": stamps,
                                **{f"prediction_{k}": rng.uniform(10, 300, len(stamps)) for k in data.TARGETS}})
    return Context(minutes=minutes, metrics=metrics, premium=premium, funding=funding,
                   regime=regime.load_regime(predictions), end=t[-1] + pd.Timedelta(minutes=1))


@pytest.fixture(scope="module")
def ctx():
    return synthetic_ctx()


@pytest.fixture(scope="module", params=["S1", "S3"])
def store(request, ctx):
    return state.build_state_store(ctx, START, END, request.param)


def _assert_rows_equal(a: state.StateStore, b: state.StateStore, rows: int):
    assert a.feature_names == b.feature_names and a.variant == b.variant
    np.testing.assert_array_equal(a.times[:rows], b.times[:rows])
    np.testing.assert_array_equal(a.seq[:rows], b.seq[:rows])
    np.testing.assert_array_equal(a.static[:rows], b.static[:rows])
    np.testing.assert_array_equal(a.mask_missing[:rows], b.mask_missing[:rows])


def test_shapes_and_names(store):
    n = len(pd.date_range(START, END, freq="15min", inclusive="left"))
    assert store.times.dtype == np.int64 and len(store.times) == n
    assert store.seq.shape == (n, 32, len(state.SEQ_NAMES)) and store.seq.dtype == np.float32
    assert store.static.shape == (n, len(store.feature_names)) and store.static.dtype == np.float32
    assert len(set(store.feature_names)) == len(store.feature_names)
    assert not any("ind_" in name for name in store.feature_names)
    s3 = [name for name in store.feature_names if name.startswith("s3_") and not name.endswith("__nan")]
    assert len(s3) == (10 if store.variant == "S3" else 0)


def test_prefix_invariance(ctx, store):
    for t in CUTS:
        cut = state.build_state_store(ctx.truncate(t), START, t + pd.Timedelta(minutes=15), store.variant)
        rows = int(np.searchsorted(store.times, t.value, side="right"))
        assert len(cut.times) == rows
        _assert_rows_equal(store, cut, rows)


def test_hourly_signal_not_visible_before_bar_close():
    times = pd.DatetimeIndex(["2024-01-01 09:45", "2024-01-01 10:00", "2024-01-01 10:45", "2024-01-01 11:15"], tz="UTC")
    hourly = pd.DataFrame({"decision_time": pd.DatetimeIndex(["2024-01-01 09:00", "2024-01-01 10:00", "2024-01-01 11:00"],
                                                             tz="UTC"), "side": [0, 1, 0], "allow_entry": True})
    event, last, age, never = state.side_channels(hourly, times, five_minute=False)
    np.testing.assert_array_equal(event, [0, 1, 1, 0])       # backward as-of decision_time <= T
    np.testing.assert_array_equal(last, [0, 1, 1, 1])
    np.testing.assert_array_equal(never, [1, 0, 0, 0])
    np.testing.assert_allclose(age, [1.0, 0.0, np.log1p(45) / np.log1p(10080), np.log1p(75) / np.log1p(10080)])
    five = pd.DataFrame({"decision_time": pd.DatetimeIndex(["2024-01-01 09:50", "2024-01-01 10:05"], tz="UTC"),
                         "side": [-1, 0], "allow_entry": True})
    event, last, _, never = state.side_channels(five, times, five_minute=True)
    np.testing.assert_array_equal(event, [0, -1, 0, 0])      # latest nonzero event in (T - 15m, T]
    np.testing.assert_array_equal(last, [0, -1, -1, -1])
    np.testing.assert_array_equal(never, [1, 0, 0, 0])


def test_store_signal_channels_match_tables(ctx, store):
    times = pd.DatetimeIndex(store.times, tz="UTC")
    for spec_id in ("K01", "K16", "K11_1h"):
        table, _ = build_variant(ctx, spec_id, gated=False, style="NATIVE")
        event = store.static[:, store.feature_names.index(f"{spec_id}_event_side")]
        visible = table.loc[table.decision_time <= times[-1]]
        hourly = CATALOG[spec_id].cadence_min >= 60
        if hourly:      # off-hour rows repeat the hour's evaluation, never the next hour's
            at = pd.merge_asof(pd.DataFrame({"t": times}), visible.rename(columns={"decision_time": "t"}), on="t")
            np.testing.assert_array_equal(event, at.side.fillna(0).to_numpy())
        else:
            assert set(np.unique(event)) <= {-1, 0, 1}


def test_normalizer_ignores_post_train_rows(store):
    train_end = pd.Timestamp(store.times[len(store.times) // 2], tz="UTC")
    norm = state.fit_normalizer(store, train_end)
    after = store.times > train_end.value
    noisy = dataclasses.replace(store, static=store.static.copy(), seq=store.seq.copy())
    noisy.static[after] += 1e6
    noisy.seq[after] += 1e6
    again = state.fit_normalizer(noisy, train_end)
    for a, b in ((norm.static_mean, again.static_mean), (norm.static_std, again.static_std),
                 (norm.seq_mean, again.seq_mean), (norm.seq_std, again.seq_std)):
        np.testing.assert_array_equal(a, b)
    out = norm.apply(store)
    assert np.isfinite(out.static).all() and np.isfinite(out.seq).all()
    unscaled = [k for k, name in enumerate(store.feature_names) if not state.is_scaled(name)]
    np.testing.assert_array_equal(out.static[:, unscaled], np.nan_to_num(store.static[:, unscaled]))
    for name in ("K01_event_side", "K01_last_side", "K01_never_seen", "missing", "dow_sin", "hour_cos",
                 "K06_k0.5_proposal_active", "pred_range_1h__nan"):
        assert not state.is_scaled(name), name
    for name in ("pred_range_1h", "M", "d_oi_1h", "funding_bps", "h1_ret", "K06_k0.5_upper_bps"):
        assert state.is_scaled(name), name


def test_normalizer_excludes_warmup_rows(ctx):
    early = state.build_state_store(ctx, T0 + pd.Timedelta(days=7), T0 + pd.Timedelta(days=9), "S1")
    shifted = dataclasses.replace(early, times=early.times - pd.Timedelta(days=679).value)   # [2022-02-28, 2022-03-02)
    train_end = pd.Timestamp(shifted.times[-1], tz="UTC")
    norm = state.fit_normalizer(shifted, train_end)
    noisy = dataclasses.replace(shifted, static=shifted.static.copy())
    noisy.static[shifted.times < state.TRAIN_START.value] += 1e6
    np.testing.assert_array_equal(norm.static_mean, state.fit_normalizer(noisy, train_end).static_mean)


def test_missing_prediction_days_masked_not_filled(ctx):
    s = state.build_state_store(ctx, START, END, "S1")
    times = pd.DatetimeIndex(s.times, tz="UTC")
    hole = (times >= HOLE[0]) & (times < HOLE[1])
    assert hole.sum() == 96
    np.testing.assert_array_equal(s.mask_missing, hole | ~np.isfinite(s.static[:, s.feature_names.index("M")]))
    assert s.mask_missing[hole].all() and not s.mask_missing[~hole].any()
    for name in ("pred_range_1h", "M", "L"):
        assert np.isnan(s.static[hole, s.feature_names.index(name)]).all()            # not interpolated
        assert (s.static[hole, s.feature_names.index(name + "__nan")] == 1).all()
    assert (s.static[hole, s.feature_names.index("missing")] == 1).all()


def test_signal_ids_exclude_composites_grid_oco(store):
    core = [k for k, v in CATALOG.items() if v.simulator == "core"]
    assert set(state.SIGNAL_IDS) | set(state.OCO_IDS) == set(core) - {"B1", "B2", "B3"}
    assert not set(state.SIGNAL_IDS) & set(state.OCO_IDS)
    assert {k.split("_")[0] for k in state.OCO_IDS} == {"K06", "K07", "K14"}
    assert "K10" not in state.SIGNAL_IDS + state.OCO_IDS
    for spec_id in state.SIGNAL_IDS:
        assert [f"{spec_id}_{c}" in store.feature_names for c in ("event_side", "last_side", "age", "never_seen")] == [True] * 4
        assert f"{spec_id}_proposal_active" not in store.feature_names
    for spec_id in state.OCO_IDS:
        assert [f"{spec_id}_{c}" in store.feature_names for c in ("proposal_active", "upper_bps", "lower_bps")] == [True] * 3
        assert f"{spec_id}_event_side" not in store.feature_names


def test_oco_ids_are_the_oco_entry_tables(ctx):
    for spec_id in state.SIGNAL_IDS + state.OCO_IDS:
        table, _ = build_variant(ctx, spec_id, gated=False, style="NATIVE")
        assert (spec_id in state.OCO_IDS) == (table.entry == "oco").any(), spec_id


@pytest.mark.slow
def test_real_missing_days_masked():
    ctx = Context.load(end=pd.Timestamp("2026-01-01", tz="UTC"), start=pd.Timestamp("2025-12-01", tz="UTC"))
    full = dataclasses.replace(ctx, regime=regime.load_regime(data.load_predictions(end=ctx.end)), _bars={})
    s = state.build_state_store(full, pd.Timestamp("2025-12-20", tz="UTC"), ctx.end, "S1")
    times = pd.DatetimeIndex(s.times, tz="UTC")
    assert s.mask_missing.sum() == 96 and (times[s.mask_missing].date == pd.Timestamp("2025-12-31").date()).all()
    # mask_missing reads only the detector frame, so the 2023 range needs no 2023 minutes here
    s23 = state.build_state_store(full, pd.Timestamp("2023-12-20", tz="UTC"), pd.Timestamp("2024-01-10", tz="UTC"), "S1")
    times = pd.DatetimeIndex(s23.times, tz="UTC")
    assert s23.mask_missing.sum() == 96 and (times[s23.mask_missing].date == pd.Timestamp("2023-12-31").date()).all()


@pytest.mark.slow
def test_real_prefix_invariance():
    ctx = Context.load(end=pd.Timestamp("2023-03-01", tz="UTC"), start=pd.Timestamp("2022-10-01", tz="UTC"))
    start = pd.Timestamp("2023-02-20", tz="UTC")
    for variant in ("S1", "S3"):
        full = state.build_state_store(ctx, start, ctx.end, variant)
        for t in (pd.Timestamp("2023-02-24 10:45", tz="UTC"), pd.Timestamp("2023-02-27 16:00", tz="UTC")):
            cut = state.build_state_store(ctx.truncate(t), start, t + pd.Timedelta(minutes=15), variant)
            _assert_rows_equal(full, cut, len(cut.times))


def test_cached_store_round_trip(ctx, tmp_path):
    built = state.build_state_store(ctx, START, START + pd.Timedelta(days=1), "S3")
    first = state.cached_state_store(ctx, START, START + pd.Timedelta(days=1), "S3", root=tmp_path)
    again = state.cached_state_store(ctx, START, START + pd.Timedelta(days=1), "S3", root=tmp_path)
    assert len(list(tmp_path.rglob("*.parquet"))) == 1
    for s in (first, again):
        _assert_rows_equal(built, s, len(built.times))
