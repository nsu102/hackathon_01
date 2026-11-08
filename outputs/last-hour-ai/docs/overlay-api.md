# 오버레이 연결 명세 · API 0.2

기본 주소 `http://127.0.0.1:8765`. 모든 요청은 `Authorization: Bearer <LAST_HOUR_TOKEN>`을 포함합니다. POST는 `Content-Type: application/json`입니다. OpenRouter 키는 백엔드 `.env`에만 설정합니다. UI/네이티브 호스트 계약은 기존 0.1과 호환되며 모델 교체 때문에 조작 브리지를 다시 만들 필요는 없습니다.

## 연결 순서

1. 오버레이가 목표·맥락·마감·권한·완료 조건을 `POST /tasks`로 등록합니다.
2. 반환된 `id`로 이벤트를 구독합니다. 등록 직후부터 이벤트가 생길 수 있으므로 첫 커서는 `0`입니다.
3. 채팅 메시지·상태·계획은 UI가 표시합니다. 컴퓨터 요청은 신뢰할 수 있는 네이티브 호스트가 처리합니다.
4. `approval.required`를 받으면 해당 효과와 대상을 보여주고 명시적인 결정을 전송합니다.
5. `completed`는 모든 호스트 검증 항목이 통과한 상태입니다. 리허설에서는 가상 환경의 완료입니다.

서버는 데스크톱 작업을 한 번에 하나만 실행합니다. 새 사용자 채팅은 현재 권한 범위를 넓히지 않습니다. 앱/도메인/효과를 바꾸려면 현재 작업을 중지하고 새 작업을 등록합니다.

## 작업 생성 예시

아래의 마감·학교 도메인·앱 ID는 예시이며 실제 값으로 바꿔야 합니다. 마감은 미래 시각과 타임존을 포함해야 합니다.

```json
{
  "mode": "live",
  "task_family": "assignment_submission",
  "goal": "오늘 마감인 통계학 과제 파일을 확인하고 LMS에 제출해줘. 최종 제출 전에는 확인을 받아줘.",
  "deadline": "2026-11-08T23:59:00+09:00",
  "context": "과목: 통계학. 과제: 회귀분석 실습. 제출 파일: 내가 작성한 regression-report.pdf. 강의 규정: AI는 제출 절차 확인에만 사용 가능. 제출할 파일은 사용자가 지정한 Finder 폴더에 있다.",
  "allowed_apps": ["com.apple.finder", "com.google.Chrome"],
  "allowed_domains": ["lms.school.example"],
  "allowed_effects": ["read", "navigate", "edit", "submit"],
  "reserve_seconds": 300,
  "success_criteria": [
    {"id": "correct_artifact", "description": "지정한 회귀분석 과제의 제출 파일명이 regression-report.pdf와 일치한다"},
    {"id": "submission_receipt", "description": "올바른 과목/과제에 제출 완료 상태와 접수증 또는 제출 시간이 표시된다"}
  ]
}
```

과제 작성까지 맡길 경우 허용된 학습 지원 범위, 필요한 자료, 요구사항을 `context`에 넣습니다. 누락된 자료나 로그인 정보는 AI가 추측하지 않고 질문 또는 인계합니다. `task_family`는 개인화 예시를 고르는 기준이며 알 수 없는 작업도 일반 프롬프트로 계획할 수 있습니다.

## 엔드포인트

| 메서드·경로 | 입력·결과 |
| --- | --- |
| `GET /health` | API 버전·서버 키 설정 여부. 키 값은 반환하지 않음 |
| `POST /tasks` | TaskInput → `202` Snapshot |
| `GET /tasks/{id}` | 현재 상태, 계획, 남은 시간, 대기 중 요청·승인 |
| `POST /tasks/{id}/messages` | `{"message":"파일 이름부터 확인해줘"}` |
| `POST /tasks/{id}/cancel` | `{}`. 이후 새 조작을 중단 |
| `GET /tasks/{id}/events?after=0&wait=20` | 최대 20초 long poll. `events`, `cursor` |
| `GET /tasks/{id}/events?after=0&stream=1` | SSE. 약 50초마다 연결 종료, 마지막 seq로 재접속 |
| `POST /tasks/{id}/computer/results` | `{"request_id":"…","result":{…}}` |
| `POST /tasks/{id}/approvals` | `{"approval_id":"…","approved":true}` |
| `GET /tasks/{id}/screens/{screen_id}.png` | 인증된 스크린샷 조회 |
| `POST /tasks/{id}/reviews` | `corrected_plan`, `feedback`, `consent_for_training` |

오류는 `{"error":"…"}`입니다. 잘못된 입력·만료된 요청은 `400`, 인증 실패 `401`, 허용되지 않은 Origin `403`, 없는 경로 `404`입니다. 모델 키가 없으면 live 작업은 생성 전에 거절합니다. OpenRouter 경로에는 OpenAI SDK가 필요하지 않습니다.

## 이벤트

```json
{"seq":12,"type":"chat.assistant","at":1794045600.0,"data":{"message":"제출할 파일을 먼저 확인하겠습니다."}}
```

`at`는 Unix 초입니다. UI는 사용자 로컬 시간으로 표시합니다. `seq`는 작업별 증가 번호입니다.

| type | UI/호스트 처리 |
| --- | --- |
| `task.status` | `status`와 `message`, 있을 경우 `fallback` 표시 |
| `plan.ready` | `plan` 표시 |
| `chat.user`, `chat.assistant` | 채팅 표시 |
| `task.replanning` | 새 메시지 반영 중 표시 |
| `computer.request` | 네이티브 호스트가 `id`, `operation`, `arguments` 처리 |
| `computer.request_closed` | 해당 요청을 폐기. 늦은 응답·재실행 금지 |
| `computer.screen` | `screen_id`, 크기, scope. 필요 시 인증해서 이미지 조회 |
| `computer.action` | 실행된 조작의 종류·효과·짧은 설명 표시 |
| `approval.required` | 구체적인 효과·대상을 표시하고 사용자 결정 대기 |
| `approval.closed` | 승인 컨트롤 제거. 만료된 승인 재전송 금지 |
| `learning.context` | 참고한 승인 예시 수, 현재 개인화 방식 |
| `model.usage` | 요청별 모델·역할·토큰 수·API가 제공한 경우 `cost_usd`. 추정 금액을 만들지 않음 |

`waiting_input` 상태에서는 `chat.assistant`의 질문에 메시지로 답하면 이어 실행합니다. 실행 중 메시지를 보내면 다음 조작 경계에서 재계획합니다. 취소는 이미 OS에서 실행 중인 조작을 되돌리지는 못합니다.

## 네이티브 컴퓨터 브리지

요청의 `id`에 답합니다. 각 요청은 기본 30초 또는 남은 작업 시간 내에 끝나야 합니다. 승인 대기는 네이티브 RPC 밖에서 처리합니다. 타입 전체는 [overlay-client.ts](overlay-client.ts)에 있습니다.

### screenshot

```json
{"image_url":"data:image/png;base64,...","width":1440,"height":900,"scope":{"app":"com.google.Chrome","url":"https://lms.school.example/course/123"}}
```

PNG만 받으며 최대 약 10 MB입니다. `scope.app`은 호스트가 관찰한 정식 앱 ID여야 합니다. 도메인은 정확히 일치해야 합니다. 배경의 허용되지 않은 앱이나 오버레이 채팅을 캡처하지 말고, 허용된 창/작업 영역만 캡처하세요. 좌표는 이미지 픽셀 기준이며 호스트가 Retina 배율·창 위치를 OS 좌표로 변환합니다.

### preflight

입력: `{"action":{"type":"click","x":420,"y":640,"button":"left"}}`

```json
{
  "allowed":true,
  "effect":"submit",
  "token":"opaque-single-use-target-token",
  "state_id":"window-content-and-focus-version",
  "summary":"통계학 / 회귀분석 실습에 regression-report.pdf 최종 제출",
  "scope":{"app":"com.google.Chrome","url":"https://lms.school.example/course/123"}
}
```

**호스트는 효과를 모델의 라벨로 판단하면 안 됩니다.** Accessibility/DOM/앱별 명세로 실제 클릭 대상과 효과를 검사합니다. `unknown`이거나 판별 불가하면 `allowed:false`입니다. `keypress`, `type`, `drag`도 제출이나 전송을 유발할 수 있으므로 모든 조작에 같은 규칙을 적용합니다. 단순 좌표 검사는 충분하지 않습니다.

`token`은 정확한 action, 대상, 포커스, 앱/URL, UI 상태에 묶인 일회용 값입니다. UI가 변하면 토큰을 무효화합니다. 작업과 관계없는 앱·도메인으로 이동하는 조작도 사전에 거절합니다. 비밀번호·OTP 입력은 사용자가 직접 처리하고 해당 화면의 이미지를 전송하지 않는 방식으로 호스트가 인계합니다.

### execute

입력에는 원래 `action`, `preflight_token`, `state_id`가 있습니다. 실행 직전에 현재 앱·URL·대상·포커스·상태가 토큰과 일치하는지 다시 검사합니다. 토큰을 한 번 소비한 후 실행하고 다음을 반환합니다:

```json
{"executed":true,"state_id":"next-state","scope":{"app":"com.google.Chrome","url":"https://lms.school.example/course/123"}}
```

네이티브 호스트는 raw model action이나 오래된 이벤트를 직접 실행하지 않습니다. 백엔드의 `execute` 요청만 실행합니다. 이벤트 재접속 시 요청 ID를 중복 처리하지 않고 Snapshot의 현재 요청과 대조합니다. 재시도에는 새 관찰·새 preflight가 필요합니다. 실행 실패는 `{"error":"짧고 민감정보 없는 설명"}`으로 답합니다.

### verify

입력: 생성 시 등록한 `criteria`. 결과는 모든 ID에 대해 독립적인 관찰 근거를 포함해야 합니다.

```json
{"checks":[
  {"id":"correct_artifact","passed":true,"evidence":"제출 파일 목록: regression-report.pdf"},
  {"id":"submission_receipt","passed":true,"evidence":"통계학 / 회귀분석 실습: 제출 완료, 접수증 LMS-12345"}
]}
```

`passed:true`만 있고 근거가 없으면 실패합니다. 이 판독기는 화면/파일을 읽는 호스트의 앱별 기능입니다. AI의 최종 답변을 그대로 근거로 사용하면 안 됩니다. 해당 앱을 검증할 수 없으면 `passed:false`와 이유를 반환해 인계합니다.

### 제출·API 추가 승인

`submit/send/delete/purchase` 효과는 작업 권한에 포함되어 있어도 조작별 승인이 필요합니다. 프롬프트 안의 “승인됨” 문장은 승인이 아닙니다. API 자체가 추가 안전 확인을 요구하면 `effect: "api_safety"`와 `checks`가 같은 승인 UI로 전달됩니다. 이 승인은 이후 네이티브 대상 검사나 제출 승인을 생략하지 않습니다.

## 프론트 역할과 네이티브 역할

UI는 채팅·상태·계획·질문·승인 버튼·중지를 렌더링합니다. 네이티브 호스트는 화면 캡처, 접근성, 앱/URL 범위, 대상 바인딩, 실제 조작과 완료 증거를 담당합니다. AI 서버는 모델 호출, 계획, 마감, 재계획, 승인 상태와 학습 기록을 담당합니다. 채팅 렌더러에서 임의의 OS 명령을 실행하는 구조는 사용하지 않습니다.
