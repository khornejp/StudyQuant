"""Multi-feature, rule-based regime detector (up / down / range).

This replaces learned-classifier hard routing with a deterministic, causal
rule over multiple multi-timeframe (F17) features. It combines four scores --
trend, volatility, range, and breakout -- then applies a decision with
entry/exit hysteresis and a minimum-hold so the routed regime does not churn.

Design goals (mirroring the existing RegimeDetector patterns so it drops into
the same train/backtest/live plumbing):

* Deterministic and causal. Per-row scores depend only on that row's features
  and normalization statistics fit ONCE on the training span; the sequential
  hysteresis state depends only on past rows. Nothing looks ahead.
* Train/serve parity. fit() computes per-feature (mean, std) on the training
  rows; those stats are persisted (to_dict) and reloaded (from_dict) so the
  backtest and live paths score against the SAME normalization the training
  bucket assignment used -- no re-fitting on a live buffer.
* Same up/down/range output classes as the existing entry-model buckets, so
  the regime-aware entry models can be trained/served against it unchanged
  (they must be retrained with THIS detector's bucketing -- switching the
  router without re-bucketing would reintroduce train/serve skew).

Thresholds/weights default to the values sketched in the rule-based design
note; every constant is exposed on MultiFeatureRegimeConfig for tuning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from statistics import fmean, pstdev
from typing import Mapping, Sequence

REGIME_CLASSES: tuple[str, ...] = ("up", "down", "range")

# Minimum std used when normalizing a feature whose training-span dispersion is
# ~0 (constant feature); prevents divide-by-zero and runaway z-scores.
_STD_FLOOR = 1e-9


@dataclass(frozen=True)
class MultiFeatureRegimeConfig:
    """Structure, weights, and decision thresholds for the rule detector."""

    # --- Aggregate (regime-anchor) trend score: LONG timeframes only
    #     (1h / 4h / 24h). The short 5m/15m/30m timeframes are intentionally
    #     NOT here -- they live solely in fast_trend_weights below, so their
    #     role (confirmation / early exit) is cleanly separated from the long-TF
    #     role (defining the regime). Weights sum to 1.0. trend_slope_24h is a
    #     real F17 feature (price-normalized linreg slope over the last <=24
    #     closed 1h bars); range center context also uses distance_from_24h_*.
    trend_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "trend_slope_1h": 0.25,
            "trend_slope_4h": 0.30,
            "return_4h": 0.15,
            "ema_gap_4h": 0.15,
            "trend_slope_24h": 0.15,
        }
    )
    # --- Fast-trend (short-TF) sub-score: 5m/15m/30m ONLY, used as a distinct
    #     multi-timeframe confirmation/timing signal in the decision rules
    #     (separate from the aggregate trend that anchors the regime). Weights
    #     are normalized among themselves. ---
    fast_trend_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "return_5": 0.20,          # 5m -- lower weight (noisiest)
            "trend_slope_15m": 0.35,   # 15m
            "trend_slope_30": 0.45,    # 30m -- heaviest short-TF anchor
        }
    )
    use_fast_trend_rules: bool = True
    # Block a fresh up/down entry when the short-TF trend opposes the candidate
    # direction by more than this magnitude (MTF confirmation gate).
    fast_conflict_max: float = 0.60
    # While holding up/down, exit to range early if the short-TF trend flips
    # against the position past this magnitude (before the slow aggregate trend
    # crosses trend_exit).
    fast_exit: float = 0.80

    # --- Volatility score: weighted z-scores of dispersion features. ---
    vol_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "atr_pct_1h": 0.40,
            "atr_pct_4h": 0.30,
            "bb_width_1h": 0.30,
        }
    )
    # --- Range score: high when NOT trending (low ADX / low BB width) and
    #     price sits near the middle of its 24h band. ADX/BB-width enter as
    #     INVERSE z-scores (low -> high range score). ---
    range_adx_weights: Mapping[str, float] = field(
        default_factory=lambda: {"adx_1h": 0.35, "adx_4h": 0.20}
    )
    range_bbwidth_weights: Mapping[str, float] = field(
        default_factory=lambda: {"bb_width_1h": 0.30}
    )
    range_center_weight: float = 0.15  # weight on 24h-band center proximity

    # --- Breakout override: immediate up/down on a 24h break with volume. ---
    breakout_up_flag: str = "rolling_high_breakout_24h"
    breakout_down_flag: str = "rolling_low_breakdown_24h"
    breakout_volume_feature: str = "volume_z_1h"
    breakout_volume_z_min: float = 1.5

    # --- Decision thresholds (in trend/range score units, i.e. ~z). ---
    trend_enter: float = 0.70   # |trend| to ENTER up/down
    trend_exit: float = 0.40    # |trend| to STAY in current up/down (hysteresis)
    range_enter: float = 0.65   # range score to enter range
    trend_abs_max_for_range: float = 0.45  # trend must be flat-ish for range
    vol_min_for_trend: float = 0.20        # need some volatility to call a trend

    # --- Stabilization. ---
    min_hold_bars: int = 60  # 1m bars; strong breakouts bypass this
    # A regime switch also requires the NEW candidate to persist for this many
    # consecutive bars (a debounce on top of min_hold_bars, which only gates how
    # long the CURRENT regime has been held). Default 1 = no extra confirmation
    # (a single differing bar can switch once min_hold is met, the prior
    # behavior). Raise to 5-15 to suppress single-bar/noise switches. A strong
    # breakout bypasses both gates.
    switch_confirm_bars: int = 1
    # If False, a held up/down regime cannot flip directly to the opposite
    # direction via the slow trend -- it must pass through range first
    # (up -> range -> down). A strong breakout still flips immediately (that
    # override is applied before this rule). Default True preserves the direct
    # up<->down transition. Setting False is the more conservative choice for
    # 1m scalping (avoids hard reversals on a single slow-trend cross).
    allow_direct_reversal: bool = True

    def __post_init__(self) -> None:
        if self.trend_exit > self.trend_enter:
            raise ValueError("trend_exit must be <= trend_enter (hysteresis)")
        if self.min_hold_bars < 0:
            raise ValueError("min_hold_bars must be non-negative")
        if self.switch_confirm_bars < 1:
            raise ValueError("switch_confirm_bars must be >= 1")
        if self.fast_conflict_max < 0.0:
            raise ValueError("fast_conflict_max must be non-negative")
        if self.fast_exit < 0.0:
            raise ValueError("fast_exit must be non-negative")

    def referenced_features(self) -> list[str]:
        names: set[str] = set()
        names.update(self.trend_weights)
        names.update(self.fast_trend_weights)
        names.update(self.vol_weights)
        names.update(self.range_adx_weights)
        names.update(self.range_bbwidth_weights)
        names.update({
            self.breakout_volume_feature,
            "distance_from_24h_low",
            "drawdown_from_24h_high",
        })
        return sorted(names)

    def as_dict(self) -> dict[str, object]:
        return {
            "trend_weights": dict(self.trend_weights),
            "fast_trend_weights": dict(self.fast_trend_weights),
            "use_fast_trend_rules": self.use_fast_trend_rules,
            "fast_conflict_max": self.fast_conflict_max,
            "fast_exit": self.fast_exit,
            "vol_weights": dict(self.vol_weights),
            "range_adx_weights": dict(self.range_adx_weights),
            "range_bbwidth_weights": dict(self.range_bbwidth_weights),
            "range_center_weight": self.range_center_weight,
            "breakout_up_flag": self.breakout_up_flag,
            "breakout_down_flag": self.breakout_down_flag,
            "breakout_volume_feature": self.breakout_volume_feature,
            "breakout_volume_z_min": self.breakout_volume_z_min,
            "trend_enter": self.trend_enter,
            "trend_exit": self.trend_exit,
            "range_enter": self.range_enter,
            "trend_abs_max_for_range": self.trend_abs_max_for_range,
            "vol_min_for_trend": self.vol_min_for_trend,
            "min_hold_bars": self.min_hold_bars,
            "switch_confirm_bars": self.switch_confirm_bars,
            "allow_direct_reversal": self.allow_direct_reversal,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "MultiFeatureRegimeConfig":
        defaults = cls()
        def _m(key: str, fallback: Mapping[str, float]) -> Mapping[str, float]:
            v = payload.get(key)
            return {str(k): float(x) for k, x in v.items()} if isinstance(v, Mapping) else dict(fallback)
        def _f(key: str, fallback: float) -> float:
            v = payload.get(key)
            try:
                return float(v)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return fallback
        def _s(key: str, fallback: str) -> str:
            v = payload.get(key)
            return str(v) if isinstance(v, str) else fallback
        def _b(key: str, fallback: bool) -> bool:
            v = payload.get(key)
            return bool(v) if isinstance(v, bool) else fallback
        return cls(
            trend_weights=_m("trend_weights", defaults.trend_weights),
            fast_trend_weights=_m("fast_trend_weights", defaults.fast_trend_weights),
            use_fast_trend_rules=_b("use_fast_trend_rules", defaults.use_fast_trend_rules),
            fast_conflict_max=_f("fast_conflict_max", defaults.fast_conflict_max),
            fast_exit=_f("fast_exit", defaults.fast_exit),
            vol_weights=_m("vol_weights", defaults.vol_weights),
            range_adx_weights=_m("range_adx_weights", defaults.range_adx_weights),
            range_bbwidth_weights=_m("range_bbwidth_weights", defaults.range_bbwidth_weights),
            range_center_weight=_f("range_center_weight", defaults.range_center_weight),
            breakout_up_flag=_s("breakout_up_flag", defaults.breakout_up_flag),
            breakout_down_flag=_s("breakout_down_flag", defaults.breakout_down_flag),
            breakout_volume_feature=_s("breakout_volume_feature", defaults.breakout_volume_feature),
            breakout_volume_z_min=_f("breakout_volume_z_min", defaults.breakout_volume_z_min),
            trend_enter=_f("trend_enter", defaults.trend_enter),
            trend_exit=_f("trend_exit", defaults.trend_exit),
            range_enter=_f("range_enter", defaults.range_enter),
            trend_abs_max_for_range=_f("trend_abs_max_for_range", defaults.trend_abs_max_for_range),
            vol_min_for_trend=_f("vol_min_for_trend", defaults.vol_min_for_trend),
            min_hold_bars=int(_f("min_hold_bars", float(defaults.min_hold_bars))),
            switch_confirm_bars=int(_f("switch_confirm_bars", float(defaults.switch_confirm_bars))),
            allow_direct_reversal=_b("allow_direct_reversal", defaults.allow_direct_reversal),
        )


def _finite(x: object, default: float = 0.0) -> float:
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return v if isfinite(v) else default


class MultiFeatureRegimeDetector:
    """Causal up/down/range detector combining trend/vol/range/breakout scores."""

    def __init__(
        self,
        config: MultiFeatureRegimeConfig | None = None,
        norm_stats: Mapping[str, tuple[float, float]] | None = None,
    ) -> None:
        self.config = config or MultiFeatureRegimeConfig()
        # feature -> (mean, std); std already floored.
        self.norm_stats: dict[str, tuple[float, float]] = {
            str(k): (float(v[0]), float(v[1])) for k, v in (norm_stats or {}).items()
        }

    # -- fitting -----------------------------------------------------------
    def fit(self, feature_rows: Sequence[Mapping[str, float]]) -> "MultiFeatureRegimeDetector":
        """Fit per-feature (mean, std) on the training rows.

        Fitting on the whole training span (not per-fold) matches the existing
        RegimeDetector.fit_directional_threshold pattern and is causal w.r.t.
        the backtest/live windows, which are chronologically after training.
        """
        stats: dict[str, tuple[float, float]] = {}
        for name in self.config.referenced_features():
            vals = [_finite(r.get(name, 0.0)) for r in feature_rows]
            if not vals:
                stats[name] = (0.0, 1.0)
                continue
            mean = fmean(vals)
            std = pstdev(vals) if len(vals) > 1 else 0.0
            stats[name] = (mean, max(std, _STD_FLOOR))
        self.norm_stats = stats
        return self

    @property
    def fitted(self) -> bool:
        return bool(self.norm_stats)

    def _z(self, name: str, features: Mapping[str, float]) -> float:
        mean, std = self.norm_stats.get(name, (0.0, 1.0))
        return (_finite(features.get(name, mean)) - mean) / (std if std else 1.0)

    # -- scoring -----------------------------------------------------------
    def _row_scores(self, features: Mapping[str, float]) -> tuple[float, float, float, float, bool, bool]:
        cfg = self.config
        trend = sum(w * self._z(name, features) for name, w in cfg.trend_weights.items())
        # Short-TF (5m/15m/30m) trend, normalized among itself -> confirmation/timing.
        fast_total = sum(abs(w) for w in cfg.fast_trend_weights.values()) or 1.0
        trend_fast = sum(w * self._z(name, features) for name, w in cfg.fast_trend_weights.items()) / fast_total
        vol = sum(w * self._z(name, features) for name, w in cfg.vol_weights.items())
        # Range: inverse z of ADX / BB width (low -> high range) + center proximity.
        rng = 0.0
        for name, w in cfg.range_adx_weights.items():
            rng += w * (-self._z(name, features))
        for name, w in cfg.range_bbwidth_weights.items():
            rng += w * (-self._z(name, features))
        rng += cfg.range_center_weight * self._center_proximity(features)
        bo_up, bo_down = self._breakouts(features)
        return trend, vol, rng, trend_fast, bo_up, bo_down

    def _center_proximity(self, features: Mapping[str, float]) -> float:
        """~1 near the middle of the 24h band, ~0 at an extreme. Uses the two
        24h-distance features (both are fractions of price)."""
        dist_low = abs(_finite(features.get("distance_from_24h_low", 0.0)))    # >=0, 0 at low
        drawdown = abs(_finite(features.get("drawdown_from_24h_high", 0.0)))   # >=0, 0 at high
        span = dist_low + drawdown
        if span <= 0.0:
            return 0.0
        position = dist_low / span  # 0 at low, 1 at high
        return 1.0 - 2.0 * abs(position - 0.5)  # 1 at center, 0 at extremes

    def _breakouts(self, features: Mapping[str, float]) -> tuple[bool, bool]:
        cfg = self.config
        vol_z = _finite(features.get(cfg.breakout_volume_feature, 0.0))
        strong_vol = vol_z > cfg.breakout_volume_z_min
        up = _finite(features.get(cfg.breakout_up_flag, 0.0)) > 0.5 and strong_vol
        down = _finite(features.get(cfg.breakout_down_flag, 0.0)) > 0.5 and strong_vol
        return up, down

    # -- decision ----------------------------------------------------------
    def _enter_decision(self, trend: float, vol: float, rng: float, trend_fast: float) -> str:
        cfg = self.config
        if rng > cfg.range_enter and abs(trend) < cfg.trend_abs_max_for_range:
            return "range"
        if trend > cfg.trend_enter and vol > cfg.vol_min_for_trend:
            # MTF confirmation: don't enter up if short-TF trend opposes hard.
            if not cfg.use_fast_trend_rules or trend_fast > -cfg.fast_conflict_max:
                return "up"
            return "range"
        if trend < -cfg.trend_enter and vol > cfg.vol_min_for_trend:
            if not cfg.use_fast_trend_rules or trend_fast < cfg.fast_conflict_max:
                return "down"
            return "range"
        return "range"

    def _stay_decision(self, current: str, trend: float, vol: float, rng: float, trend_fast: float) -> str:
        cfg = self.config
        if current == "up":
            # Early exit: short-TF momentum flipped hard down while holding up.
            if cfg.use_fast_trend_rules and trend_fast < -cfg.fast_exit:
                return "range"
            if trend > cfg.trend_exit:
                return "up"
            if cfg.allow_direct_reversal and trend < -cfg.trend_enter and vol > cfg.vol_min_for_trend:
                return "down"
            return "range"
        if current == "down":
            if cfg.use_fast_trend_rules and trend_fast > cfg.fast_exit:
                return "range"
            if trend < -cfg.trend_exit:
                return "down"
            if cfg.allow_direct_reversal and trend > cfg.trend_enter and vol > cfg.vol_min_for_trend:
                return "up"
            return "range"
        # currently range: only leave on a genuine trend WITH short-TF agreement.
        if trend > cfg.trend_enter and vol > cfg.vol_min_for_trend and (
            not cfg.use_fast_trend_rules or trend_fast > -cfg.fast_conflict_max
        ):
            return "up"
        if trend < -cfg.trend_enter and vol > cfg.vol_min_for_trend and (
            not cfg.use_fast_trend_rules or trend_fast < cfg.fast_conflict_max
        ):
            return "down"
        return "range"

    def detect_all(self, feature_rows: Sequence[Mapping[str, float]]) -> list[str]:
        """Return the causal up/down/range regime for each row."""
        cfg = self.config
        min_hold = max(0, int(cfg.min_hold_bars))
        confirm = max(1, int(cfg.switch_confirm_bars))
        out: list[str] = []
        current: str | None = None
        hold = 0
        pending: str | None = None
        pending_count = 0
        for features in feature_rows:
            trend, vol, rng, trend_fast, bo_up, bo_down = self._row_scores(features)
            strong = bo_up or bo_down
            if bo_up:
                candidate = "up"
            elif bo_down:
                candidate = "down"
            elif current is None:
                candidate = self._enter_decision(trend, vol, rng, trend_fast)
            else:
                candidate = self._stay_decision(current, trend, vol, rng, trend_fast)

            if current is None:
                current = candidate
                hold = 0
                pending = None
                pending_count = 0
            elif candidate == current:
                hold += 1
                pending = None
                pending_count = 0
            else:
                # Candidate differs: count consecutive bars it persists.
                if candidate == pending:
                    pending_count += 1
                else:
                    pending = candidate
                    pending_count = 1
                # Switch only if a strong breakout, or both gates are met:
                # current held long enough AND new candidate confirmed enough.
                if strong or (hold >= min_hold and pending_count >= confirm):
                    current = candidate
                    hold = 0
                    pending = None
                    pending_count = 0
                else:
                    hold += 1
            out.append(current)
        return out

    def detect_one(self, feature_rows: Sequence[Mapping[str, float]]) -> str:
        """Causal regime for the LAST row given the buffer of prior rows."""
        regimes = self.detect_all(feature_rows)
        return regimes[-1] if regimes else "range"

    # -- persistence -------------------------------------------------------
    def to_dict(self) -> dict[str, object]:
        return {
            "config": self.config.as_dict(),
            "norm_stats": {k: [v[0], v[1]] for k, v in self.norm_stats.items()},
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "MultiFeatureRegimeDetector":
        config = MultiFeatureRegimeConfig.from_dict(payload.get("config", {}) if isinstance(payload.get("config"), Mapping) else {})
        raw = payload.get("norm_stats", {})
        norm: dict[str, tuple[float, float]] = {}
        if isinstance(raw, Mapping):
            for k, v in raw.items():
                try:
                    norm[str(k)] = (float(v[0]), float(v[1]))  # type: ignore[index]
                except (TypeError, ValueError, IndexError):
                    continue
        return cls(config=config, norm_stats=norm)

    def diagnostics(self, regimes: Sequence[str]) -> dict[str, object]:
        regimes = list(regimes)
        total = len(regimes) or 1
        counts = {c: regimes.count(c) for c in REGIME_CLASSES}
        ratios = {c: counts[c] / total for c in REGIME_CLASSES}
        transitions = sum(1 for a, b in zip(regimes, regimes[1:]) if a != b)
        # Per-type transition counts (a -> b).
        by_type: dict[str, int] = {}
        for a, b in zip(regimes, regimes[1:]):
            if a != b:
                by_type[f"{a}->{b}"] = by_type.get(f"{a}->{b}", 0) + 1
        direct_reversals = by_type.get("up->down", 0) + by_type.get("down->up", 0)
        # Average duration (in bars) of each regime's runs.
        durations: dict[str, list[int]] = {c: [] for c in REGIME_CLASSES}
        if regimes:
            run_regime = regimes[0]
            run_len = 1
            for r in regimes[1:]:
                if r == run_regime:
                    run_len += 1
                else:
                    durations.setdefault(run_regime, []).append(run_len)
                    run_regime = r
                    run_len = 1
            durations.setdefault(run_regime, []).append(run_len)
        avg_duration = {
            c: (sum(durations[c]) / len(durations[c]) if durations.get(c) else 0.0)
            for c in REGIME_CLASSES
        }
        return {
            "regime_counts": counts,
            "regime_ratios": ratios,
            "regime_transition_count": transitions,
            "transition_by_type": by_type,
            "direct_reversal_count": direct_reversals,
            "avg_regime_duration_bars": avg_duration,
        }
