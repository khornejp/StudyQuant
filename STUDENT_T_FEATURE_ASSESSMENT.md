# Student-t Feature 설계안 검토 — 기존 피처로 커버 가능한가

> 작성일: 2026-07-11
> 대상 문서: `BTCUSDT_StudentT_Feature_Design.md`
> 결론: **바로 적용하지 않는다.** 제안된 8개 피처 중 6개는 기존 180개 피처와 사실상 중복이고, 유일한 gap(꼬리 두께)은 무거운 Student-t MLE 없이 **rolling kurtosis 1개**로 대체 가능하다. 이 문서는 판단 근거만 기록하며, 실제 구현은 실데이터 IC 확인 후 별도 결정.

---

## 1. 요약

`BTCUSDT_StudentT_Feature_Design.md`가 제안하는 것: 1분 로그수익률 → EWMA 표준화 → 표준화 잔차에 대칭 Student-t를 매 60분 MLE 적합 → `df`, `scale`, `surprise`, `signed_surprise` 등 8개 피처를 CatBoost에 추가.

**방법론은 탄탄하고 우리 원칙(causal 계산, ablation, IC 우선 검증)과 잘 맞는다.** 그러나 Student-t가 노리는 세 가지 정보를 우리 피처와 실측 대조한 결과:

| Student-t 개념 | 우리 자산 | 판정 |
|---|---|---|
| surprise (부호 없는 이상도) | `close_zscore_20/60`, `rv_zscore_60`, `vwap_deviation_zscore` 등 18개 | **이미 있음** (상관 0.975) |
| signed_surprise (방향 있는 이상 움직임) | `return_*_vol_adj` 등 15개 | **이미 있음** (상관 0.994) |
| df (꼬리 두께) | rv 계열은 있으나 **kurtosis 없음** | **유일한 gap → rolling kurtosis로 대체** |

---

## 2. 실측 근거

스모크 데이터(24k봉, 추세/레인지 혼합)에서 문서의 recipe 그대로 Student-t 피처를 프로토타이핑하고, 기존/값싼 대체물과의 Spearman 순위상관을 측정했다.

### 2.1 forward 60바 수익률에 대한 IC

```
student_t_signed_surprise         IC = +0.2364   (강해 보이지만…)
(기존) raw signed z                IC = +0.2405
  corr(둘) = +0.994               → 사실상 같은 신호. 중복.

student_t_surprise (부호 없음)    IC = -0.0628
(기존) |z| magnitude              IC = -0.0211
student_t_df                      IC = +0.0386
```

→ signed 계열은 기존 vol-adjusted 수익률과 중복. 부호 없는 surprise / df만 직교하나 IC가 약함(~0.04–0.06).

### 2.2 기존/값싼 대체물이 Student-t 피처를 얼마나 재현하나

```
student_t_surprise  ~  |z| (close_zscore식)     : +0.975   ← 사실상 동일
student_t_df        ~  rolling excess kurtosis  : -0.735   ← 강한 대응 (df↓ = kurt↑)
df(MLE) vs df(=6/kurt+4), fat-tail 구간          : +0.596   ← 공식 변환이 MLE를 추적
```

핵심: **`df = 6/kurtosis + 4`** 관계라, 표준화 잔차의 rolling excess kurtosis 하나가 MLE 없이 df와 같은 정보를 준다.

### 2.3 스모크 데이터의 한계 (실데이터에서 결과가 바뀔 수 있는 부분)

- `df`가 5 ~ 1.5e13까지 폭발했다. 합성 데이터가 거의 가우시안이라 꼬리가 없어 df가 상한으로 간 것.
- **실제 BTC는 fat-tail이라 df가 대략 3~8에 몰릴 것**이므로, 위 IC(특히 df)는 실데이터보다 **과소평가**일 가능성이 크다.
- df↔kurtosis 대응(0.60)도 fat-tail 구간에서 더 안정적으로 나올 여지가 있다.

---

## 3. 결론 — 무엇을, 어떻게

### 하지 말 것
- **Student-t MLE 파이프라인 전체** (매 60분 재적합 × 6년 ≈ 43,000회, 10,080봉 warmup, scipy 의존, 수렴 실패/짧은 window 불안정 — 문서 §4.2 단점).
- **`surprise` / `signed_surprise` 계열 추가** — 기존 `close_zscore_*` / `return_*_vol_adj`와 상관 0.975/0.994. 다중공선성만 늘고 IC는 이미 우리 피처가 보유.

### 검토할 것 (실데이터 IC 확인 후 결정)
- **rolling excess kurtosis 1~2개** (`kurtosis_60` 또는 `_20`/`_120`). 우리가 `rv_*`를 계산하는 것과 같은 causal rolling window에서 표준화 잔차의 4차 모멘트로 계산. Student-t가 노리는 유일한 gap(꼬리 두께)을 MLE 없이 커버.
- 필요 시 `tail_thickness = 1/(6·max(kurt,ε)⁻¹ + 4)` 유도 가능하나, 우선 kurtosis 하나만.

### 개념적 위치
```
Student-t 8개 피처
  ├─ surprise (4개)          → close_zscore_*, rv_zscore_60 로 이미 커버 (중복)
  ├─ signed_surprise (2개)   → return_*_vol_adj 로 이미 커버 (중복)
  └─ df / tail_thickness (2개) → rolling kurtosis 1개로 대체 (MLE 불필요)   ← 유일하게 신규
```

---

## 4. 만약 진행한다면 (구현 스케치, 미착수)

`btcusdt_quant/feature_registry.py`의 F03 VOLATILITY 계열에 causal rolling 피처로 추가하는 형태. 기존 `rv_60`(min_samples=61)과 같은 규칙:

```python
# feature_registry.py (예시, 미적용)
_feature("kurtosis_60", "F03", VOLATILITY,
         "excess kurtosis of vol-standardized 1m returns over 60 bars ending at t",
         min_samples=61, warmup=61, source="klines_1m", deps=("return_1",))
```

- 표준화: 기존 vol_adj 피처들이 쓰는 EWMA/rolling vol을 재사용 (자기 자신이 분모에 안 들어가도록 shift).
- causal 검증: `verify_weekly_causality.py`의 truncation-invariance 패턴 재사용 — 전체 시계열로 계산한 값이 임의 prefix로 계산한 값과 바 단위로 일치해야 함.
- warmup: 60~120봉 추가 (주간 MA50 warmup 504,000봉에 비하면 무시할 수준).

---

## 5. 권장 다음 단계 (실행 전 게이트)

1. 실제 2020–2025 parquet에서 `kurtosis_60`(및 `_20`, `_120`)을 causal하게 시험 계산.
2. `python ic_diagnostic.py --input artifacts/btcusdt_2020_2025.parquet --regime-file regimes.json --metrics-dir artifacts/metrics --output artifacts/ic_kurtosis`
3. 판정 기준 (문서 §10.3 + 우리 ic_diagnostic 관례):
   - 레짐별 IC가 `rv_zscore_60`과 크게 겹치면 → 그것도 중복, 추가 안 함.
   - `|IC| < 0.01`이면 dead feature, 추가 안 함.
   - fold별 IC 표준편차가 평균보다 크면 불안정 — 레짐 의존성인지 노이즈인지 재검토.
   - 리키지 플래그가 뜨면 truncation-invariance 테스트로 확정 후 판단.
4. 통과 시에만 feature_registry에 편입하고 2025 OOS ablation(logloss / net sharpe / calibration).

---

## 6. 한 줄 결론

**Student-t 설계안의 방법론은 좋지만, 신규 정보는 "꼬리 두께" 하나뿐이고 그마저 rolling kurtosis 1개로 값싸게 얻을 수 있다.** MLE 파이프라인 전체를 짓기 전에, kurtosis 피처의 실데이터 IC부터 재는 것이 맞다. 실데이터에서 df/kurtosis가 대부분 상한에 붙거나 IC가 0.01 미만이면, 붙이지 않는 것이 올바른 판단이다.
