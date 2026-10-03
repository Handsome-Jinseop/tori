# 매장 폰 앱(Android) 개발 가이드

백엔드(`backend/`)와 관리자 웹앱(`admin-web/`)은 이미 구현돼 있습니다. 이 문서는 세 번째 축인 **매장 폰 앱**을 PC에서 개발할 때 필요한 것들 — 서버 API 계약, 화면별 동작 규칙, 로컬 테스트 방법 — 을 한 곳에 정리한 핸드오프 문서입니다.

원본 요구사항은 `project/uploads/식당 직원 출퇴근·급여 관리 시스템 설계서.md`(전체 설계)와 `project/uploads/출퇴근·급여 관리 시스템 화면 명세서 (디자이너용).md`(화면별 상세), 디자인은 `project/phone-app*.dc.html`(P1~P10 시안)에 있습니다. 이 문서는 그걸 "지금 백엔드가 실제로 어떻게 구현돼 있는지"에 맞춰 재정리한 것이므로, 애매한 부분은 원본 설계서가 우선합니다.

## 1. 기술 스택 (설계서 기준 권장)

| 구성 요소 | 선택 |
| --- | --- |
| 언어/UI | Kotlin, Jetpack Compose |
| 카메라 | CameraX (전면 카메라, 상시 프리뷰) |
| 얼굴 검출 | ML Kit Face Detection (온디바이스) |
| 얼굴 임베딩 | TensorFlow Lite 모델 (MobileFaceNet 계열, 128~512차원 벡터) |
| 비교 | 이 폰에 승인된 직원 벡터와 코사인 유사도 1:N 순차 비교 |
| 로컬 저장 | Room(SQLite). 얼굴 벡터는 Android Keystore 키로 암호화해서 저장, 사진 원본은 저장하지 않음 |
| 오프라인 큐 / 동기화 | WorkManager (네트워크 생기면 배치 업로드, 실패 시 지수 백오프) |
| 기기 키 저장 | Android Keystore |

## 2. 기기 API 레퍼런스

서버 베이스 URL: 로컬 개발 시 백엔드를 `uvicorn app.main:app --host 0.0.0.0 --port 8000`으로 띄우고, 에뮬레이터에서는 `http://10.0.2.2:8000`, 같은 네트워크의 실기기에서는 PC의 LAN IP(`http://192.168.x.x:8000`)를 쓰세요.

인증: `/register`를 제외한 모든 요청에 헤더 `X-Device-Key: <api_key>`가 필요합니다. 틀리거나 비활성화된 기기면 `401`.

### POST `/api/device/register`
기기 등록 코드를 기기 키로 교환합니다. 코드는 관리자 웹앱 A12(기기 관리 → 등록 코드 발급)에서 발급하며, 10분 유효·1회용입니다.

```json
// 요청
{ "code": "7K39P2", "app_version": "1.0.0" }
// 응답 200
{ "device_id": "uuid", "api_key": "긴 랜덤 문자열 — 이걸 Keystore에 저장", "store_name": "토리코코로 별내 본점" }
// 실패 400: 코드가 틀렸거나 만료됨
```

### GET `/api/device/config`
대기 화면 진입 시, 그리고 주기적 동기화 때마다 호출. 매장 설정·직원 목록·얼굴 등록 상태·신규 직원 요청 처리 결과를 한 번에 내려줍니다.

```json
{
  "server_time": "2026-09-19T08:16:43.668Z",
  "store": { "id": "...", "name": "...", "close_time": "22:00", "close_next_day": false, "grace_min": 15 },
  "face_match_threshold": 0.75,
  "allow_manual_pick": true,
  "allow_pre_approval_clock": true,
  "employees": [{ "id": "emp-uuid", "name": "홍길동" }],
  "enrollments": [
    { "id": "...", "employee_id": "emp-uuid 또는 temp-id", "device_id": "...", "status": "pending|approved|revoked", "is_reenroll": false, "requested_at": "...", "approved_at": null }
  ],
  "resolved_employee_requests": [
    { "temp_id": "폰이 만든 임시 ID", "status": "accepted|linked|rejected", "linked_employee_id": "실제 employee_id 또는 null", "reject_reason": "" }
  ]
}
```

- `employees`: 이 매장(`work_store_ids`에 이 기기의 store_id 포함)에서 근무 가능한 **재직 중** 직원만. 얼굴 등록 1단계(이름 선택) 목록으로 그대로 씁니다.
- `enrollments`: 이 기기에 연결된 모든 얼굴 등록 레코드. `employee_id`는 신규 임시 등록 중이면 temp_id입니다. 로컬에 캐시해서 "등록됨" 표시(P7 1단계)나 승인 상태 확인(P2의 "등록 확인 중")에 쓰세요.
- `resolved_employee_requests`: **멱등** 처리됩니다 — 서버는 처리된 요청을 계속 내려주므로, 폰은 로컬에 그 `temp_id`가 더 이상 없으면 무시하면 됩니다. `accepted`/`linked`면 로컬에 남아있는 temp_id의 얼굴 벡터·이름을 `linked_employee_id`로 재매핑하고 표시를 지우세요. `rejected`면 설계서대로 로컬 이름·얼굴 데이터를 지우고 안내 문구를 한 번 보여주세요.

### POST `/api/device/enrollments`
기존 직원(목록에 이름이 있는 경우)의 얼굴 등록 요청. 재등록이면 `is_reenroll: true`.

```json
{ "employee_id": "emp-uuid", "consent_version": "v1", "is_reenroll": false }
```

승인 전에도 그 폰에서는 인식·출퇴근이 가능합니다(설계서 기준, `allow_pre_approval_clock`이 켜져 있으면).

### POST `/api/device/employee-requests`
목록에 없는 신규 직원의 임시 등록 요청(P8). `temp_id`는 폰이 만든 UUID. 서버는 이 호출과 **동시에** `face_enrollments`에도 `employee_id=temp_id`인 pending 레코드를 만들어주므로, 얼굴 등록 2~3단계(동의·촬영)는 별도 호출 없이 그대로 진행하면 됩니다.

```json
{ "temp_id": "temp-uuid-폰생성", "name": "이가을" }
```

### POST `/api/device/events`
출퇴근 이벤트 배치 업로드(오프라인 큐 플러시). 한 번에 최대 100건, 서버는 `device_clock_at`(없으면 `recorded_at`) 기준으로 정렬해 순서대로 처리합니다.

```json
// 요청
{
  "events": [
    {
      "uuid": "이벤트 UUID — 폰이 생성, 재전송해도 서버는 한 번만 저장",
      "employee_id": "emp-uuid 또는 temp_id",
      "kind": "in",               // "in" | "out"
      "recorded_at": "2026-09-19T00:30:00Z",   // 확정된 기록 시각 (UTC ISO)
      "time_source": "device",    // "device"(정상 인식) | "manual"(수기 입력)
      "device_clock_at": "2026-09-19T00:30:01Z", // 버튼 누른 순간의 기기 시각
      "input_method": "recognized", // "recognized" | "manual_pick"(P6에서 수기 선택)
      "similarity_score": 0.91,   // 인식 성공 시 점수, 수기 선택이면 null
      "manual_prev_checkout_at": null // P4-a(퇴근 없이 출근)에서만: 이전 근무 퇴근 시각
    }
  ]
}
// 응답 200
{ "results": [ { "uuid": "...", "status": "accepted", "shift_id": "...", "flags": ["manual_out"] } ] }
```

- `status`는 `accepted` 또는 `duplicate`(같은 UUID 재전송 — 폰은 그냥 완료 처리).
- `flags`는 서버가 이 이벤트로 인해 근무 기록에 붙인 특이사항(`manual_in/out`, `auto_checkout`은 서버 스케줄러가 붙임, `duplicate_in`, `missing_in`, `clock_skew`, `manual_pick`, `temp_employee`). 폰에서 특별히 보여줄 필요는 없지만, 디버깅에 유용합니다.
- **P4-a(퇴근 없이 출근)**: `manual_prev_checkout_at`을 채운 `in` 이벤트 하나만 보내면 서버가 이전 열린 근무를 그 시각으로 닫고 새 출근을 엽니다. 이전 퇴근 이벤트를 별도로 만들 필요 없습니다.
- **P4-b(출근 없이 퇴근)**: `recorded_at`에 실제 출근 시각, `time_source: "manual"`, `manual_prev_checkout_at`은 비워두고 `kind: "in"` 이벤트와 `kind: "out"` 이벤트 두 개를 순서대로 보내세요 (또는 설계서처럼 "출근+퇴근을 함께 기록" 의미로 두 이벤트를 같은 배치에 넣으면 됩니다).

## 3. 화면 흐름과 클라이언트 로직 체크리스트

화면별 상세 요구사항은 화면 명세서의 "매장 폰 앱: 출퇴근 화면(P1~P6)"과 "얼굴 등록과 관리 화면(P7~P10)" 절을 그대로 따르면 됩니다. 구현 시 놓치기 쉬운 서버-무관 로직만 모았습니다:

- **P1 대기**: 얼굴 감지 → ML Kit 검출 → TFLite 임베딩 → 로컬에 캐시된 승인된 직원 벡터들과 코사인 유사도 비교 → 최고점이 `face_match_threshold` 이상 *이고* 2등과 차이가 충분할 때만 일치. 연속 3회 실패 시 P5. 왼쪽 위 모서리 5연타로 P9.
- **직원별 "마지막 상태" 캐시**: Room에 직원별 최근 in/out 상태를 저장해서 오프라인에서도 P2의 출근/퇴근 버튼 강조가 정확하게 동작하게 하세요. `GET /api/device/config`는 이 상태를 내려주지 않으므로, 폰이 보낸 이벤트 기준으로 로컬에서 직접 추적합니다.
- **60초 중복 방지**: 같은 직원이 60초 안에 다시 기록하려 하면 "방금 기록했어요" — 이것도 로컬 캐시 기준.
- **30초 자동 복귀**: 대기 화면 제외 모든 화면. 타이머 리셋 조건(입력 발생 시)도 챙기세요.
- **P3 완료 3초 + 취소**: 취소 가능한 3초 동안은 서버로 업로드를 보류(큐에 넣지 않음). 취소 안 하면 그때 큐에 넣고 WorkManager가 전송.
- **오프라인 배너 + 전송 대기 N건**: Room의 pending 이벤트 개수를 그대로 표시.
- **얼굴 등록 품질 검사·중복 얼굴 거부**: 클라이언트에서만 가능한 로직(밝기/흔들림/크기, 기존 등록자와 벡터 유사도 과다 시 등록 거부) — 서버는 관여하지 않습니다.
- **P9 인식 테스트**: 서버에 아무것도 보내지 않는 로컬 전용 화면.
- **P10 기기 등록**: 성공하면 `api_key`를 Keystore에 저장하고 P1로. 등록 전에는 다른 화면으로 못 나가게.

## 4. 로컬 테스트 방법

1. 백엔드 실행 (`backend/README.md` 참고): `USE_MOCK_DB=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` — 처음 실행하면 데모 데이터가 자동 시드됩니다(매장 3개 등).
   - 목업 DB는 프로세스를 껐다 켜면 초기화됩니다. 계속 쓰려면 실제 MongoDB를 쓰세요(`USE_MOCK_DB` 빼고 `MONGO_URL` 설정).
2. 관리자 웹앱(`admin-web`) 실행 후 `localhost:5173`에서 패스키로 로그인 → **기기 관리(A12) → 등록 코드 발급**으로 테스트용 매장을 골라 코드를 받으세요.
   - 시드 스크립트가 만들어둔 `seed-device-key-0/1/2` 같은 고정 키도 있지만(터미널 로그에 출력됨, `USE_MOCK_DB=true`일 때만), 실제 등록 플로우(P10)를 테스트하려면 A12에서 새 코드를 받아 `/api/device/register`를 직접 호출해보는 걸 권장합니다.
3. 같은 관리자 웹앱에서 **대시보드(A2)**로 신규 직원 요청·얼굴 등록 승인을 처리하면서 폰 쪽 플로우(P7/P8 → 승인 대기 → `resolved_employee_requests`/`enrollments`로 상태 반영)를 end-to-end로 확인할 수 있습니다.

## 5. 아직 서버에 없는 것 / 주의

- 승인 전 출퇴근 허용 여부(`allow_pre_approval_clock`)와 수기 등록 허용 여부(`allow_manual_pick`)는 `/api/device/config`로 내려주지만, **강제하는 쪽은 클라이언트**입니다 — 서버 `/api/device/events`는 이 설정과 무관하게 들어오는 이벤트를 항상 저장합니다(설계서의 "거부보다 저장 우선" 원칙).
- 인식 기준값(`face_match_threshold`)이 바뀌면 다음 `/api/device/config` 호출 때 반영됩니다. 폰이 즉시 반응할 필요는 없고, 다음 동기화 주기에 적용하면 됩니다.
- 얼굴 벡터/임베딩은 전적으로 폰 로컬 책임입니다. 서버 어디에도 얼굴 데이터를 저장하는 API가 없습니다(의도된 설계).
