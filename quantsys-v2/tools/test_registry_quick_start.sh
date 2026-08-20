#!/bin/bash
# Quick start script for testing Agent OS Registry integration

echo "=== Agent OS Registry Integration - Quick Start ==="
echo ""

# 检查 Agent OS 是否运行
echo "1. Checking if Agent OS is running..."
if pgrep -f "agent-os" > /dev/null; then
    echo "   ✅ Agent OS is running"
else
    echo "   ❌ Agent OS is NOT running"
    echo "   Starting Agent OS..."
    cd /Users/yunpeng/pi-investment/agent-os
    nohup ./agent-os > agent-os.log 2>&1 &
    sleep 2
    if pgrep -f "agent-os" > /dev/null; then
        echo "   ✅ Agent OS started"
    else
        echo "   ❌ Failed to start Agent OS"
        exit 1
    fi
fi
echo ""

# 测试注册功能
echo "2. Testing registry integration..."
cd /Users/yunpeng/pi-investment/quantsys-v2
python tools/test_registry_integration.py
echo ""

# 查看注册的 Agents
echo "3. Checking registered agents..."
curl -s http://127.0.0.1:8080/api/v1/registry/agents/available | python -m json.tool
echo ""

echo "=== Test Complete ==="
echo ""
echo "Next steps:"
echo "  - Start quantsys-v2: python adapters/inbound/fastapi_app/main.py"
echo "  - Check logs for registry integration messages"
echo "  - Query agents: curl http://127.0.0.1:8080/api/v1/registry/agents/available"
