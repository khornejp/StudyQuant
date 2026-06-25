# 데이터 누수 검증 보고서 (Phase 0)

**검증 일자:** 2026-06-25  
**검증 대상:** BTCUSDT 1m Quant Trading System v7.18  
**검증 범위:** triple-barrier 라벨링, stacking ensemble, 피처 계산

---

## 1. Triple-Barrier 라벨링 검증

### 1.1 구현 코드

```python
def triple_barrier_label(
    entry_index: int,
    candles: Sequence[data.Candle],
    horizon: int,
    label_threshold: float,
    tp_pct: float,
    sl_pct: float,
    target_return: float,
) -> tuple[int, str]:
    entry_price = candles[entry_index].close
    tp_level = entry_price * (1.0 + tp_pct)
    sl_level = entry_price * (1.0 - sl_pct)
    gap_seen = False
    for future_index in range(entry_index + 1, entry_index + horizon + 1):
        candle = candles[future_index]
        if candle.gap_flag == 1:
            gap_seen = True
        tp_touched = candle.high >= tp_level
        sl_touched = candle.low <= sl_level
        if tp_touched and sl_touched:
            if candle.close > candle.open:
                return 1, "tp_first"
            if candle.close < candle.open:
                return 0, "sl_first"
            return 0, "ambiguous_path"
        if tp_touched:
            return 1, "tp_first"
        if sl_touched:
            return 0, "gap_cross_sl" if candle.gap_flag == 1 else "sl_first"
    timeout_reason = "gap_cross_timeout" if gap_seen else "timeout_no_tp"
    return (1 if target_return > label_threshold else 0), timeout_reason
```

### 1.2 검증 결과

| 항목 | 상태 | 설명 |
|---|---|---|
| **미래 캔들 접근** | ✅ 안전 | `entry_index + 1`부터 `entry_index + horizon`까지만 접근. 라벨 계산에 필요한 미래 데이터만 사용 |
| **entry_price 사용** | ⚠️ 주의 | `candles[entry_index].close`를 진입가로 사용. 이는 **현재 봉의 종가**를 의미하며, 실시간 추론 시에는 **아직 확정되지 않은 가격**일 수 있음 |
| **동시 터치 처리** | ⚠️ 한계 | 동일 캔들에서 TP와 SL이 동시에 터치되면 `close > open`으로 판단. 이는 **실제 체결 순서를 알 수 없는 근사치** |
| **Timeout 처리** | ✅ 안전 | `target_return`은 `attach_labels()`에서 미리 계산되며, horizon 시점의 종가만 사용 |
| **라벨 의미** | ⚠️ Long-biased | `label=1`은 LONG 진입 기준 TP 먼저 도달을 의미. SHORT 진입 시나리오는 고려되지 않음 |

### 1.3 발견된 이슈

**이슈 1: entry_price 시점 (중요도: 중간)**
```
현재: entry_price = candles[entry_index].close
문제: 실시간 추론 시 현재 봉의 close는 아직 확정되지 않음
권장: 실시간 추론 시는 open 또는 현재가를 사용하도록 분리 필요
```

**이슈 2: 동시 터치 시 close/open 판단 (중요도: 낮음)**
```
현재: candle.close > candle.open 이면 TP 우선
문제: 실제로는 high가 먼저 찍혔는지 low가 먼저 찍혔는지 알 수 없음
영향: 동시 터치 케이스(드묾)에서 라벨 노이즈 발생 가능
```

**이슈 3: Long-biased 라벨 (중요도: 높음)**
```
현재: label=1은 항상 "TP가 SL보다 먼저" (가격 상승 기준)
문제: SHORT 진입 시 TP는 가격 하락인데, 동일 라벨 구조로는 표현 불가
영향: Phase 2에서 LONG/SHORT 라벨 분리가 필수적임
```

---

## 2. Stacking Ensemble 검증

### 2.1 구현 코드

```python
def fit_stacking_ensemble(
    labeled_rows: Sequence[dataset.LabeledRow],
    feature_names: Sequence[str],
    direction_family: str = "catboost",
    profitability_family: str = "catboost",
    meta_family: str = "sklearn_logistic",
) -> StackingEnsembleAdapter:
    n = len(labeled_rows)
    base_train_end = int(n * 0.6)
    meta_train_end = int(n * 0.8)

    base_train_rows = labeled_rows[:base_train_end]
    meta_train_rows = labeled_rows[base_train_end:meta_train_end]

    # Train base models on base_train
    direction_model = train_on(base_train_rows)
    profitability_model = train_on(base_train_rows)

    # Generate meta features on meta_train slice
    for row in meta_train_rows:
        p_dir = direction_model.probability(row.features)
        p_prof = profitability_model.probability(row.features)
        meta_X.append([p_dir, p_prof])
        meta_y.append(row.label)

    # Train meta model on meta_train predictions
    meta_adapter = _fit_meta_model(meta_X, meta_y, meta_family)
```

### 2.2 검증 결과

| 항목 | 상태 | 설명 |
|---|---|---|
| **데이터 분할** | ✅ 안전 | 시간 순서 기반 60/20/20 분할 (shuffle 없음) |
| **Base 모델 학습** | ✅ 안전 | base_train(60%)만 사용 |
| **Meta feature 생성** | ⚠️ 주의 | base 모델이 meta_train(20%)에 대해 예측. 이는 **OOF-like** 구조이나, base 모델이 meta_train을 본 적 없으므로 안전 |
| **Meta 모델 학습** | ✅ 안전 | meta_train의 예측값만 사용 |
| **Validation 분할** | ✅ 안전 | 마지막 20%는 검증용으로 완전히 분리됨 |

### 2.3 발견된 이슈

**이슈 1: OOF가 아닌 Hold-out 구조 (중요도: 중간)**
```
현재: Base 모델은 첫 60%로 학습 → 나머지 40% 예측
문제: Base 모델이 전체 데이터의 패턴을 60%만 보고 학습하므로,
      나머지 40%에 대한 예측 품질이 떨어질 수 있음
권장: K-fold OOF 예측으로 변경 (보다 안전한 stacking)
```

**이슈 2: Meta 모델이 단순함 (중요도: 낮음)**
```
현재: Meta 모델은 direction 확률 + profitability 확률만 입력
문제: 원본 피처 정보가 meta 모델에 전달되지 않음
영향: Meta 모델이 원본 피처의 맥락을 활용하지 못함
```

---

## 3. 피처 계산 검증

### 3.1 검증 방법

`build_feature_rows()` 함수의 주요 피처 계산 로직 검토:

| 피처 그룹 | 미래 데이터 사용 여부 | 상태 |
|---|---|---|
| F01 수익률 | `closes[index - n]` 과거 데이터만 사용 | ✅ 안전 |
| F02 추세 | `closes[index - n]` 과거 데이터만 사용 | ✅ 안전 |
| F03 변동성 | 과거 high/low/close만 사용 | ✅ 안전 |
| F04 거래량 | 과거 volume만 사용 | ✅ 안전 |
| F05 캔들 구조 | 현재 캔들만 사용 | ✅ 안전 |
| F06 갭 | 과거 갭 플래그만 사용 | ✅ 안전 |
| F07 정규화 | 과거 rolling 통계만 사용 | ✅ 안전 |
| F08-F10 변동성조정 | 과거 RV만 사용 | ✅ 안전 |
| F11 미시구조 | 외부 소스(호가창) 사용 - 실시간 | ⚠️ 주의 |
| F12 펀딩 | 외부 소스(펀딩비) 사용 - 실시간 | ⚠️ 주의 |
| F13 주간 | `pd.resample("W")`로 과거 주간 데이터만 사용 | ✅ 안전 |

### 3.2 발견된 이슈

**이슈 1: F11/F12 외부 소스 (중요도: 중간)**
```
현재: F11(호가창), F12(펀딩비)는 외부 소스에서 가져옴
문제: 훈련 시점과 실시간 추론 시점에서 소스 가용성이 다름
영향: Train/Live 피처 불일치 (parity 문제)
대응: 이미 fallback 기본값 설정되어 있음, parity 검증 로직 존재
```

**이슈 2: Weekly MA 웜업 (중요도: 낮음)**
```
현재: F13 주간 MA는 첫 50주(504,000봉) 동안 불안정
대응: build_dataset()에서 첫 50주 자동 제외 처리됨
```

---

## 4. 종합 평가

### 4.1 누수 위험도 요약

| 영역 | 위험도 | 주요 이슈 |
|---|---|---|
| **Triple-barrier 라벨** | 🟡 중간 | entry_price 시점, Long-biased 구조 |
| **Stacking ensemble** | 🟢 낮음 | OOF 구조는 아니나 hold-out으로 안전 |
| **피처 계산** | 🟢 낮음 | 대부분 과거 데이터만 사용 |
| **외부 소스(F11/F12)** | 🟡 중간 | Train/Live 소스 불일치 가능성 |

### 4.2 권장 사항

**Phase 1-3 진행 전 해야 할 일:**

1. ✅ **즉시 진행 가능**: Phase 1 (피처 추가), Phase 2 (라벨 분리)
   - 누수 이슈가 없거나, Phase 2에서 자연스럽게 해결됨

2. ⚠️ **주의 필요**: `entry_price` 시점 문제
   - 백테스트 시: `close` 사용이 맞음 (종가 기준 진입 가정)
   - 실시간: `open` 또는 현재가 사용 필요 (별도 처리)
   - **현재 구조 유지하고, 실시간 추론 로직에서만 분리**

3. ❌ **심각한 누수 없음**: 전체 구조가 시간 순서 기반으로 안전하게 설계됨

### 4.3 최종 판단

```text
현재 코드베이스는 누수 측면에서 안전하게 설계되어 있다.

주의가 필요한 부분:
1. entry_price 시점 (Phase 3 실시간 추론 시 처리)
2. Long-biased 라벨 (Phase 2에서 자연스럽게 해결)
3. OOF stacking 개선 (Phase 3 이후 고도화)

Phase 1-3 진행에 누수는 주요 장애물이 아니다.
```

---

**검증자:** Sisyphus AI  
**다음 단계:** Phase 1 (스캘핑 피처 추가) 진행 권장
