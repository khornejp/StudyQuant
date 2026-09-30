Repo: D:\StudyQuant. 내가 로직·알고리즘 결함을 직접 찾아봤다. 여섯 개 나왔고 두 개가 중요하다.
확인이 아니라 **공격**해라. 내 계산을 받아쓰지 말고 직접 재현하고, 틀린 곳을 찾아라.
맞으면 맞다고 말해라. 새 fit 0회, 새 학습 0회.

# 재현 기준

내 계산은 전부 아래로 했다. 이 재현부터 확인해라.

```python
d = pd.read_parquet("out/patchtst_k45_causal_admission_ordering_20260930/causal_candidates.parquet")
ex = d[(d.arm=="DOWN_BREAKOUT_LONG") & (d.first_come_executed==True)]
e, s = ex.entry_index, ex.scheduled_exit_index
r = 1e4*(close[s]/close[e] - 1) - 4
```

`n=3066`, `mean = +0.4550`으로 기존 `LONG_ONLY`와 정확히 일치했다. 이 경로가 올바른
재현인지 확인해라. 아니면 어디가 틀렸는지 지목해라.

# 결함 1 (치명적) — `+0.4550`이 거래 2건에 달려 있다

```
n=3066   총합 +1395.1 bps = $13.95
중앙값 +5.9749   sd 114.2   왜도 -1.11   min -1173   max +808

최고 1건 제거 -> +0.1916
최고 2건 제거 -> -0.0171      <- 부호 반전
최고 3건 제거 -> -0.2099
최고 10건    -> -1.3572
최고 30건    -> -3.6113

최악 1건 제거 -> +0.8380
최악 2건 제거 -> +1.2139
최악 10건    -> +2.9029

iid 부트스트랩(20,000) 95% CI [-3.566, +4.409], P(mean<=0)=0.407
```

공격 지점:

- 이 trimmed-mean 계산이 맞는가
- iid 부트스트랩은 거래 중첩을 무시한다. 단일 포지션 book이라 중첩이 없으니 iid가
  타당한가, 아니면 여전히 의존이 남는가
- 상위 2건이 무엇인가. 날짜, 수익, 그때 시장에 무슨 일이 있었는가. 한 사건에서 나온
  두 거래인가
- 중앙값 `+5.9749`인데 평균 `+0.4550`이다. 이 괴리를 어떻게 읽어야 하는가.
  "자주 조금 벌고 가끔 크게 잃는다"가 맞는 해석인가
- 이 집중도에서 `LONG_ONLY +0.4550`을 "실행 가능한 최선"이라 부르는 것이 정당한가.
  나는 철회했다. 네 판단은

# 결함 2 — 표류 대비 기준선을 한 번도 계산하지 않았다

A~F 전 실험에 무작위 방향 기준선이 없다. 내가 계산했다.

```
45분 무작위 롱, 후보 구간 전 분(n=2,879,368), -4bps : -3.7834 bps
같은 것, 15분 격자(n=191,957)                        : -3.7834 bps
전략 LONG_ONLY                                       : +0.4550 bps
차이                                                 : +4.2384 bps
```

즉 gross로 보면 무작위 롱 `+0.2166`, 전략 `+4.4550`이다.

공격 지점:

- 이 기준선이 올바른 비교인가. 후보 구간 전체의 모든 분을 쓰는 것이 맞는가, 아니면
  **게이트는 통과했지만 트리거가 안 걸린 바**로 맞춰야 하는가. 후자가 더 엄격한
  기준선이라고 본다. 계산해라
- 진입 시점 분포가 다르다. 전략은 큰 움직임 직후에만 들어간다. 시간대·요일·연도를
  맞춘 기준선이 필요한가
- `+4.2384`를 **게이트 기여**와 **트리거 기여**로 분해해라. 셋을 비교하면 된다:
  (a) 게이트 없음 + 트리거 없음 = 무작위, (b) 게이트만, (c) 게이트 + 트리거 = 전략.
  (b)가 얼마인가
- 이 gross 4.24가 결함 1의 상위 2건에서 나온 것인가. 그렇다면 두 발견은 같은 얘기다.
  상위 2건을 뺀 뒤에도 무작위 대비 우위가 남는가. **이게 가장 중요한 질문이다**

# 결함 3 — 진입과 청산이 같은 종가다

`first_crossing`이 `close[t+tau]`로 트리거를 판정하고
([fixed_trigger_hold_sweep.py:145](D:/StudyQuant/out/run_patchtst_fixed_trigger_hold_sweep.py:145)),
진입가도 `close[entry_index]`다
([stop_grid_audit_fix.py:176](D:/StudyQuant/out/run_patchtst_k45_stop_grid_audit_fix.py:176)).

같은 봉의 종가를 보고 그 종가에 체결한다. 실행 불가능하다.

크기를 쟀다.

```
구현대로 close->close        : +0.4550
다음 시가->다음 시가          : +0.4587
차이                         : +0.0037  (paired sd 0.94, t 0.22)
```

공격 지점: 이 측정이 맞는가. 청산도 같이 옮긴 것이 맞는 비교인가. 진입만 옮기고 청산은
그대로 두는 변형도 봐야 하는가. 그리고 `--maker-fill-window` 전제(지정가 전용)에서
"돌파 직후 종가 체결"이 애초에 성립하는가. **지정가 전제 자체는 사용자 결정이므로
다시 따지지 마라.** 체결 시점 정합성만 봐라.

# 결함 4 — purge/embargo가 0이다

[run_short_patchtst_3day_cadence_pilot.py:43-47](D:/StudyQuant/out/run_short_patchtst_3day_cadence_pilot.py:43):

```python
"train_end": stop_start.isoformat(),
"stop_start": stop_start.isoformat(),
"stop_end": at.isoformat(),
"test_start": at.isoformat(),
```

간격이 0이다. excursion/range 라벨은 `t+1..t+15`를 본다. 경계 직전 origin의 라벨이
다음 구간을 넘본다. 레포 계약(`references/leakage-and-cv.md`)이 purge+embargo를 요구한다.

공격 지점:

- 실제로 경계를 넘는 origin이 fold당 몇 개인가. TRAIN/STOP 경계와 STOP/TEST 경계 각각
- 그 origin들을 제외하면 예측 품질(Spearman)과 게이트 임계값이 얼마나 달라지는가
- 이것이 결론을 바꾸는 결함인가, 계약 위반이지만 미용상인가. 수치로 답해라

# 결함 5 — 서로 다른 calendar 두 개를 한 표본에 섞었다

`fold_plan()`은 `END = 2026-01-01`이고 `606 folds`를 assert한다
([:50](D:/StudyQuant/out/run_short_patchtst_3day_cadence_pilot.py:50)).
그런데 `causal_candidates.parquet`의 `pilot_fold`는 **0~666**이다. 606~666의 61 fold,
712 후보는 다른 생성기에서 왔다.

Codex 너는 `backward_k45` / `forward_hold_sweep`로 라벨은 붙였지만, HAC와 월 블록 통계는
둘을 한 표본으로 합쳐 계산했다.

공격 지점:

- 606~666의 TRAIN/STOP/TEST 기하가 0~605와 같은가. 다르면 어떻게 다른가
- 두 소스를 한 HAC/월 통계에 합친 것이 정당한가
- 소스를 나눠 재계산하면 `LONG_ONLY +0.4550`과 F-1 결과가 어떻게 달라지는가

# 결함 6 — fold당 후보 밀도가 25배 차이난다

fold당 후보 평균 15.39, 중앙값 8, **최대 203**. 592개 fold.

공격 지점: 이 편차가 HAC와 월 블록 통계를 어느 정도 왜곡하는가. E에서 월 블록으로
바꾼 것이 이 문제를 충분히 해결했는가, 아니면 월 안에서도 같은 편중이 남는가.

# 요구 출력

결함별로 `CONFIRMED` / `WRONG` / `MISLEADING` / `INCONCLUSIVE`를 붙이고, 틀린 것은
올바른 값을 써라. 그리고 마지막에 한 줄로 답해라.

**"결함 1의 상위 2건을 제거한 뒤에도 무작위 롱 대비 gross 우위가 통계적으로 남는가?"**

이 질문 하나가 이 프로젝트의 남은 전부다.

# 제약

- 새 fit 0회. `new_model_fits: 0`, `new_orders: 0`, `external_data_added: 0`, `live_orders: 0`
- 외부 데이터 금지. 기존 로컬 parquet과 funding ZIP만
- 기존 산출물 불변. 새 산출물이 필요하면 새 디렉터리
- 예측은 입력이다. 재학습·재튜닝·fold 선택 금지
- 숫자마다 file:line 또는 정확한 필터 조건을 달아라
- 승자 선택·판정 없음. 이건 감사다
