#!/usr/bin/env bash
set -euo pipefail
: "${VLLM_API_KEY:?Set VLLM_API_KEY in the GPU server environment}"
model="${BASE_MODEL:-Qwen/Qwen3-4B-Instruct-2507}"
adapter="${1:?Usage: bash infra/serve_lora.sh /absolute/path/to/trained/adapter}"
[[ -f "$adapter/adapter_config.json" ]] || { echo 'Trained adapter_config.json not found'; exit 1; }
exec vllm serve "$model" --host 127.0.0.1 --port 8000 --served-model-name study-base --enable-lora --lora-modules "study-tutor=$adapter" --max-model-len 4096 --gpu-memory-utilization 0.6
