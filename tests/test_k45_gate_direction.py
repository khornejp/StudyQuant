import numpy as np
import pandas as pd
import pytest

from out import k45_gate_direction as gd


def test_label_45_thresholds_are_strict():
    close = np.full(200, 100.0)
    close[45] = 100.0399
    close[46] = 100.0401
    close[47] = 99.9599
    r, cls = gd.label_45(close, np.array([0, 1, 2]))
    assert cls.tolist() == [1, 2, 0]
    assert r[0] == pytest.approx(3.99)


def test_label_45_refuses_out_of_range():
    with pytest.raises(IndexError):
        gd.label_45(np.ones(50), np.array([10]))


def test_microstructure_join_is_exact_time_only():
    bars = pd.DataFrame({
        "open_time": pd.date_range("2024-01-01", periods=3, freq="min", tz="UTC")
    })
    micro = pd.DataFrame({"open_time": bars.open_time.iloc[[0, 2]], "x": [1.0, 3.0]})
    from out import run_k45_gate_direction_dataset as ds

    got = ds.join_exact(bars.iloc[[1]], micro, prefix="m_")
    assert np.isnan(got["m_x"].iloc[0])


def test_monthly_sign_test_detects_consistent_relation():
    rng = np.random.default_rng(0)
    month = np.repeat(np.arange(24), 100)
    x = rng.normal(size=len(month))
    r = x + rng.normal(size=len(month))
    got = gd.monthly_sign_test(x, r, month)
    assert got["agree_months"] == 24 and got["p_one_sided"] < 1e-6


def test_monthly_sign_test_drops_thin_and_constant_months():
    month = np.array([0] * 10 + [1] * 50)
    x = np.r_[np.arange(10.), np.zeros(50)]
    got = gd.monthly_sign_test(x, np.arange(60.), month)
    assert got["n_months"] == 0


def test_predict_proba3_fills_missing_class():
    class Stub:
        classes_ = np.array([0, 2])

        def predict_proba(self, X):
            return np.tile([0.3, 0.7], (len(X), 1))

    p = gd.predict_proba3(Stub(), np.zeros((2, 1)))
    assert p.tolist() == [[0.3, 0.0, 0.7], [0.3, 0.0, 0.7]]


def test_select_features_uses_only_given_rows_and_falls_back():
    rng = np.random.default_rng(1)
    n = 3000
    df = pd.DataFrame({
        "month": np.repeat(np.arange(30), 100),
        "a": rng.normal(size=n),
        "b": rng.normal(size=n),
    })
    df["r45_bps"] = rng.normal(size=n)
    cols, mode = gd.select_features(df, ["a", "b"], k_min=5, k_fallback=1)
    assert mode == "FALLBACK" and len(cols) == 1


def test_training_rows_are_purged_before_stop():
    from out import run_k45_gate_direction_walkforward as wf

    ds = pd.DataFrame({"signal_index": [100, 154, 155, 200]})
    assert wf.train_mask(ds, stop_start_index=200).tolist() == [True, True, False, False]


def test_zero_test_rows_are_skipped():
    from out import run_k45_gate_direction_walkforward as wf

    assert wf.skip_reason(n_train=2000, n_test=0) == "zero_test_rows"


def test_valid_flags_become_numeric_and_other_text_is_rejected():
    from out import run_k45_gate_direction_walkforward as wf

    frame = pd.DataFrame({"m_book_valid": [True, False], "f_x": [1.0, 2.0]})
    got = wf.prepare_feature_frame(frame, ["m_book_valid", "f_x"])
    assert got.dtypes.tolist() == [np.dtype("int8"), np.dtype("float64")]
    with pytest.raises(TypeError, match="non-numeric"):
        wf.prepare_feature_frame(pd.DataFrame({"f_bad": ["x"]}), ["f_bad"])


def test_decile_table_is_monotone_on_perfect_score():
    from out import run_k45_gate_direction_quality as q

    s = np.arange(1000.)
    t = q.decile_table(s, s)
    assert t.decile.tolist() == list(range(10))
    assert np.all(np.diff(t.r_mean) > 0)


def test_choose_side_margin_is_strict():
    from out import run_k45_gate_direction_backtest as bt

    got = bt.choose_side(
        np.array([.50, .60, .30, .36]),
        np.array([.45, .45, .45, .45]),
        0.10,
    )
    assert got.tolist() == [0, 1, -1, 0]
