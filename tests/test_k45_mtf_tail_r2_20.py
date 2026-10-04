import numpy as np
import pandas as pd

from out import run_k45_mtf_tail_r2_20 as run


def _scores() -> pd.DataFrame:
    return pd.DataFrame({
        "pilot_fold": np.repeat([0, 1, 2], 4),
        "decision_time": pd.date_range("2026-01-01", periods=12, freq="h", tz="UTC"),
        "edge_long": np.arange(12, dtype=float),
        "edge_short": np.arange(12, dtype=float)[::-1],
    })


def test_thresholds_never_use_current_or_future_fold_scores():
    original = _scores()
    changed = original.copy()
    changed.loc[changed.pilot_fold.ge(1), ["edge_long", "edge_short"]] = 1e9
    for method in run.THRESHOLD_METHODS:
        left = run.causal_cutoffs(original, method, min_expanding=2)
        right = run.causal_cutoffs(changed, method, min_expanding=2)
        target = left.pilot_fold.eq(1)
        columns = [name for name in left if "cutoff" in name]
        pd.testing.assert_frame_equal(left.loc[target, columns], right.loc[target, columns])
        measured = left.reference_max_fold.ge(0)
        assert (left.loc[measured, "reference_max_fold"] <
                left.loc[measured, "pilot_fold"]).all()


def test_r2_12_e0_reproduction_matches_trades_and_gross():
    result = run.reproduce_e0()
    assert len(result) == 8
    assert result.n_diff.eq(0).all()
    assert np.allclose(result.gross_sum_bps_diff, 0.0, atol=1e-9)


def test_tail_book_never_overlaps():
    candidates = pd.DataFrame({
        "signal_time": pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 00:30Z",
                                        "2026-01-01 01:00Z"]),
        "entry_time": pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 00:30Z",
                                       "2026-01-01 01:00Z"]),
        "exit_time": pd.to_datetime(["2026-01-01 01:00Z", "2026-01-01 01:30Z",
                                      "2026-01-01 02:00Z"]),
    })
    accepted, _ = run.admit_tail_positions(candidates)
    assert run.max_concurrent(accepted) <= 1


def test_equal_arm_scores_never_trade():
    frame = pd.DataFrame({"edge_long": [1.0], "edge_short": [1.0]})
    cutoffs = pd.DataFrame({"score_cutoff_q01": [0.0],
                            "edge_long_cutoff_q01": [0.0],
                            "edge_short_cutoff_q01": [0.0]})
    assert run.select_tail(frame, cutoffs, "MAX", 0.01).side.iat[0] == 0
    assert run.select_tail(frame, cutoffs, "SIDE", 0.01).side.iat[0] == 0


def test_pw_block_below_one_is_clamped():
    seen = []

    def selector(_):
        return {"block_length_stationary": 0.25}

    def bootstrap(centered, block, reps, seed):
        seen.append(block)
        return np.zeros(reps)

    result = run.pw_statistics(2.0, np.array([1.0, 3.0]), selector=selector,
                               bootstrap=bootstrap, reps=10)
    assert seen == [1.0]
    assert result["pw_status"] == "MEASURABLE_BLOCK1"
    assert result["pw_block"] == 1.0
