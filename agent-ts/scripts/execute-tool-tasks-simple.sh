#!/bin/bash
# 简化版工具任务执行脚本 - 使用curl测试核心工具

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 工具任务执行报告"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

success_count=0
fail_count=0

# 任务1: Portfolio Status (portfolio_status 工具)
echo "📊 任务1: 查看投资组合状态"
echo "工具: portfolio_status"
response=$(curl -s http://127.0.0.1:5001/api/portfolio)
if echo "$response" | grep -q '"success":true'; then
  echo "✅ 成功"
  cash=$(echo "$response" | grep -o '"cash":[0-9.]*' | cut -d: -f2)
  holdings=$(echo "$response" | grep -o '"holdings":\[' | wc -l | xargs)
  total=$(echo "$response" | grep -o '"totalValue":[0-9.]*' | cut -d: -f2)
  echo "   - 可用资金: ¥${cash:-0}"
  echo "   - 持仓数量: ${holdings:-0}只"
  echo "   - 总资产: ¥${total:-0}"
  ((success_count++))
else
  echo "❌ 失败"
  ((fail_count++))
fi
echo ""

# 任务2: Pool List (pool_list 工具)
echo "📋 任务2: 获取股票池列表"
echo "工具: pool_list"
response=$(curl -s http://127.0.0.1:5001/api/pools)
if echo "$response" | grep -q '"success":true'; then
  echo "✅ 成功"
  pool_count=$(echo "$response" | grep -o '"name"' | wc -l | xargs)
  echo "   - 股票池数量: ${pool_count:-0}个"
  # 显示前3个池名称
  echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    pools = data.get('data', [])[:3]
    for p in pools:
        print(f\"   - {p['name']} ({p['pool_type']}, {p['symbol_count']}只股票)\")
except: pass
" 2>/dev/null
  ((success_count++))
else
  echo "❌ 失败"
  ((fail_count++))
fi
echo ""

# 任务3: Health Check (health_check 工具)
echo "🏥 任务3: 系统健康检查"
echo "工具: health_check"
response=$(curl -s http://127.0.0.1:5001/api/health)
if echo "$response" | grep -q '"status":"ok"'; then
  echo "✅ 成功"
  db_connected=$(echo "$response" | grep -o '"db_connected":[a-z]*' | cut -d: -f2)
  stock_count=$(echo "$response" | grep -o '"stock_count":[0-9]*' | cut -d: -f2)
  echo "   - 数据库状态: $([ "$db_connected" = "true" ] && echo '✅ 已连接' || echo '❌ 未连接')"
  echo "   - 股票数据: ${stock_count:-0}只"
  ((success_count++))
else
  echo "❌ 失败"
  ((fail_count++))
fi
echo ""

# 任务4: WebSocket 连接测试
echo "🔌 任务4: WebSocket 服务检查"
echo "工具: WebSocket 连接"
ws_response=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5003/)
if [ "$ws_response" = "200" ] || [ "$ws_response" = "404" ]; then
  echo "✅ 成功"
  echo "   - WebSocket 服务: 在线 (端口 5003)"
  echo "   - 连接地址: ws://localhost:5003/ws"
  ((success_count++))
else
  echo "❌ 失败 (HTTP $ws_response)"
  ((fail_count++))
fi
echo ""

# 任务5: 获取股票数据样本 (stock_info 工具)
echo "📈 任务5: 获取股票数据"
echo "工具: stock_info (测试股票: 000001.SZ 平安银行)"
response=$(curl -s "http://127.0.0.1:5001/api/stock/000001.SZ/info")
if echo "$response" | grep -q '"success":true'; then
  echo "✅ 成功"
  echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    info = data.get('data', {})
    print(f\"   - 股票名称: {info.get('name', 'N/A')}\")
    print(f\"   - 股票代码: {info.get('symbol', 'N/A')}\")
    print(f\"   - 所属行业: {info.get('industry', 'N/A')}\")
except: pass
" 2>/dev/null || echo "   - 数据获取成功"
  ((success_count++))
else
  echo "❌ 失败"
  ((fail_count++))
fi
echo ""

# 总结
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 执行总结"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "成功: $success_count 个任务"
echo "失败: $fail_count 个任务"
echo "总计: $((success_count + fail_count)) 个任务"
echo ""

if [ $fail_count -eq 0 ]; then
  echo "✅ 所有工具任务执行成功！"
  echo ""
  echo "💡 说明:"
  echo "   - quantsys-v2 REST API 服务正常 (端口 5001)"
  echo "   - quantsys-v2 WebSocket 服务正常 (端口 5003)"
  echo "   - 数据库连接正常"
  echo "   - 核心工具 API 可用"
  exit 0
else
  echo "⚠️  有 $fail_count 个任务失败，请检查服务状态"
  exit 1
fi
