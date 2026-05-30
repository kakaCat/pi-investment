#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# 量化流程测试运行器
#
# 一键运行所有流水线相关测试：
#   - quantsys-v2 后端 E2E 全链路测试
#   - quantsys-v2 daemon 桥接层测试
#   - quantsys-v2 信号/盈亏/经验单元测试
#   - TypeScript Agent 经验工具测试
#
# 用法:
#   ./scripts/run-quant-flow-tests.sh          # 运行全部
#   ./scripts/run-quant-flow-tests.sh --python # 只运行 Python 测试
#   ./scripts/run-quant-flow-tests.sh --ts     # 只运行 TypeScript 测试
#   ./scripts/run-quant-flow-tests.sh --e2e    # 只运行 E2E 测试
#   ./scripts/run-quant-flow-tests.sh --quick  # 快速模式（跳过慢测试）
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
QUANT_DIR="$PROJECT_ROOT/quantsys-v2"
VENV_DIR="$PROJECT_ROOT/.venv-py313"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# ── 解析命令行参数 ──────────────────────────────────────────────────────────

RUN_PYTHON=false
RUN_TYPESCRIPT=false
RUN_E2E=false
QUICK_MODE=false
RUN_ALL=true

for arg in "$@"; do
    case $arg in
        --python)   RUN_PYTHON=true; RUN_ALL=false ;;
        --ts)       RUN_TYPESCRIPT=true; RUN_ALL=false ;;
        --e2e)      RUN_E2E=true; RUN_ALL=false ;;
        --quick)    QUICK_MODE=true ;;
        --help|-h)
            echo "量化流程测试运行器"
            echo ""
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --python   只运行 Python (quantsys-v2) 后端测试"
            echo "  --ts       只运行 TypeScript Agent 测试"
            echo "  --e2e      只运行 E2E 端到端测试"
            echo "  --quick    快速模式（跳过慢测试）"
            echo "  --help     显示帮助"
            exit 0
            ;;
    esac
done

if [ "$RUN_ALL" = true ]; then
    RUN_PYTHON=true
    RUN_TYPESCRIPT=true
    RUN_E2E=true
fi

# ── 环境检查 ────────────────────────────────────────────────────────────────

echo -e "${CYAN}═════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  量化流程测试运行器${NC}"
echo -e "${CYAN}═════════════════════════════════════════════════════════════════${NC}"
echo ""

# 检查 PostgreSQL
if pg_isready -h 127.0.0.1 &>/dev/null; then
    echo -e "${GREEN}✓${NC} PostgreSQL 连接正常"
else
    echo -e "${RED}✗${NC} PostgreSQL 不可用 — 请启动数据库"
    exit 1
fi

# 检查 Python 虚拟环境
if [ -f "$VENV_DIR/bin/activate" ]; then
    echo -e "${GREEN}✓${NC} Python 虚拟环境存在"
else
    echo -e "${RED}✗${NC} Python 虚拟环境不存在: $VENV_DIR"
    exit 1
fi

# 检查测试数据库
if psql -h 127.0.0.1 -U mac -lqt 2>/dev/null | grep -q quant_test; then
    echo -e "${GREEN}✓${NC} 测试数据库 quant_test 存在"
else
    echo -e "${YELLOW}⚠${NC} 测试数据库 quant_test 不存在，正在创建..."
    createdb -h 127.0.0.1 -U mac quant_test 2>/dev/null || {
        echo -e "${RED}✗${NC} 无法创建测试数据库"
        exit 1
    }
    echo -e "${GREEN}✓${NC} 测试数据库创建成功"
fi

# 检查 Node.js
if command -v node &>/dev/null; then
    NODE_VERSION=$(node -v)
    echo -e "${GREEN}✓${NC} Node.js $NODE_VERSION"
else
    echo -e "${RED}✗${NC} Node.js 不可用"
    exit 1
fi

echo ""

# ── 运行函数 ────────────────────────────────────────────────────────────────

run_pytest() {
    local test_name="$1"
    local test_path="$2"
    local extra_args="${3:-}"

    echo -e "${BLUE}▶${NC} $test_name"

    local cmd="cd $QUANT_DIR && source $VENV_DIR/bin/activate && PGDATABASE=quant_test python -m pytest $test_path -v --tb=short --no-cov $extra_args"

    local output
    output=$(eval "$cmd" 2>&1)
    local exit_code=$?
    echo "$output" | tail -5

    if echo "$output" | grep -q " FAILED "; then
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo -e "${RED}  ✗ FAILED${NC}"
    elif [ $exit_code -eq 0 ]; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo -e "${GREEN}  ✓ PASSED${NC}"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo -e "${RED}  ✗ FAILED (exit code: $exit_code)${NC}"
    fi
    echo ""
}

run_jest() {
    local test_name="$1"
    local test_pattern="$2"

    echo -e "${BLUE}▶${NC} $test_name"

    local cmd="cd $PROJECT_ROOT && npm run test -- --testPathPattern=\"$test_pattern\" --verbose 2>&1"

    if eval "$cmd" | tail -5 | grep -q "Tests:"; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo -e "${GREEN}  ✓ PASSED${NC}"
    else
        local exit_code=${PIPESTATUS[0]:-0}
        if [ $exit_code -eq 0 ]; then
            PASS_COUNT=$((PASS_COUNT + 1))
            echo -e "${GREEN}  ✓ PASSED${NC}"
        else
            FAIL_COUNT=$((FAIL_COUNT + 1))
            echo -e "${RED}  ✗ FAILED${NC}"
        fi
    fi
    echo ""
}

# ── 运行 Python 测试 ────────────────────────────────────────────────────────

if [ "$RUN_PYTHON" = true ]; then
    echo -e "${YELLOW}── Python (quantsys-v2) 后端测试 ──${NC}"
    echo ""

    # L1 数据管道测试
    run_pytest "L1 数据管道层" \
        "tests/e2e/test_l1_data_pipeline.py" \
        ""

    # L2 因子工厂测试
    run_pytest "L2 因子工厂层" \
        "tests/e2e/test_l2_factor_factory.py" \
        ""

    # L3 模型层测试
    run_pytest "L3 模型层" \
        "tests/e2e/test_l3_model_layer.py" \
        ""

    # L2→L4 策略桥接测试
    run_pytest "L2→L4 策略桥接" \
        "tests/e2e/test_strategy_factor_bridge.py" \
        ""

    # 全流程集成测试
    run_pytest "全流程集成 (Phase A→D)" \
        "tests/e2e/test_full_pipeline_e2e.py" \
        ""

    # E2E 全链路测试（信号→经验，后半段）
    run_pytest "E2E 信号→经验全链路" \
        "tests/e2e/test_quant_flow_e2e.py" \
        ""

    # 信号追踪测试
    run_pytest "信号追踪单元测试" \
        "tests/test_signal_tracking.py" \
        ""

    # 策略表现统计测试
    run_pytest "策略表现统计测试" \
        "tests/test_strategy_performance_repository.py" \
        ""

    # 经验积累测试
    run_pytest "经验积累器测试" \
        "tests/test_experience_accumulator.py" \
        ""

    # Daemon 桥接测试
    run_pytest "Daemon 桥接层测试" \
        "tests/daemon/test_daemon_pipeline.py" \
        ""

    if [ "$QUICK_MODE" = false ]; then
        # 信号执行调度器测试
        run_pytest "信号执行调度器测试" \
            "tests/test_signal_execution_scheduler.py" \
            ""

        # 信号处理器测试
        run_pytest "信号处理器测试" \
            "tests/test_signal_processor.py" \
            ""

        # 信号监控测试
        run_pytest "信号监控测试" \
            "tests/test_signal_monitoring.py" \
            ""

        # 信号集成测试
        run_pytest "信号集成测试" \
            "tests/integration/test_signal_to_order_flow.py" \
            ""

        # 信号执行集成测试
        run_pytest "信号执行集成测试" \
            "tests/test_signal_execution_integration.py" \
            ""
    fi
fi

# ── 运行 TypeScript 测试 ─────────────────────────────────────────────────────

if [ "$RUN_TYPESCRIPT" = true ]; then
    echo -e "${YELLOW}── TypeScript Agent 测试 ──${NC}"
    echo ""

    run_jest "经验查询工具测试" \
        "query-experience-tool.test"

    run_jest "经验写入工具测试" \
        "experience-write-tool.test"

    run_jest "经验管理器测试" \
        "experience-manager.test"

    if [ "$QUICK_MODE" = false ]; then
        run_jest "流水线集成测试" \
            "pipeline-integration.test" 2>/dev/null || true
    fi
fi

# ── 运行 E2E 测试 ────────────────────────────────────────────────────────────

if [ "$RUN_E2E" = true ] && [ "$RUN_PYTHON" = false ]; then
    echo -e "${YELLOW}── E2E 端到端测试 ──${NC}"
    echo ""

    run_pytest "E2E 全链路测试 (独立运行)" \
        "tests/e2e/test_quant_flow_e2e.py" \
        "-m integration -v"
fi

# ── 汇总 ─────────────────────────────────────────────────────────────────────

echo -e "${CYAN}═════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  测试结果汇总${NC}"
echo -e "${CYAN}═════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}通过: $PASS_COUNT${NC}"
echo -e "  ${RED}失败: $FAIL_COUNT${NC}"

if [ $FAIL_COUNT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}  🎉 所有流水线测试通过！${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}  ❌ $FAIL_COUNT 个测试组失败，请检查上面的输出${NC}"
    exit 1
fi
