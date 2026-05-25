#!/bin/bash

# Web-Frontend 风控检查页面修复 - 服务重启脚本
# 用于重启后端和前端服务

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="/Users/mac/Documents/ai/pi-investment"
QUANTSYS_DIR="${PROJECT_ROOT}/quantsys-v2"
FRONTEND_DIR="${PROJECT_ROOT}/web-frontend"

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}服务重启脚本${NC}"
echo -e "${BOLD}========================================${NC}\n"

# 检查目录是否存在
if [ ! -d "$QUANTSYS_DIR" ]; then
    echo -e "${RED}✗ 后端目录不存在: $QUANTSYS_DIR${NC}"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}✗ 前端目录不存在: $FRONTEND_DIR${NC}"
    exit 1
fi

# 停止现有服务
echo -e "${YELLOW}[1/4] 停止现有服务...${NC}"

# 停止后端
echo "  停止后端服务..."
pkill -f "python.*api/server.py" 2>/dev/null && echo -e "${GREEN}  ✓ 后端服务已停止${NC}" || echo -e "${BLUE}  ℹ 后端服务未运行${NC}"

# 停止前端
echo "  停止前端服务..."
pkill -f "vite.*web-frontend" 2>/dev/null && echo -e "${GREEN}  ✓ 前端服务已停止${NC}" || echo -e "${BLUE}  ℹ 前端服务未运行${NC}"

# 等待端口释放
echo -e "\n${YELLOW}[2/4] 等待端口释放...${NC}"
sleep 2

# 检查端口是否释放
if lsof -i :5001 > /dev/null 2>&1; then
    echo -e "${RED}  ✗ 端口 5001 仍被占用${NC}"
    lsof -i :5001
    exit 1
else
    echo -e "${GREEN}  ✓ 端口 5001 已释放${NC}"
fi

if lsof -i :3001 > /dev/null 2>&1; then
    echo -e "${RED}  ✗ 端口 3001 仍被占用${NC}"
    lsof -i :3001
    exit 1
else
    echo -e "${GREEN}  ✓ 端口 3001 已释放${NC}"
fi

# 启动后端服务
echo -e "\n${YELLOW}[3/4] 启动后端服务...${NC}"
cd "$QUANTSYS_DIR"

# 检查 Python
if ! command -v python &> /dev/null; then
    echo -e "${RED}  ✗ Python 未安装${NC}"
    exit 1
fi

# 启动后端（后台运行）
nohup python api/server.py > logs/server.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}  ✓ 后端服务已启动 (PID: $BACKEND_PID)${NC}"
echo "  日志文件: $QUANTSYS_DIR/logs/server.log"

# 等待后端启动
echo "  等待后端启动..."
for i in {1..10}; do
    if curl -s http://127.0.0.1:5001/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ 后端服务启动成功${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}  ✗ 后端服务启动超时${NC}"
        echo "  查看日志: tail -f $QUANTSYS_DIR/logs/server.log"
        exit 1
    fi
    sleep 1
done

# 启动前端服务
echo -e "\n${YELLOW}[4/4] 启动前端服务...${NC}"
cd "$FRONTEND_DIR"

# 检查 npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}  ✗ npm 未安装${NC}"
    exit 1
fi

# 启动前端（后台运行）
nohup npm run dev > logs/dev.log 2>&1 &
FRONTEND_PID=$!
echo -e "${GREEN}  ✓ 前端服务已启动 (PID: $FRONTEND_PID)${NC}"
echo "  日志文件: $FRONTEND_DIR/logs/dev.log"

# 等待前端启动
echo "  等待前端启动..."
for i in {1..15}; do
    if curl -s http://127.0.0.1:3001 > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ 前端服务启动成功${NC}"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "${RED}  ✗ 前端服务启动超时${NC}"
        echo "  查看日志: tail -f $FRONTEND_DIR/logs/dev.log"
        exit 1
    fi
    sleep 1
done

# 验证服务
echo -e "\n${BOLD}========================================${NC}"
echo -e "${BOLD}服务验证${NC}"
echo -e "${BOLD}========================================${NC}\n"

# 验证后端
echo -e "${YELLOW}验证后端服务...${NC}"
BACKEND_HEALTH=$(curl -s http://127.0.0.1:5001/api/health)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 后端健康检查通过${NC}"
    echo "  URL: http://127.0.0.1:5001"
else
    echo -e "${RED}✗ 后端健康检查失败${NC}"
fi

# 验证前端
echo -e "\n${YELLOW}验证前端服务...${NC}"
if curl -s http://127.0.0.1:3001 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 前端服务正常${NC}"
    echo "  URL: http://127.0.0.1:3001"
else
    echo -e "${RED}✗ 前端服务异常${NC}"
fi

# 测试风险检查接口
echo -e "\n${YELLOW}测试风险检查接口...${NC}"
RISK_CHECK_RESPONSE=$(curl -s -X POST http://127.0.0.1:5001/api/risk/check \
    -H "Content-Type: application/json" \
    -d '{"accountValue": 1000000}')

if echo "$RISK_CHECK_RESPONSE" | jq -e '.checks' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 风险检查接口正常${NC}"

    # 检查新增字段
    FIRST_CHECK=$(echo "$RISK_CHECK_RESPONSE" | jq -r '.checks[0]' 2>/dev/null)
    if [ "$FIRST_CHECK" != "null" ] && [ "$FIRST_CHECK" != "" ]; then
        HAS_CURRENT_PRICE=$(echo "$FIRST_CHECK" | jq 'has("current_price")')
        HAS_VAR_95=$(echo "$FIRST_CHECK" | jq 'has("var_95")')
        HAS_VOLATILITY=$(echo "$FIRST_CHECK" | jq 'has("volatility")')
        HAS_MAX_DRAWDOWN=$(echo "$FIRST_CHECK" | jq 'has("max_drawdown")')

        if [ "$HAS_CURRENT_PRICE" = "true" ] && [ "$HAS_VAR_95" = "true" ] && \
           [ "$HAS_VOLATILITY" = "true" ] && [ "$HAS_MAX_DRAWDOWN" = "true" ]; then
            echo -e "${GREEN}✓ 新增字段验证通过${NC}"
            echo "  - current_price: ✓"
            echo "  - var_95: ✓"
            echo "  - volatility: ✓"
            echo "  - max_drawdown: ✓"
        else
            echo -e "${YELLOW}⚠ 部分新增字段缺失${NC}"
            [ "$HAS_CURRENT_PRICE" = "true" ] && echo "  - current_price: ✓" || echo "  - current_price: ✗"
            [ "$HAS_VAR_95" = "true" ] && echo "  - var_95: ✓" || echo "  - var_95: ✗"
            [ "$HAS_VOLATILITY" = "true" ] && echo "  - volatility: ✓" || echo "  - volatility: ✗"
            [ "$HAS_MAX_DRAWDOWN" = "true" ] && echo "  - max_drawdown: ✓" || echo "  - max_drawdown: ✗"
        fi
    else
        echo -e "${BLUE}ℹ 无持仓数据，跳过字段验证${NC}"
    fi
else
    echo -e "${RED}✗ 风险检查接口异常${NC}"
fi

# 总结
echo -e "\n${BOLD}========================================${NC}"
echo -e "${BOLD}重启完成${NC}"
echo -e "${BOLD}========================================${NC}\n"

echo -e "${GREEN}✓ 所有服务已重启${NC}\n"

echo "服务信息:"
echo "  后端 PID: $BACKEND_PID"
echo "  前端 PID: $FRONTEND_PID"
echo ""
echo "访问地址:"
echo "  后端 API: http://127.0.0.1:5001"
echo "  前端页面: http://127.0.0.1:3001"
echo "  风控检查: http://127.0.0.1:3001/risk-check"
echo ""
echo "日志文件:"
echo "  后端日志: tail -f $QUANTSYS_DIR/logs/server.log"
echo "  前端日志: tail -f $FRONTEND_DIR/logs/dev.log"
echo ""
echo "停止服务:"
echo "  后端: kill $BACKEND_PID"
echo "  前端: kill $FRONTEND_PID"
echo "  或者: pkill -f 'python.*api/server.py' && pkill -f 'vite.*web-frontend'"
echo ""
echo -e "${YELLOW}建议：${NC}"
echo "  1. 访问 http://127.0.0.1:3001/risk-check 测试功能"
echo "  2. 运行完整测试: ./test-risk-check-api.sh"
echo "  3. 查看日志确认无错误"
