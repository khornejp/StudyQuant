import numpy as np
import pandas as pd

from out import run_patchtst_k45_short_signal_veto as veto


def test_short_state_uses_latest_observed_trigger_and_half_open_window():
    longs = pd.DataFrame({
        "entry_index": [5, 10, 54, 55, 70], "signal_index": [1, 2, 3, 4, 5],
    })
    shorts = pd.DataFrame({
        "entry_index": [10, 55], "signal_index": [1, 2],
        "gate_margin_bps": [2.0, 3.0], "abs_d_tau_bps": [51.0, 52.0],
    })
    result = veto._short_state(longs, shorts)
    assert result.short_signal_active.tolist() == [0, 1, 1, 1, 1]
    assert np.isnan(result.short_signal_age_min.iloc[0])
    assert result.short_signal_age_min.iloc[1:].tolist() == [0.0, 44.0, 0.0, 15.0]
    assert result.short_signal_count_60m.tolist() == [0, 1, 1, 2, 1]
    assert result.short_gate_margin.iloc[1:].tolist() == [2.0, 2.0, 3.0, 3.0]


def test_periodic_mask_exact_count_and_admission_leaves_rejected_slot_empty():
    assert veto._periodic_mask(10, 7).sum() == 7
    frame = pd.DataFrame({
        "entry_index": [0, 10, 20, 55], "signal_index": [0, 1, 2, 3],
        "scheduled_exit_index": [45, 55, 65, 100],
    })
    accepted = veto._admit(frame, np.array([False, True, True, True]))
    assert accepted.tolist() == [False, True, False, True]
