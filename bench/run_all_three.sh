#!/usr/bin/env bash
set -euo pipefail

export LMUData=${LMUData:-/mnt/data/gk/LMUData}
export PYTHONUSERBASE=${PYTHONUSERBASE:-/mnt/data/gk/.pyuser}

set -a
source /mnt/data/gk/VLMEvalKit/.env
source /mnt/data/gk/pretrained_models/doubao-1.8
set +a

export JUDGE_BASE_URL=${JUDGE_BASE_URL:-$DOUBAO_BASE_URL}
export JUDGE_API_KEY=${JUDGE_API_KEY:-$DOUBAO_API_KEY}

python3 /mnt/data/gk/VLMEvalKit/run_api.py \
  --data DREAM-1K_8frame moviechat1k_breakpoint_8frame moviechat1k_global_8frame_limit0.01 \
  --model tool-agent \
  --base-url ${AGENT_BASE_URL:-http://127.0.0.1:18080/v1} \
  --key ${AGENT_KEY:-sk-admin} \
  --mode all \
  --api-nproc ${API_NPROC:-16} \
  --timeout ${API_TIMEOUT:-300} \
  --retry ${API_RETRY:-2} \
  --max-samples ${MAX_SAMPLES:-50} \
  --work-dir ${WORK_DIR:-/mnt/data/gk/outputs} \
  --judge ${JUDGE_MODEL:-$DOUBAO_MODEL} \
  --judge-base-url ${JUDGE_BASE_URL} \
  --judge-api-nproc ${JUDGE_NPROC:-16} \
  --judge-timeout ${JUDGE_TIMEOUT:-300} \
  --judge-retry ${JUDGE_RETRY:-2}

