# 외부 자료 적용 검토 통합 리스트

> 작성일: 2026-07-09
> 원천 문서: `GRESEARCH_SUMMARY_REVIEW.md`, `ML4T_RESOURCES_REVIEW.md`
> 코드베이스 재검증: btcusdt_quant 내 Kelly 로직 없음, `ensemble.py`에 multi-horizon 없음,
> half-life 계산·`shift(-1)` 리키지 검사는 `ml4t-main/` 원본에만 존재, `ic_diagnostic.py`는 fold별 IC 미보고 — 두 문서의 gap 분석 모두 유효 확인.

---

## ✅ 적용 권장 — 우선순위 높음

1. **자동 리키지 회귀 테스트** (ML4T §2.3)
   - `analyze_leak.py` 패턴 응용: 신규 피처 추가 시 `target vs feature` / `target vs feature.shift(-1)` 상관 차이를 자동 검사, 임계치 초과 시 경고.
   - V5~V9 FIX_REPORT에 걸친 리키지 버그 반복 이력 고려 시 **ROI 최상위**.
   - 구현 위치: `ic_diagnostic.py` 파이프라인에 통합.

2. **Multi-horizon 앙상블 파일럿** (G-Research §2.1)
   - 30/60/90분 horizon 모델을 각각 학습해 확률을 단순평균하는 `MultiHorizonEnsembleAdapter`를 `ensemble.py`에 추가.
   - 레짐×horizon 조합 폭발 방지를 위해 **단일 레짐(trend) 파일럿** 후 확장.

3. **OU 반감기(Half-Life) 진단** (ML4T §2.2)
   - range 레짐의 고정 20바 윈도우(`range_position_20`, `bb_zscore` 등)가 실제 평균회귀 속도와 맞는지 실측.
   - 구현 위치: `verify_range_halflife.py` (기존 `verify_*.py` 계열과 동일 스타일).
   - 코드 패턴: `ml4t-main/.../Example7_5.py`의 OU 반감기 OLS 추정.

## 🟡 적용 검토 — 우선순위 중간

4. **Half-Kelly 동적 포지션 사이징** (ML4T §2.1)
   - `risk.py`의 고정 `max_leverage`를 예측 확신도 + 레짐별 변동성 기반 Kelly 비율로 확장, `max_leverage`는 캡으로 재해석.
   - 1분봉 특성에 맞는 lookback/재계산 주기 재보정 필요. 기본값은 Half-Kelly.

5. **fold별 Rank IC 보고** (ML4T §3.2)
   - `ic_diagnostic.py`의 전체 구간 단일 IC를 fold별 평균±표준편차 보고로 확장.
   - 기존 레짐별 IC와 상호보완적, 구현 비용 작음.

6. **거래비용 포함/미포함 샤프비율 병기** (ML4T §3.1)
   - 백테스트 리포트에 gross/net 샤프를 항상 나란히 표기. 편도 5bps만으로 샤프 반전 가능하다는 교훈 반영.

7. **OOS 강건성 게이트 명문화** (ML4T §3.3)
   - "in-sample 유의 + out-of-sample 재현성 검증 통과 시에만 배포" 원칙을 신규 피처/레짐 분류기 승인 프로세스에 문서화.

## 🔵 백로그 — 데이터/확장 선행 필요

8. **ETH/시장 인덱스 상대강도 피처** (G-Research §2.2) — 다자산 다운로더 구축 선행 필요.
9. **멀티코인 확장 시 공적분/페어 트레이딩** (ML4T §4) — `Example7_2/7_3.py` 출발점으로 추후 재검토.

## ⚪ 재확인만 필요 (코드 변경 없음)

10. **초장기 lookback 피처의 fold 경계 안정성** (G-Research §3) — warmup 처리(`WEEKLY_WARMUP_BARS`) 기존재, 검증만.
11. **기구현 확인 항목** — log_return/캔들형태/rolling zscore(F07), purge/embargo(`PurgedWalkForwardSplit`), 거래비용 모델링, walk-forward 분리.

## ❌ 적용하지 않기로 결론

12. **Weighted Pearson 지표** — 다자산 cross-sectional 전용.
13. **Deep Learning(Axial Attention) 아키텍처** — 현행 CatBoost 라우팅 유지.
14. **Data Lightweighting(Close만 사용)** — 메모리 제약 절충일 뿐, 역행 방향.
15. **계절성 모멘텀 / QuantConnect 멀티종목 전략 / Campisi 논문 재현** — 무관하거나 이식 비용 대비 가치 낮음.

---

## 구현 범위 (2026-07-09 결정)

**1~6번을 구현 대상으로 확정.** 7번은 문서화 항목으로 별도 진행, 8번 이후는 백로그.
