# V8 분석(Optuna 최종 학습) 잔여 이슈 수정 보고 (2026-07-08)

기준 문서: `rulebased_regime_v8_optuna_training_summary.md`
이전 보고: `FIX_REPORT_V7_REMEDIATION.md`

v8 분석의 수정 요청 1~6을 전부 반영했다(권장 구조 1 채택). 추가로 분석
§3의 timeout 항목과 §5의 feature cache 추정을 각각 재확인·확정했다.

---

## 핵심: Optuna 최종 재학습에 best_iteration 반영 — 수정 완료

### 확인된 실체 (`training.py` regime-aware 경로)
- Trial: `adapter.fit(train_x, train_y, eval_set=(val_x, val_y),
  use_best_model=True)` + `od_type=Iter`/`od_wait` — 조기 종료 활성.
- 그러나 `get_best_iteration()`은 어디에서도 호출되지 않았고,
  `study.best_params`의 suggested `iterations`(300~2000 탐색)가 그대로
  merge되어 **최종 모델은 eval_set 없이(od 파라미터는 silent no-op) 전체
  regime 데이터로 suggested budget 끝까지 학습** — 검증 loss가 악화되기
  시작한 지점을 지나서도 계속 학습하는, 분석 지적 그대로의 구조.
- 참고: legacy 단일 모델 경로의 `OptunaStudyRunner`(features.py)는
  threshold/signal_scale만 튜닝하고 CatBoost fit 자체를 조기종료로 돌리지
  않으므로 이 문제와 무관 — 수정 범위는 regime-aware 경로만.

### 수정 (요청 1~5)
1. `_objective` 내부에서 trial fit 직후 `adapter.model.get_best_iteration()`
   추출(getter 부재/예외는 None) → `trial_history` 각 entry에
   `best_iteration` 저장.
2. study 종료 후 `study.best_trial.number`로 우승 trial의 best_iteration을
   조회.
3. `merged["iterations"] = min(suggested, best_iteration + 1)` —
   best_iteration은 0-base 트리 인덱스이므로 +1이 트리 개수. `min()`은
   비정상 getter가 budget 초과값을 반환해도 iterations를 **올리지는 못하게**
   하는 방어.
4. `best_iteration`이 None이거나 `<= 0`이면 suggested budget 유지
   (0 = 첫 트리가 best라는 퇴화 신호는 cap 근거로 신뢰하지 않음).
5. report(→ run_summary의 `optuna.per_target.{long,short}`)에
   `best_trial_number` / `best_iteration` / `suggested_iterations` /
   `final_iterations` 기록. 파이프라인 로그에도 cap 발생 시
   `final refit capped at iterations=N (early stopping best_iteration=M;
   suggested budget was K)` 한 줄 출력.

최종 fit 코드 자체(`long_model.fit(f_matrix, ...)`)는 변경 불필요 — merged
params가 이미 cap된 상태로 전달된다. 분석의 권장 구조 1 그대로: 전체 regime
데이터를 사용하면서(validation 구간 버리지 않음) 학습 길이만 검증 기준으로
제한. 2025 백테스트 구간은 어떤 경로로도 eval_set에 쓰이지 않음(기존과 동일
— optuna 튜닝은 test-period 이전 rows로만 수행되는 기존 slice 유지).

### 검증 (요청 6): `tests/test_optuna_best_iteration.py` 신설 — 5/5 OK
catboost/optuna 미설치 환경에서도 돌도록 fake optuna 모듈 + fake
CatBoostAdapter를 주입해 `_tune_catboost_with_optuna`를 직접 검증:
1. **cap 동작**: `merged["iterations"] == best_iteration + 1`이고 suggested
   대비 실제로 감소했는지(무의미한 통과 방지), report 4필드 정합.
2. **None getter** → suggested 유지.
3. **best_iteration == 0** → suggested 유지 (요청 4).
4. **budget 초과 getter** → iterations 상승 불가(min cap).
5. **trial_history**에 trial별 best_iteration 기록.

---

## 분석 §3 후속: verify_metrics_parity 4번 timeout

분석 환경에서 60k 병렬 비교가 timeout됐다는 보고 — 본 환경에서는 이전
세션에서 4/4 통과를 확인했고(60k봉/6 chunks, 수 분 내), 스크립트 자체
결함은 아님. 항목 1~3(핵심 parity)은 분석 환경에서도 통과했으므로 결론
불변. 참고로 4번은 1~3과 독립 실행 가능하다(스크립트 구조상 앞 3개 통과
후 진행).

## 분석 §5 후속: feature cache 위치 — 추정을 사실로 확정

`save_dataset_cache`/`load_dataset_cache`/`dataset_cache_dir`의 호출부를
전수 확인한 결과 **tests/test_core.py에서만 사용**되며 CLI·train·backtest
경로 어디에서도 호출되지 않는다. 즉:
- **파이프라인 기본 실행은 feature cache를 디스크에 만들지 않는다** —
  feature는 매 실행 메모리에서 재계산(§5.1 추정 확정).
- 재실행 전 삭제 대상은 `artifacts/regime_stacking_model/`(모델)과
  `artifacts/backtest_results/`(결과)뿐. `*.parquet_cache` 탐색은 과거에
  cache API를 수동 사용한 적 있는 환경에서만 의미 있음.
- 보존: `artifacts/archive_full/`, `artifacts/metrics/`,
  `artifacts/btcusdt_2020_2025.parquet` (분석 §5.4와 동일).

---

## 테스트 결과 (회귀 0)

| 검증 | 결과 |
|---|---|
| tests/test_optuna_best_iteration (신규) | 5/5 OK |
| tests.test_regime_rules | 15/15 OK |
| tests.test_core | 131, errors=7 (전부 pyarrow 미설치; baseline 동일) |
| tests.test_v718 | **실패 집합 baseline과 diff 완전 일치** |
| py_compile | OK |

## 재실행 순서 (분석 §9의 6~10 그대로)

```powershell
Remove-Item -Recurse -Force artifacts\regime_stacking_model
Remove-Item -Recurse -Force artifacts\backtest_results   # 또는 별도 보관
.\run_full_pipeline.ps1
```

결과에서 새로 볼 것: run_summary의 `optuna.per_target.*.best_iteration` vs
`suggested_iterations`(얼마나 일찍 멈췄는지 = 과적합이 얼마나 방지됐는지의
간접 지표), 그리고 cap 이후 holdout metrics/threshold가 이전 대비 어떻게
움직였는지. best_iteration이 suggested에 계속 붙어 나온다면(early stop
미발동) od_wait/learning_rate 탐색 범위 재검토 신호다.
