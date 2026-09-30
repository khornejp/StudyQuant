# K=45 single-position and 50 bps stop preregistration

Frozen at `2026-09-29T21:21:51+09:00`, before this zero-fit replay.

## Purpose and honest prior

The current K=45 strategy is not executable as previously reported because it
allows up to four overlapping positions. A post-hoc independent-book filter
puts the full-span primary result at `-0.356` net bps over 3,078 trades and the
2022 primary result at `-4.504` bps while the control is `+2.398` bps. The
strategy is under water before this change. The stop is risk control. It is not
expected or permitted to manufacture an edge.

This replay measures the interaction between a single-position constraint and
one pre-committed stop. It creates no new acceptance condition, model verdict,
or permission. The existing frozen acceptance conditions and their prior
`VALIDATION_FAIL` remain authoritative.

## Frozen sources and cutoff

Use only existing local Binance USD-M BTCUSDT artifacts:

- `artifacts/btcusdt_2020_2026h1.parquet`, SHA-256
  `6ad4dba7c55550e380426b4397b55dfbea3bcb318e37632971d82cad8cf6ada4`;
- `out/patchtst_backward_k45_validation_20260929/k45_ledger.parquet`, SHA-256
  `584d31ae426d0082bcadbcaee8b54c41268c28a8cae5d9e545d21541470d2b47`;
- `out/patchtst_fixed_trigger_hold_sweep_20260929/fixed_hold_ledger.parquet`,
  SHA-256
  `1233c83c1f294088cbcd86d47b592208ff254c295bd290ffb045fb297e3dcb4b`.

Data cutoff is `2026-06-30T23:59:00Z`. Use folds 0--666. No new external
data, model fit, checkpoint load, authenticated exchange action, or live order
is allowed. Frozen counters are `new_model_fits: 0` and `new_orders: 0`.

## Frozen arms and books

Keep the existing directional arms:

- primary: `DOWN_BREAKOUT_LONG`;
- negative control: `UP_BREAKOUT_SHORT`.

Each directional arm gets its own single-position book. The primary and
negative control do not compete for one slot. This preserves the control as a
counterfactual evaluation rather than making its result depend on primary-arm
signals. Sharing one slot is not evaluated.

Within each directional book, process signals by completed-close entry time.
Treat positions as half-open intervals `[entry_index, exit_index)`. Accept a
signal when `entry_index >= current_exit_index`; otherwise skip it immediately.
A skipped signal is never queued and never changes book state. Preserve its
hypothetical outcome for the skipped-signal report.

## Frozen execution variants

Evaluate exactly three variants. No sweep follows.

- `A_SINGLE_NO_STOP`: one position per directional book, 45-minute time exit.
- `B_SINGLE_STOP_50`: one position per directional book, 50 bps stop plus the
  same 45-minute time exit.
- `C_CONCURRENT_NO_STOP`: all overlapping signals, 45-minute time exit. This is
  the old non-executable baseline and reference only.

Entry remains the observed completed close at `entry_index`. The time exit is
the close at `entry_index + 45`.

## Frozen stop and fill convention

Fix the only stop at 50 bps against entry, by symmetry with the frozen 50 bps
breakout trigger. For entry price `p`:

```text
long stop level  = p * (1 - 50 / 1e4)
short stop level = p * (1 + 50 / 1e4)
```

The entry occurs at a completed close, so the entry bar's earlier high/low is
not eligible. Inspect one-minute bars `entry_index + 1` through
`entry_index + 45`, inclusive. A long stops when `low <= long stop level`; a
short stops when `high >= short stop level`. Use the first eligible stop bar.

Assume fill exactly at the stop level. Do not model gap-through, extra
slippage, spread, or partial fill. This is optimistic: when a bar opens or
trades through the level before execution, realizable loss can exceed the
reported stop loss. Gross bps remains the existing signed log return from
entry to fill, so the price-symmetric thresholds need not equal exactly
`-50.0000` log bps. Subtract 4 bps round trip once for both stop and time exits.

The stop scan includes the 45-minute exit bar. If that bar's extreme crosses
the stop, the stop takes precedence over its close. A stop exit at minute `m`
frees the half-open slot for a new completed-close entry at minute `m`.

## Frozen reports and inference

Report folds 0--405, 406--605, and 606--666 separately and pooled. For each
execution variant and directional arm, report candidate signals, executed
trades, skipped signals, stop exits, mean gross and net bps, total PnL using
fixed $100 notional per trade, and a two-sided 95% CR1 interval for mean net
bps clustered by TEST fold. Also report each UTC calendar year with the same
return units and CR1 interval.

For skipped signals, report count and their hypothetical mean gross and net
bps, total fixed-$100 PnL, and fold-CR1 interval under that variant's own exit
rule. These outcomes are diagnostics only.

For every variant, directional arm, and span including pooled, report maximum
drawdown in cumulative bps and dollars. Order realized PnL by exit minute,
aggregate ties at the same minute, start equity at zero, and measure the
largest peak-to-trough decline. The drawdown is closed-trade fixed-notional
drawdown. It does not include intratrade mark-to-market, shared capital,
margin, leverage, compounding, funding, or liquidation.

CR1 uses intercept-only OLS, fold clusters, correction `G/(G-1)`, and a
two-sided Student-t critical value with `G-1` degrees of freedom. Pooled and
calendar-year views are descriptive dependent views, not new holdouts.

## Reproducibility and safety

Write only to `out/patchtst_single_position_stop_20260929/`. Freeze a manifest
covering this plan and hash, runner, tests, market data, input ledgers, their
upstream hash indexes, and upstream status/verification records. Write an
output SHA-256 index.

`--verify` must validate all hashes, rebuild both books, stop outcomes,
statistics, drawdowns, tables, and report, compare them with stored outputs,
perform zero fits, and print peak process RSS. Abort above 3 GiB. No result
changes the existing acceptance verdict.
