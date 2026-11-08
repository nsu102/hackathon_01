#!/bin/zsh
set -eu
project_dir="${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v node >/dev/null 2>&1; then
  for node_dir in "$HOME"/.nvm/versions/node/*/bin(N); do
    export PATH="$node_dir:$PATH"
  done
fi
cd "$project_dir/overlay"
if [[ ! -d node_modules/electron ]]; then
  npm ci
fi
exec npm start
