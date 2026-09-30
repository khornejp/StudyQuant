# docs/

Where the project's markdown lives, and why some of it does not live here.

Reorganized 2026-09-22. 101 files moved out of the repository root; 81 stayed.

| Folder | Holds |
| --- | --- |
| `docs/plans/` | Experiment plans and preregistrations no longer referenced by code |
| `docs/reports/` | Results, audits, diagnostics, source reviews, research summaries |
| `docs/sessions/` | Session states, handoffs and TODO lists |
| `docs/archive/` | Everything older that fits none of the above |

## Why 74 plan files are still in the repository root

A frozen runner writes its plan's **path string** into `manifest.json` as a key
and asserts that file's SHA-256 on every `--verify` run:

```python
PLAN = Path("PATCHTST_DIRECTION_CLASSWISE_SELECTIVE_CONTINUOUS_200_PLAN_2026-09-19.md")
manifest = {"source_sha256": {..., str(PLAN): base.old.sha(PLAN), ...}}
```

Moving such a file makes that experiment unverifiable, and the frozen runners
must not be edited to fix it — a correction needs a new wrapper and a new output
directory. So any `.md` whose name appears inside a `.py` stays exactly where it
is. The tidy pass detects this automatically rather than relying on a hand-kept
list.

Also kept at the root, because they are the entry points a new session reads
first: `README.md`, `README_FULL.md`, `AGENTS.md`, the current
`SESSION_STATE_*`, `REVIEW_HANDOFF_*`, and the two most recent reports.

## Known cost of the move

Older session states and handoffs refer to other documents by bare filename.
Those references now point one directory up from where the file sits. Nothing in
code depends on them, and rewriting the prose of frozen session records would be
worse than the broken link.
