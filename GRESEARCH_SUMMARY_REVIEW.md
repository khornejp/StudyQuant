# `g_research_crypto_forecasting_extracted_summary.md` 검토 — BTCUSDT 프로젝트 적용 가능성 분석

> 작성일: 2026-07-09
> 대상 문서: `g_research_crypto_forecasting_extracted_summary.md` (Kaggle G-Research Crypto Forecasting 발표 자료 요약)
> 방법: 문서가 제안하는 항목을 실제 `btcusdt_quant/` 코드베이스와 하나씩 대조하여, **이미 구현된 것 / 아직 없는 진짜 gap / 구조상 적용이 어려운 것**을 구분

원본 문서 9~10절에 이미 "현재 프로젝트에 주는 시사점"이 상당히 구체적으로 작성되어 있지만, 실제 코드를 확인하지 않고 작성된 일반론입니다. 본 문서의 핵심 가치는 **그 제안들을 코드와 대조 검증**하는 데 있습니다 — 상당수는 이미 구현되어 있었습니다.

---

## 1. 대조 검증 결과 요약표

| 원본 문서 제안 (9~10절) | 코드베이스 확인 결과 | 판정 |
|---|---|---|
| log_return / relative OHLCV feature 추가 | `feature_registry.py:85-86`에 `log_return_1`, `log_return_5` 이미 존재. `body_pct`(132행), `wick_imbalance`(136행) 등 캔들 형태 피처도 이미 존재 | ✅ **이미 구현됨** — 추가 작업 불필요 |
| Local standardization (rolling zscore) | `close_zscore_20/60`, `volume_zscore_5/20`, `rv_zscore_60`, `range_zscore_20`, `trade_count_zscore_20` 등 F07 REGIME_NORMALIZATION 피처군이 이미 rolling window 기준으로 계산됨 (`feature_registry.py:149-154`) | ✅ **이미 구현됨** |
| Embargo / Purge gap 유지 | `training.py`에 `PurgedWalkForwardSplit`, `embargo_size` 필드, `default_splits(n_rows, purge_gap)` 가 이미 존재. CLI에 `--purge-gap`, `--embargo-size` 옵션도 있음 (`cli.py:156,405,705`) | ✅ **이미 구현됨** — 오히려 원본 발표(3,750분)보다 우리 default(60분)가 훨씬 작아 재검토 가치는 있음 (아래 §3 참고) |
| Multi-horizon(30/60/90/120분) ensemble | `--horizon` CLI 플래그로 **개별** horizon 학습은 가능(`cli.py:1033` 등). 하지만 여러 horizon 모델을 동시에 학습해 확률을 평균/가중평균하는 **앙상블 로직은 없음**. `ensemble.py`의 `StackingEnsembleAdapter`는 direction+profitability+meta 3단 스태킹이지 multi-horizon 구조가 아님 | ❌ **진짜 gap** — §2.1 참고 |
| Market-neutral proxy (BTC vs ETH/시장 인덱스) | `metrics_source.py`, `sources.py`는 BTCUSDT 자체의 파생상품 지표(open interest 등, F16)만 다룸. ETH나 시장 인덱스 등 **타 자산 데이터 자체가 프로젝트에 없음** | ❌ **진짜 gap이지만 데이터 소스 확보가 선행 조건** — §2.2 참고 |
| Weighted Pearson Correlation 평가지표 | 우리는 단일 자산이라 "자산별 weight" 개념 자체가 없음 | ⚪ **해당 없음** (구조적으로 다자산 문제 전용 지표) — §4 참고 |

---

## 2. 진짜 적용 가치가 있는 항목 (Gap)

### 2.1 Multi-horizon Ensemble — 우선순위 높음

발표의 7위 솔루션 핵심은 "45/60/90/120분 창을 각각 학습 후 평균 → 단일 모델(28위)보다 크게 개선"이었습니다. 우리 프로젝트는:

- `TrainingConfig.label_horizon`(기본 60바)이 **단일 값**이고, 학습 파이프라인 전체(레이블링 → CV split → 모델 학습)가 이 값에 고정되어 있습니다.
- `run_train`류 함수를 여러 `--horizon` 값으로 반복 실행해 모델을 각각 저장하는 것은 현재도 가능하지만, **추론 시점에 여러 horizon 모델의 확률을 결합하는 코드가 없습니다.**

**적용 방법 제안**:
1. 기존 `run_train_regime_classifier`가 이미 여러 fold의 OOF 확률을 만드는 구조(`cli.py` 300행대)와 유사하게, `horizon in [30, 60, 90, 120]`에 대해 별도로 엔트리 모델을 학습.
2. `ensemble.py`에 `MultiHorizonEnsembleAdapter`를 추가하여 각 horizon 모델의 `predict_proba` 결과를 단순평균 또는 검증 성능 기반 가중평균으로 결합.
3. 다만 우리 프로젝트는 이미 레짐별(up/down/range) 라우팅이라는 별도의 축이 있으므로, "레짐 × horizon" 조합이 학습/서빙 복잡도를 크게 늘릴 수 있음 — 먼저 **단일 레짐(예: trend) 안에서만** 30/60/90분 3-horizon 앙상블을 파일럿으로 검증한 뒤 확장하는 것을 권장.

### 2.2 Market-neutral Proxy Feature — 우선순위 중간 (데이터 확보 필요)

원본 발표의 핵심 개념(시장 Beta 제거 후 잔차 Alpha 예측)은 우리 프로젝트가 **단일 자산**이라 원형 그대로는 적용할 수 없지만, 변형 아이디어는 유효합니다:

- `BTC return - ETH return` 또는 `BTC return - 시가총액 가중 크립토 지수 return` 같은 상대강도 피처는 "BTC가 시장 전체와 무관하게 얼마나 독자적으로 움직이는지"를 포착할 수 있어, 특히 **레짐 분류기의 오탐(false regime switch)을 줄이는 보조 피처**로 유용할 수 있습니다.
- **선행 조건**: 현재 `dataset.py`/`sources.py`는 BTCUSDT 단일 심볼 파이프라인만 지원합니다. ETH나 시장 인덱스 데이터를 별도로 수집·정렬하는 다운로더가 필요하며, 이는 F16 메트릭 파이프라인(`metrics_source.py`)을 다자산으로 확장하는 것과 유사한 작업량입니다. **당장 착수하기보다 백로그로 등록해 우선순위를 재논의할 항목**입니다.

---

## 3. 주의 깊게 재검토할 만한 기존 설정값

원본 발표는 **embargo period 3,750분(약 2.6일)**을 사용했습니다. 이는 그들의 target이 15분 잔차 수익률임에도, rolling feature(예: beta 계산용 rolling window 자체가 3,750분)의 lookback을 고려해 크게 잡은 것으로 보입니다.

우리 프로젝트의 기본값은 `--purge-gap 60`(1시간, `label_horizon`과 동일)입니다. 이 자체는 **label 겹침 방지 목적으로는 정확**합니다 (label horizon과 purge gap이 일치해야 fold 경계에서 미래 정보가 새지 않음). 다만:

- 주간 단위 피처(`weekly_features.py`, MA50 warmup = 50주 ≈ 504,000분)처럼 **매우 긴 lookback을 갖는 피처**가 존재하는데, 이는 causal(과거만 참조)하므로 purge gap과는 별개 문제이며 이미 별도의 warmup 배제 로직(`ic_diagnostic.py`의 `WEEKLY_WARMUP_BARS` 등)으로 처리되고 있어 **추가 조치가 필요하지는 않아 보입니다.** 다만 "fold 경계 근처에서 이 초장기 피처들이 실제로 얼마나 안정적으로 채워지는지"는 별도 검증 스크립트로 확인해볼 가치가 있습니다 (기존 `verify_*.py` 계열과 같은 방식).

이 항목은 **버그가 아니라 확인 차원의 제안**이며, 즉시 코드 변경이 필요한 사항은 아닙니다.

---

## 4. 구조적으로 적용 어려운 항목 (참고만)

| 항목 | 이유 |
|---|---|
| Weighted Pearson Correlation 평가지표 | 자산별 weight라는 개념 자체가 다자산 cross-sectional 문제 전용. 굳이 변형하자면 "레짐별 가중 평가"(예: 실거래 비중이 큰 레짐의 성능에 더 큰 가중치)로 재해석할 수 있으나, 이는 원 지표의 본질과 다르므로 억지로 채용할 필요는 없음 |
| Axial Attention Transformer / Deep Learning 아키텍처 | 원본 문서도 스스로 "해석 가능성, 검증 용이성, feature importance 확인 가능성" 측면에서 현재는 CatBoost + feature engineering이 더 현실적이라고 결론 내림 — 이 프로젝트의 방향(레짐별 CatBoost 라우팅)과 일치하므로 **현행 유지가 맞는 판단** |
| Data Lightweighting (Close만 사용) | 우리는 이미 OHLCV 전체 + 파생 피처(F01~F18)를 정교하게 활용 중이므로 역행하는 방향. 발표팀은 메모리 제약(16GB) 때문에 taken한 절충이었을 뿐, 일반 원칙은 아님 |

---

## 5. 결론 — 실행 우선순위

1. **(재확인만, 코드 변경 불필요)** log_return/캔들형태/rolling zscore 피처, purge/embargo 구조는 이미 잘 구현되어 있음을 확인했습니다. 원본 문서의 해당 제안은 **참고용으로만 남기고 실행 목록에서 제외**합니다.
2. **(우선순위 높음)** Multi-horizon ensemble — 단일 레짐 파일럿으로 30/60/90분 모델을 학습해 단순평균 앙상블의 효과를 먼저 검증. `ensemble.py`에 `MultiHorizonEnsembleAdapter` 추가가 구체적 다음 단계.
3. **(우선순위 중간, 데이터 선행 필요)** ETH/시장 인덱스 상대강도 피처 — 데이터 수집 파이프라인 확장이 선행되어야 하므로 백로그 항목으로 등록.
4. **(확인 차원)** 초장기 lookback 피처(주간 MA50 등)가 fold 경계에서 안정적으로 채워지는지 검증 스크립트로 재확인 — 급하지 않음.
5. Weighted Pearson 지표, Deep Learning 아키텍처, Data Lightweighting은 **적용하지 않는 것이 맞는 판단**으로 결론.

---

*이 문서는 `g_research_crypto_forecasting_extracted_summary.md`와 `btcusdt_quant/feature_registry.py`, `training.py`, `cli.py`, `ensemble.py`, `metrics_source.py`, `sources.py`를 대조하여 작성되었습니다.*
