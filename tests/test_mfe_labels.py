from __future__ import annotations

"""Independent raw-OHLC checks for path-truncated MFE and MAE labels."""

import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from btcusdt_quant import data, dataset
from btcusdt_quant import models


_RAW_CSV = Path(__file__).resolve().parents[1] / "artifacts" / "archive_full" / "BTCUSDT-1m-2020-01-01.csv"
_HORIZON = 15
_TP_PCT = 0.0002
_SL_PCT = 0.0002


def _raw_candles(limit: int = 500) -> list[data.Candle]:
    """Parse archive OHLC directly; never call a production label helper."""
    candles: list[data.Candle] = []
    with _RAW_CSV.open(newline="", encoding="utf-8") as handle:
        for values in csv.reader(handle):
            candles.append(data.Candle(
                open_time=datetime.fromtimestamp(int(values[0]) / 1000, tz=timezone.utc),
                open=float(values[1]), high=float(values[2]), low=float(values[3]), close=float(values[4]),
                volume=float(values[5]), quote_volume=float(values[7]), number_of_trades=int(values[8]),
                taker_buy_base_volume=float(values[9]), taker_buy_quote_volume=float(values[10]),
            ))
            if len(candles) == limit:
                break
    return candles


def _oracle_mfe(
    candles: list[data.Candle], entry_index: int, *, short: bool,
    no_tp_dual_cap: bool = False, cap_one_bar_late: bool = False,
    wrong_cap_extreme: bool = False, short_uses_long_extreme: bool = False,
) -> float:
    """Independent MFE oracle plus explicit truncation mutants."""
    entry = candles[entry_index].close
    sl = entry * (1.0 + _SL_PCT if short else 1.0 - _SL_PCT)
    tp = entry * (1.0 - _TP_PCT if short else 1.0 + _TP_PCT)
    best, stop_next = 0.0, False
    for index in range(entry_index + 1, entry_index + _HORIZON + 1):
        candle = candles[index]
        if short:
            favorable = (entry - candle.high) / entry if (wrong_cap_extreme or short_uses_long_extreme) else (entry - candle.low) / entry
            sl_touched, tp_touched, tp_first = candle.high >= sl, candle.low <= tp, candle.close < candle.open
        else:
            favorable = (candle.low - entry) / entry if wrong_cap_extreme else (candle.high - entry) / entry
            sl_touched, tp_touched, tp_first = candle.low <= sl, candle.high >= tp, candle.close > candle.open
        if sl_touched:
            if tp_touched and tp_first:
                best = max(best, favorable)
                if no_tp_dual_cap:
                    continue
                if cap_one_bar_late:
                    stop_next = True
                    continue
            break
        best = max(best, favorable)
        if stop_next:
            break
    return best * 10_000.0


def _oracle_mae(candles: list[data.Candle], entry_index: int, *, short: bool) -> float:
    """Independent MAE oracle: adverse excursion until the TP resolves."""
    entry = candles[entry_index].close
    sl = entry * (1.0 + _SL_PCT if short else 1.0 - _SL_PCT)
    tp = entry * (1.0 - _TP_PCT if short else 1.0 + _TP_PCT)
    best = 0.0
    for index in range(entry_index + 1, entry_index + _HORIZON + 1):
        candle = candles[index]
        if short:
            adverse, tp_touched, sl_touched, tp_first = (candle.high - entry) / entry, candle.low <= tp, candle.high >= sl, candle.close < candle.open
        else:
            adverse, tp_touched, sl_touched, tp_first = (entry - candle.low) / entry, candle.high >= tp, candle.low <= sl, candle.close > candle.open
        if tp_touched and sl_touched and tp_first:
            break
        best = max(best, adverse)
        if tp_touched:
            break
    return best * 10_000.0


def _labeled_rows(candles: list[data.Candle]) -> list[dataset.LabeledRow]:
    features = [dataset.FeatureRow(index, candle.open_time, {"return_1": 0.0}, 0, False, False) for index, candle in enumerate(candles)]
    return dataset.attach_labels(features, candles, horizon=_HORIZON, label_threshold=0.0, tp_pct=_TP_PCT, sl_pct=_SL_PCT, include_warmup=True)


def test_mfe_and_mae_match_independent_raw_ohlc_oracles_row_by_row() -> None:
    candles, rows = _raw_candles(), _labeled_rows(_raw_candles())
    assert rows
    for row in rows:
        assert row.mfe_long_bps == pytest.approx(_oracle_mfe(candles, row.index, short=False))
        assert row.mfe_short_bps == pytest.approx(_oracle_mfe(candles, row.index, short=True))
        assert row.mae_long_bps == pytest.approx(_oracle_mae(candles, row.index, short=False))
        assert row.mae_short_bps == pytest.approx(_oracle_mae(candles, row.index, short=True))


@pytest.mark.parametrize(
    ("name", "kwargs", "side"),
    [
        ("no_cap_on_tp_resolved_dual_touch", {"no_tp_dual_cap": True}, "both"),
        ("cap_applied_one_candle_late", {"cap_one_bar_late": True}, "both"),
        ("cap_uses_wrong_extreme", {"wrong_cap_extreme": True}, "both"),
        ("short_uses_long_side_extreme", {"short_uses_long_extreme": True}, "short"),
    ],
)
def test_independent_oracle_catches_each_new_mfe_truncation_mutation(name: str, kwargs: dict[str, bool], side: str) -> None:
    candles, rows = _raw_candles(), _labeled_rows(_raw_candles())
    if side == "both":
        actual = [(row.mfe_long_bps, row.mfe_short_bps) for row in rows]
        mutated = [(_oracle_mfe(candles, row.index, short=False, **kwargs), _oracle_mfe(candles, row.index, short=True, **kwargs)) for row in rows]
    else:
        actual = [row.mfe_short_bps for row in rows]
        mutated = [_oracle_mfe(candles, row.index, short=True, **kwargs) for row in rows]
    assert any(expected != pytest.approx(observed) for expected, observed in zip(actual, mutated)), name


def test_dual_touch_mfe_and_mae_use_opposite_reachable_extremes() -> None:
    """TP-first caps MFE but excludes MAE; SL-first does the converse."""
    def candle(open_: float, high: float, low: float, close: float) -> data.Candle:
        return data.Candle(datetime(2020, 1, 1, tzinfo=timezone.utc), open_, high, low, close, 0.0, 0.0, 0, 0.0, 0.0)
    candles = [candle(100, 100, 100, 100), candle(100, 102, 98, 101), candle(100, 102, 98, 99)]
    # Long bullish dual-touch: TP-first includes the high for MFE, but the low is unreachable for MAE.
    assert dataset.maximum_favorable_excursion_long_bps(0, candles, 1, 0.01, 0.01) == pytest.approx(200.0)
    assert dataset.maximum_adverse_excursion_long_bps(0, candles, 1, 0.01, 0.01) == 0.0
    # Long bearish dual-touch: SL-first excludes MFE, but its low is reachable for MAE.
    assert dataset.maximum_favorable_excursion_long_bps(0, candles[0:1] + candles[2:3], 1, 0.01, 0.01) == 0.0
    assert dataset.maximum_adverse_excursion_long_bps(0, candles[0:1] + candles[2:3], 1, 0.01, 0.01) == pytest.approx(200.0)


def test_mfe_and_mae_floats_do_not_change_interned_target_content_counts() -> None:
    rows = _labeled_rows(_raw_candles())
    target_contents = {tuple(sorted(row.targets.items())) for row in rows}
    reason_contents = {tuple(sorted(row.target_reasons.items())) for row in rows}
    assert len({id(row.targets) for row in rows}) == len(target_contents)
    assert len({id(row.target_reasons) for row in rows}) == len(reason_contents)


@pytest.mark.skipif(not models.CatBoostRegressorAdapter.available(), reason="catboost not installed")
def test_catboost_quantile_regressor_round_trips() -> None:
    adapter = models.CatBoostRegressorAdapter(feature_names=("x",), model_params={"task_type": "CPU", "iterations": 4, "depth": 2, "verbose": False}).fit([[0.0], [1.0], [2.0], [3.0]], [0.0, 10.0, 20.0, 30.0])
    assert adapter.model_params["loss_function"] == "Quantile:alpha=0.5"
    assert models.CatBoostRegressorAdapter.from_dict(adapter.as_dict()).predict([[1.5]]) == pytest.approx(adapter.predict([[1.5]]))


def test_catboost_quantile_regressor_predict_proba_directs_callers_to_predict() -> None:
    with pytest.raises(NotImplementedError, match="use predict instead"):
        models.CatBoostRegressorAdapter(feature_names=("x",)).predict_proba([[1.0]])
