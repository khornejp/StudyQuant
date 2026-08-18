# Calibration TP-reference correction

## Decision

Option 1 is the valid correction. The side models are trained and calibrated
for `P(TP before SL within the horizon)`, so binary TP labels remain the right
target for calibration. They do not identify either `P(timeout)` or the
conditional return at the horizon close. Treating every non-TP label as an SL
payoff would be an assumption, not data. Therefore calibration cannot issue an
economic trade/no-trade decision.

`DecisionBand` / `decision_band` and `clears_breakeven` have been removed.
Their replacement is `EntryTpRateReference` /
`entry_tp_rate_reference`. It reports the observed binary TP-before-SL rate and
the corresponding binary TP/SL reference, explicitly labelled as **not an
economic decision**. Its serialized `economic_decision` is
`unavailable_from_binary_tp_labels`.

Economic approval must use a measured three-outcome execution population:
TP, SL, and TIMEOUT settled at the actual horizon close, including the actual
cost schedule. The existing backtest execution summaries (`mean_net_bps`,
outcome counts, and settled trade returns) are the appropriate source when a
run has been made; they are not inferred by calibration.

## Consumer audit

The source-tree search for `clears_breakeven` found only these runtime
consumers before this correction:

| Location | Previous use | Corrected use |
| --- | --- | --- |
| `btcusdt_quant/calibration.py` | Produced an economic-sounding boolean from binary labels. | Produces TP-label reference metadata only. |
| `verify_calibration.py` | Printed `CLEARS/BELOW break-even` as the CLI verdict. | Prints a TP-label reference and an explicit unavailable economic decision. |
| `tests/test_calibration.py` | Tested the misleading field. | Tests that the identical binary cohorts cannot yield an economic verdict. |

No gate, live entry path, backtest admission path, approval-package validator,
model card, or other human-facing CLI consumes this value. The live/backtest
EV gate is separate: it defaults to refusing binary-only EV in
`live.select_entry_signal`; it must use a three-outcome economic estimate to
admit trades. `clears_breakeven` was not a gate.

The only recorded historical instance located was
`artifacts/backtest_results/calibration_report.json`. It contains the old
`clears_breakeven: false` display field, but no approval or accept/reject record
references it. On repository evidence, no recorded result was accepted or
rejected on its strength. That historical field must be read only as a binary
TP-label comparison, never as an economic rejection.

## Replay provenance

`run_backtest` now records `run_config.allow_binary_ev` in every new result.
This makes future regime-aware replays auditable: the summary will show whether
the binary-only EV waiver was used. Existing summaries lack the field, so their
waiver state remains unknown rather than being inferred from configuration.
