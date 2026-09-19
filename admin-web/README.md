# 관리자 웹앱 (admin-web)

식당 직원 출퇴근·급여 관리 시스템의 관리자용 Vue 3 PWA입니다. PC에서는 좌측 사이드바 + 표, 폰에서는 하단 탭 + 카드로 같은 기능을 보여줍니다. 디자인은 `project/*.dc.html` 시안의 방향 A(크림 & 버터, 노랑 포인트, Jua/Pretendard)를 따릅니다.

## 개발 서버 실행

```bash
npm install
npm run dev -- --host localhost --port 5173
```

- `http://localhost:5173` 로 접속하세요. **`127.0.0.1` 대신 반드시 `localhost`를 쓰세요** — 패스키(WebAuthn)는 IP 주소에서 동작하지 않습니다.
- `vite.config.js`의 `server.proxy`가 `/api`를 `http://127.0.0.1:8000`(백엔드)으로 프록시합니다. 백엔드를 먼저 띄워야 합니다 (`../backend/README.md`).

## 빌드

```bash
npm run build
```

## 환경 변수

`VITE_API_BASE` — 배포 시 백엔드 API의 origin이 다르면 설정하세요 (기본값은 빈 문자열로, 같은 origin의 `/api`를 그대로 씁니다).

## 구조

- `src/api/` — 백엔드 REST 클라이언트
- `src/stores/` — Pinia (auth, catalog=매장/설정 캐시, ui=토스트/확인 대화상자)
- `src/components/` — 공용 컴포넌트(배지, 패널/시트, 기간·시각·금액 입력 등)와 다이얼로그(A7/A8/A9)
- `src/views/` — 화면별 컴포넌트 (A1~A16)
- `src/styles/tokens.css` — 디자인 토큰(색·폰트·반경)
