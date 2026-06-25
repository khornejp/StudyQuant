# CatBoost Bitcoin Scalping 전략 적용성 분석 보고서

**분석 일자:** 2026-06-25  
**대상 저장소:** StudyQuant (BTCUSDT 1m Quant Trading System v7.18)  
**분석 대상:** `catboost_bitcoin_scalping_strategies.md` vs 현재 코드베이스

---

## 1. 현재 코드베이스 아키텍처 요약

### 1.1 특성 체계 (115개, F01-F13)

| 카테고리 | 코드 | 개수 | 주요 내용 |
|---|---|---|---|
| **F01** 가격/수익률 | f01 | 12 | return_1/3/5/10/15/30/60, log_return, momentum, rolling min/max |
| **F02** 추세/MA | f02 | 14 | SMA/EMA 비율, trend_slope_10/20/30, distance_to_high/low, prior_horizon_trend |
| **F03** 변동성 | f03 | 16 | rv_5/10/15/30, ATR_14, Parkinson vol, Garman-Klass, HAR-RV |
| **F04** 거래량/흐름 | f04 | 14 | volume_ratio, taker_ratio, trade_count, volume_per_trade, volume_shock |
| **F05** 캔들 구조 | f05 | 10 | range/body/wick ratios, close_location, inside/outside bars |
| **F06** 갭/데이터 품질 | f06 | 8 | gap_flag, gap_ratio, max_gap_run, repaired, gap_length, gap_pressure |
| **F07** 국면 정규화 | f07 | 6 | close_zscore, volume_zscore, rv_zscore, volatility_regime |
| **F08** 변동성조정 수익률 | f08 | 6 | return/vol_adjusted, momentum/vol_adjusted |
| **F09** 변동성조정 추세 | f09 | 6 | zscore_adjusted, ma_spread_adjusted |
| **F10** 변동성조정 캔들/흐름 | f10 | 6 | range/body/volume/trade/taker_adjusted |
| **F11** 미시구조 | f11 | 10 | spread, spread_bps, book_imbalance, bid/ask_ratio, microprice_deviation |
| **F12** 거래소/펀딩 안전 | f12 | 12 | ADL, funding_rate, mark_basis, premium_index, leverage_utilization |
| **F13** 주간 고차원 | f13 | 7 | weekly_ma20/50_slope, ma_cross, weekly_drawdown, vol_contraction |

**총 115개 활성 특성**

### 1.2 모델 구조

```
[데이터 입력]
    ↓
[특성 계산: 115개 F01-F13]
    ↓
[국면 분류: RegimeDetector 또는 UserRegime]
    ├─ up (상승)
    ├─ down (하락)  
    └─ range (횡보)
         ↓
[Per-Regime Ensemble: 3개 모델]
    ├─ CatBoost Fast (빠른 학습)
    ├─ CatBoost Deep (깊은 학습)
    └─ LightGBM
         ↓
[Stacking Ensemble]
    ├─ direction_model (미래 방향 예측)
    ├─ profitability_model (수익성 예측)
    └─ meta_model (최종 확률 결합)
         ↓
[라이브 추론: TP/SL 브라켓 주문]
```

### 1.3 라벨링 방식

**Triple-Barrier (Long-oriented)**
- **Horizon:** 60분봉 (1시간)
- **TP:** +0.3% (진입가 대비)
- **SL:** -0.15% (진입가 대비)
- **Timeout:** horizon 도달 시 threshold(0.1%) 초과 여부
- **출력:** 
  - `label`: 1 (TP 먼저) / 0 (SL 먼저 또는 타임아웃)
  - `direction`: 1 (미래 수익률 > 0) / 0 (< 0)
  - `profitability`: triple-barrier 결과

**⚠️ 한계:** Short-side 라벨링 없음, 비용(수수료+슬리피지) 미반영

### 1.4 교차 검증

- Walk-forward validation
- Combinatorial purged CV (CPCV)
- Sample uniqueness weighting
- Embargo 적용

---

## 2. 전략 문서(catboost_bitcoin_scalping_strategies.md) 핵심 요약

### 2.1 추천 전략 우선순위

| 순위 | 전략 | CatBoost 적합도 | 핵심 아이디어 |
|---|---|---|---|
| 1 | 변동성 압축 후 확장 돌파 | ⭐⭐⭐⭐⭐ | 저변동성 구간 → 거래량+변동성 동반 증가 시 돌파 |
| 2 | 마이크로 추세 눌림목 | ⭐⭐⭐⭐⭐ | 상위 프레임 추세 → 하위 프레임 눌림 후 재진행 |
| 3 | 가짜 돌파/유동성 스윕 탐지 | ⭐⭐⭐⭐ | 고점/저점 살집 돌파 후 반전 패턴 필터 |
| 4 | 체결강도 기반 스캘핑 | ⭐⭐⭐⭐ | buy/sell volume ratio, CVD, 대량 체결 |
| 5 | 호가창 불균형 스캘핑 | ⭐⭐⭐⭐ | bid/ask depth imbalance, spread 변화 |
| 6 | 평균회귀 스캘핑 | ⭐⭐⭐ | VWAP/EMA 과도 이탈 후 회귀 |
| 7 | 청산/OI 기반 필터 | ⭐⭐⭐ | OI, funding, liquidation 보조 필터 |

### 2.2 추천 모델 구조

```
Stage 1: 시장 국면 분류 (CatBoostClassifier)
    ├─ ranging
    ├─ trending_up
    ├─ trending_down
    ├─ high_volatility
    └─ squeeze

Stage 2: 진입 성공 확률 예측 (분리 모델)
    ├─ LONG 성공 확률 (CatBoostClassifier)
    └─ SHORT 성공 확률 (CatBoostClassifier)

Stage 3: 기대수익 필터 (CatBoostRegressor)
    └─ expected_net_return > 수수료 + 슬리피지 + 안전마진

Optional: CatBoostRanker (다중 후보 중 최상위 선택)
```

### 2.3 추천 라벨 설계

**LONG 진입 성공 여부:**
```
TP = +0.15%
SL = -0.10%
Timeout = 5분

TP 먼저 도달 → 1 (성공)
SL 먼저 도달 → 0 (실패)
Timeout → 0 (실패 또는 제외)
```

**SHORT 진입 성공 여부:**
```
TP = -0.15%
SL = +0.10%
Timeout = 5분

TP 먼저 도달 → 1 (성공)
SL 먼저 도달 → 0 (실패)
Timeout → 0 (실패 또는 제외)
```

**핵심 원칙:**
> CatBoost에서는 다음 가격을 맞히는 모델보다,  
> 지금 진입했을 때 TP가 SL보다 먼저 맞을 확률을 예측하는 모델이 더 현실적이다.

---

## 3. 갭 분석 (Gap Analysis)

### 3.1 구조적 격차

| 전략 문서 요구사항 | 현재 코드베이스 | 격차 수준 |
|---|---|---|
| **LONG/SHORT 분리 모델** | 없음 (direction + profitability만) | 🔴 **높음** |
| **expected_net_return 회귀** | 없음 | 🟡 **중간** |
| **CatBoostRanker** | 없음 | 🔴 **높음** |
| **Short-side triple-barrier** | 없음 (Long-biased) | 🔴 **높음** |
| **비용 반영 라벨** | 없음 | 🟡 **중간** |
| **시장 국면 CatBoost 분류** | 휴리스틱 규칙 기반 | 🟡 **중간** |

### 3.2 파라미터 격차

| 항목 | 전략 문서 | 현재 코드 | 적용 난이도 |
|---|---|---|---|
| **Horizon** | 3-5분 | 60분 (1시간) | 🟢 쉬움 |
| **TP/SL (Long)** | +0.15% / -0.10% | +0.3% / -0.15% | 🟢 쉬움 |
| **TP/SL (Short)** | -0.15% / +0.10% | 없음 | 🟡 중간 |
| **Timeout 처리** | 제외 또는 실패 | threshold 기반 | 🟡 중간 |
| **NO_TRADE 비중** | Downsampling/가중치 | 미처리 | 🟡 중간 |

### 3.3 특성 격차

| 전략 문서 피처 그룹 | 현재 상태 | 적용 난이도 |
|---|---|---|
| **Bollinger Band** (width, %b) | ❌ 없음 | 🟢 쉬움 (추가) |
| **VWAP** (price_vs_vwap) | ❌ 없음 | 🟢 쉬움 (추가) |
| **RSI** (7, 14) | ❌ 없음 | 🟢 쉬움 (추가) |
| **MACD** (histogram) | ❌ 없음 | 🟢 쉬움 (추가) |
| **ADX** (14) | ❌ 없음 | 🟢 쉬움 (추가) |
| **EMA** (5, 20, 60 slope) | ⚠️ 일부 (SMA 기반) | 🟢 쉬움 (변경) |
| **시간/세션** (hour, session) | ❌ 없음 | 🟢 매우 쉬움 |
| **호가창 depth** (5단, 10단) | ⚠️ F11 일부 | 🟡 중간 (데이터 필요) |
| **Tick/CVD** (1s, 5s) | ❌ 없음 | 🔴 어려움 (데이터 필요) |
| **OI/청산/롱숏비율** | ⚠️ F12 일부 | 🟡 중간 (API 연동) |

---

## 4. 적용 우선순위 로드맵

### Phase 1: 파라미터 조정 + 피처 추가 (즉시 적용 가능, 1-2일)

**작업 항목:**
1. **Horizon 축소**: 60분 → 5분 (스캘핑 목적)
2. **TP/SL 조정**: Long +0.15% / -0.10%
3. **시간 피처 추가**: hour, minute, day_of_week, session_asia/europe/us
4. **기술적 지표 추가**: RSI_7, RSI_14, MACD, Bollinger_width, VWAP
5. **EMA 개선**: EMA 5/20/60 slope 추가

**예상 효과:** 스캘핑 시간대 맞춤, 기술적 지표 기반 전략 지원

### Phase 2: 모델 구조 개편 (1-2주)

**작업 항목:**
1. **LONG/SHORT 분리 모델**:
   - `long_model`: LONG 진입 시 TP 먼저 도달 확률
   - `short_model`: SHORT 진입 시 TP 먼저 도달 확률
   - 각각 CatBoostClassifier 이진 분류

2. **expected_net_return 회귀 모델**:
   - CatBoostRegressor 추가
   - 수수료(0.02%×2) + 슬리피지(0.01%) + 안전마진(0.02%) 반영
   - EV > 0일 때만 진입 게이트

3. **Short-side triple-barrier 라벨**:
   - 기존 라벨링을 long-only에서 long/short dual로 확장
   - `label_long`, `label_short` 별도 생성

4. **비용 반영 라벨**:
   - 미래 가격이 아닌, TP/SL 도달 확률을 비용 차감 후 계산

**예상 효과:** 전략 문서의 핵심 구조 (Stage 1-2-3) 구현

### Phase 3: 고급 피처 + Ranker (2-4주)

**작업 항목:**
1. **호가창 depth 피처**: Binance order book API 연동
2. **Tick/CVD 피처**: 체결 데이터 수집 및 집계
3. **OI/청산 데이터**: 선물 특화 데이터 연동
4. **CatBoostRanker**: 다중 후보(돌파/눌림/반전) 중 최상위 선택

**예상 효과:** 고급 스캘핑 전략 지원, 미시구조 기반 진입

### Phase 4: 시장 국면 CatBoost 분류 (선택적)

**작업 항목:**
1. **국면 분류 모델**: 휴리스틱 규칙 → CatBoostClassifier 전환
2. **국면 세분화**: up/down/range → squeeze/trending_up/trending_down/high_vol/ranging
3. **국면별 threshold 최적화**: per-regime TP/SL/threshold 튜닝

**예상 효과:** 더 정교한 국면 대응, per-regime 성능 향상

---

## 5. 구현 예시

### 5.1 LONG/SHORT 분리 모델 의사결정 흐름

```python
# 현재 (단일 모델)
direction_prob = model.predict_proba(features)  # 0=하락, 1=상승
profitability_prob = model.predict_proba(features)  # 0=실패, 1=성공
meta_prob = meta_model.predict_proba([direction_prob, profitability_prob])

# 전략 문서 방식 (분리 모델)
long_success_prob = long_model.predict_proba(features)  # LONG 진입 시 TP 먼저
short_success_prob = short_model.predict_proba(features)  # SHORT 진입 시 TP 먼저
expected_return = return_model.predict(features)  # CatBoostRegressor

# 진입 결정
if long_success_prob > threshold and expected_return > cost + margin:
    enter_long()
elif short_success_prob > threshold and expected_return > cost + margin:
    enter_short()
else:
    no_trade()
```

### 5.2 비용 반영 라벨 예시

```python
# 현재 (비용 미반영)
target_return = (future_close - entry) / entry  # 단순 수익률

# 전략 문서 방식 (비용 반영)
fee_rate = 0.0002  # 0.02% (Binance taker fee)
slippage = 0.0001  # 0.01% (추정 슬리피지)
safety_margin = 0.0002  # 0.02% (안전마진)
total_cost = fee_rate * 2 + slippage + safety_margin  # 진입+청산 수수료

# 라벨: TP가 SL보다 먼저 도달 AND (TP - total_cost) > 0
label = 1 if tp_first and (tp_pct - total_cost) > 0 else 0
```

---

## 6. 현재 코드베이스에서의 제약사항

### 6.1 데이터 소스
- **1분봉 OHLCV**: ✅ Binance daily archive 지원
- **호가창**: ❌ 실시간 WebSocket만 가능 (히스토리컬 수집 미구현)
- **Tick 체결**: ❌ 미지원
- **OI/청산/롱숏비율**: ⚠️ F12 일부 지원 (funding_rate, mark_basis 등)

### 6.2 계산 성능
- **병렬 처리**: ✅ ProcessPoolExecutor 지원 (50,000+ 캔들 시 자동)
- **GPU**: ✅ CatBoost GPU 지원 (CUDA), CPU 폴백
- **메모리**: ⚠️ 대용량 데이터셋 시 chunk 처리 권장

### 6.3 실전 운영
- **Mock Exchange**: ✅ 기본값, 안전한 백테스트/데모
- **Binance Testnet**: ✅ 서명된 주문, API 키 필요
- **Binance Production**: ⚠️ 승인 아티팩트 + 명시적 확인 필요
- **TP/SL 브라켓**: ✅ reduce-only 주문 지원
- **위험 관리**: ✅ 드로다운 3단계, ADL 모니터링

---

## 7. 결론

### 7.1 적용 가능성 평가

| 전략 | 적용 가능성 | 구현 복잡도 | 예상 효과 |
|---|---|---|---|
| 변동성 압축 후 돌파 | ⭐⭐⭐⭐⭐ | 낮음 | 높음 (피처 대부분 존재) |
| 마이크로 추세 눌림목 | ⭐⭐⭐⭐⭐ | 낮음 | 높음 (추세 피처 존재) |
| 가짜 돌파 탐지 | ⭐⭐⭐⭐ | 중간 | 중간 (라벨링 수정 필요) |
| LONG/SHORT 분리 모델 | ⭐⭐⭐⭐ | 중간 | 높음 (구조 변경 필요) |
| expected_net_return | ⭐⭐⭐ | 중간 | 중간 (회귀 모델 추가) |
| 호가창 스캘핑 | ⭐⭐ | 높음 | 높음 (데이터 소스 제약) |
| 체결강도 스캘핑 | ⭐ | 높음 | 높음 (데이터 소스 제약) |
| CatBoostRanker | ⭐⭐⭐ | 높음 | 중간 (후보 체계 구축 필요) |

### 7.2 핵심 권장사항

**즉시 적용 (Phase 1):**
1. Horizon 5분 + TP/SL 0.15%/0.10% 조정
2. 시간/세션 피처 추가
3. RSI/MACD/Bollinger/VWAP 피처 추가

**단기 적용 (Phase 2):**
4. LONG/SHORT 분리 모델 구조 도입
5. Short-side triple-barrier 라벨 추가
6. 비용 반영 라벨 계산

**중기 적용 (Phase 3-4):**
7. 호가창/체결 데이터 연동
8. CatBoostRanker 실험
9. 국면 분류 모델 CatBoost 전환

### 7.3 최종 판단

> 현재 코드베이스는 전략 문서의 **Phase 1-2**를 구현하기에 충분한 기반을 갖추고 있다.  
> 특히 CatBoost 기반 regime-aware ensemble 구조, 115개 피처, triple-barrier 라벨링,  
> walk-forward CV 등 핵심 인프라가 이미 구축되어 있다.
>
> **핵심은 라벨링과 모델 구조의 방향 전환**이다:  
> - "다음 가격 예측" → "TP가 SL보다 먼저 맞을 확률 예측"  
> - "단일 모델" → "LONG/SHORT 분리 모델"  
> - "비용 무시" → "비용 반영 EV 게이트"
>
> 이 세 가지 전환만 이루어지면 전략 문서의 핵심 철학이 코드베이스에 반영된다.

---

## 부록 A: 현재 vs 전략 문서 피처 매핑

| 전략 문서 피처 | 현재 코드 피처 | 상태 |
|---|---|---|
| return_1/3/5/10 | F01 return_1/3/5/10/15/30/60 | ✅ |
| atr_14/30 | F03 atr_14, rv_15/30 | ✅ |
| realized_vol_10/30 | F03 rv_10/30 | ✅ |
| volume_zscore_20 | F04 volume_ratio | ⚠️ 유사 |
| ema_5_slope | F02 trend_slope_10 | ⚠️ 유사 |
| price_vs_vwap | ❌ 없음 | ❌ |
| rsi_7/14 | ❌ 없음 | ❌ |
| macd_hist | ❌ 없음 | ❌ |
| bb_width_20 | ❌ 없음 | ❌ |
| breakout_distance_high_20 | F02 distance_to_high_20 | ✅ |
| pullback_depth | ❌ 없음 | ❌ |
| volume_decline_ratio | F04 volume_shock | ⚠️ 유사 |
| hour / session_asia | ❌ 없음 | ❌ |
| spread | F11 spread | ✅ |
| book_imbalance_5 | F11 book_imbalance | ✅ |
| cvd_5s | ❌ 없음 | ❌ |
| open_interest_change | F12 OI 관련 | ⚠️ 일부 |
| funding_rate | F12 funding_rate | ✅ |

---

*본 보고서는 2026-06-25 기준 코드베이스 분석 결과입니다.*
