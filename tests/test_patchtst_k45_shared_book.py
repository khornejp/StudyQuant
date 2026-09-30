import numpy as np
import pandas as pd

from out import run_patchtst_k45_shared_book as shared


def candidates(rows):
    frame = pd.DataFrame(rows, columns=["candidate_id", "arm", "entry_index"])
    frame["signal_index"] = frame.entry_index - 1
    frame["exit_index"] = frame.entry_index + 45
    return frame


def test_drop_both_is_symmetric_and_does_not_consume_slot():
    frame = candidates([
        (0, shared.LONG, 10), (1, shared.SHORT, 10),
        (2, shared.LONG, 11), (3, shared.SHORT, 20), (4, shared.LONG, 56),
    ])
    mask, reason, stats = shared.admission(frame)
    assert mask.tolist() == [False, False, True, False, True]
    assert reason[:2].tolist() == ["same_index_conflict", "same_index_conflict"]
    assert stats == {"conflict_index_count": 1, "conflict_candidate_count": 2,
                     "free_slot_conflict_count": 1, "accepted_conflict_count": 0}


def test_tie_shadows_are_frozen_directional_priorities():
    frame = candidates([(0, shared.LONG, 10), (1, shared.SHORT, 10)])
    long, _, _ = shared.admission(frame, "LONG_FIRST")
    short, _, _ = shared.admission(frame, "SHORT_FIRST")
    assert long.tolist() == [True, False]
    assert short.tolist() == [False, True]


def test_three_term_decomposition_reconstructs():
    pieces = shared.matched._decomposition(2.0, 5.0, 1.0, -3.0, 3, 2, 1)
    total = (pieces["matched_contribution_bps"] + pieces["added_contribution_bps"] +
             pieces["dropped_contribution_bps"])
    assert np.isclose(total, pieces["full_difference_net_lin_bps"], atol=1e-12)
    assert abs(pieces["reconstruction_residual_bps"]) <= 1e-12
