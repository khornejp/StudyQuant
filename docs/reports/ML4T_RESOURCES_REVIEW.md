# `ml4t-main` 자료 검토 — BTCUSDT 퀀트 프로젝트 적용 가능성 분석

> 작성일: 2026-07-09
> 대상: `ml4t-main/` (Ernest Chan *Quantitative Trading* 2nd Ed. 스터디 자료 + Kaggle/논문/전략 리뷰 아카이브)
> 목적: 현재 BTCUSDT 1분봉 퀀트 트레이딩 프로젝트(`btcusdt_quant/`)에 실질적으로 도움이 될 만한 개념·코드·방법론을 선별

---

## 1. 폴더 구성 요약

```
ml4t-main/
├── source/
│   ├── Chan E. Quantitative Trading...2ed 2021/   # 스터디 교재 (챕터 1~7, 발표자료/노트북/리포트)
│   ├── kaggle/                                     # Kaggle 대회 코드 (크립토 예측, 주식 수익률/추세 예측)
│   ├── papers/                                     # 논문 리뷰 (ML 기반 방향성 예측)
│   └── Quant Trading Strategy Review/              # 개별 전략 리뷰 (계절성, 모멘텀, 반전, TDA 등)
└── archive/                                         # 이전 스터디(2013년 Algorithmic Trading) 아카이브
```

우리 프로젝트(단일 자산 BTCUSDT, 1분봉, 레짐 기반 롱/숏 방향성 + 레인지 평균회귀, CatBoost/LightGBM 분류)와 대조했을 때, **다자산 롱숏/크로스섹셔널 전략** 코드는 대부분 직접 이식이 어렵고, **리스크 관리·백테스트 방법론·평균회귀 캘리브레이션** 관련 자료가 실질적으로 유용합니다.

---

## 2. 우선순위 높음 — 바로 적용 검토 가치가 있는 항목

### 2.1 Kelly / Half-Kelly 기반 포지션 사이징
- **출처**: `chapter_6_money_and_risk_management/src/Example6_3.py`, `reports/chapter6_report.md`
- **핵심 수식**: 단일 전략 $f^* = m/s^2$ (평균초과수익 / 분산), 포트폴리오 $F^* = C^{-1}M$
- **현재 프로젝트 상태**: `btcusdt_quant/risk.py`는 고정된 `max_leverage`만 사용하고 있으며 (`grep` 결과 `kelly` 관련 로직 없음), 모델의 예측 확신도(예측 확률)나 최근 변동성에 따라 포지션 크기를 동적으로 조절하는 로직이 없습니다.
- **적용 아이디어**:
  - 엔트리 모델의 `predict_proba` 확신도를 기대수익 추정치로 변환 → 최근 N바 수익률 분산으로 나눠 단일 자산 Kelly 비율 산출
  - 파산/과도한 낙폭 방지를 위해 **Half-Kelly**를 기본값으로 채택 (리포트에 따르면 성장률 -18.5% 대신 MDD 43% 개선, 변동성 50% 감소 — 트레이드오프가 실무적으로 합리적)
  - 리버리지 상한(`max_leverage`)은 Kelly 산출값에 대한 **캡(cap)**으로 재해석 가능
- **주의**: Chan의 예시는 일별 데이터·다자산 포트폴리오 기준이라, 1분봉 고빈도 데이터에 그대로 적용 시 파라미터(예: lookback window, 재계산 주기)를 재보정해야 함. 레짐별로 분산이 크게 다르므로(range vs trend) Kelly 분산 추정도 레짐별로 분리하는 것이 합리적.

### 2.2 평균회귀 반감기(Half-Life, Ornstein-Uhlenbeck) 계산
- **출처**: `chapter_7_special_topics_in_quantitative_trading/src/Example7_5.py`
- **핵심 코드 패턴**:
  ```python
  dz = z.diff().dropna()
  prevz = z.shift().dropna()
  theta = OLS(dz, prevz - prevz.mean()).fit().params[0]
  halflife = -np.log(2) / theta
  ```
- **현재 프로젝트 상태**: `apply_range_mean_reversion_gate` (`btcusdt_quant/backtest.py:83`, `live.py:1658`)와 F15 레인지 피처군(`range_position_20`, `bb_zscore`, `vwap_deviation_zscore` 등, `feature_registry.py`)이 **고정 윈도우(20바)** 로 평균회귀를 가정하고 있습니다. 반감기를 실측하지 않고 있음.
- **적용 아이디어**:
  - `close` 또는 `vwap_deviation` 시계열에 대해 OU 반감기를 정기적으로 재추정 → range 레짐일 때의 롤링 윈도우 길이(`_20`)나 홀딩 기간(TP/SL 타임아웃)을 반감기 기준으로 캘리브레이션
  - 레짐 분류기 학습/검증 스크립트(`ic_diagnostic.py`, `regime_classifier.py`)에 half-life를 진단 지표로 추가하면, "range 레짐이 실제로 평균회귀 특성을 갖는지"를 정량적으로 검증 가능 (현재는 규칙 기반 레짐 판정만 존재)

### 2.3 리키지(look-ahead leakage) 자동 탐지 패턴
- **출처**: `kaggle/stocks-return-prediction-v-2/analyze_leak.py`
- **핵심 아이디어**: 각 피처에 대해 (1) target과의 직접 상관, (2) target과 **1스텝 미래로 shift한 피처**와의 상관, (3) target과 "다음 값/현재 값 - 1" 형태의 계산된 수익률과의 상관을 모두 비교하여, 비정상적으로 높은 상관관계가 나오면 해당 피처가 미래 정보를 담고 있음을 의심하는 방식.
- **현재 프로젝트 상태**: 이 프로젝트는 이미 leakage 이슈를 다수 겪고 수정한 이력이 있습니다 (`FIX_REPORT_V5~V9_REMEDIATION.md`, `FIX_REPORT_TRAIN_SERVE_PARITY.md`, `verify_weekly_causality.py`, `verify_external_slicing.py` 등). 다만 이런 검증들은 대부분 **개별 버그 발견 후 사후 대응**으로 작성된 스크립트이며, **신규 피처 추가 시 자동으로 도는 표준 회귀 테스트**는 아직 없어 보입니다.
- **적용 아이디어**: `feature_registry.py`에 새 피처가 추가될 때마다 "target vs feature", "target vs feature.shift(-1)"의 상관계수 차이를 자동 계산해 임계치 초과 시 경고하는 CI성 스크립트를 만들면, `ic_diagnostic.py`가 이미 계산하는 IC 파이프라인에 자연스럽게 얹을 수 있음.

---

## 3. 우선순위 중간 — 방법론 검증/보강 참고 자료

### 3.1 백테스팅 체크리스트 (Chapter 3)
- **출처**: `chapter_3_backtesting/src/reports/chapter3_report.md`
- **핵심 교훈**: 샤프비율만이 아니라 MDD 병행 평가, **거래비용 민감도**가 회전율 높은 전략에서 특히 파괴적(예제에서 편도 5bps만으로 샤프비율 0.42 → -3.38로 반전), in-sample/out-of-sample 샤프 괴리로 과적합 진단.
- **대조**: 이 프로젝트는 이미 `DEFAULT_FEE_RATE_PER_SIDE`/`DEFAULT_SLIPPAGE_RATE_PER_SIDE` (`backtest.py:78-80`)로 비용을 모델링하고, walk-forward 방식의 fold 분리를 사용 중 — 방법론적으로는 이미 이 챕터의 권고사항을 따르고 있음. **새로운 코드보다는 체크리스트로서 참고 가치** (특히 "거래비용 포함 전/후 샤프비율을 항상 나란히 보고하라"는 습관은 백테스트 리포트에 명시적으로 채택할 만함).

### 3.2 Rank IC 기반 walk-forward 검증
- **출처**: `kaggle/stocks-return-prediction-v-2/baseline_rank_ic.py`, `.md`
- **핵심**: `TimeSeriesSplit`으로 fold별 Spearman Rank IC를 산출하고 평균±표준편차로 보고.
- **대조**: `ic_diagnostic.py`가 이미 스피어만 IC를 계산하지만 전체 구간 단일 값으로 보고합니다. Kaggle 예제처럼 **fold별 IC의 평균/표준편차**를 함께 보고하면 피처의 시간에 따른 안정성(regime-dependent IC drift)을 더 잘 진단할 수 있음 — 이는 이미 `ic_diagnostic.py`가 레짐별(`up`/`down`/`range`) IC를 계산하는 것과 상호보완적.

### 3.3 요일 효과(day-of-week) 극값 군집 + In/Out-of-sample 강건성 게이트
- **출처**: `Quant Trading Strategy Review/Calendar-based clustering of weekly extremes/`
- **핵심 아이디어**: (a) 특정 요일에 주간 고점/저점이 몰리는 현상을 마르코프 전이모형으로 탐지, (b) **KL divergence/G-검정으로 in-sample 적합도와 out-of-sample 강건성을 모두 통과해야 트레이딩을 시작**하는 게이트 구조.
- **대조**: `btcusdt_quant/weekly_features.py`가 이미 주간 단위 피처(주간 이동평균, drawdown 등)를 계산하지만 요일별 패턴 자체를 피처화하지는 않음. 암호화폐는 24/7 거래로 전통적 "월요일 갭" 효과는 없지만, 주말 유동성 저하로 인한 변동성 패턴 차이는 보고된 바 있어 **가설 검증 대상**으로는 흥미로움.
- **적용 아이디어**: 새 피처를 만들기보다, **"in-sample에서 유의미해도 out-of-sample 검증(KL/G-검정 또는 단순 fold별 재현성)을 통과 못하면 배포하지 않는다"는 게이트 원칙**을 레짐 분류기나 신규 피처 승인 프로세스에 명문화하는 쪽이 더 실용적 (이 프로젝트가 겪은 다수의 leakage/overfitting 이슈를 고려하면 특히).

---

## 4. 우선순위 낮음 / 참고용 (직접 적용성 낮음)

| 자료 | 내용 | 비고 |
|---|---|---|
| Chapter 7 공적분/페어 트레이딩 (GLD-GDX, KO-PEP), PCA 팩터 모델 | 멀티에셋 통계적 차익거래 | 현재 프로젝트는 **단일 자산(BTCUSDT)** 이므로 직접 적용 불가. 추후 멀티 코인(예: ETHUSDT와의 스프레드 트레이딩) 확장 시 재검토 가치 있음 |
| 1월 효과, 계절성 모멘텀 (Example 7.6, 7.7) | 주식시장 세금/리밸런싱 기반 계절성 | 크립토 시장 구조와 무관, 원 논문에서도 유의미한 수익 없음으로 결론 |
| `kaggle/G-research-crypto-forecasting` | 크립토 방향성 예측 대회 자료 | README에 대회 링크만 있고 코드/노트북 없음 (PDF 발표자료만 존재) — 실질적 재사용 코드 없음 |
| `Quant Trading Strategy Review/short_term_reversal_effect`, `Low_Volatility_Time_Series_Momentum`, `Portfolio Construction Using Topological Data Analysis` 등 | QuantConnect 기반 멀티종목 롱숏 전략 | 유니버스 선택/리밸런싱 구조가 크로스섹셔널 주식 전략 전용이라 이식 비용이 큼. 아이디어 수준(변동성 역가중, TDA 기반 분산)만 참고 가능 |
| `papers/Campisi_2024...` | S&P500 방향 예측 ML 방법론 비교 논문 재현 | 방법론(피처 비교, 롤링 재학습)은 일반적이나 이미 우리 프로젝트가 더 정교한 walk-forward + 레짐 기반 프레임워크를 갖추고 있어 우선순위 낮음 |

---

## 5. 결론 및 권장 다음 단계

실질적으로 도움이 되는 순서:

1. **`analyze_leak.py` 패턴을 응용한 자동 리키지 회귀 테스트 추가** — 이 프로젝트가 반복적으로 leakage 버그를 겪어온 이력(V5~V9 FIX_REPORT)을 고려하면 ROI가 가장 높음. `ic_diagnostic.py` 파이프라인에 `feature vs feature.shift(-1) vs target` 상관 검사를 추가하는 형태로 구현 가능.
2. **Half-Life(OU) 진단을 range 레짐 피처 설계에 반영** — 현재 고정 20바 윈도우가 실제 평균회귀 속도와 맞는지 검증. `verify_*.py` 스크립트 계열에 `verify_range_halflife.py` 형태로 추가 가능.
3. **Half-Kelly 기반 동적 포지션 사이징 검토** — `risk.py`의 고정 `max_leverage`를 모델 확신도·레짐별 변동성 기반 동적 사이징으로 확장. 다만 1분봉 데이터 특성에 맞는 재보정(lookback, 재계산 주기) 필요.
4. **백테스트 리포트에 거래비용 포함/미포함 샤프비율을 항상 나란히 표기하는 관행 명문화** — 코드 변경보다는 리포트 템플릿/체크리스트 수준의 개선.
5. (장기) **멀티코인 확장 시** 챕터 7의 공적분/헤지비율 코드(`Example7_2.py`, `Example7_3.py`)를 페어 트레이딩 모듈의 출발점으로 재검토.

---

*이 문서는 `ml4t-main/` 내 README, 챕터 리포트(`chapter{3,6,7}_report.md` 계열), 예제 코드(`Example6_3.py`, `Example7_5.py`), Kaggle 스크립트(`analyze_leak.py`, `baseline_rank_ic.*`)를 검토하여 작성되었습니다.*
