# 외부 버그 리포트 검증 및 수정 (2026-07-03)

사용자가 다른 도구/세션의 분석 리포트를 전달. 그대로 믿지 않고 6개 항목을
전부 실제 코드로 재검증 후, **6개 전부 실제 버그로 확인**되어 수정.

## 1. Regime classifier 확률 매핑 버그 — 확인, 수정
**문제**: `_catboost_multiclass_fold_classifier`와 `RegimeClassifierModel.
predict_proba`가 `predict_proba()`의 컬럼 순서를 `REGIME_CLASSES`
(down,range,up) 고정 순서로 가정. Walk-forward fold의 학습 데이터에 3개
클래스가 다 없으면(초기 fold에 특정 regime이 아직 안 나타난 경우 등),
CatBoost의 실제 컬럼 순서(`model.classes_` 기준)와 어긋나 확률이 완전히
잘못된 클래스에 배정될 수 있었음.

**수정**: `model.classes_`로 실제 컬럼→라벨 매핑을 읽어 사용. 누락된
클래스는 명시적으로 0.0 (다른 클래스 확률을 훔쳐오지 않음).

**검증**: `classes_=[1,2]`(down 누락) mock으로 클래스 누락 시나리오 재현,
수정 전이라면 `down=0.4, range=0.6`처럼 완전히 틀렸을 상황이 이제
`down=0.0, range=0.4, up=0.6`으로 정확히 매핑됨을 확인.

## 2. 백테스트 F18 feature 누락 — 확인, 수정
**문제**: `run_backtest`/`compare_strategies`가 `route_regime_causal()`의
반환값 중 `detected`(라우팅 결정)만 쓰고 `raw_probs`(실제 확률)는
버림(`_, detected = ...`). 그 결과 entry 모델이 학습 때는
`regime_prob_up/range/down`를 실제 값으로 보고, 백테스트/라이브에서는
0.0(fallback 기본값)으로 봄 — 입력 분포가 학습과 다름.

**수정**: `raw_probs`를 버리지 않고 `dataclasses.replace`로
`FeatureRow.features`에 `regime_prob_up/range/down`을 실제로 병합.

**검증**: mock classifier(`{down:0.2, range:0.3, up:0.5}`)로 병합 후
`feature_rows[i].features['regime_prob_up']`이 정확히 0.5로 들어감을 확인
(이전엔 0.0이었을 상황).

## 3. test-period 평가가 `full_labeled_rows` 대신 `build.labeled_rows` 사용 — 확인, 수정
**문제**: `training_end` 이후(예: 2025 H1) test period 평가가
`build.labeled_rows`(이미 `training_end`로 잘린 데이터)에서 행을 찾음 —
그 이후 데이터는 애초에 없으니 **항상 빈 결과**. `full_labeled_rows`
파라미터를 받아놓고 안 씀.

**수정**: `full_labeled_rows`(잘리기 전 전체)를 test row 소스로 사용.

**검증**: 학습 구간 밖 미래 400행(3개 regime 섞음)으로 재현, 수정 전엔
`build.labeled_rows`만 봐서 0행 매치, 수정 후 정확히 400행 발견·평가됨.

## 4. model.json 파일명 불일치로 test-period 평가 자체가 무실행 — 확인, 수정
**문제**: 저장되는 파일은 `long_model.json`/`short_model.json`인데 평가
코드는 `model.json`을 찾음 — 파일이 존재한 적이 없어 매번 조용히
`continue`, 즉 **이 블록이 한 번도 실행된 적이 없었음**.

**수정**: `long_model.json`/`short_model.json` 각각 로드해 `long_success`/
`short_success` 타깃으로 정확히 평가.

**검증**: 3번 검증과 함께 확인 — `regime_metrics` 키가 `range_long`,
`range_short`로 정확히 나타남 (이전엔 파일을 못 찾아 빈 dict).

## 5. holdout 진단이 in-sample — 확인, 수정 (가장 심각)
**문제**: regime holdout 평가(`_train_single_regime`)가 `long_model`/
`short_model`(배포용, **regime 전체 데이터로 학습**)을 그대로 holdout
tail 평가에 사용. 그 tail은 배포용 모델이 이미 `.fit()`에서 본 데이터라
**완전히 in-sample**. 지금까지의 regime holdout F1/Acc/baseline
improvement, `threshold-objective`로 고른 임계값 **전부 오염**되어 있었음.

**수정**: holdout 평가 전용 "진단 모델"을 **prefix(앞 80%)만으로 별도
학습**해 tail에서 평가하도록 분리. 배포용 모델(전체 데이터 학습)과
진단용 모델(prefix만 학습)을 명확히 구분.

**검증**: mock으로 `fit()` 호출마다 입력 크기를 기록 — 배포용 884행,
진단용 707행(prefix, holdout 133행 제외)으로 **서로 다른 크기**로 별도
fit됨을 확인. 로그에도 `(diagnostic model trained on prefix only, n=707)`
명시.

## 6. 라이브 auto-regime threshold train/serve skew — 확인, 수정
**문제**: 라이브 라우팅이 학습 시 저장된 `dir_threshold`
(`regime_bundle.detector_thresholds`)를 무시하고, 매 추론마다 라이브
버퍼(최근 데이터)로 threshold를 다시 계산. 학습 때 계산된 threshold와
실전에서 쓰는 threshold가 다를 수 있음.

**수정**: 저장된 `dir_threshold`가 있으면 우선 사용, 없을 때만(구버전
아티팩트 등) 라이브 버퍼로 fallback 계산.

**한계**: 이 경로는 detector fallback(trend_slope_30) 라우팅 전용. F18
classifier 기반 라우팅의 라이브 대응은 **아직 미구현** — live.py에
`route_regime_causal`/`regime_classifier_model` 연결이 없음. 별도 작업 필요.

## 회귀 검증
전체 컴파일 통과. test_core/test_v718 모두 수정 전후 diff 0 (완전 일치,
errors=7+14=21, skipped=1+6=7, failures=0+2=2 그대로). 사용자가 언급한
`test_live_loads_detector_thresholds`는 이 환경(catboost 미설치)에서 원래도
실패하던 환경 문제이지 회귀가 아님 — catboost 있는 환경에서 별도 확인 필요.

## 총평
6개 지적 모두 실제 버그였고, 특히 5번(holdout in-sample)은 이번 세션에서
제가 직접 만든 코드의 결함이라 가장 심각했음. 이 세션 내내 반복된 패턴 —
"안전한 것처럼 보이는 코드도 실제로 값을 추적해서 확인해야 한다"는 원칙이
외부 리포트 검증에서도 그대로 적용됨. 외부 리포트를 무비판적으로 적용하지
않고 각 항목을 재현 가능한 mock 테스트로 직접 검증한 뒤 반영.
