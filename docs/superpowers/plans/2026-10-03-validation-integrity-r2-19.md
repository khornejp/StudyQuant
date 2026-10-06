# R2-19 검증 정합성 복구 + 후보 재평가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 이 프로젝트의 작업 방식: Codex가 구현(`codex exec ... - < BRIEF.md`), Claude가 검토·테스트·커밋. `out/`은 git 제외, 테스트만 커밋.

**Goal:** 외부 검토 문서(`scripts/BTCUSDT_RESULTS_LIVE_READINESS_REVIEW_KO.md`)가 지적한 검증 결함 중 코드에서 사실로 확인된 것을 고치고, 같은 엔진으로 후보 전략(E1, F3, A3, F4)의 위험·유의성을 다시 계산한다.

**Architecture:** 공통 모듈 1개(`out/k45_ledger.py`: 분 단위 평가손익 원장, 구간 경계 분할, 사건 묶음, 디플레이티드 Sharpe)와 실행기 1개(`out/run_k45_validation_r2_19.py`)를 만든다. 거래 생성은 R2-14 코드(`out/run_k45_classic_rules_r2_14.py`)의 신호·체결 함수를 import해서 그대로 쓰고, PW 블록 추정·stationary bootstrap은 기존 `out/run_patchtst_k45_flow_inference.py`의 함수를 import한다. 새 데이터, 새 모델 학습은 없다.

**Tech Stack:** Python (venv_btcusdt), pandas, numpy, scipy, pytest.

**Spec:** `scripts/BTCUSDT_RESULTS_LIVE_READINESS_REVIEW_KO.md` (2026-10-02 작성, 입력 = 당시 results.zip). 이 문서는 외부 검토이므로 지적 하나하나를 코드로 확인한 뒤에만 반영한다. 아래 "검토 지적 확인 결과" 표가 반영 근거다.

## 검토 지적 확인 결과 (2026-10-03, 코드 대조)

| # | 검토 지적 | 코드 확인 결과 | 반영 |
|---|---|---|---|
| 1 | 일별 수익이 청산일 실현손익 합이라 보유 중 낙폭을 못 본다 (6.1) | 사실. `out/run_k45_classic_rules_r2_14.py:851-865` `_daily_returns`는 `exit_time` 날짜에 net을 더한다. MDD·Sharpe 모두 이 값 기준 | Task 1, 6 |
| 2 | 구간 경계를 넘는 거래를 진입 구간 마지막 날로 배정 → DEV가 2026 손익을 봄 (6.2) | 사실. 같은 함수가 `.clip(upper=end - 1day)`로 DEV 마지막 날에 몰고, `assign_segment`(197-201)는 진입 시각으로 구간을 정한다 | Task 1 |
| 3 | `pw_block`이 Politis–White 자동 추정이 아니라 `round(n^(1/3))` 고정 블록 (6.4) | 사실. 1091행 `max(2, round(n ** (1 / 3)))`, manifest 1195행 문구도 동일. 반면 `out/run_patchtst_k45_flow_inference.py:114-210`에는 실제 PW 추정·stationary bootstrap 구현이 있다 | Task 2 |
| 4 | 813칸 탐색 보정 후 유의성 없음, 디플레이티드 Sharpe 필요 (6.3, 부록 C) | SPA·RC는 이미 있음. DSR은 없음 | Task 4 |
| 5 | 상위 거래가 아니라 사건·날짜·주 단위로 묶어 제외해야 함 (4장) | R2-17에 사건 묶음이 일부 있음(F3/F1/A3만). 공통 함수는 없음 | Task 3 |
| 6 | 펀딩 컬럼이 실제 정산률인지 대조 필요 (6.5) | 미확인. 로컬에 `artifacts/funding_2020_2026h1/BTCUSDT-fundingRate-*.zip`(공식 아카이브)이 있어 대조 가능 | Task 5 |
| 7 | 롱숏비율 timestamp가 기간 종료 시각, as-of 조인 필요 (3.2) | `btcusdt_quant/metrics_source.py` 설명: 1분봉은 자기 open_time 이하 최신 create_time 값만 봄. R2-14 `_attach_minute_features`(404-410)는 결정 시각 직전 분 행을 씀. 누수 근거는 아직 없음. 확인 테스트만 추가 | Task 5 |
| 8 | E1 돌파 기준이 현재 봉 고가를 포함하면 안 됨 (3.1) | 616-618행: `close > high_20.shift()` → 직전 20봉 고가와 비교, 현재 봉 미포함. `volume_z20`(144-145)은 현재 닫힌 봉 거래량을 자기 포함 20봉 평균·표준편차로 표준화 — 누수는 아니나 정의를 문서에 명시 | Task 6 (고정 테스트) |
| 9 | 비용 8/12 bps는 산술 차감만 했다 (7장) | R2-14에 비용 0/4/8 재계산 있음. 12 bps 없음 | Task 6 |
| 10 | 같은 노출·거래 수·보유시간 무작위 기준 필요 (E1) | R2-14 무작위는 "같은 n·노출". 보유시간 분포 일치는 확인 안 됨 | Task 6 |

| 11 | (계획 작성 중 발견) 기존 `optimal_block_length`는 자기상관이 거의 없는 시계열에서 추정 블록 < 1이면 예외를 낸다 | 2026-10-03 확인: iid 정규 1,500개 seed 0, 3에서 `invalid Politis-White block length`. 이 경로를 쓴 기존 실험에서 `UNMEASURABLE`로 빠진 칸이 있었을 수 있음 | Task 2 (블록 1로 대체, 상태 `MEASURABLE_BLOCK1`로 구분 기록) |

계획서의 Task 1~4 예시 코드는 작성 시점에 임시 파일로 실행해 테스트 12개 통과를 확인했다(2026-10-03, 임시 파일은 삭제).

검토 문서가 "결과 없음"으로 본 R2-9b, R2-13, R2-15, R2-16(진행 중), R2-17은 그 뒤 완료됐다. 결과는 `docs/results/`에 있다. 이 계획은 그 결과를 바꾸지 않는다.

## Global Constraints

- 로컬 데이터만. 다운로드 금지. 데이터 cutoff 2026-06-30 23:59 UTC.
- HOLD_A(2026 Q3)는 사용자 결정(2026-10-02)으로 제외. `artifacts/btcusdt_2026q3_source/` 읽지 않음.
- 실주문·지갑·인증 API 금지. 검토 6.5의 `GET /fapi/v1/commissionRate`(인증 필요)와 8장 단계 E(shadow/paper)는 이번 범위 밖.
- 비용 왕복 4 bps 기본. 스트레스 8, 12 bps는 **재계산**(산술 차감 아님).
- 단일 포지션(SINGLE)만. 레버리지·피라미딩 없음.
- CPU 워커 최대 4 (R2-16이 동시에 돈다).
- 결과 보고: 판정 문구보다 숫자를 먼저. 모든 칸 보고. HOLD_B는 "이미 본 구간" 표기.
- 출력: `out/k45_validation_r2_19_20261003/` (REPORT.md 숫자만, 5,000줄 이하, manifest.json에 입력·출력·소스 SHA256, cutoff, 동결 가설).

## Review Focus

1. **보유 중 구간 경계를 넘는 거래** (2025-12-31 진입 → 2026-01-02 청산): DEV 몫은 2025-12-31 23:59 평가가격까지, 나머지는 HOLD_B. 두 몫의 합 = 전체 거래 손익. → Task 1 테스트 `test_boundary_split_sums_to_trade`.
2. **거래가 하나도 없는 날**: 일별 수익 0으로 포함, 일수는 구간 달력 일수와 같음. → Task 1 `test_no_trade_days_are_zero`.
3. **펀딩 정산이 보유 중 여러 번**(24h 보유 → 3회): 평가손익 원장에서 정산 시각의 분에 반영. → Task 1 `test_funding_booked_at_settlement_minute`.
4. **PW 추정이 불가능한 짧은/상수 시계열**(HOLD_B 거래 3건 등): 예외로 죽지 않고 `UNMEASURABLE` 기록. → Task 2 `test_pw_unmeasurable_is_reported`.
5. **같은 사건에 여러 거래가 붙은 경우**(F3 연속 신호): 사건 단위 제외가 거래 단위 제외보다 더 많이 빠지거나 같음. → Task 3 `test_event_exclusion_removes_whole_event`.

---

## File Structure

- Create `out/k45_ledger.py` — 평가손익 원장(분→일), 구간 경계 분할, 사건 묶음, DSR. 순수 함수만.
- Create `out/run_k45_validation_r2_19.py` — 후보 칸 재생성(R2-14 함수 import), 원장 계산, 지표·기준선·보고서.
- Create `tests/test_k45_ledger.py` — Task 1~4 테스트.
- Create `tests/test_k45_validation_r2_19.py` — Task 5~6 테스트.
- 재사용(수정 금지): `out/run_k45_classic_rules_r2_14.py`(`load_inputs`, `prepare_bars`, `grid_specs`, `simulate*`, `settlement_events`), `out/run_patchtst_k45_flow_inference.py`(`optimal_block_length`, `stationary_bootstrap_errors`).

---

### Task 1: 분 단위 평가손익 원장과 구간 경계 분할

**Files:**
- Create: `out/k45_ledger.py`
- Test: `tests/test_k45_ledger.py`

**Interfaces:**
- Produces:
  - `mtm_minute_pnl(trades: pd.DataFrame, closes: pd.Series, funding: pd.DataFrame, cost_bps: float) -> pd.Series` — index = 분 UTC, 값 = 그 분의 평가손익 변화(bps, 1단위 기준). 진입 분에 진입 비용 cost/2, 청산 분에 cost/2, 정산 분에 펀딩.
    - `trades` 열: `side`(+1/−1), `entry_time`, `entry_price`, `exit_time`, `exit_price`.
    - `closes`: 1분봉 종가, index = open_time(UTC).
    - `funding`: 열 `time`, `rate`.
  - `daily_from_minutes(minute_pnl: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series` — [start, end) 달력 일 전체, 거래 없는 날 0.
  - `segment_pnl(minute_pnl, segments: dict[str, tuple[Timestamp, Timestamp]]) -> dict[str, pd.Series]` — 분 손익을 시각으로 자름. 경계를 넘는 거래는 자동으로 나뉨.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_k45_ledger.py
import numpy as np
import pandas as pd
import pytest

from out import k45_ledger as L

UTC = "UTC"


def _closes(start, prices):
    idx = pd.date_range(start, periods=len(prices), freq="min", tz=UTC)
    return pd.Series(prices, index=idx, dtype=float)


def _trade(side, entry, entry_px, exit_, exit_px):
    return pd.DataFrame({"side": [side], "entry_time": [pd.Timestamp(entry, tz=UTC)],
                         "entry_price": [entry_px], "exit_time": [pd.Timestamp(exit_, tz=UTC)],
                         "exit_price": [exit_px]})


NO_FUNDING = pd.DataFrame({"time": pd.to_datetime([], utc=True), "rate": []})


def test_minute_pnl_sums_to_realized_trade():
    closes = _closes("2024-01-01 00:00", [100, 101, 99, 102, 103])
    t = _trade(1, "2024-01-01 00:00", 100.0, "2024-01-01 00:04", 103.0)
    pnl = L.mtm_minute_pnl(t, closes, NO_FUNDING, cost_bps=4.0)
    realized = np.log(103 / 100) * 1e4 - 4.0
    assert pnl.sum() == pytest.approx(realized)
    # 보유 중 최저점이 원장에 보여야 한다 (99에서 평가손실)
    equity = pnl.cumsum()
    assert equity.min() < 0


def test_boundary_split_sums_to_trade():
    # 23:57 100, 23:58 100, 23:59 90 | 00:00 110, 00:01 110, 00:02 110, 00:03 110
    closes = _closes("2025-12-31 23:57", [100.0, 100.0, 90.0, 110.0, 110.0, 110.0, 110.0])
    t = _trade(1, "2025-12-31 23:57", 100.0, "2026-01-01 00:03", 110.0)
    pnl = L.mtm_minute_pnl(t, closes, NO_FUNDING, cost_bps=4.0)
    seg = L.segment_pnl(pnl, {"DEV": (pd.Timestamp("2020-07-01", tz=UTC), pd.Timestamp("2026-01-01", tz=UTC)),
                              "HOLD_B": (pd.Timestamp("2026-01-01", tz=UTC), pd.Timestamp("2026-07-01", tz=UTC))})
    total = np.log(110 / 100) * 1e4 - 4.0
    assert seg["DEV"].sum() + seg["HOLD_B"].sum() == pytest.approx(total)
    # DEV 몫은 2025-12-31 23:59 종가(90)까지의 평가손익 + 진입 비용
    assert seg["DEV"].sum() == pytest.approx(np.log(90 / 100) * 1e4 - 2.0)


def test_no_trade_days_are_zero():
    closes = _closes("2024-01-01 00:00", [100, 101])
    t = _trade(1, "2024-01-01 00:00", 100.0, "2024-01-01 00:01", 101.0)
    pnl = L.mtm_minute_pnl(t, closes, NO_FUNDING, cost_bps=4.0)
    daily = L.daily_from_minutes(pnl, pd.Timestamp("2024-01-01", tz=UTC), pd.Timestamp("2024-01-08", tz=UTC))
    assert len(daily) == 7
    assert (daily.iloc[1:] == 0).all()


def test_funding_booked_at_settlement_minute():
    closes = _closes("2024-01-01 07:58", [100.0] * 5)
    t = _trade(1, "2024-01-01 07:58", 100.0, "2024-01-01 08:02", 100.0)
    funding = pd.DataFrame({"time": [pd.Timestamp("2024-01-01 08:00", tz=UTC)], "rate": [0.001]})
    pnl = L.mtm_minute_pnl(t, closes, funding, cost_bps=0.0)
    assert pnl.loc[pd.Timestamp("2024-01-01 08:00", tz=UTC)] == pytest.approx(-10.0)
    assert pnl.sum() == pytest.approx(-10.0)
```

- [ ] **Step 2: 실패 확인**

Run: `venv_btcusdt\Scripts\python.exe -m pytest tests/test_k45_ledger.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'out.k45_ledger'`

- [ ] **Step 3: 최소 구현**

```python
# out/k45_ledger.py
"""Mark-to-market ledger, segment split, event clustering and deflated Sharpe (R2-19)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import norm


def mtm_minute_pnl(trades: pd.DataFrame, closes: pd.Series, funding: pd.DataFrame,
                   cost_bps: float) -> pd.Series:
    """Per-minute log-return P&L in bps for a 1-unit book; costs at entry/exit minute."""
    # ponytail: per-trade loop, fine for the 7 frozen candidates; vectorise if run over 813 cells
    out = pd.Series(0.0, index=closes.index)
    log_close = np.log(closes.astype(float))
    for t in trades.itertuples(index=False):
        held = closes.index[(closes.index >= t.entry_time) & (closes.index <= t.exit_time)]
        if len(held) == 0:
            continue
        # entry at entry_price, marked at each held minute's close, exit at exit_price in the exit minute
        level = np.r_[log_close.loc[held[:-1]].to_numpy(), math.log(t.exit_price)]
        prev = np.r_[math.log(t.entry_price), level[:-1]]
        out.loc[held] += (level - prev) * 1e4 * t.side
        out.loc[held[0]] -= cost_bps / 2
        out.loc[held[-1]] -= cost_bps / 2
        hit = funding[(funding.time > t.entry_time) & (funding.time <= t.exit_time)]
        missing = hit.time[~hit.time.isin(out.index)]
        if len(missing):
            raise ValueError(f"funding time outside minute index: {missing.iloc[0]}")
        for f in hit.itertuples(index=False):
            out.loc[f.time] -= t.side * f.rate * 1e4
    return out


def daily_from_minutes(minute_pnl: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    days = pd.date_range(start, end - pd.Timedelta(days=1), freq="D", tz="UTC")
    part = minute_pnl.loc[(minute_pnl.index >= start) & (minute_pnl.index < end)]
    return part.groupby(part.index.normalize()).sum().reindex(days, fill_value=0.0)


def segment_pnl(minute_pnl: pd.Series, segments: dict) -> dict[str, pd.Series]:
    return {name: minute_pnl.loc[(minute_pnl.index >= s) & (minute_pnl.index < e)]
            for name, (s, e) in segments.items()}
```

구현 메모(실행자용): 계약은 테스트가 정한다 — (a) 분 손익 합 = 실현 로그수익 − 비용 + 펀딩, (b) 보유 중 각 분 종가로 평가, 마지막 분은 청산가, (c) 비용은 진입 분/청산 분에 절반씩, (d) 펀딩은 `entry < time <= exit`인 정산 분에. 813칸 전체에 쓰면 느리므로 후보 칸(Task 6)에만 쓰고, 벡터화가 필요하면 `ponytail:` 주석으로 한계를 적는다.

- [ ] **Step 4: 통과 확인**

Run: `venv_btcusdt\Scripts\python.exe -m pytest tests/test_k45_ledger.py -q`
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add tests/test_k45_ledger.py
git commit -m "test: minute mark-to-market ledger and segment boundary split (R2-19 Task 1)"
```

---

### Task 2: Politis–White 자동 블록 + stationary bootstrap 연결

**Files:**
- Modify: `out/k45_ledger.py` (함수 추가)
- Test: `tests/test_k45_ledger.py`

**Interfaces:**
- Consumes: `out/run_patchtst_k45_flow_inference.py`의 `optimal_block_length(series) -> dict`, `stationary_bootstrap_errors(centered, block_length, reps, seed) -> np.ndarray` (import, 복제 금지).
- Produces: `pw_mean_ci(daily: np.ndarray, reps: int = 2000, seed: int = 20261003) -> dict` — 키 `status`("MEASURABLE"/"MEASURABLE_BLOCK1"/"UNMEASURABLE"), `block`, `mean`, `ci95_lower`, `ci95_upper`, `p_greater_zero`, `error`.

- [ ] **Step 1: 실패하는 테스트**

```python
def _ar(phi, n=1500, seed=0):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal()
    return x


def test_pw_block_grows_with_autocorrelation():
    assert L.pw_mean_ci(_ar(0.8))["block"] > L.pw_mean_ci(_ar(0.2))["block"]


def test_pw_iid_falls_back_to_block_one():
    # 2026-10-03 확인: 기존 optimal_block_length는 iid 시계열에서
    # "invalid Politis-White block length"(추정 블록 < 1)로 예외를 낸다.
    out = L.pw_mean_ci(np.random.default_rng(0).normal(size=1500))  # seed 0: 추정 블록 < 1 확인됨
    assert out["status"] == "MEASURABLE_BLOCK1"
    assert out["block"] == 1.0
    assert np.isfinite(out["ci95_lower"])


def test_pw_unmeasurable_is_reported():
    out = L.pw_mean_ci(np.zeros(181))
    assert out["status"] == "UNMEASURABLE"
    assert np.isnan(out["ci95_lower"])


def test_pw_is_seeded():
    x = np.random.default_rng(1).normal(size=400)
    assert L.pw_mean_ci(x) == L.pw_mean_ci(x)
```

- [ ] **Step 2: 실패 확인** — `AttributeError: module 'out.k45_ledger' has no attribute 'pw_mean_ci'`

- [ ] **Step 3: 구현**

```python
from out.run_patchtst_k45_flow_inference import optimal_block_length, stationary_bootstrap_errors


def pw_mean_ci(daily: np.ndarray, reps: int = 2000, seed: int = 20261003) -> dict:
    x = np.asarray(daily, dtype=float)
    centered = x - x.mean()
    status = "MEASURABLE"
    try:
        block = float(optimal_block_length(centered)["block_length_stationary"])
    except ValueError as error:
        if "invalid Politis-White block length" not in str(error):
            return {"status": "UNMEASURABLE", "block": math.nan, "mean": float(x.mean()),
                    "ci95_lower": math.nan, "ci95_upper": math.nan, "p_greater_zero": math.nan,
                    "error": str(error)}
        block, status = 1.0, "MEASURABLE_BLOCK1"  # estimated block < 1: no serial dependence detected
    errors = stationary_bootstrap_errors(centered, block, reps=reps, seed=seed)
    mean = float(x.mean())
    return {"status": status, "block": block, "mean": mean,
            "ci95_lower": mean - float(np.quantile(errors, .975)),
            "ci95_upper": mean - float(np.quantile(errors, .025)),
            "p_greater_zero": (1 + int((errors >= mean).sum())) / (reps + 1), "error": ""}
```

먼저 `python -c "import out.run_patchtst_k45_flow_inference"`가 부작용(파일 쓰기·학습) 없이 끝나는지 확인한다. 부작용이 있으면 두 함수를 `out/k45_ledger.py`로 옮기지 말고 멈추고 보고한다.

- [ ] **Step 4: 통과 확인** — `8 passed`
- [ ] **Step 5: 커밋** — `test: Politis-White automatic block and stationary bootstrap CI (R2-19 Task 2)`

---

### Task 3: 사건·주 단위 묶음 제외

**Files:**
- Modify: `out/k45_ledger.py`
- Test: `tests/test_k45_ledger.py`

**Interfaces:**
- Produces:
  - `assign_events(trades: pd.DataFrame, gap: pd.Timedelta = pd.Timedelta(hours=24)) -> pd.Series` — 진입 시각 순으로, 직전 거래 청산 후 `gap` 안에 진입한 거래는 같은 사건 번호.
  - `exclude_top(trades: pd.DataFrame, net: pd.Series, by: pd.Series, k: int) -> float` — `by`로 묶은 그룹 합이 큰 순으로 k개 그룹을 뺀 총 net.

- [ ] **Step 1: 실패하는 테스트**

```python
def _tr(entries, exits, nets):
    return pd.DataFrame({"entry_time": pd.to_datetime(entries, utc=True),
                         "exit_time": pd.to_datetime(exits, utc=True)}), pd.Series(nets, dtype=float)


def test_event_exclusion_removes_whole_event():
    trades, net = _tr(["2024-01-01 00:00", "2024-01-01 05:00", "2024-02-01 00:00"],
                      ["2024-01-01 04:00", "2024-01-01 09:00", "2024-02-01 04:00"],
                      [50.0, 40.0, 60.0])
    ev = L.assign_events(trades)
    assert ev.iloc[0] == ev.iloc[1] != ev.iloc[2]
    by_trade = L.exclude_top(trades, net, pd.Series(range(3)), k=1)
    by_event = L.exclude_top(trades, net, ev, k=1)
    assert by_trade == pytest.approx(90.0)
    assert by_event == pytest.approx(60.0)
    assert by_event <= by_trade


def test_week_grouping_uses_entry_week():
    trades, net = _tr(["2024-01-01", "2024-01-03", "2024-01-10"],
                      ["2024-01-02", "2024-01-04", "2024-01-11"], [10.0, 20.0, 5.0])
    week = trades.entry_time.dt.to_period("W")
    assert L.exclude_top(trades, net, week, k=1) == pytest.approx(5.0)
```

- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현**

```python
def assign_events(trades: pd.DataFrame, gap: pd.Timedelta = pd.Timedelta(hours=24)) -> pd.Series:
    order = trades.sort_values("entry_time")
    new = order.entry_time.sub(order.exit_time.shift()).gt(gap) | order.exit_time.shift().isna()
    return new.cumsum().reindex(trades.index)


def exclude_top(trades: pd.DataFrame, net: pd.Series, by: pd.Series, k: int) -> float:
    grouped = net.groupby(by.to_numpy()).sum().sort_values(ascending=False)
    return float(grouped.iloc[k:].sum())
```

- [ ] **Step 4: 통과 확인** — `10 passed`
- [ ] **Step 5: 커밋** — `test: event and week grouped exclusion (R2-19 Task 3)`

---

### Task 4: 디플레이티드 Sharpe (Bailey & López de Prado 2014)

**Files:**
- Modify: `out/k45_ledger.py`
- Test: `tests/test_k45_ledger.py`

**Interfaces:**
- Produces: `deflated_sharpe(daily: np.ndarray, n_trials: int, trial_sharpe_var: float) -> dict` — 키 `sr`(일 단위), `sr0`(시도 수 보정 기준), `dsr`(확률), `skew`, `kurt`, `n`.
  - `sr0 = sqrt(V) * ((1 - γ) * Φ⁻¹(1 - 1/N) + γ * Φ⁻¹(1 - 1/(N e)))`, γ = 0.5772156649.
  - `dsr = Φ( (sr - sr0) * sqrt(n - 1) / sqrt(1 - skew*sr + (kurt - 1)/4 * sr²) )`, kurt는 보통 첨도(정규=3).

- [ ] **Step 1: 실패하는 테스트**

```python
def test_dsr_falls_with_more_trials():
    x = np.random.default_rng(2).normal(0.05, 1.0, size=1500)
    few = L.deflated_sharpe(x, n_trials=2, trial_sharpe_var=0.001)
    many = L.deflated_sharpe(x, n_trials=813, trial_sharpe_var=0.001)
    assert many["dsr"] < few["dsr"]
    assert 0.0 <= many["dsr"] <= 1.0


def test_dsr_single_trial_matches_psr_against_zero():
    x = np.random.default_rng(3).normal(0.02, 1.0, size=1000)
    out = L.deflated_sharpe(x, n_trials=1, trial_sharpe_var=0.0)
    assert out["sr0"] == 0.0
```

- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현**

```python
from scipy.stats import kurtosis, skew

EULER = 0.5772156649


def deflated_sharpe(daily: np.ndarray, n_trials: int, trial_sharpe_var: float) -> dict:
    x = np.asarray(daily, dtype=float)
    n = len(x)
    sr = float(x.mean() / x.std(ddof=1))
    g3 = float(skew(x))
    g4 = float(kurtosis(x, fisher=False))
    if n_trials <= 1 or trial_sharpe_var <= 0:
        sr0 = 0.0
    else:
        sr0 = math.sqrt(trial_sharpe_var) * ((1 - EULER) * norm.ppf(1 - 1 / n_trials)
                                             + EULER * norm.ppf(1 - 1 / (n_trials * math.e)))
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    dsr = float(norm.cdf((sr - sr0) * math.sqrt(n - 1) / denom))
    return {"sr": sr, "sr0": sr0, "dsr": dsr, "skew": g3, "kurt": g4, "n": n}
```

`trial_sharpe_var`는 R2-14 `all_cells.parquet`의 DEV 칸들 일 단위 Sharpe(= daily_sharpe/√365)의 분산을 쓴다(Task 6에서 계산).

- [ ] **Step 4: 통과 확인** — `12 passed`
- [ ] **Step 5: 커밋** — `test: deflated Sharpe ratio for multiple trials (R2-19 Task 4)`

---

### Task 5: 펀딩·롱숏비율 시점 대조 (데이터 감사)

**Files:**
- Create: `out/run_k45_validation_r2_19.py` (함수 `audit_funding`, `audit_ls_asof`)
- Test: `tests/test_k45_validation_r2_19.py`

**Interfaces:**
- Consumes: R2-14 `load_inputs()`, `settlement_events(registry)`.
- Produces:
  - `load_funding_archive(path: Path) -> pd.DataFrame` — `artifacts/funding_2020_2026h1/*.zip`의 CSV를 읽어 열 `time`(UTC, fundingTime), `rate`(float).
  - `audit_funding(r214_events: pd.DataFrame, archive: pd.DataFrame) -> pd.DataFrame` — 정산 시각별 R2-14 요율, 아카이브 요율, 차이, 일치 여부(|차이| < 1e-9), 한쪽에만 있는 시각.
  - `audit_ls_asof(registry: pd.DataFrame, metrics_rows) -> dict` — create_time 분포(분 단위 나머지), R2-14가 쓴 값이 결정 시각 이전 create_time 값인지 위반 수.

- [ ] **Step 1: 실패하는 테스트**

```python
import pandas as pd
import pytest

from out import run_k45_validation_r2_19 as R


def test_audit_funding_flags_mismatch_and_missing():
    t = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 08:00", "2024-01-01 16:00"], utc=True)
    ours = pd.DataFrame({"time": t[:2], "rate": [0.0001, 0.0002]})
    arch = pd.DataFrame({"time": t, "rate": [0.0001, 0.0003, 0.0001]})
    out = R.audit_funding(ours, arch)
    assert out.set_index("time").loc[t[0], "match"]
    assert not out.set_index("time").loc[t[1], "match"]
    assert out.set_index("time").loc[t[2], "only_in"] == "archive"


def test_ls_feature_uses_only_past_create_time():
    create = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:05"], utc=True)
    decision = pd.Timestamp("2024-01-01 00:05", tz="UTC")
    used = R.asof_value_time(create, decision)
    assert used == create[0]
```

- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현** — `audit_funding`은 `outer` merge 후 `only_in`(`both`/`ours`/`archive`)와 `match`를 계산. `asof_value_time(create_times, decision)`은 R2-14와 같은 규칙(결정 시각 1분 전 행이 볼 수 있는 마지막 create_time, 즉 `create_time <= decision - 1min`)을 반환. `load_funding_archive`는 zip 안 CSV의 `calc_time`/`funding_time` 열 이름을 실제 파일에서 확인해 쓰고, 열 이름을 manifest에 기록.
- [ ] **Step 4: 실제 데이터로 실행** — 결과 표: 정산 수, 일치 수, 불일치 목록(상위 50), 한쪽에만 있는 시각. 롱숏비율: create_time 분 나머지 분포, 위반 수.
  - **불일치가 0이 아니면** Task 6에서 R2-14 펀딩 대신 아카이브 요율로 재계산한 버전을 추가로 보고(대체가 아니라 병기).
- [ ] **Step 5: 커밋** — `test: funding archive and long/short as-of audit (R2-19 Task 5)`

---

### Task 6: 후보 재평가 (동결 목록, 같은 엔진)

**Files:**
- Modify: `out/run_k45_validation_r2_19.py`
- Test: `tests/test_k45_validation_r2_19.py`

**동결 후보 (결과 보고 바꾸지 않음):**
`E1|1h|3|signal|L`(검토 1순위), `E1|1h|2|signal|L`(인접), `F3|1h|10/24|signal|LS`, `F3|1h|5/24|signal|LS`, `A3|4h|720|signal|LS`, `F4|1h|5/4|signal|L`, 그리고 바이앤홀드.

**Interfaces:**
- Consumes: R2-14 `grid_specs()`에서 위 cell_id의 Spec → 같은 신호·체결 함수로 거래 생성. Task 1~5 함수.
- Produces: `out/k45_validation_r2_19_20261003/` 표:
  - `reproduction.parquet` — 새 엔진 거래 n·실현 net 합이 R2-14 `all_cells.parquet`와 일치(차이 0)하는지. 불일치면 멈추고 보고.
  - `risk.parquet` — 칸 × 구간(DEV, DEV_EX2020, HOLD_B) × 비용(4, 8, 12): 평가손익 일별 Sharpe, 평가손익 MDD, 최악 1일, 실현 기준 MDD(기존 방식, 비교용), 거래 수, 총 net.
  - `boundary.parquet` — 경계를 넘는 거래 목록과 DEV 몫·HOLD_B 몫, 기존 방식(전부 DEV) 대비 DEV 총 net 차이.
  - `inference.parquet` — PW 자동 블록 길이, CI, p; 기존 n^(1/3) 블록 CI와 나란히. DSR(시도 수 813, 그리고 R2-14~R2-18 누적 칸 수 기준 두 가지).
  - `concentration.parquet` — 상위 1/2/5 거래, 사건, 날짜, 주 제외 후 총 net (DEV, HOLD_B).
  - `random_matched.parquet` — 같은 거래 수·같은 보유시간 분포(실제 보유시간을 무작위 진입 시각에 재배치)·같은 방향 비율의 무작위 1,000회 백분위.
  - `e1_definition.md` — E1 정의 원문: `close > high_20.shift()`(직전 20봉, 현재 봉 제외), `volume_z20 = (v - mean20(v incl. current)) / std20(v incl. current, ddof=0)`, 닫힌 1h봉, 다음 1분 시가 체결, 20봉(1,200분) 시간 청산.

- [ ] **Step 1: 실패하는 테스트**

```python
def test_reproduction_matches_r2_14_for_e1():
    rep = R.reproduce(["E1|1h|3|signal|L"])
    row = rep.set_index(["cell_id", "segment"]).loc[("E1|1h|3|signal|L", "DEV")]
    assert row.n_new == row.n_r214
    assert abs(row.net_new - row.net_r214) < 1e-6


def test_matched_random_keeps_hold_distribution():
    holds = pd.Series([60, 120, 1200], dtype=float)
    draws = R.matched_random_holds(holds, n_draws=5, seed=7)
    for d in draws:
        assert sorted(d) == sorted(holds.tolist())


def test_e1_breakout_excludes_current_bar():
    bars = R.toy_bars_for_e1()          # 21봉, 마지막 봉 high가 신고가지만 close는 직전 20봉 고가 아래
    assert R.e1_entries(bars, zcut=0.0)[-1] == 0
```

- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현** — `reproduce`, `matched_random_holds`, `toy_bars_for_e1`, `e1_entries`(R2-14 `_base_signals`의 E1 분기를 import 경로로 호출하는 얇은 래퍼)와 위 표 생성. 일별 지표는 모두 `daily_from_minutes(segment_pnl(...))` 기준, 거래 없는 날 포함.
- [ ] **Step 4: 실행·보고** — REPORT.md 앞부분 순서: 재현 확인 → 경계 거래 영향 → 칸별 평가손익 MDD·Sharpe vs 기존 → PW 자동 블록 CI vs 기존 → DSR → 집중도(사건·주) → 무작위 대비 → 비용 12 bps. 판정 문장 없이 숫자.
- [ ] **Step 5: 커밋** — 테스트 파일만: `test: candidate re-evaluation with MTM ledger, PW blocks and DSR (R2-19 Task 6)`

**동결 가설(실행 전 manifest에 기록):**
"검토 1순위 E1|1h|3|signal|L은 평가손익 원장·경계 분할·PW 자동 블록·DSR(813 시도)을 적용해도 (a) DEV 총 net > 0, (b) DEV PW CI 하한 > 0, (c) DSR > 0.95, (d) 사건 단위 상위 5개 제외 후 DEV 총 net > 0 을 모두 만족한다." HOLD_B는 이미 본 구간이라 판정에서 제외하고 따로 기록.

---

## 범위 밖 (검토 문서 항목 중 이번에 하지 않는 것과 이유)

| 검토 항목 | 이유 |
|---|---|
| 6.5 `GET /fapi/v1/commissionRate`로 실제 수수료 확인 | 인증 API — 프로젝트 경계상 금지. 사용자가 직접 확인해 값을 주면 비용 칸에 추가 |
| 8장 단계 C: 보지 않은 새 구간 1회 평가 | 로컬에 남은 미사용 구간 없음(HOLD_A는 사용자 결정으로 제외). 새 데이터는 사용자 결정 필요 |
| 8장 단계 E: shadow/paper, 제한 위험 실거래 | 실거래 경로 보류 결정 유지 |
| 3.2 Binance LS API 30일 제한(운영 데이터 조건) | 운영 단계 문제. 이번엔 과거 아카이브 시점 정합성만 Task 5에서 확인 |
| 8장 단계 D: E1 메타 필터 | R2-15에서 E1 메타 필터는 이미 실행됨(E1|1h|3 catboost base DEV +39.03 → +68.81). 재평가는 Task 6 결과 뒤 별도 계획 |

## Self-Review 결과

- 검토 지적 1~10 중 코드로 확인된 1, 2, 3과 확인 필요한 6, 7, 8은 Task 1, 2, 5, 6에 대응. 4는 Task 4, 5는 Task 3, 9·10은 Task 6.
- 플레이스홀더: Task 5 Step 3의 아카이브 CSV 열 이름은 파일 확인 후 정하도록 명시(추측 금지).
- 이름 일관성: `mtm_minute_pnl`, `daily_from_minutes`, `segment_pnl`, `pw_mean_ci`, `assign_events`, `exclude_top`, `deflated_sharpe`, `audit_funding`, `asof_value_time`, `reproduce`, `matched_random_holds`, `e1_entries` — Task 간 동일.
