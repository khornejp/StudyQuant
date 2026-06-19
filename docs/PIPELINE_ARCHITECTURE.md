# BTCUSDT Quant Trading System - Pipeline Architecture

## 현재 구조 (Current: Option B)

### 데이터 흐름
```
Binance USD-M Futures 1m 아카이브
    ↓ (40개 기간 병렬/순차 다운로드)
[CSV 파일들] artifacts/futures_*/
    ↓ (PyArrow CSV → Parquet 변환)
[Parquet 파일들] artifacts/futures_*.parquet
    ↓ (open_time 기준 정렬 후 concat)
[통합 학습 데이터] artifacts/training_combined.parquet
    ↓ (Regime Detect → 분할)
[Regime별 모델] artifacts/regime_{ranging|trending|high_volatility}/
    ↓ (2025년 unseen 데이터)
[백테스트 결과] artifacts/backtest_results/
```

### 학습 모드
현재 `training.py`의 분기 로직:
```python
if training_config.regime_aware:      # ← 우선 체크
    return run_regime_aware_training(...)  # Option B
if training_config.ensemble_enabled:  # ← 이건 실행 안 됨!
    return run_ensemble_training(...)      # 무시됨
```

**결과**: `--ensemble --regime-aware` 동시 사용 시 **Ensemble 무시**, Regime-Aware 단일 모델만 학습

### 모델 구조 (Option B)
```
전체 데이터
    ↓ Regime Detect (rv_15 + trend_slope_30)
    ├─ high_volatility  → CatBoost 단일 모델
    ├─ trending         → CatBoost 단일 모델
    └─ ranging          → CatBoost 단일 모델

백테스트 추론:
    현재 캔들 Regime Detect → 해당 Regime의 모델로 probability 계산
```

---

## 목표 구조 (Target: Option A)

### 모델 구조 (Regime-Aware Stacking Ensemble)
```
전체 데이터
    ↓ Regime Detect
    ├─ high_volatility
    │   └─ Stacking Ensemble
    │       ├─ Direction Model (CatBoost)
    │       ├─ Profitability Model (CatBoost)
    │       └─ Meta Model (CatBoost) ← 위 2개 확률을 입력으로 최종 확률 출력
    ├─ trending
    │   └─ Stacking Ensemble (동일 구조)
    └─ ranging
        └─ Stacking Ensemble (동일 구조)
```

### 필요 수정사항
1. **`training.py`**: `run_regime_aware_training()` 낶에서 `_train_single_regime()` 호출 시 `ensemble_enabled=True`로 설정
2. **`training.py`**: 분기 로직 수정 (ensemble + regime-aware 동시 지원)
3. **백테스트**: `live.py`의 `load_model_artifact()`가 regime-aware ensemble 구조를 로드하도록 수정

---

## 파일 구조

### 학습 아티팩트 (Regime-Aware 단일 모델 - 현재)
```
artifacts/regime_stacking_model/
├── regime_run_summary.json
├── regime_high_volatility/
│   ├── model.json              # CatBoost 단일 모델
│   ├── run_summary.json
│   └── ...
├── regime_trending/
│   ├── model.json
│   └── ...
└── regime_ranging/
    ├── model.json
    └── ...
```

### 학습 아티팩트 (Regime-Aware Stacking Ensemble - 목표)
```
artifacts/regime_stacking_model/
├── regime_run_summary.json
├── regime_high_volatility/
│   ├── model.json              # StackingEnsembleAdapter
│   │                           #  - direction_model: CatBoostAdapter
│   │                           #  - profitability_model: CatBoostAdapter
│   │                           #  - meta_adapter: CatBoostAdapter
│   └── ...
├── regime_trending/
│   └── ...
└── regime_ranging/
    └── ...
```

---

## 파이프라인 스크립트

### 현재
- `run_pipeline.ps1`: 5단계 (Collect → Convert → Combine → Train → Backtest)
- 문제: 병렬 다운로드(`Start-Job`) 실패 시 오류 미표시

### 수정 필요
- 순차 다운로드로 변경 (안정성 ↑, 속도 ↓)
- 각 단계별 검증 추가 (CSV 존재 여부 확인)

---

## 백테스트 구조

### 입력
- **학습 데이터**: 2020-01-01 ~ 2024-12-31 (regime별로 분할된 40개 기간)
- **백테스트 데이터**: 2025-01-01 ~ 2025-06-30 (완전히 unseen)

### 시뮬레이션
```
For each 1m candle in 2025:
    1. Feature extraction (F01-F13, 112 features)
    2. Regime detection (rv_15 + trend_slope_30 + weekly features)
    3. Model inference (해당 regime의 모델로 probability 계산)
    4. Signal generation:
         prob > long_threshold  → BUY
         prob < short_threshold → SELL
         else                   → HOLD
    5. If signal and no position:
         Enter with TP/SL (optimized_tp_sl)
    6. If position active:
         Check TP/SL hit or horizon timeout
         Close trade → record P&L
```

### 비용 구조
- **Fee**: 0.02% per side (entry + exit = 0.04%)
- **Slippage**: 0.02% per side (entry + exit = 0.04%)
- **Total round-trip cost**: 0.08%

### 출력 메트릭
- `total_return`: 순수익률 (비용 차감 후)
- `gross_total_return`: 비용 차감 전
- `win_rate`: 승률
- `profit_factor`: 총수익/총손실
- `max_drawdown`: 최대 낙폭
- `sharpe`: 샤프 비율
- `trade_count`: 거래 횟수

---

## 향후 개선 로드맵

### Phase 1: 안정적인 파이프라인 (현재)
- [x] Regime-Aware 단일 모델 학습
- [x] 2025년 백테스트
- [ ] 파이프라인 오류 수정 (순차 다운로드)

### Phase 2: Option A 구현
- [ ] `training.py`: `_train_single_regime()`에 ensemble 지원
- [ ] `training.py`: regime + ensemble 동시 분기
- [ ] `ensemble.py`: meta model을 regime별로 저장/로드
- [ ] `live.py`: regime-aware ensemble inference

### Phase 3: 고급 기능
- [ ] Feature selection (6-stage pipeline 활성화)
- [ ] Optuna hyperparameter tuning
- [ ] Champion-Challenger promotion
- [ ] Live trading 연동 (Binance Testnet)

---

## 관련 파일

| 파일 | 역할 |
|---|---|
| `btcusdt_quant/training.py` | 학습 파이프라인 (regime/ensemble 분기) |
| `btcusdt_quant/ensemble.py` | StackingEnsembleAdapter |
| `btcusdt_quant/dataset.py` | Feature engineering, labeling |
| `btcusdt_quant/features.py` | RegimeDetector, FeatureClipper |
| `btcusdt_quant/backtest.py` | 백테스트 엔진 |
| `btcusdt_quant/live.py` | 실시간 추론 (regime-aware model loading) |
| `run_pipeline.ps1` | 전체 파이프라인 자동화 |
| `collect_futures_regimes.ps1` | 데이터 수집 |
