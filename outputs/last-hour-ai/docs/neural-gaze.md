> v0.6: 정밀 화면 좌표 보정은 실험 설정으로 이동했습니다. 기본 응시/이탈은 신경망 방향과 짧은 정면 기준을 사용하며 9점 회귀와 독립적입니다. 음성 질문은 선택 모니터 화면 또는 수동 문단을 사용합니다.

# UniGaze-L 엔진 선정과 통합 · 2026-11-08

사용자가 이전 방식으로 올바르게 보정했지만 중앙 113 / 최대 393 DIP px로 실패해, 최신 공개 모델을 찾아 교체하도록 요청했다. 기존 엔진의 임계값 조정 대신 얼굴 영상 기반 사전학습 모델을 도입했다.

| 후보 | 확인 결과 | 결정 |
|---|---|---|
| UniGaze, WACV 2026 | 공식 논문·추론 코드·B/L/H 공개 safetensors 존재 | L/16 Joint를 M4 Metal FP16으로 통합 |
| CapStARE, 2025 | 논문과 코드 확인. 검토한 저장소에서 즉시 쓸 공개 체크포인트를 확인하지 못함 | 이번 실행 경로에서 제외 |
| GazeFormer-MoE, 2026 | 공식 학습 구현 확인. 검토한 저장소는 모델 경로가 준비돼 있어야 하는 형태 | 이번 실행 경로에서 제외 |
| GazeFollower2 | 검색 결과는 있었지만 검토 시 실제 저장소 접근이 404 | 재현 가능한 파일을 확보하지 못해 제외 |
| RealEye Light Open | 브라우저 화면 좌표 라이브러리. 공개판은 이미지 픽셀/기하 특징의 개인 회귀 | 사전학습 신경망 교체 요구와 구분 |

논문별 평가 데이터·프로토콜이 다르므로 모든 기준에서 1위라는 ‘SOTA’ 보장은 하지 않는다. 공개 가중치·Mac 실행·실제 통합 가능성을 확인한 최신 연구 모델을 선택했다. 논문의 각도 오차를 사용자의 픽셀 정확도로 대체하지 않는다.

## 구현

1. renderer가 카메라 프레임을 canvas에 고정한다. MediaPipe 검출과 신경망이 **같은 프레임**을 사용한다.
2. 눈꼬리·코 날개 6개 앵커와 얼굴 영역으로 UniGaze 공식 video demo의 정규화 절차를 적용한다. 출력 패치는 224×224 RGB, 정규화 초점거리 960, 거리 600mm이며 ImageNet mean/std를 적용한다. 카메라 내재값은 공식 예제처럼 근사값이므로 개인 화면 보정이 필요하다.
3. `last_hour/neural_gaze.py`가 같은 Mac의 별도 프로세스에서 엄격히 로드한 UniGaze-L을 Metal FP16으로 실행한다. 이미지·앵커는 로컬 IPC/stdio 메모리로만 전달한다. HTTP·OpenRouter 전송이나 원본 저장을 하지 않는다.
4. 예측한 pitch/yaw를 역정규화하고, 시선 기울기·상호작용 항·머리 방향을 개인 화면 좌표에 보정한다. 기존 홍채 위치 회귀로 자동 전환하지 않는다.
5. 기존 9＋5점 프로토콜, 점당 유효 12샘플, 120/220 DIP px·80% 기준은 유지한다. 검증 실패 시 집중 알림을 켜지 않는다.
6. 600ms가 지난 추론은 유효 시선으로 쓰지 않는다. 질문 버퍼에는 처리 지연을 되돌려 실제 프레임 시각을 전달한다. 이전 프레임의 신호를 현재 시선으로 신선하게 포장하지 않는다.

기존 검은 보정 화면은 밝은 문서에 가까운 중성 배경으로 바꿨다. 메뉴/Dock 때문에 하단이 잘리는 문제는 workArea에 보정 창을 열고 전체 모니터 DIP와 따로 매핑하도록 수정했다.

## 검증과 남은 일

- 공식 Hugging Face revision과 SHA-256: `last_hour/neural_assets/model-manifest.json`.
- 모델 구조: 공식 체크포인트의 모든 키·형상이 일치함을 strict load로 확인.
- M4 Metal 벤치마크: [L/B, FP32/FP16](qa/unigaze-benchmark.json). 합성 입력이며 사용자 정확도 시험 아님.
- 실제 MediaPipe 공개 얼굴 예제→정규화→로컬 워커 추론: [결과](qa/unigaze-smoke.json). 사람의 화면 응시 정답이 있는 평가는 아님.
- 실제 Electron에서 UniGaze-L/Metal 모델 로딩과 새 보정 안내를 확인. 새 사용자 보정 오차는 아직 미측정.
- 기존 학습/음성 UI 회귀 9개 흐름 통과. 원격 GPU/SSH/LLM 파인튜닝은 재개하지 않음.

## 1차 출처

- [UniGaze 공식 저장소와 공개 모델 안내](https://github.com/ut-vision/UniGaze), [WACV 2026 논문](https://openaccess.thecvf.com/content/WACV2026/papers/Qin_UniGaze_Towards_Universal_Gaze_Estimation_via_Large-scale_Pre-Training_WACV_2026_paper.pdf)
- [공식 Hugging Face 체크포인트](https://huggingface.co/UniGaze/UniGaze-models/tree/main), [공식 라이선스](https://github.com/ut-vision/UniGaze/blob/main/LICENSE.txt)
- [CapStARE 공식 코드](https://github.com/toukapy/capsStare), [GazeFormer 공식 코드](https://github.com/AIPMLab/Gazeformer)
- [RealEye Light Open 공식 구현](https://github.com/RealEye-io/webcam-eyetracker-light-open)
- [MediaPipe→Dlib 앵커 대응](https://github.com/PeizhiYan/Mediapipe_2_Dlib_Landmarks/blob/main/mediapipe2dlib/mp2dlib.py)

공식 모델은 연구·비상업용 라이선스다. 상용 배포는 모델 권리자와 별도 확인이 필요하며 소스 배포물에 라이선스를 보존한다.


## 보정 재사용

검증을 통과한 보정 계수는 이 Mac에 자동 저장한다. 같은 모델·모니터·카메라 환경에서 재실행하면 기존 계수로 5점 재검증만 수행한다. 9점 학습 샘플이나 얼굴 영상을 저장하지 않는다. 다른 환경이면 새로 보정하며, 검증 전에는 좌표·자동 알림을 활성화하지 않는다. 설정에서 저장된 보정을 삭제할 수 있다.
