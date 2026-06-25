# CatBoost 스캘핑 전략 구현 계획

**작성일:** 2026-06-25  
**기준 문서:** `catboost_scalping_applicability_review.md`  
**구현 범위:** Phase 0 ~ Phase 3 (검토 보고서 기준)  
**목표:** LONG/SHORT 분리 모델 + EV 기반 진입 게이트 구현

---

## 구현 로드맵

### Phase 0: 기존 구조 누수 검증 (1-2일)

**목표:** 기존 triple-barrier / stacking / 라벨링 구조의 데이터 누수 여부 확인

| 검증 항목 | 방법 | 완료 기준 |
|---|---|---|
| label=1 의미 확인 | 코드 리뷰 | LONG TP만 의미하는지 확인 |
| direction/profitability 중복 확인 | 타겟 상관관계 분석 | 중복 학습 여부 확인 |
| meta_model OOF 학습 확인 | 코드 리뷰 | Out-of-fold prediction 사용 여부 |
| stacking leakage 확인 | 학습/검증 데이터 분리 확인 | 미래 정보 미사용 확인 |
| triple-barrier 동시 터치 처리 | 코드 리뷰 | high/low 동시 터치 시 처리 방식 확인 |
| 현재 봉 high/low/close 사용 시점 | 코드 리뷰 | 미래 데이터 미사용 확인 |

**출력물:** `docs/LEAKAGE_VERIFICATION_REPORT.md`

---

### Phase 1: 스캘핑 피처 추가 (2-3일)

**목표:** RSI, MACD, Bollinger, VWAP, 시간/세션 피처 추가

#### 1.1 시간/세션 피처
```
hour                    - 0~23
minute                  - 0~59
day_of_week             - 0(월)~6(일)
session_asia            - 00:00~08:00 UTC
session_europe          - 08:00~16:00 UTC
session_us              - 16:00~00:00 UTC
session_overlap         - 08:00~16:00 (유럽+미국 겹침)
weekend_flag            - 토/일 여부
```

#### 1.2 기술 지표 피처
```
RSI
  rsi_7                 - 7봉 RSI
  rsi_14                - 14봉 RSI

MACD
  macd_line             - MACD 선
  macd_signal           - Signal 선
  macd_hist             - Histogram

Bollinger Band
  bb_width_20           - (upper - lower) / middle
  bb_percent_b          - (close - lower) / (upper - lower)

EMA
  ema_5_slope           - EMA 5 기울기
  ema_20_slope          - EMA 20 기울기
  ema_60_slope          - EMA 60 기울기
```

#### 1.3 VWAP 피처
```
rolling_vwap_20         - 20봉 rolling VWAP
rolling_vwap_60         - 60봉 rolling VWAP
rolling_vwap_240        - 240봉 rolling VWAP
price_vs_rolling_vwap_20   - (close - vwap) / vwap
price_vs_rolling_vwap_60   - (close - vwap) / vwap
price_vs_rolling_vwap_240  - (close - vwap) / vwap
```

**수정 파일:**
- `btcusdt_quant/feature_registry.py` - 새 피처 등록
- `btcusdt_quant/dataset.py` - 피처 계산 로직 추가
- `tests/test_v718.py` - 피처 계산 테스트 추가

---

### Phase 2: LONG/SHORT 라벨 분리 (3-5일)

**목표:** 기존 단일 라벨을 LONG 성공/SHORT 성공 분리 라벨로 변경

#### 2.1 라벨 구조 변경

**기존:**
```python
LabeledRow.label          # 1=성공, 0=실패 (LONG 기준)
LabeledRow.targets["direction"]       # 1=상승, 0=하락
LabeledRow.targets["profitability"]   # triple-barrier 결과
```

**신규:**
```python
LabeledRow.targets["long_success"]    # LONG 진입 시 TP 먼저 도달: 1, 아니면 0
LabeledRow.targets["short_success"]   # SHORT 진입 시 TP 먼저 도달: 1, 아니면 0
LabeledRow.targets["direction"]       # 유지 (미래 수익률 방향)
LabeledRow.targets["profitability"]   # 유지 (기존 triple-barrier)
```

#### 2.2 Triple-Barrier 라벨링 수정

**LONG 라벨 (label_long_success):**
```
현재 시점에서 LONG 진입 가정
TP = +0.15%  (또는 grid 후보 중 하나)
SL = -0.10%  (또는 grid 후보 중 하나)
Timeout = horizon 봉

TP 먼저 도달 → 1
SL 먼저 도달 → 0
Timeout → 0 또는 제외
```

**SHORT 라벨 (label_short_success):**
```
현재 시점에서 SHORT 진입 가정
TP = -0.15%  (가격 하띝이 수익)
SL = +0.10%  (가격 상승이 손실)
Timeout = horizon 봉

TP 먼저 도달 → 1
SL 먼저 도달 → 0
Timeout → 0 또는 제외
```

#### 2.3 Grid Sweep 지원

**Horizon 후보:** 5, 10, 15, 30 (분)
**TP/SL 후보:**
- 0.12% / 0.08%
- 0.15% / 0.10%
- 0.20% / 0.12%
- 0.30% / 0.15%

**Timeout 처리 방식:**
- 방식 A: Timeout = 0 (실패)
- 방식 B: Timeout 샘플 제외
- 방식 C: Timeout 중 순수익률이 비용 이상이면 성공

**수정 파일:**
- `btcusdt_quant/dataset.py` - `triple_barrier_label()` 함수 수정
- `btcusdt_quant/dataset.py` - `attach_labels()` 함수 수정
- `btcusdt_quant/cli.py` - grid 파라미터 CLI 인자 추가
- `tests/test_v718.py` - 라벨 분리 테스트 추가

---

### Phase 3: 모델 구조 변경 (5-10일)

**목표:** LONG/SHORT 성공 확률 분리 모델 + EV 기반 진입 게이트

#### 3.1 모델 구조

**기존:**
```
direction_model         → 방향 예측
profitability_model     → 수익성 예측
meta_model             → 최종 확률 결합
```

**신규:**
```
long_success_model      → LONG 진입 시 TP 먼저 도달 확률
short_success_model     → SHORT 진입 시 TP 먼저 도달 확률
(long_ev_model)         → LONG 기대수익 회귀 (선택)
(short_ev_model)        → SHORT 기대수익 회귀 (선택)
```

#### 3.2 EV 기반 진입 게이트

**비용 구성:**
```
fee_entry   = 0.02%     # Binance taker fee
fee_exit    = 0.02%     # Binance taker fee
slippage    = 0.01%     # 추정 슬리피지
spread_cost = 0.01%     # 추정 스프레드 비용
safety_margin = 0.02%   # 안전마진

total_cost = fee_entry + fee_exit + slippage + spread_cost
```

**Net TP/SL 계산:**
```
net_long_tp  = gross_tp - total_cost    # 예: +0.15% - 0.06% = +0.09%
net_long_sl  = gross_sl - total_cost    # 예: -0.10% - 0.06% = -0.16%
net_short_tp = gross_tp - total_cost    # 예: +0.15% - 0.06% = +0.09%
net_short_sl = gross_sl - total_cost    # 예: -0.10% - 0.06% = -0.16%
```

**EV 계산 (확률 기반):**
```python
long_ev = long_prob * net_long_tp - (1.0 - long_prob) * abs(net_long_sl)
short_ev = short_prob * net_short_tp - (1.0 - short_prob) * abs(net_short_sl)
```

**진입 조건:**
```python
if long_ev > min_ev and long_prob > long_threshold:
    signal = "LONG"
elif short_ev > min_ev and short_prob > short_threshold:
    signal = "SHORT"
else:
    signal = "NO_TRADE"
```

#### 3.3 Probability Calibration

**검토 항목:**
- Platt scaling 적용 여부
- Isotonic calibration 적용 여부
- Validation OOF 기반 calibration

**목표:** CatBoost predict_proba 출력이 실제 확률과 일치하도록 보정

**수정 파일:**
- `btcusdt_quant/training.py` - `_train_single_regime()` 수정
- `btcusdt_quant/ensemble.py` - StackingEnsembleAdapter 수정
- `btcusdt_quant/models.py` - ModelAdapter에 calibration 메서드 추가
- `btcusdt_quant/live.py` - 추론 시 EV 계산 로직 추가
- `btcusdt_quant/cli.py` - min_ev, threshold 파라미터 추가

---

## 구현 순서 및 의존성

```
Phase 0 (누수 검증)
    ↓
Phase 1 (피처 추가)
    ↓
Phase 2 (라벨 분리)
    ↓
Phase 3 (모델 변경)
```

**핵심 원칙:**
- 각 Phase별로 독립적인 브랜치 또는 커밋 단위로 관리
- Phase 완료 시마다 테스트 실행 및 성능 검증
- Phase 3 진행 전 Phase 2 라벨의 의미적 정확성 확인 필수

---

## 파일 수정 예상 목록

### Phase 0
- `docs/LEAKAGE_VERIFICATION_REPORT.md` (신규)

### Phase 1
- `btcusdt_quant/feature_registry.py`
- `btcusdt_quant/dataset.py`
- `tests/test_v718.py`

### Phase 2
- `btcusdt_quant/dataset.py`
- `btcusdt_quant/cli.py`
- `tests/test_v718.py`

### Phase 3
- `btcusdt_quant/training.py`
- `btcusdt_quant/ensemble.py`
- `btcusdt_quant/models.py`
- `btcusdt_quant/live.py`
- `btcusdt_quant/cli.py`
- `tests/test_v718.py`

**총 예상 수정 파일:** 7개 파일

---

## 테스트 전략

### 단위 테스트
- 각 새 피처의 계산 정확성 (RSI, MACD, Bollinger, VWAP)
- LONG/SHORT 라벨 분리 정확성 (triple-barrier 시뮬레이션)
- EV 계산 로직 정확성

### 통합 테스트
- 전체 파이프라인: collect → train → backtest
- LONG/SHORT 모델 학습 및 추론
- EV 기반 진입 게이트 동작 확인

### 백테스트 검증
- 기존 모델 vs 신규 모델 성능 비교
- Sharpe, MDD, win rate, profit factor 비교
- 거래 횟수 및 평균 수익 비교

---

## 완료 기준

- [ ] Phase 0: 누수 검증 완료 및 보고서 작성
- [ ] Phase 1: 모든 새 피처가 정확히 계산되고 테스트 통과
- [ ] Phase 2: LONG/SHORT 라벨이 분리되어 저장됨
- [ ] Phase 3: LONG/SHORT 모델이 개별적으로 학습됨
- [ ] Phase 3: EV 기반 진입 게이트가 백테스트에서 동작함
- [ ] 전체 테스트 280+/280 통과
- [ ] GitHub에 push 완료

---

## 리스크 및 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| 기존 라벨링 버그 발견 | Phase 2 지연 | Phase 0에서 충분히 검증 후 진행 |
| LONG/SHORT 라벨 불균형 | 모델 편향 | class_weight 또는 샘플링 조정 |
| EV 계산 왜곡 | 진입 게이트 오작동 | calibration 필수 적용 |
| 새 피처 계산 오류 | 특성 품질 저하 | 단위 테스트로 각 피처 검증 |
| 모델 학습 실패 | 아티팩트 미생성 | fallback 체인 유지 |

---

**작성:** Sisyphus AI  
**기준 문서:** `catboost_scalping_applicability_review.md`
