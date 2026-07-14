# Stale 모델 혼입 · 게이트 사각지대 · 파이프라인 중단 수정

> 작성일: 2026-07-11
> 대상 문서: `Project7_source_review_summary.md`
> 관련 문서: `SILENT_ONESIDED_FIX.md`, `SOURCE_REVIEW_FIXES.md`, `CODE_REVIEW_FIXES.md`, `PIPELINE_INTEGRATION.md`
> 변경 파일: `btcusdt_quant/cli.py`, `btcusdt_quant/live.py`, `btcusdt_quant/training.py`, `btcusdt_quant/backtest.py`, `compare_backtests.py`, `run_full_pipeline.{ps1,sh}`, `tests/test_review_items.py`

---

## 1. 요약

`Project7_source_review_summary.md`의 지적 4건은 **전부 실재**했다(그중 CRITICAL 1, HIGH 2). 수정하는 과정에서 코드리뷰가 **파이프라인 레벨의 더 큰 문제**(파일럿 실패가 주 백테스트를 중단)와 **데이터 손실 위험**(정리 후 게이트 실패 시 이전 모델 소실)을 추가로 잡아냈고, staging swap으로 근본 해결했다.

| 구분 | 건수 |
|---|---|
| 문서 지적 재검증 | 4건 전부 실재 |
| 문서 지적 수정 | 4건 (D1~D4) |
| 코드리뷰가 새 코드에서 잡은 결함 | 5건 (CRITICAL 1: 데이터 손실 / HIGH 1: 파이프라인 중단) |
| 회귀 검증 | `test_review_items.py` **90 passed** |

---

## 2. 문서 지적 재검증 및 수정

### D1 — [CRITICAL] 이전 실행의 stale 모델 혼입

**문제.** 로더 `load_regime_aware_models`가 `long_path.exists()`/`short_path.exists()`로 **파일 존재만** 보고 로드했다. 이전 실행에서 남은 `regime_up/short_model.json`이 있고 새 정책이 up=long-only이면, 로더가 그 stale short를 로드해 up이 정책상 금지된 short를 거래한다. `missing_side_models`는 **없는** 사이드만 검사하므로 **초과** 사이드를 못 잡는다.

**수정 (심층 방어 2겹).**
1. **학습이 정리 + staging swap** — train-multi-horizon과 train(single-horizon) 모두, 학습이 자기 정책의 `regime_*`를 (symlink 제외) 정리하고 새로 쓴다.
2. **로더가 선언 대조** — `regime_run_summary.json`의 `regime_results[regime]["sides"]`에 선언된 사이드만 로드. 파일이 있어도 미선언이면 무시 + 경고. 구버전 아티팩트(선언 없음)는 파일 존재로 폴백.

```
WARNING: ignoring stale short_model.json in regime_up: the summary does not
declare a 'short' side for this regime (left by an earlier run?).
```

### D2 — [HIGH] min_regime_rows 미달 레짐이 게이트 우회

**문제.** 레짐 데이터가 `min_regime_rows` 미달이면 `skipped_regimes`에만 기록하고 `continue` — `missing_sides`에 안 들어가 `--allow-partial-sides` 게이트를 우회, exit 0. 필수 레짐 전체가 빠져도 학습 성공으로 끝났다.

**수정.** min-rows 스킵 레짐의 모든 정책 사이드를 `missing_sides`에 기록 → 게이트가 exit 1. 실증: `min=5000`으로 `up` 스킵 시 `up/long`이 걸려 rc=1, `--allow-partial-sides`로만 rc=0.

### D3 — [HIGH] auto/rule 레짐 모델 누락 시 다른 레짐 모델로 거래

**문서 권장:** auto 모드에서 모델 누락 시 HOLD/실패.
**우리 판단:** 이 문제는 **D2로 근본 커버된다.** auto 모드에서 `default_fallback > 0`은 "감지된 레짐에 모델 없음"인데, 학습 게이트(D2)가 필수 레짐 누락을 exit 1로 막으면 애초에 그런 아티팩트가 생기지 않는다. 백테스트 쪽은 이미(직전 라운드) auto 라우팅에서 `fallback > 0`이면 즉시 경고하고, 이번에 `missing_side_models`를 `backtest_summary.json`과 `compare_backtests`에 기록하도록 보강했다. 무조건 HOLD 강제는 정당한 커버리지 갭(user-regime-file)과 구분 불가라 채택하지 않았다.

### D4 — [MEDIUM] _ctx_genuine_sides가 실제로 fail-open

**문제.** `if _ctx_genuine_sides and entered_side not in _ctx_genuine_sides:` — 빈 집합이면 short-circuit으로 검사 자체를 건너뛴다. 주석은 fail-closed라 했지만 실제로는 fail-open.

**수정.** `and _ctx_genuine_sides` 제거 → `if entered_side not in _ctx_genuine_sides:`. 이제 빈 집합도 거부(fail-closed). 현재 모든 경로가 신호 전에 최소 `"long"`을 선언하므로 도달 불가하나, 새 라우팅 경로가 선언을 빼먹으면 자동 차단된다.

---

## 3. 코드리뷰가 새 코드에서 잡은 결함 5건

### C1 — [CRITICAL] 정리 후 게이트 실패 시 이전 아티팩트 소실

처음 수정(학습 시작 시 `output/regime_*` rmtree)은 **재학습이 게이트에 걸리면 이전 good 아티팩트를 지운 뒤 partial만 남기고 exit 1** → "게이트에 걸리는 재실행이 아무것도 안 하느니만 못한" 상황을 만들었다.

**해결 — staging swap (문서 §1이 권장한 atomic replace).**
- 학습을 `output/.mh_staging`에 수행.
- **모든** 게이트 통과 후에만 정책 `regime_*` + summary를 output으로 승격(swap). 정책 밖 디렉터리는 건드리지 않는다.
- 어떤 게이트 실패든 output은 **무손상**, 부분 결과는 `.mh_staging`에 진단용으로 남는다.
- 추가로, row-count 게이트를 rmtree/staging **전**으로 당겨 "데이터 부족" 실패는 staging조차 만들지 않는다.

실증:
```
1차(성공): rc=0, 아티팩트 승격됨
2차(short fit 실패 강제): rc=1, 이전 MARKER.txt 생존, 부분 결과는 .mh_staging에
```

### C2 — [HIGH] 파일럿 실패가 주 백테스트(Phase 4)를 중단

파이프라인이 Phase 3.5(multi-horizon **파일럿/챌린저**)를 Phase 4(주 산출물) **전에** fatal gating(`Assert-PhaseSucceeded` / `set -e`)으로 실행. Phase 3.5의 새 fail-closed exit(too_small / missing_sides / partial-refit) 하나가 발동하면 **주 regime-model 백테스트가 실행되지 못하고 파이프라인 전체가 중단**된다. 부차적 파일럿의 데이터 quirk가 주 결과물을 죽인다.

**수정.** ps1/sh 모두 Phase 3.5를 **non-fatal**로: 실패 시 경고 + `MultiHorizonPilot=false`로 Phase 4.5만 스킵, Phase 4는 계속. `--allow-partial-*`를 넘겨 부분 파일럿을 억지로 비교하는 대신, 파일럿을 조용히 건너뛴다.

### C3 — [MEDIUM] rmtree가 symlink에서 크래시 / 공유 디렉터리의 무관 레짐 삭제

`if _stale.is_dir()`은 symlink-to-dir에 True를 반환하는데 `rmtree(symlink)`는 OSError. 또 `glob("regime_*")`는 현재 정책 밖 레짐도 지웠다.

**수정.** 정책 레짐만 대상(`for regime in USER_REGIME_NAMES` / `MH_REGIME_SIDES`) + `and not is_symlink()`. staging swap의 승격 단계도 동일 규칙.

### C4 — [MEDIUM] missing_side_models가 비교 도구에 미노출

`missing_side_models`가 `backtest_summary.json`과 stderr에만 있고 `compare_backtests`가 안 읽었다. 사이드 모델이 **통째로 없으면** kelly 스킵 카운터가 0이라, 이 필드가 유일한 단방향 증거인데 비교 시점에 안 보였다.

**수정.** `compare_backtests`가 `missing_side_models`를 (빈 트레이드 경로 포함) 출력하고, `longs_skipped_no_long_model`도 함께 경고.

### C5 — [정정] 문서가 우려한 Phase 3 stale 비대칭은 실재하지 않음

Angle C 확인: training.py(Phase 3, single-horizon)도 이번에 정리를 추가해 Phase 3.5와 대칭. 문서 §1의 "Phase 3에 정리 없음" 우려는 (이번 수정으로) 해소됨.

---

## 4. 검증

```
tests/test_review_items.py : 90 passed
  신규: 로더 stale-side 무시, missing_side_models 비교 노출, fail-closed 소스 가드
staging swap 실증          : 성공 승격 / 실패 시 이전 아티팩트 보존 확인
min-rows 게이트 실증        : rc=1, --allow-partial-sides로만 rc=0
stale 정리 실증            : before=True → after=False, 로더 경고 발동
ps1 ParseFile / bash -n    : 통과
전체 스위트                : 254 passed, 1 deselected (제외 1건은 기존 parquet float32)
```

---

## 5. 남은 항목 / 재학습 전 체크

문서 §9의 재학습 후 체크리스트가 이제 **코드로 강제**된다:
- `missing_sides`가 있으면 학습이 exit 1 (`--allow-partial-sides` 없이).
- 백테스트가 `missing_side_models`를 아티팩트·경고·비교 도구에 노출.
- stale 모델은 정리 + 선언 대조로 이중 차단.
- staging swap으로 실패해도 이전 good 모델 보존.

남은 것:
- **live Kelly 배선** (`entry_quantity = 0.001`). `has_side_probability`가 준비돼 선행 문제는 해소.
- Phase 4.5는 여전히 challenger (horizon 블렌드 / Optuna / 캘리브레이션 의미론이 Phase 4와 다름).
- `DrawdownProtocol.reduce_factor` 미배선(K7).
- 파이프라인은 이제 파일럿 실패에 견고하다 — 단, `--min-regime-rows` 기본값이 MH(2000) vs train(80)로 달라, 짧은 학습 창에서는 파일럿만 스킵될 수 있음(주 결과에는 무영향).
