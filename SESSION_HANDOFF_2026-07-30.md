# 세션 핸드오프 — 2026-07-30 (Bitget 비용 기준 정정 + exit 체결 mix 측정)

브랜치: `fix/barrier-parity-and-metric-guards` (main 아님)
이 세션 커밋: `776fe7a` `2fe9950` `1347f61` `3e08136` `aa8d119` `8fc08f5` `1699b88`
직전 핸드오프: `SESSION_HANDOFF_2026-07-27.md` (🔴 §7의 다음 실험 목록은 무효 — 아래 §6 참조)

---

## 0. 한 줄 요약

> 30m 평균회귀 판정은 **REJECT 유지**. 단, §8이 본 이유(관통 bps)가 아니라 **exit 체결 mix** 때문이다.
> 계정은 Binance가 아니라 **Bitget VIP0**(maker 0.02% / taker 0.06%)이고, 코드는 taker 체결에
> maker 요율을 물리고 있었다(왕복 8 bps 과소). exit 다리는 아예 taker로 하드코딩돼 있었다.
> 둘 다 고치고 청산 방식별로 쪼개 측정한 결과: **양수인 유일한 시나리오가 "SL도 지정가로 대기 체결된다"를
> 가정한다 — stop은 정의상 그럴 수 없다.** 방어 가능한 최선은 연 +4.78%이고 1.5x 비용 stress에서 죽는다.

상세 전부: `EDGE_EXPERIMENT_RESULTS_2026-07-25.md` **§9**.

---

## 1. 이 세션에서 한 일

1. **재부팅 복구** — 직전 세션이 테스트 중 재부팅으로 끊겼다. 코드·아티팩트 손실 없음, 미커밋
   작업(maker_exit + skill 문서)을 3개 커밋으로 정리.
2. **계정 등급 확인** (§8.4의 마지막 미해결 항목): **Bitget VIP0**. 요율 상수를 maker/taker로 분리,
   `live.py` EV 게이트와 파이프라인 드라이버까지 같은 치환 오류 정리.
3. **cost basis 분열 발견·수정** — 상수를 쪼개면서 backtest 왕복비용이 0.0016이 됐는데 training이
   0.0008에 남아 threshold가 실행의 절반 비용으로 선택되고 있었다. 테스트로 고정.
4. **`edge-validate`에 maker 경로 배선** + cost_stress가 maker 요율도 배수하도록 수정
   (양다리 maker 전략이 2x를 무사통과하던 결함).
5. **`maker_exit` bool → `maker_exit_outcomes`** (TP/SL/TIMEOUT/OPEN_AT_END). 청산 방식별 비용.
6. **A/B/C 실측 3런** → 손익분기 f=0.556 확정, 선형 비용 모델 `cost = 4 + 6f` 검증.
7. **`--sl-fill next_open` 구현** (봇 사이드 stop). 미실행.
8. **45m 학습 착수** (22:09, `artifacts/exp_mr45_unified`).

---

## 2. 핵심 결과 표

### 비용 기준 (Bitget VIP0, 2025 OOS, 30m long, 고정사이즈 0.1)

| 대기하는 청산 | f (taker 비율) | 연 net | net_sharpe | maxDD | 1.5x 생존 |
|---|---:|---:|---:|---:|:--:|
| 전부 (물리적으로 불가) | 0.000 | +10.59% | 0.106 | 0.7% | ✔ (2x ✘) |
| **TP+TIMEOUT (방어 최선)** | 0.298 | **+4.78%** | 0.046 | 1.2% | **✘ −3.99%** |
| 손익분기 | 0.556 | 0 | — | — | — |
| TP+SL | 0.568 | −0.24% | −0.002 | 2.3% | ✘ |
| TP만 | 0.866 | −5.48% | −0.057 | 6.2% | ✘ |

gross는 네 런 모두 **+24.80%**(거래당 7.336 bps)로 동일 — 같은 시그널, 비용만 다르다.
outcome 분포: TP 13.4% / SL 29.8% / TIMEOUT 56.8%.

---

## 3. 코드 변경

| 커밋 | 내용 |
|---|---|
| `776fe7a` | 비용을 **다리별**로 계산. maker/taker 요율 분리(0.0002 / 0.0006). `maker_exit` 도입 |
| `2fe9950` | `live.py` EV 게이트가 maker 요율을 물던 것 수정 (0.0002 → 0.0006) |
| `1347f61` | `btcusdt-quant-code` 스킬 6원칙 재구성 + reference 2건 신설 |
| `3e08136` | 계정을 Bitget으로 확정(taker 0.0006). training/backtest cost basis 분열 수정 + 고정 테스트 |
| `aa8d119` | `edge-validate`에 maker exit 배선, cost_stress가 maker 요율도 배수 |
| `8fc08f5` | `maker_exit` bool → `maker_exit_outcomes`(청산 방식별) |
| `1699b88` | `--sl-fill barrier\|next_open` (거래소 stop vs 봇 사이드 stop) |

전체 스위트: **501 passed, 1 skipped, 28 subtests** (49분, `3e08136` 시점).
이후 커밋들은 `test_review_items` + `test_edge_validation` 156건 통과 — **전체 스위트 재실행 필요.**

---

## 4. 재현 명령

공통: `./venv_btcusdt/Scripts/python.exe -m btcusdt_quant` (`.cli`는 무출력 종료).
입력 `artifacts/btcusdt_2020_2025.parquet`, 메트릭 `artifacts/metrics`.

### exit mix 측정 (각 ~40분)
```
python -m btcusdt_quant edge-validate \
  --input artifacts/btcusdt_2020_2025.parquet --model-artifact artifacts/exp_mr30_unified \
  --metrics-dir artifacts/metrics --backtest-start 2025-01-01 --backtest-end 2025-12-31 \
  --horizon 30 --exec-tp-pct 0.006 --exec-sl-pct 0.003 \
  --long-threshold 0.37 --short-threshold 0.0 --disable-range-gate \
  --maker-fill-window 5 --maker-exit-outcomes tp,timeout \
  --fee-rate-per-side 0.0006 --maker-fee-rate-per-side 0.0002 --slippage-rate-per-side 0.0002 \
  --cost-multipliers 1.0,1.5,2.0 --output artifacts/ev_mr30_exit_tp_timeout
```
`--maker-exit-outcomes`를 `tp` / `tp,sl` / `tp,timeout`으로 바꾸면 A/B/C.
`--maker-exit`은 전부 대기(상한선) shorthand. 둘 다 주면 거부된다.

### 45m 학습 (~4h, 진행 중)
```
python -m btcusdt_quant train \
  --input artifacts/btcusdt_2020_2025.parquet --metrics-dir artifacts/metrics \
  --horizon 45 --tp-pct 0.008 --sl-pct 0.004 --target profitability \
  --output artifacts/exp_mr45_unified
```

---

## 5. 함정/주의

- **비용 기준은 계정(Bitget)을 따른다.** `exchange.py`가 Binance 어댑터인 것과 무관하다.
- **`--round-trip-cost` 기본값은 이제 `backtest.DEFAULT_ROUND_TRIP_COST_PCT`에서 읽는다.** 리터럴로
  되돌리지 말 것 — 그렇게 해서 0.0008 대 0.0016으로 갈라졌었다.
- **파이프라인 기본값으로 낸 과거 수치는 왕복 8 bps 과소 계상이다.** 30m maker 실험은 요율을 명시로
  넘겼으므로 무관.
- **`--sl-fill`은 live가 거는 주문과 일치해야 한다.** 거래소 상주 stop을 `next_open`으로,
  봇 사이드 stop을 `barrier`로 백테스트할 수 없다.
- **소스 편집 중에 테스트 스위트를 띄우지 말 것.** 49분짜리라 중간에 파일이 바뀌면 결과 신뢰도가
  통째로 날아간다(이 세션에서 한 번 겪음).
- **GPU는 하나다.** 스위트·학습·백테스트를 동시에 돌리지 말 것.
- 전체 스위트 ~49분, 30m 학습 ~3.5h, 백테스트/edge-validate ~40분. 행 아님.

---

## 6. 다음 실험

1. **45m 결과 확인** (학습 진행 중). **gross가 약 9 bps를 못 넘기면 이 비용 기준에서 mean-reversion
   계열 종료.** 30m 7.34 bps, SL 크로싱 기준 비용 하한 ≈ 5.8 bps.
2. **`--sl-fill next_open`을 30m·45m 양쪽에** — 되돌린 꼬리가 REJECT을 뒤집는지. 양방향 효과라
   결과 방향을 미리 알 수 없다.
3. 전체 스위트 재실행 (`8fc08f5`, `1699b88` 이후 미실행).

**2025 H2 홀드아웃은 아직 깨끗하다.** 후보가 살아 있을 때만 쓸 것.

**보류**: 라이브 경로 연결(2026-07-30 사용자 결정). 실제 maker 체결률·유효 관통은 실계좌 주문 없이
측정 불가하므로, 이 축은 보류 동안 미검증으로 남는다.

미착수(이전부터 사용자 미승인): `select_threshold` 승인-거부 게이트, regime-path uniqueness weighting.
