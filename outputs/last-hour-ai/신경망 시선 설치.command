#!/bin/zsh
set -eu
cd "$(dirname "$0")"
PYTHON_FOR_GAZE="$(command -v python3.13 || command -v python3)"
echo 'UniGaze 로컬 추론 환경을 준비해요. 공식 모델은 연구·비상업용 라이선스예요.'
"$PYTHON_FOR_GAZE" scripts/setup_neural_gaze.py
