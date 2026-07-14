"""Reliability (calibration) of the side models' probabilities.

Every entry model in this repo answers one question -- "does price reach
+label_tp_pct before -label_sl_pct within the horizon?" -- and the whole
downstream stack reads that output as a PROBABILITY, not a score:
risk.kelly_leverage_for_signal sizes the bet with it, risk.expected_edge
decides whether an edge exists at all, and training.select_threshold picks the
entry cutoff by assuming the number means what it says. If the model says 0.52
and the event happens 17% of the time, every one of those consumers is wrong in
the same direction, and no amount of threshold tuning repairs it -- the 2025
backtest entered at a mean probability of 0.522 and realized a 32.3% win rate.

Accuracy does not surface this: a model can rank bars perfectly and still be
badly calibrated (a monotone squash of the probabilities leaves the ranking
untouched). So this module measures the thing the stack actually relies on:

  reliability_curve  -- bucket the predictions, compare each bucket's mean
                        prediction against the rate the event really occurred.
                        A calibrated model sits on the diagonal.
  brier_score        -- mean squared error of the probabilities (sharpness and
                        calibration together; lower is better).
  expected_calibration_error -- the sample-weighted average gap from the
                        diagonal. One number for "how far off are the stated
                        probabilities".
  decision_band      -- the only slice that spends money: the bars ABOVE the
                        deployed entry threshold. Its observed rate is compared
                        against risk.breakeven_probability for the barrier, so
                        the report answers "can this model pay for its costs at
                        this barrier" and not merely "is it well calibrated".

Pure metrics, no I/O: the caller supplies (probability, outcome) pairs it
produced with the same feature/label/routing path training used. See
verify_calibration.py for the artifact-driven wiring.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from . import risk

__all__ = [
    "ReliabilityBin",
    "CalibrationReport",
    "DecisionBand",
    "brier_score",
    "decision_band",
    "expected_calibration_error",
    "reliability_curve",
]

# Below this many samples a bin's observed rate is noise, not a rate: a bucket
# holding 3 bars can only report 0%, 33%, 67% or 100%, none of which says
# anything about the model. Such bins are still reported (the operator must see
# where the mass is), but they are excluded from the ECE so a nearly empty tail
# bucket cannot dominate the headline number.
MIN_BIN_SAMPLES = 20

# Probabilities are read from model adapters, which clip to [0, 1]; anything
# outside that (or non-finite) is a bug in the adapter, not a datum to average.
_PROBABILITY_TOLERANCE = 1e-9


@dataclass(frozen=True)
class ReliabilityBin:
    """One bucket of the reliability curve.

    gap = observed_rate - mean_predicted. Negative means the model OVERSTATES
    the event (says 0.52, happens 0.17) -- the direction that makes a losing
    strategy look profitable, because every consumer downstream sizes and enters
    on the stated number.
    """

    lower: float
    upper: float
    count: int
    mean_predicted: float
    observed_rate: float

    @property
    def gap(self) -> float:
        return self.observed_rate - self.mean_predicted

    def as_dict(self) -> dict[str, object]:
        return {
            "lower": self.lower,
            "upper": self.upper,
            "count": self.count,
            "mean_predicted": self.mean_predicted,
            "observed_rate": self.observed_rate,
            "gap": self.gap,
        }


@dataclass(frozen=True)
class DecisionBand:
    """What happens on the bars the model would actually have traded.

    The reliability curve grades the model everywhere; this grades it where the
    money is. `observed_rate` here is the win rate the strategy would realize
    (before the backtest's own exit rules), and `breakeven_rate` is what the
    barrier demands of it -- so `clears_breakeven` is the verdict the operator
    is really after.

    The caller decides what population it hands in, and that choice IS the
    meaning of this band: pass only the bars the entry policy would let the
    strategy take (direction policy, range mean-reversion gate), or the band
    reports a win rate for bars nobody trades. share_of_bars is therefore the
    share of THAT population which cleared the threshold.
    """

    threshold: float
    count: int
    share_of_bars: float
    mean_predicted: float
    observed_rate: float
    breakeven_rate: float

    @property
    def clears_breakeven(self) -> bool:
        if not isfinite(self.breakeven_rate) or self.count == 0:
            return False
        return self.observed_rate >= self.breakeven_rate

    @property
    def margin(self) -> float:
        """Observed rate minus the barrier's hurdle. Negative = structurally unprofitable."""
        return self.observed_rate - self.breakeven_rate

    def as_dict(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "count": self.count,
            "share_of_bars": self.share_of_bars,
            "mean_predicted": self.mean_predicted,
            "observed_rate": self.observed_rate,
            "breakeven_rate": self.breakeven_rate,
            "margin": self.margin,
            "clears_breakeven": self.clears_breakeven,
        }


@dataclass(frozen=True)
class CalibrationReport:
    count: int
    mean_predicted: float
    observed_rate: float
    brier: float
    ece: float
    bins: tuple[ReliabilityBin, ...]
    decision: DecisionBand | None = None

    @property
    def overall_gap(self) -> float:
        """Mean prediction minus base rate. The headline miscalibration."""
        return self.mean_predicted - self.observed_rate

    def as_dict(self) -> dict[str, object]:
        return {
            "count": self.count,
            "mean_predicted": self.mean_predicted,
            "observed_rate": self.observed_rate,
            "overall_gap": self.overall_gap,
            "brier": self.brier,
            "ece": self.ece,
            "ece_min_bin_samples": MIN_BIN_SAMPLES,
            "bins": [b.as_dict() for b in self.bins],
            "decision_band": None if self.decision is None else self.decision.as_dict(),
        }


def _validate(probabilities: Sequence[float], outcomes: Sequence[int]) -> None:
    if len(probabilities) != len(outcomes):
        raise ValueError(
            f"probabilities and outcomes must be the same length "
            f"({len(probabilities)} vs {len(outcomes)})"
        )
    for probability in probabilities:
        if not isfinite(probability) or not (
            -_PROBABILITY_TOLERANCE <= probability <= 1.0 + _PROBABILITY_TOLERANCE
        ):
            raise ValueError(f"probability outside [0, 1]: {probability!r}")
    for outcome in outcomes:
        if outcome not in (0, 1):
            raise ValueError(f"outcome must be 0 or 1, got {outcome!r}")


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean squared error of the probabilities. NaN on an empty sample."""
    _validate(probabilities, outcomes)
    return _brier_unchecked(probabilities, outcomes)


def _brier_unchecked(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    # Validation is a full Python-level pass over the sample, and reliability_curve
    # scores hundreds of thousands of bars; the internal callers validate once and
    # then use this.
    if not probabilities:
        return float("nan")
    return sum((p - o) ** 2 for p, o in zip(probabilities, outcomes)) / len(probabilities)


def reliability_curve(
    probabilities: Sequence[float],
    outcomes: Sequence[int],
    *,
    bin_count: int = 10,
    threshold: float | None = None,
    tp_pct: float | None = None,
    sl_pct: float | None = None,
    round_trip_cost: float = 0.0,
) -> CalibrationReport:
    """Bucket predictions into `bin_count` equal-width bins over [0, 1].

    Equal-width, not equal-mass: the question is "when the model says 0.5, does
    it happen half the time", which is a statement about probability VALUES.
    Equal-mass bins would hide exactly the pathology seen here -- probabilities
    compressed into a narrow band around 0.52 -- by spreading that band across
    every bucket.

    Pass threshold + the barrier to also get the decision band (see
    decision_band); without a barrier there is no break-even to judge it
    against, so it is reported without one only when tp/sl are omitted.
    """
    if bin_count <= 0:
        raise ValueError("bin_count must be positive")
    _validate(probabilities, outcomes)

    edges = [i / bin_count for i in range(bin_count + 1)]
    sums: list[float] = [0.0] * bin_count
    hits: list[int] = [0] * bin_count
    counts: list[int] = [0] * bin_count
    for probability, outcome in zip(probabilities, outcomes):
        # The top edge belongs to the last bin (a 1.0 prediction is not its own
        # bucket), so clamp the index rather than opening a bin_count+1'th bin.
        index = min(int(probability * bin_count), bin_count - 1)
        sums[index] += probability
        hits[index] += outcome
        counts[index] += 1

    bins = tuple(
        ReliabilityBin(
            lower=edges[i],
            upper=edges[i + 1],
            count=counts[i],
            mean_predicted=sums[i] / counts[i] if counts[i] else float("nan"),
            observed_rate=hits[i] / counts[i] if counts[i] else float("nan"),
        )
        for i in range(bin_count)
    )

    total = len(probabilities)
    decision = None
    if threshold is not None:
        decision = _decision_band_unchecked(
            probabilities,
            outcomes,
            threshold=threshold,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            round_trip_cost=round_trip_cost,
        )
    return CalibrationReport(
        count=total,
        mean_predicted=sum(probabilities) / total if total else float("nan"),
        observed_rate=sum(outcomes) / total if total else float("nan"),
        brier=_brier_unchecked(probabilities, outcomes),
        ece=expected_calibration_error(bins),
        bins=bins,
        decision=decision,
    )


def expected_calibration_error(bins: Sequence[ReliabilityBin]) -> float:
    """Sample-weighted mean |observed - predicted| over the usable bins.

    Bins below MIN_BIN_SAMPLES are dropped, not counted as zero error: their
    observed rate is quantization noise, and including them would let a
    3-sample bucket that happened to land on the diagonal flatter the model.
    NaN when no bin has enough samples -- that is "not measurable", and a 0.0
    there would read as perfect calibration.
    """
    usable = [b for b in bins if b.count >= MIN_BIN_SAMPLES]
    total = sum(b.count for b in usable)
    if not total:
        return float("nan")
    return sum(b.count * abs(b.gap) for b in usable) / total


def decision_band(
    probabilities: Sequence[float],
    outcomes: Sequence[int],
    *,
    threshold: float,
    tp_pct: float | None = None,
    sl_pct: float | None = None,
    round_trip_cost: float = 0.0,
) -> DecisionBand:
    """Grade the model on the bars it would have entered (probability >= threshold).

    breakeven_rate is NaN when no barrier is supplied: there is then no hurdle
    to compare against, and inventing one (0.5) would silently pass or fail the
    model against a barrier it never traded.
    """
    _validate(probabilities, outcomes)
    return _decision_band_unchecked(
        probabilities, outcomes, threshold=threshold, tp_pct=tp_pct, sl_pct=sl_pct,
        round_trip_cost=round_trip_cost,
    )


def _decision_band_unchecked(
    probabilities: Sequence[float],
    outcomes: Sequence[int],
    *,
    threshold: float,
    tp_pct: float | None,
    sl_pct: float | None,
    round_trip_cost: float,
) -> DecisionBand:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must be in [0, 1], got {threshold!r}")

    entered = [(p, o) for p, o in zip(probabilities, outcomes) if p >= threshold]
    total = len(probabilities)
    count = len(entered)
    if tp_pct is None or sl_pct is None:
        breakeven = float("nan")
    else:
        breakeven = risk.breakeven_probability(tp_pct, sl_pct, round_trip_cost)
    return DecisionBand(
        threshold=threshold,
        count=count,
        share_of_bars=count / total if total else float("nan"),
        mean_predicted=sum(p for p, _ in entered) / count if count else float("nan"),
        observed_rate=sum(o for _, o in entered) / count if count else float("nan"),
        breakeven_rate=breakeven,
    )
