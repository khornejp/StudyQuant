# K45 funding-rate adversarial review

| claim | verdict | basis |
| --- | --- | --- |
| A | SUPPORTED | R2-14(T)=archive(T-8h), premium formula(T)=archive(T) |
| B | REFUTED | 전략 계열 목록은 맞지만 R2-19도 R2-14 source를 소비; 일부 gate-direction은 archive가 아니라 funding 미반영 |
| C | REFUTED | R2-15 CatBoost y=R2-14 net_bps>0; 나머지 조사 모델 타깃은 가격 경로 |
| D | REFUTED | E1 예시는 맞지만 6칸 net 부호 변화, DEV 최대 \|Δ\| 703.9bps |

- 범위: 로컬 데이터만. 다운로드 0. 원본 코드 수정 0. 재학습 0.
- 데이터 cutoff: 2026-06-30 23:59 UTC.
- 동결 가설: `R2-14는 T에 T-8h 정산 요율을 적용한다`; 반대 가설부터 검사.
- OOS 결과: 회계 요율만 교체한 813칸 DEV/HOLD_B 재계산. 신호·거래·모델 고정.

## 1. 아카이브 시각 규약 — A SUPPORTED

- 실제 열: `calc_time|funding_interval_hours|last_funding_rate`. 78 ZIP 모두 동일.
- 행: 7119. `funding_interval_hours!=8`: 0.
- `calc_time` 분 경계 비정수 ms 행: 3190; 최대 offset 47 ms.
- 공식 근사: 1m premium close의 480분 선형가중 TWAP + clamp(0.01%-TWAP, ±0.05%), 최종 ±0.30% cap. Binance 정산은 5초 관측이라 exact match는 기대하지 않는다.

### 프리미엄 공식 결과

| comparison | n | pearson | spearman | mae_bps | median_ae_bps | p95_ae_bps | match_1e9_rate | within_0_01bps_rate | within_0_05bps_rate | within_0_10bps_rate | sign_match_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| archive_T_minus_8h | 7118 | 0.79491388 | 0.80873880 | 0.57285627 | 0.23154777 | 2.37109783 | 0.26425962 | 0.27507727 | 0.31834785 | 0.37046923 | 0.85951110 |
| archive_T | 7118 | 0.99683330 | 0.98034785 | 0.04525121 | 0.01267814 | 0.14339818 | 0.34054510 | 0.47400955 | 0.76144985 | 0.90207924 | 0.98468671 |
| archive_T_plus_8h | 7117 | 0.80573913 | 0.81092729 | 0.56130855 | 0.23389789 | 2.27044176 | 0.26513981 | 0.27638050 | 0.32190530 | 0.37515807 | 0.86398764 |

`archive_T`가 상관·MAE 모두 최상이다. 따라서 `calc_time=T`는 `(T-8h,T]`에서 계산되어 T에 정산된 요율이다.

### R2-14 event와 archive shift

| comparison | n | match_count | match_rate | pearson | spearman | mae_bps | max_ae_bps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| archive_T_minus_8h | 7118 | 7118 | 1.00000000 | 1.00000000 | 1.00000000 | 0.00000003 | 0.00000102 |
| archive_T | 7118 | 1881 | 0.26425962 | 0.79893641 | 0.81949518 | 0.56511942 | 28.39270007 |
| archive_T_plus_8h | 7117 | 1758 | 0.24701419 | 0.73919778 | 0.76807597 | 0.67523988 | 28.48509993 |

근거 코드: `out/run_k45_classic_rules_r2_14.py:204-221`은 T 직전 행을 shift하고, `btcusdt_quant/funding_source.py:290-337`은 registry current/next를 마지막 정산 완료 요율로 정의한다.

### registry 전수

| rows | funding_nonnull | current_vs_last_settled_matches | current_vs_last_settled_match_rate | next_named_vs_last_settled_matches | next_named_vs_last_settled_match_rate | next_named_equals_current_count | current_equals_strict_future_count | strict_future_comparable | current_equals_strict_future_rate | past_future_same_count | future_differs_count | current_equals_future_when_future_differs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3417120 | 3417120 | 3417120 | 1.00000000 | 3417120 | 1.00000000 | 3417120 | 902885 | 3416641 | 0.26426101 | 902885 | 2513756 | 0 |

미래 요율이 과거와 실제로 다른 2513756분 중 registry current가 미래와 일치한 분: 0.
미래 일치 사례는 다음 정산 요율이 직전 정산 요율과 같은 반복값이다. 미래정보 증거가 아니다.

| registry_minute_relative_T | comparison | n | match_count | match_rate |
| --- | --- | --- | --- | --- |
| -1 | archive_T_minus_8h | 7118 | 7118 | 1.00000000 |
| -1 | archive_T | 7118 | 1881 | 0.26425962 |
| -1 | archive_T_plus_8h | 7117 | 1758 | 0.24701419 |
| 0 | archive_T_minus_8h | 7118 | 4276 | 0.60073054 |
| 0 | archive_T | 7119 | 4724 | 0.66357634 |
| 0 | archive_T_plus_8h | 7118 | 1831 | 0.25723518 |
| 1 | archive_T_minus_8h | 7118 | 1881 | 0.26425962 |
| 1 | archive_T | 7119 | 7119 | 1.00000000 |
| 1 | archive_T_plus_8h | 7118 | 1881 | 0.26425962 |

| registry_change_count | offset_0_minutes | offset_1_minutes | other_offset_minutes |
| --- | --- | --- | --- |
| 5237 | 2842 | 2395 | 0 |

| minutes_after_scheduled_T | change_count |
| --- | --- |
| 0 | 2842 |
| 1 | 2395 |

## 2. 실험별 손익 펀딩 경로 — B REFUTED

| file | pnl_funding_source | affected_by_r214_shift | import_chain | evidence | note |
| --- | --- | --- | --- | --- | --- |
| out/k45_gate_direction.py | none | False | out.run_patchtst_k45_flow_inference | out/k45_gate_direction.py:16-27 | price label helpers; no PnL funding |
| out/k45_ledger.py | caller | True | out.run_patchtst_k45_flow_inference.optimal_block_length -> out.run_patchtst_k45_flow_inference.stationary_bootstrap_errors | out/k45_ledger.py:13-39 | funding DataFrame supplied by caller |
| out/k45_trend_side.py | none | False |  | out/k45_trend_side.py:32-40 | price return minus fixed cost |
| out/run_k45_classic_rules_r2_14.py | registry_prior_minute | True |  | out/run_k45_classic_rules_r2_14.py:204-257 | settlement_events then _funding_bps |
| out/run_k45_contrarian_robust_r2_17.py | registry_prior_minute | True | out.run_k45_classic_rules_r2_14 -> run_k45_classic_rules_r2_14 | out/run_k45_contrarian_robust_r2_17.py:144-187 | r214.load_inputs -> r214.simulate |
| out/run_k45_gate_direction_backtest.py | none | False | out.k45_trend_side -> out.run_patchtst_k45_flow_inference -> out.run_k45_gate_direction_dataset.sha256 -> out.run_k45_gate_direction_dataset.write_json -> out.run_k45_gate_direction_dataset.write_parquet | out/run_k45_gate_direction_backtest.py:35-44 | price PnL through k45_trend_side |
| out/run_k45_gate_direction_dataset.py | none | False | out.k45_gate_direction -> out.k45_trend_side -> out.k45_defect_audit_20260930.run_audit | out/run_k45_gate_direction_dataset.py:1-40 | dataset construction; no realized funding PnL |
| out/run_k45_gate_direction_precheck.py | none | False | out.k45_gate_direction | out/run_k45_gate_direction_precheck.py:1-40 | precheck only |
| out/run_k45_gate_direction_quality.py | none | False | out.k45_gate_direction -> out.run_k45_gate_direction_dataset.sha256 -> out.run_k45_gate_direction_dataset.write_json -> out.run_k45_gate_direction_dataset.write_parquet | out/run_k45_gate_direction_quality.py:1-40 | quality audit only |
| out/run_k45_gate_direction_r2.py | none | False | out.k45_gate_direction -> out.k45_trend_side -> out.run_k45_gate_direction_walkforward -> out.run_patchtst_k45_flow_inference -> out.k45_defect_audit_20260930.run_audit | out/run_k45_gate_direction_r2.py:281-325 | gross minus 4 bps |
| out/run_k45_gate_direction_r2_10.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_8 -> out.run_k45_gate_direction_walkforward | out/run_k45_gate_direction_r2_10.py:459-459 | r26.funding_events |
| out/run_k45_gate_direction_r2_11.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_8 -> out.run_k45_gate_direction_r2_9 -> out.run_k45_gate_direction_r2_10 -> out.run_k45_gate_direction_walkforward -> out.k45_defect_audit_20260930.run_audit | out/run_k45_gate_direction_r2_11.py:929-929 | r26.funding_events |
| out/run_k45_gate_direction_r2_6.py | archive_direct | False | btcusdt_quant.funding_source.load_funding_dir -> out.k45_trend_side -> out.run_k45_gate_direction_r2 | out/run_k45_gate_direction_r2_6.py:128-135 | load_funding_dir |
| out/run_k45_gate_direction_r2_7.py | archive_r26 | False | out.k45_trend_side -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 | out/run_k45_gate_direction_r2_7.py:399-399 | r26.funding_events |
| out/run_k45_gate_direction_r2_8.py | archive_r26 | False | out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 | out/run_k45_gate_direction_r2_8.py:147-147 | r26.funding_events via load_inputs |
| out/run_k45_gate_direction_r2_9.py | archive_r26 | False | out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_7 -> out.run_k45_gate_direction_r2_8 | out/run_k45_gate_direction_r2_9.py:184-184 | r26.funding_events |
| out/run_k45_gate_direction_r2_9b.py | archive_r26 | False | out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_9 -> out.run_k45_gate_direction_r2_11 | out/run_k45_gate_direction_r2_9b.py:256-256 | r26.funding_events |
| out/run_k45_gate_direction_walkforward.py | none | False | out.k45_gate_direction -> out.k45_defect_audit_20260930.run_audit | out/run_k45_gate_direction_walkforward.py:1-50 | training split helper; no PnL funding |
| out/run_k45_holdout_a_2026q3.py | none | False | out.run_patchtst_k45_causal_admission_ordering | out/run_k45_holdout_a_2026q3.py:486-486 | manifest states funding input unnecessary |
| out/run_k45_meta_label_r2_15.py | registry_prior_minute | True | out.run_k45_classic_rules_r2_14 | out/run_k45_meta_label_r2_15.py:214-233 | r214.load_inputs -> make_trades |
| out/run_k45_mtf_entry_r2_12.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.k45_defect_audit_20260930.run_audit | out/run_k45_mtf_entry_r2_12.py:379-381,499 | r26.funding_events |
| out/run_k45_mtf_persistence_r2_13.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_mtf_entry_r2_12 -> out.run_patchtst_k45_flow_inference -> out.k45_defect_audit_20260930.run_audit | out/run_k45_mtf_persistence_r2_13.py:390-392,588 | r26.funding_events |
| out/run_k45_mtf_tail_r2_20.py | archive_r26 | False | out.run_k45_classic_rules_r2_14 -> out.run_k45_mtf_entry_r2_12 -> out.run_patchtst_k45_flow_inference.optimal_block_length -> out.run_patchtst_k45_flow_inference.stationary_bootstrap_errors | out/run_k45_mtf_tail_r2_20.py:154-161 | r212.r26.funding_events |
| out/run_k45_patchtst_updown_r2_21.py | archive_direct | False | btcusdt_quant.funding_source.load_funding_dir | out/run_k45_patchtst_updown_r2_21.py:442-447,511-519 | load_funding_dir |
| out/run_k45_risk_stop_r2_18.py | registry_prior_minute | True | out.run_k45_classic_rules_r2_14 -> out.run_k45_gate_direction_r2_7 -> out.run_k45_mtf_entry_r2_12 | out/run_k45_risk_stop_r2_18.py:164-170,749-795 | final simulation uses r214 funding; source reproduction also reads archive |
| out/run_k45_train_window_r2_16.py | archive_r26 | False | out.k45_gate_direction -> out.run_k45_gate_direction_r2 -> out.run_k45_gate_direction_r2_6 -> out.run_k45_gate_direction_r2_8 -> out.run_k45_gate_direction_r2_9 -> out.run_k45_gate_direction_r2_10 -> out.run_k45_gate_direction_walkforward -> out.run_k45_mtf_entry_r2_12 -> out.k45_defect_audit_20260930.run_audit | out/run_k45_train_window_r2_16.py:512-512,567-567 | r26.funding_events |
| out/run_k45_trend_side.py | none | False | out.k45_trend_side -> out.run_patchtst_k45_flow_inference | out/run_k45_trend_side.py:29-30 | price PnL through k45_trend_side |
| out/run_k45_trend_side_tp.py | none | False | out.k45_trend_side -> out.run_k45_trend_side -> out.run_patchtst_k45_flow_inference | out/run_k45_trend_side_tp.py:57-60 | inherits no-funding trend-side PnL |
| out/run_k45_validation_r2_19.py | mixed_r214_and_archive | True | out.run_k45_classic_rules_r2_14 -> out.k45_ledger | out/run_k45_validation_r2_19.py:592-628 | loads r214 and archive comparison sets |

R2-14 오류를 전략 손익에 직접 전파하는 기본 계열은 R2-14/15/17/18이다. 그러나 literal 주장에는 R2-19가 누락됐다. 또 초기 gate-direction/R2는 archive를 쓰는 것이 아니라 정산 펀딩을 아예 빼고 4bps만 쓴다.

## 3. 학습 라벨·미래정보 — C REFUTED

| experiment | model | label | settlement_funding_in_label | evidence |
| --- | --- | --- | --- | --- |
| gate-direction R2 | CatBoost | forward price return > 4bps | False | out/run_k45_gate_direction_r2.py:99-102,281-292 |
| R2-10/R2-11 | CatBoost | directional price return/class | False | out/run_k45_gate_direction_r2_10.py:179-192; out/run_k45_gate_direction_r2_11.py:278-302 |
| R2-12 | CatBoost | directional price return > 4bps | False | out/run_k45_mtf_entry_r2_12.py:289-298; funding attached 379-381 |
| R2-13 | CatBoost | price-path capture/duration/MFE | False | out/run_k45_mtf_persistence_r2_13.py:101-180,224-230; funding attached 390-392 |
| R2-15 | CatBoost/logistic meta | R2-14 net_bps > 0 | True | out/run_k45_meta_label_r2_15.py:214-233,367-419 |
| R2-16 | CatBoost | price return direction | False | out/run_k45_train_window_r2_16.py:167-172,237-245; funding attached 512 |
| R2-21 | PatchTST | up/down/range price excursion | False | out/run_k45_patchtst_updown_r2_21.py:122-158,272-274; funding attached 511-519 |

- R2-15는 예외가 아니라 실제 CatBoost 학습 경로다: `run_k45_meta_label_r2_15.py:214-233,367-419`.
- R2-13 라벨은 가격 path capture/duration/MFE(`:101-180`); 펀딩은 거래 평가 때 `:390-392`.
- R2-16 CatBoost 라벨은 가격 방향(`:167-172,237-245`); archive 펀딩은 평가 때 `:512`.
- R2-20 손익은 `r212.r26.funding_events()` archive(`run_k45_mtf_tail_r2_20.py:154-161`).
- R2-21 PatchTST 타깃은 up/down/range 가격 excursion(`:122-158`); archive 펀딩은 `:511-519`.
- registry `funding_rate`와 `next_funding_rate`는 둘 다 last-settled다. 이름 `next_`는 예상 요율이 아니다.

## 4. R2-14 813칸 재계산 — D REFUTED

| segment | cells | mean | std | min | q05 | q25 | median | q75 | q95 | max | abs_mean | abs_max | net_sign_changed_cells | funding_sign_changed_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEV | 813 | -60.52484745 | 173.92901605 | -703.91118656 | -360.27123803 | -128.54390298 | -19.17793032 | 11.59558020 | 180.81352986 | 607.22520022 | 117.04489875 | 703.91118656 | 4 | 13 |
| HOLD_B | 813 | -1.11572878 | 7.78903487 | -77.50250008 | -7.27380010 | -1.86570009 | -0.06270000 | 1.12780005 | 4.23085990 | 36.21389988 | 3.15444390 | 77.50250008 | 2 | 40 |

### net 부호 변화 6칸

| cell_id | segment | old_net_bps | archive_net_bps | net_difference_bps |
| --- | --- | --- | --- | --- |
| A3\|1h\|168\|trail2\|L | HOLD_B | 0.66860761 | -0.04489241 | -0.71350002 |
| A4\|1h\|10/2\|trail2\|LS | DEV | 461.64413610 | -165.23076265 | -626.87489875 |
| A4\|1h\|10/4\|trail2\|LS | DEV | 317.06184675 | -20.70225065 | -337.76409740 |
| A5\|1h\|25\|signal\|LS | DEV | 291.59969493 | -197.05190038 | -488.65159532 |
| A5\|1h\|25\|trail2\|LS | DEV | 340.02797220 | -168.72212128 | -508.75009348 |
| F1\|1h\|10/24\|signal\|LS | HOLD_B | 5.05553545 | -23.01276460 | -28.06830005 |

### E1 z3

| segment | n | old_funding_bps | archive_funding_bps | funding_difference_bps | old_net_bps | archive_net_bps | net_difference_bps | net_sign_changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEV | 375 | -1238.06279139 | -1401.83920000 | -163.77640861 | 14636.43366430 | 14472.65725569 | -163.77640861 | False |
| HOLD_B | 30 | -2.48790005 | -3.12050000 | -0.63259995 | 1447.34304576 | 1446.71044581 | -0.63259995 | False |

### F1/G2

| family | segment | cells | trades | old_funding_bps | archive_funding_bps | funding_difference_bps | mean_cell_difference_bps | max_abs_cell_difference_bps | net_sign_changed_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | DEV | 12 | 12600 | 22682.89578929 | 18113.03030000 | -4569.86548929 | -380.82212411 | 703.91118656 | 0 |
| F1 | HOLD_B | 12 | 678 | 649.35849924 | 443.58740000 | -205.77109924 | -17.14759160 | 34.35899992 | 1 |
| G2 | DEV | 24 | 96464 | 61643.82519419 | 56495.99840000 | -5147.82679419 | -214.49278309 | 643.47834927 | 0 |
| G2 | HOLD_B | 24 | 8680 | 1690.51360066 | 1070.49360000 | -620.02000066 | -25.83416669 | 77.50250008 | 0 |

칸별 전체 값: `r214_cell_funding_impact.parquet`. 신호·진입·청산은 기존 R2-14 함수와 기존 registry event clock으로 고정하고, 거래별 정산 손익만 archive T 요율로 교체했다.

## 5. 추가 결함·해석

1. `next_funding_rate`는 이름과 달리 last-settled 복제값이다(`btcusdt_quant/funding_source.py:290-337`). G2는 미래 예상 요율 전략이 아니라 8시간 이상 지연된 요율 신호다. 누수는 아니지만 의미가 다르다.
2. R2-15 영향은 label만이 아니다. target 선택도 R2-14 `all_cells.parquet`의 net/Sharpe를 읽는다(`run_k45_meta_label_r2_15.py:138-181,790-803`). 요율 교정 시 선택 집합도 바뀔 수 있다. 이번 요청은 재학습 금지라 재선택하지 않았다.
3. archive raw `calc_time` 중 3190행이 분 경계 뒤 1ms 이상이다. R2-6 loader는 ms를 보존(`btcusdt_quant/funding_source.py:132-151,255-279`)하지만 R2-19는 분으로 floor(`run_k45_validation_r2_19.py:48-65`). `exit_time==T` 거래 포함 여부가 경로별로 달라질 수 있다. 거래 체결 시각 정의 없이는 UNCERTAIN.
4. R2-14 첫 2020-01-01 00:00 archive event는 직전 registry 분이 없어 누락된다(7118 vs 7119). DEV 시작 전이라 이번 DEV/HOLD_B 합에는 영향 0.
5. 1m premium 검산은 5초 원자료가 아니므로 exact equality가 아니라 shift 식별용이다. 낮은 MAE와 상관 최대가 시각 규약 판정 근거다.

## 산출물

- `claim_verdicts.parquet`, `archive_schema.parquet`, `archive_time_properties.parquet`
- `premium_formula_alignment.parquet`, `r214_archive_shift.parquet`
- `registry_future_summary.parquet`, `registry_future_by_lead.parquet`, `registry_event_alignment.parquet`
- `registry_transition_summary.parquet`, `registry_transition_offsets.parquet`
- `experiment_funding_paths.parquet`, `model_label_paths.parquet`
- `r214_cell_funding_impact.parquet`, `r214_impact_distribution.parquet`, `r214_f1_g2_summary.parquet`
- 최종화 실행 시간: 6.9s. 813칸 계산은 선행 완료 parquet에서 재개.
