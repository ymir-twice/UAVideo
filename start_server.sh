#!/bin/bash
# ============================================
# 视频理解智能体 - 一键启动脚本
# ============================================

set -e  # 遇到错误立即退出

# 配置
export HOST=${HOST:-"0.0.0.0"}
export PORT=${PORT:-"8800"}
export AUTH_TOKEN=${AUTH_TOKEN:-"sk-admin"}

# 豆包配置
export CORE_LLM_BASE_URL=${CORE_LLM_BASE_URL:-"https://ark.cn-beijing.volces.com/api/v3"}
export CORE_LLM_API_KEY=${CORE_LLM_API_KEY:-"3c664f72-0209-488f-b48d-eb20aaf656ef"}
export CORE_LLM_MODEL=${CORE_LLM_MODEL:-"doubao-seed-1-8-251228"}
export CORE_LLM_TIMEOUT=${CORE_LLM_TIMEOUT:-"180"}

# vLLM配置（本地部署的模型）
export VLLM_BASE_URL=${VLLM_BASE_URL:-"http://localhost:8008/v1"}
export VLLM_API_KEY=${VLLM_API_KEY:-"EMPTY"}
export VLLM_CAPTION_MODEL=${VLLM_CAPTION_MODEL:-"Qwen3-VL-4B"}
export VLLM_ASR_MODEL=${VLLM_ASR_MODEL:-"Qwen3-ASR-1.7B"}

# 缓存目录
export CACHE_DIR=${CACHE_DIR:-"/mnt/data/gk/.cache/tool_agent"}
export SESSION_STORAGE_DIR=${SESSION_STORAGE_DIR:-"/mnt/data/gk/.cache/tool_agent/sessions"}

# 其他配置
export MAX_FRAMES=${MAX_FRAMES:-"16"}
export CAPTION_ENABLED=${CAPTION_ENABLED:-"true"}
export OCR_ENABLED=${OCR_ENABLED:-"true"}
export ASR_ENABLED=${ASR_ENABLED:-"true"}

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  视频理解智能体 - 启动脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查Python
echo -e "${YELLOW}[1/5] 检查Python环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到python3${NC}"
    exit 1
fi
PYTHON_CMD="python3"
if command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi
echo -e "${GREEN}  Python: $($PYTHON_CMD --version)${NC}"

# 检查pip
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo -e "${YELLOW}  pip未找到，尝试安装必要依赖...${NC}"
    ${PYTHON_CMD} -m pip install python-dotenv requests fastapi uvicorn pydantic --user -q 2>/dev/null || true
fi

# 检查依赖
echo -e "${YELLOW}[2/5] 检查依赖...${NC}"
${PYTHON_CMD} -c "import dotenv; import fastapi; import uvicorn; import pydantic; print('  核心依赖: OK')" 2>/dev/null || {
    echo -e "${YELLOW}  安装依赖中...${NC}"
    ${PYTHON_CMD} -m pip install python-dotenv fastapi uvicorn pydantic --user -q
}

# 检查vLLM连接（可选）
echo -e "${YELLOW}[3/5] 检查vLLM服务...${NC}"
if curl -s --max-time 2 "${VLLM_BASE_URL%:*}" > /dev/null 2>&1; then
    echo -e "${GREEN}  vLLM服务: 可连接${NC}"
    echo -e "${GREEN}    URL: ${VLLM_BASE_URL}${NC}"
    echo -e "${GREEN}    Caption模型: ${VLLM_CAPTION_MODEL}${NC}"
    echo -e "${GREEN}    ASR模型: ${VLLM_ASR_MODEL}${NC}"
else
    echo -e "${YELLOW}  vLLM服务: 未连接（将使用备选方案）${NC}"
    echo -e "${YELLOW}    如需使用vLLM，请先启动: vllm serve ${VLLM_CAPTION_MODEL}${NC}"
fi

# 检查豆包API（必须）
echo -e "${YELLOW}[4/5] 检查豆包API...${NC}"
if curl -s --max-time 5 \
    -H "Authorization: Bearer ${CORE_LLM_API_KEY}" \
    -H "Content-Type: application/json" \
    "${CORE_LLM_BASE_URL}/models" > /dev/null 2>&1; then
    echo -e "${GREEN}  豆包API: 可连接${NC}"
    echo -e "${GREEN}    URL: ${CORE_LLM_BASE_URL}${NC}"
    echo -e "${GREEN}    Model: ${CORE_LLM_MODEL}${NC}"
else
    echo -e "${RED}  错误: 无法连接豆包API${NC}"
    echo -e "${RED}  请检查网络和API配置${NC}"
    exit 1
fi

# 检查服务是否已在运行
echo -e "${YELLOW}[5/5] 检查服务状态...${NC}"
EXISTING_PID=$(lsof -ti:${PORT} 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    if curl -s --max-time 3 http://localhost:${PORT}/health > /dev/null 2>&1; then
        echo -e "${GREEN}  服务已在运行 (PID: ${EXISTING_PID})${NC}"
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  服务状态${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "${GREEN}  服务地址: http://localhost:${PORT}${NC}"
        echo -e "${GREEN}  健康检查: http://localhost:${PORT}/health${NC}"
        echo ""
        echo -e "${YELLOW}  服务已在运行，无需重复启动${NC}"
        echo -e "${YELLOW}  如需重启，请先运行: pkill -f tool_agent.server${NC}"
        exit 0
    else
        echo -e "${YELLOW}  端口${PORT}被占用但服务无响应，将重启...${NC}"
        lsof -ti:${PORT} 2>/dev/null | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
else
    echo -e "${GREEN}  端口${PORT}空闲${NC}"
fi

# 创建缓存目录
mkdir -p "${CACHE_DIR}"
mkdir -p "${SESSION_STORAGE_DIR}"
echo -e "${GREEN}  缓存目录: ${CACHE_DIR}${NC}"

# 启动服务
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  启动服务...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}配置汇总:${NC}"
echo -e "  服务地址: ${HOST}:${PORT}"
echo -e "  认证Token: ${AUTH_TOKEN}"
echo -e "  vLLM服务: ${VLLM_BASE_URL}"
echo -e "  豆包API: ${CORE_LLM_MODEL}"
echo ""

cd /mnt/data/gk

${PYTHON_CMD} -m tool_agent.server
