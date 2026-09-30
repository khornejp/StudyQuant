import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from out import run_patchtst_k45_causal_admission_ordering as runner


def test_stable_deciles_are_equal_count_and_tie_deterministic():
    frame = pd.DataFrame({
        "score": np.ones(20), "pilot_fold": np.repeat([1, 2], 10),
        "entry_index": np.arange(20)[::-1],
    })
    first = runner.stable_deciles(frame, "score")
    second = runner.stable_deciles(frame.sample(frac=1, random_state=7), "score").sort_index()
    assert first.value_counts().sort_index().tolist() == [2] * 10
    assert first.equals(second)


def test_cluster_rank_slope_equals_spearman():
    x = np.array([3., 1., 4., 2., 6., 5.])
    y = np.array([2., 1., 3., 4., 6., 5.])
    result = runner.cluster_rank_test(x, y, np.array([0, 0, 1, 1, 2, 2]))
    assert np.isclose(result["cluster_rho"], pd.Series(x).corr(pd.Series(y), method="spearman"))


def test_contrast_hac_estimate_is_top_minus_bottom():
    rows = []
    for decile in range(1, 11):
        for fold in range(3):
            rows.append({"decile": decile, "pilot_fold": fold,
                         "none_net_lin_bps": float(decile + fold)})
    result = runner.contrast_hac(pd.DataFrame(rows))
    assert np.isclose(result["top_minus_bottom_bps"], 9.0)
    assert result["top_bottom_hac_ci95_lower_bps"] <= 9.0 <= result["top_bottom_hac_ci95_upper_bps"]


def test_frozen_zero_fit_contract_and_plan_hash():
    digest = hashlib.sha256(runner.PLAN.read_bytes()).hexdigest()
    assert runner.PLAN_HASH.read_text(encoding="utf-8").split()[0] == digest
    assert len(runner.FEATURES) == 10
    assert len(runner.FEATURES) * len(runner.audit.ARMS) == 20
    assert runner.RHO_MIN == .05 and runner.BONFERRONI_P == .0025
    assert runner.FIT_CALLS == 0
