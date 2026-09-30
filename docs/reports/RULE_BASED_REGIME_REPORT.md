# 룰베이스 Regime Detector 전환 보고서 (2026-07-03)

결정: regime 라우팅을 학습형 classifier에서 **멀티피처 룰베이스 디텍터**로 전환.
학습형 classifier 코드는 삭제하지 않고(테스트/CLI 보존) 파이프라인 경로에서만 제외.

## 새 컴포넌트

`btcusdt_quant/regime_rules.py` — `MultiFeatureRegimeDetector`
(+ `MultiFeatureRegimeConfig`). 설계 노트 7–14절 스펙 구현.

- **입력**: 기존 F17 멀티타임프레임 피처(추가 피처 엔지니어링 불필요).
- **점수**: trend / volatility / range / breakout 를 조합.
  - trend = w·z(trend_slope_1h, trend_slope_4h, return_4h, ema_gap_4h)
  - vol = w·z(atr_pct_1h/4h, bb_width_1h)
  - range = 역z(adx_1h/4h, bb_width_1h) + 24h밴드 중심 근접도
  - breakout = rolling_high_breakout_24h / rolling_low_breakdown_24h + volume_z_1h
- **결정**: breakout 즉시 override → range/up/down 임계값 판정. 진입/유지
  임계값을 분리한 **히스테리시스**(trend_enter=0.70 / trend_exit=0.40)와
  **min_hold_bars=60** 안정화.
- **정규화**: `fit()`이 학습구간에서 피처별 (mean, std)를 구해 저장하고,
  backtest/live는 이 통계를 **그대로 재사용**(live 버퍼 재적합 금지) →
  per-bar 점수가 학습과 정확히 일치, train/serve skew 없음.
- **인과성**: per-bar 점수는 그 bar 피처 + 고정 통계에만 의존, 순차 상태는
  과거에만 의존. 미래 미참조. 저장/복원(`to_dict`/`from_dict`)으로 재현 가능.

## 배선 (세 경로 일관)

동일한 fitted 디텍터가 세 곳을 구동하도록 연결:

1. **학습 bucket 배정** (`training.py::run_regime_aware_training`):
   `--multi-feature-regime` 시 룰 디텍터로 bucket 배정(최우선). fitted 디텍터를
   `regime_run_summary.json`의 `multi_feature_regime_detector`에 저장.
2. **백테스트** (`backtest.py::run_backtest`, `compare_strategies`):
   `multi_feature_regime_detector` 인자 추가, 최우선 라우팅. CLI가 아티팩트의
   `regime_run_summary.json`에서 디텍터를 로드해 주입(있으면 classifier/auto 무시).
3. **live** (`live.py`): `RegimeModelBundle.multi_feature_regime_detector`로 실어
   `_compute_signal`에서 Priority 2(user_regime 다음, classifier·slope보다 우선)로
   `detect_one(버퍼)` 라우팅. 별도 CLI 플래그 불필요 — 아티팩트가 자기 라우터를
   내장.

CLI: `train --multi-feature-regime` 추가(--regime-classifier-dir보다 우선, 동시
지정 시 경고). backtest/live는 아티팩트에서 자동 감지.

## ⚠️ 필수: entry 모델 재학습

라우터가 바뀌면 bucket 정의가 바뀝니다. 기존 entry 모델은 classifier(또는
trend_slope_30) bucket으로 학습됐으므로, **`--multi-feature-regime`로 학습을 다시
돌려** entry 모델을 룰 bucket에 맞춰야 합니다. 안 그러면 라우터-모델 불일치
(train/serve skew)가 재발합니다. 순서:

```
python -m btcusdt_quant train --multi-feature-regime --regime-aware \
    --training-start 2020-01-01 --training-end 2024-12-31 ... 
# → regime_run_summary.json 에 fitted 룰 디텍터 저장 + entry 모델이 룰 bucket으로 학습됨

python -m btcusdt_quant backtest --model-artifact <위 출력 디렉터리> ...
# → 아티팩트의 룰 디텍터로 자동 라우팅 (2025)

python -m btcusdt_quant live --regime-aware --model-artifact <동일 디렉터리> ...
# → 동일 룰 디텍터로 자동 라우팅
```

## 학습형 classifier 처리

`train-regime-classifier` / `regime_classifier.py` / `.cbm` 경로는 **그대로 유지**
(삭제 시 테스트·CLI 광범위 파손). 단 파이프라인 기본 경로에서 빠지고,
`--multi-feature-regime`이 `--regime-classifier-dir`보다 우선. 나중에 하이브리드
(p_up/p_range/p_down를 confidence로)로 되살리고 싶으면 F18 주입 인프라가 이미
있어 재연결이 쉬움.

## 튜닝

모든 가중치·임계값·min_hold는 `MultiFeatureRegimeConfig` 필드로 노출. 기본값은
설계 노트 예시값. 실데이터에서 regime 분포/전환 빈도를 보고 조정 권장
(특히 trend_enter/exit, range_enter, min_hold_bars).

## 검증

```
python3 -m compileall -q btcusdt_quant                 # 통과
python3 -m unittest tests.test_regime_rules            # 8 tests OK (표준 라이브러리만)
python3 -m unittest tests.test_core                    # errors=7(pyarrow), failures=0 — 베이스라인 동일
python3 -m unittest tests.test_v718                    # failures=2/errors=14/skipped=6 — 베이스라인 동일 (회귀 0)
backtest 라우팅 스모크(합성 캔들) 통과, live dry-run 통과
```

디텍터 단위검증: 결정성 / 3-class / 인과성(prefix==detect_one) / min-hold churn 감소
/ breakout 즉시전환 / 저장복원 일치 / 결측피처 안전 / config 검증 — 전부 통과.

catboost·pyarrow·lightgbm·torch 미설치로 실제 entry 모델 학습→백테스트→live
end-to-end는 이 환경에서 미실행. 해당 의존성이 있는 환경에서 위 순서로 한 번
돌려 최종 확인 권장.

## 파이프라인 스크립트

`run_full_pipeline.sh` / `run_full_pipeline.ps1`에 `REGIME_MODE`(기본 `rule`)
토글을 추가. **기본이 룰베이스**라 그냥 실행하면 됩니다:

```
./run_full_pipeline.sh                 # rule 모드 (기본): Phase 2.5 classifier 생략,
                                       #   Phase 3 --multi-feature-regime로 학습,
                                       #   Phase 4 아티팩트에서 룰 디텍터 자동 로드
REGIME_MODE=classifier ./run_full_pipeline.sh   # 옛 학습형 classifier 경로로 복귀
```

rule 모드에서는 `train-regime-classifier`(Phase 2.5)가 생략되고 `regimes.json`도
bucket 배정에 불필요합니다(룰 디텍터가 F17에서 regime을 직접 도출). entry 모델은
Phase 3에서 룰 bucket으로 (재)학습되고, backtest/live는 아티팩트에 저장된 동일
디텍터로 라우팅합니다.

## 변경/추가 파일

```
btcusdt_quant/regime_rules.py     (신규: 룰 디텍터)
btcusdt_quant/training.py         (bucket 배정 분기 + 저장)
btcusdt_quant/backtest.py         (run_backtest/compare_strategies 라우팅)
btcusdt_quant/live.py             (bundle 필드 + 로더 + _compute_signal 라우팅)
btcusdt_quant/cli.py              (train 플래그, backtest 로드/주입)
run_full_pipeline.sh / .ps1       (REGIME_MODE 토글, 기본 rule)
tests/test_regime_rules.py        (신규: 8 tests)
```
