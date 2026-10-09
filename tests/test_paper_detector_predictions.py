"""R2-54 Task 2: prediction availability split (logical_available_at vs written_at) and immutability."""
import sqlite3

import numpy as np, pandas as pd, pytest

from btcusdt_quant.paper import detector
from btcusdt_quant.sim import regime

T0 = pd.Timestamp("2026-10-07T07:00", tz="UTC")


def _legacy_table(connection, rows):
    """detector_predictions exactly as the pre-Task-2 code created and filled it."""
    names = [f"prediction_{t}" for t in detector.target_names()]
    connection.execute(f"CREATE TABLE {detector.TABLE} (timestamp TEXT PRIMARY KEY, retrain_time TEXT, "
                       f"{', '.join(n + ' REAL' for n in names)}, created_at TEXT, available_at TEXT, model_id TEXT, "
                       "source TEXT)")
    for stamp, created in rows:
        connection.execute(f"INSERT INTO {detector.TABLE} (timestamp, retrain_time, {', '.join(names)}, created_at, "
                           f"available_at, model_id, source) VALUES (?,?,{','.join('?' * len(names))},?,?,?,?)",
                           (stamp, "2026-10-01T00:00:00+00:00", *[1.0] * len(names), created, created,
                            "w730_raw_20261001", "live"))


def test_migration_is_additive_and_fills_split_columns():
    c = sqlite3.connect(":memory:")
    _legacy_table(c, [(T0.isoformat(), "2026-10-07T07:00:16+00:00")])
    detector.ensure_table(c)
    row = c.execute(f"SELECT timestamp, available_at, logical_available_at, written_at FROM {detector.TABLE}").fetchone()
    # legacy available_at (= commit time, the live rule) is kept; written_at = the commit time; logical = prediction_ts
    assert row == (T0.isoformat(), "2026-10-07T07:00:16+00:00", T0.isoformat(), "2026-10-07T07:00:16+00:00")
    detector.ensure_table(c)       # idempotent
    assert c.execute(f"SELECT COUNT(*) FROM {detector.TABLE}").fetchone()[0] == 1


def test_old_writer_rows_are_filled_after_cutover():
    """A pre-restart process keeps inserting with the old column list; the new code fills the split columns."""
    c = sqlite3.connect(":memory:")
    detector.ensure_table(c)
    names = [f"prediction_{t}" for t in detector.target_names()]
    c.execute(f"INSERT INTO {detector.TABLE} (timestamp, retrain_time, {', '.join(names)}, created_at, available_at, "
              f"model_id, source) VALUES (?,?,{','.join('?' * len(names))},?,?,?,?)",
              (T0.isoformat(), "2026-10-01T00:00:00+00:00", *[1.0] * len(names), "2026-10-07T07:00:20+00:00",
               "2026-10-07T07:00:20+00:00", "w730_raw_20261001", "live"))
    frame = detector.read_predictions(c)
    assert frame.logical_available_at.iloc[0] == T0
    assert frame.written_at.iloc[0] == pd.Timestamp("2026-10-07T07:00:20", tz="UTC")


def test_write_predictions_splits_logical_and_written():
    c = sqlite3.connect(":memory:")
    origins = pd.DatetimeIndex([T0, T0 + pd.Timedelta(minutes=15)])
    values = np.ones((2, len(detector.target_names())))
    before = pd.Timestamp.now(tz="UTC")
    assert detector.write_predictions(c, origins, pd.Timestamp("2026-10-01", tz="UTC"), values) == 2
    frame = detector.read_predictions(c)
    assert list(frame.logical_available_at) == list(origins)            # causal availability = data cutoff T
    assert (frame.written_at >= before).all() and (frame.written_at == frame.available_at).all()
    assert (frame.model_id == "w730_raw_20261001").all()


def test_grid_rows_are_immutable_minute_rows_prunable():
    c = sqlite3.connect(":memory:")
    values = np.ones((1, len(detector.target_names())))
    detector.write_predictions(c, pd.DatetimeIndex([T0]), pd.Timestamp("2026-10-01", tz="UTC"), values)
    assert detector.write_predictions(c, pd.DatetimeIndex([T0]), pd.Timestamp("2026-10-08", tz="UTC"), 2 * values) == 0
    for sql in (f"UPDATE {detector.TABLE} SET prediction_exc_4h=2", f"UPDATE {detector.TABLE} SET model_id='x'",
                f"UPDATE {detector.TABLE} SET written_at='2030-01-01'",
                f"UPDATE {detector.TABLE} SET logical_available_at='2030-01-01'", f"DELETE FROM {detector.TABLE}"):
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(sql)
    assert detector.read_predictions(c).prediction_exc_4h.iloc[0] == 1.0
    detector.write_predictions(c, pd.DatetimeIndex([T0]), pd.Timestamp("2026-10-01", tz="UTC"), values,
                               table=detector.MINUTE_TABLE)
    c.execute(f"DELETE FROM {detector.MINUTE_TABLE}")                   # the 1 m table is pruned after 3 days


def test_research_replay_uses_logical_available_at_live_uses_both():
    t = pd.DatetimeIndex([T0, T0 + pd.Timedelta(minutes=15)])
    research = pd.DataFrame({"timestamp": t, "logical_available_at": t, "prediction_exc_4h": [100.0, 200.0]})
    d = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=15)])
    assert regime.e_bps(research, d, "4h")[0] == 200.0                  # written_at is never a research input
    live = research.assign(written_at=t + pd.Timedelta(minutes=5), available_at=t + pd.Timedelta(minutes=5))
    assert regime.e_bps(live, d, "4h")[0] == 100.0                      # live: written_at <= T as well
    late_logical = research.assign(logical_available_at=t + pd.Timedelta(minutes=1))
    assert regime.e_bps(late_logical, d, "4h")[0] == 100.0


R1 = pd.Timestamp("2026-10-01", tz="UTC")
R2 = pd.Timestamp("2026-10-08", tz="UTC")


def _versions(c):
    return c.execute(f"SELECT model_id, prediction_ts, version FROM {detector.VERSIONED_TABLE} "
                     "ORDER BY prediction_ts, model_id, version").fetchall()


def test_versioned_table_keeps_a_differing_model_row_and_records_it():
    c = sqlite3.connect(":memory:")
    values = np.ones((1, len(detector.target_names())))
    detector.write_predictions(c, pd.DatetimeIndex([T0]), R1, values)
    assert detector.write_predictions(c, pd.DatetimeIndex([T0]), R2, 2 * values) == 0      # legacy row kept
    assert detector.read_predictions(c).model_id.iloc[0] == "w730_raw_20261001"
    assert _versions(c) == [("w730_raw_20261001", T0.isoformat(), 1), ("w730_raw_20261008", T0.isoformat(), 1)]
    kinds = [r[0] for r in c.execute(f"SELECT kind FROM {detector.REVISION_TABLE}")]
    assert kinds == ["legacy_kept_other_row"]


def test_same_model_correction_is_a_new_version_identical_rewrite_is_noop():
    c = sqlite3.connect(":memory:")
    values = np.ones((1, len(detector.target_names())))
    detector.write_predictions(c, pd.DatetimeIndex([T0]), R1, values)
    detector.write_predictions(c, pd.DatetimeIndex([T0]), R1, values)                      # identical: nothing
    assert _versions(c) == [("w730_raw_20261001", T0.isoformat(), 1)]
    assert c.execute(f"SELECT COUNT(*) FROM {detector.REVISION_TABLE}").fetchone()[0] == 0
    detector.write_predictions(c, pd.DatetimeIndex([T0]), R1, 3 * values)
    assert _versions(c)[-1] == ("w730_raw_20261001", T0.isoformat(), 2)
    kinds = sorted(r[0] for r in c.execute(f"SELECT kind FROM {detector.REVISION_TABLE}"))
    assert kinds == ["correction", "legacy_kept_other_row"]
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(f"UPDATE {detector.VERSIONED_TABLE} SET prediction_exc_4h=0")
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(f"DELETE FROM {detector.VERSIONED_TABLE}")


def test_legacy_rows_of_old_writers_are_mirrored_into_versions():
    c = sqlite3.connect(":memory:")
    _legacy_table(c, [(T0.isoformat(), "2026-10-07T07:00:16+00:00")])
    detector.ensure_table(c)
    detector.ensure_table(c)
    row = c.execute(f"SELECT model_id, prediction_ts, version, logical_available_at, written_at, source "
                    f"FROM {detector.VERSIONED_TABLE}").fetchall()
    assert row == [("w730_raw_20261001", T0.isoformat(), 1, T0.isoformat(), "2026-10-07T07:00:16+00:00", "live")]
