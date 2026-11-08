# 사례·논문 검토와 제품 반영

확인: 2026-11-07. 범위: 사용자가 제시한 자료의 기획 검토. 원문에서 방법·평가·제약을 확인했으며 코드 재현이나 독립적인 앱 성능 검증을 수행한 것은 아니다. 아래의 ‘반영’은 우리 제품의 설계 결정이다.

## 앱·프로젝트 사례

| 사례 | 공식 설명에서 확인한 범위 | 제품에 반영 | 이 자료가 증명하지 않는 것 |
|---|---|---|---|
| [FOCUS — UC Irvine](https://projects.eng.uci.edu/projects/2025-2026/facial-orientation-and-concentration-understanding-system-focus) | Python/PySide6, MediaPipe/OpenCV, PnP 머리 방향, EAR/MAR·PERCLOS 등의 시간 지표를 규칙으로 결합. 알림·세션 대시보드 | 신호 품질과 시간 누적을 분리한 상태 엔진, 세션 회고 | 우리 사용자에 대한 집중 정확도나 학습 효과 |
| [Focus Buddy](https://chromewebstore.google.com/detail/focus-buddy/enefnbeijiedpklbfihgdlhknicikmam) | 홍채 특징·SVM으로 화면 응시 여부를 분류한다고 설명. 약 3초 이탈 알림, 복귀 해제와 추적 토글 | 지속 이탈/복귀에 각각 시간을 두고 사용자가 잔소리 제어 | ‘화면 밖’이 항상 ‘인지적으로 비집중’이라는 결론 |
| [Focus Monitor](https://chromewebstore.google.com/detail/focus-monitor/pememjimlfldeaomcdfnebhofglpjhmm) | 얼굴·눈 개방·머리 방향, 보정·민감도·세션 타임라인·내보내기 제공을 설명 | 개인 설정, 판정 근거와 unknown을 포함한 시간 기록 | 점수 하나의 타당도나 생산성 개선 효과 |

앱 목록의 기능은 제작자 측 설명으로 확인한 것이다. 리뷰 점수나 설치 수를 정확도 평가로 사용하지 않는다. 경쟁 앱의 화면/코드를 그대로 복제하는 계획은 아니다.

## Hutt 등 — 인지적 집중을 추정할 근거와 범위

**Webcam-based eye tracking to detect mind wandering and comprehension errors**, *Behavior Research Methods* 56, 1–17 (2024), 온라인 공개 2023-01-10. [DOI](https://doi.org/10.3758/s13428-022-02040-x), [저자 제공 원고](https://learninganalytics.upenn.edu/ryanbaker/BRMWebcamGaze.pdf).

대학생 105명과 Prolific 참가자 173명의 읽기/이해 과제에서 WebGazer 시선과 과제 관련 영역 정보를 사용했다. 과제 무관 사고의 기준에는 참가자 자기보고를 사용한다. 참가자 단위 검증과 데이터 집단 간 검증을 다룬다. 일반적인 모든 데스크톱 작업의 딴생각을 확실히 식별한다는 연구로 읽지 않는다.

검토 위치: 원고 pp. 11–12의 보정/과제/자기보고, pp. 15–18의 영역 특징·분류·검증, pp. 31–34의 개입·오류·일반화 한계.

반영: 초기 제품에서는 관측 가능한 이탈을 관리한다. 후속 인지 모델은 읽기 과제·자기보고·화면 맥락으로 별도 학습/평가한다. 사람/세션을 넘는 분할, 단순 기준과의 비교, 오탐·누락 비용을 사용한다. 불확실한 추정은 잔소리보다 확인 질문·자가 설명 같은 가벼운 지원으로 연결한다.

## Saxena 등 — 좌표 정확도와 실시간성의 구분

**Deep learning models for webcam eye tracking in online experiments**, *Behavior Research Methods* 56, 3487–3503 (2024), 온라인 공개 2023-08-22. [출판사 원문](https://doi.org/10.3758/s13428-023-02190-6), [공개 분석 코드](https://github.com/ShreshthSaxena/Eye_Tracking_Analysis).

118명 완료 자료에서 품질 등의 기준으로 제외 후 65명을 분석했다. 기기/시선 보정이 있었고 웹캠 녹화를 **오프라인**으로 처리했다. FAZE의 보고 결과는 정확도 약 2.4°, precision 약 0.47°다. 두 수치는 다른 지표이며, 우리 앱의 픽셀 오차나 인지적 집중 정확도가 아니다. 분석에서 영역을 크게 잡으면 분류가 나아지고, 모델별 계산 비용에도 차이가 난다.

검토 위치: Methods의 Participants/Procedure/Data treatment, Results의 Fixation/Zone classification, Discussion.

반영: 보정과 별도 검증을 필수로 하고 큰 학습 영역부터 지원한다. 정확도·유효율·지연을 함께 평가한다. 논문 수치를 제품 문구로 전용하지 않는다. 실시간 속도와 안경·조명·카메라 조건은 우리 장비에서 다시 확인한다.

## WebGazer — 엔진 후보 검토

[공식 페이지](https://webgazer.cs.brown.edu/), [공식 저장소](https://github.com/brownhci/WebGazer).

일반 웹캠으로 브라우저 페이지의 시선 위치를 추정하고 사용자 상호작용을 보정에 활용한다. Electron 후보로 시험할 수 있지만 데스크톱 전체와 캡처 이미지에 쓰려면 좌표계를 연결해야 한다. 클릭 좌표와 추정한 시선 좌표는 로그에서 구분한다.

공식 페이지는 2026-02-24 이후 업데이트를 보장하지 않는다고 안내하며 GPLv3를 명시한다. 따라서 유지보수·배포 조건까지 고려한 후보로 평가하고, 곧바로 폐쇄형 상용 제품의 확정 엔진으로 선언하지 않는다. 현재 MediaPipe 기반 개인 보정과 같은 시험 조건에서 비교한다.

## 설계에서 구분할 검증

| 검증 질문 | 적절한 자료 | 부적절한 대체 |
|---|---|---|
| 시선 좌표가 맞는가? | 보정과 다른 목표의 오차, 영역 적중률, 유효율 | 좌표가 출력됐다는 로그 |
| 이탈 알림이 맞는가? | 응시/이탈/필기 등 시나리오 라벨, 오탐·누락·지연 | 카메라 프레임이 들어온다는 사실 |
| 화면 응시 중 딴생각인가? | 과제에 맞는 자기보고·행동 근거와 분리 검증 | 화면 응시 여부를 정답 라벨로 사용 |
| 설명이 맞는가? | 질문과 올바른 캡처 영역의 연결, 내용의 정답성 | LLM이 자연스럽게 말한다는 사실 |
| 학습에 도움이 되는가? | 별도 평가한 이해/복습 결과·사용 경험 | 응시 시간·사용 시간 증가 |

사용자의 ‘시선만으로도 추정할 수 있다는 연구가 있다’는 지적을 반영해 인지 추정 가능성을 계획에 포함했다. 다만 첫 릴리즈의 관측 기반 기능과 후속 연구 모델의 성능 주장을 분리했다.
