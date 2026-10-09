"""R2-54 Task 3: archive-vs-REST parity rule (freeze amendment A1), offline fixtures only; no network."""
import importlib.util, sys
from decimal import Decimal
from pathlib import Path

import numpy as np, pandas as pd, pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r2_54_parity", ROOT / "out/run_r2_54_parity_snapshot.py")
par = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = par; SPEC.loader.exec_module(par)

START = pd.Timestamp("2026-10-01", tz="UTC")
END = START + pd.Timedelta(minutes=15)          # three 5-minute periods
GRID = pd.date_range(START, END, freq="5min", inclusive="left")


def _rows(source, values, shift=pd.Timedelta(0), times=GRID):
    rows = []
    for t, v in zip(times, values):
        stamp = t + (shift if source == "rest" else pd.Timedelta(0))
        rows.append({"symbol": "BTCUSDT", "create_time": t.isoformat(), "source_timestamp": stamp.isoformat(),
                     **v, "logical_available_at": (t + pd.Timedelta(minutes=5)).isoformat(),
                     "received_at": "2026-10-09T00:00:00+00:00", "source": source})
    return pd.DataFrame(rows)


def _ls(r):
    """REST fields as Binance publishes them: Q4 long/short, Q4 ratio of the Q4 parts."""
    long, short = par.q4(Decimal(repr(r)) / (1 + Decimal(repr(r)))), par.q4(1 / (1 + Decimal(repr(r))))
    return {"long_account": float(long), "short_account": float(short), "long_short_ratio": float(par.q4(long / short))}


def test_quantize_is_decimal_round_half_up_not_float_or_bankers():
    assert par.q4(Decimal("0.12345")) == Decimal("0.1235")         # bankers would give 0.1234
    assert par.q3(1.2345) == Decimal("1.235")                       # 1.2345 as float is 1.23449999...; repr-decimal
    assert par.q4(2.5e-05) == Decimal("0.0000")
    assert par.dec(None) is None and par.dec(float("nan")) is None


def test_ls_parity_passes_when_rest_fields_are_q4_derivations_of_the_archive_ratio():
    ratios = [1.21285859, 1.21376756, 0.98765432]
    archive = _rows("archive", [{"long_short_ratio": r, "long_account": None, "short_account": None} for r in ratios])
    rest = _rows("rest", [_ls(r) for r in ratios], shift=par.PERIOD)
    out = par.check_table("futures_global_ls_5m", archive, rest, START, END)
    assert out["passed"], out
    assert {f: v["mismatch"] for f, v in out["fields"].items()} == {
        "long_account": 0, "short_account": 0, "long_short_ratio": 0}
    assert out["fields"]["long_short_ratio"]["compared"] == 3
    assert out["fields"]["long_short_ratio"]["max_abs_raw_residual"] > 0      # raw residuals still reported


def test_ls_parity_fails_on_one_tick_difference_and_lists_it():
    ratios = [1.21285859, 1.21376756, 0.98765432]
    archive = _rows("archive", [{"long_short_ratio": r, "long_account": None, "short_account": None} for r in ratios])
    fields = [_ls(r) for r in ratios]
    fields[1] = {**fields[1], "long_account": fields[1]["long_account"] + 0.0001}
    rest = _rows("rest", fields, shift=par.PERIOD)
    out = par.check_table("futures_top_ls_5m", archive, rest, START, END)
    assert not out["passed"]
    assert out["fields"]["long_account"]["mismatch"] == 1 and out["fields"]["short_account"]["mismatch"] == 0
    assert out["fields"]["long_account"]["examples"][0]["create_time"] == GRID[1].isoformat()


def test_oi_requires_exact_equality_per_field():
    values = [{"sum_open_interest": 97750.06, "sum_open_interest_value": 8266596646.622662},
              {"sum_open_interest": 97727.7, "sum_open_interest_value": 8262466578.66},
              {"sum_open_interest": 97700.0, "sum_open_interest_value": 8.1e9}]
    archive, rest = _rows("archive", values), _rows("rest", values, shift=par.PERIOD)
    assert par.check_table("futures_oi_5m", archive, rest, START, END)["passed"]
    bumped = [dict(v) for v in values]
    bumped[2]["sum_open_interest_value"] = np.nextafter(8.1e9, 9e9)       # one ulp
    out = par.check_table("futures_oi_5m", archive, _rows("rest", bumped, shift=par.PERIOD), START, END)
    assert not out["passed"]
    assert out["fields"]["sum_open_interest"]["mismatch"] == 0
    assert out["fields"]["sum_open_interest_value"]["mismatch"] == 1


def test_taker_rest_internal_q4_and_archive_rest_q3():
    archive = _rows("archive", [{"buy_sell_ratio": r, "buy_volume": None, "sell_volume": None}
                                for r in (1.256407, 0.9873, 1.0004)])
    rest_values = [{"buy_sell_ratio": 1.2564, "buy_volume": 1256.4070, "sell_volume": 1000.0},
                   {"buy_sell_ratio": 0.9873, "buy_volume": 987.3, "sell_volume": 1000.0},
                   {"buy_sell_ratio": 1.0004, "buy_volume": 1000.4, "sell_volume": 1000.0}]
    out = par.check_table("futures_taker_lsr_5m", archive, _rows("rest", rest_values), START, END)
    assert out["passed"], out
    assert out["fields"]["archive_vs_rest_q3"]["max_abs_raw_residual"] == pytest.approx(7e-06, abs=1e-12)
    bad = [dict(v) for v in rest_values]
    bad[0]["buy_sell_ratio"] = 1.2563                                   # != Q4(buy/sell)=1.2564, same Q3
    out = par.check_table("futures_taker_lsr_5m", archive, _rows("rest", bad), START, END)
    assert out["fields"]["rest_internal_q4"]["mismatch"] == 1
    assert out["fields"]["archive_vs_rest_q3"]["mismatch"] == 0 and not out["passed"]


def test_missing_period_masks_and_timestamps_fail_closed():
    ratios = [1.1, 1.2, 1.3]
    archive = _rows("archive", [{"long_short_ratio": r, "long_account": None, "short_account": None} for r in ratios])
    rest = _rows("rest", [_ls(r) for r in ratios[:2]], shift=par.PERIOD, times=GRID[:2])
    out = par.check_table("futures_global_ls_5m", archive, rest, START, END)
    assert out["coverage"]["missing_rest"] == [GRID[2].isoformat()] and not out["passed"]
    # REST stamped at period start for an end-stamped endpoint = timestamp mismatch
    rest = _rows("rest", [_ls(r) for r in ratios])
    out = par.check_table("futures_global_ls_5m", archive, rest, START, END)
    assert out["timestamps"]["rest_source_timestamp_mismatch"] == 3 and not out["passed"]
    # a null archive value against a present REST value = mask mismatch
    archive.loc[0, "long_short_ratio"] = None
    out = par.check_table("futures_global_ls_5m", archive, _rows("rest", [_ls(r) for r in ratios], shift=par.PERIOD),
                          START, END)
    assert out["masks"]["mismatch"] == 1 and not out["passed"]


def test_rows_outside_window_are_ignored_and_window_is_end_exclusive():
    times = GRID.append(pd.DatetimeIndex([END]))
    ratios = [1.1, 1.2, 1.3, 9.9]
    archive = _rows("archive", [{"long_short_ratio": r, "long_account": None, "short_account": None} for r in ratios],
                    times=times)
    rest = _rows("rest", [_ls(r) for r in ratios[:3]], shift=par.PERIOD)
    out = par.check_table("futures_global_ls_5m", archive, rest, START, END)
    assert out["passed"] and out["coverage"]["expected"] == 3


def test_snapshot_files_are_read_only_and_manifest_records_required_fields(tmp_path):
    frame = pd.DataFrame({"open_time": GRID, "x": [1.0, 2.0, np.nan]})
    record = par.write_artifact(tmp_path / "a.parquet", frame, "open_time", "fixture")
    assert record["rows"] == 3 and record["min_time"] == str(GRID[0]) and record["max_time"] == str(GRID[-1])
    assert set(record) >= {"path", "sha256", "bytes", "rows", "schema", "min_time", "max_time", "source"}
    assert record["schema"]["x"] == "float64"
    with pytest.raises(PermissionError):
        (tmp_path / "a.parquet").write_bytes(b"x")
    with pytest.raises(RuntimeError):
        par.write_artifact(tmp_path / "a.parquet", frame, "open_time", "fixture")      # write-once


class _FakeClient:
    """Offline stand-in for PublicBinanceClient.get_raw: one finalized taker row per call."""
    def __init__(self):
        self.calls = []

    def get_raw(self, path, params, on_attempt=None):
        self.calls.append((path, dict(params)))
        if path.endswith("takerlongshortRatio"):
            body = [{"buySellRatio": "1.2564", "buyVol": "1256.4070", "sellVol": "1000.0000",
                     "timestamp": int(START.value // 10**6)}]
        elif path.endswith("openInterestHist"):
            body = [{"symbol": "BTCUSDT", "sumOpenInterest": "1.5", "sumOpenInterestValue": "2.5",
                     "timestamp": int((START + par.PERIOD).value // 10**6)}]
        else:
            body = [{"symbol": "BTCUSDT", "longShortRatio": "1.2129", "longAccount": "0.5481",
                     "shortAccount": "0.4519", "timestamp": int((START + par.PERIOD).value // 10**6)}]
        text = __import__("json").dumps(body)
        on_attempt(200, text, pd.Timestamp.now(tz="UTC"))
        return 200, text


def test_fetch_rest_writes_audit_and_rows_to_staging_only_without_api_key(tmp_path):
    import sqlite3
    client = _FakeClient()
    staging = tmp_path / "staging.sqlite"
    summary = par.fetch_rest(staging, START, END, client)
    assert set(summary) == set(par.ENDPOINT)
    assert all("apiKey" not in p and "signature" not in p for _, p in client.calls)
    with sqlite3.connect(staging) as c:
        assert c.execute("SELECT COUNT(*) FROM futures_raw_audit").fetchone()[0] == len(client.calls)
        row = c.execute("SELECT create_time, source_timestamp, source FROM futures_taker_lsr_5m").fetchone()
        assert row == (START.isoformat(), START.isoformat(), "rest")
        row = c.execute("SELECT create_time, source_timestamp FROM futures_global_ls_5m").fetchone()
        assert row == (START.isoformat(), (START + par.PERIOD).isoformat())
    again = par.fetch_rest(staging, START, END, client)                   # identical re-fetch: no new rows
    assert all(v["inserted"] == 0 and v["revised"] == 0 for v in again.values())


def test_live_connection_round_trips_through_detector_live_inputs():
    from btcusdt_quant.paper import detector
    now = pd.Timestamp("2026-10-01 01:00", tz="UTC")
    minutes = pd.date_range(now - pd.Timedelta(hours=2), now, freq="1min", inclusive="left")
    market = pd.DataFrame({"open_time": minutes, **{c: 1.0 for c in ("open", "high", "low", "close", "volume",
                           "quote_volume", "number_of_trades", "taker_buy_base_volume")}})
    metrics = pd.DataFrame({"create_time": pd.date_range(minutes[0], now, freq="5min"), "global_ls": 1.5})
    premium = pd.DataFrame({"open_time": minutes, "close_time": minutes + pd.Timedelta(milliseconds=59_999),
                            "premium": 0.001})
    funding = pd.DataFrame({"publish_time": [now - pd.Timedelta(minutes=60, milliseconds=-2)], "rate": [1e-4],
                            "interval_hours": [0.0], "interval_missing": [1]})
    with par.live_connection((market, metrics, premium, funding), now) as c:
        l_market, l_metrics, l_premium, l_funding = detector.live_inputs(c)
    assert l_market.open_time.equals(market.open_time)
    assert l_metrics.create_time.max() == now - par.PERIOD                # create_time + 5 m <= now only
    assert l_premium.close_time.equals(premium.close_time)
    assert l_funding.publish_time.tolist() == funding.publish_time.tolist()
    assert l_funding.interval_missing.tolist() == [1] and l_funding.interval_hours.tolist() == [0.0]


def test_snapshot_is_final_only_after_both_parity_checks_pass(tmp_path):
    assert par.snapshot_status(True, True, par.SNAPSHOT_DIR, False) == "FINAL"
    with pytest.raises(RuntimeError, match="only after parity passes"):
        par.snapshot_status(False, True, tmp_path / "x", False)
    with pytest.raises(RuntimeError, match="final snapshot path"):
        par.snapshot_status(True, False, par.SNAPSHOT_DIR, True)
    assert par.snapshot_status(False, True, tmp_path / "x", True) == "NOT_FINAL_PARITY_FAILED"


def test_archive_file_period_start_daily_and_monthly():
    assert par.file_period_start("BTCUSDT-metrics-2025-12-31.zip") == pd.Timestamp("2025-12-31", tz="UTC")
    assert par.file_period_start("BTCUSDT-fundingRate-2020-01.zip") == pd.Timestamp("2020-01-01", tz="UTC")
    assert par.file_period_start("BTCUSDT-premiumIndexKlines-1m-2026-01.zip") == pd.Timestamp("2026-01-01", tz="UTC")
