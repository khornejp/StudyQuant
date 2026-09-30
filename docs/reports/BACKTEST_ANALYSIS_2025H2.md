# 백테스트 결과 분석 및 수정 (2025 H2)

## 관찰된 증상
- 거래 165건이 **전부 BUY, SELL 0건**
- net -1.49%, **gross도 -0.18%**
- outcome: TP 26 / SL 72 / TIMEOUT 67
- gross 승률 43%, net 승률 37.6%

## 근본 원인 (설정 문제)
`regimes.json`이 **2024-12-31에서 끝나는데** 백테스트는 **2025-07-01부터** 시작.
백테스트 전 구간이 regime 정의 밖 → 모든 캔들이 `default_regime="up"`으로 폴백.
`up` regime은 long 전용(direction_policy={"LONG"})이므로 **SELL이 원천 불가**.

결과적으로:
- down regime의 short 모델(logloss 0.642, 엣지 있음)이 전혀 안 쓰임
- range regime 모델도 안 쓰임
- up/long 모델 하나로만 6개월 거래
- 게다가 2025 H2는 실제로 하락장($126k→$88k)이라 long-only는 필연적 손실

즉 "regime-aware 백테스트"가 이름뿐이고 실제론 단일 모델 백테스트였음.
그리고 이 폴백이 **아무 경고 없이** 조용히 발생.

## 수정 1: regimes.json을 2025년까지 연장
실제 2025년 BTC 가격 흐름(웹 조사)으로 regime 경계 추가:
- 7월: $120k~124k 돌파 (up)
- 8월 중순~9월 초: 고점 정체 (range)
- 9월 초~중순: $108k 조정 (down)
- 9월 말~10월 초: 금리인하 반등 → $126k ATH (up)
- 10월 초~12월: 관세쇼크 급락 → $84k~88k (down)

백테스트 기간(2025 H2) regime 분포: down 105일, up 49일, range 30일.
이제 down/range가 등장 → short 모델 활성화 → SELL 가능.

**중요 한계**: 2025 regime은 **사후 라벨링**(look-ahead bias)이라 실전 성능이 아님.
"regime 라우팅이 작동할 때 모델이 어떤지" 측정용. 실전/포워드는 RegimeDetector로
실시간 감지해야 함(regimes.json은 과거 라벨일 뿐 미래를 알 수 없음).

## 수정 2: regime 커버리지 경고 (코드 견고성)
`BacktestResult.regime_coverage`에 matched/default_fallback/no_model 집계 추가.
백테스트 후 cli가 검사:
- matched==0: "모든 bar가 default_regime으로 폴백, regime 파일이 백테스트 기간
  미커버, 방향 라우팅이 사실상 단일 regime" 경고
- fallback>20%: 커버리지 공백 경고
백테스트 summary JSON에도 regime_coverage 기록.

이제 이번 같은 상황이 재발하면 즉시 경고가 뜸.

## 검증 (이 환경 = catboost/pyarrow 없음, 실데이터 없음)
- regime resolve: 2025 H2 날짜가 정확한 regime으로 매핑됨 확인
- SELL 라우팅: down 구간 mock 백테스트에서 SELL 200개 발생 확인 (이전 0개)
- 경고 로직: regime 정의 밖 기간에서 matched=0 → 경고 발동 확인
- 실제 catboost 모델 재백테스트는 이 환경에서 불가(라이브러리/데이터 없음) →
  실환경에서 재실행 필요.

## 다음 단계
1. 실환경에서 새 regimes.json으로 백테스트 재실행 → SELL 발생, gross 지표 확인
2. gross가 여전히 ~0이면 모델 엣지 문제 (range/long logloss 0.736은 여전히 red flag)
3. 실전 배포 시엔 --use-user-regime 대신 RegimeDetector 자동 감지 사용
   (regimes.json은 미래를 커버할 수 없음)

## 수정 3: RegimeDetector 실시간 감지 (실전 대비)
미래에는 regime을 미리 알 수 없으므로 실시간 감지가 필수. 두 가지를 추가/수정:

### 문제: 라벨 체계 불일치
- RegimeDetector.detect()는 high_volatility/trending/ranging 반환 (변동성/추세 강도)
- 학습된 모델은 up/down/range 키 (방향)
- 기존 live.py 자동 감지 폴백은 detect()를 써서 "trending" 등을 냈고, 이는
  모델 키와 매칭 안 됨 → direction_policy 기본값 폴백 → 신호 안 나옴 (사실상 고장)

### RegimeDetector에 방향 감지 추가 (features.py)
- `_classify_directional`: trend_slope_30의 부호로 up/down/range 판정
- `fit_directional_threshold`: 방향 임계를 별도 percentile(기본 0.55)로 보정
  (강도용 0.90 percentile은 방향 판정엔 너무 엄격해 전부 range가 됨)
- `detect_all_directional`: 전 구간 방향 regime + hysteresis (백테스트용)
- `detect_directional`: 단일 bar 방향 감지 (라이브용)
- 기존 detect()/detect_all()은 불변 (강도 기반 진단은 그대로)

### 백테스트 배선 (backtest.py, cli.py)
- run_backtest/compare_strategies에 regime_detector 파라미터 추가
- 주어지면 feature_rows의 trend_slope_30/rv_15로 실시간 regime 산출해
  user_regime을 덮어씀 (frozen dataclass라 dataclasses.replace 사용)
- CLI `--auto-regime` 플래그 추가. --user-regime-file이 있으면 그게 우선(경고).

### 라이브 배선 (live.py)
- 자동 감지 폴백을 detect() → detect_directional()로 교체.
  이제 up/down/range를 내므로 모델 라우팅이 정상 작동.
- 버퍼된 feature_rows의 slope 이력으로 방향 임계 실시간 보정.

### 검증
- 방향 감지: 상승/횡보/하락 구간을 up/range/down으로 정확히 분류
- 백테스트 auto-regime: user-regime-file 없이 하락 추세에서 SELL 발생 (mock)
- 라이브 감지: slope 부호로 up/down/range 반환 (모델 키 일치)
- 기존 RegimeDetector 테스트 4개 통과 (회귀 없음)

### 사용법
- 실전/포워드: `backtest --auto-regime` (regimes.json 없이 실시간 감지)
- 과거 검증: `backtest --user-regime-file regimes.json` (사후 라벨, look-ahead)
- 라이브: regime_aware 모드에서 user_regime 없으면 자동으로 방향 감지 폴백
