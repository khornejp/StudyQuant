# Label · 실행 시점 · 거래비용 계약

모델이 예측한 대상과 백테스트가 실제로 거래한 대상이 다르면, predictive metric이 좋아도 edge로 연결되지 않는다.
이 문서는 feature, label, signal, execution의 시점 계약을 고정한다.

## 모든 변경 전에 명시할 다섯 시점

1. **Feature cutoff** — feature가 사용할 수 있는 마지막 관측 시각
2. **Decision timestamp** — 모델 예측과 주문 결정이 생성되는 시각
3. **Earliest execution** — 주문이 현실적으로 가장 빨리 체결 가능한 시각
4. **Label start** — 수익률 또는 barrier 측정을 시작하는 시각
5. **Label end** — horizon 또는 exit/barrier가 끝나는 시각

기본 안전 계약:

- candle `t` close까지의 정보로 feature를 계산한다.
- 예측은 `t` close가 확정된 뒤 생성한다.
- 체결은 `t+1` open 또는 latency를 반영한 이후 가격에서 시작한다.
- label은 같은 execution point부터 측정한다.
- 상위 timeframe feature는 완료된 candle만 사용한다.

현재 close를 feature에 사용하면서 같은 close 가격에 체결하는 방식은 현실적인 주문 체결 모델이 없다면 누수 또는
과도한 낙관으로 취급한다.

## 라벨 감사 체크리스트

- `shift(-h)`는 target 생성에만 사용되고 feature로 섞이지 않는가?
- label horizon이 CV purge gap보다 길지 않은가?
- entry delay를 label에도 동일하게 반영했는가?
- TP/SL/barrier 판정에서 동일 candle 내 고가와 저가가 모두 닿았을 때 순서를 어떻게 처리하는가?
- timeout exit가 실제 체결 가능한 가격을 사용하는가?
- long과 short의 fee/funding 부호가 정확한가?
- multi-horizon label이 서로 중첩될 때 uniqueness 또는 concurrency를 고려하는가?
- regime 또는 threshold별로 label balance가 급변하지 않는가?

## 고가·저가 기반 barrier의 모호성

1분봉 OHLC만으로는 한 candle 안에서 TP와 SL 중 무엇이 먼저 발생했는지 알 수 없다. 둘 다 닿았다면 다음 중 하나를
명시적으로 선택한다.

- 보수적 처리: 손실 barrier가 먼저라고 가정
- 해당 sample 제외
- 더 낮은 timeframe/tick 데이터로 순서 복원
- 사전에 고정한 deterministic tie-break

결과가 가장 좋아지는 순서를 사후 선택하지 않는다.

## 고정, ATR, volatility-scaled label 비교

라벨 후보는 경제적 의미와 intended holding period를 기준으로 비교한다.

- fixed-return threshold
- ATR-scaled threshold
- realized-volatility-scaled threshold
- triple-barrier 또는 timeout 구조

각 후보는 동일한 OOS split과 동일한 비용 조건에서 비교한다. final test를 보고 라벨을 다시 고르지 않는다.

## 거래비용

최소 포함 항목:

- maker/taker fee
- entry/exit slippage
- spread 또는 adverse selection proxy
- funding payment
- turnover 증가에 따른 비용
- 필요할 경우 latency와 partial fill

보고할 비용 시나리오:

1. baseline cost
2. 1.5x baseline cost
3. 2x baseline cost

gross expectancy가 아니라 **net expectancy**가 최종 판단 기준이다.

## 확률에서 거래로의 변환

단순히 `probability > threshold`만 최적화하지 않는다. 가능하면 다음 구조를 사용한다.

```text
EV_long = p_win * avg_win - (1 - p_win) * avg_loss - total_cost
EV_short = p_win_short * avg_win_short - (1 - p_win_short) * avg_loss_short - total_cost
```

`avg_win`, `avg_loss`, cost는 validation fold에서만 추정하고 기간별 안정성을 확인한다. threshold, sizing,
calibration을 같은 fold에 반복 최적화하면 과적합 위험이 커지므로 nested 또는 분리된 split을 사용한다.

## 테스트해야 할 불변식

- feature row `t`가 label의 미래 값을 직접 포함하지 않는다.
- earliest execution이 feature cutoff보다 늦다.
- label interval이 train/validation 경계를 넘으면 purge된다.
- 비용 0과 실제 비용 결과가 모두 저장된다.
- long/short 비용 부호와 funding 방향이 unit test로 고정된다.
- resampled feature는 완료된 bucket만 사용한다.
