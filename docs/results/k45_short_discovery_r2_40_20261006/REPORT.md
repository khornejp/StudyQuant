# R2-40 숏 개선 설계·진단

결론: 새 백테스트는 하지 않았다. 현재 근거에서 바로 할 일은 **F3 숏 전용 관찰 장부를 주문 없는 shadow로 추가**하는 것이다. 첫 실행 후보는 P1(에피소드 상태기계), 다음은 P4(6h 무진전 청산)다. R2-39에서 실패한 추세·funding·premium·OI/taker 매도 gate와 router는 재제안하지 않는다.

- 생성: 2026-10-06 Asia/Seoul
- 로컬 원천: Binance USD-M BTCUSDT 1m OHLCV/체결수/taker buy, 5m metrics, funding, premium
- 선택 cutoff: DEV_COMMON `[2021-03-01, 2026-01-01)`; HOLD_B `[2026-01-01, 2026-07-01)` 확인만; HOLD_A 사후만
- 금지 확인: 다운로드 0, 주문 0, 인증 0, bookTicker/spot/m_* 0, 모의·라이브·docs 변경 0
- 이 문서의 경로·bucket 수치는 기술통계다. 청산 규칙의 성과 증거가 아니다.

## 1. 시험 이력 대장

| experiment | idea | direction | input_data | result | failure_reason |
|---|---|---|---|---|---|
| R2-1 | 팔별 binary CatBoost와 train payoff p* | 양방향 | OHLCV+기존 ML 피처 | 실패 | DEV 롱/숏 평균 net이 모두 음수 |
| R2-2 | SINGLE/CAP3/ALL 동시보유 방식 | 양방향 | R2-1·3분류 신호 | 미채택 | 용량 변경이 음의 방향 edge를 복구하지 못함 |
| R2-3 | fade 피처 제거·잔차화 | 양방향 | OHLCV ML 피처 | 미채택 | 점수 순서·net 변화가 안정적 개선으로 연결되지 않음 |
| R2-4/5 | 극단 점수 꼬리와 PW 대체 CI | 양방향 | CatBoost 점수·OHLCV | 진단 | 전체분포 꼬리는 미래정보; R2-7에서 인과 재검증 |
| R2-6 | 보유시간 5~240분 sweep | 롱/숏 분리 | 기존 예측·OHLCV·funding | 실패 | 숏은 길수록 악화; 대부분 비용 후 음수 |
| R2-7 | 인과 expanding/180d 극단 꼬리 | 롱/숏 분리 | 회귀·크기가중 점수 | 탐색 | 일부 양수지만 HOLD_B 표본 2~30건 및 부호 불안정 |
| R2-8 | 더 높은 확률 한 방향+팔별 보유 | 양방향 | 3분류·팔별 확률 | 실패 | PRIMARY HOLD_B 평균 -29.22bp |
| R2-9 | 모델 점수 꼬리 단일포지션 516칸 | 양방향 | REG/WGT/SIDE/RESIDUAL | 탐색 통과 | DEV 자동선택과 HOLD_B 반복열람; 교란 전 강건성 미확정 |
| R2-9b | 7개 seed/모델 교란 꼬리 강건성 | 양방향 | R2-9 예측 변형 | 후보 채택 | 28칸 규칙 통과, SIDE 180d q1 L120/S60 선택; 새 OOS 아님 |
| R2-10/10b | 보유시간 일치 라벨 재학습 | 양방향 | OHLCV ML 피처 | 실패 | 117 matched 중 DEV/HOLD_B 동시 양수 11칸 |
| R2-11 | fold STOP 구간 CatBoost 튜닝 | 양방향 | R2-10 피처 | 실패 | Spearman·단일장부 net 네 평균 delta 모두 음수 |
| R2-12 | 상위봉 신호+하위봉 limit 정밀진입 | 양방향 | OHLCV·MTF 모델 | 미채택 | 필터 없이 전 결과 보고; 일관된 우월 규칙 선정 안 됨 |
| R2-13 | capture/persistence 예측+고정/예측/trailing 청산 | 양방향 | 1h/4h OHLCV 모델 | 탐색 | 60 matched 중 양 구간 지지 9칸; 미채택 |
| R2-14 A | MA/ADX/모멘텀/RSI 추세 A1~A6, L/S/LS | 양방향 | OHLCV | 실패 | 계열 대표 HOLD_B 다수 음수; 전체 SPA 미통과 |
| R2-14 B | zscore·밴드·오실레이터 B1~B4, L/S/LS | 양방향 | OHLCV | 실패 | 813칸 전체 SPA zero p=0.144; 통과 계열 0 |
| R2-14 C | limit/pattern/inside/pin C1~C5, L/S/LS | 양방향 | OHLCV | 실패 | 일부 대표 양수이나 다중검정 가설 미통과 |
| R2-14 D | NR·range D1~D2, L/S/LS | 양방향 | OHLCV | 실패 | 대표 HOLD_B 음수·다중검정 미통과 |
| R2-14 E | 거래량 돌파/추종·fade E1~E3 | 양방향 | OHLCV | 부분 채택 | E1 long 채택; E1 short DEV +533bp이나 top2 제거 -2517bp |
| R2-14 F | funding/premium/global-LS fade F1~F4 | 양방향 | funding·premium·global LS | F3 채택 | F3 강했으나 나머지와 전체 family 가설은 미통과 |
| R2-14 G | 세션·정산 전후·요일 G1~G3 | 양방향 | OHLCV·funding clock | 실패 | 대표 HOLD_B 혼재/음수, 다중검정 미통과 |
| R2-14 H | 복합 squeeze/funding/MTF H1~H3 | 양방향 | OHLCV·funding | 실패 | 희소 또는 음수; 다중검정 미통과 |
| R2-15 | 고전규칙 meta-label logistic/CatBoost | 주로 롱 | OHLCV 216피처 | 부분 통과·미채택 | trend 가설 실패; E1 AUC DEV .557/HOLD_B .464 |
| R2-16 | 30/90일·expanding·시간가중 학습창 | 양방향 | MTF 모델 피처 | 실패 | 지지 학습창 0 |
| R2-17 | global/top LS 역추세 이웃 강건성 | 양방향 | metrics LS | 통과 | 360 qualified 중 HOLD_B 양수 334; F3-w30 후보 근거 |
| R2-18 | 1x/2x ATR 고정 손절·single/hedge | 양방향 | OHLCV·ATR·기존 후보 | 실패 | DEV 낙폭이 base보다 작다는 조건 실패 |
| R2-19 | funding/장부/집중도/DSR 재검증 | 양방향 | 후보 원장·funding | 실패 | R2-14와 archive 가설 모두 false |
| R2-20 | MTF 점수 인과 꼬리 q1/q2 | 양방향 | 1h/4h MTF 점수 | 후보 | 48 eligible 중 45 통과지만 후속 후보 HOLD_B/조합 불안정 |
| R2-21 | PatchTST up/down 분리 d 방향 | 양방향 | OHLCV PatchTST | 실패 | direction -4.06bp < fade -3.03bp |
| R2-22 | funding 경계 PESS/OPT 수정 | 해당없음 | funding archive | 방법 채택 | 알파 아이디어가 아니라 결함 수정 |
| R2-23 | 동일 원장 후보 12개 비교 | 양방향 | R2-9b/14/15/17/18/20 | 선택 | F3-w30·4h tail 선택; 재현 일부 gross 정의 불일치 |
| R2-24 | C1~C6 단일포지션 FIRST/PRIORITY/SWITCH | 양방향 | 후보 신호 원장 | C1 채택 | C1 FIRST Sharpe↑·MDD↓; SWITCH까지 이미 시험 |
| R2-25 | C1 이웃 81칸·모델·비용·지연 강건성 | 양방향 | F3/E1/MTF 후보 | 실패 | Sharpe↑&MDD↓ 18.5%/21.0% < 70% |
| R2-26~32 | HOLD_A 데이터·러너·bookTicker 제외 재현 | 해당없음 | 2026Q3 로컬 데이터 | 검증 완료 | 새 알파 시험 아님; 기술 차단 해소와 사후평가 |
| R2-33 | HOLD_A 국면·집중도 적대 진단 | 양방향 | C1/F3/E1/C4 원장 | 실전 후보 없음 | 상위2 제거 모두 음수; 새 OOS 부재 |
| R2-34 | 모의 승격 검정력·12/24개월 기준 | 해당없음 | C1 일별 PnL | 설계 채택 | 전략 알파가 아니라 판정 절차 |
| R2-35/36 | global LS create_time +5분 정렬 | 양방향 | metrics archive·REST 비교 | 채택 | 시각 오염 수정; +5분 C1/F3 기준으로 교체 |
| R2-37 | 1h→5m/1m 판단주기 변형 | 양방향 | LS 5m·OHLCV 1m | 실패 | DEV 사전 paired 통과 변형 0; 놓친 거래 평균도 불안정 |
| R2-38 | 숏 후보·전략 router 적대 설계 | 숏 우선 | 로컬 전 피처 | 설계 | 실행 전 명세; 성능 증거 아님 |
| R2-39 S1 | F3 short + prior 30d 하락 | 숏 | global LS·OHLCV | 실패 | DEV PW 하한 -0.91; overlay 개선 0 |
| R2-39 S2 | 하락국면 저점이탈·거래량 | 숏 | OHLCV | 실패 | DEV -817bp; overlay -2742bp |
| R2-39 S3/S4 | funding·premium 과열 fade | 숏 | funding·premium·global LS | 실패 | PW 하한 음수; S4 n=4·top2 제거 음수 |
| R2-39 S5/S6 | OI 급증+가격하락+taker 매도 | 숏 | OI·OHLCV·taker share | 실패 | 둘 다 DEV net·overlay delta 음수 |
| R2-39 router | 15피처 ridge/depth2 전략 선택 | 양방향 | OHLCV·metrics·funding·premium | 실패 | C1 paired -7831/-6834bp; PW 하한 약 -14bp/일 |

대장 행 수는 43다. R2-14의 813칸은 A~H 묶음으로 표시했지만 누적 시험 수에서는 813개 전부 센다. 상세 source·timestamp·cutoff·evidence rule은 `tested_ideas.parquet`에 있다.

## 2. DEV 기술통계

### 2.1 숏의 구조적 불리함과 하락 표본

| stat | n | value | hold_hours |
|---|---|---|---|
| DEV mean close-close log drift | 1766.000 | 3.222 | NA |
| short headwind, 12h | 1766.000 | 1.611 | 12.000 |
| short headwind, 20h | 1766.000 | 2.685 | 20.000 |
| short headwind, 24h | 1766.000 | 3.222 | 24.000 |
| negative calendar days | 882.000 | 49.943 | NA |
| prior-30d down decision hours | 20470.000 | 48.269 | NA |

| regime | n | net_bps | mean_bps | win_rate | top2_removed_bps |
|---|---|---|---|---|---|
| prior30d_down | 254.00 | 9532.48 | 37.53 | 0.46 | 5683.64 |
| prior30d_up | 110.00 | 3297.51 | 29.98 | 0.50 | 1396.11 |

`drift×보유시간`은 기대값 분해일 뿐 거래별 손실 예측값이 아니다. 하락 표본은 두 정의를 병기했다: 일별 close-close 음수일과 판단 직전 30일 return<0. 후자는 R2-39 S1과 같은 정의이며 이미 gate로 실패했다.

### 2.2 C1 수익원 분해

DEV C1: 859건, 34,870.6bp. short 364건 12,830.0bp, long 495건 22,040.6bp.

#### 방향·source

| side_name | n | net_bps | mean_bps | win_rate | top2_removed_bps |
|---|---|---|---|---|---|
| LONG | 495.00 | 22040.64 | 44.53 | 0.54 | 19011.39 |
| SHORT | 364.00 | 12829.99 | 35.25 | 0.48 | 8981.15 |

| component_name | n | net_bps | mean_bps | win_rate | top2_removed_bps |
|---|---|---|---|---|---|
| E1 | 188.00 | 4713.93 | 25.07 | 0.49 | 3035.25 |
| F3 | 671.00 | 30156.71 | 44.94 | 0.52 | 26307.87 |

#### global LS 수준

| ls_level | n | net_bps | mean_bps | win_rate | top2_removed_bps |
|---|---|---|---|---|---|
| low<=20% | 328.00 | 20142.93 | 61.41 | 0.56 | 17113.68 |
| mid20-80% | 156.00 | 2080.09 | 13.33 | 0.49 | 536.66 |
| high>=80% | 373.00 | 13027.94 | 34.93 | 0.47 | 9179.10 |
| NA | 2.00 | -380.32 | -190.16 | 0.00 | 0.00 |

#### 24h 실현변동성 3분위

DEV 전체 정시 기준 cutoff: low/mid `0.003627`, mid/high `0.005646`.

| volatility | n | net_bps | mean_bps | win_rate | top2_removed_bps |
|---|---|---|---|---|---|
| low | 271.00 | 6409.14 | 23.65 | 0.49 | 4931.54 |
| mid | 274.00 | 11561.06 | 42.19 | 0.50 | 8456.79 |
| high | 314.00 | 16900.44 | 53.82 | 0.54 | 13126.61 |

#### UTC 진입 시간대

| utc_session | n | net_bps | mean_bps | win_rate | top2_removed_bps |
|---|---|---|---|---|---|
| 00-07 | 272.00 | 11879.50 | 43.67 | 0.56 | 9876.82 |
| 08-15 | 270.00 | 6632.48 | 24.56 | 0.48 | 3093.54 |
| 16-23 | 317.00 | 16358.65 | 51.60 | 0.50 | 13019.50 |

#### 보유 중 경로

| side | outcome | n | net_bps | median_mae | median_mfe | median_mfe6h | median_giveback | median_t_mfe |
|---|---|---|---|---|---|---|---|---|
| LONG | loss | 229.00 | -42009.34 | 251.15 | 81.30 | 61.89 | 221.93 | 210.00 |
| LONG | win | 266.00 | 64049.98 | 66.00 | 294.35 | 134.82 | 107.89 | 989.50 |
| SHORT | loss | 191.00 | -33456.79 | 229.65 | 89.11 | 58.73 | 248.09 | 278.00 |
| SHORT | win | 173.00 | 46286.78 | 67.01 | 329.90 | 104.15 | 124.45 | 1025.00 |

#### 손실 거래 공통점

| group | loss_n | loss_rate | median_mae | median_mfe | mfe6h_lt_0.25atr_rate | mfe_ge50_rate |
|---|---|---|---|---|---|---|
| all | 420.000 | 0.489 | 242.151 | 83.781 | 0.157 | 0.693 |
| short | 191.000 | 0.525 | 229.655 | 89.114 | 0.157 | 0.702 |
| long | 229.000 | 0.463 | 251.149 | 81.302 | 0.157 | 0.686 |

MAE/MFE는 entry 이후 실제 exit 직전까지 1분 high/low로 계산했다. `MFE>=50bp인데 최종 손실` 비율은 이익잠금 가능성의 상한일 뿐이다. 고점·저점을 사후에 알아야 하므로 그대로 청산 규칙으로 쓸 수 없다.

R2-18과의 차이: R2-18은 entry ATR의 1x/2x 불리한 가격을 건드리면 즉시 나가는 **고정 손절**이었다. 여기서 본 경로 통계와 P4는 6시간까지 유리한 진행이 없을 때만 나가는 **시간×확인 실패**다. 그래도 성과는 별도 사전등록 시험 전까지 0으로 간주한다.

### 2.3 F3 숏 전용 단일포지션 장부

| segment | trade_n | total_net_bps | net_per_trade_bps | daily_sharpe | pw_ci95_lower_daily_bps | alpha_daily_bps | alpha_ci95_low | beta | top2_removed_net_bps | top5_removed_net_bps |
|---|---|---|---|---|---|---|---|---|---|---|
| DEV_COMMON | 368.000 | 12686.557 | 34.474 | 0.923 | 0.311 | 7.446 | 1.386 | -0.239 | 8837.718 | 5719.397 |
| HOLD_B | 24.000 | 2048.109 | 85.338 | 1.735 | -11.461 | 5.368 | -9.585 | -0.264 | 88.028 | -1372.056 |

`total_net_bps`는 경계 분할 MTM, 아래 `trade_net`은 진입 구간 기준 완결 거래 합이다. HOLD_B 2bp 차이는 경계 비용 귀속이다.

| segment | f3_short_n | f3_short_trade_net | c1_short_n | c1_short_trade_net | f3_entries_blocked_in_c1 | net_difference |
|---|---|---|---|---|---|---|
| DEV_COMMON | 368.00 | 12686.56 | 364.00 | 12829.99 | 4.00 | -143.43 |
| HOLD_B | 24.00 | 2046.11 | 23.00 | 1918.77 | 1.00 | 127.34 |

F3 숏 전용은 F3 standalone에서 long 거래를 버린 단일 장부다. DEV에서 C1 short보다 4건 많고 trade-net은 143.4bp 적다. 즉 C1 안 short와 사실상 같은 수익원이며 새 독립 alpha가 아니다. DEV beta는 음수이고 alpha 하한은 양수지만, HOLD_B PW·alpha 하한은 음수이며 top5 제거도 음수다. 관찰 가치는 있으나 승격 근거는 없다.

## 3. 새 개선안

| id | proposal | market_logic | preregistered_definition | nearest_test | actual_difference | expected_dev_n | learn_if_fail |
|---|---|---|---|---|---|---|---|
| P1 | F3 short를 혼잡 에피소드 1회로 거래 | 같은 tail 지속 중 24h마다 재진입하면 비용과 동일 국면 의존이 쌓인다. | global_ls가 현행 90d q90을 아래→위 돌파할 때만 T+1m open short. q75 이하에서 청산·재무장, 72h cap, q10 반대신호 청산. 4bp+PESS. | R2-14 F3/R2-6 고정보유 | 고정보유·반복 재진입이 아니라 명시적 hysteresis 상태와 중립 복귀 청산. 분위수 미세조정 아님. | 190.00 | 반복 재진입이 alpha인지 비용성 중복인지 판별 |
| P2 | F3 tail 진입을 LS 되돌림까지 지연 | crowding 자체보다 crowd가 풀리기 시작한 시점이 short 촉매일 수 있다. | q90 상향 돌파 후 tail 안에서 global_ls가 처음 전시점보다 하락한 정시 T에 T+1m open short. 12h 또는 q50 이하 먼저 청산. episode당 1회. | R2-39 S1·R2-37 5m | 가격 추세 gate/판단주기 변경이 아니라 LS 상태전환을 entry event로 사용. 기존 F3는 tail 진입 즉시 거래. | 204.00 | level fade와 unwind timing 중 어느 쪽이 수익원인지 판별 |
| P3 | crowded-long failed auction short | 공격적 매수가 많아도 가격이 못 오르면 수동 매도 흡수·분배일 수 있다. | F3 short tail 중 return_1h<=0 AND taker_buy_share_1h가 직전 90d q70 이상이 처음 된 T에 T+1m open short. 12h 또는 F3 q10 반대신호 청산. episode당 1회. | R2-39 S5/S6 | S5/S6은 OI 급증+가격하락+taker 매도(<.45/.40). 본 안은 OI 없이 taker 매수 우위인데 가격반응이 없는 괴리이며 부호가 반대. | 79.00 | sell aggression이 아니라 buy absorption이 short 정보를 갖는지 판별 |
| P4 | 6h 무진전 short time-stop | 좋은 short가 초기에 전혀 유리하게 움직이지 않으면 24h drift headwind만 더 받을 수 있다. | 현행 F3 short 진입 후 6h 동안 MFE < 0.25×entry ATR14이면 6h 시점 open 청산. 아니면 현행 reverse/24h 청산 유지. 새 진입 없음. | R2-18 ATR stop·R2-13 trailing/X_PRED | R2-18은 불리한 가격 도달 즉시 고정 손절, R2-13은 학습/추적 청산. 본 안은 손실폭과 무관한 시간×무진전 조건 1개. | 368.00 | 손실이 늦은 미확인 거래에서 생기는지, 단순 손절로는 못 본 구조 판별 |
| P5 | F3 short 인과 변동성 목표 비중 | 동일 1단위는 고변동 국면에 위험과 집중도를 몰아준다. | size=clip(prior 90d rv_24h median/current rv_24h,0.5,1.5). 현행 entry/exit 그대로, cost·funding·PnL 모두 size 비례. 목표는 Sharpe/MDD, 단위 alpha 아님. | R2-2 capacity·R2-18 risk stop | 동시포지션/청산을 바꾸지 않고 사전 인과 risk budget만 바꿈. 기존 시험에 연속 notional scaling 없음. | 368.00 | alpha가 아니라 변동성 집중이 C1 위험을 만드는지 판별 |

예상 n은 P1~P3의 사전 entry event를 각각 24h/12h 점유로 순차 계수한 값이다. P1은 실제 q75/72h 상태청산이 점유시간을 바꾸므로 190건은 설계용 proxy이며 정확한 거래 수가 아니다. P4/P5는 기존 F3 short 368건 전부가 대상이다.

제외한 재탕: fixed hold sweep, q/창 미세조정, downside breakout, 30일 하락 gate, funding/premium 극단, OI+taker 매도, 고정 ATR stop, trailing, meta-label, router, 판단주기 단축, FIRST/PRIORITY/SWITCH. 모두 대장에 있다.

## 4. 시험 설계

### 누적 시험 수

- R2-19 감사: 4,707.
- R2-20 120 + R2-21 144 = R2-23 기준 4,971.
- R2-24 36 = 5,007.
- R2-25 manifest 누적 = 5,078.
- R2-37 비기준 변형 22 = 5,100.
- R2-39 short 12 + router 2 = **5,114**.
- P1~P5를 모두 열면 내부 `m=5`, 누적 **5,119**로 사전 고정한다. R2-39 manifest의 하한 5,050보다 큰 대장 재계산값을 쓴다.

### 실행 단위와 통과 기준

1. P1~P4는 F3_SHORT와 paired 일별 MTM delta, P5는 위험조정 장부와 F3_SHORT를 비교한다. C1 개선판도 별도 single-position replay로 C1과 paired 비교한다.
2. DEV에서 절대 net>0, 절대 PW 95% 하한>0, paired net>0, paired PW 하한>0, HAC alpha와 95% 하한>0, top2 제거 net>0, 8bp net>0을 모두 요구한다.
3. DSR은 내부 m=5와 누적 m=5,119를 모두 계산하고 둘 다 0.95 이상이어야 한다. 하나라도 실패하면 DEV FAIL이다.
4. DEV 통과가 여러 개면 paired PW 하한 최대 1개만 HOLD_B를 연다. HOLD_B는 net>0, paired net>=0, top2 제거>=0만 확인한다. HOLD_A는 숫자 표시만 한다.
5. P5는 net 우월이 아니라 Sharpe 증가·MDD 감소·paired PW 하한>0을 주 조건으로 하고, 평균 gross/net per unit은 개선 주장 대상에서 제외한다.

### 국면 편향 보정

- prior 30d return `<0`/`>=0`, 당일 close-close 하락/상승, rv_24h 3분위, 연도별을 모두 분리한다.
- B0 일별 log return에 대한 HAC alpha/beta를 주 시장중립 지표로 둔다.
- 각 국면에서 n, net, 거래당 net, exposure를 보고한다. 하락 n<50이면 부호를 통과조건으로 쓰지 않고 `UNDERPOWERED`로 표시한다.
- 현재 HOLD_B와 HOLD_A는 이미 반복 열람됐다. 최종 채택은 새 T0 이후 shadow 12개월 전에는 금지한다.

하락 표본 부족 평가는 정직하게 해야 한다. DEV에는 음의 일별 수익일이 882/1766일 있지만, 전략의 prior-30d 하락 short 표본은 위 표처럼 더 작다. 같은 하락 episode에서 여러 거래가 나오므로 거래 수가 독립 표본 수도 아니다.

## 5. 의견

**F3 숏 전용 관찰 장부는 바로 추가할 가치가 있다.** 단, 주문·자본을 하나 더 만드는 모의 전략이 아니라 현행 F3/C1 신호에서 파생한 read-only shadow 장부여야 한다. 새 T0, 별도 누적 PnL, alpha/beta/PW, top2/5, regime, MAE/MFE만 기록한다. 이번 작업에서는 시스템과 DB를 수정하지 않았다.

우선순위는 `P1 → P4 → P2 → P3 → P5`다. P1은 동일 tail 반복진입과 비용을 직접 겨냥한다. P4는 진단 경로와 가장 가까우나 사후 MFE 착시 위험이 있어 두 번째다. P2/P3는 새 entry event지만 표본이 줄어든다. P5는 alpha 개선이 아니라 위험배분이라 마지막이다.

## Claude에게 반박할 점

1. “하락장에서만 숏”은 상식이지 증거가 아니다. 같은 정의의 S1이 실패했고, C1 short는 prior30d 상승 구간에서도 따로 봐야 한다.
2. 새 지표를 더 붙이는 방식은 이미 S1~S6와 router가 실패했다. 다음 시험은 상태전환·에피소드·청산 구조처럼 실제 거래 생성 과정이 달라야 한다.
3. MAE/MFE 사후 통계만으로 stop을 채택하면 미래 극값을 사용한 선택이다. P4도 별도 시험 전에는 개선으로 부르지 않는다.
4. F3_SHORT의 DEV/HOLD_B 양수는 독립 발견이 아니다. C1의 같은 F3 short leg를 분리한 것이다.
5. HOLD_B/HOLD_A로 후보를 고르면 재차 사후 선택이다. 새 OOS는 동결 뒤 shadow 기록뿐이다.
6. router 실패를 “ML 전체 실패”로 넓힐 수는 없지만, 동일 15피처로 모델만 바꾸거나 threshold를 조정할 근거도 없다.
