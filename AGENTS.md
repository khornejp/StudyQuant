# Response style

- Caveman always on: answer in Korean, short and direct. Lead with result. Keep necessary evidence and risk warnings; cut filler.
- Caveman applies to all input and output, every turn, no exceptions: user replies, status lines, and prompts/briefs sent to subagents and Codex. Korean replies use fragments, not polite full sentences (no "~입니다" chains). Reporting every result unfiltered is not an excuse for length: give all numbers and verdicts, cut the prose.
- Use the installed CLI `caveman` skill at full level for this workspace. A `Caveman Mode` widget picker is a different plugin and does not activate the CLI skill.

# Research boundary

- This project tests Binance USD-M BTCUSDT futures direction: short first, long separately. No live orders, wallet setup, payments, or authenticated exchange actions.
- External skills are research aids, not evidence of predictive improvement. Do not mix spot or DEX data into futures experiments without an explicit, causally valid plan.
- Record source, timestamp, data cutoff, frozen hypothesis, and out-of-sample result for each experiment. Prefer existing local data before collecting more.
- Test with existing data. Do not label data as "contaminated" or add contamination notes because an earlier experiment used the same window; do not wait for future data to test.
