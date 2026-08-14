from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence


@dataclass(frozen=True)
class KlineSnapshot:
    symbol: str = "BTCUSDT"
    interval: str = "1m"
    rows: int = 0
    first_open_time: str = ""
    last_open_time: str = ""
    source: str = "local"
    complete: bool = True
    available: bool = True
    source_hash: str = ""


@dataclass(frozen=True)
class MarkPriceSnapshot:
    symbol: str = "BTCUSDT"
    interval: str = "1m"
    mark_price: float = 0.0
    rows: int = 0
    source: str = "local"
    available: bool = True
    source_hash: str = ""


@dataclass(frozen=True)
class PremiumIndexSnapshot:
    symbol: str = "BTCUSDT"
    interval: str = "1m"
    premium_index: float = 0.0
    rows: int = 0
    source: str = "local"
    available: bool = True
    source_hash: str = ""


@dataclass(frozen=True)
class FundingSnapshot:
    symbol: str = "BTCUSDT"
    funding_rate: float = 0.0
    next_funding_rate: float = 0.0
    next_funding_time: str = ""
    source: str = "local"
    available: bool = True
    source_hash: str = ""


@dataclass(frozen=True)
class ExchangeInfoSnapshot:
    symbol: str = "BTCUSDT"
    min_qty: float = 0.001
    qty_step: float = 0.001
    price_tick: float = 0.1
    source: str = "local"
    available: bool = True
    source_hash: str = ""


@dataclass(frozen=True)
class LeverageBracketSnapshot:
    symbol: str = "BTCUSDT"
    initial_leverage: int = 1
    max_notional_value: float = 0.0
    current_notional: float = 0.0
    source: str = "local"
    available: bool = True
    source_hash: str = ""


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str = "BTCUSDT"
    last_update_id: int = 0
    best_bid: float = 0.0
    best_ask: float = 0.0
    bid_qty: float = 0.0
    ask_qty: float = 0.0
    source: str = "local"
    available: bool = True
    source_hash: str = ""


@dataclass(frozen=True)
class ADLSnapshot:
    symbol: str = "BTCUSDT"
    quantile: int = 0
    measured_at: str = ""
    source: str = "local"
    available: bool = True
    source_hash: str = ""


@dataclass(frozen=True)
class LiquidationSnapshot:
    symbol: str = "BTCUSDT"
    event_count: int = 0
    last_event_time: str = ""
    source: str = "local"
    available: bool = True
    source_hash: str = ""


@dataclass(frozen=True)
class MarketSourceBundle:
    klines_1m: KlineSnapshot | None = None
    mark_price_1m: MarkPriceSnapshot | None = None
    premium_index_1m: PremiumIndexSnapshot | None = None
    funding_rate: FundingSnapshot | None = None
    exchange_info: ExchangeInfoSnapshot | None = None
    leverage_bracket: LeverageBracketSnapshot | None = None
    depth_snapshot: OrderBookSnapshot | None = None
    agg_trades: object | None = None
    liquidation_feed: LiquidationSnapshot | None = None
    adl_quantile: ADLSnapshot | None = None
    source_hashes: Mapping[str, str] | None = None

    def snapshot_for(self, source_name: str) -> object | None:
        if source_name not in SOURCE_DEFINITIONS:
            raise KeyError(f"unknown source: {source_name}")
        # Some sources (e.g. "metrics") are delivered via the external_sources
        # channel rather than as a bundle attribute; getattr default None keeps
        # snapshot_for total over all SOURCE_DEFINITIONS.
        return getattr(self, source_name, None)

    def hashes_by_source(self) -> dict[str, str]:
        hashes: dict[str, str] = dict(self.source_hashes or {})
        for source_name in SOURCE_DEFINITIONS:
            snapshot = self.snapshot_for(source_name)
            if _snapshot_available(snapshot):
                hashes.setdefault(source_name, snapshot_hash(snapshot))
        return hashes

    def available_sources(self) -> tuple[str, ...]:
        return tuple(source_name for source_name in SOURCE_DEFINITIONS if _snapshot_available(self.snapshot_for(source_name)))


@dataclass(frozen=True)
class SourceDefinition:
    source_name: str
    snapshot_type: str
    description: str
    columns: tuple[str, ...]
    feature_names: tuple[str, ...]
    historical_backfill: bool
    local_archive_supported: bool
    live_capture_required: bool
    critical_live: bool
    retention_days: int
    live_action: str
    cache_forward_plan: str


KLINE_FEATURES: tuple[str, ...] = (
    "return_1",
    "return_3",
    "return_5",
    "return_10",
    "close_sma_5_ratio",
    "close_sma_10_ratio",
    "close_sma_20_ratio",
    "close_sma_60_ratio",
    "rv_15",
    "rv_60",
    "rv_120",
    "atr_pct",
    "volume_sma_5_ratio",
    "volume_sma_20_ratio",
    "taker_ratio",
    "trade_count_ratio",
    "high_low_range",
    "body_pct",
    "upper_shadow",
    "lower_shadow",
    "gap_ratio_20",
    "gap_ratio_60",
    "gap_ratio_120",
    "max_gap_run_120",
    "close_zscore_20",
    "close_zscore_60",
    "volume_zscore_5",
    "volume_zscore_20",
    "return_5_vol_adj",
    "return_10_vol_adj",
    "close_zscore_20_vol_adj",
    "volume_zscore_20_vol_adj",
    "candle_range_vol_adj",
    "body_pct_vol_adj",
)

DEPTH_FEATURES: tuple[str, ...] = (
    "spread",
    "spread_bps",
    "bid_ask_imbalance",
    "best_bid_qty_ratio",
    "best_ask_qty_ratio",
    "microprice_deviation",
    "order_book_pressure",
    "depth_top_qty",
    "depth_mid_price",
    "depth_spread_regime",
)
AGG_TRADE_FEATURES: tuple[str, ...] = (
    "agg_trade_count_1m",
    "agg_trade_buy_ratio",
    "agg_trade_sell_ratio",
    "agg_trade_avg_size",
    "agg_trade_notional_zscore",
    "agg_trade_intensity_5m",
)
FUNDING_FEATURES: tuple[str, ...] = (
    "funding_rate",
    "next_funding_rate",
    "minutes_to_next_funding",
    "funding_blackout_active",
    "funding_rate_zscore_8h",
    "funding_rate_change_8h",
)
MARK_PRICE_FEATURES: tuple[str, ...] = ("mark_price_basis", "mark_price_return_1m", "mark_price_basis_zscore")
PREMIUM_FEATURES: tuple[str, ...] = ("premium_index", "premium_index_zscore", "premium_index_change")
LEVERAGE_FEATURES: tuple[str, ...] = ("leverage_bracket_utilization", "leverage_max_notional_ratio", "initial_leverage_flag")
EXCHANGE_INFO_FEATURES: tuple[str, ...] = ("min_qty_distance", "price_tick_distance", "notional_filter_flag")
LIQUIDATION_FEATURES: tuple[str, ...] = ("liquidation_event_count_1m", "liquidation_notional_1m", "liquidation_side_imbalance")
ADL_FEATURES: tuple[str, ...] = ("adl_indicator", "adl_quantile_change", "adl_high_risk_flag")
# Binance futures metrics archive (open interest, long/short ratios, taker
# buy/sell). Historical-backfillable from data.binance.vision; 5m cadence
# forward-filled to the 1m clock. Live parity requires the /futures/data/*
# REST endpoints (NOT yet wired) — models using these are research-only until
# that live source exists.
METRICS_FEATURES: tuple[str, ...] = (
    "oi_change_rate_5m",
    "oi_change_rate_30m",
    "oi_zscore_1d",
    "oi_value_zscore_1d",
    "toptrader_ls_account",
    "toptrader_ls_position",
    "global_ls_account",
    "taker_ls_ratio",
    "toptrader_ls_account_change_5m",
    "global_ls_account_change_5m",
    "taker_ls_ratio_change_5m",
)

# Soft regime probabilities (F18), produced by regime_classifier.py's purged
# K-fold OOF pipeline from F17 multi-timeframe features. Research-only until
# a live-serving path for the classifier exists (required_for_live=False).
REGIME_PROBABILITY_FEATURES: tuple[str, ...] = (
    "regime_prob_up",
    "regime_prob_range",
    "regime_prob_down",
)


SOURCE_DEFINITIONS: dict[str, SourceDefinition] = {
    "klines_1m": SourceDefinition(
        "klines_1m",
        "KlineSnapshot",
        "Canonical BTCUSDT USD-M futures 1m klines used for labels and active features.",
        (
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "number_of_trades",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
        ),
        KLINE_FEATURES,
        True,
        True,
        True,
        True,
        3650,
        "block_new_entries",
        "must be complete from archive or captured stream before approval",
    ),
    "mark_price_1m": SourceDefinition(
        "mark_price_1m",
        "MarkPriceSnapshot",
        "Mark price snapshots aligned to the 1m feature clock.",
        ("open_time", "mark_price"),
        MARK_PRICE_FEATURES,
        False,
        False,
        True,
        False,
        365,
        "no_trade_current_bar",
        "cache forward every closed minute before enabling mark-price features",
    ),
    "premium_index_1m": SourceDefinition(
        "premium_index_1m",
        "PremiumIndexSnapshot",
        "Premium index state aligned to the 1m feature clock.",
        ("open_time", "premium_index"),
        PREMIUM_FEATURES,
        False,
        False,
        True,
        False,
        365,
        "no_trade_current_bar",
        "cache forward every closed minute before enabling premium features",
    ),
    "funding_rate": SourceDefinition(
        "funding_rate",
        "FundingSnapshot",
        "Current and next funding rate state for funding blackout features.",
        ("funding_time", "funding_rate", "next_funding_rate"),
        FUNDING_FEATURES,
        True,
        False,
        True,
        False,
        3650,
        "block_new_entries",
        "persist every observed funding-rate update and backfill before feature promotion",
    ),
    "exchange_info": SourceDefinition(
        "exchange_info",
        "ExchangeInfoSnapshot",
        "Symbol filters and precision limits needed by live order safeguards.",
        ("symbol", "min_qty", "qty_step", "price_tick"),
        EXCHANGE_INFO_FEATURES,
        False,
        False,
        True,
        False,
        3650,
        "block_new_entries",
        "snapshot daily and on filter-change detection",
    ),
    "leverage_bracket": SourceDefinition(
        "leverage_bracket",
        "LeverageBracketSnapshot",
        "Leverage bracket and notional utilization state.",
        ("symbol", "initial_leverage", "max_notional_value", "current_notional"),
        LEVERAGE_FEATURES,
        False,
        False,
        True,
        False,
        3650,
        "reduce_size",
        "snapshot daily and cache forward bracket transitions",
    ),
    "depth_snapshot": SourceDefinition(
        "depth_snapshot",
        "OrderBookSnapshot",
        "Top-of-book depth snapshot for spread and imbalance features.",
        ("open_time", "best_bid", "best_ask", "bid_qty", "ask_qty"),
        DEPTH_FEATURES,
        False,
        False,
        True,
        False,
        30,
        "no_trade_current_bar",
        "cache top-of-book snapshots per closed minute before enabling F11 features",
    ),
    "agg_trades": SourceDefinition(
        "agg_trades",
        "AggregateTradeSnapshot",
        "Aggregate trade stream summarized to the 1m feature clock.",
        ("open_time", "trade_count", "buy_volume", "sell_volume", "notional"),
        AGG_TRADE_FEATURES,
        False,
        False,
        True,
        False,
        30,
        "no_trade_current_bar",
        "cache live aggregate trades and only promote once forward history covers the training window",
    ),
    "liquidation_feed": SourceDefinition(
        "liquidation_feed",
        "LiquidationSnapshot",
        "Forced liquidation event feed summarized to the 1m feature clock.",
        ("open_time", "event_count", "liquidation_notional", "side_imbalance"),
        LIQUIDATION_FEATURES,
        False,
        False,
        True,
        False,
        30,
        "block_new_entries",
        "cache liquidation events and keep features disabled until train/live coverage matches",
    ),
    "adl_quantile": SourceDefinition(
        "adl_quantile",
        "ADLSnapshot",
        "ADL quantile snapshot for exchange-safety features.",
        ("open_time", "adl_quantile"),
        ADL_FEATURES,
        False,
        False,
        True,
        False,
        365,
        "reduce_size",
        "cache quantile snapshots and require deterministic fallback when unavailable",
    ),
    "metrics": SourceDefinition(
        "metrics",
        "MetricsSnapshot",
        "Binance futures metrics: open interest, long/short ratios, taker buy/sell (5m, forward-filled to 1m).",
        (
            "create_time",
            "sum_open_interest",
            "sum_open_interest_value",
            "count_toptrader_long_short_ratio",
            "sum_toptrader_long_short_ratio",
            "count_long_short_ratio",
            "sum_taker_long_short_vol_ratio",
        ),
        METRICS_FEATURES,
        True,   # historical_backfill: data.binance.vision metrics archive
        True,   # local_archive_supported: daily CSV zips
        True,   # live_capture_required: needs /futures/data/* REST for live
        False,  # critical_live: not required to trade (features degrade gracefully)
        3650,
        "no_trade_current_bar",
        "download metrics archive (collect-metrics) for training; wire /futures/data/* REST before live use",
    ),
    "regime_classifier": SourceDefinition(
        "regime_classifier",
        "RegimeProbabilitySnapshot",
        "Soft up/range/down probabilities from a multiclass classifier trained on F17 multi-timeframe features via leakage-safe walk-forward OOF prediction.",
        ("regime_prob_up", "regime_prob_range", "regime_prob_down"),
        REGIME_PROBABILITY_FEATURES,
        True,   # historical_backfill: derived entirely from klines already held (OOF pipeline)
        False,  # local_archive_supported: not an archive, a computed pipeline output
        True,   # live_capture_required: needs a live-serving classifier, not built yet
        False,  # critical_live: features degrade gracefully (no probabilities -> 0)
        0,
        "no_trade_current_bar",
        "run the OOF regime-classifier pipeline (regime_classifier.py) for training; a live-serving classifier must be wired before live use",
    ),
}

FEATURE_SOURCE_HINTS: dict[str, tuple[str, ...]] = {}
for _definition in SOURCE_DEFINITIONS.values():
    for _feature_name in _definition.feature_names:
        FEATURE_SOURCE_HINTS[_feature_name] = (_definition.source_name,)

SOURCE_ALIASES: dict[str, tuple[str, ...]] = {
    "canonical_timeline": ("klines_1m",),
    "derived_klines_1m": ("klines_1m",),
    "book_ticker": ("depth_snapshot",),
    "premium_index": ("premium_index_1m",),
    "futures_exchange_state": ("exchange_info",),
}


def stable_json(payload: object) -> str:
    return json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def snapshot_hash(snapshot: object | None) -> str:
    if snapshot is None:
        return ""
    explicit = getattr(snapshot, "source_hash", "")
    if isinstance(explicit, str) and explicit:
        return explicit
    return hashlib.sha256(stable_json(snapshot).encode("utf-8")).hexdigest()


def bundle_from_candles(candles: Sequence[object], source: str = "local", include_mock_sources: bool = False) -> MarketSourceBundle:
    candle_rows = [_candle_row(candle) for candle in candles]
    kline_hash = hashlib.sha256(stable_json(candle_rows).encode("utf-8")).hexdigest() if candle_rows else ""
    first_open_time = str(candle_rows[0].get("open_time", "")) if candle_rows else ""
    last_open_time = str(candle_rows[-1].get("open_time", "")) if candle_rows else ""
    kline_snapshot = KlineSnapshot(
        rows=len(candle_rows),
        first_open_time=first_open_time,
        last_open_time=last_open_time,
        source=source,
        complete=bool(candle_rows),
        available=bool(candle_rows),
        source_hash=kline_hash,
    )
    if not include_mock_sources:
        return MarketSourceBundle(klines_1m=kline_snapshot, source_hashes={"klines_1m": kline_hash})

    last_close = float(candle_rows[-1].get("close", 0.0)) if candle_rows else 0.0
    last_volume = float(candle_rows[-1].get("volume", 0.0)) if candle_rows else 0.0
    deterministic_hashes = {"klines_1m": kline_hash}
    bundle = MarketSourceBundle(
        klines_1m=kline_snapshot,
        mark_price_1m=MarkPriceSnapshot(mark_price=last_close, rows=len(candle_rows), source=source),
        premium_index_1m=PremiumIndexSnapshot(premium_index=0.0, rows=len(candle_rows), source=source),
        funding_rate=FundingSnapshot(funding_rate=0.0, next_funding_rate=0.0, next_funding_time=last_open_time, source=source),
        exchange_info=ExchangeInfoSnapshot(source=source),
        leverage_bracket=LeverageBracketSnapshot(max_notional_value=1_000_000.0, current_notional=last_close * last_volume, source=source),
        depth_snapshot=OrderBookSnapshot(best_bid=max(0.0, last_close - 0.5), best_ask=last_close + 0.5, bid_qty=last_volume, ask_qty=last_volume, source=source),
        agg_trades={"available": True, "rows": len(candle_rows), "trade_count": sum(int(row.get("number_of_trades", 0)) for row in candle_rows), "source": source},
        liquidation_feed=LiquidationSnapshot(source=source),
        adl_quantile=ADLSnapshot(quantile=0, measured_at=last_open_time, source=source),
    )
    for source_name in SOURCE_DEFINITIONS:
        snapshot = bundle.snapshot_for(source_name)
        if _snapshot_available(snapshot):
            deterministic_hashes[source_name] = snapshot_hash(snapshot)
    return MarketSourceBundle(
        klines_1m=bundle.klines_1m,
        mark_price_1m=bundle.mark_price_1m,
        premium_index_1m=bundle.premium_index_1m,
        funding_rate=bundle.funding_rate,
        exchange_info=bundle.exchange_info,
        leverage_bracket=bundle.leverage_bracket,
        depth_snapshot=bundle.depth_snapshot,
        agg_trades=bundle.agg_trades,
        liquidation_feed=bundle.liquidation_feed,
        adl_quantile=bundle.adl_quantile,
        source_hashes=deterministic_hashes,
    )


def source_availability_grade(
    source_name: str,
    historical_backfill: bool | None = None,
    local_archive_complete: bool | None = None,
    diagnostic_only: bool = False,
    live_available: bool | None = None,
    source_bundle: MarketSourceBundle | None = None,
    external_sources: Mapping[str, object] | None = None,
) -> dict[str, object]:
    definition = _definition(source_name)
    snapshot = _source_value(source_name, source_bundle, external_sources)
    if historical_backfill is None:
        historical_backfill = definition.historical_backfill
    if local_archive_complete is None:
        local_archive_complete = definition.local_archive_supported
    if live_available is None:
        live_available = _snapshot_available(snapshot) if snapshot is not _MISSING else bool(historical_backfill or local_archive_complete)

    if diagnostic_only:
        grade = "D"
        parity_passed = False
    elif definition.critical_live and not live_available:
        grade = "D"
        parity_passed = False
    elif historical_backfill and local_archive_complete and live_available:
        grade = "A"
        parity_passed = True
    elif historical_backfill and live_available:
        grade = "B"
        parity_passed = True
    elif live_available or local_archive_complete:
        grade = "C"
        parity_passed = bool(live_available)
    else:
        grade = "C"
        parity_passed = False

    approval_eligible = parity_passed and not (definition.critical_live and not live_available) and grade != "D"
    return {
        "source_name": source_name,
        "grade": grade,
        "availability_grade": grade,
        "historical_backfill": bool(historical_backfill),
        "local_archive_complete": bool(local_archive_complete),
        "live_available": bool(live_available),
        "critical_live": definition.critical_live,
        "parity_passed": parity_passed,
        "train_live_feature_parity_passed": parity_passed,
        "approval_eligible": approval_eligible,
        "live_action": definition.live_action,
    }


def required_sources_for_features(
    feature_names: Sequence[str] | None = None,
    feature_registry: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, tuple[str, ...]]:
    required: dict[str, tuple[str, ...]] = {}
    if feature_registry is not None:
        for row in feature_registry:
            raw_name = row.get("feature_name")
            if not isinstance(raw_name, str):
                continue
            if feature_names is not None and raw_name not in set(feature_names):
                continue
            raw_source = FEATURE_SOURCE_HINTS.get(raw_name, row.get("source", ("klines_1m",)))
            required[raw_name] = _source_tuple(raw_source)
    else:
        names = tuple(feature_names) if feature_names is not None else tuple(FEATURE_SOURCE_HINTS)
        for feature_name in names:
            required[feature_name] = FEATURE_SOURCE_HINTS.get(feature_name, ("klines_1m",))
    return required


def train_live_feature_parity_report(
    feature_names: Sequence[str] | None = None,
    source_bundle: MarketSourceBundle | None = None,
    external_sources: Mapping[str, object] | None = None,
    feature_registry: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    feature_sources = required_sources_for_features(feature_names, feature_registry)
    required_sources = sorted({source_name for source_names in feature_sources.values() for source_name in source_names})
    source_rows: list[dict[str, object]] = []
    unavailable_sources: list[str] = []
    grade_c_sources: list[str] = []
    source_hashes: dict[str, str] = {}
    source_grades: dict[str, dict[str, object]] = {}

    for source_name, definition in SOURCE_DEFINITIONS.items():
        snapshot = _source_value(source_name, source_bundle, external_sources)
        available = _snapshot_available(snapshot)
        grade = source_availability_grade(
            source_name,
            historical_backfill=available and definition.historical_backfill,
            local_archive_complete=available and definition.local_archive_supported,
            live_available=available,
            source_bundle=source_bundle,
            external_sources=external_sources,
        )
        source_grades[source_name] = grade
        if not available:
            unavailable_sources.append(source_name)
        if grade["availability_grade"] == "C":
            grade_c_sources.append(source_name)
        source_hash = snapshot_hash(snapshot) if available else ""
        if source_hash:
            source_hashes[source_name] = source_hash
        source_rows.append(
            {
                "source_name": source_name,
                "availability_grade": grade["availability_grade"],
                "train_live_feature_parity_passed": grade["train_live_feature_parity_passed"],
                "approval_eligible": grade["approval_eligible"],
                "live_available": available,
                "critical_live": definition.critical_live,
                "live_action": definition.live_action,
                "source_hash": source_hash,
            }
        )

    feature_source_status: dict[str, str] = {}
    fallback_features: list[str] = []
    for feature_name, source_names in feature_sources.items():
        missing = [source_name for source_name in source_names if source_name in unavailable_sources]
        if missing:
            feature_source_status[feature_name] = "fallback_unavailable_source"
            fallback_features.append(feature_name)
        else:
            feature_source_status[feature_name] = "available"

    missing_required_sources = [source_name for source_name in required_sources if source_name in unavailable_sources]
    missing_critical_sources = [source_name for source_name in missing_required_sources if SOURCE_DEFINITIONS[source_name].critical_live]
    feature_space_parity_passed = not fallback_features
    train_live_feature_parity_passed = feature_space_parity_passed and not missing_critical_sources
    approval_block_reasons = [f"missing_required_source:{source_name}" for source_name in missing_required_sources]
    approval_block_reasons.extend(f"missing_critical_live_source:{source_name}" for source_name in missing_critical_sources if f"missing_required_source:{source_name}" not in approval_block_reasons)
    return {
        "required_sources": required_sources,
        "feature_required_sources": feature_sources,
        "source_rows": source_rows,
        "source_grades": source_grades,
        "source_hashes": source_hashes,
        "feature_source_status": feature_source_status,
        "feature_space_parity_passed": feature_space_parity_passed,
        "train_live_feature_parity_passed": train_live_feature_parity_passed,
        "unavailable_sources": tuple(unavailable_sources),
        "grade_c_sources": tuple(grade_c_sources),
        "fallback_features": tuple(fallback_features),
        "approval_block_reasons": tuple(approval_block_reasons),
    }


def source_retention_contract_rows(
    source_bundle: MarketSourceBundle | None = None,
    external_sources: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    report = train_live_feature_parity_report((), source_bundle=source_bundle, external_sources=external_sources)
    grades = report["source_grades"]
    rows: list[dict[str, object]] = []
    for source_name, definition in SOURCE_DEFINITIONS.items():
        grade = grades[source_name]
        rows.append(
            {
                "source_name": source_name,
                "availability_grade": grade["availability_grade"],
                "backfill_available": definition.historical_backfill,
                "local_archive_supported": definition.local_archive_supported,
                "live_capture_required": definition.live_capture_required,
                "critical_live": definition.critical_live,
                "retention_days": definition.retention_days,
                "cache_forward_plan": definition.cache_forward_plan,
                "train_live_feature_parity_passed": grade["train_live_feature_parity_passed"],
                "approval_eligible": grade["approval_eligible"],
            }
        )
    return rows


def column_data_contract_rows(
    feature_names: Sequence[str] | None = None,
    feature_registry: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    feature_sources = required_sources_for_features(feature_names, feature_registry)
    required_sources = {source_name for source_names in feature_sources.values() for source_name in source_names}
    features_by_source: dict[str, list[str]] = {source_name: [] for source_name in SOURCE_DEFINITIONS}
    for feature_name, source_names in feature_sources.items():
        for source_name in source_names:
            features_by_source.setdefault(source_name, []).append(feature_name)
    rows: list[dict[str, object]] = []
    for source_name, definition in SOURCE_DEFINITIONS.items():
        for column_name in definition.columns:
            rows.append(
                {
                    "column_name": column_name,
                    "source": source_name,
                    "source_name": source_name,
                    "required_for_training": source_name in required_sources,
                    "required_for_live": definition.live_capture_required,
                    "live_action": definition.live_action,
                    "availability_grade_if_forward_cached": "C" if not definition.historical_backfill else "A",
                    "feature_dependencies": ";".join(sorted(features_by_source.get(source_name, []))),
                }
            )
    return rows


def _definition(source_name: str) -> SourceDefinition:
    try:
        return SOURCE_DEFINITIONS[source_name]
    except KeyError as error:
        raise KeyError(f"unknown source: {source_name}") from error


def _source_tuple(raw_source: object) -> tuple[str, ...]:
    if isinstance(raw_source, str):
        values = SOURCE_ALIASES.get(raw_source, (raw_source,))
    elif isinstance(raw_source, Sequence) and not isinstance(raw_source, (bytes, bytearray)):
        values = tuple(alias for value in raw_source for alias in SOURCE_ALIASES.get(str(value), (str(value),)))
    else:
        values = ("klines_1m",)
    for value in values:
        _definition(value)
    return values


class _Missing:
    pass


_MISSING = _Missing()


def _source_value(source_name: str, source_bundle: MarketSourceBundle | None, external_sources: Mapping[str, object] | None) -> object:
    if external_sources is not None and source_name in external_sources:
        return external_sources[source_name]
    if source_bundle is not None:
        return source_bundle.snapshot_for(source_name)
    return _MISSING


def source_availability_snapshot(external_sources: Mapping[object, object] | None) -> dict[str, object] | None:
    """Reduce direct or per-minute external inputs to source-presence evidence.

    Archive merges are keyed by candle time. Inspecting only their first minute
    is invalid: a finalized 1m source correctly has no value at its first open
    time, yet is available for the rest of the history. This helper is only
    for availability reporting; feature builders retain the full timeline.
    """
    if external_sources is None:
        return None
    snapshots: dict[str, object] = {
        name: external_sources[name]
        for name in SOURCE_DEFINITIONS
        if name in external_sources
    }
    for value in external_sources.values():
        if not isinstance(value, Mapping):
            continue
        for name in SOURCE_DEFINITIONS:
            if name not in snapshots and name in value:
                snapshots[name] = value[name]
    return snapshots


def _snapshot_available(snapshot: object | None) -> bool:
    if snapshot is None or snapshot is _MISSING:
        return False
    if isinstance(snapshot, bool):
        return snapshot
    if isinstance(snapshot, Mapping):
        if "available" in snapshot:
            return bool(snapshot["available"])
        return bool(snapshot)
    available = getattr(snapshot, "available", None)
    if available is not None:
        return bool(available)
    return True


def _candle_row(candle: object) -> dict[str, object]:
    names = (
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "number_of_trades",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
        "gap_flag",
        "repaired",
    )
    return {name: _jsonable(getattr(candle, name, "")) for name in names}


def _jsonable(value: object) -> object:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, (str, bytes, bytearray)):
        return str(value.isoformat())
    return value
