# R2-54 Task 4 report: Stage-B validation selection

Status: **DONE_WITH_CONCERNS.**
- Validation selection ran in full. Long passes every validation gate. Short fails the economic gate.
- The final test stays **LOCKED**. Unlock was not run, and no 2026 labels, outcomes or market rows were read; only snapshot file hashes were checked.
- Base 324a56e. The freeze was not edited: sha256 `710cb08b…`, verified on load.

## Code
- `btcusdt_quant/stageb.py` (new library), covering:
  - labels g_H; purge, embargo and block membership; N_eff;
  - V1–V4 feature builder with per-row max logical_available_at;
  - isolation checks;
  - Ridge (closed form, train-only scaling and imputation) and CatBoost, with deterministic checkpoints;
  - position rule to signal table, and the fold ledger through `sim_adaptive_exit.run_ax` (R2_52A core);
  - ranking with the 1e-12 tie rule, eligibility, validation gates and v6 gates;
  - circular block bootstrap, Holm, weekly Thursday schedule and fallback rule;
  - snapshot settlement rounding, and the ledger funding override for the test.
- Reused: `rl.state` (s4_indicators, side_channels, oco_channels), `strategies.build_variant` and `grid_plan`, `regime`, `sim_adaptive_exit` (run_ax, e_series, e_at, plan2.input_hashes), and `costs.funding_events`.
- `out/run_r2_54_stageb.py` (force-added). Commands: `run`, `dry-run`, `unlock-test`.
- Tests:
  - `tests/test_r2_54_stageb.py` (24) and `tests/test_r2_54_stageb_runner.py` (3), written first.
  - They cover:
    - causality: avail ≤ T, truncated-context equality, and the label-copy catch;
    - purge and embargo, block membership and N_eff;
    - label isolation and train-only scaling;
    - the position rule and NO_ENTRY_E;
    - ledger parity: `fold_ledger` == `validation_pnl`, and core trades == `reference.simulate`;
    - ranking ties and the frozen priorities, with no runner-up promotion;
    - gates, bootstrap, Holm, the schedule and fallback;
    - unlock refusals, and the snapshot merge on synthetic frames.

## Run
- Data gates pass:
  - 1 m bars are gap-free;
  - 0 feature rows have availability > T;
  - 0 split-crossing labels;
  - Stage-A is missing only the known days 2023-12-31 and 2025-12-31, with 0 retrain-after-timestamp rows.
- Real-data truncation causality: 2 cuts, rows identical.
- Features: 134,592 rows × 475 columns.
  - V5 has 322 columns; V6 adds 154 technique columns.
  - There are 3,183 missing 5 m metric periods before 2026. They are masked, not filled.
- Every structure × k × side ran through the full minute ledger on all 10 folds: 4,800 runs at 4 and 8 bps. All 120 rows per side are eligible.
- Trials: registry 5417 → **5544** (+120 selectable, +7 robustness), registered once.
- Runtime: 1,459 s (fits 10 min, ledgers 3 min, robustness 10 min). The dry run took about 1 min.

| side | selected (view, H, model, k) | pooled 4 bps | pooled 8 bps | median IC | IC>0 folds | net4>0 folds | positions | M / L bucket IC | result |
|---|---|---|---|---|---|---|---|---|---|
| long | V5_continuous, 4h, CatBoost, 2.0 | +8,741 | +3,025 | 0.0225 | 7/10 | 7/10 | 1,427 | .017/.011/.030 ; .011/.026/.019 | **PASS** |
| short | V5_continuous, 4h, CatBoost, 2.0 | +5,251 | **−785** | 0.0225 | 7/10 | 7/10 | 1,507 | same | **FAIL (economic: 8 bps < 0)** |

- Both sides selected V5, so the V6 robustness run is diagnostic only.
  - Long V6 finalist (24h, CatBoost, k 2): top-id removal (K30) keeps 49% of IC. That fails, but it does not affect the V5 primary.
  - Short V6 finalist (12h, CatBoost, k 2): passes, with 5/6 families and 92% retained.
- Final fit: long only, on all pre-test data (labels exit < 2026-01-01).
  - Checkpoint `out/k45_rl_r2_48_20261007/r2_54/stageb/final/final_long_V5_continuous_4h_catboost.bin`, sha `521aae3b…`.
- Manifest `out/k45_rl_r2_48_20261007/r2_54/stageb/manifest.json` (sha f3ef6c36…) records:
  - the freeze, snapshot (b748d364…, every artifact re-hashed) and git hashes;
  - the hypotheses and registry;
  - all 120 rows per side;
  - the ranking trace (`validation/ranking_trace.json`, d1534eaf…);
  - the gates, bias controls and 7 removals;
  - Stage-A ids and hashes;
  - the bootstrap plan and the contamination note.
- Dry run (`dry-run`): the replay code ran on the already-seen window 2025-09..12. It produced 14 checkpoints per side with 0 fallbacks, every train cutoff before its retrain, and 0 NO_ENTRY_E rows. It is a code check only.

## Unlock (not run)
`venv_btcusdt\Scripts\python.exe out\run_r2_54_stageb.py unlock-test --confirm R2-54-STAGEB-ONE-SHOT`
- It refuses unless the freeze, snapshot, trace, final checkpoint and registry hashes all verify and no unlock is recorded yet. Right now only the confirmation is missing.
- It records the unlock UTC and process identity before reading any 2026 data.
- It then:
  1. checks taker is archive-only on the rows;
  2. checks the pre-2026 feature rows are identical (aborts otherwise);
  3. runs the long side only: weekly retrain replay, 4/8 bps ledgers with data-end close reported separately, bootstrap 10000 / 672 / 20261008, Holm with short counted as p=1;
  4. freezes the primary result;
  5. runs the oracles and the A3 archive-vs-REST taker diagnostic.

## Concerns
1. This venv's numpy has no BLAS: a 120k×475 Gram matrix takes about 6 min.
   - Ridge now uses scipy BLAS normal equations. It matches sklearn to 2e-17.
   - A first run that used sklearn was killed. Its caches were deleted and it was never registered.
2. Short fails only on the 8 bps stress. Long passes at the 7/10 threshold on both IC and net4 folds.
3. The unlock path itself is untested on real 2026 data:
   - snapshot merge: unit-tested;
   - replay: dry-run only;
   - refit check, oracles and taker diagnostic: never executed.
   A bug there would show up after the one-shot unlock is recorded.
4. October funding: snapshot `funding_live_table` rates feed the ledger, rounded to the 8 h schedule. Their interval stays masked in the features.
5. The A3 REST taker diagnostic places rows at period end; staging `received_at` is after the window.
6. Interpretation choices:
   - Embargo applies to every fold/test boundary for training rows as well.
   - Stability buckets use per-fold train terciles, pooled across folds.
   - "Sparse" means fewer than 100 events.
   - Unopened sides count as p=1 in Holm.
7. `out/` is gitignored, so only the scripts, manifest, trace, CSV and final checkpoint are force-added. Fold artifacts (481 MB) are hashed in the manifest but not committed.

## Fix round 1 (Codex pre-unlock review: safe to unlock NO)

All 8 items are fixed with tests written first. Unlock was not run, and the test stays LOCKED.

1. **BLOCKER** `unlock_preconditions` now refuses unless `code_hashes()` equals the manifest `code_sha256` exactly.
2. **BLOCKER** Unlock order:
   1. preconditions;
   2. `verify_snapshot(read_frames=False)`;
   3. refit check;
   4. only then the one-shot flag;
   5. after the flag, the taker row check and any 2026 read.

   A test confirms that a snapshot or refit failure leaves the manifest byte-unchanged and reads no 2026 data.
3. **BLOCKER** `refit_check` refits each opened side on the pre-2026 artifacts before any 2026 access. A hash mismatch refuses the unlock. The replay only loads the hash-verified committed checkpoint.
4. **BLOCKER** Funding:
   - `stageb.settlements` keeps the actual fundingTime (no 8 h rounding).
   - `simulator_minutes` buckets events to their minute only inside the ledger override.
   - Validation ledgers now use these actual events as well.
   - Validation was rerun; see the old vs new table below.
5. **HIGH** `stageb.weekly_predictions`: on a retrain failure, the previous checkpoint serves only decisions before active_retrain + 7 d. Later decisions get NaN, which blocks new entries and model exits; R2-52A stops keep running. Tests cover a fallback week and a hard failure.
6. **MEDIUM** The A3 diagnostic is now the identical continuous replay:
   - it reuses the same hash-verified checkpoints, rule, k and ledger;
   - archive taker vs REST taker for 10-01..10-07, with missing REST periods left missing;
   - it records actual matched and unmatched entry times and exit differences.
7. **MEDIUM** V4 availability (technique row decision_time, K10 plan time) now feeds `seen()` and the causality gate. The gate passes, and the feature frame is unchanged (sha `204014f0…`).
8. **MEDIUM** The manifest `sources.pre_2026` now holds data.binance.vision URLs and the local files used, with retrieval timestamps. The timestamps are file mtimes, since no download log exists; this is noted in the manifest.

### Validation: old vs new
- The minute floor of the actual fundingTime equals the 8 h-rounded time for all 7,119 pre-2026 and 819 2026 events, so the ledgers are bit-identical.
- Across all 240 rows, the max diff is 0 for net4, net8, median IC, completed and folds_valid, and every fold list is equal.
- Gates, robustness, ranking trace (`d1534eaf…`) and final checkpoint (`521aae3b…`) are all unchanged.

| side | selection old = new | net4 | net8 | gates |
|---|---|---|---|---|
| long | V5_continuous, 4h, CatBoost, 2.0 | 8,741 = 8,741 | 3,025 = 3,025 | PASS = PASS |
| short | V5_continuous, 4h, CatBoost, 2.0 | 5,251 = 5,251 | −785 = −785 | FAIL (economic) = FAIL |

- Fold fits were reused, guarded by the identical feature-frame hash (marker `folds/_features_frame_sha256.txt`).
- Registry: no new rows. It stays at 5544, and the manifest has a `validation_rerun` note.
- Round-0 files kept: `manifest_round0.json` (sha `f3ef6c36…`) and `validation/candidates_round0.csv`.
- New manifest sha: `c01c7601b6195e4de9cbab8ee4eae0677e99fb9a720d17fad2d3785b82104df8`. Rerun runtime: 327 s.
- The dry run passes again: 14 checkpoints per side, 0 fallbacks, 0 blocked decisions.
- `unlock-test` without `--confirm` refuses with only "confirmation missing", so the code hash matches.
- Tests: 34 new. Full suite (sim + paper + r2_54 + rl state): 931 passed, 2 skipped.
