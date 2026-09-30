# 이중 regime 학습 (user-regime vs detector) — 구현 완료

## 배경 문제
이전엔 학습이 user-regime(up/down/range) 하나만 했는데, auto-regime 백테스트도
그 user-regime 모델을 재사용 → 불공정 비교. 게다가 detector 학습 경로는
high_volatility/trending/ranging(강도 기반)로 되어 있어:
- _train_single_regime의 long/short 정책(up→long, down→short, range→둘다)과 안 맞아
  train_long=train_short=False → 아무 모델도 학습 안 됨
- auto-regime 백테스트(up/down/range)와 키가 안 맞아 라우팅 죽음

## 수정 내용
1. **training.py detector 경로를 방향 기반으로 전환**
   - detect_all → detect_all_directional (up/down/range)
   - fit_thresholds → fit_directional_threshold
   - _REGIME_NAMES(강도) → dataset.USER_REGIME_NAMES(방향)
   - run_summary에 regime_source="detector_directional" 명시
   - 이제 _train_single_regime의 long/short 정책과 정합, 저장 구조도 regime_up/
     regime_down/regime_range로 user 모델과 동일 → 백테스트 로딩 호환

2. **파이프라인 이중 학습 (Phase 3a/3b)**
   - 3a: --use-user-regime → regime_stacking_model (user 방향 라벨)
   - 3b: (플래그 없음) → regime_stacking_model_auto (detector 실시간 방향)

3. **백테스트 각자 자기 모델 사용 (Phase 4a/4b)**
   - 4a: --user-regime-file + regime_stacking_model
   - 4b: --auto-regime + regime_stacking_model_auto ← 이제 자기 모델
   - 공정 비교: "같은 up/down/range인데 경계를 손으로 vs 알고리즘으로"

## 비교의 의미
- 4a (user): regime 경계를 사람이 손으로. 2025는 사후 라벨이라 look-ahead 있음.
  "완벽한 regime을 알 때의 상한선".
- 4b (auto): regime을 실시간 감지. 실전 배포와 정합. "실제로 가능한 성능".
- 4a >> 4b: 모델이 완벽한 regime 예지에 의존 → 실전 부진 예상.
- 4a ≈ 4b: detector가 regime 구조를 잘 재현 → 배포 가능.

## 주의
- 학습 시간 2배 (모델 2개). Optuna 30 trials × (regime×방향) × 2.
- 이 환경(catboost 없음)에선 실제 학습 검증 불가. regime 분류·long/short 매핑·
  저장/로딩 호환은 mock 검증 완료. 실제 F1/gross는 사용자 환경 필요.
- detector 3b 학습에도 --metrics-dir 적용됨 (F16 metrics 피처 포함).

## 검증
- detector가 up/down/range 방향 이름 출력 확인
- _train_single_regime long/short 정책과 일치 (up→long, down→short, range→둘다)
- 백테스트 load_regime_aware_models가 regime_{name} 디렉토리로 로드 → 호환 확인
- test_core 원본과 동일(errors=7 환경 문제) → 회귀 없음
