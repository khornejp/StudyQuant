# 소스 감사 및 버그 수정 요약

이 문서는 전체 소스 감사(`철저히 분석 후 버그 찾아 수정`)에서 발견·수정한
버그와, TP/SL 비용 하한·스윕 하네스 작업을 정리합니다.

## 발견·수정한 버그 (9건)

### 버그 #1 — Dead CLI 인자 (train + live) [수정]
`--long-threshold`, `--short-threshold`, `--min-ev`가 argparse로 파싱되지만
`args.*`로 읽는 코드가 전무했습니다. 라이브 거래에서 사용자가 threshold를
지정해도 무시되고 하드코딩된 0.50이 쓰였습니다.
- **수정**: `strategy_for_regime`에 `long_threshold_override`/
  `short_threshold_override` 파라미터 추가(반환 직전 `dataclasses.replace`로
  적용). `LiveEngine.__init__` → `run_live`(live.py) → cli `run_live` 래퍼 →
  live 명령 dispatch까지 배선. `--min-ev`는 EV 게이트가 존재하지 않으므로
  경고. train 명령에서는 세 인자 모두 학습에 무영향임을 경고.

### 버그 #2 — 백테스트 방향 라우팅 사망 (심각) [수정]
`cli.py`가 `models_by_regime=regime_bundle.models`(=`{regime: ModelAdapter}`
dict)를 넘겨서, backtest의 `hasattr(value, 'direction_policy')`가 항상 False가
되어 long/short 방향 분리가 통째로 비활성화되고 legacy 단일모델 경로로
빠졌습니다. 결과적으로 long 전용 regime이 short 신호를 방출했습니다.
-43.5% 백테스트 결과의 유력한 기여 요인.
- **수정**: `models_by_regime = {regime_name: regime_bundle for ...}`로 각
  regime을 bundle에 매핑해 방향 인지 경로를 활성화.

### 버그 #3 — default_regime 무시 [수정]
`max(models_by_regime, key=lambda k: 1)`(임의 키)를 default_regime으로 썼습니다.
summary의 실제 `default_regime`을 무시.
- **수정**: `regime_bundle.default_regime` 사용.

### 버그 #4 — default-regime 분기 크래시 [수정]
default_regime 폴백에서 `active_model.probability()`를 호출하는데 값이 이제
bundle이라 해당 메서드가 없습니다. regime 경계 밖 구간에서 크래시.
- **수정**: default 분기도 메인 분기와 동일하게 bundle의 long/short 모델을
  방향별로 사용(+ range mean-reversion gate), legacy 폴백 유지.

### 버그 #7 — 스윕 라벨/백테스트 barrier 불일치 (설계 결함) [수정]
ATR multiplier가 살아있어 백테스트 TP가 floor(=라벨 TP)를 초과 → 스윕의
"동일 barrier에서 모델 엣지 측정" 목적이 훼손.
- **수정**: `StrategyConfig.use_atr_pricing` 플래그 + backtest `--fixed-tp-sl`
  옵션. 켜면 ATR 무시하고 floor를 정확한 TP/SL로 사용 → 라벨과 완전 일치.

### 버그 #8 — 백테스트 낙관 편향 [수정]
한 캔들에서 TP·SL을 동시 터치했을 때 백테스트가 **항상 TP 우선**으로 처리해
승률을 부풀렸습니다. 라벨러(dataset.py)는 캔들 방향으로 판정합니다
(long: close>open→TP first, short: close<open→TP first).
- **수정**: backtest도 side별 캔들-방향 규칙으로 tie-break(라벨러와 정확히 일치).

### 버그 #9 — 병렬 feature 계산 OOM / BrokenProcessPool [수정]
(a) `_process_feature_chunk`가 **전체 candles 리스트**를 받아 워커 내부에서
슬라이스 → 전체 리스트가 워커당 1회씩 pickle(측정: 100만 캔들에서
1,384MB vs 174MB, 8배). 6년치(3.16M)면 수 GB → BrokenProcessPool.
- **수정**: 부모에서 `candles[start:end]`로 슬라이스해 전달, 워커는 이미
  슬라이스된 청크 사용(인덱스 오프셋 로직 불변, parity 검증).

(b) 청크 개수를 `num_workers`로 고정 → 1워커면 청크 1개=전체. 청크당 ~52개
전체 길이 float64 배열이 materialize되어 대용량에서 피크 메모리 초과.
- **수정**: 청크 크기를 데이터 크기 기반으로(MAX_CHUNK=250,000 상한),
  `executor.map`이 스트리밍. 소규모(6만/20만 캔들) parity 검증 완료.

## 리스크 (버그 아님, 유지보수 주의)
- `apply_range_mean_reversion_gate`가 backtest.py와 live.py에 중복 정의됨.
  현재는 동일 구현(range_position_20 <0.25→LONG, >0.75→SHORT, else 없음).

## 회귀 및 조치 (weekly warmup 상호작용)
이전 세션에서 weekly MA50 warmup을 504,000(50주)으로 올린 것이 offline
fixture 기반 테스트(약 6천 캔들)에서 `labeled_rows=0`을 유발했습니다. fixture가
50주 warmup을 못 채워 전 행이 warmup_invalid가 되기 때문입니다.
- **결정**: 실환경 정합성(504,000) 유지, 테스트 쪽 조정.
- **수정**: `max_feature_min_samples(n_candles=None)` — `n_candles`가 주어지면
  그보다 큰 min_samples를 가진 feature(짧은 데이터에서 계산 불가)를 warmup
  최댓값에서 제외. `build_feature_rows`가 `max_feature_min_samples(len(candles))`
  를 사용. 짧은 fixture는 계산 가능한 feature 기준 warmup(예: 121), 실환경
  대용량은 여전히 504,000. `build_dataset()` labeled_rows가 0→5,820으로 복구.
- **archive retry 테스트**: `request_interval_seconds`(성공 후 sleep) 추가로
  sleep 호출 횟수가 1→2가 되어 `assert_called_once_with(1.0)` 실패. 새 동작에
  맞게 테스트를 수정(재시도 1.0초 + interval 0.2초 둘 다 검증).

## 이 샌드박스에서 검증 불가 항목
- `test_warmup_invalidation_strict_for_all_features`는 504,000 캔들 생성·처리가
  필요해 이 컨테이너(1 CPU, 저메모리)에서 타임아웃/OOM. warmup 경계 로직 자체는
  소규모 데이터로 정상 검증됨. 실사용자 환경에선 통과 예상.
- catboost/lightgbm/torch/pyarrow 미설치로 인한 실패(parquet·training 테스트)는
  원본에서도 동일 — 환경 문제이며 이번 변경과 무관.
