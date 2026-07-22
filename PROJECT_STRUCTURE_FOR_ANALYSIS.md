# BTCUSDT 1분봉 퀀트 시스템 — 외부 분석 요청용 구조 문서

작성 기준: `run_full_pipeline.ps1` (커밋 `f9017a5`, 2026-07-22 갱신; 초판 `76af491`)
목적: **현재 엣지를 확보하지 못한 상태**의 원인 진단을 위한 구조 공개.

> **갱신 이력 (f9017a5)**: 초판이 ⚠️로 지적한 4개 항목이 수정됨 — ① Optuna/임계값 홀드아웃
> 겹침(§6.2), ② F12 오프라인 mock 학습(§3.3), ③ shuffled-label 대조군 미배선(§11c → Phase
> 3.8/4.7 신설), ④ range 게이트 A/B 플래그(§6.1). 본문에 [수정됨] 표기.

---

## 0. 한눈에 보기

| 항목 | 값 |
|---|---|
| 심볼 / 바 | BTCUSDT USD-M 선물, 1분봉 단일 심볼 |
| 원천 | `data.binance.vision` 일별 아카이브 (klines + metrics) |
| 전체 스팬 | 2020-01-01 ~ 2025-12-31 (약 3.15M 봉) |
| 학습 구간 | 2020-01-01 ~ 2024-12-31 (단, 워밍업으로 실질 시작 **2020-12-16**, 아래 §1 참조) |
| 백테스트 구간 | 2025-01-01 ~ 2025-12-31 (풀이어 out-of-sample, 단일 구간) |
| 등록 피처 | **196개** (모델 투입 **180개**, 비활성 16개) |
| 타겟 | 트리플 배리어 이진 분류 (TP 1.00% / SL 0.50% / 60바 타임아웃) |
| 모델 | CatBoost 이진 분류, 레짐×사이드별 독립 모델 (최대 4개) |
| 레짐 | 규칙 기반 3분류 (up / down / range), 인과적 |
| 사이징 | Half-Kelly (f* = 0.5·edge/variance), position_size가 상한 |
| 비용 | 편도 fee 0.02% + slippage 0.02% → 왕복 **0.08%** |

### 알려진 증상 (엣지 부재의 핵심 데이터포인트)

> ⚠️ **낡은 수치 주의**: "평균 예측 확률 0.522 vs 실현 승률 32.3%"는 **과거 계측 버그 시기의
> 기록**이다 (`calibration.py` docstring에 역사적 사례로 남아 있음). 배리어 패리티·지표 수정
> 이후의 최신 완주 런(2026-07-21)에서는 **캘리브레이션이 정직하다** — 이 낡은 수치를 전제로
> "캘리브레이션 붕괴"를 진단하면 틀린다 (실제로 한 외부 분석이 이 함정에 빠졌음).

최신 완주 런 (2025 full-year OOS, 커밋 76af491 코드):

- 캘리브레이션 **정직**: 전 레짐/사이드 ECE < 0.03 (모델이 5%라고 하면 실제 ~5% 발생)
- 확률 분포가 **극도로 낮게 압축** (up/long은 P≥0.3인 봉이 연중 0개)
- regime 백테스트: 97거래, 승률 39.2% (손익분기 38.7% 바로 위), gross +0.61% / **net −0.15%**
- 비용 스트레스: 기본비용 net +0.22%(고정사이즈) → **1.5배 비용에서 즉시 음전** (`survives_1_5x=False`)
- 4-way 라우팅: **oracle(사후 완벽 라우팅)조차 net 음수** → 디텍터가 아니라 라벨·피처·진입모델 문제
- `ic_report.csv`: 180개 중 49개가 |IC|≥0.03 (fold-stable, 누수 플래그 0) — 단, **전부 음의 IC**
  (추세·모멘텀 피처 ↔ 60분 순방향 수익률). 즉 **평균회귀 신호는 존재**하는데 라벨은
  +1.0%/−0.5%의 **추세추종형 배리어** — 신호와 타겟의 방향 불일치가 현재 1순위 가설.

---

## 1. Phase 1 / 1.5 / 2 — 데이터 수집 및 결합

### Phase 1: klines 아카이브
```
python -m btcusdt_quant collect-archive --start 2020-01-01 --end 2025-12-31
```
- 일별 zip → CSV. 헤더 유무 자동 감지, OHLCV 유효성 검증(양수/high≥low/open·close가 범위 내), `open_time` 중복 제거, 시간 순 강제.
- 체크포인트 재개 지원. HTTP 429 지수 백오프, **418은 즉시 중단**(재시도 없음).

### Phase 1.5: futures metrics 아카이브
```
python -m btcusdt_quant collect-metrics --start 2020-01-01 --end 2025-12-31
```
- 컬럼: `sum_open_interest`, `sum_open_interest_value`, `count_toptrader_long_short_ratio`, `sum_toptrader_long_short_ratio`, `count_long_short_ratio`, `sum_taker_long_short_vol_ratio`
- **5분 격자**. BTCUSDT metrics는 약 2020-09부터 존재 → 그 이전 구간은 F16 피처가 전부 0.
- 같은 `create_time` 중복 행은 마지막 값 채택(동일 타임스탬프이므로 look-ahead 없음).

### Phase 2: 단일 Parquet 결합
`dataset.load_archive_candles()` → `write_candles_parquet()`.

### 캐노니컬 타임라인 (`data.CanonicalTimelineBuilder`)
결측 분봉을 **직전 종가로 복구**(OHLC 전부 직전 close, volume=0)하고 다음을 부착:
`gap_flag`, `gap_length`, `gap_ratio_20/60/120`, `max_gap_run_120`, `repaired`

### ⚠️ 실질 학습 시작일

`dataset.build_dataset()`:
```python
WEEKLY_WARMUP_BARS = 50 * 7 * 24 * 60   # 504,000
if len(canonical) >= WEEKLY_WARMUP_BARS + 80:
    labeled_rows = [row for row in labeled_rows if row.index >= WEEKLY_WARMUP_BARS]
```
F13 주봉 피처가 MA50을 채우려면 **50주 완결 = 504,000분 = 350일**이 필요. 따라서:

> **`--training-start 2020-01-01`을 주더라도 라벨링된 학습 행은 실질적으로 2020-12-16부터 시작.**
> 명목 5년이 아니라 **약 4년치**가 실제 학습 데이터.

부수 효과: metrics 공백기(2020-01~2020-09)는 어차피 워밍업에 잘려나감.

---

## 2. 타겟(Target) 정의 — **분석 요청 항목 ①**

### 2.1 기본형: 트리플 배리어 (`dataset.triple_barrier_label*`)

t 시점 **종가**를 진입가로 삼고, t+1 ~ t+horizon 구간을 앞으로 스캔:

```
entry  = candles[t].close
tp     = entry * (1 + tp_pct)        # LONG
sl     = entry * (1 - sl_pct)
for k in t+1 .. t+horizon:
    tp_touched = candles[k].high >= tp
    sl_touched = candles[k].low  <= sl
```

| 상황 | 라벨 | reason |
|---|---|---|
| TP 먼저 터치 | 1 | `tp_first` |
| SL 먼저 터치 | 0 | `sl_first` |
| **같은 봉에서 둘 다 터치** | close>open이면 1, close<open이면 0, 같으면 0 | `tp_first`/`sl_first`/`ambiguous_path` |
| horizon 내 미터치 | `target_return > label_threshold` 여부 | `timeout_no_tp` |
| 갭 봉이 관여 | 위와 동일하되 reason에 표기 | `gap_cross_sl` / `gap_cross_timeout` |

동일봉 동시 터치의 tie-break 규칙은 **백테스트 실행부(`backtest.run_backtest`)와 문자 그대로 동일**하게 구현되어 있음 (라벨은 TP우선, 실행은 SL우선 같은 낙관 편향 방지).

### 2.2 실제 사용 타겟: 사이드별 타겟

각 행은 4개 타겟을 함께 보유 (`LabeledRow.targets`):

| 키 | 정의 |
|---|---|
| `direction` | `future_close(t+h) > close(t)` 단순 부호 |
| `profitability` | 위 트리플 배리어 (롱 기준) |
| **`long_success`** | 롱 진입 시 +tp가 -sl보다 먼저 오는가 |
| **`short_success`** | 숏 진입 시 **-tp**(가격 하락)가 **+sl**(가격 상승)보다 먼저 오는가 |

**배포 모델이 학습하는 것은 `long_success` / `short_success`.**
`profitability`는 레거시 호환 및 비레짐 단일 모델(Phase 3.7)에서만 사용.

> 설계 근거(코드 주석): `1 - P(long_success) ≠ P(short_success)`. 타임아웃으로 끝난 롱은 숏의 승리가 아님. 실측으로 두 확률의 합이 1이 아님이 테스트에 고정되어 있음(`test_short_target_is_not_the_complement_of_long`).

### 2.3 배리어 기하 (파이프라인 기본값)

```powershell
$Horizon    = 60        # 바(=분)
$LabelTpPct = "0.010"   # 1.00%
$LabelSlPct = "0.005"   # 0.50%
```

`dataset.py` 상단에 선택 근거가 기록되어 있음:

| 배리어 | 명목 R:R | 왕복 0.08% 반영 후 | 손익분기 승률 |
|---|---|---|---|
| TP 0.30% / SL 0.15% (구버전) | 2.00 : 1 | +0.22% / −0.23% = **0.96 : 1** | **51.1%** |
| TP 1.00% / SL 0.50% (현재) | 2.00 : 1 | +0.92% / −0.58% = **1.59 : 1** | **38.7%** |

구버전은 손익분기 51.1%가 모델 성능을 초과 → 모든 백테스트가 손실. 그래서 배리어를 확대함.

### 2.4 ⚠️ 거래 비용이 라벨에 들어가는가 → **아니오**

**라벨 자체는 비용을 반영하지 않은 순수 가격 사건.** 비용은 세 지점에서 따로 들어감:

1. **임계값 선택** — `training.select_threshold(objective="trading_pnl")` 가 `_trading_pnl()`로 시뮬레이션:
   ```python
   win  = tp_pct - round_trip_cost   # 0.010 - 0.0008 = +0.0092
   loss = -sl_pct - round_trip_cost  # -0.005 - 0.0008 = -0.0058
   # 임계값 미만이면 PnL 0 (무거래)
   ```
   calmar → sharpe → f1 → |t−0.5| 순 정렬로 후보 선택. 최소 거래수 = `max(1, 5% of rows)`.
2. **Kelly edge** — `risk.expected_edge(p, tp, sl, round_trip_cost)` 가 net 기준. 비용 차감 후 기대값이 ≤0이면 진입 자체를 스킵.
3. **백테스트 실행** — `_close_trade()`가 편도 fee×2 + slippage×2를 매 거래 차감.

> **분석 시 유의**: 모델은 "비용 없는 가격 사건"을 학습하고, 비용은 임계값·사이징·집계 단계에서만 반영됨. 라벨 단계에서 비용을 반영하지 않은 것이 확률 왜곡의 원인인지 검토 필요.

### 2.5 라벨 산출 구간 무결성

- `attach_labels`는 `row.index + horizon >= len(candles)`인 행을 **버림** (미래 데이터 없는 꼬리).
- `FeatureRow.index`는 **전체 캔들 리스트의 인덱스**. 행을 슬라이스해도 캔들 리스트는 통째로 넘김. (슬라이스한 캔들을 같이 넘기면 라벨이 i0봉만큼 미래 가격을 읽게 되며, 이 함정은 `test_labels_use_full_candles_not_sliced`로 고정.)
- `--training-end 2024-12-31` 지정 시, 멀티호라이즌 경로는 `label_reach = max(max(horizons), threshold_horizon)`만큼 학습 구간 꼬리를 **추가로 잘라내어** 라벨이 2025년 캔들을 읽지 못하게 함.

---

## 3. 피처(Feature) — **분석 요청 항목 ②**

단일 진실원: `btcusdt_quant/feature_registry.py`. 각 피처는 `formula`, `lookback`, `min_samples`, `warmup_rule`, `dependencies`, `source`, `leakage_risk`, `scaffold_status`를 메타데이터로 보유.

### 3.1 카테고리별 개수

| 카테고리 | 그룹 | 등록 | **활성** | 원천 |
|---|---|---:|---:|---|
| F01 | price_return | 13 | 13 | klines |
| F02 | trend_ma | 14 | 14 | klines |
| F03 | volatility | 13 | 13 | klines |
| F04 | volume_trade_flow | 12 | 11 | klines |
| F05 | candle_structure | 10 | 10 | klines |
| F06 | gap_data_quality | 8 | 8 | klines(캐노니컬) |
| F07 | regime_normalization | 8 | 8 | klines |
| F08 | vol_adjusted_return | 6 | 6 | 파생 |
| F09 | vol_adjusted_trend | 4 | 4 | 파생 |
| F10 | vol_adjusted_candle_flow | 5 | 5 | 파생 |
| **F11** | microstructure (호가창) | 7 | **0** | depth_snapshot |
| F12 | exchange_funding_safety | 8 | 8 | funding/mark/ADL |
| F13 | higher_timeframe (주봉) | 7 | 7 | klines 리샘플 |
| F14 | time_session | 8 | 8 | open_time |
| F15 | momentum + range_mean_reversion | 25 | 17 | klines |
| F16 | derivatives_metrics | 11 | 11 | metrics 아카이브 |
| F17 | multi_timeframe (15m/1h/4h/24h) | 34 | 34 | klines 리샘플 |
| F18 | regime_probability | 3 | 3 | OOF 분류기 |
| **합계** | | **196** | **180** | |

### 3.2 비활성 16개와 그 이유

**(a) `pending_data_source` — F11 호가창 7개**
`spread`, `spread_bps`, `bid_ask_imbalance`, `best_bid_qty_ratio`, `best_ask_qty_ratio`, `microprice_deviation`, `order_book_pressure`

> Binance bookDepth 아카이브는 **%밴드 누적 깊이**이지 top-of-book이 아님 → 학습 시점에 재현 불가. 학습은 mock 상수, 라이브는 실제 값이 되는 train/live 갭이 발생하므로 아예 제외. 정의는 provenance 목적으로 남김.

**(b) `disabled_scale_dependent` — 절대 스케일 9개**
`rolling_vwap_20/60`, `range_high_20`, `range_low_20`, `range_mid_20`, `macd_line`, `macd_signal`, `macd_hist`, `quote_volume_per_trade`

> 2020~2025 BTC 가격이 7k → 100k. 절대 가격/달러 수준 값은 트리 모델이 **연도 프록시(era proxy)** 로 악용 가능("close 수준 → 어느 해인지" 암기). 달러 스케일 일부는 클리퍼의 ±100 ratio 경계에 상시 포화되어 고가 구간에서 정보가 소실되면서 시대만 흘림.
> **단, 내부적으로는 계속 계산되어 상대 피처의 입력으로 쓰임** (예: `range_high_20` → `range_position_20`, `distance_to_range_high`). 모델 투입 벡터에서만 제외.

### 3.3 주요 피처가 측정하려는 것

**F01 가격 수익률** — `return_1/3/5/10/15/30/60`(= `close_t/close_{t-n} − 1`), `log_return_1/5`, `momentum_10/30`, `rolling_return_max/min_20`(직전 20봉 1분 수익률의 최대/최소)

**F02 추세/이동평균** — `close_sma_{5,10,20,60}_ratio`(= `close/SMA − 1`), `close_ema_{12,26}_ratio`, `ema_12_26_spread`(= `(EMA12−EMA26)/close`, **가격 정규화**), `sma_5_20_spread`, `sma_20_60_spread`, `trend_slope_10/30`(선형회귀 기울기 / close), `distance_to_high/low_20`, `prev_horizon_trend`(직전 15봉 변화가 ±0.1% 넘으면 ±1)

**F03 변동성** — `rv_5/15/30/60/120`(1분 수익률의 롤링 표준편차), `atr_pct`(ATR14/close), `atr_pct_30`, `parkinson_vol_20`, `garman_klass_vol_20`, `range_vol_20`, HAR 구성요소 `har_rv_short/medium/long`(각각 rv_5/rv_30/rv_120)

**F04 거래량/체결 흐름** — `volume_sma_{5,20,60}_ratio`, `quote_volume_sma_20_ratio`, `taker_ratio`(테이커 매수 / 전체 거래량), `taker_imbalance`(매수−매도 / 전체), `taker_quote_ratio`, `trade_count_ratio`, `trade_count_zscore_20`, `volume_per_trade`, `volume_shock_20`

**F05 캔들 구조** — `high_low_range`, `body_pct`, `upper_shadow`, `lower_shadow`, `close_location_value`, `wick_imbalance`, `body_to_range`, `range_sma_20_ratio`, `inside_bar_flag`, `outside_bar_flag`

**F06 갭/데이터 품질** — 캐노니컬 복구 상태를 그대로 피처화. `gap_flag`, `gap_ratio_20/60/120`, `max_gap_run_120`, `repaired_flag`, `gap_length`, `canonical_gap_pressure`(= `gap_ratio_20 × (1+max_gap_run_120)`). 데이터 품질을 모델이 인지하도록 하는 용도.

**F07 레짐 정규화** — `close_zscore_20/60`, `volume_zscore_5/20`, `rv_zscore_60`, `range_zscore_20`, `volatility_regime_60`(= `rv_15 / SMA(rv_15,60) − 1`), `volume_regime_60`

**F08/F09/F10 변동성 조정** — 각각 수익률 / 추세 / 캔들·흐름 지표를 `max(rv_15, rv_60, rv_120, atr_pct, 1e-12)` 또는 `rv_60`으로 나눔. 변동성 레짐 간 스케일 통일 목적.

**F12 거래소 안전 상태** — `funding_rate`, `next_funding_rate`, `minutes_to_next_funding`, `funding_blackout_active`, `mark_price_basis`, `premium_index`, `adl_indicator`, `leverage_bracket_utilization`
> ⚠️ **오프라인 학습에서는 이 8개가 전부 상수 fallback**(funding 0.0, minutes 480, mark basis 0.0, ...). `--collect-external-sources` 없이 학습하면 정보량 0. 파이프라인 기본 실행은 이 플래그를 쓰지 않음.
> **[수정됨, f9017a5]** 학습이 이제 fallback/mock 값인 피처를 **기본으로 학습 매트릭스에서 제외**함(`training.drop_fallback_features`, 옵트아웃 `--keep-fallback-features`). 행·레지스트리는 그대로 두고 모델 투입만 제외; `model.json`이 자체 피처 목록을 갖고 있어 백테스트/라이브가 자동으로 같은 축소 집합을 씀.

**F13 주봉(완결 주 기준)** — `weekly_ma20_slope_closed`, `weekly_ma50_slope_closed`, `weekly_ma20_above_ma50`, `weekly_drawdown`, `weekly_vol_contraction`, `close_vs_weekly_ma20/50`
> MA는 주 단위로 **고정**, `close_vs_*`만 분 단위로 변동.

**F14 시간/세션** — `hour`, `minute`, `day_of_week`, `session_asia/europe/us/overlap`, `weekend_flag`

**F15 모멘텀 + 레인지 평균회귀** — `rsi_7/14`, `bb_width_20`, `bb_percent_b`, `ema_5/20/60_slope`, `price_vs_rolling_vwap_20/60`, `range_position_20`(20봉 레인지 내 위치 0~1), `distance_to_range_high/low`, `fake_break_low/high`(가짜 이탈 후 되돌림), `close_back_inside_range`, `vwap_deviation_zscore`, `bb_zscore`

**F16 파생상품 메트릭** — `oi_change_rate_5m/30m`, `oi_zscore_1d`, `oi_value_zscore_1d`(trailing 1일 = 288틱 인과적 z-score), `toptrader_ls_account/position`, `global_ls_account`, `taker_ls_ratio`, 각 `*_change_5m`
> 미결제약정의 **절대 수준은 절대 노출하지 않음**(연 단위 드리프트) — 변화율과 롤링 z-score만.

**F17 멀티 타임프레임** — 15m/1h/4h 각각에 대해 `trend_slope`, `return`, `ema_gap`, `ma_slope`, `rsi`, `atr_pct`, `bb_width`, `adx`, `volume_z` (9×3=27개) + 24시간 롤링 그룹 7개(`trend_slope_24h`, `return_24h`, `drawdown_from_24h_high`, `distance_from_24h_high/low`, `rolling_high_breakout_24h`, `rolling_low_breakdown_24h`)
> 도입 동기: 손으로 라벨한 레짐은 수일~수개월 스케일인데, 자동 레짐 탐지의 유일한 추세 신호였던 `trend_slope_30`은 30분 창이라 그 스케일을 볼 수 없었음.

**F18 레짐 확률** — `regime_prob_up/range/down`. Phase 2.5의 walk-forward OOF 분류기 산출값.
> ⚠️ **파이프라인 기본값 `$RegimeMode="rule"`에서는 Phase 2.5를 건너뛰므로 이 3개가 전부 0.0 상수.**

### 3.4 미래 정보 미사용 검증 로직 — **분석 요청 항목 ②-c**

| 계층 | 검증 방식 |
|---|---|
| 롤링 윈도우 | 부분 창 금지·백필 금지. 창이 안 차면 0.0 또는 NaN. `min_samples` 미만 행은 `warmup_invalid=True`로 표시되고 라벨링에서 제외 |
| 상위 타임프레임 (F17) | `resample_causal()`이 **완결된 봉만** 방출. 마지막 미완결 그룹은 버림. 각 봉은 `close_time` 이후의 1분봉부터 참조 가능 |
| 주봉 (F13) | pandas `resample("W")`가 주 bin에 **일요일 00:00 날짜**를 붙이는데 그 bin의 close는 일요일 23:59 값. `label <= ts`로 고르면 **일요일 하루 전체가 그 주의 최종 종가를 미리 봄**(주 1회 최대 24시간 look-ahead). 수정: `available_index = weekly_index + 1 day`. 검증 스크립트 `verify_weekly_causality.py`가 **절단 불변성(truncation invariance)** 으로 확인 — 전체 시리즈로 계산한 값과 임의 prefix로 계산한 값이 prefix 내부에서 완전히 일치해야 함 |
| metrics (F16) | `align_metrics_to_minutes()`가 `create_time <= t`인 최근 관측만 as-of join. 첫 관측 이전 분봉은 값 없음 |
| 병렬 처리 | 청크 경계에서 lookback 부족 방지를 위해 overlap 6,000봉. 주봉은 청크가 50주를 못 채우므로 **부모 프로세스가 전체 시리즈로 한 번 계산 후 슬라이스 배포** |
| 라벨 | `attach_labels`는 `candles[row.index]`를 참조. 행 슬라이싱 시에도 캔들은 전체를 넘김 |
| 진단 도구 | `ic_diagnostic.py`가 피처별 Spearman IC와 함께 2개 누수 휴리스틱 실행: ① `fwd>past` — 미래 수익률과의 \|IC\|가 0.10 초과이면서 같은 길이 **과거** 수익률과의 \|IC\|보다 큰 경우 ② `lag1-collapse` — \|IC\|≥0.05인데 피처를 1봉 늦춰 쓰면 절반 이상 소멸 |

**클리핑**: `features.FeatureClipper`가 피처 이름으로 타입을 분류해 상한 적용 —
`zscore` ±10, `ratio` ±100, `return` ±0.20, `vol_adj` ±10, `bps` ±10000, `vol` ±10, `price` ±1e6, `regime` ±10, `flag` ±1, `minutes` ±1440, `funding` ±1, `adl` ±4.
비유한값(inf/NaN)은 `None`으로 치환 후 `NaNSourceClassifier`가 원인을 4분류(`outage_nan` / `warmup_nan` / `structural_nan` / `isolated_feature_nan`).

**저장 형식**: `FeatureVector` — float32 컬럼 배열. 189개 dict가 행당 9~20KB인데 3.15M행이면 수십 GB이므로 array('f')로 대체.

---

## 4. Phase 2.3 — 데이터 진단 (정보성, 게이트 아님)

```
python ic_diagnostic.py --input <parquet> --metrics-dir <metrics> [--regime-file regimes.json]
python verify_range_halflife.py --input <parquet> --series log_zscore [--regime-file regimes.json]
```

### `ic_diagnostic.py`
- 호라이즌 15/30/60/120/240분 각각에 대해 **피처 × 호라이즌** Spearman IC
- 5개 연대순 fold의 IC **평균/표준편차** → IC 드리프트 가시화 (`std > |mean|`이면 UNSTABLE)
- 레짐별 IC 분해 (regimes.json 있을 때)
- 판정 기준: `|IC| < 0.01` 죽은 피처, `0.01~0.03` 약함, `≥0.03` 신호, **`> 0.10` 의심**(누수 재확인 필요)
- 학습과 같은 워밍업 제외(504,000봉)를 적용해 **모델이 실제로 보는 모집단**에서 측정

### `verify_range_halflife.py`
- Ornstein-Uhlenbeck 반감기 측정: `dz[t] = θ·(z[t-1] − mean) + ε`를 OLS로 적합, 반감기 = `−ln2/θ`
- 원가격이 아니라 **드리프트 제거 log z-score**(detrend 창 60봉)에 적합 — 원가격 OU는 BTC의 추세를 측정할 뿐
- 판정: range 레짐 반감기의 중앙값이 고정 20봉 창의 **1~3배** 안에 들어오면 타당
- 목적: `range_position_20` / `bb_zscore` / `vwap_deviation_zscore` / `apply_range_mean_reversion_gate`가 전부 쓰는 **고정 20봉**이 데이터로 정당화되는지 확인. 이 20은 원래 근거 없이 정해진 값.

> **분석 참고**: 이 두 리포트의 실제 산출물(`artifacts/ic_report/ic_report.csv`)이 엣지 부재 진단의 1차 자료.
> **실측 요약 (2026-07-22 리포트, horizon=60m)**: |IC|≥0.03 **49/180**, |IC|≥0.01 98/180, 누수 플래그 0.
> 상위권(ema_gap_15m −0.048, close_zscore_60 −0.043, rsi_14 −0.040, return_60 −0.040 등)은 fold-stable이며 **전부 음의 IC** — 추세·모멘텀이 높을수록 60분 순방향 수익률이 낮음 = **평균회귀 신호**. 현재 라벨(+1.0% before −0.5%)은 추세추종형이므로 신호-타겟 방향 불일치가 유력한 병목.

---

## 5. Phase 2.5 — 레짐 확률 분류기 (기본 실행에서는 **스킵**)

`$RegimeMode="rule"`(기본값)이면 실행되지 않음. `"classifier"`일 때만 동작.

동작 시:
- F17 피처로 up/range/down 멀티클래스 CatBoost
- **엄격한 walk-forward OOF**: fold f는 fold 0..f−1로만 학습, fold 경계 직전 `purge_gap=60`봉 제거. **미래 fold를 절대 학습에 쓰지 않음**(Lopez de Prado의 purged K-fold보다 엄격 — 그쪽은 미래 fold도 학습에 포함)
- fold 0은 이전 데이터가 없으므로 예측을 **지어내지 않고** 중립 (1/3, 1/3, 1/3)
- 전이 구간 가중치 완화: 라벨 경계 ±1일 이내 행은 weight 0.1 (0이 아님 — "전이 중"이라는 정보 자체는 유효)
- 사후 스무딩: 30봉 롤링 평균 + 최소 지속 60봉 + 신뢰도 0.45 히스테리시스

**학습 버킷 배정 시 규율(중요)**: 저장된 최종 `.cbm`으로 학습 행을 재예측하지 **않음**. 그 분류기는 전체 구간으로 적합되었으므로 2021년 행을 판정하면 2023~2024년을 이미 본 모델이 판정하는 셈 — 라벨 누수는 아니지만 명백한 look-ahead. **학습 버킷은 OOF 확률의 argmax만 사용**하고, `.cbm`은 연대적으로 이후인 백테스트/라이브에서만 사용.

---

## 6. Phase 3 — 레짐 인식 학습 (**핵심 배포 모델**)

```powershell
python -m btcusdt_quant train `
    --input $FullParquet --regime-aware `
    --training-start 2020-01-01 --training-end 2024-12-31 `
    --metrics-dir $MetricsDir `
    --threshold-objective trading_pnl --round-trip-cost 0.0008 `
    --horizon 60 --tp-pct 0.010 --sl-pct 0.005 `
    --multi-feature-regime --rule-regime-config configs/rule_regime.json `
    --optuna --optuna-trials 100 `
    --output artifacts/regime_stacking_model
```

### 6.1 레짐 분류 로직 — **분석 요청 항목 ③**

`regime_rules.MultiFeatureRegimeDetector`. **4개 점수를 계산 → 히스테리시스 결정**.

#### 입력 점수

모든 입력은 학습 구간에서 적합한 (mean, std)로 **z-score 정규화**.

**(1) 장기 추세 점수 `trend`** — 1h/4h/24h만 사용 (가중합, 합=1.0):
```
trend_slope_1h  0.25
trend_slope_4h  0.30
return_4h       0.15
ema_gap_4h      0.15
trend_slope_24h 0.15
```

**(2) 단기 추세 점수 `trend_fast`** — 5m/15m/30m만 (자기들끼리 정규화):
```
return_5         0.20
trend_slope_15m  0.35
trend_slope_30   0.45
```
역할이 명확히 분리됨: 장기는 **레짐 정의**, 단기는 **확인/타이밍**.

**(3) 변동성 점수 `vol`**: `atr_pct_1h 0.40 + atr_pct_4h 0.30 + bb_width_1h 0.30`

**(4) 레인지 점수 `rng`**: ADX·BB폭의 **역** z-score(낮을수록 레인지) + 24시간 밴드 중앙 근접도
```
−z(adx_1h)·0.35 − z(adx_4h)·0.20 − z(bb_width_1h)·0.30 + center_proximity·0.15
```

**(5) 브레이크아웃 오버라이드**: `rolling_high_breakout_24h`(또는 low breakdown) = 1 **AND** `volume_z_1h > 1.5`

#### 결정 규칙 (`configs/rule_regime.json` 적용값)

```
진입(현재 레짐 없음):
  rng > 0.65 AND |trend| < 0.45              → range
  trend > +0.70 AND vol > 0.20               → up   (단, trend_fast > −0.60 일 때만; 아니면 range)
  trend < −0.70 AND vol > 0.20               → down (단, trend_fast < +0.60 일 때만; 아니면 range)
  그 외                                        → range

유지(up 보유 중):
  trend_fast < −0.80                          → range   (단기 급반전 조기 이탈)
  trend > +0.40                               → up      (히스테리시스: 이탈 임계 0.40 < 진입 0.70)
  allow_direct_reversal=false 이므로 up→down 직행 불가  → range 경유 강제
```

#### 안정화
- `min_hold_bars = 60` — 현재 레짐 최소 유지 60봉
- `switch_confirm_bars = 10` — 새 후보가 **연속 10봉** 지속해야 전환 승인
- `allow_direct_reversal = false` — up↔down 직행 금지, 반드시 range 경유
- **강한 브레이크아웃은 위 두 게이트를 모두 우회** (즉시 전환)

#### 시계열 무결성
- 행별 점수는 **그 행의 피처 + 학습 구간 정규화 통계**만 사용 → 미래 미참조
- 순차 히스테리시스 상태는 **과거 행에만** 의존
- `detect_one(rows[:k]) == detect_all(rows)[k-1]` 이 테스트로 고정 (`test_causal_prefix_matches_detect_one`)
- 적합된 detector(설정 + 정규화 통계)가 `regime_run_summary.json`에 **직렬화되어 저장** → 백테스트/라이브가 **동일 객체를 재사용**, 라이브에서 재적합 안 함

#### ⚠️ 정규화 통계의 비정상성 문제 (분석 요청 항목 — 검토 필요)

`fit()`이 **2020-12 ~ 2024-12 전 구간에 대해 단일 (mean, std)** 를 계산.
2021년 불장, 2022년 베어, 2023년 횡보의 변동성 수준이 전혀 다른데 하나의 z-score 기준으로 묶임. 롤링/확장 윈도우 정규화가 아님.

#### 레짐별 데이터 개수

> **현재 문서에 실측치 없음.** `artifacts/regime_stacking_model/regime_run_summary.json`의 `regime_counts` 및 `regime_diagnostics`에 기록됨.
> 다만 코드 주석에 기록된 관측: **2025 백테스트 구간에서 range 레짐이 약 91%**. `--threshold-floor 0.45`를 걸었을 때 range가 학습 임계값 0.348/0.358로 전부 차단되어 **백테스트가 데이터의 9%만 거래하고 그것을 결과로 보고한 사고**가 있었음. 그래서 현재 `$ThresholdFloor = "0.0"`(비활성).

#### 하드코딩된 방향 정책 (`training.REGIME_SIDES`)

| 레짐 | 허용 사이드 | 학습 타겟 |
|---|---|---|
| `up` | long only | `long_success` |
| `down` | short only | `short_success` |
| `range` | long + short | 각각 `long_success` / `short_success` |

추가로 range 레짐에는 **평균회귀 게이트**(`apply_range_mean_reversion_gate`):
```
range_position_20 < 0.25  → LONG만 허용
range_position_20 > 0.75  → SHORT만 허용
그 사이(0.25~0.75)        → 진입 금지 (빈 집합)
```
> 이 게이트가 range 구간의 **대부분 바를 거래 불가로 만듦**. range가 91%인 구간에서 실제 진입 가능 바가 얼마나 되는지가 중요.
> **[수정됨, f9017a5]** A/B 실험용으로 `backtest --disable-range-gate` 플래그 신설(백테스트 전용; 라이브는 게이트 유지). `run_config.range_gate_enabled`에 기록되고 `compare_backtests`의 비교 가능성 검사 대상이라 게이트 유무가 다른 런이 몰래 비교되지 않음.

### 6.2 학습 및 검증 방식 — **분석 요청 항목 ④**

#### ⚠️ 가장 중요한 구조적 사실: **레짐 인식 경로는 Walk-Forward CV를 쓰지 않음**

레포에는 `cv.py`에 `CombinatorialPurgedCV`, `PurgedWalkForwardSplit`, 샘플 uniqueness 가중치가 완비되어 있으나 —
**`--regime-aware` 경로(`training.run_regime_aware_training`)는 이들을 호출하지 않음.**
walk-forward / combinatorial purged CV는 비레짐 단일 모델 경로(`run_training` 본체, = Phase 3.7)에서만 동작.

레짐 경로의 검증은 **레짐별 단일 연대순 홀드아웃**:

```
n = 해당 레짐의 행 수
holdout_split = int(n * 0.8)
holdout_gap   = min(label_horizon, (n - holdout_split) // 4)     # 퍼지 갭
holdout_start = holdout_split + holdout_gap

진단 모델: prefix[:holdout_split] 으로만 학습  →  [holdout_start:] 에서 평가
배포 모델: 해당 레짐 전체 행으로 학습            →  홀드아웃 지표를 산출하지 않음
```

설계 의도(코드 주석): 배포 모델은 데이터를 100% 쓰고, 정직한 홀드아웃 지표와 임계값은 **별도의 prefix-only 진단 모델**에서 뽑는다. 배포 모델로 홀드아웃을 평가하면 in-sample이라 F1이 부풀려짐.

> **따라서 `regime_run_summary.json`의 `mean_test_f1` 등은 배포 모델이 아니라 진단 모델의 성능.**

#### ⚠️ Optuna 검증 구간과 임계값 홀드아웃 구간이 **겹침**

`_tune_catboost_with_optuna(feature_matrix_values=f_matrix, ...)` — `f_matrix`는 **해당 레짐의 전체 행**.
내부에서:
```
split_index = int(n * 0.8)
horizon_gap = min(label_horizon, (n - split_index) // 4)
val_start   = split_index + horizon_gap
train = rows[:split_index],  val = rows[val_start:]
```

이는 `_train_single_regime`의 홀드아웃 분할과 **동일한 공식·동일한 구간**.
즉:
1. Optuna 100 trial이 **꼬리 20%의 logloss를 최소화**하도록 하이퍼파라미터 선택
2. 그 다음 같은 꼬리 20%에서 **결정 임계값을 선택**하고 **홀드아웃 성능을 보고**

> **하이퍼파라미터는 그 홀드아웃에 대해 out-of-sample이 아님.** 보고되는 홀드아웃 F1/정확도/임계값이 낙관 편향될 수 있는 경로.
>
> **[수정됨, f9017a5]** Optuna는 이제 **홀드아웃 이전 prefix(앞 80%)만** 입력으로 받고, 내부 80/20 분할이 그 prefix 안에서 이루어짐(HPO 검증은 전체의 64~80% 구간). 임계값 선택·홀드아웃 지표가 쓰는 마지막 20%는 하이퍼파라미터 선택이 한 번도 보지 못한 구간이 됨. 회귀 테스트가 튜너 입력 행 수를 캡처해 고정(`test_optuna_tunes_on_prefix_only_never_the_threshold_holdout`).

#### CatBoost 파라미터

**기본값(Optuna 미사용 시, `_REGIME_CATBOOST_DEFAULT_PARAMS`)**
```python
iterations = 500, learning_rate = 0.03, depth = 8, verbose = False
```

**어댑터 기본값(`CatBoostAdapter.DEFAULT_PARAMS`)**
```python
loss_function = "Logloss"
iterations = 500, learning_rate = 0.03, depth = 8
random_seed = 42
task_type = "GPU", devices = "0"      # 실패 시 CPU 자동 폴백
od_type = "Iter", od_wait = 50
allow_writing_files = False
auto_class_weights_enabled = False    # ← 아래 참조
```

**Optuna 탐색 공간 (100 trial, TPESampler seed=42, 목적함수 = validation logloss 최소화)**

| 파라미터 | 범위 | 스케일 |
|---|---|---|
| `iterations` | 300 ~ 2000 | int |
| `learning_rate` | 0.005 ~ 0.08 | **log** |
| `depth` | 3 ~ 8 | int |
| `l2_leaf_reg` | 1.0 ~ 50.0 | **log** |
| `random_strength` | 0.1 ~ 10.0 | **log** |
| `bagging_temperature` | 0.0 ~ 5.0 | float |
| `min_data_in_leaf` | 20 ~ 500 | int |
| `border_count` | 64 ~ 254 | int |
| `od_wait` | `max(30, iterations//10)` | 파생 |

> `subsample`은 탐색하지 않음. `bagging_temperature`(베이지안 부트스트랩)가 그 역할.

**조기 종료 및 최종 refit 캡**
trial은 `eval_set` + `use_best_model=True`로 학습(이게 없으면 `od_type`/`od_wait`가 무의미한 no-op).
최종 배포 모델은 `eval_set` 없이 전체 데이터로 refit하므로 조기 종료가 작동하지 않음 → **승리 trial의 `best_iteration + 1`로 `iterations`를 캡**(제안 예산을 넘기지는 않음). 안 하면 검증 최적점을 지나쳐 학습함.
`best_iteration == 0`(첫 트리가 최적)이면 퇴화 신호로 보고 `best_iteration_degenerate=true`를 리포트에 기록.

**클래스 불균형 — 의도적으로 미처리**
`auto_class_weights_enabled = False`가 기본값. 주석의 근거:
> 클래스 가중치는 recall/precision 균형을 자동 조정하지만, 예측 확률을 실제 기저율에서 **밀어냄**. 그건 우리가 쓰는 손실함수(Logloss)가 정확히 벌하는 것. 확률 캘리브레이션을 지키기 위해 기본 OFF. F1/recall 최적화가 목표일 때만 켤 것.

**단일 클래스 방어**: 어떤 레짐/사이드의 타겟이 단일 클래스면 크래시 대신 사유와 함께 skip.

#### 결정 임계값 선택 (`training.select_threshold`)

후보 = {0.05, 0.10, ..., 0.95} ∪ {실제 예측 확률 전부}
기본 목적함수 `trading_pnl`:
```
각 후보 t에 대해:
  거래수 = 예측 양성 수  (< max(1, 5% of rows) 이면 후보 탈락)
  PnL 시뮬레이션: p >= t 이면 label==1 → +0.0092, label==0 → −0.0058 / p < t 이면 0
  정렬 키 = (calmar, sharpe, f1, −|t−0.5|)  ← 전부 클수록 좋음
```
`calmar`가 **첫 번째 정렬 키**이므로, mdd가 float 노이즈 수준일 때 ~1e18을 반환하는 것을 막기 위해 `_MIN_PNL_MDD = 1e-12` 바닥값을 둠. `sharpe`도 동일하게 `_MIN_PNL_STD`.

#### 평가 지표

`training.metrics()`가 반환: `accuracy`, `precision`, `recall`, `f1`, `ece`, `mce`, `brier`, `brier_skill_score`, `positive_rate`, `predicted_positive_rate`, `mdd`, `sharpe`, `calmar`.
`_baseline_logloss()`가 **기저율 상수 예측의 logloss**를 함께 보고 — 개선폭 해석 기준:

| 개선폭 | 해석 |
|---|---|
| < 0.005 | 사실상 개선 없음 |
| 0.005 ~ 0.015 | 약한 개선 |
| 0.015 ~ 0.03 | 유의미 |
| > 0.03 | 강함 |

---

## 7. Phase 3.7 — 비레짐 단일(unified) 베이스라인

```powershell
python -m btcusdt_quant train --input $FullParquet `
    --training-start 2020-01-01 --training-end 2024-12-31 --metrics-dir $MetricsDir `
    --threshold-objective trading_pnl --round-trip-cost 0.0008 `
    --horizon 60 --tp-pct 0.010 --sl-pct 0.005 `
    --optuna --optuna-trials 100 --output artifacts/unified_model
```

`--regime-aware` **없음** → `run_training` 본체 경로:
- **여기서만 walk-forward CV 동작**: `cv.SplitManager.get_splits(cv_mode="walk_forward")`,
  `train_size = max(60, n//3)`, `validation/test = max(20, n//8)`, **purge_gap = label_horizon(60)**
- 샘플 uniqueness 가중치(`cv.uniqueness_weights`) 적용 — 트리플 배리어 창이 겹치는 표본의 중복 정보를 할인
- fold별 Platt/Beta 캘리브레이터 적합(검증 폴드), 임계값도 fold별 선택
- 학습 타겟은 `profitability`(롱 기준) — **숏 가격 산정 불가**
- Optuna는 첫 test fold 시작 이전 구간으로 시야를 제한

목적: 하우스룰 원칙 6 — **레짐 분할이 실제로 도움이 되는지**를 같은 데이터·피처·배리어·윈도우·튜닝 예산으로 판정. Phase 4.6의 4-way 비교에서 `unified` arm으로 투입.

---

## 8. Phase 3.5 — 멀티호라이즌 앙상블 파일럿

```powershell
python -m btcusdt_quant train-multi-horizon --horizons 30,60,90 `
    --regime-aware --threshold-horizon 60 --weighting validation ...
```

- G-Research 암호화폐 예측 7위 패턴. 같은 피처를 여러 호라이즌(30/60/90분)으로 라벨링해 각각 모델을 학습하고 확률을 블렌딩. 호라이즌 간 오차가 탈상관되는 효과를 노림.
- 레짐 인식. Phase 3의 버킷팅·방향 정책·사이드별 타겟을 그대로 공유.
- 블렌드 가중치: `validation` 모드는 각 호라이즌 모델의 **검증 정확도 − 0.5** (음수는 1e-6으로 바닥). 검증 꼬리는 `max(horizons)` 퍼지 갭 뒤에 배치.
- **최종 refit**: 가중치는 prefix 진단 적합에서 가져오고, 호라이즌 모델은 전체 레짐 행으로 다시 적합 → Phase 3와 데이터 커버리지 동일. 가중치·임계값은 out-of-sample 유지.
- 스테이징 디렉터리에 학습 후 **모든 게이트 통과 시에만** 실제 출력 디렉터리로 승격. 실패하면 이전 아티팩트가 그대로 남음.
- ⚠️ **Optuna 미적용**(기본 파라미터). Phase 3는 100 trial 튜닝 → Phase 4.5 승패는 호라이즌 블렌딩과 튜닝 차이가 **혼재**된 결과.

---

## 9. Phase 4 — 백테스트 (2025 full-year OOS)

```powershell
python -m btcusdt_quant backtest `
    --input $FullParquet --model-artifact artifacts/regime_stacking_model `
    --kelly-sizing --kelly-multiplier 0.5 --kelly-lookback-bars 1440 `
    --exec-tp-pct 0.010 --exec-sl-pct 0.005 `
    --metrics-dir $MetricsDir `
    --fee-rate-per-side 0.0002 --slippage-rate-per-side 0.0002 `
    --horizon 60 --threshold-floor 0.0 `
    --backtest-start 2025-01-01 --backtest-end 2025-12-31
```

### 9.1 배리어 패리티 강제

실행 전 `check_execution_barrier_parity()`가 **아티팩트에 기록된 라벨 tp/sl과 실행 tp/sl을 비교**하고, 불일치면 `ValueError`로 **거부**. 근거:
> 모델은 "라벨된 배리어에서 TP가 SL보다 먼저 오는가"에만 답한다. 다른 배리어로 실행하면 모든 확률·임계값·승률이 아무도 학습하지 않은 배리어로 표시된다. 크래시도 안 나고 그냥 무의미한 숫자가 나온다.

### 9.2 레짐 라우팅

아티팩트에 저장된 **적합된 rule detector가 자동 로드**됨 (별도 플래그 불필요) → 학습 버킷팅과 서빙 라우팅이 동일 객체.
진단(`regime_routing_diagnostics`)은 **백테스트 윈도우로 슬라이스**해 저장 (전체 시리즈 통계가 아님). `detect_all` 자체는 히스테리시스 상태를 위해 전체 시리즈에서 돌림.

### 9.3 진입 결정

```
allowed = direction_policy[regime]                       # up→LONG, down→SHORT, range→둘 다
allowed = apply_range_mean_reversion_gate(...)           # range면 0.25/0.75 밴드 게이트
long_prob  = bundle.probability_for(regime,"long",  feats)   # 모델 없으면 None
short_prob = bundle.probability_for(regime,"short", feats)

evaluate_entry_signal(long_prob, short_prob,
                      long_threshold=lt, short_threshold=st,
                      strategy=..., features=...)
```

`lt/st` 우선순위: **CLI 명시 override > 학습 시 저장된 레짐별 임계값(`selected_thresholds`) > 전략 프로파일 기본값**, 그 뒤 `threshold_floor` 하한 적용(override에는 미적용).

**EV 게이트** (`live.evaluate_entry_signal`):
```
net_tp = gross_tp − (fee_entry 0.0002 + fee_exit 0.0002 + slippage 0.0001 + spread 0.0001)
net_sl = −gross_sl − 위와 동일
long_ev  = p_long  · net_tp + (1−p_long)  · net_sl
signal = LONG  if long_ev > min_ev(0.0001) and p_long > lt
```
> 배리어는 `resolve_tp_sl_deltas()`가 **실제 실행될 값과 동일하게** 계산 — EV가 실제 거래와 다른 배리어로 계산되는 것을 방지.

### 9.4 Kelly 사이징

```
edge     = p·(tp − rt) − (1−p)·(sl + rt)          # rt = 0.0008
var_bar  = 최근 1440봉 수익률의 모집단 분산
var_trade= var_bar × holding_period_bars(=60)     # 분산은 기간에 선형
f*       = 0.5 × edge / var_trade
fraction = min(f*, position_size)                 # position_size가 상한
edge ≤ 0 이거나 분산 추정 불가 → 진입 스킵
```
> `holding_period_bars` 스케일링을 빠뜨리면 f*가 보유기간 배수만큼 부풀어 상한에 고정됨.

**사이드 확률이 없으면 진입 거부(fail-closed)**: 단일 모델 경로는 `P(long_success)`만 산출하므로 SELL 신호를 Kelly가 사이징할 수 없음(`1 − P(long)`은 숏 승률이 아님). `shorts_skipped_no_short_model` / `longs_skipped_no_long_model` 카운터로 보고 → **런이 조용히 단방향이 되는 것을 가시화**.

### 9.5 청산

```
BUY:  hit_tp = high >= tp_price ; hit_sl = low  <= sl_price
SELL: hit_tp = low  <= tp_price ; hit_sl = high >= sl_price

동일봉 동시 터치 tie-break (라벨러와 동일):
  BUY  : close > open → TP 먼저
  SELL : close < open → TP 먼저
```
`min_hold_bars = 0`, `cooldown_bars = 30`(기본), `label_horizon = 60`에서 강제 타임아웃.

### 9.6 리스크 지표의 표본 게이트

```python
MIN_TRADES_FOR_RISK_METRICS = 20
```
거래 20건 미만이면 `sharpe` / `gross_sharpe` / `profit_factor` = **NaN**(0.0 아님). `win_rate` / `max_drawdown`은 서술적 지표라 유지.
> 근거: 2건 다 TP로 끝난 런이 win_rate 1.0, profit_factor inf, mdd 0, **Sharpe 1.08e14**를 보고한 실제 사고.

지표는 **가격 수익률이 아니라 자기자본 수익률**(`trade_return_pct = net_pnl_pct × 실제 베팅 비율`)로 계산. 고정 사이즈면 상수가 상쇄되어 결과 불변, Kelly면 1%짜리와 10%짜리 거래를 동일 가중하는 오류 방지.

`per_trade_sharpe`는 분산이 `MIN_RETURN_STD = 1e-12` 이하이면 NaN.

### 9.7 전략 프로파일 축퇴 감지

balanced/conservative/aggressive 3개 프로파일이 다른 점은 진입 임계값, `tp_pct`, `min_reward_risk` 세 가지뿐.
`--exec-tp-pct/--exec-sl-pct`로 배리어를 고정하고 임계값을 학습값에서 가져오면 **셋이 완전히 동일한 거래를 실행**함(그리고 `min_reward_risk`는 백테스트가 읽지 않음).
→ `indistinguishable_profiles()`가 실행 지문을 비교해 축퇴를 감지하면 **1개 arm만 실행**하고 `best_strategy = None`(무승부에 승자를 만들지 않음), 사유를 문자열로 기록.

---

## 10. Phase 4.3 — 캘리브레이션 검증 (**엣지 부재 진단의 핵심**)

```powershell
python verify_calibration.py --input $FullParquet --model-dir $ModelDir `
    --start 2025-01-01 --end 2025-12-31 --horizon 60 --round-trip-cost 0.0008 `
    --output artifacts/backtest_results/calibration_report.json
```

백테스트는 "모델이 **얼마를 벌었는가**"를 말하고, 이 단계는 "그 돈을 벌게 한 숫자가 **의미가 있는가**"를 말함.

### 방법
- 피처: `dataset.build_feature_rows` — 학습·라이브와 동일 경로 (파리티 깨짐이 여기서 드러남)
- 레짐: **아티팩트 내부의 적합된 detector** — 각 바를 실제로 가격 매겼을 모델이 평가되도록
- 라벨: `dataset.attach_labels`를 **아티팩트가 기록한 배리어**(`label_tp_pct`/`label_sl_pct`)로 생성. 기록이 없으면 **거부**(추측 금지). `--horizon`이 기록된 `threshold_horizon`과 다르면 **거부**.

### 두 개의 모집단을 구분

| 스트림 | 대상 | 목적 |
|---|---|---|
| `samples` | 모델이 가격을 매긴 **모든 바** | **모델** 채점 — 확률이 정직한가는 정책과 무관 |
| `entered` | 진입 정책(방향 정책 + range 평균회귀 게이트)이 **실제로 허용한 바만** | **거래** 채점 — decision band는 여기서만 측정 |

> range가 91%인데 그 대부분이 평균회귀 게이트로 막히므로, 이 구분을 안 하면 아무도 거래하지 않는 바의 승률을 보고하게 됨.

### 산출물

- **reliability curve**: [0,1]을 10개 **등폭** 구간으로 분할(등질량 아님 — 확률이 0.52 근처 좁은 밴드로 압축된 병리를 등질량 구간은 흩뿌려 감춤). 구간별 `mean_predicted` vs `observed_rate` 및 `gap`
- **ECE**: 표본 20개 미만 구간은 제외(양자화 노이즈). 측정 가능한 구간이 하나도 없으면 **NaN**(0.0이면 완벽 캘리브레이션으로 오독됨)
- **Brier score**
- **decision band** ← **최종 판정**:
  ```
  배포 임계값 이상인 (진입 가능) 바만 모아
  observed_rate 를 risk.breakeven_probability(tp, sl, round_trip_cost) 와 비교
  clears_breakeven = observed_rate >= breakeven_rate
  margin           = observed_rate − breakeven_rate
  ```

> **핵심**: 정확도는 이 문제를 볼 수 없음. 확률을 0.5 쪽으로 단조 압축하면 **순위(따라서 정확도·AUC)는 그대로**인 채 확률만 파괴됨. 현재 증상(0.522 예측 / 32.3% 실현)이 정확히 그 형태.

---

## 11. Phase 4.6 — 엣지 검증 (비용 스트레스 + 4-way 라우팅)

```powershell
python -m btcusdt_quant edge-validate `
    --model-artifact artifacts/regime_stacking_model `
    --unified-artifact artifacts/unified_model/model.json `
    --user-regime-file regimes.json `
    --metrics-dir $MetricsDir --exec-tp-pct 0.010 --exec-sl-pct 0.005 `
    --fee-rate-per-side 0.0002 --slippage-rate-per-side 0.0002 `
    --horizon 60 --threshold-floor 0.0 --kelly-sizing ... `
    --backtest-start 2025-01-01 --backtest-end 2025-12-31
```

### (a) 비용 스트레스 (하우스룰 원칙 5)
**같은 모델·같은 신호·같은 배리어**로 fee+slippage만 **1x / 1.5x / 2x** 로 스케일해 재실행.
판정: `survives_1_5x`(1.5배에서도 net > 0), `survives_2x`(2배에서 급붕괴하지 않음).

### (b) 4-way 라우팅 비교 (하우스룰 원칙 6)

| arm | 내용 |
|---|---|
| `unified` | Phase 3.7의 비레짐 단일 모델 |
| `oracle` | **regimes.json 사후 라벨**로 라우팅 — 구조상 look-ahead. "라우팅이 완벽했다면"의 **진단적 상한**이지 전방 성능이 아님 |
| `predicted` | 아티팩트의 rule detector (= 학습 버킷팅과 동일 소스) |
| `detector_diagnostics` | predicted arm의 레짐 카운트/비율/전이/평균 지속 |

**해석 규칙** (`_interpret_routing`):
```
oracle > 0  AND  predicted <= 0   → 디텍터 / 전이 / 라우팅 지연 문제
oracle <= 0                        → 라벨·피처·진입모델·레짐분할 자체의 문제 (디텍터 탓 아님)
unified > predicted                → 현재 버킷팅이 표본을 쪼개서 엣지를 해치고 있음
```

> `oracle` arm의 캐비엇: 진입 모델은 **디텍터의 버킷팅으로 학습**되었으므로, oracle은 "완벽한 라우팅 + 디텍터로 버킷된 모델"의 혼합. 순수 상한은 아님.

### (c) 셔플 라벨 대조군 — **[수정됨, f9017a5: 파이프라인 배선 완료]**

- **Phase 3.8 (신설)**: `train --shuffle-labels`로 **셔플 라벨 음성 대조군** 학습. 각 행의 라벨 payload(label + targets + reason, 함께 이동)를 행 간 결정론적 순열(seed 지정 가능), 피처는 그대로. 아티팩트에 `shuffled_labels=true` 각인 — 배포 금지. 미튜닝(데이터 경로의 대조군이지 HPO 경로의 대조군이 아님).
- **Phase 4.7 (신설)**: 그 셔플 모델을 Phase 4와 같은 윈도우·비용·배리어로 백테스트 → `artifacts/backtest_results_shuffled_control`. **판독**: 셔플 모델의 net/Sharpe가 본 모델과 비슷하면 그 "엣지"는 누수·임계값 과적합·백테스트 버그·선택 편향.

라이브러리 전용으로 남은 하네스 (파이프라인 미배선 — seed별/그룹별 모델을 직접 재학습해 넘겨야 하며, 하네스는 절대 재학습하지 않음):
- `seed_stability` — 시드별 방향성 유지 확인
- `feature_group_ablation` — 피처 그룹 제거 후 **재학습** 비교 (추론 시 0으로 만드는 것은 train/serve 스큐이지 ablation이 아니라는 이유로 금지)

---

## 12. Phase 4.5 — 멀티호라이즌 파일럿 백테스트

Phase 4와 **동일한 윈도우·비용·Kelly 설정·배리어**로 `artifacts/multi_horizon_model` 백테스트.
이후 `compare_backtests.py`가 두 요약을 **레짐 × 사이드 × 월** 축으로 분해 비교.

- `trade_return_pct`(자기자본 수익률) 기준
- `sum_ret`(기여도, 가법적) 과 `comp_ret`(해당 부분집합만 거래했을 때의 복리) 를 **구분해서** 보고. 둘 다 `net_total_return`과 같지 않음
- **정합성 검사**: `prod(1 + trade_return_pct) − 1 == net_total_return` 을 `rel_tol=1e-9, abs_tol=1e-9`로 확인. 어긋나면 trades 배열과 자기자본 곡선이 불일치 → 리포트 전체를 의심하라고 출력
- **비교 가능성 검사**: 두 런의 `run_config`(윈도우, 배리어, 전략 config, 임계값 override, position_size, Kelly 설정) 및 비용/게이팅 필드가 다르면 "NOT LIKE-FOR-LIKE" 경고
- Sharpe는 `backtest.per_trade_sharpe`를 **import해서 사용**(복사본이 드리프트하는 것 방지)

---

## 13. 분석 시 중점 체크 항목에 대한 현황 정리

### ① 타겟·레짐 정의의 시계열 무결성

| 항목 | 상태 |
|---|---|
| 라벨 방향성 | 트리플 배리어는 **정의상 전방 참조**(그것이 타겟). 피처는 엄격 인과. 꼬리 행은 폐기 |
| 주봉 일요일 누수 | **발견 및 수정 완료**. 절단 불변성 테스트로 고정 |
| 상위 TF 봉 | 완결 봉만 사용, `close_time` 이후부터 가시 |
| metrics as-of join | `create_time <= t` 인과 조인 |
| 레짐 라벨링 | rule detector는 **현재까지 정보만** 사용 + 인과적 히스테리시스. `detect_one(prefix) == detect_all()[k-1]` 테스트 고정 |
| regimes.json | **사후 라벨**. 파일 자체에 look-ahead 경고 주석. 기본 파이프라인의 학습·라우팅에 미사용. Phase 4.6 oracle arm에서만 진단 목적 사용 |
| 학습 버킷 배정 (classifier 모드) | OOF 확률만 사용. 최종 `.cbm` 재예측 금지 |
| 병렬 청크 경계 | overlap 6,000봉 + 주봉은 부모가 전역 계산 후 배포 |
| Optuna 검증 ∩ 임계값 홀드아웃 | **[수정됨, f9017a5]** Optuna는 prefix(앞 80%)만 입력받음 — 임계값/지표 홀드아웃(뒤 20%)은 HPO가 못 봄 |

### ② 비정상성(Non-stationarity) 대응

| 항목 | 상태 |
|---|---|
| 절대 가격 수준 피처 | **9개 비활성화**(era proxy 방지). 상대/비율 대응물만 활성 |
| 정규화 | z-score(20/60봉 롤링), 비율(SMA 대비), 변동성 조정(rv/atr로 나눔) 광범위 적용 |
| 미결제약정 | 절대 수준 미노출. 변화율 + trailing 1일 z-score만 |
| 차분 | 명시적 차분은 없음. 수익률·변화율·기울기가 그 역할 |
| **⚠️ 레짐 디텍터 정규화** | **2020-12~2024-12 전 구간 단일 (mean, std)**. 롤링/확장 윈도우 아님. 2021 불장·2022 베어·2023 횡보의 변동성 수준이 하나의 기준에 묶임 |
| **⚠️ 클리핑 경계** | `ratio` ±100 등 고정 상수. 6년에 걸쳐 분포가 이동하면 특정 시기만 포화될 여지 |

### ③ 데이터 불균형과 생존 편향

| 항목 | 상태 |
|---|---|
| 생존 편향 | **해당 없음** — BTCUSDT 단일 심볼, 상장폐지 없음 |
| 클래스 불균형 | **의도적으로 미보정**(`auto_class_weights_enabled=False`). 확률 캘리브레이션 보호가 이유 |
| 레짐별 표본 수 | 최소 `--min-regime-rows`(train 기본 80) 미달 시 skip + 경고. **2025 백테스트 구간은 range가 약 91%** |
| range 게이트 후 실거래 가능 바 | 0.25/0.75 밴드 밖만 진입 가능 → **실질 모집단이 크게 축소**. 정확한 비율은 `calibration_report.json`의 `enterable_bars` 참조 |
| 사이드 결손 | `missing_side_models`로 보고. 결손 사이드는 신호를 못 내므로 skip 카운터에도 안 잡히는 것을 별도 필드로 가시화 |
| 워밍업 손실 | 앞 **504,000봉(350일)** 폐기 → 명목 5년 학습이 실제 4년 |
| F12 오프라인 상수화 | **[수정됨, f9017a5]** fallback/mock 피처는 기본으로 학습 매트릭스에서 제외 (`--keep-fallback-features`로 구동작 복원) |
| F18 상수화 | **[수정됨, f9017a5]** rule 모드에서는 regime_classifier 소스가 미가용으로 잡혀 3개가 fallback 목록에 들어가 **학습에서 제외**됨. classifier 모드에서는 실값 OOF가 병합되어 소스가 available → 정상 투입 유지 |

### ④ 과적합 가능성

| 항목 | 상태 |
|---|---|
| 규제 | `l2_leaf_reg` 1~50(log), `random_strength` 0.1~10(log), `bagging_temperature` 0~5, `min_data_in_leaf` 20~500, `depth` 3~8 — Optuna 탐색 대상 |
| 조기 종료 | trial은 `eval_set` + `use_best_model`. 최종 refit은 `best_iteration+1`로 캡 |
| **⚠️ 교차 검증** | **레짐 인식 경로(= 배포 모델)는 walk-forward CV를 쓰지 않음.** 레짐별 단일 80/20 연대순 홀드아웃 + 퍼지 갭. purged/combinatorial CV 코드는 존재하나 **비레짐 경로에서만** 동작 |
| Optuna 표본 재사용 | **[수정됨, f9017a5]** HPO는 prefix(앞 80%)만; 임계값·홀드아웃 보고용 꼬리 20%는 HPO 미노출 |
| 임계값 과적합 방어 | 임계값은 **prefix-only 진단 모델**의 홀드아웃에서 선택(배포 모델 in-sample 아님). 최소 거래수 5% 하한 |
| 시간 질서 | 모든 분할이 연대순. 랜덤 분할 없음. 퍼지 갭 = `min(label_horizon, (n−split)//4)` |
| 샘플 중복 | uniqueness 가중치는 **비레짐 경로에만** 적용. 레짐 경로는 겹치는 트리플 배리어 창을 할인하지 않음 |
| 보고 지표의 정직성 | 측정 불가는 전부 NaN/null(0.0 금지). 20거래 미만 리스크 지표 차단. 축퇴 비교는 승자 미선정 |

---

## 14. 재현 명령

```powershell
# 전체 (Windows)
powershell -ExecutionPolicy Bypass -File run_full_pipeline.ps1

# 주요 환경변수 기본값
$Horizon = 60 ; $LabelTpPct = "0.010" ; $LabelSlPct = "0.005"
$FeePerSide = "0.0002" ; $SlippagePerSide = "0.0002"   # → RoundTripCost 0.0008
$ThresholdObjective = "trading_pnl" ; $ThresholdFloor = "0.0"
$RegimeMode = "rule" ; $RuleRegimeConfig = "configs/rule_regime.json"
$KellySizing = $true ; $KellyMultiplier = "0.5" ; $KellyLookbackBars = "1440"
$MhHorizons = "30,60,90"
```

### 산출 아티팩트

| 경로 | 내용 |
|---|---|
| `artifacts/btcusdt_2020_2025.parquet` | 결합 캔들 |
| `artifacts/ic_report/ic_report.csv` | 피처별 IC + fold 안정성 + 누수 플래그 |
| `artifacts/regime_stacking_model/regime_run_summary.json` | 레짐 카운트, 적합된 디텍터, 레짐별 홀드아웃 지표, `selected_thresholds`, Optuna 리포트, 라벨 배리어 |
| `artifacts/unified_model/` | 비레짐 베이스라인 (fold 지표, 캘리브레이션 리포트 포함) |
| `artifacts/backtest_results/backtest_summary.json` | 거래 전체 + 레짐 커버리지 + Kelly 진단 + `run_config` |
| `artifacts/backtest_results/calibration_report.json` | **reliability curve + decision band (엣지 판정)** |
| `artifacts/backtest_results/edge_validation/edge_validation_report.json` | 비용 스트레스 + 4-way 라우팅 |
| `artifacts/shuffled_control_model/` | **[신설, f9017a5]** Phase 3.8 셔플 라벨 대조군 모델 (`shuffled_labels=true` 각인) |
| `artifacts/backtest_results_shuffled_control/` | **[신설, f9017a5]** Phase 4.7 대조군 백테스트 — 본 모델과 비슷하면 엣지는 가짜 |
| `artifacts/backtest_results_multi_horizon/` | 파일럿 백테스트 |

---

## 15. 이 문서가 제공하지 않는 것

- 실제 수치 결과 전체(레짐별 행 수, 홀드아웃 F1, 거래 목록). §0·§4에 최신 런의 핵심 수치만 요약. 위 아티팩트 JSON/CSV를 함께 보내면 정밀도가 올라감.
- `shuffled_label_control` 결과 — f9017a5부터 Phase 3.8/4.7로 배선됐으나 **수정판 파이프라인이 아직 완주되지 않아 결과 없음**.
- `seed_stability` / `feature_group_ablation` 결과 — 라이브러리 전용, 실행된 적 없음.
