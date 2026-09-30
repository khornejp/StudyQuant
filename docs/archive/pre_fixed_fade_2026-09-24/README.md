# Pre-"fixed fade" archive, 2026-09-24

Everything in this folder predates the fixed-fade meta-policy work. It was moved
out of the repository root to leave a clean slate, not deleted: several of these
plans are the preregistration for runs whose numbers are still quoted.

## What stayed at the root, and why

A frozen runner writes the SHA-256 of its plan file **by path** into its
manifest, so moving that file breaks its `--verify`. These three runs are still
live, so their plans stayed:

- `PATCHTST_PAYOFF_LADDER_2026-09-23.md` — C0/C1/C3. C0 is the trunk of the
  current design and its checkpoints are reused.
- `PATCHTST_RESIDUAL_PILOT_2026-09-24.md` — R0/R1, and it re-checks the
  ladder manifest's own hashes.
- `PATCHTST_C0_SEQUENTIAL_REPLAY_2026-09-24.md` — the next-open ledger, which
  also re-checks the ladder manifest.
- `PATCHTST_MOVE_TARGET_LADDER_2026-09-23.md` — the B-series, whose module the
  payoff ladder imports.

## What moving the rest costs

The 52 plans here belong to runs from 2026-09-08 to 2026-09-22 (the TRANSFORMER,
SHORT and PATCHTST_DIRECTION families). Their runners hash these paths, so
`--verify` on those older artifacts will now fail on a missing file. Their
recorded results are unaffected; only the reconstruction check is. Nothing in
the current design depends on them.

To restore one, move it back to the repository root under its original name.
