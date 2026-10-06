# BTCUSDT paper system v1

실주문 기능은 없다. 공개 Binance USD-M 데이터만 수집한다. `mode="live"`는 항상 오류로 종료한다.

## 실행 환경

저장소 루트에서 기존 가상환경을 사용한다. 새 설치는 필요 없다.

```powershell
cd D:\StudyQuant
venv_btcusdt\Scripts\python.exe scripts\paper_backfill.py --config config\paper.toml
venv_btcusdt\Scripts\python.exe scripts\paper_run.py --config config\paper.toml
venv_btcusdt\Scripts\python.exe scripts\paper_dashboard.py --config config\paper.toml
```

5분 smoke 수집:

```powershell
venv_btcusdt\Scripts\python.exe scripts\paper_run.py --config config\paper.toml --minutes 5
```

대시보드: `http://127.0.0.1:8765`. 외부 인터페이스에는 bind할 수 없다.

## `.env` 형식

v1 paper 모드는 값을 전송하지 않는다. 파일을 로그나 화면에 원문으로 표시하지 않는다.

```dotenv
BINANCE_API_KEY=fake_api_key_not_valid
BINANCE_API_SECRET=fake_api_secret_not_valid
```

현재 `.env`를 만들거나 수정할 필요 없다. 상태 화면은 존재 여부와 마스킹 값만 표시한다.

## 시작, 중지, 재시작

- 시작: `paper_run.py` 실행.
- 중지: 콘솔에서 `Ctrl+C`.
- 재시작: 같은 명령 재실행. `meta.last_processed_minute` 이후 공개 REST gap-fill부터 재개한다.
- 대시보드는 collector와 별도 프로세스로 실행한다.

SQLite 분 트랜잭션은 bar, health, resume cursor를 함께 commit한다. 비정상 종료 시 마지막 미완료 분 전체가 rollback된다.

## 데이터 위치

- `artifacts/live/live.sqlite`: WAL SQLite 원장.
- `artifacts/live/raw/YYYY-MM-DD.jsonl.gz`: 공개 API 원 응답.
- `artifacts/live/daily/<dataset>/...parquet`: 일별 export.
- `artifacts/live/ledger/<book>_trades.parquet`: 장부 export.

기존 `out/k45_*`와 `artifacts/hold_a_2026q3`는 읽기 전용 입력이다.

## 장애 복구

1. collector를 중지한다.
2. `live.sqlite`, `live.sqlite-wal`, `live.sqlite-shm`를 함께 보존한다.
3. 디스크 여유와 dashboard Health의 gap/retry를 확인한다.
4. 같은 config로 collector를 재시작한다. REST가 마지막 저장 분 이후를 채운다.
5. 다음 날 archive reconcile 결과를 확인한다. revision은 별도 기록되며 원 live 값은 덮어쓰지 않는다.

스키마 버전이 다르면 자동 변경하지 않고 종료한다. DB를 보존한 뒤 migration이 필요하다.

## live fail-closed

`config/paper.toml`의 `mode`를 `live`로 바꾸면 다음 오류로 종료한다.

```text
live mode is disabled: LiveBroker is not implemented
```

AGENTS.md 변경, 별도 승인, LiveBroker 구현 전에는 인증 호출과 주문 경로가 없다.

