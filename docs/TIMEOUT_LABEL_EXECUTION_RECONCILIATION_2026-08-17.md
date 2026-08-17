# Timeout label/execution reconciliation

The executable settlement is authoritative.  A triple-barrier class is a
forecast target (TP-before-SL); it is not itself a payoff.  In particular,
`long_timeout` remains class `0`, while its economic settlement is the signed
close-to-close return from the entry bar to the horizon bar.  The same applies
to the short side with the return sign inverted.

The implementation is deliberately shared by contract rather than by treating
all class-zero rows as a stop loss:

- `dataset.triple_barrier_label_long` records `long_timeout` when neither
  barrier touches.
- `training.realized_payoffs` maps that reason to the horizon-close return;
  `select_threshold` and training metrics pass that complete vector to
  `_trading_pnl`.
- `backtest._resolve_execution_outcome` returns `("TIMEOUT", candle.close)`
  on the horizon bar and charges the configured limit-only maker/maker cost.
- `barrier_screen.screen` uses the same horizon-bar close and 4 bps cost.

`_trading_pnl` rejects a partial settlement vector.  It may not fall back to
the legacy `class 0 -> -sl_pct` mapping for any subset of rows.

## Recorded-result interpretation

Stage 3 and stage 4 threshold/EV figures produced before this reconciliation
priced every selected timeout class zero as `-sl_pct` (plus cost), rather than
its horizon-close return (plus cost).  Those threshold-selection-derived
figures are not comparable to this code's definition.  Barrier-screen and
horizon-screen payoff fields that used horizon-close settlement retain that
settlement basis, but their resolution shares are descriptive touch rates, not
label/execution mismatch scores.  No result was regenerated here: retraining
and backtesting are intentionally out of scope.
