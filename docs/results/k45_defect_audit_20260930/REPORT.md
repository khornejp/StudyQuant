# K=45 결함 공격 감사

감사 결과: 결함 1·2·3·6은 **CONFIRMED**, 결함 4는 **WRONG**, 결함 5는 **MISLEADING**이다. 이 감사는 사후 분석이다. 승자 선택이나 신규 판정이 아니다.

제약: `new_model_fits: 0`, `new_orders: 0`, `external_data_added: 0`, `live_orders: 0`. 데이터 cutoff는 2026-06-30 23:59 UTC다. 외부 데이터는 쓰지 않았다.

## 재현 경로

**올바르다.** `causal_candidates.parquet`에서 `arm == 'DOWN_BREAKOUT_LONG' & first_come_executed == True`를 적용하고, `1e4*(close[scheduled_exit_index]/close[entry_index]-1)-4`를 계산했다. `n=3,066`, 평균 `0.4550` bps, 합계 `1395.1` bps다. 저장된 `none_net_lin_bps`와 최대 차이는 `0.000e+00` bps다. 이 값은 frozen **linear close→close** endpoint 재현이다. maker 체결 재현은 아니다. 근거: `out/run_patchtst_k45_stop_grid_audit_fix.py:166-182`, `out/run_patchtst_k45_causal_admission_ordering.py:177-201`.

## 결함 1 — CONFIRMED

필터 D1: 위 재현 표본. 절사값은 D1에서 `none_net_lin_bps` 상·하위 k개를 직접 제거했다. 결과는 `trimmed_means.parquet`다.

- 중앙값 `5.9749`, 표준편차 `114.22`, 왜도 `-1.11`, 최솟값 `-1173.3`, 최댓값 `807.9` bps다.
- 상위 2건 제거 후 평균은 `-0.0171` bps다. 부호 반전이 맞다.
- iid bootstrap 20,000회, seed `20260930` 재현값은 95% CI `[-3.566, 4.409]`, `P(mean<=0)=0.407`다.
- iid는 최종 추론으로 부적절하다. 단일 book은 거래 겹침을 없애지만 시장 regime, fold gate, 시간 군집 의존은 남는다. 일별 influence stationary bootstrap의 원 평균 net CI는 `[-3.045, 4.163]`, one-sided p=`0.402`다. 결론은 같다.
- 양수 거래 비율은 `54.01%`, 양수 평균 `69.97`, 비양수 평균 `-81.18` bps다. “조금 자주 벌고 왼쪽 꼬리에서 더 크게 잃는다”가 더 정확하다. 단순한 고승률 전략은 아니다.

상위 2건은 같은 사건이 아니다. `top_trades.parquet`의 정확한 두 행:

- 2021-05-19 14:36 UTC 진입, net `807.931` bps. 그 UTC 일봉은 고가 `43615.93`, 저가 `28688.00`, 일중 범위 `3481.1` bps였다.
- 2021-02-23 12:34 UTC 진입, net `639.559` bps. 일중 범위 `1730.5` bps였다.

85일 떨어진 별도 급락·반등 구간이다. 로컬 OHLC만으로 사건 원인은 말할 수 없다. `LONG_ONLY +0.4550`을 강건한 “실행 가능한 최선”이라 부를 근거는 없다. 철회가 맞다.

## 결함 2 — CONFIRMED

사용자 기준선의 숨은 정확한 필터를 복원했다: `i = arange(min(causal.entry_index), max(causal.entry_index)-45)`. 이때 `n=2,879,368`, net `-3.7834` bps다. 같은 구간에서 `UTC minute % 15 == 0`이면 `n=191,957`, net `-3.7834` bps다. 둘은 4자리 반올림에서 같다. 전체 실제 fold TEST 구간과 `entry+45<test_end`를 쓰면 `n=2,848,545`, net `-3.7728` bps다. 사용자 기준선의 결론은 유지된다.

분해 필터:

- A: 사용자 전 분 기준선. gross `0.2166` bps.
- B: 세 prediction parquet을 합치고 `passes_q90 & signal_index+45<test_end`; signal close long; first-come 45m book. `n=12,217`, gross `0.9406` bps.
- C: D1 전략. gross `4.4550` bps.

따라서 gate 기여 B−A는 `0.7240` bps, trigger·방향·진입시점 기여 C−B는 `3.5145` bps, 합계는 `4.2385` bps다. gate 통과 후 15분 안에 절대 50 bps trigger가 전혀 없었던 stricter book은 `n=9,954`, gross `0.9946` bps다.

시간분포를 맞춰야 한다. 다만 맞추면 우위가 사라지지 않는다. `matched_baselines.parquet`에서 year×weekday×hour 기준 full 우위는 `4.8797` bps, top2 제거 후 `4.4127` bps다. year-month×weekday×hour에서도 각각 `9.3871`, `8.9664` bps다.

상위 2건 제거 후 사용자 random-long 대비 gross 우위는 `3.7663` bps다. 일별 PW stationary bootstrap은 95% CI `[0.240, 7.501]`, one-sided p=`0.0180`다. 고정 7·14·30·60·90·180일 block에서도 하한은 모두 양수다. equal-month 차이는 `4.5730` bps, CI `[1.262, 7.884]`, 양수 월 `42/66`다. stricter no-trigger book 대비 top2 제거 우위는 `2.9883` bps, PW CI `[-0.691, 6.760]`, p=`0.0576`다.

해석: 결함 1과 2는 같은 사실이 아니다. 상위 2건은 전체 gross excess에서 `0.4721` bps만 설명한다. 그러나 top2 제거 전략 net은 `-0.0171` bps다. gross signal excess가 통계적으로 양수여도 4 bps 비용을 넘지 못한다.

## 결함 3 — CONFIRMED

`first_crossing()`은 `close[t+tau]`를 본다(`out/run_patchtst_fixed_trigger_hold_sweep.py:137-153`). frozen entry도 같은 close다(`out/run_patchtst_k45_stop_grid_audit_fix.py:166-181`). 시점 위반이 맞다.

- close→close `0.4550` bps.
- 다음 open→다음 open `0.4587` bps. paired 차이 `0.0037`, SD `0.94`, t=`0.22`다.
- 진입만 다음 open, 기존 exit close는 `0.4585` bps. 차이 `0.0035`, t=`0.29`다.

고정 45분 latency 비교에는 양쪽 이동이 주 비교다. 원래 청산 시각을 고정하는 44분 노출 진단에는 진입만 이동이 맞다. 둘 다 수익 결론은 바꾸지 않는다.

maker-only 시점에는 다음 open 체결도 아니다. trigger close 뒤 그 가격에 resting limit를 내고 후속 bar가 touch해야 한다. `--maker-fill-window` 계약은 `btcusdt_quant/cli.py:1839`다. 5-bar local OHLC touch는 `3,041/3,066` (`99.18%`), 미touch `25`건이다. frozen ledger는 전부 trigger close 즉시 체결한다. 성과 차이는 작아 보여도 체결 시점 계약은 불일치한다. pending order가 book 점유를 바꾸므로 정확한 maker book PnL은 이 감사에서 새 backtest로 만들지 않았다.

## 결함 4 — WRONG

calendar 문자열만 보면 경계 간격은 0이다(`out/run_short_patchtst_3day_cadence_pilot.py:35-50`). 그러나 실제 학습 runner는 각 phase에서 `last=t+15`의 마지막 bar close가 phase end 이하일 때만 origin을 남긴다(`out/run_patchtst_excursion_range.py:205-216`; backward `out/run_patchtst_backward_k45_validation.py:70-82`; confirmation `out/run_patchtst_down_breakout_long_confirmation.py:89-100`). 라벨 정의는 `t+1..t+15`다(`out/run_patchtst_excursion_range.py:101-119`).

15분 grid에서 phase 끝 15분 전 raw origin 1개가 매 fold·phase마다 경계를 넘지만 이미 제거된다. 실제 admitted crossing은 TRAIN/STOP `0`건, STOP/TEST `0`건이다. 제거할 admitted origin이 없으므로 Spearman 변화와 q90 threshold 변화는 정확히 0이다. `boundary_audit.parquet`, `boundary_quality.parquet`에 fold별 근거가 있다.

명시적 post-boundary embargo는 0이다. 하지만 이 walk-forward에서 label overlap purge는 이미 작동한다. 추가 serial-correlation embargo의 재학습 효과는 zero-fit 제약 아래 측정 불가이며, 현재 수치에서 누수 결함으로 부를 근거는 없다.

## 결함 5 — MISLEADING

fold 606..666은 다른 runner다. 그러나 calendar 공식은 같은 3일 continuation이다(`out/run_patchtst_down_breakout_long_confirmation.py:74-86`). 차이는 edge 두 개다: fold 606은 시작 clip으로 TEST 2일과 1일 gap, fold 666은 종료 clip으로 TEST 2일이다. folds 607..665는 기존과 같은 180d/3d/3d다. `calendar_geometry.parquet`에 정확한 기하가 있다.

source 분리 LONG_ONLY net 평균은 다음과 같다. 정확한 필터는 D1에 `pilot_fold` 범위를 추가했다.

- 0..405: `n=2,021`, `-1.0247` bps.
- 406..605: `n=789`, `2.1407` bps.
- 606..666: `n=256`, `6.9416` bps.

따라서 source heterogeneity는 크다. 한 pooled 평균은 안정된 공통 효과로 읽으면 안 된다. 다만 chronology 전체의 거래가중 estimand로 합치는 것 자체가 통계 오류는 아니다.

F-1 45m coefficient를 같은 controls·month FE·PW로 source 분리하면:

- 0..405: beta `6.3524`, p=`0.128`.
- 406..605: beta `-2.4411`, p=`0.656`.
- 606..666: beta `8.4701`, p=`0.171`.

어느 source도 유의하지 않고 중간 source는 부호가 반대다. 기존 `FLOW_REGRESSION_GATE_FAILED`는 바뀌지 않는다.

## 결함 6 — CONFIRMED

필터 D6: `causal_candidates.parquet.groupby('pilot_fold').size()`의 nonempty folds. `n=592`, 평균 `15.3936`, 중앙값 `8`, 최대 `203`(fold 15)다. Kish 유효 fold 수는 `191.5`다. 상위 1% folds가 후보 `10.05%`, 상위 10%가 `44.27%`를 가진다.

HAC가 틀린 것은 아니다. `hac_mean()`은 fold별 score 합을 만들어 거래가중 평균의 SE를 계산한다(`out/run_patchtst_k45_stop_grid_audit_fix.py:413-450`). 하지만 fold 밀도 편중을 제거하지는 않는다.

- all-candidate 평균은 거래가중 `-0.9963` bps, nonempty-fold 동일가중 `1.0757` bps로 부호가 바뀐다.
- executed long은 `0.4550` 대 `2.8462` bps다.
- F-1 beta는 거래가중 `4.5155`에서 fold 동일가중 `1.3188` bps로 줄어든다.

월 block은 일부만 해결한다. 월 안 최대 fold share 중앙값은 `32.18%`, 최대는 `74.47%` (2022-11)다. fold 동일가중 시 66개월 중 `18`개월 coefficient 부호가 바뀐다. 양수 월 수는 `31`→`31`로 같아 최종 F-1 실패는 유지된다. E의 월 block은 calendar dependence를 다루지만 월내 fold 편중까지 없애지는 않는다.

## 최종 한 줄

**예, 명목상 남는다: top2 제거 후 random-long 대비 gross +3.7663 bps, 일별 stationary-bootstrap 95% CI [0.240, 7.501], one-sided p=0.0180. 다만 사후 감사라 확증 결과는 아니며, net은 -0.0171 bps다.**
