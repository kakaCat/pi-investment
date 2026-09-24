#!/bin/bash
set -e

echo "=== Workflow-PTC 修复诊断脚本 ==="
echo ""

# 1. 检查配置文件
echo "1. 检查 cordis.patch.yml 中的 workflow-ptc 配置："
grep -A 2 "workflow-ptc" .dsh-data/profiles/agent-dh/cordis.patch.yml || echo "配置未找到"
echo ""

# 2. 检查服务是否运行
echo "2. 检查服务状态："
if lsof -ti:13080 > /dev/null 2>&1; then
    echo "✓ 服务正在运行 (端口 13080)"
    
    # 3. 尝试通过 API 检查插件状态
    echo ""
    echo "3. 检查插件加载状态："
    if command -v curl > /dev/null 2>&1; then
        curl -s http://localhost:13080/api/plugins 2>/dev/null > /tmp/plugins.json || echo "API 请求失败"
        if [ -f /tmp/plugins.json ]; then
            if command -v jq > /dev/null 2>&1; then
                echo "workflow-ptc 状态："
                jq '.plugins[] | select(.id == "workflow-ptc")' /tmp/plugins.json || echo "workflow-ptc 未加载"
            else
                echo "jq 未安装，显示原始响应："
                grep -o '"id":"workflow-ptc"[^}]*' /tmp/plugins.json || echo "workflow-ptc 未找到"
            fi
        fi
    else
        echo "curl 未安装，跳过 API 检查"
    fi
else
    echo "✗ 服务未运行"
fi

echo ""
echo "=== 修复建议 ==="
echo ""
echo "方案 1: 重启服务（推荐）"
echo "  cd agent-dh"
echo "  ./scripts/restart-with-build.sh"
echo ""
echo "方案 2: 如果 workflow-ptc 仍然 disabled=true，手动修改配置"
echo "  编辑 .dsh-data/profiles/agent-dh/cordis.patch.yml"
echo "  确保有："
echo "    - id: workflow-ptc"
echo "      disabled: false"
echo ""
echo "方案 3: 检查 agent preset 是否覆盖了配置"
echo "  查看 .dsh-data/.agent-presets/investment/cordis.patch.yml"
echo ""
