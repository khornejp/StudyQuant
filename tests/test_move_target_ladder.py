"""Guards for the five-arm ladder.

The silent failures here are causality (a feature or threshold reading a bar it
should not) and arm confusion (two rungs differing by more than one thing).
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from out import run_patchtst_move_target_ladder as ladder


def test_every_contrast_changes_exactly_one_thing():
    for low, high in ladder.CONTRASTS:
        if low == "A0":
            continue  # A0 is the frozen blend, compared for its own sake
        a, b = ladder.ARMS[low], ladder.ARMS[high]
        changed = [k for k in ("target", "threshold", "trend", "loss", "depth") if a[k] != b[k]]
        if a["target"] != b["target"]:
            # a sign target has no threshold, and a two-class BCE is the same
            # objective as a two-class CE, so going ternary entails both moves
            changed = [k for k in changed if k != "threshold"]
            if (a["loss"], b["loss"]) == ("bce", "ce"):
                changed = [k for k in changed if k != "loss"]
        assert len(changed) == 1, f"{low} -> {high} changes {changed}"


def test_slope_weights_recover_a_known_gradient():
    y = np.array([1.0, 3.0, 5.0, 7.0])  # slope 2 per step
    # the weights are pre-reversed for np.convolve, which flips the kernel again
    assert float(np.convolve(y, ladder.slope_weights(4), mode="valid")[0]) == pytest.approx(2.0)


def test_slope_weights_sign_follows_the_direction_of_travel():
    falling = np.array([7.0, 5.0, 3.0, 1.0])
    assert float(np.convolve(falling, ladder.slope_weights(4), mode="valid")[0]) == pytest.approx(-2.0)


def test_causal_slope_leaves_the_warmup_unknown_and_reads_no_future_bar():
    series = np.arange(50, dtype=float)
    out = ladder.causal_slope(series, 5, 10)
    assert np.isnan(out[:9]).all(), "the first window-1 rows cannot have a slope"
    assert np.isfinite(out[9:]).all()
    # perturbing a future bar must not change an earlier slope
    moved = series.copy()
    moved[40] += 1000.0
    assert ladder.causal_slope(moved, 5, 10)[30] == pytest.approx(out[30])


def test_trend_features_read_no_future_bar():
    rng = np.random.default_rng(0)
    close = 100 * np.exp(np.cumsum(rng.normal(0, .0005, 400)))
    frame = pd.DataFrame({"close": close})
    values, valid = ladder.trend_features(frame)
    assert values.shape == (400, len(ladder.TREND_NAMES))
    moved = close.copy()
    moved[350] *= 1.05
    shifted, _ = ladder.trend_features(pd.DataFrame({"close": moved}))
    np.testing.assert_allclose(values[:349], shifted[:349], rtol=0, atol=1e-6)
    assert not valid[:20].any(), "warmup rows must be marked invalid, not silently filled"


def test_vol_threshold_is_causal_and_positive():
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(0, .0005, 300)))
    thresholds = ladder.vol_threshold(close)
    # the window ends at the origin bar, so the first full window closes at VOL_WINDOW-1
    assert np.isnan(thresholds[:ladder.VOL_WINDOW - 1]).all()
    assert (thresholds[ladder.VOL_WINDOW - 1:] > 0).all()
    moved = close.copy()
    moved[250] *= 1.10
    assert ladder.vol_threshold(moved)[200] == pytest.approx(thresholds[200])


def test_vol_threshold_rises_with_realized_volatility():
    rng = np.random.default_rng(2)
    quiet = 100 * np.exp(np.cumsum(rng.normal(0, .0001, 300)))
    loud = 100 * np.exp(np.cumsum(rng.normal(0, .0020, 300)))
    assert np.nanmean(ladder.vol_threshold(loud)) > 5 * np.nanmean(ladder.vol_threshold(quiet))


def test_ternary_targets_accept_a_per_row_threshold():
    forward = np.array([15.0, 15.0, -15.0, 2.0])
    limits = np.array([10.0, 20.0, 10.0, 10.0])
    labels = ladder.ternary_targets(forward, limits)
    assert list(labels) == [ladder.UP, ladder.SMALL, ladder.DOWN, ladder.SMALL]


def test_ternary_targets_still_accept_a_scalar_threshold():
    forward = np.array([15.0, -15.0, 2.0])
    assert list(ladder.ternary_targets(forward, 10.0)) == [ladder.UP, ladder.DOWN, ladder.SMALL]


def test_ternary_targets_mark_an_unknown_threshold_as_unavailable():
    forward = np.array([15.0, 15.0])
    labels = ladder.ternary_targets(forward, np.array([np.nan, 10.0]))
    assert labels[0] == -1 and labels[1] == ladder.UP


def test_no_arm_reuses_the_stopped_runs_weights():
    # every arm now trains on the two-layer encoder, and those weights are one-layer
    for arm in ladder.ORDER:
        assert ladder.ROOT.name in str(ladder.checkpoint(arm, 506, 42)), \
            f"{arm} must never load a checkpoint trained under a different recipe"


def test_the_reuse_guard_still_refuses_once_an_arm_goes_deep(monkeypatch):
    scratch = Path(tempfile.mkdtemp(prefix="ladder_ckpt_"))
    try:
        monkeypatch.setattr(ladder, "ROOT", scratch)
        assert ladder.ARMS["B1"]["depth"] == "deep"
        assert ladder.REUSE.name not in str(ladder.checkpoint("B1", 506, 42))
        # and a local file always wins, so a file appearing in REUSE later cannot
        # change what --verify rebuilds from
        monkeypatch.setitem(ladder.ARMS, "B1", {**ladder.ARMS["B1"], "depth": "shallow"})
        local = scratch / "B1_fold_506_seed_42_h15.pt"
        local.write_bytes(b"")
        assert ladder.checkpoint("B1", 506, 42) == local
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_every_executed_module_is_hashed():
    names = {m.__name__ for m in ladder.SOURCE_MODULES}
    for required in ("out.run_patchtst_move_target_ladder", "out.run_patchtst_move_target_10bps",
                     "btcusdt_quant.short_fast_regime"):
        assert required in names, f"{required} runs but is not pinned by the manifest"
    assert len({m.__file__ for m in ladder.SOURCE_MODULES}) == len(ladder.SOURCE_MODULES), \
        "a module listed twice hashes the same file twice and hides nothing"


def test_the_count_lines_are_separable_from_the_significance_lines():
    a0 = {"coverage": .05, "accepted": {"rows": 2000, "gross_bps": 1.0, "se": .5, "t": 2.0, "hit": .55},
          "accepted_minus_fade": {"rows": 2000, "gross_bps": 0.0, "se": .5, "t": 0.0, "hit": .5},
          "accepted_long": {"rows": 1000}, "accepted_short": {"rows": 1000},
          "by_magnitude": {"50_plus": {"gross_bps": 0.0}}}
    thin = {**a0, "coverage": .034,
            "accepted": {"rows": 950, "gross_bps": 8.0, "se": 1.0, "t": 8.0, "hit": .6},
            "accepted_minus_fade": {"rows": 950, "gross_bps": 5.0, "se": 1.0, "t": 5.0, "hit": .6},
            "accepted_long": {"rows": 500}, "accepted_short": {"rows": 450},
            "by_magnitude": {"50_plus": {"gross_bps": 2.0}}}
    checks = ladder.prior.gate(thin, a0)
    assert not all(checks.values()), "it is short on trade count"
    power = {k: v for k, v in checks.items() if k not in ladder.COUNT_CHECKS}
    assert all(power.values()), "but every significance line holds"
    assert ladder.reading(thin, checks) == "passes on significance, short on trade count"


def test_an_arm_that_barely_trades_reads_as_a_refusal_not_a_thin_sample():
    a0 = {"coverage": .05, "accepted": {"rows": 2000, "gross_bps": 1.0, "se": .5, "t": 2.0, "hit": .55},
          "accepted_minus_fade": {"rows": 2000, "gross_bps": 0.0, "se": .5, "t": 0.0, "hit": .5},
          "accepted_long": {"rows": 1000}, "accepted_short": {"rows": 1000},
          "by_magnitude": {"50_plus": {"gross_bps": 0.0}}}
    silent = {**a0, "coverage": .001,
              "accepted": {"rows": 12, "gross_bps": None, "se": None, "t": None, "hit": None},
              "accepted_minus_fade": {"rows": 12, "gross_bps": None, "se": None, "t": None, "hit": None},
              "accepted_long": {"rows": 6}, "accepted_short": {"rows": 6},
              "by_magnitude": {"50_plus": {"gross_bps": None}}}
    assert ladder.reading(silent, ladder.prior.gate(silent, a0)) == "declined to trade"


def test_the_interval_widens_as_the_sample_thins():
    wide = ladder.interval({"gross_bps": 2.0, "se": 2.0})
    narrow = ladder.interval({"gross_bps": 2.0, "se": 0.4})
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])
    assert wide[0] < 0 < wide[1] and narrow[0] > 0
    assert ladder.interval({"gross_bps": None, "se": None}) is None


def test_only_the_trend_arms_widen_the_input():
    assert [a for a in ladder.ORDER if ladder.ARMS[a]["trend"]] == ["B2", "B3", "B4"]
    assert len(ladder.TREND_NAMES) == 5


def test_every_arm_that_tests_something_runs_on_the_deep_encoder():
    shallow = [a for a in ladder.ORDER if ladder.ARMS[a]["depth"] == "shallow"]
    assert shallow == ["B0"], "only the control against the frozen baseline stays one-layer"


def test_b0d_is_b0_one_layer_deeper_and_nothing_else():
    a, b = ladder.ARMS["B0"], ladder.ARMS["B0d"]
    assert {k: v for k, v in a.items() if k != "depth"} == {k: v for k, v in b.items() if k != "depth"}
    assert ("B0", "B0d") in ladder.CONTRASTS, "depth has to be measured on its own"


def test_the_deep_encoder_stacks_layers_and_leaves_the_head_alone():
    for shallow_arm, deep_arm, channels in (("B0", "B0d", 35),):
        shallow = ladder.make_model(shallow_arm, channels)
        deep = ladder.make_model(deep_arm, channels)
        assert len(shallow.encoder.layers) == 1 and len(deep.encoder.layers) == 2
        head = lambda m: sum(p.numel() for p in m.head.parameters())
        assert head(shallow) == head(deep), "only the encoder may grow"
        enc = lambda m: sum(p.numel() for p in m.encoder.parameters())
        assert enc(deep) > enc(shallow)


def test_each_arm_keeps_its_own_head_width():
    with torch.no_grad():
        assert ladder.make_model("B0d", 35)(torch.zeros(3, 60, 35)).shape == (3, 1)
        assert ladder.make_model("B2", 40)(torch.zeros(3, 60, 40)).shape == (3, 3)
    assert ladder.outputs_of("B0d") == 1 and ladder.outputs_of("B2") == 3


def test_a_deep_arm_can_never_take_the_stopped_runs_one_layer_weights():
    for arm in ladder.ORDER:
        if ladder.ARMS[arm]["depth"] == "deep":
            assert ladder.REUSE.name not in str(ladder.checkpoint(arm, 506, 42))


def test_pnl_objective_prefers_the_profitable_side():
    logits = torch.tensor([[8.0, 0.0, 0.0], [0.0, 0.0, 8.0]])  # confident UP, confident DOWN
    rising = torch.tensor([50.0, 50.0])
    long_right = ladder.pnl_objective(logits[:1], rising[:1], 20.0)
    short_wrong = ladder.pnl_objective(logits[1:], rising[1:], 20.0)
    assert long_right < short_wrong, "being long a rising bar must cost less than being short it"


def test_pnl_objective_is_flat_on_a_bar_that_goes_nowhere():
    flat = torch.tensor([0.0])
    for logits in (torch.tensor([[8.0, 0.0, 0.0]]), torch.tensor([[0.0, 8.0, 0.0]])):
        assert float(ladder.pnl_objective(logits, flat, 1.0)) == pytest.approx(0.0, abs=1e-3)


def test_pnl_objective_rewards_size_when_the_side_is_right():
    small = torch.tensor([[1.0, 0.0, 0.0]])
    large = torch.tensor([[8.0, 0.0, 0.0]])
    rising = torch.tensor([50.0])
    assert float(ladder.pnl_objective(large, rising, 20.0)) < float(ladder.pnl_objective(small, rising, 20.0))


def test_the_loss_does_not_charge_cost_so_the_rung_can_trade():
    # a cost inside the loss drove exposure to exactly zero in smoke; cost is scored, not trained on
    assert ladder.LOSS_COST_BPS == 0.0


def test_winsorized_scale_ignores_a_single_outlier():
    returns = np.concatenate([np.full(999, 10.0), [100000.0]])
    train = np.arange(1000)
    scale, low, high = ladder.winsorized_scale(returns, train)
    assert scale == pytest.approx(10.0, rel=1e-3), "one spike must not set the loss scale"
    assert high < 100000.0


def test_every_arm_is_reached_by_exactly_one_contrast():
    reached = [high for _, high in ladder.CONTRASTS]
    assert sorted(reached) == sorted(ladder.ORDER), "an arm with no contrast measures nothing"
    assert len(reached) == len(set(reached))


def test_the_feature_and_loss_arms_sit_on_the_branch_that_trains():
    # B1v collapsed to SMALL in smoke; B2/B3 must not inherit its threshold rule
    assert ladder.ARMS["B2"]["threshold"] == ladder.ARMS["B1"]["threshold"] == "fixed"
    assert ladder.ARMS["B3"]["threshold"] == "fixed"
    assert ladder.ARMS["B1v"]["threshold"] == "vol"
    assert ("B1", "B1v") in ladder.CONTRASTS, "the threshold rule still has to be measured"


def test_squeeze_survives_a_flat_stretch_without_becoming_infinite():
    close = np.concatenate([np.full(150, 100.0), 100 * np.exp(np.cumsum(
        np.random.default_rng(3).normal(0, .0005, 150)))])
    values, valid = ladder.trend_features(pd.DataFrame({"close": close}))
    assert np.isfinite(values).all(), "a zero-width reference must not leak an inf into the tensor"
    assert not valid[100:140].any(), "a flat stretch has no squeeze, and must be marked invalid"
