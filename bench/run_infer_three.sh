#!/usr/bin/env bash
set -euo pipefail

export LMUData=${LMUData:-/mnt/data/gk/LMUData}
export PYTHONUSERBASE=${PYTHONUSERBASE:-/mnt/data/gk/.pyuser}

python3 /mnt/data/gk/VLMEvalKit/run_api.py \
  --data DREAM-1K_8frame moviechat1k_breakpoint_8frame moviechat1k_global_8frame_limit0.01 \
  --model tool-agent \
  --base-url ${AGENT_BASE_URL:-http://127.0.0.1:18080/v1} \
  --key ${AGENT_KEY:-sk-admin} \
  --mode infer \
  --api-nproc ${API_NPROC:-16} \
  --timeout ${API_TIMEOUT:-300} \
  --retry ${API_RETRY:-2} \
  --max-samples ${MAX_SAMPLES:-50} \
  --work-dir ${WORK_DIR:-/mnt/data/gk/outputs}

