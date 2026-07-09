# Metrics 피처 통합 — 완료

## 목표 (달성)
Binance futures metrics 아카이브(open interest, long/short ratios, taker buy/sell)를
학습 피처로 추가. depth 7개(형식 불일치·train-live 간극)는 비활성화.

## 최종 피처 구성: 152개
148(기존) − 7(depth 비활성) + 11(metrics) = 152

## 완료된 통합 (전부 검증됨)
1. metrics_source.py — 다운로드·dedup·정렬·피처화 (실데이터 검증 완료)
   - 실데이터 확인: 5분 주기, create_time 동일-값동일 중복, 2020-09부터 존재
2. collect-metrics CLI — Phase 1.5 다운로드
3. feature_registry — 11개 F16 피처 등록 (required_for_live=False, warmup 불변)
4. depth 7개 — scaffold_status=pending_data_source (비활성, 정의는 보존)
5. sources.py — metrics 소스 정의, snapshot_for 안전화
6. dataset.py build_feature_rows — metrics 주입(_metrics_feature_value), 없으면 0 degrade
   - 병렬 경로도 자동 반영 확인
7. train --metrics-dir — 캐시 metrics 로드→피처화→병합
8. run_full_pipeline ps1/sh — Phase 1.5 + train --metrics-dir 연결
9. tests 갱신 — depth 비활성·F16 추가 반영

## 11개 metrics 피처
- OI(정규화): oi_change_rate_5m, oi_change_rate_30m, oi_zscore_1d, oi_value_zscore_1d
- L/S(원값): toptrader_ls_account, toptrader_ls_position, global_ls_account, taker_ls_ratio
- L/S(변화): toptrader_ls_account_change_5m, global_ls_account_change_5m, taker_ls_ratio_change_5m

## 검증 결과
- 최종 152개, FEATURE_NAMES=FeatureRow 일치
- metrics 주입/degrade 정상 (병렬 포함)
- look-ahead 없음 (causal 변화율/z스코어, 5m→1m as-of join)
- test_core 원본과 동일(errors=7, 전부 catboost/pyarrow 환경 문제) — 회귀 없음
- end-to-end: 다운로드→피처화→주입→학습피처 전 경로 작동

## ⚠ 중요: 라이브 배포 전 필수 작업
metrics 피처는 required_for_live=False. 라이브 API(/futures/data/openInterestHist,
globalLongShortAccountRatio, takerlongshortRatio 등)를 live 엔진에 아직 안 붙임.
→ 이 모델은 연구·백테스트 전용. 실거래하려면 라이브 API 경로부터 구현해야 함.
(depth처럼 train-live 간극 만들지 않기 위한 의도적 게이팅)

## 실행 방법 (사용자 환경, 네트워크 필요)
전체 파이프라인 (metrics 자동 포함):
  ./run_full_pipeline.sh   또는   .\run_full_pipeline.ps1
  → Phase 1(klines) → Phase 1.5(metrics) → Phase 2(parquet) → Phase 3(학습, metrics 포함)
    → Phase 4a(사후regime 백테스트) + 4b(auto-regime 백테스트)

metrics만 미리 받기:
  python -m btcusdt_quant collect-metrics --start 2020-09-01 --end 2025-12-31 \
    --allow-public-network --output artifacts/metrics

## 다음에 볼 것
재학습 후 gross_total_return 비교:
- metrics 추가 전(133 유효피처) vs 후(144 유효피처, metrics 11개 살아있음)
- gross가 개선되면 metrics(OI/롱숏/taker)에 예측력이 있다는 증거
- 여전히 gross~0이면 라벨 재정의(TP 확대, 메타라벨링)로 넘어가야 함
