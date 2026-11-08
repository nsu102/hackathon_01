# Mac에서 사용하기 · v0.6

`학습 보조 실행.command`를 실행하면 메뉴 막대와 반투명 오버레이가 열린다. Python 3.13+/Node.js 22+, 기존 OpenRouter 키가 필요하다. 처음 신경망 모델을 준비할 때 다운로드가 발생한다. 소스 실행과 v0.7 Apple Silicon DMG 개발 설치판을 제공한다. Apple Developer ID 서명·공증은 포함하지 않는다.

## 메뉴 막대

상단의 눈 안에 음성 파형이 있는 아이콘을 누르고 **설정…**을 고른다. 같은 메뉴에서 감지 켜기/끄기, 이탈 알림, 잔소리 음소거, 휴식, 도우미 열기, 종료를 선택할 수 있다. 닫기(×)는 창만 숨기고 감지는 유지한다. Cmd+Shift+Space로 다시 표시할 수 있다.

SVG 원본: `overlay/assets/StudySignalTemplate.svg`. macOS 표시에는 투명 16×16/72dpi와 32×32/144dpi 템플릿 PNG를 함께 사용한다. 이름의 Template/@2x 규칙과 setTemplateImage를 적용해 밝고 어두운 메뉴 막대에 대응한다. [Electron Tray](https://www.electronjs.org/docs/latest/api/tray), [NativeImage](https://www.electronjs.org/docs/latest/api/native-image).

## 감지

학습 시작 시 카메라를 준비한다. 화면 가운데를 약 2초 바라보면 기본 화면 방향 기준을 잡는다. 설정의 감도는 여유롭게/보통/민감하게다. 자리나 거리가 바뀌면 **화면 기준 다시 잡기**를 누른다. ‘측정 불가’일 때는 이유가 표시되며 알림을 보내지 않는다. 실제 인지적 집중을 판정하는 기능으로 보지 않는다.

정밀 위치 보정은 실험 설정이며 기본 감지와 음성 질문에 필수적이지 않다. 통과한 정밀 보정은 이 Mac에 저장되고 같은 환경이면 5점 재검증으로 사용할 수 있다.

## 음성

‘음성과 선택 모니터 화면을 OpenRouter로 전송’ 체크 → 말하기 시작 → 질문 → 말 끝내고 보내기. 화면 범위는 선택 모니터 전체 또는 매번 문단 선택이다. 전체 모니터 옵션은 그 모니터 전체를 전송한다. 기본 OS 음성 읽기는 설정에서 끌 수 있다.

버튼은 카메라 없이도 쓸 수 있다. 마이크·화면 녹화 권한은 필요하다. 개발 버전은 시스템 권한 목록에 Electron으로 나타날 수 있다. 권한 변경 후 재시작이 필요하면 앱에 안내가 나온다. 운영체제의 권한 스위치를 앱이 대신 바꾸지 않는다.

전역 Cmd+Shift+Enter는 선택 기능이다. 누르는 동안 녹음하고 놓으면 전송하며 손쉬운 사용/입력 모니터링 권한이 추가로 필요할 수 있다. 최대 20초 watchdog은 자동 보내기가 아니라 녹음 폐기다. 얼굴 영상·녹음·화면을 기본 기록에 보관하지 않는다.

## v0.7 DMG 설치판

`Study-Signal-0.7.0-arm64.dmg`는 Apple Silicon(M1 이상), macOS 15 이상용이다. DMG를 열어 Study Signal.app을 Applications로 옮겨 실행한다. Electron·Python·Torch와 기본 UniGaze-L 모델을 포함해 Node.js/Homebrew/Python을 별도로 설치하지 않는다.

설정은 **⌘,**(앱에 포커스가 있을 때) 또는 메뉴 막대 아이콘 → 설정에서 연다. OpenRouter 키를 입력하고 ‘저장 후 앱 다시 시작’을 누른다. 키 입력칸을 비우면 기존 키를 유지한다. 진행 중인 학습은 종료한 뒤 저장한다.

설치판의 설정·보정·학습 기록은 `~/Library/Application Support/Study Signal`에 보관한다. API 키는 이 위치의 `.env`에 현재 사용자만 읽도록 저장하며 DMG에 포함하지 않는다. 정밀 보정과 센서 원본의 기존 저장 정책은 그대로다.

이 빌드는 ad-hoc 무결성 서명이며 Apple Developer ID 서명·Apple 공증은 포함하지 않는다. 다른 Mac이나 인터넷 배포 환경의 Gatekeeper 동작을 공증된 상용 설치판과 같다고 보장하지 않는다. 모델의 연구·비상업용 라이선스 고지는 앱 안에 포함한다.

개발자가 다시 빌드하려면 신경망 환경에 `scripts/macos-build-requirements.txt`를 설치하고, Playwright와 Chrome이 있는 Python으로 `python3 scripts/build_macos.py`를 실행한다. `--reuse-service`는 독립 서비스 재빌드를 생략한다. 빌드 작업은 `.build`에만 모으고 완성 DMG는 상위 outputs에 생성한다.
