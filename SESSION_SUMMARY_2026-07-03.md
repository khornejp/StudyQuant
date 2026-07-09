# 세션 요약 — BTCUSDT Quant: Train/Serve Parity → 룰베이스 Regime → 백테스트 정합성 (2026-07-03)

이 세션에서 수행한 전체 작업의 요약. 최종 산출물은
`CodexProject-rulebased-regime.zip`이며, 세부 처리 이력은
`TODO_RULE_REGIME_REVIEW.md`(리뷰 1~7차)와 `FIX_REPORT_TRAIN_SERVE_PARITY.md`,
`RULE_BASED_REGIME_REPORT.md`에 있다.

---

## 1. 시작점: Train/Serve Parity 4대 이슈 검증·수정

외부 분석의 4개 주장을 코드로 검증 → 전부 실재 → 수정.

| # | 이슈 | 수정 |
|---|---|---|
| 1 | F18(0/0/0) 커버리지 갭이 학습 bucket 오염 가능 | 갭 감지·경고 + 해당 row 전 버킷 제외. (당시 regimes.json은 2020~2024 무결 커버라 dormant) |
| 2 | live가 learned classifier 대신 trend_slope_30 룰로 라우팅 (skew) | live에 `.cbm` 로드 + `route_regime_causal` + F18 주입 배선 |
| 3 | 학습된 `selected_thresholds`가 live/backtest에서 미사용 | bundle에 적재, live 우선순위(override > learned > 0.55) 적용 |
| 4 | EV가 고정 0.15%/0.10%(RR1.5)인데 실제 barrier는 라벨 0.30%/0.15%(RR2.0) | `resolve_tp_sl_deltas` 단일 소스화, EV가 실제 barrier 사용 |

---

## 2. 아키텍처 결정: Regime을 룰베이스로 전환

사용자 결정: 학습형 regime classifier 제외, **멀티피처 룰베이스**로.

**신규 `regime_rules.py` — `MultiFeatureRegimeDetector`:**
- 점수 4종: trend(장기) / volatility / range / breakout(24h 돌파+volume_z>1.5 즉시 override)
- 히스테리시스(trend_enter 0.70 / exit 0.40) + `min_hold_bars` 60
- 정규화 통계를 학습구간에 fit → 아티팩트 저장 → backtest/live가 동일 통계 재사용 (skew 없음)
- 세 경로 일관 배선: 학습 bucket 배정(`--multi-feature-regime`) / backtest(아티팩트 자동 로드) / live(bundle 내장)
- 파이프라인 `REGIME_MODE=rule` 기본. 학습형 classifier 코드는 삭제하지 않고 잠자는 옵션으로 보존(`REGIME_MODE=classifier`)

**멀티 타임프레임 확장:**
- 단기 TF(5m `return_5` / 15m `trend_slope_15m` / 30m `trend_slope_30`) 추가 →
  이중반영 논의 후 **역할 분리**: 장기(1h/4h/24h)=regime 방향, 단기=진입확인(`fast_conflict_max`)·조기이탈(`fast_exit`)
- **24h 방향 피처 신규 구현**: `trend_slope_24h`(24×1h linreg slope), `return_24h` — F17/registry 등록 (활성 피처 187→189)
- `allow_direct_reversal`(up↔down 직접전환 토글), `switch_confirm_bars`(새 후보 N바 연속 디바운스) 추가
- **JSON config 외부화**: `train --rule-regime-config configs/rule_regime.json` — 전 필드 override, 아티팩트에 embed되어 backtest/live 자동 상속. 보수 프리셋(switch_confirm=10, direct_reversal=false)이 파이프라인 기본

---

## 3. 메모리 최적화

- **컬럼형 float32** (`feature_vector.py`): 행당 189-피처 dict → 단일 `array('f')` 기반
  `FeatureVector`(Mapping 완전 호환: get/[]/items/dict()/pickle). 행당 ~11KB→~800B,
  **약 7~10x 절감**(2.8M행 기준 ~31GB→2GB대). LabeledRow는 벡터 공유. None→NaN.
  float32 경계 1 ULP로 클리퍼 테스트 1건 허용오차 조정.
- 빌드 피크: MTF 중간구조 `get`→`pop`(소비 즉시 해제, 피크 −24% ≈ 2.3GB),
  MTF 조회 hoist(캔들당 26회→1회), `FeatureRow slots=True`.

---

## 4. 첫 실전 백테스트(2025 OOS) 결과 분석

- net −10.98% (gross +2.06%, 비용 −13.03%), 1,708 trades, WR 40.9%, PF 0.74
- outcome: **TIMEOUT 47.5% / SL 40.5% / TP 12.0%**
- 진단: (a) 모델 엣지 부재(F1 0.33~0.40) + threshold 0.32까지 하락 →
  저확신 진입 남발, (b) **라벨(0.30%/0.15%) vs 실행(ATR ~0.84%/0.42%) barrier 불일치**,
  (c) range 78~80% 지배. 인프라/라우팅 자체는 정상(분포 train↔backtest 일치, 직접반전 0)
- 사용자 방침: range 거래 유지, #3(barrier/horizon)부터, #4(모델 엣지)는 보류

---

## 5. 백테스트/학습 정합성 수정 (리뷰 5~7차 반영)

**Barrier/Horizon 정렬:**
- `backtest --exec-tp-pct/--exec-sl-pct`: 실행 barrier를 라벨과 동일 고정값으로 강제(ATR 무시)
- 파이프라인 `HORIZON`/`LABEL_TP_PCT`/`LABEL_SL_PCT` 노브 — train과 backtest에 동일 값 자동 전달
- 타임아웃(horizon) 확인: 기본 60분(라벨=백테스트 강제청산 동일)

**Threshold 선택의 근본 수정:**
- `_trading_pnl`: threshold 미만을 **반대 포지션(−1)이 아닌 no-trade(0)**로,
  비대칭 TP/SL + round-trip 비용 반영 → 약모델 선택 threshold 0.32 → **0.58**
- 파이프라인 기본 objective `precision_recall` → **`trading_pnl`**
- `--threshold-floor`(기본 파이프라인 0.45): learned/strategy에만 적용, 명시 override 제외
- tp/sl/cost가 `select_threshold`→`metrics`→`_trading_pnl` 체인 관통
  (`TrainingConfig.round_trip_cost` 신설) — TP/SL sweep 시 objective 자동 동기화.
  holdout metrics도 동일 geometry 사용

**기간 경계 정확화:**
- `--backtest-end` 신설(이전엔 로그만 있고 파일 끝까지 거래)
- date-only end는 **다음날 00:00 exclusive**(하루 전체 포함; 기존엔 1,439/1,440바 누락)
- end 도달 시 `break` + `last_in_window_candle`에서 OPEN_AT_END 마감
  (기존: `candles[-1]` = 파일 끝 → parquet이 2026까지 자라면 경계 파괴)
- routing diagnostics를 **backtest 윈도우로 slice**(기존: 2020~2025 전체 집계)

**분석 가능성·성능:**
- trade record 확장: `entry_regime`/`long_probability`/`short_probability`/
  `used_threshold`/`model_side`/`entry_probability` → regime×side 손익 귀속 가능
- summary에 `threshold_floor` + regime별 `effective_thresholds`(learned vs effective)
- `regime_routing_diagnostics`(counts/ratios/전환 by-type/direct_reversal/평균지속)를
  로그+JSON 저장
- feature 계산 1회 공유(compare↔run), rule detect_all도 1회
  (`apply_multi_feature_routing` 헬퍼 + precomputed diag)
- backtest CLI `--long/--short-threshold` override, backtest도 learned per-regime
  threshold 사용(live와 동일 우선순위, `_resolve_backtest_thresholds`)
- legacy 경로의 0.55/0.45 이중 hard gate 3곳 제거
- 학습 test-period 진단 평가가 rule detector로 라우팅(기존: user_regime=None으로 공집합)

---

## 6. 미해결 / 보류 (TODO_RULE_REGIME_REVIEW.md 참조)

- **Live warmup/backfill (실전 배포 전 필수)**: buffer 500(≈8h)로는 4h/24h 피처
  warmup 부족 → REST backfill(≥6,000~10,080봉) + `max_candles` 상향 필요
- **#4 모델 엣지**: F1 0.33~0.40이 본질 병목. regime 정보의 피처화(연속 score/F18
  재도입), 라벨·피처·목표 재설계 — 정렬된 백테스트 결과 보고 결정
- 전환 구간 성능 분석(안정/전환직후 구간별 PnL), warmup drop 로그, rule 임계값
  실데이터 튜닝(전환 통계 기반)

## 7. 다음 실행

```powershell
.\run_full_pipeline.ps1   # 기본: rule 모드 + 보수 프리셋 + trading_pnl + floor 0.45
                          # + barrier 정렬 + end 경계. feature 캐시 별도 삭제 불필요
                          # (candles parquet은 재사용, feature는 매회 재계산)
```

결과에서 볼 것: `effective_thresholds`(learned vs floor), `trade_count`(대폭 감소
예상), net vs gross, TP/SL/TIMEOUT 비율, trade별 `entry_regime`/`entry_probability`
귀속, `regime_routing_diagnostics`(2025 전용).
