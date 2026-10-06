# K45 펀딩 오류 후속 계획 적대적 검토

| item | verdict | basis |
| --- | --- | --- |
| 1 | PARTIAL | central error holds; 100% is minute-floor/tolerance result, formula exact-match 34.05% |
| 2 | PARTIAL | 6 candidates include >1% changes; family proxy/exact changes=1/1; R2-19 omitted |
| 3 | DISAGREE | direct repricing sign changes=4; memory 0.1156 not reproduced |
| 4 | DISAGREE | boundary rule is sign-dependent; raw-ms and floor differ |
| 5 | DISAGREE | R2-15 fit audits using next feature=1197; G2 pre signal age 7.0-7.5h |
| 6 | PARTIAL | self-critique valid but misses boundary sign, initial sign flip, G2 long selection, duplicate feature |

## 1. 오류 판정

PARTIAL. 중심 결론은 유지된다. 다만 표현은 과장됐다.

- 공식 근사식 대 archive T: Pearson 0.99683330, MAE 0.04525121 bps, 1e-9 exact 0.34054510.
- R2-14 대 archive T-8h: 7,118/7,118 일치. 단, 분 floor와 1e-9 허용 결과다. 최대 오차 0.00000102 bps.
- raw `calc_time` 비정각 3,190/7,119, 최대 47 ms. raw timestamp 기준 100% 시각 일치는 아니다.
- registry `funding_rate`와 `next_funding_rate`는 last-settled와 3,417,120/3,417,120 일치. 미래값이 실제로 달랐던 2,513,756분 중 미래값 일치 0.
- 근거: `out/k45_funding_review_20261004/premium_formula_alignment.parquet`, `r214_archive_shift.parquet`, `archive_time_properties.parquet`, `registry_future_summary.parquet`; `btcusdt_quant/funding_source.py:290-337`.

## 2. 재실행 범위와 후보 영향

### 2a. 지정 6칸

| cell_id | segment | n | net_difference_bps | difference_per_trade_bps | difference_pct_abs_old_net | old_net_bps | archive_net_bps | net_sign_changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1\|1h\|3\|signal\|L | DEV | 375 | -163.77640861 | -0.43673709 | -1.11896390 | 14636.43366430 | 14472.65725569 | False |
| E1\|1h\|3\|signal\|L | HOLD_B | 30 | -0.63259995 | -0.02108666 | -0.04370767 | 1447.34304576 | 1446.71044581 | False |
| E1\|1h\|2\|signal\|L | DEV | 583 | -200.35151382 | -0.34365611 | -1.29106107 | 15518.36075588 | 15318.00924206 | False |
| E1\|1h\|2\|signal\|L | HOLD_B | 49 | -0.23930006 | -0.00488367 | -0.01247779 | 1917.80804788 | 1917.56874782 | False |
| F3\|1h\|10/24\|signal\|LS | DEV | 873 | -87.71831062 | -0.10047916 | -0.24790228 | 35384.22965313 | 35296.51134251 | False |
| F3\|1h\|10/24\|signal\|LS | HOLD_B | 76 | -0.60010016 | -0.00789605 | -0.05075295 | 1182.39459428 | 1181.79449412 | False |
| F3\|1h\|5/24\|signal\|LS | DEV | 612 | -92.31741018 | -0.15084544 | -0.32540154 | 28370.30485868 | 28277.98744850 | False |
| F3\|1h\|5/24\|signal\|LS | HOLD_B | 43 | 1.66009987 | 0.03860697 | 0.16008780 | 1036.99339277 | 1038.65349264 | False |
| A3\|4h\|720\|signal\|LS | DEV | 339 | -39.18471045 | -0.11558912 | -0.12515326 | 31309.38061028 | 31270.19589983 | False |
| A3\|4h\|720\|signal\|LS | HOLD_B | 45 | -1.63580030 | -0.03635112 | -0.05352859 | 3055.93744477 | 3054.30164447 | False |
| F4\|1h\|5/4\|signal\|L | DEV | 1812 | 166.31399388 | 0.09178476 | 2.06439935 | 8056.28979850 | 8222.60379239 | False |
| F4\|1h\|5/4\|signal\|L | HOLD_B | 186 | 13.59439981 | 0.07308817 | 1.21119393 | 1122.39662435 | 1135.99102416 | False |

`difference_pct_abs_old_net = 100 * 차이 / abs(old net)`. F4 DEV +2.064399%, HOLD_B +1.211194%. E1 z2 DEV -1.291061%, z3 DEV -1.118964%. 12행 중 1% 초과 4행, 0.1% 미만 4행, 0.1~1% 4행.

### 2b. 계열 대표

| family | old_cell_id | old_daily_sharpe | proxy_cell_id | proxy_archive_sharpe | exact_cell_id | exact_archive_sharpe | proxy_changed | exact_changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | A1\|4h\|50/200\|trail2\|L | 0.94427472 | A1\|4h\|50/200\|trail2\|L | 0.94367766 | A1\|4h\|50/200\|trail2\|L | 0.94393375 | False | False |
| A2 | A2\|4h\|55/10\|signal\|L | 0.90694420 | A2\|4h\|55/10\|signal\|L | 0.90505850 | A2\|4h\|55/10\|signal\|L | 0.90589118 | False | False |
| A3 | A3\|4h\|720\|signal\|LS | 0.80035349 | A3\|4h\|720\|signal\|LS | 0.79935182 | A3\|4h\|720\|signal\|LS | 0.79964198 | False | False |
| A4 | A4\|4h\|10/3\|signal\|L | 0.60204447 | A4\|4h\|10/3\|signal\|L | 0.59989241 | A4\|4h\|10/3\|signal\|L | 0.60044277 | False | False |
| A5 | A5\|4h\|25\|trail2\|L | 0.78304764 | A5\|4h\|25\|trail2\|L | 0.78002389 | A5\|4h\|25\|trail2\|L | 0.78115823 | False | False |
| A6 | A6\|1h\|40/60\|signal\|L | 0.36339307 | A6\|1h\|40/60\|signal\|L | 0.36431538 | A6\|1h\|40/60\|signal\|L | 0.36418839 | False | False |
| B1 | B1\|15m\|2.5/12\|signal\|L | -0.27537316 | B1\|15m\|2.5/12\|signal\|L | -0.27752706 | B1\|15m\|2.5/12\|signal\|L | -0.27750740 | False | False |
| B2 | B2\|1h\|20/80/4\|signal\|L | 0.67064712 | B2\|1h\|20/80/4\|signal\|L | 0.67910185 | B2\|1h\|20/80/4\|signal\|L | 0.67640083 | False | False |
| B3 | B3\|1h\|3\|signal\|L | 0.02830351 | B3\|1h\|3\|signal\|L | 0.04007746 | B3\|1h\|3\|signal\|L | 0.04008697 | False | False |
| B4 | B4\|1h\|20/5\|signal\|L | -0.43217380 | B4\|1h\|20/5\|signal\|L | -0.42176555 | B4\|1h\|20/5\|signal\|L | -0.42213975 | False | False |
| C1 | C1\|1h\|20/12\|limit\|L | 0.83760607 | C1\|1h\|20/12\|limit\|L | 0.83255342 | C1\|1h\|20/12\|limit\|L | 0.83342027 | False | False |
| C2 | C2\|4h\|20\|signal\|L | 0.38520187 | C2\|4h\|20\|signal\|L | 0.38695856 | C2\|4h\|20\|signal\|L | 0.38700087 | False | False |
| C3 | C3\|4h\|inside\|signal\|L | 0.87527881 | C3\|4h\|inside\|signal\|L | 0.87358651 | C3\|4h\|inside\|signal\|L | 0.87447138 | False | False |
| C4 | C4\|4h\|pin/trend4h\|signal\|S | 0.27638284 | C4\|4h\|pin/trend4h\|signal\|S | 0.27779400 | C4\|4h\|pin/trend4h\|signal\|S | 0.27795851 | False | False |
| C5 | C5\|4h\|3\|signal\|L | 0.27078014 | C5\|4h\|3\|signal\|L | 0.26953051 | C5\|4h\|3\|signal\|L | 0.26978303 | False | False |
| D1 | D1\|1h\|20\|signal\|L | -0.14229020 | D1\|4h\|20\|signal\|S | -0.14659601 | D1\|4h\|20\|signal\|S | -0.14674368 | True | True |
| D2 | D2\|4h\|NR4\|signal\|L | 0.55303006 | D2\|4h\|NR4\|signal\|L | 0.54871097 | D2\|4h\|NR4\|signal\|L | 0.54939252 | False | False |
| E1 | E1\|1h\|3\|signal\|L | 1.14823991 | E1\|1h\|3\|signal\|L | 1.13539152 | E1\|1h\|3\|signal\|L | 1.13769962 | False | False |
| E2 | E2\|1h\|4h/follow/5\|signal\|L | 0.44106873 | E2\|1h\|4h/follow/5\|signal\|L | 0.43046447 | E2\|1h\|4h/follow/5\|signal\|L | 0.43048965 | False | False |
| E3 | E3\|1h\|revert\|signal\|L | 0.13739256 | E3\|1h\|revert\|signal\|L | 0.14622040 | E3\|1h\|revert\|signal\|L | 0.14610064 | False | False |
| F1 | F1\|1h\|5/24\|signal\|LS | 0.74949435 | F1\|1h\|5/24\|signal\|LS | 0.72627385 | F1\|1h\|5/24\|signal\|LS | 0.72708712 | False | False |
| F2 | F2\|4h\|--/fade/24\|signal\|L | 0.30520342 | F2\|4h\|--/fade/24\|signal\|L | 0.30972449 | F2\|4h\|--/fade/24\|signal\|L | 0.31017044 | False | False |
| F3 | F3\|1h\|10/24\|signal\|LS | 1.48559729 | F3\|1h\|10/24\|signal\|LS | 1.48191446 | F3\|1h\|10/24\|signal\|LS | 1.48365989 | False | False |
| F4 | F4\|1h\|5/4\|signal\|L | 0.59888866 | F4\|1h\|5/4\|signal\|L | 0.61125211 | F4\|1h\|5/4\|signal\|L | 0.61097858 | False | False |
| G1 | G1\|1m\|us/60\|signal\|L | 0.64702321 | G1\|1m\|us/60\|signal\|L | 0.65156700 | G1\|1m\|us/60\|signal\|L | 0.65239166 | False | False |
| G2 | G2\|1m\|before/60/60\|signal\|L | 0.79149743 | G2\|1m\|before/60/60\|signal\|L | 0.74563965 | G2\|1m\|before/60/60\|signal\|L | 0.74517534 | False | False |
| G3 | G3\|1d\|1\|signal\|L | 0.73909840 | G3\|1d\|1\|signal\|L | 0.74110921 | G3\|1d\|1\|signal\|L | 0.74194310 | False | False |
| H1 | H1\|4h\|55/20/squeeze10\|signal\|L | 0.14923506 | H1\|4h\|55/20/squeeze10\|signal\|L | 0.14944378 | H1\|4h\|55/20/squeeze10\|signal\|L | 0.14958840 | False | False |
| H2 | H2\|1h\|40/60/funding5\|signal\|L | 0.50621585 | H2\|1h\|40/60/funding5\|signal\|L | 0.50504098 | H2\|1h\|40/60/funding5\|signal\|L | 0.50507701 | False | False |
| H3 | H3\|1h\|4h20/60/C2\|signal\|S | -0.08734380 | H3\|1h\|4h20/60/C2\|signal\|S | -0.08510006 | H3\|1h\|4h20/60/C2\|signal\|S | -0.08513719 | False | False |

근사: `old Sharpe * archive net / old net`; 일별 표준편차 고정. 변경 1/30계열. 정확 재계산은 exit-day 일별 archive 손익 사용. 변경 1/30계열.

### 2c. 누락

R2-19 누락. R2-19는 6개 후보, R2-14 all_cells/cost/buy-hold, archive floor를 읽는다(`out/run_k45_validation_r2_19.py:27-36,48-65,592-631`). R2-14 대표 변경 시 후보 목록부터 바뀐다.

## 3. 초기 실험 직접 재계산

| experiment | table | cells | trade_instances | crossing_instances | crossing_rate_weighted | signed_difference_mean_bps_weighted | absolute_difference_mean_bps_weighted | sign_changed_cells | rank_changed_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gate_direction_1 | backtest | 8 | 30358 | 2928 | 0.09644904 | -0.03341098 | 0.10766595 | 1 | 0 |
| gate_direction_r2 | r21_arm | 12 | 40285 | 3403 | 0.08447313 | -0.04274554 | 0.10225749 | 0 | 2 |
| gate_direction_r2 | r21_decision | 4 | 16876 | 1672 | 0.09907561 | -0.01611581 | 0.11362491 | 0 | 0 |
| gate_direction_r2 | r22_books | 18 | 76219 | 7497 | 0.09836130 | -0.04080053 | 0.12164810 | 2 | 0 |
| gate_direction_r2 | r23_backtest | 8 | 37124 | 3573 | 0.09624502 | -0.05212651 | 0.11869375 | 0 | 0 |
| gate_direction_r2 | r24_tail | 160 | 84696 | 7850 | 0.09268442 | 0.01584908 | 0.13573816 | 1 | 0 |
| trend_side | 30d | 4 | 3036 | 279 | 0.09189723 | -0.08604246 | 0.14463752 | 0 | 0 |
| trend_side | 7d_report_only | 4 | 3047 | 289 | 0.09484739 | -0.05648569 | 0.14214358 | 0 | 0 |

원장 범위: gate-direction 1차 `book_trades.parquet`; R2는 prediction 원장으로 R2-1~R2-4 실행 규칙 재구성; trend-side는 30d/7d book 원장. raw archive ms, `entry < T <= exit` 적용.

메모리 9.30%/0.1156 bps와 동일하지 않다. gate-direction 1차 공식 8칸의 가중 통과율과 절대 차이는 위 표 값이다. HOLD_B margin=0.05는 +0.00567648 -> -0.00344394 bps로 부호 변경.

### 부호·순위 변경 칸

| experiment | table | cell_id | segment | n | crossing_rate | signed_difference_mean_bps | old_net_mean_bps | new_net_mean_bps | sign_changed | old_rank | new_rank | rank_changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gate_direction_1 | backtest | margin=0.05 | HOLD_B | 886 | 0.11738149 | -0.00912043 | 0.00567648 | -0.00344394 | True | 1.00000000 | 1.00000000 | False |
| gate_direction_r2 | r21_arm | LONG\|h=45 | DEV | 9217 | 0.09883910 | -0.10785094 | -2.46856452 | -2.57641546 | False | 2.00000000 | 1.00000000 | True |
| gate_direction_r2 | r21_arm | LONG\|h=60 | DEV | 8899 | 0.13911675 | -0.13502755 | -2.45886641 | -2.59389397 | False | 1.00000000 | 2.00000000 | True |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|ALL | DEV | 2967 | 0.08897877 | -0.06314456 | 0.05195392 | -0.01119063 | True | 1.00000000 | 1.00000000 | False |
| gate_direction_r2 | r22_books | MULTICLASS_0.20\|CAP3 | DEV | 2967 | 0.08897877 | -0.06314456 | 0.05195392 | -0.01119063 | True | 2.00000000 | 2.00000000 | False |
| gate_direction_r2 | r24_tail | MULTICLASS\|share=0.02\|HIGH\|SINGLE | DEV | 319 | 0.07523511 | -0.10562539 | 0.01412412 | -0.09150127 | True | 2.00000000 | 2.00000000 | False |

순위 정의: gate1=segment 내 margin; R2-1 arm=segment·arm 내 horizon; R2-2=segment·signal 내 book; R2-3=segment 내 variant·book; R2-4=segment·score·tail·book 내 share; trend-side=lookback·segment 내 arm.

## 4. 정산 경계

| scope | boundary | trade_instances | boundary_trade_n | boundary_nonzero_offset_n | boundary_cashflow_sum_bps | nonzero_offset_cashflow_sum_bps | floor_minus_raw_boundary_bps | floor_minus_raw_all_events_bps | floor_event_count_minus_raw |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R2-19 six candidate trade-instances | entry | 5522 | 1312 | 538 | -719.04160000 | -145.70680000 | 145.70680000 | 37.75900000 | -45 |
| R2-19 six candidate trade-instances | exit | 5522 | 1216 | 493 | -665.60210000 | -107.94780000 | -107.94780000 | 37.75900000 | -45 |
| R2-6 model metric trade-instances | entry | 745590 | 24372 | 10947 | -12600.40750000 | -4831.59840000 | 4831.59840000 | 1908.37720000 | -1527 |
| R2-6 model metric trade-instances | exit | 745590 | 20409 | 9420 | -6409.02020000 | -2923.22120000 | -2923.22120000 | 1908.37720000 | -1527 |

`entry < T <= exit`는 보수적이지 않다. cashflow=`-side*rate*10000`. 경계 cashflow가 양수면 포함은 낙관적이다. 음수면 포함은 보수적이다.

R2-6은 loader가 raw ms를 보존한다(`out/run_k45_gate_direction_r2_6.py:128-136`; `btcusdt_quant/funding_source.py:131-157,255-280`). R2-19는 분 floor다(`out/run_k45_validation_r2_19.py:48-65`). 동일 거래가 다른 event set을 받는다.

더 나은 규칙: scheduled T로 정규화하고 체결 규약을 고정한다. T 경계는 두 값도 병기한다. pessimistic은 경계 cashflow `min(cashflow,0)`만 포함. optimistic은 `max(cashflow,0)`만 포함. 1차 판정은 두 값 모두 같은 결론일 때만 확정한다.

## 5. `next_funding_rate` 전수

| consumer | direct | count | detail |
| --- | --- | --- | --- |
| R2-14 G2 before | True | 12 | 12 grid cells call attached.next_funding_rate for direction |
| R2-15 model feature | True | 1197 | fit audits using feature / all fit audits = 1197/2170 |
| R2-15 G2 ctx_signal_strength | True | 1030 | G2 candidate rows; selected G2 rules=1 |
| R2-18 G2 rule candidates | False | 4 | 4 before/pre/post rules call R2-14 _g2_signals |
| generic feature registry | True | 1 | metadata says announced next rate; loader supplies last-settled alias |
| gate-direction dataset | False | 28518 | f_next range=0.0..0.0; selected feature rows=0 |

G2 문서 정정만으로 부족하다. G2 before는 다음 정산 60/30분 전 진입한다. last-settled 요율 나이는 약 7.0/7.5시간이다. `8시간 이상`도 틀렸다(`out/run_k45_classic_rules_r2_14.py:188-189,690-700`).

R2-15는 registry feature로 직접 학습하고 G2 signal strength에도 쓴다(`out/run_k45_meta_label_r2_15.py:287-329,380-428,793-803`). R2-18도 4개 G2 before 규칙을 만든다(`out/run_k45_risk_stop_r2_18.py:231-250`). feature registry 설명은 `announced next funding rate`지만 loader는 last-settled 복제다(`btcusdt_quant/feature_registry.py:190`; `btcusdt_quant/funding_source.py:297-307`).

## 6. 추가 실수·위험

- G2 숏만 언급했다. R2-15 selected_rules에는 `G2|1m|before/60/60|signal|L` 1칸이 있다: DEV +5,553.163853 bps, Sharpe 0.791497, HOLD_B +680.485058 bps.
- R2-6 `funding_bps`는 비용 양수 후 차감이다(`run_k45_gate_direction_r2_6.py:90-98`). R2-14 `funding_bps`는 cashflow 후 가산이다(`run_k45_classic_rules_r2_14.py:250-268`). 재가격 코드에서 부호 혼용 위험.
- 초기 PnL 누락은 모델 라벨 오류가 아니어도 결과표 오류다. `문서만`은 재현 가능한 수치 교정이 아니다.
- R2-15 `funding_rate`와 `next_funding_rate`는 완전 중복이다. CatBoost에 중복 열을 넣으면 의미 없는 자유도와 중요도 분산이 생긴다. alias 제거 ablation 필요.
- archive raw ms를 실제 snapshot 시각으로 볼 근거가 로컬 자료에 없다. floor와 raw 중 하나를 진실로 단정하면 안 된다.

## Codex 권고안

| order | scope | action | reason |
| --- | --- | --- | --- |
| 1 | funding boundary policy + loader | FIX | sign-aware boundary and one clock |
| 2 | R2-14 | RERUN | PnL, Sharpe, representatives |
| 3 | R2-15 | RERUN | targets, labels, next-rate feature |
| 4 | R2-17 | RERUN | direct R2-14 funding import |
| 5 | R2-18 | RERUN | direct funding and G2 rules |
| 6 | R2-19 | RERUN | candidate list, corrected baseline, floor clock |
| 7 | gate-direction 1/R2/trend-side metrics | REPRICE | models fixed; PnL tables and one sign flip |
| 8 | R2-20/R2-21 | VERIFY ONLY | archive path already used; no R2-14 PnL dependency |

1. scheduled T, 체결 시각, sign-aware 경계 상·하한을 먼저 고정한다.
2. R2-14를 재실행한다. all_cells, family representatives, cost, buy-hold를 모두 갱신한다.
3. R2-15를 새 대표·새 label로 재학습한다. `next_funding_rate` alias 제거 ablation을 분리한다.
4. R2-17·18을 재실행한다. 그 뒤 R2-19 후보를 다시 고르고 검증한다.
5. 초기 gate-direction 1차·R2·trend-side는 모델 재학습 없이 원장 재가격과 결과표 재생성만 한다.
6. R2-20·21은 입력 SHA와 archive path를 확인한다. R2-14 PnL 의존이 없으면 재실행하지 않는다.

## 산출물

`candidate_impact.parquet`, `family_representative_changes.parquet`, `initial_cell_changes.parquet`, `initial_experiment_summary.parquet`, `boundary_impact.parquet`, `next_funding_usage.parquet`, `rerun_scope.parquet`, `verdicts.parquet`, `manifest.json`.
