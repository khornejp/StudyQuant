# 세션 핸드오프 — 2026-07-27 (평균회귀 배리어/호라이즌 + maker 체결 실험)

브랜치: `fix/barrier-parity-and-metric-guards` (main 아님, push 안 함)
이 세션 커밋: `d604b8f` (maker 체결 모델), `ed10457` (관통 곡선 문서)
직전 세션 커밋: `6de790f` (`--train-target` 노브)

---

## 0. 한 줄 요약

> 🔴 **이 문서의 maker 수치·판정은 2026-07-28 코드 리뷰로 무효화됨. 커밋 `4b470e8`,
> 정정 내용은 `EDGE_EXPERIMENT_RESULTS_2026-07-25.md` §8.**
> 실행 모델 버그 2건(maker fee 미부과, 체결봉 배리어 미평가)을 고친 뒤:
> touch 체결 **+10.49% → +4.10%/년**, 관통 2 bps **+2.27% → −3.24%/년**,
> 손익분기 큐 깊이 **~2.9 bps → ~1.1 bps**. 판정 **PROMISING BUT UNPROVEN → REJECT 쪽으로 격하**.
> 아래 §2 표와 §7의 다음 실험 목록은 무너진 전제 위에 있다.

원래 "엣지 없다"의 진짜 답: **신호 부재 아님. 배포 배리어(60m)가 신호 스케일과 안 맞았을 뿐.**
60m(신호 소멸) → 15m(신호 있으나 배리어 작아 비용에 압도) → 30m(신호 유지). 이 호라이즌/배리어 발견은
버그의 영향을 받지 않으므로 **유효하다.** 무효인 것은 maker 실행 경제성 결론뿐이다.

---

## 1. 이 세션에서 한 일 (순서대로)

1. **실험 #1 — short-side 15m** (`--target short_success`): 예측력 최강(F1 0.22)이나 2025 OOS에서 거래 8건뿐.
   임계값 0.24→0.08(3배 완화)에도 8건 불변 → 급락 셋업이 2025 저변동장에 희소. **INCONCLUSIVE (표본 부족).**
2. **실험 #2 — 30m sweet-spot** (`--horizon 30 --tp-pct 0.006 --sl-pct 0.003`, long/profitability): F1 0.135(15m급),
   taker net −0.57 bps, maker(100%-fill 가정) +10.5%/년.
3. **maker 체결 모델 코드화** (`backtest.py`에 pending-limit 상태머신) → 현실적 체결로 재검증:
   - touch 체결: 체결률 99.2%, net +10.49%/년 (→ +11%는 체결 허상 아님).
   - 관통 2 bps(큐 우선순위): 체결률 80%, net +2.27%/년.
4. **관통 민감도 곡선** (0/1/2/3/4 bps): 손익분기 큐 깊이 ≈ 2.9 bps.

전체 상세: `EDGE_EXPERIMENT_RESULTS_2026-07-25.md` §6(short), §7.1~7.8(30m + maker).

---

## 2. 핵심 결과 표

### 배리어/호라이즌 (2025 OOS, 고정사이즈, notional bps/거래)
| 설정 | F1 | 승률 | gross/t | net/t | 판정 |
|---|---:|---:|---:|---:|---|
| 60m long / 1%·0.5% | 0.018 | — | 음수 | — | REJECT (신호 소멸) |
| 15m long / 0.4%·0.2% | 0.139 | 37.9% | +1.47 | −6.5 | REJECT (배리어 작음) |
| 15m short / 0.4%·0.2% | 0.220 | — | — | ~0 | INCONCLUSIVE (8거래) |
| **30m long / 0.6%·0.3%** | 0.135 | 49.9% | +8.33 | −0.57(taker) | 경계 |

### 30m maker 체결 관통 민감도 곡선 🔴 무효 (fee 미부과 상태에서 산출)
| 관통 | 체결률 | 승률 | gross/t | net/t | net_sharpe | 연 net |
|---|---:|---:|---:|---:|---:|---:|
| 0 bps (touch) | 99.2% | 54.1% | 8.20 | +3.50 | 0.105 | **+10.49%** |
| 1 bps | 86.3% | 52.2% | 6.18 | +1.73 | 0.053 | +4.93% |
| 2 bps | 79.9% | 51.1% | 5.15 | +0.82 | 0.026 | +2.27% |
| **3 bps** | 74.4% | 49.8% | 4.05 | −0.15 | −0.005 | **−0.41%** |
| 4 bps | 68.6% | 48.6% | 3.53 | −0.62 | −0.020 | −1.60% |

위 표는 maker 진입 fee를 부과하지 않은 코드로 산출됐다. 거래당 2 bps씩 과대평가. 정정판:

| 관통 | 체결률 | 승률 | gross/t | net/t | net_sharpe | 연 net |
|---|---:|---:|---:|---:|---:|---:|
| 0 bps (touch) | 99.31% | 51.85% | 7.336 | **+1.336** | +0.042 | **+4.10%** |
| 2 bps | 79.55% | 49.15% | 4.816 | **−1.184** | −0.038 | **−3.24%** |

**손익분기 관통점 ≈ 2.9 bps → ≈ 1.1 bps.** 관통↑ → 체결률↓(거래↓) + 승률↓(역선택) 이중 침식은 그대로.

---

## 3. 코드 변경 (커밋 `d604b8f`, 테스트 클린)

`btcusdt_quant/backtest.py`:
- `BacktestTrade.entry_maker: bool` — maker 체결분 표시.
- `_close_trade`: `entry_maker`면 진입측 fee/slippage 면제(청산은 taker 유지). 기본(False)은 양측 부과 = 무회귀.
- `run_backtest(maker_fill_window: int = 0, maker_fill_penetration: float = 0.0)`:
  - `maker_fill_window > 0`: 신호봉 종가에 지정가 등록 → 후속 봉이 되돌아와 터치(역선택)하면 체결, 창 내 미터치 취소(미체결).
  - `maker_fill_penetration`: 큐 우선순위 프록시 — 터치가 아니라 buffer(fraction)만큼 관통해야 체결.
  - `_open_trade` 중첩 헬퍼(taker/maker 공용) — 기존 Kelly 가드 로직 이관.
  - `maker_fill_diagnostics` (placed/filled/unfilled/fill_rate) + run_config 기록.
- **기본 `maker_fill_window=0` = 기존 즉시 taker 체결 그대로**(무회귀).

`btcusdt_quant/cli.py`: `--maker-fill-window`, `--maker-fill-penetration-bps` 인자 + run_backtest 배선.

`tests/test_review_items.py`: `MakerFillTests` 4개(taker 무회귀 / maker 체결+비용면제 / 미체결 runaway / 관통이 단순터치 차단)
+ `test_kelly_guard_fails_closed_on_empty_genuine_sides` 소스검사 갱신(가드가 `_open_trade`로 이동). **127 passed.**

---

## 4. 재현 명령 (정확한 재실행용)

공통: `python -m btcusdt_quant` (`__main__.py`) 사용. `.cli`는 무출력 종료(가드 없음).
venv: `./venv_btcusdt/Scripts/python.exe`. 입력: `artifacts/btcusdt_2020_2025.parquet`, 메트릭: `artifacts/metrics`.

### 30m 모델 학습 (~3.5h, CatBoost CV 4-fold)
```
python -m btcusdt_quant train \
  --input artifacts/btcusdt_2020_2025.parquet --metrics-dir artifacts/metrics \
  --horizon 30 --tp-pct 0.006 --sl-pct 0.003 --target profitability \
  --output artifacts/exp_mr30_unified
```

### 30m 백테스트 — maker 관통 N bps (~25min)
```
python -m btcusdt_quant backtest \
  --input artifacts/btcusdt_2020_2025.parquet --model-artifact artifacts/exp_mr30_unified \
  --metrics-dir artifacts/metrics --backtest-start 2025-01-01 --backtest-end 2025-12-31 \
  --horizon 30 --fixed-tp-sl --tp-floor 0.006 --sl-floor 0.003 \
  --exec-tp-pct 0.006 --exec-sl-pct 0.003 \
  --long-threshold 0.37 --short-threshold 0.0 --disable-range-gate \
  --maker-fill-window 5 --maker-fill-penetration-bps <N> \
  --output artifacts/exp_mr30_pen<N>
```

### short 모델은 range/short 번들 필요
`artifacts/exp_mr15_short_bundle/`(regime_range/short_model.json + regime_run_summary.json) +
`artifacts/all_range.json`(전 봉 range 라우팅) 사용. `load_regime_aware_models`가 short로 인식.

---

## 5. 아티팩트 (모두 git-ignored, `artifacts/`)

| 경로 | 내용 |
|---|---|
| `exp_mr15_unified` | 15m long 모델 |
| `exp_mr15_short` / `exp_mr15_short_bundle` | 15m short 모델 + range/short 번들 |
| `exp_mr30_unified` | 30m long 모델 (핵심) |
| `exp_mr30_backtest` | 30m taker 백테스트 |
| `exp_mr30_backtest_maker` | 30m maker (100%-fill 가정, fee 0) |
| `exp_mr30_backtest_makerfill` | 30m maker touch 체결 (window 5) |
| `exp_mr30_backtest_makerpen` | 30m maker 관통 2bps |
| `exp_mr30_pen1 / pen3 / pen4` | 관통 1/3/4 bps |
| `all_range.json` | short 백테스트용 전-봉 range 라우팅 |

---

## 6. 함정/주의 (다음 세션 필독)

- **CLI 진입점**: `python -m btcusdt_quant` (O). `python -m btcusdt_quant.cli` (X, 무출력 종료 — `__main__` 가드 없음).
- **standalone 스크립트 + 병렬 피처빌드**: Windows spawn에서 자식 부트스트랩 실패. 정식 CLI(`-m btcusdt_quant`)만 안전.
- **데이터 윈도잉 금지**: 2024-10부터 자르면 주봉 MA 워밍업(~350일) 오염 → train/serve skew. 항상 전체 파케 사용.
- **30m 학습 ~3.5h**(15m ~90min): 30m 균형 클래스에서 CatBoost early-stop 안 걸림. 정상, hang 아님.
- **short 모델 F16 피처 포함**(taker/oi) → 백테스트에 반드시 `--metrics-dir artifacts/metrics`.
- **전체 테스트 스위트 ~65분**(499 tests). 행 아님 — Optuna 3건이 632/438/421초, regime 학습 6건이 각 152초.
- **GPU는 하나다**(`models.py:169` `task_type: "GPU"`). 스위트·백테스트를 동시에 띄우면 CPU와 GPU가
  같이 경합해 몇 배로 늘어진다. **한 번에 하나씩 돌릴 것.**
- **백그라운드 명령에 `| tail` 붙이지 말 것**: 완료 전까지 출력이 0이라 진행 중인지 행인지 구분 불가.

---

## 7. 다음 실험 (§7.8, 정보가치 순) 🔴 전제 붕괴 — 아래 0번 먼저

0. **1 bps 관통 백테스트** — 손익분기점 실측(현재 0/2 bps 두 점 보간으로 ~1.1 bps). 곡선이 볼록하면
   1.1보다 낮고, 그러면 어떤 현실적 큐 위치에서도 죽는다는 뜻이라 아래 1~4가 전부 불필요해진다.
   가장 싸고 가장 크게 갈리는 실험.

아래 4건은 "손익분기 2.9 bps, net 양수"라는 무효화된 전제 위에 세워졌다. 0번 결과를 보고 재검토한다.

1. **30m threshold 민감도(0.34~0.42) + 1.5x/2x 비용 stress** — net 부호 안정성.
   (이제 `edge-validate`가 `--disable-range-gate` / `--maker-fill-window` / `--maker-fill-penetration-bps`를
   받으므로 실험 대상과 같은 실행 모델로 돌릴 수 있다. 커밋 `4b470e8` 이전에는 불가능했다.)
2. **seed/기간/regime/volatility bucket 안정성 분해** — 2025 저변동 한 해 결과의 일반화 가능성.
3. (위 통과 시) **final untouched test 2025 H2** — 선택·튜닝에 절대 미사용.
4. 45m 확인(30m이 정점인지) — 우선순위 낮음.

미착수(직전 세션부터 보류, 사용자 미승인): §4/§21 select_threshold 승인-거부 게이트, §16.1 regime-path uniqueness weighting.
