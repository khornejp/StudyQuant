# 누수 방지 · 교차검증 (btcusdt_quant)

이 레포에서 성능 신뢰의 전부는 "미래가 과거로 새지 않는다"에 달려 있다. 이 파일은 이미 구현된 CV 도구를
어떻게 써야 하는지와, 새 코드에서 누수를 만들지 않는 법을 정리한다.

## 절대 하지 말 것

- **랜덤 split / shuffle split.** 시계열이므로 `train_test_split(shuffle=True)`나 임의의 KFold를 쓰지
  않는다. train은 항상 validation/test보다 과거여야 한다.
- **전체 구간에 통계 fit.** 스케일러·정규화·feature-selection·regime 통계를 전체 데이터에 fit한 뒤
  split하면 미래 정보가 샌다. 반드시 train 구간에서만 fit한다.
- **경계를 넘는 라벨/윈도우.** 라벨 horizon이 있는 샘플이 test 구간과 겹치면 train에서 purge해야 한다.
  시퀀스 윈도우가 train/test 경계를 걸치면 test 정보를 포함한다.

## 이미 있는 도구를 쓴다 (`cv.py`)

새로 split 로직을 짜지 말고 기존 것을 쓴다.

- **`SplitManager.get_splits(...)`** — 진입점. `cv_mode`로 방식을 고른다:
  - `"walk_forward"` → purged walk-forward(`features.PurgedWalkForwardSplit`). `purge_gap`이 없으면
    `label_horizon`을 gap으로 쓴다.
  - `"combinatorial_purged"` → `CombinatorialPurgedCV`(CPCV). `n_groups`, `test_group_count`,
    `embargo_size`를 받는다.
  단계별 헬퍼(`get_feature_selection_splits`, `get_hpo_splits`, `get_calibration_splits`,
  `get_threshold_splits`, `get_test_splits`)가 있으니 각 파이프라인 단계는 해당 헬퍼를 쓴다. 결과는 캐시된다.

- **`CombinatorialPurgedCV`** — test 그룹과 겹치는 학습 샘플을 `purged`로 제거하고, test 윈도우 뒤
  `embargo_size`만큼을 `embargoed`로 제거한다. split 결과에는 `train/validation/test/purged/embargoed`가
  모두 담겨 무엇이 제외됐는지 추적 가능하다.

- **`sample_intervals_from_labeled_rows(rows, label_horizon=...)`** — 라벨의 시작·끝 인덱스로
  `SampleInterval`을 만든다. 라벨이 미래로 뻗는 구간(`end_index`)이 purge/embargo 계산의 기준이다.

- **`uniqueness_weights(intervals)`** — 겹치는 라벨의 concurrency로 sample uniqueness 가중치를 계산한다
  (겹칠수록 낮은 가중치). 학습 시 이 가중치를 쓰면 중복 정보로 인한 과대평가를 줄인다. 새 학습 코드에서
  가중치가 필요하면 여기서 얻는다.

## 새 feature를 만들 때 (look-ahead 방지)

- 롤링/이동평균은 과거만 보게 한다. `center=True` 금지, 미래 `shift(-k)` 금지(타깃 생성 제외).
- 타깃(다음 봉 수익률/방향 등)은 `shift(-k)`로 만들되, 그 타깃이 feature 쪽으로 새지 않게 한다. 라벨이
  미래로 뻗는 만큼이 곧 purge horizon이다 — registry의 `lookback`/`warmup_rule`과 CV의 `label_horizon`을
  일치시킨다.
- warmup 구간(통계가 아직 안 찬 초반)은 registry의 `warmup_rule`대로 처리한다. 조용히 0으로 채우지 않는다.

## Train/serve parity 점검

CV가 아무리 깨끗해도 serve 경로가 다르게 계산하면 소용없다. 새 코드가 다음을 지키는지 본다:

- 학습에서 fit한 통계를 `to_dict`로 저장하고 backtest/live에서 `from_dict`로 복원해 **같은 값**으로 점수를
  낸다. live 버퍼에 재-fit하지 않는다.
- feature가 train과 live에서 동일 공식으로 계산된다(feature parity gate). live 전용 소스가 없을 때의
  fallback 기본값이 train 분포와 어긋나지 않게 한다.

## 검증 신호

- **"성능이 비현실적으로 좋다" → 누수부터 의심.** split·통계 fit 위치·feature의 미래 참조·regime 라벨
  출처를 위 기준으로 되짚는다.
- CPCV split의 `purged`/`embargoed`가 비어 있으면(라벨 horizon이 있는데도) purge 설정이 빠졌을 수 있다.
- 라벨 horizon과 CV `label_horizon`/`purge_gap`이 어긋나면 경계 누수가 생긴다 — 값이 일치하는지 확인.
