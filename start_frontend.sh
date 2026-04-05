#!/bin/bash
# ============================================
# VideoBuddy 前端 - 启动脚本
# ============================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  VideoBuddy 前端 - 启动脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 Node.js
echo -e "${YELLOW}[1/3] 检查 Node.js 环境...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误: 未找到 Node.js${NC}"
    echo -e "${YELLOW}请先安装 Node.js: https://nodejs.org/${NC}"
    exit 1
fi
echo -e "${GREEN}  Node.js: $(node --version)${NC}"
echo -e "${GREEN}  npm: $(npm --version)${NC}"

# 检查依赖
echo -e "${YELLOW}[2/3] 检查依赖...${NC}"
cd /mnt/data/gk/tool_agent/web
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}  安装依赖中...${NC}"
    npm install
fi
echo -e "${GREEN}  依赖: OK${NC}"

# 检查后端服务
echo -e "${YELLOW}[3/3] 检查后端服务...${NC}"
if curl -s --max-time 3 http://localhost:8800/health > /dev/null 2>&1; then
    echo -e "${GREEN}  后端服务: 可连接 (http://localhost:8800)${NC}"
else
    echo -e "${YELLOW}  后端服务: 未连接${NC}"
    echo -e "${YELLOW}  提示: 请先启动后端服务 (bash start_server.sh)${NC}"
fi

# 启动服务
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  启动前端服务...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}访问地址:${NC}"
echo -e "  本地: http://localhost:8801"
echo -e "  公网: http://js3.blockelite.cn:15577"
echo ""

npm run dev
