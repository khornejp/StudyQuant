# 세션 핸드오프 — 2026-07-30 (Bitget 비용 기준 정정 + exit 체결 mix 측정)

브랜치: `fix/barrier-parity-and-metric-guards` (main 아님)
이 세션 커밋: `776fe7a` `2fe9950` `1347f61` `3e08136` `aa8d119` `8fc08f5` `1699b88`
직전 핸드오프: `SESSION_HANDOFF_2026-07-27.md` (🔴 §7의 다음 실험 목록은 무효 — 아래 §6 참조)

---

## 0. 한 줄 요약

> **실행 전제: 지정가 전용, 미체결 없음** (사용자 확인 2026-07-31). 진입과 네 청산
> (TP/SL/TIMEOUT/OPEN_AT_END) 전부 대기 체결 = `--maker-fill-window N --maker-exit`.
> 이 전제에서 왕복 비용은 **4 bps 상수**이고, 세션 중반에 내가 세운 exit-mix 축과 REJECT 판정은
> 무효다(§9.4/§9.5 → §10).
>
> 비용 기준 자체는 두 군데가 틀려 있었고 고쳤다: 계정은 Binance가 아니라 **Bitget VIP0**
> (maker 0.02% / taker 0.06%)이며 코드가 taker 체결에 maker 요율을 물려 왕복 8 bps를 과소
> 계상했고, exit 다리는 taker로 하드코딩돼 있었다.
>
> 2025 결과: 30m 연 +10.59%(1.5x 통과, 2x 탈락), 45m 연 +22.67%(1.5x·2x 모두 통과).
>
> 🔴 **그리고 45m은 2026 H1 미사용 홀드아웃에서 FAIL했다** — net **−5.448 bps/거래**,
> gross가 비용 전에 이미 음수, 6개월 전부 음수, 기간 net −35.86%. 2026 H1이 **−33% 지속
> 하락장**이었고 이 전략은 방향 필터 없는 롱 전용 눌림목 매수다. 2025 성적은 엣지가 아니라
> **국면 적합**이었다. **판정: REJECT.**

> 🔴 **최종(§14): 근본 원인은 방향이 아니라 배리어 기하다.** `--target profitability`가
> 타임아웃 소폭 상승을 승리로 세는데 EV 게이트는 그 확률에 TP 보상(+0.8%)을 곱하고 있었다
> (승리의 71~81%가 +0.27%짜리 타임아웃). 라벨을 `long_success`로 정합시키자 롱이 숏과 **동일한
> 확률 분포**가 됐고(중앙값 0.039 vs 0.041, 손익분기 0.333 초과 0.5% vs 0.6%), 거래가 사라졌다.
> 원인: 45분 변동성 0.46% 대비 tp 0.8%는 1.7σ라 **59%가 어느 배리어에도 도달 못 한다.**
> §13의 진단(라우터·게이트·숏)은 전부 이것의 그림자였다.

상세 전부: `EDGE_EXPERIMENT_RESULTS_2026-07-25.md` **§9(비용 기준 정정), §10(전제 확정 + 45m),
§11(오염 시인 + 사전 등록), §12(2026 H1 FAIL), §13(방향 해부), §14(근본 원인)**.

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

### 30m vs 45m (전제 A: 전 leg 지정가, 2025 OOS, 고정사이즈 0.1, Bitget VIP0)

| | 30m (0.6/0.3) | 45m (0.8/0.4) |
|---|---:|---:|
| 거래 | 3,022 | 2,424 |
| **gross/거래** | 7.336 bps | **12.435 bps** |
| 비용/거래 | 4.0 bps | 4.0 bps |
| **net/거래** | +3.336 bps | **+8.435 bps** |
| 승률 | 53.44% | **61.01%** |
| **연 net 1x** | +10.59% | **+22.67%** |
| 연 net 1.5x | +4.10% | **+16.86%** |
| 연 net 2x | **−2.00%** | **+11.33%** |
| net_sharpe | 0.106 | **0.227** |
| PF | 1.28 | **1.74** |
| maxDD | 0.71% | **0.50%** |
| 게이트 | 1.5x만 | **1.5x·2x 모두** |

산출물 `ev_mr30_bitget_makerexit`, `ev_mr45_makerexit_all`.
outcome 분포: 30m TP 13.4 / SL 29.8 / TIMEOUT 56.8%, 45m TP 10.6 / SL 20.8 / TIMEOUT 68.6%.
전제 A에서는 셋 다 대기 체결이라 비용에 영향 없음.

### 전제가 흔들릴 경우의 민감도 (참고, 헤드라인 아님)

30m을 exit 체결 mix별로 실측한 표는 `EDGE_EXPERIMENT_RESULTS` §9.4에 있다. taker 청산 비율 f에
대해 `cost = 4 + 6f` bps이고 손익분기 f = 0.556. 45m은 TIMEOUT 비중이 높아 전제 이탈에 더 크게
노출된다.

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

**단일 판정 기준**: 미사용 구간의 **net bps/거래 > 0**. 한 번에 하나의 축만 열고, 닫기 전에 새 축을
열지 않는다. 현재 최선은 −1.234 bps(45m 롱 + range 게이트 edge 0.15, 2026 H1).

**다음 후보 — 배리어 폐기(§14.5)**: 라벨·실행·EV를 호라이즌 수익률로 정합시킨다.
```
라벨   45봉 뒤 수익률       실행  45봉 보유 후 청산(배리어 없음)      EV  기대수익률 − 4bps
```
근거: 타임아웃 거래 평균이 +0.060%(6 bps)로 비용 4 bps를 넘는다. 지금은 그 59%를 실패로 버린다.

**미사용 구간이 없다.** 2025 소모, 2026 H1 소모. 다음은 2026 H2이며 아직 존재하지 않는다.
그때까지의 모든 결과는 검증이 아니라 후보 발굴이다.

### 이전 목록 (대부분 종료)

1. ~~**45m threshold 민감도 0.36~0.44**~~ → **완료, 고원 확인** (§11.2). 전 구간 양수,
   gross/거래가 threshold에 단조 증가(5.34→19.86 bps). threshold 과적합 의심 해소.
2. **regime 라우팅을 켠 45m 재검증** — §12.4(2). 30m/45m 실험은 `--disable-range-gate` +
   unified 모델로 방향 설계를 전부 끄고 돌렸고, 그것이 하락장에서 무방비였던 직접 원인이다.
3. **30m 숏 백테스트.** 학습 완료(`exp_mr30_short`, F1 0.2198, Brier 0.057, ECE 0.0086). 번들 조립
   필요(§4 참조). 단, fold별 threshold가 0.065~0.244로 3.8배 흩어져 있다 — 15m 숏의 "8거래" 문제와
   같은 뿌리일 수 있으므로 거래 수부터 볼 것.
3. **seed/기간/변동성 버킷 분해** (2025 한 해뿐이다).
4. **60m 재확인.** 45m이 이만큼 좋으면 60m 실패(F1 0.018)가 배리어 1.0/0.5 탓인지 재검토할 가치가 있다.
5. 전체 스위트 재실행 (`8fc08f5`, `1699b88` 이후 미실행).

🔴 **정정: "2025 H2 홀드아웃은 아직 깨끗하다"는 사실이 아니었다** (§11.1). 오늘까지의 모든
백테스트가 `2025-01-01 ~ 2025-12-31`이었고, 따라서 threshold 0.40 선택과 30m/45m 배리어 선택이
모두 H2를 본 상태에서 내려졌다. 2025 안에는 미사용 구간이 더 이상 없고, 데이터가 2025-12-31에서
끝나므로 복구도 불가능하다.

**대응**: 2026-01-01 ~ 06-30을 새로 수집해 진짜 미사용 최종 검증 구간으로 삼았다(§11.5).
파케 `artifacts/btcusdt_2020_2026h1.parquet`, 2020-2025 구간이 기존 파일과 바이트 동일함을 대조로
확인. 모델·배리어·threshold·사이징 전부 동결, 합격선(net ≥ 4 bps/거래 AND 거래 ≥ 500)을 결과
확인 전에 등록했다. **이 구간도 한 번 쓰면 소모된다.**

**보류**: 라이브 경로 연결(2026-07-30 사용자 결정). 실제 maker 체결률·유효 관통은 실계좌 주문 없이
측정 불가하므로, 이 축은 보류 동안 미검증으로 남는다.

미착수(이전부터 사용자 미승인): `select_threshold` 승인-거부 게이트, regime-path uniqueness weighting.
