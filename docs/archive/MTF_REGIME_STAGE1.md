# Regime 개선 (Method B) — Stage 1 완료

## 배경
사용자 지적: auto-regime이 trend_slope_30(1분봉 30개=30분) 하나로만 방향을
판정하는데, manual regime은 며칠~몇달 단위라 스케일이 안 맞음. Method B(근본
해결) 선택: regime을 hard label 대신 확률로, 그리고 그 확률/피처를 entry
모델이 직접 학습하도록.

전체 계획 (사용자 원안 반영):
1. Multi-timeframe feature 엔진 (15m/1h/4h/24h-rolling) — **완료 (이번 세션)**
2. Regime probability classifier (hard label 대신 p_up/p_range/p_down) — 미착수
3. Manual regime 경계 근처 sample_weight 하향 — 미착수
4. 평가 지표 (macro F1, confusion matrix, up↔down vs range 오분류 비대칭) — 미착수
5. 예측 후 smoothing (rolling mean + min duration + confidence threshold) — 미착수
   (참고: min_regime_run_bars 기반 hysteresis는 RegimeDetector에 이미 있음,
   확률 rolling mean 방식으로 확장 필요)
6. 확률을 entry 모델 feature로 통합 — 미착수 (2번 완료 후 가능)

## Stage 1: Multi-timeframe feature 엔진 — 완료, 검증됨

### 만든 것
**btcusdt_quant/mtf_features.py** (신규):
- `resample_causal(candles, minutes)`: 1분봉을 N분 OHLCV로 causal 재집계.
  완전히 닫힌 봉만 emit (미완성 trailing 그룹은 버림).
- 15m/1h/4h 타임프레임별: trend_slope, return, ema_gap, ma_slope, rsi,
  atr_pct, bb_width, adx, volume_z (9개 x 3 = 27개)
- 24h-rolling(1h봉 24개 기준): drawdown_from_24h_high, distance_from_24h_high,
  distance_from_24h_low, rolling_high_breakout_24h, rolling_low_breakdown_24h
  (5개)
- 총 32개 피처, `compute_mtf_features_to_minutes()`로 1분봉에 causal
  forward-fill.

### 왜 metrics(F16)보다 쉬웠나
외부 데이터 다운로드 불필요 — 이미 가진 1분봉을 재집계하는 것뿐. 네트워크,
gap, dedup 문제 없음. 라이브 재현성도 klines만 있으면 100% 가능
(source="klines_1m"으로 등록, required_for_live 제한 없음 — F16 metrics와
달리 라이브 API도 필요 없음).

### feature_registry.py 등록
- F17 카테고리(MULTI_TIMEFRAME)로 32개 등록.
- min_samples는 1분 단위로 환산 (최대 4800분 = 4h봉 20개 필요한
  bb_width_4h/volume_z_4h). weekly warmup(504,000)보다 훨씬 작아 전체 warmup
  불변 확인.
- 최종 피처 수: 184개 (152 + 32).

### dataset.py 통합 — 핵심 위험 지점과 해결
1. **성능**: 최초 구현이 청크 경계마다 전체 이력을 다시 슬라이싱해 사실상
   O(n²) (30일→120일에 처리량 65k/s→24k/s로 저하 확인). `deque(maxlen=24)`로
   교체해 O(n)로 수정. 최종: 1년 8초, 6년 추정 ~48초.
2. **병렬 처리 청크 경계 정확성**: `_build_feature_rows_parallel`이 후보를
   250k개씩 청크로 나누는데, 기존 overlap=500분은 MTF 최대 lookback(4800분)
   보다 훨씬 작아 청크 경계마다 MTF 피처가 부정확해질 위험 확인. overlap을
   500→6000으로 확대.
   - **검증**: os.cpu_count()를 4로 몽키패치해 강제로 4청크 분할, 청크 분할
     결과와 비청크(단일 패스) 결과를 32개 피처 x 40,000행 전부 비교 →
     **완전히 일치(불일치 0개)** 확인. overlap 크기가 충분함을 실증.
3. **look-ahead 방지**: 첫 15분봉이 아직 안 닫힌 구간(00:00~00:14)의 모든
   행이 그 15분봉 급등 정보를 못 보는지 결정적으로 검증. 경계(00:30 등)에서
   정확히 그 시점부터 갱신되는지도 검증.

### 회귀 검증
- test_core: 원본과 완전히 동일한 실패 목록 (diff 없음). 2개 테스트 갱신
  (RSI 중립값 50.0 허용 목록에 rsi_15m/1h/4h 추가 — 기존 rsi_7/14 패턴과
  동일; F16→F17 카테고리 범위).
- test_v718: 이전 세션 기준(원본 대비 회귀 0)과 완전히 동일. 1개 테스트 갱신
  (F16→F17 카테고리 범위).

## Stage 2 (다음 단계, 미착수) — 왜 여기서 멈췄는지

Stage 2(regime probability classifier 학습 + smoothing + entry 모델 통합)는
범위가 크고 이 환경(catboost 없음)에서 끝까지 검증이 불가능해 다음으로
미룹니다. 구체적으로 필요한 것:

1. **Regime classifier 학습**: F17 피처만(또는 F17+기존 trend 계열)을 입력
   으로 up/down/range 확률을 예측하는 multiclass CatBoost. regimes.json의
   hard label을 타깃으로 쓰되, 경계 ±1일 sample_weight 하향.
2. **⚠ 중요 — leakage 위험**: 이 확률을 entry 모델(long/short)의 피처로
   쓰려면, 학습 시 반드시 **out-of-fold 예측**을 써야 함. regime classifier를
   전체 데이터로 학습한 뒤 그 자기 자신에 대한 예측을 entry 모델 피처로
   쓰면, classifier가 학습 데이터를 "암기"한 결과가 새어 들어가 심각한
   과적합이 됨. Walk-forward 방식으로 fold별 out-of-fold 확률을 만들어야
   함 — 별도 설계 필요.
3. **Smoothing**: 확률 rolling mean + 최소 지속시간 + confidence threshold.
   기존 RegimeDetector의 hysteresis(min_regime_run_bars)를 확률 버전으로
   확장.
4. **평가**: macro F1, confusion matrix, up↔down vs range 오분류 비대칭 추적.
5. **entry 모델 재학습**: F17 원시 피처는 이미 184개 피처에 포함되어 있어
   지금 재학습만 해도 entry 모델이 그걸 볼 수 있음 (regime classifier
   확률 없이도). classifier 확률 자체를 추가하려면 2번 leakage-safe 파이프
   라인이 먼저 필요.

## 지금 바로 할 수 있는 것
F17 피처는 이미 전체 파이프라인에 통합됐으므로, **재학습만 하면** entry
모델(long/short)이 이 32개 피처를 즉시 활용할 수 있습니다 (regime
classifier/확률 없이, 원시 MTF 피처로). Method B의 "regime을 모델이 직접
배우게" 정신에 부분적으로 부합 — 다만 지금은 "regime 확률"이 아니라
"regime을 판단할 원재료"를 모델에 준 상태입니다. IC 진단(ic_diagnostic.py)
으로 이 32개 피처의 예측력을 먼저 확인하는 것을 권장합니다.
