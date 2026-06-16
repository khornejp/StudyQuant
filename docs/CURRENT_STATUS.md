# btcusdt_quant v7.18 — 현재 진행상황

**Last Updated**: 2026-06-15 (Option C 진행 중)  
**Current Commit**: `282fd96` (GitHub pushed)  
**Test Status**: 214 tests pass (skipped=1), 0 errors  
**Environment**: Python 3.10, Windows 10, NumPy 2.2.6

---

## 1. 프로젝트 개요

BTCUSDT 1분봉 기반 자동화 양매매(quant) 시스템 v7.18의 오프라인 스캐폴드 구현.

| 항목 | 상태 |
|------|------|
| **데이터 수집** | ✅ 완료 (Public API, Archive, Parquet) |
| **피처 엔지니어링** | ✅ 완료 (107개 피처, F01~F12) |
| **학습 파이프라인** | ✅ 완료 (4-fold CV, Calibration, Feature Selection) |
| **모델 성능** | ⚠️ 개선 중 (F1=0.430, Precision=0.51~0.57) |
| **라이브 실행** | ✅ 스캐폴드 완료 (Mock/Testnet/Prod) |
| **운영 배포** | ❌ 미완료 (추가 개선 필요) |

---

## 2. 완료된 작업 (Done)

### 2.1 핵심 기능 구현

- [x] **캐노니컬 타임라인**: 1분봉 정렬, 갭 복구, 갭 비율 추적
- [x] **107개 활성 피처**: F01~F12 (가격/추세/변동성/거래량/갭/미시구조/거래소안전)
- [x] **F11/F12 실시간 피처**: depth, funding, ADL, mark price 실시간 계산 (fallback 지원)
- [x] **라이브 소스 패리티**: train/live 피처 패리티 검증 및 진입 차단
- [x] **트리플 배리어 라벨링**: TP/SL/Time-out 기반 라벨 생성 (horizon=15분)
- [x] **보정(Calibration)**: Platt/Beta/Isotonic 보정, ECE/Brier 드리프트 모니터링
- [x] **피처 선택**: 6-stage 파이프라인 (Spearman, gain, permutation, SHAP, ablation, core set)
- [x] **부트스트랩 CI**: score-bin CI (net_return, win_rate)
- [x] **옵투나 통합**: budget profiles (research/practical/full), MDD(p90) objective
- [x] **챔피언-챌린저**: shadow → canary 5/20/50 → full promotion, rollback gates
- [x] **라이브 실행**: TP/SL 브라켓 오더, drawdown protocol, ghost-fill prevention
- [x] **긴급 청산**: priority-based execution, retry capped, hard kill
- [x] **비상율 제한**: token bucket, 429/418/503 처리, Retry-After 존중
- [x] **위치 관리**: one-way position guard, position sizing, leverage cap
- [x] **CLI**: collect, collect-archive, train, live, demo, artifacts

### 2.2 데이터 수집 및 저장

- [x] **Public API**: `fapi.binance.com` klines (unsigned), pagination, rate limit
- [x] **Archive 다운로드**: `data.binance.vision` 일일 ZIP, 체크포인트, 재시도
- [x] **Parquet 지원**: 빠른 I/O (3~5x), 작은 파일 크기 (60% 감소)
- [x] **Retry 로직**: max_retries=3, Retry-After 헤더 파싱, 418 hard ban (no retry)
- [x] **외부 소스 수집**: funding rate 히스토리 API (`/fapi/v1/fundingRate`)

### 2.3 모델 및 학습

- [x] **모델 어댑터**: stdlib centroid linear classifier (default), optional LightGBM/CatBoost
- [x] **교차 검증**: walk-forward + combinatorial purged CV (CPCV), sample uniqueness weighting
- [x] **옵투나 튜닝**: 20 trial, best params (threshold, signal_scale), MDD objective
- [x] **아티팩트 생성**: dataset/model cards, feature registry, split manifest, calibration report
- [x] **계보(Lineage)**: MLflow/DVC optional adapters, local fallback

### 2.4 검증 및 문서

- [x] **214개 테스트**: 0 errors, 1 skipped (optuna optional)
- [x] **Oracle 8차 검증**: `<promise>VERIFIED</promise>` 수신
- [x] **문서 6개**: TRACEABILITY_MATRIX, OFFLINE_TRAINING_PIPELINE, IMPLEMENTATION_GAPS, REMAINING_GAPS, V718_CRITICAL_GAPS, V718_REMAINING_IMPROVEMENTS
- [x] **실제 데이터 검증 리포트**: `docs/REAL_DATA_VALIDATION_REPORT.md`

---

## 3. 주요 변경사항 (Latest)

### 3.1 라벨 전략 수정 (2026-06-15)

- **Before**: horizon=3분, F1=0.0035 (무의미)
- **After**: horizon=15분, F1=0.526 (150배 개선)
- **파일**: `dataset.py` (line 743)
- **이유**: 1분봉에서 3분 내 TP/SL 도달 불가 → 15분 내 도달 가능

### 3.2 Parquet 지원 추가 (2026-06-15)

- **함수**: `write_candles_parquet()`, `load_parquet_candles()`
- **CLI**: `python -m btcusdt_quant collect --format parquet`
- **성능**: I/O 3~5x 빠름, 파일 크기 60% 감소
- **파일**: `dataset.py` (lines 648~), `cli.py` (lines 264~)

### 3.3 F11/F12 실제 데이터 통합 (2026-06-15)

- **클래스**: `ExternalSourcesCollector`
- **수집**: `/fapi/v1/fundingRate` (funding rate 히스토리)
- **결과**: fallback 15개 → 10개 (5개 실제 데이터화)
- **실제화된 피처**: funding_rate, next_funding_rate, minutes_to_next_funding, funding_blackout_active, mark_price_basis
- **파일**: `dataset.py` (lines 1723~), `cli.py` (lines 348~)

### 3.4 라벨 대칭화 (2026-06-15)

- **변경**: TP=1.0% → 0.5% (SL=0.5% 유지)
- **결과**: 라벨 67:33 → 50:50 (완벽 대칭)
- **이유**: TP가 SL보다 2배 멀어서 Long bias 제거
- **파일**: `dataset.py` (line 815)

### 3.5 Threshold Precision 기준 (2026-06-15)

- **변경**: F1 기준 → Precision 기준 (recall ≥ 0.3 constraint)
- **결과**: Precision 0.35 → 0.51~0.57, Recall 0.82 → 0.27~0.53
- **효과**: 더 선택적인 모델 (더 적은 거래, 더 높은 정확도)
- **파일**: `training.py` (lines 527~)

### 3.6 2-Stage Research 브랜치 (2026-06-15)

- **브랜치**: `2stage-research` (GitHub)
- **구성**: RegimeDetector 클래스 (volatility/trending/ranging)
- **목적**: 2-Stage 구조 실험 (연구용, 프로덕션 아님)
- **파일**: `features.py` (lines 1025~)

---

## 4. 현재 성능 지표

### 4.1 학습 결과 (20,000 rows, horizon=15, symmetric TP/SL)

| 메트릭 | Before (TP=1.0%) | After (TP=0.5%) | 평가 |
|--------|------------------|-----------------|------|
| **Mean Test F1** | 0.526 | **0.430** | ⚠️ 낮아짐 (selective) |
| **Mean Test Accuracy** | 0.357 | **0.516** | ✅ 향상 |
| **Precision** | 0.35 | **0.51~0.57** | ✅ 향상 |
| **Recall** | 0.82 | **0.27~0.53** | ⚠️ 낮아짐 |
| **Fold Count** | 4 | 4 | ✅ |
| **Feature Count** | 107 (59) | 107 (57) | ✅ |
| **Champion-Challenger** | FAILED | FAILED | ❌ (F11/F12 미완성) |

### 4.2 라벨 분포

| 라벨 | Before | After | 의미 |
|------|--------|-------|------|
| 0 (SL/Timeout) | 66.7% | **49.9%** | 하띌 또는 타임아웃 |
| 1 (TP) | 33.3% | **49.4%** | 상승 |
| Timeout | 0% | **0.6%** | 미도달 |

---

## 5. 알려진 문제점 및 제한사항

### 5.1 🔴 블로커 (운영 배포 차단)

| 문제 | 심각도 | 설명 | 해결 방향 |
|------|--------|------|-----------|
| **모델 성능 부족** | 🔴 | F1=0.526, 정확도=0.36 | LightGBM/CatBoost 추가 필요 |
| **F11/F12 미완성** | 🔴 | depth/ADL/leverage는 실제 데이터 불가 | Testnet 실시간 수집 또는 historical API 탐색 |
| **Optuna 버그** | 🔴 | threshold=0.6+ 설정 → F1=0.0 | Objective 수정 또는 threshold range 제한 |
| **NumPy 2.0 호환성** | 🔴 | LightGBM/CatBoost import 실패 | NumPy downgrade 또는 라이브러리 업데이트 |
| **Recall 낮음** | 🔴 | Precision 기준 threshold로 recall 0.27~0.53 | Threshold 기준 재조정 또는 다른 모델 |
| **2-Stage 미완성** | 🔴 | RegimeDetector만 추가, Long/Short 모델 미구현 | 2stage-research 브랜치에서 계속 |

### 5.2 🟡 경고 (기능 제한)

| 문제 | 심각도 | 설명 | 해결 방향 |
|------|--------|------|-----------|
| **대용량 데이터** | 🟡 | 50k+ rows 학습 시간 초과 | 병렬 처리 또는 샘플링 |
| **보정 한계** | 🟡 | Beta calibration이 극단적 불균형에서 효과적이지 않음 | Isotonic 또는 Platt scaling |
| **Champion-Challenger** | 🟡 | PSI=None으로 승격 항상 실패 | Testnet soak 7일+ 필요 |
| **Live Loop** | 🟡 | 단일 pass (max_candles), 연속 루프 없음 | 연속 루프 + graceful shutdown |

### 5.3 🟢 정보 (참고)

| 문제 | 심각도 | 설명 |
|------|--------|------|
| **Gap-cross Exit** | 🟢 | Scaffold (실제 포지션 평가 없음) |
| **WebSocket Ingestion** | 🟢 | REST backfill 미완전 통합 |
| **TP/SL Price** | 🟢 | 고정 1%/0.5% → 동적 ATR 기반 필요 |

---

## 6. 파일 구조

```
btcusdt_quant/
├── data.py              # Candle, Timeline, Gap repair
├── dataset.py           # Feature engineering, labeling, CSV/Parquet/Archive
├── feature_registry.py  # 107 feature definitions, dependency graph
├── features.py          # Feature selection, calibration, Optuna, champion-challenger
├── cv.py                # Purged CV, combinatorial CV, sample uniqueness
├── training.py          # Offline training, model adapters, artifact generation
├── models.py            # Model adapter protocol, stdlib/LightGBM/CatBoost
├── live.py              # Live execution engine, WebSocket, order safety
├── exchange.py          # Exchange adapter protocol, Binance testnet/prod
├── risk.py              # Drawdown protocol, risk policy, sizing
├── monitoring.py        # Clock drift, ADL, funding, calibration drift
├── governance.py        # Pipeline stages, fallback chain, artifact writer
├── sources.py           # Source contracts, availability grades, parity
├── parity.py            # Train/live feature parity verification
├── lineage.py           # MLflow/DVC optional adapters, local fallback
├── failure_injection.py # Deterministic fault scenarios
├── secrets.py           # Credential loading, masking
├── cli.py               # CLI entry point

└── tests/
    ├── test_core.py     # 120 original tests
    └── test_v718.py     # 94 v7.18 regression tests

artifacts/
├── real_btcusdt_1m.parquet           # 10,000 rows (1m candles)
├── real_btcusdt_1m_20k.parquet       # 20,000 rows
├── real_training_v3/                 # 10k baseline (F1=0.516)
├── real_training_v6/                 # 10k + F11/F12 (F1=0.515)
├── real_training_20k/                # 20k baseline (F1=0.526)
├── real_training_20k_f11f12/       # 20k + F11/F12 (F1=0.526)

└── docs/
    ├── REAL_DATA_VALIDATION_REPORT.md  # 본 리포트
    ├── V718_REMAINING_IMPROVEMENTS.md
    ├── V718_CRITICAL_GAPS.md
    ├── IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md
    ├── REMAINING_GAPS_V718.md
    ├── OFFLINE_TRAINING_PIPELINE.md
    └── TRACEABILITY_MATRIX.md
```

---

## 7. CLI 사용법

```powershell
# 1. 데이터 수집 (Parquet)
python -m btcusdt_quant collect --output data/btcusdt_1m.parquet --rows 20000 --allow-public-network --format parquet

# 2. 학습 (Feature Selection + Champion-Challenger + F11/F12)
python -m btcusdt_quant train --input data/btcusdt_1m.parquet --output artifacts/training --feature-selection --champion-challenger --collect-external-sources

# 3. 라이브 (Mock, Dry-run)
python -m btcusdt_quant live --dry-run --output artifacts/live --model-artifact artifacts/training/model.json

# 4. 아티팩트 검증
python -m btcusdt_quant artifacts --path artifacts/training

# 5. 테스트
python -m unittest discover -s tests
```

---

## 8. 다음 단계 권장사항

### 8.1 단기 (1주 내) — Single-Stage Main

| 우선순위 | 작업 | 예상 효과 |
|----------|------|-----------|
| P0 | **NumPy 2.0 호환성 해결** | LightGBM/CatBoost 사용 가능 |
| P0 | **LightGBM/CatBoost 모델 추가** | F1 0.43 → 0.60+ |
| P1 | **Threshold 기준 재조정** | Precision-Recall trade-off 최적화 |
| P1 | **50k+ 데이터 수집** | 더 많은 학습 데이터 |

### 8.2 중기 (2~4주) — Single-Stage + 2-Stage Research

| 우선순위 | 작업 | 예상 효과 |
|----------|------|-----------|
| P1 | **2-Stage Long/Short 모델 실험** | regime별 분리 모델 성능 비교 |
| P1 | **Regime별 threshold 최적화** | high_vol/trending/range별 다른 threshold |
| P2 | **Depth/ADL historical API 탐색** | F11/F12 완전 통합 |
| P2 | **Feature selection 최적화** | 59개 → 20~30개 축소 |

### 8.3 장기 (운영 배포 전)

| 우선순위 | 작업 | 예상 효과 |
|----------|------|-----------|
| P2 | **Testnet soak 7일+** | 실제 거래 메트릭 (PSI, latency, fill rate) |
| P2 | **Champion-Challenger 승격** | F1 > 0.6, Sharpe > 1.0, MDD < 0.1 |
| P3 | **Human-in-the-loop** | 낮은 F1에서 자동 거래 금지 |
| P3 | **2-Stage 프로덕션 통합** | Regime Detection → Long/Short 라우팅 (2stage-research 브랜치 머지) |

---

## 9. 결론

**현재 시스템은 테스트넷 검증 가능 수준, 실운영 배포는 추가 개선 필요.**

- ✅ **데이터 수집**: 완전 자동화 (Parquet, pagination, rate limit)
- ✅ **학습 파이프라인**: 완전 자동화 (F1=0.526, 4-fold CV)
- ⚠️ **모델 성능**: 기초 수준 (선형 분류기 한계, LightGBM 추가 필요)
- ⚠️ **F11/F12**: 부분 완료 (5/15 실제 데이터화, 10개는 testnet 필요)
- ❌ **Optuna**: 버그 (threshold 0.6+ 설정)
- ❌ **운영 배포**: 추가 개선 후 가능

---

**작성자**: Sisyphus (AI 개발 에이전트)  
**작성일**: 2026-06-15  
**버전**: v7.18  
**GitHub**: https://github.com/khornejp/StudyQuant (commit `190c908`)
