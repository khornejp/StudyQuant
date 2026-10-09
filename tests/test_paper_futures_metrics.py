"""R2-54 Task 1: four-table futures metrics, raw audit, archive backfill and funding intervals (offline)."""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import urllib.error
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from btcusdt_quant.metrics_source import BinanceMetricsDownloader
from btcusdt_quant.paper import book, futures_metrics as fm
from btcusdt_quant.paper.collector import Collector, PublicBinanceClient
from btcusdt_quant.paper.engine import PaperEngine
from btcusdt_quant.paper.store import PaperStore

T0 = pd.Timestamp("2026-09-30T02:20:00Z")
MS = lambda stamp: int(pd.Timestamp(stamp).timestamp() * 1000)

# Real public responses (2026-10-09 GET, startTime=2026-09-30T02:20Z) trimmed to two rows each.
REST = {
    "/futures/data/globalLongShortAccountRatio": [
        {"symbol": "BTCUSDT", "longAccount": "0.5793", "longShortRatio": "1.3770", "shortAccount": "0.4207",
         "timestamp": MS("2026-09-30T02:20Z")},
        {"symbol": "BTCUSDT", "longAccount": "0.5790", "longShortRatio": "1.3753", "shortAccount": "0.4210",
         "timestamp": MS("2026-09-30T02:25Z")}],
    "/futures/data/topLongShortAccountRatio": [
        {"symbol": "BTCUSDT", "longAccount": "0.5915", "longShortRatio": "1.4480", "shortAccount": "0.4085",
         "timestamp": MS("2026-09-30T02:20Z")},
        {"symbol": "BTCUSDT", "longAccount": "0.5913", "longShortRatio": "1.4468", "shortAccount": "0.4087",
         "timestamp": MS("2026-09-30T02:25Z")}],
    "/futures/data/openInterestHist": [
        {"symbol": "BTCUSDT", "sumOpenInterest": "92818.81500000", "sumOpenInterestValue": "7736169247.08978400",
         "CMCCirculatingSupply": "20090790.0", "timestamp": MS("2026-09-30T02:20Z")},
        {"symbol": "BTCUSDT", "sumOpenInterest": "92801.32100000", "sumOpenInterestValue": "7743133093.77281700",
         "CMCCirculatingSupply": "20090790.0", "timestamp": MS("2026-09-30T02:25Z")}],
    "/futures/data/takerlongshortRatio": [
        {"buySellRatio": "0.4615", "sellVol": "108.3870", "buyVol": "50.0170", "timestamp": MS("2026-09-30T02:15Z")},
        {"buySellRatio": "2.3119", "sellVol": "49.8240", "buyVol": "115.1890", "timestamp": MS("2026-09-30T02:20Z")}],
}
ARCHIVE_CSV = (
    "create_time,symbol,sum_open_interest,sum_open_interest_value,count_toptrader_long_short_ratio,"
    "sum_toptrader_long_short_ratio,count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
    "2026-09-30 02:15:00,BTCUSDT,92818.8150000000000000,7736169247.0897840000000000,1.44792775,1.92913300,"
    "1.37682773,0.46155900\n"
    "2026-09-30 02:20:00,BTCUSDT,92801.3210000000000000,7743133093.7728170000000000,1.44699416,1.93045800,"
    "1.37526140,2.31164800\n")


def _zip(csv_text: str, name: str = "x.csv") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, csv_text)
    return buffer.getvalue()


def test_rest_timestamp_rules_match_archive_create_time() -> None:
    received = pd.Timestamp("2026-09-30T02:26:10Z")
    by_table = {}
    for endpoint, payload in REST.items():
        table, rows = fm.normalize_rest(endpoint, payload, received)
        by_table[table] = rows
    # global/top/OI: REST timestamp = period end; taker: REST timestamp = period start
    assert [r["create_time"] for r in by_table["futures_oi_5m"]] == [
        "2026-09-30T02:15:00+00:00", "2026-09-30T02:20:00+00:00"]
    assert [r["create_time"] for r in by_table["futures_taker_lsr_5m"]] == [
        "2026-09-30T02:15:00+00:00", "2026-09-30T02:20:00+00:00"]
    oi = by_table["futures_oi_5m"][0]
    assert oi["source_timestamp"] == "2026-09-30T02:20:00+00:00"
    # live availability = max(period end, received_at)
    assert oi["logical_available_at"] == received.isoformat()
    assert by_table["futures_taker_lsr_5m"][1]["logical_available_at"] == received.isoformat()
    assert by_table["futures_taker_lsr_5m"][1]["buy_volume"] == 115.189
    # archive OI row with the same create_time carries the same value
    archive = fm.normalize_archive(
        __import__("btcusdt_quant.metrics_source", fromlist=["x"]).parse_metrics_csv_text(ARCHIVE_CSV), received)
    a_oi = archive["futures_oi_5m"][0]
    assert a_oi["create_time"] == oi["create_time"] and a_oi["sum_open_interest"] == oi["sum_open_interest"]
    assert a_oi["logical_available_at"] == "2026-09-30T02:20:00+00:00" and a_oi["source"] == "archive"
    assert archive["futures_global_ls_5m"][0]["long_account"] is None   # not in archive -> missing
    assert archive["futures_taker_lsr_5m"][1]["buy_sell_ratio"] == 2.311648


def test_rest_unfinalized_period_is_dropped() -> None:
    received = pd.Timestamp("2026-09-30T02:24:00Z")
    _, rows = fm.normalize_rest("/futures/data/takerlongshortRatio", REST["/futures/data/takerlongshortRatio"],
                                received)
    assert [r["create_time"] for r in rows] == ["2026-09-30T02:15:00+00:00"]    # 02:20 period ends 02:25


def test_schema_drift_raises() -> None:
    with pytest.raises(fm.SchemaDrift):
        fm.normalize_rest("/futures/data/openInterestHist", [{"timestamp": MS(T0), "oi": "1"}], T0)
    with pytest.raises(fm.SchemaDrift):
        fm.normalize_rest("/futures/data/openInterestHist", {"code": -1}, T0)


class _Client:
    """Offline client: REST fixtures by path, optional per-path failures."""

    def __init__(self, fail: dict | None = None, extra: dict | None = None):
        self.fail = fail or {}
        self.extra = extra or {}
        self.calls: list[tuple[str, dict]] = []

    def get(self, path, parameters):
        self.calls.append((path, dict(parameters)))
        if path in self.fail:
            raise self.fail[path]
        if path in self.extra:
            return self.extra[path]
        if path in REST:
            return [r for r in REST[path] if parameters["startTime"] <= r["timestamp"] <= parameters["endTime"]]
        return []


def test_collect_once_fills_four_tables_with_raw_audit(tmp_path) -> None:
    received = pd.Timestamp("2026-09-30T02:30:05Z")
    with PaperStore(tmp_path / "live.sqlite") as store:
        store.set_meta("last_processed_minute", "2026-09-30T02:29:00+00:00")
        collector = Collector(PaperEngine(store), tmp_path / "raw", _Client(), futures_lookback=pd.Timedelta(hours=1))
        result = collector.collect_once(received)
        assert result["futures_top_ls_5m"] == 2 and result["futures_taker_lsr_5m"] == 2
        for table in fm.TABLES:
            frame = store.frame(table)
            assert len(frame) == 2 and set(frame.source) == {"rest"}
        assert len(store.frame("ls_ratio")) == 2            # legacy table still filled from the same pages
        audit = store.frame("futures_raw_audit")
        assert set(fm.REST_SPECS) <= set(audit.endpoint)
        row = audit.loc[audit.endpoint.eq("/futures/data/openInterestHist")].iloc[0]
        assert row.status == 200 and json.loads(row.params)["period"] == "5m"
        assert row.sha256 == hashlib.sha256(row.payload.encode()).hexdigest()
        assert pd.Timestamp(row.request_utc) <= pd.Timestamp(row.response_utc)
        capability = json.loads(store.get_meta("futures_capability"))
        assert {capability[e]["status"] for e in fm.REST_SPECS} == {"OK"}
        # second poll: cursor resumes, no duplicates, no revisions
        collector.collect_once(received + pd.Timedelta(minutes=1))
        assert len(store.frame("futures_oi_5m")) == 2 and store.frame("futures_revisions").empty


def test_auth_and_schema_failures_fail_closed(tmp_path) -> None:
    forbidden = urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b'{"code":-2015}'))
    client = _Client(fail={"/futures/data/topLongShortAccountRatio": forbidden},
                     extra={"/futures/data/openInterestHist": [{"timestamp": MS(T0), "wrong": "1"}]})
    received = pd.Timestamp("2026-09-30T02:30:05Z")
    with PaperStore(tmp_path / "live.sqlite") as store:
        collector = Collector(PaperEngine(store), tmp_path / "raw", client, futures_lookback=pd.Timedelta(hours=1))
        collector.collect_once(received)
        assert store.frame("futures_top_ls_5m").empty and store.frame("futures_oi_5m").empty
        assert len(store.frame("futures_global_ls_5m")) == 2
        capability = json.loads(store.get_meta("futures_capability"))
        assert capability["/futures/data/topLongShortAccountRatio"]["status"] == "HTTP_403"
        assert capability["/futures/data/openInterestHist"]["status"] == "SCHEMA_DRIFT"
        audit = store.frame("futures_raw_audit")
        assert 403 in set(audit.status)
        drift = audit.loc[audit.endpoint.eq("/futures/data/openInterestHist")].iloc[0]
        assert json.loads(drift.payload) == [{"timestamp": MS(T0), "wrong": "1"}]    # raw kept before normalization
        # failed endpoints wait for the periodic probe instead of being retried every minute
        client.calls.clear()
        collector.collect_once(received + pd.Timedelta(minutes=1))
        assert not [c for c in client.calls if c[0] == "/futures/data/topLongShortAccountRatio"]
        collector.collect_once(received + fm.PROBE_INTERVAL + pd.Timedelta(minutes=1))
        assert [c for c in client.calls if c[0] == "/futures/data/topLongShortAccountRatio"]


def test_empty_finalized_coverage_is_flagged(tmp_path) -> None:
    received = pd.Timestamp("2026-09-30T03:30:05Z")      # an hour past the last fixture period
    with PaperStore(tmp_path / "live.sqlite") as store:
        Collector(PaperEngine(store), tmp_path / "raw", _Client(extra={"/futures/data/takerlongshortRatio": []}),
                  futures_lookback=pd.Timedelta(hours=2)).collect_once(received)
        capability = json.loads(store.get_meta("futures_capability"))
        assert capability["/futures/data/takerlongshortRatio"]["status"] == "EMPTY"


def test_public_client_sends_no_api_key() -> None:
    seen = []

    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def opener(request):
        seen.append(request)
        return Response(b"[]")

    status, text = PublicBinanceClient(opener=opener).get_raw("/futures/data/topLongShortAccountRatio",
                                                              {"symbol": "BTCUSDT"})
    assert (status, text) == (200, "[]")
    assert not any("apikey" in key.lower() for key in seen[0].headers)


def test_revision_never_silently_overwrites(tmp_path) -> None:
    received = pd.Timestamp("2026-09-30T02:30:05Z")
    _, rows = fm.normalize_rest("/futures/data/openInterestHist", REST["/futures/data/openInterestHist"], received)
    with PaperStore(tmp_path / "live.sqlite") as store:
        assert store.put_versioned("futures_oi_5m", rows[0]) == "inserted"
        later = dict(rows[0], received_at=(received + pd.Timedelta(minutes=1)).isoformat())
        assert store.put_versioned("futures_oi_5m", later) == "same"
        changed = dict(rows[0], sum_open_interest=1.0)
        assert store.put_versioned("futures_oi_5m", changed) == "revised"
        kept = store.frame("futures_oi_5m").iloc[0]
        assert kept.sum_open_interest == 92818.815 and kept.received_at == received.isoformat()
        revision = store.frame("futures_revisions").iloc[0]
        assert revision.dataset == "futures_oi_5m" and revision.old_sha256 != revision.new_sha256
        assert json.loads(revision.new_payload)["sum_open_interest"] == 1.0 and revision.detected_at


def test_archive_backfill_local_first_coverage_and_duplicates(tmp_path) -> None:
    local, download = tmp_path / "local", tmp_path / "download"
    local.mkdir()
    day1 = ARCHIVE_CSV + "2026-09-30 02:20:00,BTCUSDT,1,2,3,4,5,6\n"            # duplicate create_time
    (local / "BTCUSDT-metrics-2026-09-30.zip").write_bytes(_zip(day1))
    day2 = ARCHIVE_CSV.replace("2026-09-30", "2026-10-01")
    requested = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def urlopen(request, timeout):
        requested.append(request.full_url)
        if "2026-10-01" in request.full_url:
            return Response(_zip(day2))
        raise urllib.error.HTTPError(request.full_url, 404, "nf", {}, None)

    downloader = BinanceMetricsDownloader(urlopen=urlopen, sleep=lambda _: None, request_interval_seconds=0)
    with PaperStore(tmp_path / "live.sqlite") as store:
        coverage = fm.backfill_metrics(store, "2026-09-30", "2026-10-02", [local], download, downloader,
                                       received=pd.Timestamp("2026-10-09T00:00:00Z"))
        assert [u.rsplit("/", 1)[1] for u in requested] == ["BTCUSDT-metrics-2026-09-29.zip",   # previous day
                                                            "BTCUSDT-metrics-2026-10-01.zip",
                                                            "BTCUSDT-metrics-2026-10-02.zip"]
        assert coverage["requested_days"] == 3 and coverage["fetched_days"] == 2
        assert coverage["missing_days"] == ["2026-10-02"] and coverage["duplicates_dropped"] == 1
        file = coverage["files"]["BTCUSDT-metrics-2026-10-01.zip"]
        assert file["sha256"] == hashlib.sha256((download / "BTCUSDT-metrics-2026-10-01.zip").read_bytes()).hexdigest()
        oi = store.frame("futures_oi_5m").sort_values("create_time")
        assert len(oi) == 4 and set(oi.source) == {"archive"}
        assert oi.iloc[1].sum_open_interest == 1.0                                # last duplicate wins (dedup rule)
        assert json.loads(store.get_meta("futures_metrics_backfill"))["fetched_days"] == 2
        again = fm.backfill_metrics(store, "2026-09-30", "2026-10-01", [local, download], download, downloader,
                                    received=pd.Timestamp("2026-10-10T00:00:00Z"))
        assert again["tables"]["futures_oi_5m"] == {"inserted": 0, "same": 4, "revised": 0}


def test_funding_keeps_actual_time_and_stored_interval(tmp_path) -> None:
    with PaperStore(tmp_path / "live.sqlite") as store:
        engine = PaperEngine(store)
        engine.store_funding("2026-07-01T00:00:00.007Z", .0001, interval_hours=8)
        engine.store_funding("2026-07-01T00:02:00Z", .0002)             # no 8 h rounding/tolerance anymore
        assert store.frame("funding").time.tolist() == ["2026-07-01T00:00:00.007000+00:00",
                                                        "2026-07-01T00:02:00+00:00"]
        events = store.frame("funding_events").sort_values("funding_time")
        assert events.interval_hours.tolist()[0] == 8 and pd.isna(events.interval_hours.tolist()[1])
        assert events.interval_missing.tolist() == [0, 1]
        # a legacy row stored under the rounded key is not duplicated by the same raw event
        store.upsert("funding", {"time": "2026-07-02T00:00:00+00:00", "rate": .0003,
                                 "raw_calc_time": "2026-07-02T00:00:00.003000+00:00", "source": "rest",
                                 "received_at": "2026-07-02T00:00:01+00:00"})
        engine.store_funding("2026-07-02T00:00:00.003Z", .0003, source="rest",
                             received_at="2026-07-02T00:00:05Z")
        assert (store.frame("funding").raw_calc_time == "2026-07-02T00:00:00.003000+00:00").sum() == 1
        rest = store.frame("funding_events").set_index("funding_time").loc["2026-07-02T00:00:00.003000+00:00"]
        assert rest.logical_available_at == "2026-07-02T00:00:05+00:00"


def test_collector_funding_interval_from_funding_info(tmp_path) -> None:
    events = [{"symbol": "BTCUSDT", "fundingTime": MS("2026-10-08T16:00:00.002Z"), "fundingRate": "0.0001"},
              {"symbol": "BTCUSDT", "fundingTime": MS("2026-10-09T00:00:00Z"), "fundingRate": "0.0002"}]
    client = _Client(extra={"/fapi/v1/fundingRate": events, "/fapi/v1/fundingInfo": [
        {"symbol": "ETHUSDT", "fundingIntervalHours": 4}, {"symbol": "BTCUSDT", "fundingIntervalHours": 8}]})
    with PaperStore(tmp_path / "live.sqlite") as store:
        Collector(PaperEngine(store), tmp_path / "raw", client).collect_once(pd.Timestamp("2026-10-09T00:01:00Z"))
        frame = store.frame("funding_events").sort_values("funding_time")
        # only the current event gets the interval in force at receive time; the older one stays unknown
        assert frame.funding_time.tolist()[0] == "2026-10-08T16:00:00.002000+00:00"
        assert pd.isna(frame.interval_hours.iloc[0]) and frame.interval_hours.iloc[1] == 8
        assert "/fapi/v1/fundingInfo" in set(store.frame("futures_raw_audit").endpoint)
        # next poll resumes after the last raw event time (no re-fetch of the .002 event)
        client.calls.clear()
        Collector(PaperEngine(store), tmp_path / "raw", client).collect_once(pd.Timestamp("2026-10-09T00:02:00Z"))
        start = next(p for path, p in client.calls if path == "/fapi/v1/fundingRate")["startTime"]
        assert start == MS("2026-10-09T00:00:00.001Z")


def test_detector_live_inputs_reads_stored_interval_and_masks_missing(tmp_path) -> None:
    from btcusdt_quant.paper import detector

    with PaperStore(tmp_path / "live.sqlite") as store:
        engine = PaperEngine(store)
        engine.store_funding("2026-07-01T00:00:00.007Z", .0001, interval_hours=4)
        engine.store_funding("2026-07-01T08:00:00Z", .0002)
        funding = detector.live_inputs(store.connection)[3].sort_values("publish_time")
        assert funding.interval_hours.tolist() == [4.0, 0.0]          # 0 h -> expired -> funding_missing=1
        assert funding.interval_missing.tolist() == [0, 1]
        assert str(funding.publish_time.iloc[0]) == "2026-07-01 00:00:00.007000+00:00"


def test_minute_ledger_keeps_offset_funding_event() -> None:
    index = pd.date_range("2026-07-01T07:58Z", periods=4, freq="min")
    closes = pd.Series([100.0, 100.0, 100.0, 100.0], index=index)
    trades = pd.DataFrame([{"entry_time": index[0], "exit_time": index[-1], "side": -1,
                            "entry_price": 100.0, "exit_price": 100.0}])
    funding = pd.DataFrame({"time": [pd.Timestamp("2026-07-01T08:00:00.007Z")], "rate": [.0001]})
    minute = book.minute_components(trades, closes, funding, "PESS", 0.0)
    assert minute.funding_bps.sum() == pytest.approx(1.0)
    assert minute.funding_bps.loc[pd.Timestamp("2026-07-01T08:00Z")] == pytest.approx(1.0)
    assert book.reprice(trades, funding, "PESS", 0.0).funding_bps.iloc[0] == pytest.approx(1.0)


def test_schema_migration_is_additive(tmp_path) -> None:
    path = tmp_path / "live.sqlite"
    with PaperStore(path) as store:
        store.upsert("ls_ratio", {"timestamp": "2026-07-01T00:00:00+00:00", "global_ls_account": 1.2,
                                  "long_account": None, "short_account": None, "source": "archive",
                                  "received_at": "2026-07-01T00:00:00+00:00"})
    with sqlite3.connect(path) as connection:                      # simulate a DB made by the previous code
        for table in (*fm.TABLES, "futures_raw_audit", "futures_revisions", "funding_events"):
            connection.execute(f"DROP TABLE {table}")
    with PaperStore(path, init_schema=False) as store:              # R2-52A switch path: no schema write at open
        assert store.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='futures_oi_5m'").fetchone() is None
        with store.transaction() as connection:                     # switch transaction creates missing objects
            PaperStore.create_schema(connection)
        assert store.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='futures_oi_5m'").fetchone() is not None
        store.connection.execute("DROP TABLE futures_oi_5m")
    with PaperStore(path) as store:
        assert store.get_meta("schema_version") == "1"
        assert len(store.frame("ls_ratio")) == 1 and store.frame("futures_oi_5m").empty
        info = {row[1]: row[5] for row in store.connection.execute("PRAGMA table_info(futures_top_ls_5m)")}
        assert [name for name, pk in sorted(info.items(), key=lambda kv: kv[1]) if pk] == [
            "symbol", "create_time", "source"]
        assert list(info) == ["symbol", "create_time", "source_timestamp", "long_short_ratio", "long_account",
                              "short_account", "logical_available_at", "received_at", "source"]


def test_paper_backfill_no_longer_copies_features_parquet() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts" / "paper_backfill.py").read_text(encoding="utf-8")
    assert "features_2026q3" not in source and "backfill_metrics" in source


# ---------- fix round 1 ----------

def test_bad_timestamp_is_schema_drift_not_a_crash(tmp_path) -> None:
    bad = [dict(REST["/futures/data/openInterestHist"][0], timestamp="not-a-number")]
    with pytest.raises(fm.SchemaDrift):
        fm.normalize_rest("/futures/data/openInterestHist", bad, T0)
    with pytest.raises(fm.SchemaDrift):
        fm.normalize_rest("/futures/data/openInterestHist", [dict(bad[0], timestamp=None)], T0)
    received = pd.Timestamp("2026-09-30T02:30:05Z")
    with PaperStore(tmp_path / "live.sqlite") as store:
        collector = Collector(PaperEngine(store), tmp_path / "raw",
                              _Client(extra={"/futures/data/openInterestHist": bad}),
                              futures_lookback=pd.Timedelta(hours=1))
        collector.collect_once(received)                      # must not raise
        capability = json.loads(store.get_meta("futures_capability"))
        assert capability["/futures/data/openInterestHist"]["status"] == "SCHEMA_DRIFT"
        assert store.frame("futures_oi_5m").empty and len(store.frame("futures_top_ls_5m")) == 2


def test_stale_coverage_stores_nothing_but_keeps_audit(tmp_path) -> None:
    received = pd.Timestamp("2026-09-30T03:30:05Z")           # fixtures end at 02:25: rows exist but are stale
    with PaperStore(tmp_path / "live.sqlite") as store:
        Collector(PaperEngine(store), tmp_path / "raw", _Client(),
                  futures_lookback=pd.Timedelta(hours=2)).collect_once(received)
        capability = json.loads(store.get_meta("futures_capability"))
        for endpoint, (table, _, _) in fm.REST_SPECS.items():
            assert capability[endpoint]["status"] == "EMPTY"
            assert store.frame(table).empty
        assert store.frame("ls_ratio").empty
        assert store.get_meta("last_ls_timestamp") is None and store.get_meta("last_futures_oi_5m_timestamp") is None
        assert set(fm.REST_SPECS) <= set(store.frame("futures_raw_audit").endpoint)


def test_every_retried_http_attempt_is_audited(tmp_path) -> None:
    attempts = []

    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def opener(request):
        attempts.append(request.full_url)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many", {"Retry-After": "0"},
                                         io.BytesIO(b'{"code":-1003}'))
        return Response(b"[]")

    client = PublicBinanceClient(opener=opener, sleep=lambda _: None)
    with PaperStore(tmp_path / "live.sqlite") as store:
        collector = Collector(PaperEngine(store), tmp_path / "raw", client)
        status, payload = collector._fetch("/futures/data/takerlongshortRatio", {"symbol": "BTCUSDT"})
        assert (status, payload) == (200, [])
        audit = store.frame("futures_raw_audit").sort_values("id")
        assert audit.status.tolist() == [429, 200]
        assert json.loads(audit.payload.iloc[0]) == {"code": -1003}


def test_catalog_guard_warns_only_until_task1_activation(tmp_path, caplog) -> None:
    from btcusdt_quant.paper.store import refuse_missing_funding_backfill

    with PaperStore(tmp_path / "live.sqlite") as store:
        # live DB before the R2-54 restart: no activation marker -> old behaviour (warn, keep running)
        with caplog.at_level("WARNING"):
            refuse_missing_funding_backfill(store)
        assert "funding" in caplog.text
        store.set_meta("r2_54_task1_activation", json.dumps({"at": "2026-10-09T00:00:00+00:00"}))
        with pytest.raises(SystemExit, match="funding"):
            refuse_missing_funding_backfill(store)
        engine = PaperEngine(store)
        fm.backfill_funding(engine, "2026-07-01", "2026-07-02", [tmp_path / "none"])   # no zips -> no events
        with pytest.raises(SystemExit, match="funding"):
            refuse_missing_funding_backfill(store)
        zip_dir = tmp_path / "funding"
        zip_dir.mkdir()
        (zip_dir / "BTCUSDT-fundingRate-2026-07.zip").write_bytes(_zip(
            "calc_time,funding_interval_hours,last_funding_rate\n1782864000005,8,0.0001\n"))
        fm.backfill_funding(engine, "2026-07-01", "2026-07-02", [zip_dir])
        refuse_missing_funding_backfill(store)
        event = store.frame("funding_events").iloc[0]
        assert event.funding_time == "2026-07-01T00:00:00.005000+00:00" and event.interval_hours == 8
    source = (Path(__file__).resolve().parents[1] / "scripts" / "paper_catalog.py").read_text(encoding="utf-8")
    assert "refuse_missing_funding_backfill(store)" in source


def test_backfill_cli_writes_activation_marker_after_funding_meta(tmp_path) -> None:
    import subprocess
    import sys as _sys
    root = Path(__file__).resolve().parents[1]
    db = tmp_path / "live.sqlite"
    result = subprocess.run([_sys.executable, "scripts/paper_backfill.py", "--sqlite-path", str(db), "--futures-only",
                             "--metrics-start", "2026-07-02", "--metrics-end", "2026-07-02",
                             "--metrics-dir", "artifacts/hold_a_2026q3/metrics",
                             "--download-dir", str(tmp_path / "dl")], cwd=root, capture_output=True, text=True,
                            timeout=600)
    assert result.returncode == 0, result.stderr[-2000:]
    with PaperStore(db) as store:
        marker = json.loads(store.get_meta("r2_54_task1_activation"))
        assert json.loads(store.get_meta("funding_backfill"))["events"] > 0
        assert marker["funding_events"] > 0 and marker["metrics_range"] == ["2026-07-02", "2026-07-02"]
    assert not (tmp_path / "dl").exists()            # local zips only, nothing downloaded


def _migration_module():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "scripts" / "paper_funding_time_migrate.py"
    spec = importlib.util.spec_from_file_location("paper_funding_time_migrate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_funding_time_migration_backup_collisions_and_diff(tmp_path) -> None:
    migrate = _migration_module()
    db = tmp_path / "live.sqlite"
    with PaperStore(db) as store:
        for time, raw, rate in (("2026-07-01T08:00:00+00:00", "2026-07-01T08:00:00.007000+00:00", .0001),
                                ("2026-07-01T16:00:00+00:00", "2026-07-01T16:00:00+00:00", .0002)):
            store.upsert("funding", {"time": time, "rate": rate, "raw_calc_time": raw, "source": "archive",
                                     "received_at": raw})
        # short entered exactly at the rounded 08:00 event: PESS edge rule flips once the event moves inside
        store.insert("trades", {"book": "C1_AX", "boundary": "PESS", "candidate": "c", "side": -1,
                                "entry_time": "2026-07-01T08:00:00+00:00", "exit_time": "2026-07-01T09:00:00+00:00",
                                "entry_price": 100.0, "exit_price": 100.0, "gross_bps": 0.0, "cost_bps": 4.0,
                                "funding_bps": 0.0, "net_bps": -4.0, "hold_minutes": 60.0, "exit_reason": "t"})
    dry = migrate.run(db, tmp_path / "backup.sqlite", apply=False)
    assert dry["affected"] == 1 and dry["collisions"] == [] and not (tmp_path / "backup.sqlite").exists()
    assert dry["ledger_diff"]["changed"] == 1
    change = dry["ledger_diff"]["rows"][0]
    assert change["book"] == "C1_AX" and change["before_funding_bps"] == 0.0
    assert change["after_funding_bps"] == pytest.approx(1.0)
    assert migrate.MANIFEST_DIR == Path(__file__).resolve().parents[1] / "out/k45_rl_r2_48_20261007/r2_52a"
    result = migrate.run(db, tmp_path / "backup.sqlite", apply=True, record_dir=tmp_path / "record")
    assert result["applied"] and result["backup_integrity"] == "ok" and result["db_integrity"] == "ok"
    record = json.loads((tmp_path / "record" / migrate.RECORD_NAME).read_text(encoding="utf-8"))
    assert record["dry_run"]["rows"] == dry["rows"] and record["ledger_diff"] == dry["ledger_diff"]
    assert record["backup"] == str(tmp_path / "backup.sqlite") and record["backup_integrity"] == "ok"
    assert record["db_integrity"] == "ok" and record["updated"] == 1
    with PaperStore(db) as store:
        meta = json.loads(store.get_meta("r2_54_funding_time_migration"))
        assert meta["updated"] == 1 and meta["record"] == str(tmp_path / "record" / migrate.RECORD_NAME)
        assert meta["ledger_changed"] == 1
    with pytest.raises(SystemExit, match="record exists"):     # never overwrite a migration record
        migrate.run(db, tmp_path / "backup3.sqlite", apply=True, record_dir=tmp_path / "record")
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM funding WHERE time<>raw_calc_time").fetchone()[0] == 0
    with sqlite3.connect(tmp_path / "backup.sqlite") as connection:
        assert connection.execute("SELECT COUNT(*) FROM funding WHERE time<>raw_calc_time").fetchone()[0] == 1
    # a raw time already used as another row's key is a collision: refuse to apply
    with PaperStore(db) as store:
        store.upsert("funding", {"time": "2026-07-02T00:00:00+00:00", "rate": .1,
                                 "raw_calc_time": "2026-07-02T00:00:00.001000+00:00", "source": "rest",
                                 "received_at": "2026-07-02T00:00:00+00:00"})
        store.upsert("funding", {"time": "2026-07-02T00:00:00.001000+00:00", "rate": .1,
                                 "raw_calc_time": "2026-07-02T00:00:00.001000+00:00", "source": "rest",
                                 "received_at": "2026-07-02T00:00:00+00:00"})
    with pytest.raises(SystemExit, match="collision"):
        migrate.run(db, tmp_path / "backup2.sqlite", apply=True, record_dir=tmp_path / "record2")


def test_backfill_reads_previous_day_file_for_first_midnight_row(tmp_path) -> None:
    header = ARCHIVE_CSV.splitlines()[0]
    local = tmp_path / "local"
    local.mkdir()
    # a daily file covers 00:05 .. next day 00:00: the requested first 00:00 row is in the previous day's file
    (local / "BTCUSDT-metrics-2025-12-31.zip").write_bytes(_zip(
        f"{header}\n2025-12-31 23:55:00,BTCUSDT,1,1,1,1,1,1\n2026-01-01 00:00:00,BTCUSDT,2,2,2,2,2,2\n"))
    (local / "BTCUSDT-metrics-2026-01-01.zip").write_bytes(_zip(
        f"{header}\n2026-01-01 00:05:00,BTCUSDT,3,3,3,3,3,3\n2026-01-02 00:00:00,BTCUSDT,4,4,4,4,4,4\n"))

    def urlopen(request, timeout):
        raise AssertionError("no download expected")

    downloader = BinanceMetricsDownloader(urlopen=urlopen, sleep=lambda _: None, request_interval_seconds=0)
    with PaperStore(tmp_path / "live.sqlite") as store:
        coverage = fm.backfill_metrics(store, "2026-01-01", "2026-01-01", [local], tmp_path / "dl", downloader)
        stored = store.frame("futures_oi_5m").sort_values("create_time")
        assert stored.create_time.tolist() == ["2026-01-01T00:00:00+00:00", "2026-01-01T00:05:00+00:00"]
        assert coverage["requested_days"] == 1 and coverage["fetched_days"] == 1 and coverage["missing_days"] == []
        assert coverage["previous_day_file"]["name"] == "BTCUSDT-metrics-2025-12-31.zip"
        assert "BTCUSDT-metrics-2025-12-31.zip" not in coverage["files"]
