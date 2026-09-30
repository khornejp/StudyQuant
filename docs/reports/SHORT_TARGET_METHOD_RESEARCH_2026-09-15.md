# PatchTST 숏 타겟·보유시간 방법론 진단

작성일: 2026-09-15  
범위: BTCUSDT 선물 숏 모델, 1분 봉, 15분 간격 신호, 지정가 진입, 실주문 제외

## 결론

현재 프로젝트에는 **종가 하락폭, 최대 하락폭(MFE), TP 선도달 여부 중 하나만 고르는 방식이 맞지 않는다.** 숏의 방향을 맞히는 것이 본질이지만, 실제 거래 가능한 방향성은 다음 두 질문으로 분리해야 한다.

1. 지정가 숏 주문이 제한 시간 안에 체결되는가?
2. 체결된 뒤 60분 안에 TP와 SL 중 무엇이 언제 먼저 도달하는가?

주 타겟은 `TP-first / SL-first / timeout`과 도달 시간을 함께 나타내는 **체결 조건부 경쟁위험(first-touch competing-risk) 타겟**이 적합하다. PatchTST 인코더는 유지하되 출력 헤드를 바꾸면 된다. 최대 하락폭은 큰 하락의 존재를 알려주는 보조 타겟으로 유지하되, 최대 역행폭(MAE)과 반드시 쌍으로 학습해야 한다. 종가 또는 미래 평균 종가 방향은 “방향 학습 자체가 되는가”를 확인하는 대조군으로 남긴다.

첫 실험의 고정 대조 조건은 `H=60분, TP=20bps, SL=20bps`가 합리적이다. 이것은 최적 수익 파라미터라는 뜻이 아니라, 1분 OHLC에서 모호성이 0.265%로 작고 timeout이 12.45%여서 타겟 식별성이 좋은 기준점이라는 뜻이다. 수익 파라미터는 2020~2025의 학습·검증 구간에서만 고르고 2026에 한 번 적용해야 한다.

## 1. 이번 로컬 진단의 범위

- 표본: 기존 주간 walk-forward PatchTST의 고정 OOS 신호 시점 192,947개
- 기간: 2021-01-08 00:00 UTC ~ 2026-08-31 23:30 UTC
- 폴드: 292개
- 신호 간격: 15분
- 비교 horizon: 15, 20, 25, 30, 35, 40, 45, 50, 55, 60분
- 가격: 원본 1분 OHLC
- 새 모델 학습: 0회
- 백테스트: 0회
- 같은 1분 봉에서 TP와 SL이 모두 닿은 경우: 임의 순서 부여 없이 `ambiguous`

재현 파일은 `out/short_horizon_path_diagnostic_20260915`에 있으며 입력과 출력 SHA-256이 기록돼 있다. 이 진단은 시장 분포와 라벨 구조를 보는 작업이지, horizon이나 배리어를 OOS 수익으로 선택하는 작업이 아니다.

중요한 제한도 있다. 이번 집계에서 2026년 결과를 이미 보았으므로 2026은 더 이상 완전히 눈가림된 최종 시험 구간은 아니다. 다음 실험의 파라미터 선택은 2020~2025 안에서 끝내고, 2026은 사전 고정한 모델의 평가에만 사용해야 한다. 완전히 새 눈가림 구간이 필요하면 2026-09 이후 데이터를 별도로 보존해야 한다.

## 2. 15~60분 하락폭 비교

단위는 bps이며 숏에 유리한 하락을 양수로 표시했다. `terminal`은 정확히 H분 뒤 종가, MFE는 구간 내 최저가 기준 최대 유리 이동, MAE는 최고가 기준 최대 불리 이동이다.

| H(분) | terminal >4 | terminal >40 | terminal >100 | MFE q90 | MFE >40 | MFE >100 | MAE q90 | MAE >40 | MAE >100 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 40.43% | 5.75% | 0.80% | 46.39 | 13.02% | 1.94% | 45.47 | 12.49% | 1.80% |
| 20 | 41.57% | 7.46% | 1.19% | 54.65 | 16.79% | 2.87% | 53.26 | 16.16% | 2.66% |
| 25 | 42.32% | 8.70% | 1.56% | 61.15 | 19.78% | 3.73% | 59.24 | 19.01% | 3.45% |
| 30 | 42.44% | 9.70% | 1.87% | 66.72 | 22.22% | 4.55% | 64.97 | 21.55% | 4.21% |
| 35 | 43.20% | 10.87% | 2.25% | 72.70 | 24.90% | 5.40% | 70.52 | 24.14% | 5.04% |
| 40 | 43.42% | 11.88% | 2.58% | 78.04 | 27.04% | 6.20% | 75.41 | 26.26% | 5.76% |
| 45 | 43.55% | 12.62% | 2.92% | 82.54 | 28.91% | 7.01% | 79.92 | 28.14% | 6.50% |
| 50 | 44.00% | 13.50% | 3.26% | 87.73 | 30.90% | 7.84% | 84.82 | 30.13% | 7.28% |
| 55 | 44.25% | 14.32% | 3.62% | 92.26 | 32.60% | 8.59% | 88.87 | 31.76% | 7.99% |
| 60 | 44.27% | 14.91% | 3.87% | 96.11 | 34.03% | 9.29% | 92.87 | 33.33% | 8.70% |

해석:

- 사용자가 지적한 “실제로 1% 넘게 하락하는 경우가 많다”는 관찰은 맞다. 구간 내 저가를 보면 100bps 이상 하락은 15분 1.94%, 60분 9.29%다.
- 기존 5분 종가 타겟이 이를 거의 보지 못했던 이유는 시장에 하락이 없어서가 아니라, **정확히 5분 뒤 종가만 본 타겟이 중간 급락과 되돌림을 버렸기 때문**이다.
- 그러나 MFE가 커지는 만큼 MAE도 거의 대칭으로 커진다. 60분 MFE q90은 96.11bps, MAE q90은 92.87bps다. MFE만 양성 라벨로 쓰면 “먼저 크게 올랐다가 나중에 내린 경로”까지 좋은 숏으로 잘못 학습한다.
- 미래 평균 종가는 DeepLOB이 사용하는 방향 라벨과 유사한 노이즈 완화 대조군이다. DeepLOB은 한 시점의 미래 가격 대신 미래 가격 평균을 이용하고, 더 일관된 신호가 불필요한 거래와 비용을 줄인다고 설명한다.[^3] 다만 평균 가격은 실제 청산 가격이 아니므로 최종 수익 타겟이 될 수 없다.

## 3. TP가 SL보다 먼저 도달했는가

### 대칭 20bps 배리어

| H(분) | TP first | SL first | 같은 봉 모호 | timeout | 모호 제외 TP 비중 | 중앙 도달시간 |
|---:|---:|---:|---:|---:|---:|---:|
| 15 | 28.98% | 27.89% | 0.257% | 42.88% | 50.95% | 5분 |
| 20 | 33.10% | 31.79% | 0.257% | 34.85% | 51.01% | 6분 |
| 25 | 35.85% | 34.49% | 0.257% | 29.40% | 50.97% | 6분 |
| 30 | 37.77% | 36.50% | 0.260% | 25.47% | 50.85% | 7분 |
| 35 | 39.56% | 38.19% | 0.260% | 21.99% | 50.88% | 8분 |
| 40 | 40.92% | 39.55% | 0.261% | 19.27% | 50.86% | 8분 |
| 45 | 41.90% | 40.64% | 0.263% | 17.19% | 50.76% | 8분 |
| 50 | 42.90% | 41.56% | 0.263% | 15.29% | 50.79% | 9분 |
| 55 | 43.69% | 42.36% | 0.263% | 13.69% | 50.77% | 9분 |
| 60 | 44.29% | 42.99% | 0.265% | 12.45% | 50.75% | 9분 |

H가 길어질수록 timeout은 줄지만, 모호하지 않은 전체 표본의 TP 비중은 계속 약 51%다. 즉 first-touch 라벨로 바꾸는 것만으로 엣지가 생기지는 않는다. 모델이 조건부 확률을 50% 부근에서 충분히 끌어올릴 수 있는지가 핵심이다.

### 60분에서 배리어 폭 비교

| TP/SL | TP first | SL first | 같은 봉 모호 | timeout | 모호 제외 TP 비중 | 중앙 도달시간 | 비용 포함 손익분기 TP 비중* |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 8/8bps | 48.95% | 47.17% | 2.962% | 0.92% | 50.93% | 2분 | 75.00% |
| 12/12bps | 48.77% | 46.84% | 1.129% | 3.26% | 51.01% | 4분 | 66.67% |
| 20/20bps | 44.29% | 42.99% | 0.265% | 12.45% | 50.75% | 9분 | 60.00% |
| 40/40bps | 29.94% | 28.81% | 0.029% | 41.23% | 50.96% | 19분 | 55.00% |
| 60/60bps | 19.47% | 18.56% | 0.012% | 61.96% | 51.19% | 25분 | 53.33% |

\* 왕복 maker 수수료 4bps, 모호와 timeout을 제외한 단순 해석이다. Bitget의 표준 선물 maker 수수료는 주문가치의 편도 0.02%이므로 왕복 4bps가 맞다.[^11] 대칭 배리어 B의 손익분기 TP 비율은 `(B + 4) / (2B)`다.

이 표가 보여주는 것은 다음과 같다.

- 8bps는 중앙 2분 만에 끝나고 같은 1분 봉 모호성이 2.96%다. 수수료 때문에 75% 승률이 필요하므로 주 타겟 후보로 부적합하다.
- 40~60bps는 모호성이 거의 없지만 60분에도 timeout이 41~62%다. 학습 표본 대부분이 배리어 승패 정보를 주지 않는다.
- 20bps는 첫 실험의 **식별성 대조군**으로 가장 균형이 좋다. 단, 20/20이 실제 최적 TP/SL이라는 결론은 아니다.
- 비용 때문에 동일 승률 50%를 손익분기로 만들려면 gross TP가 SL보다 8bps 더 커야 한다. 예를 들어 28/20bps가 비용 중립 구조다. 대칭군과 함께 20/12, 28/20, 40/32 같은 비용 보정 후보를 학습 구간에서만 비교할 가치가 있다.

## 4. 어떤 라벨이 무엇을 답하는가

| 라벨 | 답하는 질문 | 장점 | 치명적 한계 | 역할 |
|---|---|---|---|---|
| H분 종가 수익률 | H분 뒤 가격이 낮은가 | 단순하고 방향 평가가 명확 | 중간 급락·반등을 모두 버림 | 방향 대조군 |
| 미래 평균 종가 | 향후 평균 가격대가 낮은가 | 노이즈와 신호 뒤집힘 완화 | 실제 체결·청산 가격이 아님 | 노이즈 완화 대조군 |
| MFE | 구간에 얼마나 큰 하락이 있었나 | 큰 하락 존재를 직접 포착 | 도달 순서·MAE·실현 가능성 무시 | MAE와 함께 보조 회귀 |
| TP-first | TP가 SL보다 먼저인가 | 거래 규칙과 직접 대응 | horizon·barrier 하나마다 별도 이진 문제 | 3-class 기준선 |
| 이벤트 종류+시간 | 무엇이 언제 먼저인가 | 모든 H의 누적확률을 한 모델로 산출 | 라벨·평가가 조금 더 복잡 | 권장 주 타겟 |
| 전체 경로 분포 | 가능한 미래 경로들은 무엇인가 | 임의 TP/SL을 사후 계산 가능 | joint path가 필요하고 검증 비용 큼 | 2단계 이후 후보 |
| Sharpe/RL 직접 최적화 | 정책 수익을 최대화하는가 | 이론상 목적과 직접 연결 | 체결 시뮬레이터 오류를 학습하며 표본·안정성 문제 큼 | 현재 보류 |

Triple Barrier는 위·아래 가격 배리어와 시간 배리어 중 먼저 닿은 것을 라벨로 삼아 고정 종가 라벨보다 실제 TP/SL 규칙에 가깝다.[^5] 2025년 BTC/ETH 연구도 next-bar보다 triple-barrier가 더 현실적이고 수익 결과가 나았다고 보고했지만, 변동성으로 배리어 자체를 동적으로 조정한 실험은 오히려 개선되지 않았다.[^4] 그러므로 “트리플 배리어가 항상 우월하다”거나 “변동성 배리어가 정답”이라고 가정하면 안 되고, 우리 데이터에서 고정 배리어와 causal 변동성 표본추출을 분리해 검증해야 한다.

## 5. 권장 타겟 구조

### 5.1 가장 작은 유효 변경

현재 모델은 정식 PatchTST를 그대로 사용한 것이 아니라, 60개 1분 입력을 길이 12·stride 6의 9개 patch로 만들고 35개 채널에 공유 Transformer를 적용한 `ShortPatchTST_adaptation`이다. 원 논문의 핵심인 patching과 channel-independent encoder는 반영돼 있지만, 원 논문은 장기 시계열 회귀 구조를 검증한 것이며 거래 라벨의 선택을 보증하지 않는다.[^1][^2]

인코더는 그대로 두고 마지막 head만 다음처럼 비교한다.

```text
60분 × 35변수 입력
        │
PatchTST 공유 인코더
        ├─ 방향 head: 미래 평균 숏 수익 > 비용 문턱 (대조군)
        ├─ 이벤트 head: TP@1..60, SL@1..60, timeout = 121-class
        └─ 보조 head: MFE와 MAE quantile
```

`121-class` softmax 하나는 10개 horizon별 분류기를 따로 만드는 것보다 작고 일관적이다. 출력 확률을 누적하면 요청한 모든 horizon을 얻는다.

```text
P(TP first by H) = Σ(t=1..H) P(TP at t)
P(SL first by H) = Σ(t=1..H) P(SL at t)
P(survive H)     = 1 - 위 두 누적확률
```

이는 첫 도달 시간과 여러 경쟁 사건을 직접 학습하는 DeepHit의 문제 설정과 맞는다. DeepHit은 사건 종류와 시간을 함께 갖는 competing risks의 분포를 신경망으로 직접 학습한다.[^6][^7] 우리 경우 관찰창이 모두 60분으로 고정돼 있어 우선은 완전한 survival 프레임워크를 들여오지 않고 PyTorch softmax head 하나로 같은 핵심 질문을 검증할 수 있다.

### 5.2 MFE는 버리지 말고 MAE와 묶는다

큰 하락 포착을 위해 MFE를 auxiliary quantile regression으로 둔다. 단독 MFE 예측은 금지한다. 모델이 다음을 함께 내야 한다.

- `q50/q75/q90(MFE_60)`
- `q50/q75/q90(MAE_60)`
- 필요하면 `MFE - λ·MAE`를 학습구간에서만 진입 점수로 조합

이렇게 해야 “큰 하락 가능성”과 “그 전에 손절될 위험”을 동시에 평가할 수 있다. MFE/MAE는 진입 ranking 보조값이지 실현 PnL이 아니다.

### 5.3 전체 경로 예측은 후순위

PatchTST가 미래 경로의 확률분포를 직접 생성하고 각 모의경로에서 TP/SL 순서를 계산하는 방법도 있다. 그러나 시점별 marginal quantile만으로는 시간 간 의존성과 순서를 알 수 없다. Nixtla의 확률 예측 문서도 여러 시점이 얽힌 사건은 marginal interval이 아니라 joint distribution이 필요하다고 명시한다.[^9] 따라서 현재 15-step MSE 경로 head에 quantile loss만 붙이는 것으로 first-touch를 해결할 수 없다. 121-class가 실패하거나 여러 TP/SL 조합을 한 모델에서 즉시 평가해야 할 때만 joint path 모델로 확장한다.

## 6. 지정가 전용 프로젝트에서 빠진 단계

현재 진단은 신호 시점 종가에 즉시 진입했다고 가정한 **가격경로 진단**이다. 이것은 지정가 실행 타겟과 동일하지 않다. 수동 주문은 체결되지 않을 수 있고, 체결 시간과 queue 위치에 따라 실제 진입가와 이후 60분 경로가 달라진다. LOB 기반 지정가 체결 연구도 passive order의 핵심 변수를 fill probability와 fill time의 분포로 둔다.[^8]

최종 라벨 생성 순서는 다음이어야 한다.

```text
신호 → maker 지정가 제출 → {미체결, 체결시간 τ_fill}
                         체결된 경우에만
                         → {TP first, SL first, timeout, τ_exit}
```

따라서 모델도 최소 두 단계가 맞다.

1. `P(fill by entry_expiry)`와 체결시간을 예측한다.
2. 체결 표본에서 `P(TP/SL/time | fill)`을 예측한다.

체결 모델에 사용할 tick/L2 데이터가 부족한 기간은 낙관적 즉시체결로 메우지 않는다. 그 기간은 방향 head 학습에는 쓰되 실행 head 학습에서는 제외하거나, 보수적 OHLC 체결 규칙을 별도 스트레스 시나리오로만 보고해야 한다.

## 7. 현재 코드에서 바로 고쳐야 할 연구 규칙

현재 공용 라벨러는 같은 1분 봉에서 TP와 SL이 모두 닿으면 봉이 음봉일 때 TP-first로 간주한다. `short_exit_sweep`도 같은 규칙을 쓴다. OHLC는 봉 안의 순서를 담지 않으므로 candle color로 순서를 복원할 근거가 없다. VectorBT 같은 오픈소스 엔진도 동일 봉의 신호 처리에 명시적 우선순위 가정을 둔다.[^10]

- 위치: `btcusdt_quant/dataset.py:2704`, `btcusdt_quant/short_exit_sweep.py:68`
- 연구 라벨: `ambiguous`로 분리하고 학습에서 mask
- 보수 스트레스: 전부 SL-first로 계산
- 정확한 판정: 더 세밀한 trade/tick 자료로만 복원

8bps에서는 이 문제가 전체의 2.96%이므로 결과를 실질적으로 흔든다. 20bps에서는 0.265%로 작지만 그래도 임의 분류하면 안 된다. 이번에는 진단만 수행했으며 기존 생산 함수를 아직 변경하지 않았다.

## 8. 검증 설계

### 데이터 분할

- 2020~2025: 모델 학습, threshold·barrier·horizon 선택
- 7일 단위 walk-forward OOS: 기존 200개 이상 폴드 설계 유지
- 2026: 고정 모델의 최종 평가. 이미 집계 결과를 본 사실을 보고서에 명시
- 2026-09 이후: 가능하면 완전 신규 holdout

H=60분 라벨은 신호 뒤 60분 가격을 사용한다. 각 train/validation/test 경계에서 최소 60분을 purge해야 한다. 15분마다 신호를 만들면 H60 라벨은 최대 네 개가 중첩된다. 중첩 표본을 독립으로 간주하지 말고 다음 중 하나를 고정 대조군으로 둔다.

- 모든 15분 신호 + label concurrency의 역수 가중치
- 학습 표본만 60분 간격으로 얇게 뽑는 독립성 대조군

오버랩 라벨의 train/test 경계 누수를 막기 위해 purging과 embargo를 적용하는 공개 구현도 있다.[^12]

### 모델 평가지표

백테스트 전에 다음을 통과해야 한다.

1. 방향 head: fold별 ROC-AUC, PR-AUC, balanced accuracy, calibration
2. 이벤트 head: H=15..60의 TP/SL cumulative incidence Brier score, log loss, calibration
3. ranking: 상위 1/5/10%에서 `TP first` precision과 `SL first` 비율
4. 보조 head: MFE/MAE pinball loss와 quantile coverage
5. 안정성: fold 과반이 아니라 최소 60% 이상에서 동일 방향 개선, 연도별 부호 확인

정확도 50%를 넘는지만 보면 안 된다. symmetric 20bps와 4bps 비용에서는 resolved TP precision 60%가 단순 손익분기이므로, 선택된 신호의 교정된 조건부 확률이 그 문턱을 넘어야 한다. timeout의 실제 청산 수익과 미체결까지 포함한 최종 문턱은 학습 구간에서 다시 계산한다.

## 9. 실험 순서와 중단 기준

### E0 — 라벨 대조군

- 동일 PatchTST 인코더
- A: H15 기존 종가 방향
- B: H60 미래 평균 종가 방향
- C: H60 20/20bps 3-class (`TP/SL/timeout`, 도달시간 제외)
- 목적: 라벨만 바꾸었을 때 방향 ranking이 실제로 개선되는지 확인
- 중단: C가 B보다 TP-vs-SL ranking과 calibration 모두 못하면 복잡한 survival head를 만들지 않는다.

### E1 — 이벤트 시간 head

- E0-C가 통과할 때만 121-class head 적용
- H=15..60은 같은 출력의 누적합으로 평가
- MFE/MAE quantile head는 보조 loss로 추가
- 중단: 2020~2025 OOS에서 상위 decile의 TP precision이 비용 문턱에 못 미치면 백테스트로 넘어가지 않는다.

### E2 — 배리어 구조

- 고정 대칭: 20/20, 40/40
- 비용 보정: 20/12, 28/20, 40/32
- 변동성은 배리어에 강제로 곱하는 arm과 입력 feature로만 주는 arm을 분리
- 모든 선택은 2020~2025 내부 OOS만 사용
- 2025년 crypto 연구에서 volatility-scaled barrier가 개선되지 않았으므로 동적 배리어를 기본값으로 승격하지 않는다.[^4]

### E3 — 지정가 체결 결합

- tick/L2가 존재하는 구간에서 fill-time 모델
- `P(fill) × E[net payoff | fill]`로 최종 진입 ranking
- 보수/기준 체결 시나리오가 모두 양수일 때만 실행 백테스트

### E4 — 최종 백테스트

- E0~E3가 통과한 뒤 한 번 수행
- maker 수수료, funding, timeout 청산, 포지션 중첩, 주문 만료 포함
- 실주문은 여전히 금지

## 최종 판단

TP가 SL보다 먼저 도달했는지를 보는 방향은 **현재 프로젝트에 맞다.** 다만 그것을 단일 H·단일 배리어 이진 라벨로 만들면 horizon 선택, timeout, 체결 실패, 같은 봉 모호성을 잃는다. 가장 적합한 재설계는 다음 한 문장으로 요약된다.

> PatchTST는 숏 방향·경로 특징을 추출하는 인코더로 유지하고, 지정가 체결 후 TP/SL first-touch의 종류와 시간을 주 타겟으로 학습하며, MFE와 MAE를 보조 타겟으로 함께 예측한다.

지금 즉시 RL이나 대규모 joint-path 생성기로 갈 필요는 없다. 기존 인코더와 3-class head로 라벨 가설을 먼저 반증하고, 통과할 때만 121-class 이벤트 시간 head로 확장하는 것이 가장 짧고 검증 가능한 경로다.

## Sources

[^1]: Yuqi Nie et al., [A Time Series is Worth 64 Words: Long-term Forecasting with Transformers](https://arxiv.org/abs/2211.14730), ICLR 2023.
[^2]: Yuqi Nie et al., [Official PatchTST implementation](https://github.com/yuqinie98/PatchTST).
[^3]: Zihao Zhang, Stefan Zohren, Stephen Roberts, [DeepLOB: Deep Convolutional Neural Networks for Limit Order Books](https://arxiv.org/html/1808.03668v6), IEEE TSP 2019.
[^4]: Przemysław Grądzki, Piotr Wójcik, Stefan Lessmann, [Algorithmic crypto trading using information-driven bars, triple barrier labeling and deep learning](https://link.springer.com/article/10.1186/s40854-025-00866-w), Financial Innovation 2025.
[^5]: Hudson & Thames, [Triple-Barrier and Meta-Labelling documentation](https://random-docs.readthedocs.io/en/latest/implementations/tb_meta_labeling.html).
[^6]: Changhee Lee et al., [DeepHit: A Deep Learning Approach to Survival Analysis With Competing Risks](https://ojs.aaai.org/index.php/AAAI/article/view/11842), AAAI 2018.
[^7]: Changhee Lee et al., [Official DeepHit implementation](https://github.com/chl8856/DeepHit).
[^8]: Alvaro Arroyo et al., [Deep Attentive Survival Analysis in Limit Order Books: Estimating Fill Probabilities with Convolutional-Transformers](https://arxiv.org/abs/2306.05479), 2023.
[^9]: Nixtla, [NeuralForecast Simulation Paths: marginal vs. joint distributions](https://nixtlaverse.nixtla.io/neuralforecast/docs/tutorials/simulation.html).
[^10]: VectorBT, [Portfolio stop-signal implementation and same-bar priority assumption](https://github.com/polakowo/vectorbt/blob/master/vectorbt/portfolio/base.py).
[^11]: Bitget, [Product Fees FAQ](https://www.bitget.com/support/articles/12560603892733), updated 2026-08-20.
[^12]: Evgenii Lazarev, [purgedcv: leakage-aware cross-validation implementation](https://github.com/eslazarev/purged-cross-validation).
[^13]: Marc Chiuminatto, [triple_barrier open-source labeler](https://github.com/mchiuminatto/triple_barrier).
