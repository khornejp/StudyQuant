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

## Stage 2: Leakage-safe regime probability classifier — 완료, 검증됨

### 만든 것
**btcusdt_quant/regime_classifier.py** (신규):
- `build_purged_kfold_folds(n_rows, n_folds, purge_gap)`: 시간순 K개 구간으로
  분할, 각 구간은 "자기 자신을 제외한 나머지"(+ 경계 purge gap)로 학습된
  classifier가 예측 (Lopez de Prado식 purged K-fold).
- `verify_no_fold_leakage(folds)`: 기계적으로 train/predict 교집합이 0인지
  검사.
- `generate_oof_regime_probabilities(...)`: 전체 구간에 대해 leakage 없는
  out-of-fold 확률 생성. `FoldClassifierFn`(주입 가능한 콜백)로 설계해
  catboost 없이도 로직 검증 가능, 실전에선 CatBoost 멀티클래스로 교체.
- `transition_zone_sample_weights(...)`: manual regime 경계 ±N일 구간을
  낮은 가중치(기본 0.1)로 (완전 제외 아님 — 전환 중이라는 정보 자체는
  살림).
- `smooth_regime_probabilities(...)`: rolling mean + 최소 지속시간 +
  confidence threshold. 노이즈엔 안 흔들리고 지속 신호엔 전환.
- `evaluate_regime_classifier(...)`: macro F1, confusion matrix,
  **up↔down(위험) vs range↔trend(덜 위험) 오분류를 분리 집계**.

### 검증 (전부 이 환경에서 완료, catboost 불필요)
- **핵심 leakage 검증**: "암기형" 가짜 classifier로 각 fold의 predict 대상
  인덱스가 그 fold의 학습에 단 한 번도 등장 안 함을 결정적으로 확인
  (fold별 로컬 dict로 각 fold 독립 검증, 0건).
- fold 전체 커버리지(중복/누락 없음), purge gap 실제 작동 확인.
- transition zone: 경계 ±1일 안은 0.1, 밖은 1.0 정확히 적용됨 확인.
- smoothing: 100틱 안정 up → 50틱 노이즈(안 흔들림, 계속 up 유지) → 200틱
  확실한 down 전환(정확히 전환됨) 시나리오로 검증.
- 평가지표: 완벽예측 F1=1.0; up↔down 오분류 20건 vs range 오분류 10건을
  각각 정확히 분리 집계하는 것 확인.

### CLI/파이프라인 통합
- **`train-regime-classifier` 명령** (신규): candles+regimes.json →
  F17 피처 계산 → OOF 확률 생성 → smoothing → 평가 → 전체 데이터로 최종
  classifier 재학습(라이브/백테스트용) → `regime_probabilities.json` +
  `regime_classifier_report.json` 저장.
- **F18 카테고리** (feature_registry.py): `regime_prob_up/range/down` 3개,
  `required_for_live=False`(라이브 서빙 미구현), source="regime_classifier".
- **`train --regime-classifier-dir`**: 저장된 확률을 external_sources로
  병합 (F16 metrics와 동일 패턴). 없으면 0 degrade.
- **파이프라인 Phase 2.5**: `run_full_pipeline.ps1/.sh`에 regime classifier
  학습 단계 추가, Phase 3a/3b 둘 다 `--regime-classifier-dir` 연결.
- 최종 피처 수: **187개** (184 + F18 3개).

### 회귀 검증
- test_core, test_v718 모두 이전 세션 기준과 diff 0 (완전 일치). 카테고리
  테스트 2개를 F18 반영해 갱신(F01~F18).
- end-to-end mock 테스트: 2만 행 합성 데이터로 `train-regime-classifier`
  전체 파이프라인 실행 → `regime_probabilities.json` 정상 생성 → 그 파일이
  `train`의 병합 로직과 형식 호환됨 확인.

### 의도적으로 남긴 트레이드오프 (문서화됨, 코드 주석에도 명시)
purged K-fold는 fold 학습 시 시간상 **미래 fold도 학습에 포함**될 수 있음
(엄격한 walk-forward라면 과거만 써야 함). 이건 "행이 자기 라벨을 보는"
치명적 leakage와는 다른 범주로, OOF 스태킹 피처 생성의 표준 관행(Kaggle류
스태킹에서 일반적)이지만, 엄격한 인과성 관점에선 약한 정보 누설(미래 분포의
한계값이 fold 경계 근처 calibration에 영향)이 있을 수 있음을 인지하고
진행. 실사용 배포 classifier는 전체 데이터로 한 번 더 학습(위 "최종
classifier").

## 다음 단계 (미착수)
1. **사용자 환경에서 실행**: `train-regime-classifier` → macro F1/confusion
   matrix로 실제 classifier 품질 확인 (이 환경은 mock이라 의미 없는 랜덤
   결과만 냄).
2. **entry 모델 재학습**: `--regime-classifier-dir`로 F18 포함 재학습 →
   2025 백테스트로 최종 확인. **여기서 특히 볼 것**: 학습기간 성능과 2025
   진짜 out-of-sample 성능 사이 격차.
3. 라이브 서빙 classifier 경로 (현재 research-only, required_for_live=False)

## C. Regime 라우팅 자체를 F17/F18 classifier로 교체 (근본 수정)

### 발견된 간극
사용자 지적: "지금 auto-regime은 trend_slope_30 하나만 본다. 만든 F17/F18은
왜 라우팅에 안 쓰였나?" — 정확한 지적이었음. Method B 작업(Stage 1/2)에서
F17 멀티 타임프레임 피처와 F18 regime 확률 classifier를 만들었지만, 그
출력은 entry 모델의 **추가 입력 피처**로만 쓰였을 뿐, "어느 regime 모델을
호출할지" 정하는 **라우팅 자체**는 여전히 `RegimeDetector.detect_all_directional`
(trend_slope_30 하나)에 의존하고 있었음. 즉 만든 정보를 실제로 안 쓰고 있었음.

### 왜 "라이브 서빙 미구현"이 핑계가 안 되는가
사용자 지적: 백테스트는 과거 데이터 batch 추론이라 실시간 인프라가 애초에
불필요하고, 라이브도 "저장된 모델 로드해서 매 틱 predict_proba 한 번"이면
충분 — 지금 long/short 모델을 로드해 쓰는 것과 동일한 패턴. 이전 세션의
"라이브 서빙 인프라 없어서 보류"는 과도한 판단이었음. 수정.

### 일관성이 핵심
학습 시 "이 캔들이 어느 regime 모델의 훈련 데이터인지" 나누는 기준과,
백테스트/라이브에서 "지금 어느 regime 모델을 호출할지" 정하는 기준이
**반드시 같은 모델·같은 함수**여야 함. 다르면 up 모델이 훈련 때 못 본
종류의 "up" 구간을 실전에서 만나는 train/serve skew가 생김.

### 구현
1. **regime_classifier.py**
   - `RegimeClassifierModel`: 저장/로드 가능한 멀티클래스 CatBoost 래퍼
     (.cbm 포맷, 기존 CatBoostAdapter는 이진분류 전제라 재사용 불가 —
     `predict_proba`가 양성 클래스 하나만 반환하는 구조라 3클래스에 안 맞음).
   - `route_regime_causal(feature_rows, classifier, smoothing_config)`:
     **학습·백테스트·라이브가 전부 호출하는 단일 함수.** F17 벡터를 넣으면
     raw 확률 + smoothing 적용된 assigned regime을 반환.
   - mtf_features.py에 `extract_feature_vector()` 추가 — 어디서 호출하든
     동일한 순서로 F17 벡터를 뽑아 라우팅 입력이 절대 어긋나지 않게 함.

2. **cli.py**
   - `_fit_final_multiclass_classifier`: 전체 데이터로 최종 classifier를
     fit해 `RegimeClassifierModel`로 반환 (fold별 임시 classifier와는 별개
     — fold classifier는 F18 OOF 확률 생성용, 이건 실제 라우팅 배포용).
   - `train-regime-classifier`가 이제 `regime_classifier_model.cbm`을
     `regime_probabilities.json`과 함께 저장.
   - `train --regime-classifier-dir`: F18 피처 병합에 더해, 같은 디렉토리의
     `.cbm`을 로드해 `TrainingConfig.regime_classifier_model_path`로 전달
     → 학습 bucket 배정에 사용.
   - `backtest --regime-classifier-dir`: 같은 `.cbm`을 로드해 라우팅에 사용.
     `--auto-regime`보다 우선순위 높음(둘 다 주면 classifier가 이김, 경고 출력).

3. **training.py**
   - `TrainingConfig.regime_classifier_model_path` 필드 추가.
   - `run_regime_aware_training`: 경로가 있으면
     `route_regime_causal(F17 벡터, classifier)`로 bucket 배정
     (`regime_source="regime_classifier"`), 없으면 기존
     `detect_all_directional` fallback (`regime_source="detector_directional"`).

4. **backtest.py**
   - `run_backtest`/`compare_strategies`에 `regime_classifier_model` 파라미터
     추가. 있으면 `route_regime_causal`로 라우팅(우선), 없으면 기존
     `regime_detector` fallback. `--user-regime-file`이 최우선(불변).

5. **파이프라인 (run_full_pipeline.ps1/.sh)**
   - Phase 4가 `--auto-regime` 대신 `--regime-classifier-dir $RegimeClassifierDir`
     사용 — **Phase 2.5가 만들고 Phase 3이 학습에 쓴 것과 정확히 같은
     디렉토리(같은 .cbm)**를 백테스트도 씀. 이게 일관성의 실체.

### 검증
- `RegimeClassifierModel` 저장→로드 왕복 후 예측 동일함 확인 (mock).
- `route_regime_causal` 결과가 라벨 순서(REGIME_CLASSES: down/range/up)와
  정확히 매핑됨 확인.
- `run_regime_aware_training`: classifier 경로/fallback 경로 각각
  `regime_source`가 정확히 "regime_classifier"/"detector_directional"로
  기록됨 확인.
- `run_backtest`: classifier로 라우팅 시 신호가 예측대로 나옴(mock이 항상
  "up" 확신 → SELL 0건, matched=200) 확인.
- **핵심 통합 테스트**: `train-regime-classifier` → `train --regime-classifier-dir`
  → `backtest --regime-classifier-dir`를 실제 `cli.main()` 경로로 전부
  실행, Phase 3(`regime_source: regime_classifier`)과 Phase 4
  (`regime_coverage: matched=12000`, 폴백 0)가 **동일 모델로 완전히
  일관되게 라우팅**됨을 end-to-end 확인.
- test_core/test_v718 회귀 없음(diff 0).

### 여전히 남은 선택지 (fallback 유지)
`--regime-classifier-dir`를 안 주면 기존 `trend_slope_30`(RegimeDetector)
경로가 그대로 작동함 — 하위호환 유지, classifier 없이도 파이프라인이
깨지지 않음. 다만 **실전 정확도를 원하면 Phase 2.5부터 다시 돌려 새
classifier로 Phase 3/4를 재실행해야** 이번 수정의 이득(F17 멀티 타임프레임
정보가 실제로 라우팅에 반영됨)을 봄.

## D. 간접 누설(모델 fitting leakage) 발견 및 수정

### 사용자 지적
"regime-classifier로 나온 결과로 long/short 모델을 학습하면 시계열이 섞일
위험은 없나?" — 정확한 지적이었고, 실제로 C 항목의 구현에 문제가 있었음.

### 정확히 무엇이 문제였나
라벨(row 자신의 미래 가격) 자체가 새는 "직접 누설"은 없었음 — F17 피처는
여전히 과거 캔들로만 계산됨. 문제는 **간접적인 형태**였음:

학습 bucket 배정(Phase 3)에 `regime_classifier_model.cbm`(2020~2024 전체로
fit된 "최종" classifier)을 다시 불러 **재예측**하고 있었음. 이 최종
classifier는 예를 들어 2021년 캔들의 regime을 판정할 때도, 자기 학습
과정에서 2023~2024년 데이터를 이미 본 상태로 답함. row 자신의 라벨을 보는
건 아니지만, "이 시대 전체의 패턴"이라는 형태로 미래 정보가 판정에
스며듦 — 학습용 bucket 배정이 실전(2025, 진짜 처음 보는 데이터)보다
부자연스럽게 "깨끗하게" 나와서, 또 다른 형태의 train/serve 불일치를 만듦.

### 수정
- **training.py**: 학습 bucket 배정에서 `.cbm` 재로드·재예측을 제거.
  대신 `build.labeled_rows[i].features`에 이미 병합된 F18 값
  (`regime_prob_up/range/down` — walk-forward OOF로 이미 안전하게 계산됨)을
  그대로 읽어 `smooth_regime_probabilities`로 argmax만 적용. **classifier
  파일 자체를 열 필요가 없어짐** (검증: 존재하지 않는 `.cbm` 경로를 줘도
  학습 성공 — 재예측을 안 하니 파일이 아예 불필요함을 증명).
- F18 값이 전부 0(즉 `--regime-classifier-dir`로 병합 안 된 상태)이면
  명확한 `ValueError`로 막음 — 조용히 degenerate한 배정(전부 같은 클래스)
  으로 새지 않게.
- **backtest.py**: 그대로 유지 — 2025년 데이터는 그 classifier가 fit할 때
  한 번도 본 적 없는 "진짜 out-of-sample"이라 `.cbm` 재예측이 안전함. 이
  경우엔 최종 classifier 사용이 맞는 선택. 주석으로 이 비대칭(학습은 OOF
  재사용, 백테스트는 최종모델 재예측)의 이유를 명시.
- `TrainingConfig.regime_classifier_model_path`와 CLI help 문구를
  "이 파일로 예측한다"가 아니라 "F18 값이 안전하다는 신호로만 쓰인다"로
  정정.

### 검증
- F18 값이 정상 병합된 경우: `regime_source: "regime_classifier"`로 정확히
  배정, 존재하지 않는 `.cbm` 경로에도 학습 성공(재예측 로직 자체가 없어
  파일이 필요 없음을 증명).
- F18 값이 전부 0인 경우: 명확한 `ValueError` 발생 확인.
- Phase 2.5→3→4 전체 통합 재검증: 여전히 end-to-end로 정상 작동, 이제
  Phase 3은 OOF 값 재사용(안전), Phase 4는 최종모델 재예측(2025는 진짜
  미지 데이터라 안전) — 두 단계가 서로 다른, 각자 올바른 방식을 씀.
- 전체 회귀 테스트 diff 0.

## 추가 수정: Walk-forward 전환 + user-regime 학습 삭제

### A. Purged K-fold → 엄격한 Walk-forward로 전환
사용자 지적: "미래 fold가 학습에 들어가면 안 될 것 같다." 정확한 지적이었음
— 기존 purged K-fold는 fold i의 학습에 시간상 **미래** fold도 포함될 수
있었음(OOF 스태킹의 표준 관행이지만 엄격한 인과성엔 어긋남).

- `build_purged_kfold_folds` → `build_walk_forward_folds`로 교체: fold i는
  오직 fold 0..i-1(과거)만으로 학습, 미래 fold 사용 절대 없음.
- fold 0(과거 데이터 없음)은 OOF 예측 불가 → neutral(1/3,1/3,1/3) 기본값
  (다른 warmup 피처들과 동일한 "정보 없음" 관례).
- **결정적 재검증**: 모든 fold에서 `max(train_indices) < min(predict_indices)`
  임을 확정 (미래 데이터가 학습에 전혀 안 섞임). 암기형 classifier로
  leakage 재검증도 통과.
- 코드/문서 전체(cli.py, feature_registry.py, sources.py, 파이프라인
  스크립트)에서 "purged K-fold" 문구를 "walk-forward"로 정정.

### B. 사용자 regime 설정 및 사용자 regime 학습 삭제
사용자 판단: "추후를 생각하면 쓸모없는 부분" — user-regime(regimes.json
hard label)으로 entry 모델을 직접 학습·라우팅하는 경로는 미래(라이브)엔
재현 불가능(사후 정보 필요)하므로 유지할 이유가 없음.

**삭제된 것:**
- `training.py`: `TrainingConfig.use_user_regime` 필드, `_run_user_regime_training`
  함수 전체 삭제. `run_regime_aware_training`은 이제 항상 detector(실시간
  방향 감지) 경로만 씀.
- `cli.py`: `train`의 `--use-user-regime`/`--user-regime-file` 인자 삭제.
  ignored-flags 경고를 `--regime-aware` 조건으로 이전(동일 경고 내용,
  detector 경로에도 여전히 유효).
- `run_full_pipeline.ps1/.sh`: Phase 3a(user 학습)/Phase 4a(labeled 백테스트)
  및 "labeled vs auto" 비교 로직 삭제. Phase 3/4 각 하나로 단순화 (detector
  학습 + auto-regime 백테스트만).
- `tp_sl_sweep.ps1/.sh`: `--use-user-regime`→`--regime-aware`,
  `--user-regime-file`→`--auto-regime`로 교체. VALIDATION_START/END,
  --test-start/end 등 부수 정리.
- `run_pipeline.ps1`(레거시 스크립트, 이전 세션에서 안 건드렸던 파일):
  동일하게 `--use-user-regime`→`--regime-aware`,
  `--user-regime-file`→`--auto-regime`로 최소 수정해 실행 가능하게 유지.
- `tests/test_v718.py`: `TestUserRegime` → `TestUserRegimePeriods`로 개명,
  삭제된 기능(`use_user_regime` 필드, `_run_user_regime_training` 호출)을
  테스트하던 2개 제거. **여전히 유효한** `resolve_user_regime`/
  `load_user_regime_periods` 테스트 3개는 보존(train-regime-classifier가
  계속 이 함수들로 regimes.json을 ground-truth 라벨로 읽으므로).

**유지된 것 (중요 — 완전 삭제 아님):**
- `regimes.json` 파일 자체와 `dataset.resolve_user_regime`/
  `load_user_regime_periods` 함수: **train-regime-classifier의 ground-truth
  라벨 소스**로 계속 사용됨. F18 regime probability classifier는 여전히
  이 hand-label을 학습 타깃으로 삼되, 그 classifier 자체는 F17(causal
  multi-timeframe 피처)만으로 추론하므로 라이브에서도 재현 가능. "사후
  정보로 직접 라우팅"만 없앴을 뿐, "사후 정보를 학습 타깃 삼아 causal한
  classifier를 배우는" 것은 유지.
- backtest의 `--user-regime-file`/`--auto-regime` 두 옵션 모두 CLI에 유지
  (학습 경로만 삭제, 백테스트 진단 옵션은 손대지 않음).

### 회귀 검증
- test_core: 원본 대비 diff 0 (완전 일치).
- test_v718: 원본 대비 새 실패 0개, 오히려 1개 감소(삭제된 기능을 테스트
  하다 원래도 실패하던 테스트를 정당하게 제거 — 개선).
- 전체 컴파일, 모든 파이프라인 스크립트 문법 검사 통과.


