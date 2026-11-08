#!/bin/zsh
set -eu
cd "$(dirname "$0")/product"
echo '제품 페이지: http://127.0.0.1:8088'
echo '종료: 이 터미널에서 Control+C'
exec python3 -m http.server 8088 --bind 127.0.0.1
