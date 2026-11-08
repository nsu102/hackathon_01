> v0.6 UI는 음성 질문만 사용합니다. 기존 텍스트 API는 호환용입니다. 기본 voice target은 screen이며 보정 없이 선택 모니터 전체를 사용합니다.

# 학습 API 계약

> v0.4 구현 계약입니다. 실제 장비 정확도 검증은 [검증 기록](study-validation.md)과 구분합니다.

Python 표준 라이브러리 서버입니다. `python3 -m last_hour serve --port 8765`. 모든 요청은 `Authorization: Bearer <LAST_HOUR_TOKEN>`과 JSON 본문을 사용합니다. 서버는 기본 loopback이며 외부 노출을 하지 않습니다. 허용된 Origin 이외는 거절합니다. Electron이 로컬 토큰을 보관하고 renderer는 제한된 IPC만 사용합니다.

| 메서드 / 경로 | 본문 또는 응답 |
|---|---|
| GET `/health` | `study_model: {provider, model, configured}` — 설정 존재이며 연결 성공 보장은 아님 |
| POST `/study/sessions` | `{goal, material, minutes:20, ai_enabled:true}` → 세션 스냅샷 |
| GET `/study/sessions/:id` | 시간·상태·심박·최근 대화·개인화·요약 |
| POST `/study/sessions/:id/assist` | `{mode:"hint"|"explain"|"quiz"|"chat", message:"..."}` → 실제 또는 데모 답변 |
| POST `/study/sessions/:id/checkins` | `{state:"okay"|"thinking"|"stuck"|"tired"}` — 사용자가 확인한 상태 |
| POST `/study/sessions/:id/pause` | `{paused:true}` 또는 `{paused:false}` |
| POST `/study/sessions/:id/end` | `{}` → 종료 요약, 반복 호출 안전 |
| POST `/study/sessions/:id/feedback` | `{response_id,helpful:true,consent_for_training:false}` |
| POST `/study/sessions/:id/focus-events` | 아래 상태 전이 집계 → `{recorded:true}` |
| POST `/study/sessions/:id/context-help` | WebM/Opus＋선택 PNG → 전사＋설명 |
| POST `/study/sessions/:id/screen-help` | 텍스트 질문＋선택 PNG → 설명, STT 호출 없음 |
| GET `/study/heart` | 연결·새로움·측정값. 없거나 오래된 bpm은 null |
| POST `/study/heart/connect` | `{}` — 환경변수 주소로 폴링 시작 |
| POST `/study/heart/disconnect` | `{}` — 폴링 중단·메모리 샘플 삭제 |

세션 ID는 32자 hex입니다. 한 번에 진행 또는 일시정지 세션 하나만 허용합니다. 자료는 30,000자, 질문은 4,000자, 세션당 AI 요청은 20회 이내입니다. 앱 재시작 시 과거 기록은 디스크에 남지만 세션을 자동 재개하지는 않습니다.

답변은 `id,role,content,question,answer,source,mode,usage`를 포함합니다. `source`는 `openrouter` 또는 `demo`입니다. `usage`는 제공자가 반환한 토큰과 비용 중 유효한 값만 담으며 없으면 추정하지 않습니다. UI는 입력 텍스트를 HTML로 실행하지 않습니다. 학습 에이전트는 도구/컴퓨터 작업을 수행하지 않습니다.

## 시선 집계

`POST /study/sessions/:id/observations`는 아래 정확한 필드만 받습니다. 영상·랜드마크·화면 좌표를 받아 저장하는 API는 없습니다.

```json
{"source":"webcam","samples":50,"window_seconds":10,"on_ratio":0.6,"away_ratio":0,"unknown_ratio":0.4,"calibrated":false}
```

세 비율의 합은 1입니다. `on`은 화면 안의 유효 좌표를 얻었다는 뜻이며 인지적 집중을 뜻하지 않습니다. 검증 전에는 좌표를 내보내지 않습니다. `away`는 유효한 화면 밖 좌표, `unknown`은 미검증·측정 불가입니다. 알림은 집계 API가 아니라 기기의 로컬 상태 엔진이 생성합니다.

## FocusEvent

```json
{"from":"away_pending","to":"away","reason":"outside_study","at_ms":12800,"duration_ms":8000,"correction":null}
```

상태: `attending / away_pending / away / unknown / paused / helping`. 근거: `help / user_pause / quality / in_allowed_region / offscreen / outside_study / user_correction`. 정정: null 또는 `thinking / notes / false_alarm`. 시각은 기기 단조 시각이며 서버 수신 벽시계와 구분합니다. 좌표·랜드마크 등 추가 필드는 거절하고 최대 최근 2,000개 전이를 저장합니다.

## ContextHelp

```json
{
  "audio":"<raw base64 WebM/Opus>",
  "duration_ms":3200,
  "speech_detected":true,
  "consent":true,
  "capture":{
    "png":"<raw base64 cropped PNG>","width":960,"height":600,
    "display_id":2,"captured_at_ms":12000
  },
  "target":{"selection":"gaze","calibration_id":"<in-memory calibration ID>"}
}
```

`target.selection`은 `gaze`, `manual`, `screen`입니다. 수동 선택과 전체 화면의 calibration_id는 null입니다. 카메라 영상·원시 시선 좌표는 전송하지 않습니다. 전체 모니터 캡처를 메모리에서 유지하다 선택된 영역만 서버에 전송합니다. Retina/음수 원점 변환은 native 계층이 수행합니다. 전역 키 해제 또는 버튼의 명시적 보내기가 확인된 요청만 native IPC `voice-submit`이 이 API로 전달하며 renderer의 일반 요청 화이트리스트에서는 직접 호출할 수 없습니다.

본문 상한은 15MB, 오디오 원본 2MB, PNG 원본 6MB, 화면 한 변 32~8192px입니다. 녹음은 250ms~20초입니다. 로컬 RMS 음성 활동·동의·WebM 서명·PNG IHDR 크기를 검사합니다. 유효한 진행 중 AI 세션에서만 전사합니다. 전사 오류·빈 발화·대표적인 무음 상투문 응답이면 Vision을 호출하지 않습니다. `speech_detected`는 로컬 음성 활동 게이트이며 인간 발화를 보증하는 인증 수단은 아닙니다.

서버→OpenRouter 전사 요청은 `/audio/transcriptions`에 `{model:STUDY_STT_MODEL,input_audio:{data,format:"webm"},language:"ko",response_format:"json"}`입니다. 채팅용 reasoning/provider 매개변수를 재사용하지 않습니다. 전사 뒤 기존 설명 모델에 텍스트＋이미지를 보냅니다. [공식 STT 문서](https://openrouter.ai/docs/guides/overview/multimodal/stt)

응답은 `{transcript,message}`이며 message는 `content,question,answer` 등을 포함합니다. 전사문과 답변은 세션 기록에 남지만 녹음·PNG·이미지 프롬프트는 기본 로그·학습 내보내기에 저장하지 않습니다. `training_eligible:false` 답변은 동의 체크가 있어도 내보내지 않습니다. 잘못된 입력은 HTTP 400, 공급자 오류는 내용이 정제된 HTTP 502입니다.


## ScreenHelp · 텍스트 화면 질문

`POST /study/sessions/:id/screen-help`는 정확히 `{message, capture, target, consent:true}`를 받습니다. message는 1~4,000자이며 capture/target과 응답 `{transcript,message}` 형식은 ContextHelp와 같습니다. 이 경로는 STT를 호출하지 않습니다. 데모·휴식·종료·중복 요청은 거절합니다. 이미지·프롬프트를 저장하거나 파인튜닝 예시로 내보내지 않습니다.

네이티브 `screen-prepare`가 질문과 시작 시점 전체 화면을 메모리에 고정합니다. 응시가 유효하면 선택 상자의 초기 위치로 사용합니다. `screen-submit`은 사용자가 확인한 영역만 크롭해 서버에 보냅니다. 화면 선택을 취소하거나 60초가 지나면 폐기합니다. 이 두 동작은 음성 설정·마이크·손쉬운 사용 권한 없이 쓸 수 있으며 macOS 화면 녹화 권한은 필요합니다. 일반 renderer API 요청으로 원격 화면 경로를 직접 호출할 수 없습니다.

## 로컬 보정 저장

`calibration-store.mjs`는 검증을 통과한 모델의 means/scales/weights와 모델·파이프라인 버전·카메라 ID/해상도·모니터 ID/원점/크기/배율/회전을 이 앱 origin의 로컬 저장소에 저장합니다. 서버 API로 전송하지 않습니다. 최대 8개 환경이며 원시 시선·랜드마크·얼굴 영상은 포함하지 않습니다. 불러온 모델은 미검증 상태로 시작하고, 새로운 5개 목표점의 검증을 통과해야 좌표와 자동 알림이 활성화됩니다. 환경 불일치·손상 파일·검증 실패 시 저장값으로 자동 판정을 켜지 않습니다. Dock/workArea 변화는 전체 모니터 보정의 식별 조건에 포함하지 않습니다.
