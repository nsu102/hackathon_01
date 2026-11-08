#!/bin/zsh
set -eu
infra_dir="${0:A:h}"
exec ssh -F "$infra_dir/ssh_config.private" -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L 127.0.0.1:8001:127.0.0.1:8000 snu-gpu
