# BTCUSDT Paper Trading System — Design

Date: 2026-10-06. Status: approved by user in chat ("sqlite로 진행해. 설계 문서 쓰고 구현 시작해").

## 1. Goal

Run the research strategies on live public Binance USD-M BTCUSDT data, minute by minute, as paper (simulated) single-position books. Show positions, signals, trades and P&L on a local web dashboard. Keep a switch so a later live-order mode can be added without restructuring. No live orders now.

## 2. Boundaries

- AGENTS.md still applies: no live orders, no wallet, no authenticated exchange calls. Market data comes only from public, unauthenticated endpoints.
- API key slot exists (`.env`, gitignored) so the user can switch later. In `paper` mode the key is never sent anywhere. The key is never logged or displayed except masked (`abcd...wxyz`).
- Strategy definitions are frozen exactly as in research (R2-14, R2-17, R2-24). No parameter changes. Paper results must equal a research-code recomputation over the same minutes.
- Single position per book. Books are never summed. Cost 4 bps round trip (2 + 2). Funding from settled rates; PESS and OPT boundary variants as in `out/k45_funding.py`.

## 3. Strategies (books)

Each book is one single-position ledger. Config selects which books run and which one is "primary".

| Book | Definition | Source |
|---|---|---|
| C1 (primary) | F3\|1h\|10/24\|signal\|LS + E1\|1h\|3\|signal\|L, FIRST, priority F3 > E1 | R2-24 `manifest_frozen.json` |
| F3 | F3\|1h\|10/24\|signal\|LS alone | R2-14 |
| E1 | E1\|1h\|3\|signal\|L alone | R2-14 |
| C4 | F3_global_ls_account\|1h\|w30\|q20\|h12\|LS + E1, FIRST, priority F3-w30 > E1 | R2-17, R2-24 |

C3 (model legs R2-9b/R2-20/PatchTST) is out of scope for v1: it needs 3-day GPU retraining and depth/trade streams. The design leaves a strategy interface so it can be added later.

Rules (from research, must be reproduced exactly):
- F3: 1h decision; `global_ls_account` value strictly before decision time; rolling 2,160 1h bars, min 720, current observation included, q .10/.90, contrarian; max hold 24 1h bars.
- F3-w30: rolling 720 bars, min 720, q .20/.80, max hold 12 bars.
- E1: closed 1h bar volume z-score over 20 bars (ddof=0, current bar included) > 3 and close > `high_20.shift(1)`; long only; max hold 20 bars.
- Entry at the next 1m open after the decision. 1h bars are aggregated from 1m bars exactly as research did.
- FIRST: while a position is open every new signal is dropped; `exit_time <= new entry_time` counts as already closed; same-minute conflicts resolved by priority.

## 4. Architecture

```
btcusdt_quant/paper/
  rules.py       # F3, F3-w30, E1 signal functions ported from out/ research code
  book.py        # single-position FIRST book, MTM ledger, cost, funding (PESS/OPT)
  store.py       # SQLite schema, WAL, read/write helpers, daily parquet export
  collector.py   # 1m klines (WS + REST gap fill), premium 1m, LS ratio 5m, funding
  engine.py      # on each closed minute: update bars, evaluate signals at 1h closes, update books
  reconcile.py   # next-day archive vs live comparison, research recomputation parity
  config.py      # YAML/TOML config + .env loading, mode paper|live
  broker.py      # Broker protocol: PaperBroker (implemented), LiveBroker (stub raising NotImplementedError)
  dashboard/     # stdlib http.server JSON API + one static HTML page using bundled plotly.min.js
scripts/
  paper_backfill.py   # seed history from local research data + Q3 archive + REST
  paper_run.py        # collector + engine loop
  paper_dashboard.py  # serve dashboard on 127.0.0.1
```

Reuse before writing: `btcusdt_quant/secrets.py` (credentials, masking), `btcusdt_quant/exchange.py` (`ExchangeAdapter` protocol, `MockExchangeAdapter`), `out/k45_funding.py`, `out/k45_ledger.py`, `out/run_k45_classic_rules_r2_14.py`, `out/run_k45_contrarian_robust_r2_17.py`, `out/run_k45_single_book_combo_r2_24.py`. Ported code must be behaviour-identical (proved by tests in §8).

No new dependencies unless unavoidable. Available: requests, httpx, websocket-client, plotly, pandas, pyarrow. Dashboard uses stdlib `http.server`; plotly.js comes from the installed plotly package (no CDN).

## 5. Data collection (every minute)

| Data | Endpoint (public) | Cadence |
|---|---|---|
| 1m klines | WS `btcusdt@kline_1m` (closed bars only), REST `/fapi/v1/klines` gap fill each minute | 1m |
| Premium index 1m | REST `/fapi/v1/premiumIndexKlines` | 1m |
| Global LS account ratio | REST `/futures/data/globalLongShortAccountRatio` period 5m | 5m (finest available) |
| Funding settlements | REST `/fapi/v1/fundingRate` | after each 00/08/16 UTC settlement |

- Only closed bars are stored and used for signals. In-progress bar is display only.
- Each row stores `source` (ws/rest/archive) and `received_at` (UTC) for latency.
- On restart: REST backfill from last stored minute. Gaps are recorded, never interpolated.
- Funding timestamps normalized to the nearest scheduled 00/08/16 UTC (|diff| ≤ 60 s, else error), raw time preserved — same rule as R2-32.
- LS ratio: store exchange timestamp; F3 uses only values with timestamp strictly before decision time.
- Rate limits respected; backoff on 429/418 using existing `RateLimitManager` in `btcusdt_quant/live.py` if suitable.

## 6. Storage

```
artifacts/live/
  live.sqlite                 # WAL mode; collector writes, dashboard reads
  raw/YYYY-MM-DD.jsonl.gz     # raw API responses (audit)
  daily/klines_1m/YYYY-MM-DD.parquet, premium_1m/..., ls_ratio_5m/..., funding/YYYY-MM.parquet
  ledger/<book>_trades.parquet, <book>_daily.parquet
```

SQLite tables: `klines_1m`, `premium_1m`, `ls_ratio`, `funding`, `signals` (incl. dropped and reason), `positions`, `trades`, `daily_pnl`, `collector_health` (per-minute lag, gaps, retries), `revisions` (archive vs live differences; originals never overwritten), `meta` (schema version, config hash, code hash).

Daily parquet export after UTC midnight uses the research column schema so research code can recompute.

## 7. Engine and books

- Initial history: local research data (≤ 2026-06-30) + `artifacts/hold_a_2026q3` (≤ 2026-09-30) + REST to now, so F3's 90-day window and E1's 20 bars are warm at start. Books start flat at the configured start time; no back-dated paper trades.
- On each closed minute: append bar; at 1h boundaries compute signals; apply FIRST per book; open at next 1m open; close at max hold; MTM every minute; apply funding at settlements; write state transactionally so a crash never leaves a half-updated book.
- Each book records gross, cost, funding, net in bps, for PESS and OPT.
- `mode: paper` uses `PaperBroker`. `mode: live` must fail closed with a clear message until AGENTS.md is changed and LiveBroker is implemented.

## 8. Verification

- Port parity: ported rules/book reproduce R2-23 trades for F3, E1, F3-w30 and R2-24 accepted trades for C1, C4, plus R2-32 HOLD_A trades for H1/H2/H3/H5, exact (max abs diff 0).
- Replay test: feed stored 1m history through the live engine minute by minute (simulated clock) over 2026-07-01..09-30; trades must equal R2-32 HOLD_A books exactly. This proves the incremental engine equals the batch research code.
- Daily reconcile: after archive files appear, recompute the previous day with research code on archive data; report kline differences, signal differences, and ledger differences in the dashboard.
- Unit tests with synthetic data: gap handling, restart resume, closed-bar-only rule, LS strict-prior, funding normalization, FIRST conflicts, max-hold exit, credential masking, live mode fail-closed.

## 9. Dashboard (127.0.0.1 only, auto refresh 60 s)

- Books tab per strategy: current position (entry, price, unrealized, remaining max hold, next funding), trades table (entry/exit time, side, prices, hold, signal source, gross, cost, funding, net PESS/OPT, exit reason; filter, sort, CSV download), signals log incl. dropped signals and reason.
- Charts: cumulative net vs buy-and-hold, monthly P&L, drawdown, price chart with entry/exit markers.
- Research reference: DEV_COMMON / HOLD_B / HOLD_A metrics for each book side by side with live paper metrics.
- Health: collector lag, gaps, last update per source, archive reconcile status, disk free (warn < 10%), mode (paper/live), credential loaded (masked).

## 10. Configuration

`config/paper.toml` (committed, no secrets): books, primary book, start time, cost, data paths, dashboard port. `.env` (gitignored): `BINANCE_API_KEY`, `BINANCE_API_SECRET`.

## 11. Out of scope (v1)

Live orders, C3 model legs (deferred; see `docs/paper_system/deferred_model_strategies.md`), multi-symbol.

## 12. Telegram notifications (added 2026-10-06, user approved)

- `.env` keys: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Missing keys disable notifications only; collector and books keep running. Token masked everywhere, never logged.
- Events: entry (book, side, entry price, signal source, scheduled max-hold exit), exit (exit price, hold, reason, gross/cost/funding/net PESS, book cumulative net), dropped signals (off by default, config switch), daily summary at UTC 00:00 (per-book day and cumulative net, trade count, vs buy-and-hold), alerts (collector lag/gap threshold, engine error, reconcile mismatch, disk free < 10%).
- Delivery: `requests` to Telegram Bot API `sendMessage`. Outbox table in SQLite (`notifications`: id, event key, payload, status, attempts, sent_at). Idempotent by event key (no duplicates after restart). Retry with backoff. Send failures never block the engine.
- Config switches per event type in `config/paper.toml`.

## 13. bookTicker recording (added 2026-10-06, user approved: record only)

- Subscribe WS `btcusdt@bookTicker` (public). Aggregate per UTC minute with exactly the `out/build_spread_features.py` definitions (reuse `reduce_chunk` logic): `spread_bps_mean`, `spread_bps_max`, `spread_bps_std`, `top_imbalance_mean`, `quote_update_count`, `spread_valid`; minute keyed by exchange transaction time.
- Store in SQLite table `book_ticker_1m` and daily parquet `artifacts/live/daily/book_ticker_1m/`. No raw tick storage by default (config switch, off).
- Not used by any strategy, signal, or dashboard decision. Shown only in the health tab (row count, gaps, last update). A stream failure must never stop klines collection or books.

## 14. Isolated 3x reference books (added 2026-10-06)

- Each configured 1x book has a separate `<book>_x3` simulation with a $100 initial budget,
  3x isolated leverage, 0.4% maintenance margin, and PESS funding only.
- The overlay consumes the accepted 1x trades; it never creates a signal or changes the 1x
  `positions`, `trades`, `daily_pnl`, parity result, or promotion decision.
- Every entry uses the full current balance as margin and three times that amount as notional.
  Normal exits use the 1x timestamp and price. Round-trip fees are 4 bps of notional.
- Each held minute checks the adverse extreme (long low, short high). Equality with maintenance
  margin liquidates. The liquidation minute uses the theoretical threshold price and writes the
  entire margin off; later accepted trades are recorded as skipped.
- Leverage state, open position, trades, daily balances, and skips live in separate
  `leverage_*` SQLite tables and are replaced atomically with the base replay publication.
- These books are risk/reference displays only. The frozen 1x books remain the sole promotion
  evidence.
