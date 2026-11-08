# Study Signal v0.6 구조

```
카메라 → MediaPipe 얼굴 정렬 → 같은 Mac의 UniGaze-L/MPS 워커
  ├─ ScreenPresence: 시선·머리 방향 + 짧은 현재 기준 → 화면 응시/이탈/unknown
  │    → FocusController: 8/20/2/90초 → 시각 알림/OS 음성/집계 이벤트
  └─ 선택 ScreenGazeModel: 9점 개인 회귀 + 5점 검증 → 실험 좌표
       → 검증된 계수만 로컬 저장, 재실행 시 5점 검증

말하기 버튼 또는 선택 단축키 → native 고정 캡처(자체 창 숨김)
  → WebM/Opus → 명시적 보내기 → 전체 선택 모니터 또는 수동 크롭
  → 로컬 context-help → OpenRouter STT → 기존 Vision 설명 → 대화/OS 음성

메뉴 막대 Tray → 제한된 app:action → 설정/감지/음소거/휴식
```

`screen-presence.mjs`는 픽셀 보정과 독립적이다. 첫 안정 구간의 각도 중앙값을 기준으로 하고 이탈 중에는 자동으로 새 기준을 만들지 않는다. 원시 좌표가 없다고 unknown으로 강제하지 않지만 얼굴/눈 품질·지연·위치 변화는 unknown으로 분리한다. 기본 각도 임계값은 초기 제품 설정이며 실측 성능이 아니다.

`native-voice.cjs`는 캡처/녹음 요청 상태·세션·20초/60초 기한을 관리한다. 버튼 입력은 두 번째 명시적 클릭으로 release한다. 키보드 경로만 uiohook과 손쉬운 사용 권한을 요구한다. 캡처·음성은 요청 동안 메모리에서만 유지한다. DIP와 이미지 픽셀은 `dipToPixels`로 구분한다.

`tray.cjs`는 macOS 템플릿 이미지와 컨텍스트 메뉴를 만들고, 원시 센서 없이 6상태 집계만 받는다. `preload.cjs`의 app:action은 정해진 명령만 전달한다. 창 닫기는 숨김, 명시적 메뉴 종료는 모델/백엔드/키 훅을 정리한다. backgroundThrottling을 끄고 숨겨진 동안에도 감지 타이밍을 유지한다.

`last_hour/context_help.py`는 voice 입력을 전사한 뒤 텍스트와 캡처를 설명 모델에 전달한다. `target.selection=screen`은 정밀 시선 보정 ID를 요구하지 않는다. 기존 text screen-help/assist API는 호환용으로 유지하며 메인 UI에서는 사용하지 않는다. 음성·이미지 프롬프트를 로그/학습 예시에 저장하지 않는다.

Watch 수집 서버는 별도 경로다. 원격 GPU·SSH·파인튜닝은 사용하지 않는다. API 키·로컬 인증 토큰은 main/서버에만 두고 renderer에 노출하지 않는다.


v0.7 설치판: `runtime.cjs`가 앱 리소스(서비스·모델)와 쓰기 가능한 Application Support(개인 .env·기록·Chromium 저장소)를 분리한다. `scripts/bundled_service.py`는 PyInstaller 독립 바이너리 진입점이다. OpenRouter용 공개 CA 인증서와 Torchvision stable 연산 파일을 포함한다. `connection-ui.mjs`는 공개 연결 상태만 읽고, 입력한 키는 저장 IPC 후 비우며 localStorage에 저장하지 않는다. DMG 빌드는 개인 .env·기록을 복사하지 않는다.
