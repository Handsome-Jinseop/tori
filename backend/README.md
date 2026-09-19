# 백엔드 (FastAPI + MongoDB)

식당 직원 출퇴근·급여 관리 시스템의 서버입니다. 관리자 웹앱(admin-web)이 쓰는 관리자 API와, 매장 폰 앱(추후 구현)이 쓸 기기 API를 함께 제공합니다.

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 필요한 값으로 수정
uvicorn app.main:app --reload --host localhost --port 8000
```

- 기본은 실제 MongoDB(`MONGO_URL`)에 접속합니다. 로컬에 MongoDB가 없으면 `USE_MOCK_DB=true`로 인메모리 목업(`mongomock-motor`)을 쓸 수 있습니다 — **개발/데모 전용**이며 프로세스를 재시작하면 데이터가 사라집니다. 운영에는 실제 MongoDB를 쓰세요.
- `USE_MOCK_DB=true`로 실행하면 시작할 때 DB가 비어 있을 경우 자동으로 데모 데이터를 시드합니다(3개 매장, 알바 18명 + 직원 6명, 8월~9월 근무 기록, 대기 중인 신규 직원 요청과 얼굴 등록 등). 수동으로 다시 시드하려면:

```bash
USE_MOCK_DB=true python -m app.seed
```

## 관리자 로그인 (패스키/WebAuthn)

처음 실행하면 관리자 계정이 없는 상태(`setup_required: true`)입니다. admin-web의 로그인 화면에서 "패스키로 계정 만들기"를 누르면 이 기기의 지문·얼굴 인증으로 사장님 계정이 만들어집니다.

**패스키는 `localhost`에서만 동작합니다.** `127.0.0.1`이나 다른 IP로 접속하면 등록·로그인이 실패합니다. `RP_ID`/`ORIGIN` 환경 변수와 브라우저 접속 주소가 모두 `localhost` 기준으로 일치해야 합니다. 운영 배포 시에는 실제 도메인(Cloudflare Tunnel 등)에 맞게 `RP_ID`, `ORIGIN`을 설정하세요.

## 구조

- `app/main.py` — FastAPI 앱, 라우터 등록, 스케줄러 시작
- `app/routers/admin_*.py` — 관리자 API (화면별로 대응: 대시보드/직원/매장/근무 기록/정산/설정 등)
- `app/routers/device_api.py` — 매장 폰이 쓰는 기기 API (등록, 설정 조회, 얼굴 등록 요청, 출퇴근 이벤트 업로드)
- `app/services/payroll_engine.py` — 급여 계산 규칙 모듈(기본급/주휴수당/야간·휴일 가산/4대보험)
- `app/services/scheduler.py` — 5분마다 자동 퇴근 처리 + 예약된 직원 이동 적용
- `app/seed.py` — 데모 데이터 생성 스크립트

## 아직 안 된 것

- 매장 폰 앱(Kotlin/Compose, 온디바이스 얼굴 인식)은 이번 범위에 포함되지 않았습니다. 기기 API는 구현돼 있어 나중에 앱과 바로 연결할 수 있습니다.
- 임금명세서 PDF, 소득세 계산 등은 설계서의 "6단계 후속" 항목이라 포함하지 않았습니다.
