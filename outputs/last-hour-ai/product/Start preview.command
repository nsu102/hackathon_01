#!/bin/zsh
set -eu
cd "$(dirname "$0")"
echo 'Study Signal: http://127.0.0.1:8088'
echo 'Press Control+C in this terminal to stop the preview.'
exec python3 -m http.server 8088 --bind 127.0.0.1
