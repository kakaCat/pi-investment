#!/bin/bash
# 因子数据补录脚本（2026-08-22 ~ 2026-08-27）
# 
# 用法：
#   bash scripts/backfill-factors.sh
#   bash scripts/backfill-factors.sh 2026-08-22 2026-08-27  # 自定义日期范围
#
# 原理：
#   调用 quantsys-v2 的 POST /api/compute/factors，计算并写入数据库
#   注意：只补录交易日，跳过周末和节假日

set -euo pipefail

API_URL="${QUANTSYS_V2_URL:-http://localhost:5001}"
START_DATE="${1:-2026-08-22}"
END_DATE="${2:-2026-08-27}"

# A股主要成分股（代表性样本，避免全量4000+股票耗时过长）
SYMBOLS=(
  "600519" "000858" "600036" "601318" "000333"  # 白酒、五粮液、招行、平安、美的
  "600276" "002594" "002475" "600887" "002271"  # 恒瑞、比亚迪、立讯精密、伊利、东方雨虹
  "601888" "600900" "000651" "601012" "300750"  # 中免、长江电力、格力、隆基绿能、宁德时代
  "300059" "002415" "603259" "688981" "688599"  # 东方财富、海康威视、药明康德、中芯国际、天合光能
)

echo "[*] 开始补录因子数据"
echo "    日期范围: $START_DATE ~ $END_DATE"
echo "    样本股票: ${#SYMBOLS[@]} 只"
echo "    API 地址: $API_URL"
echo ""

# 遍历日期范围（简化：只按日历日递增，API内部会处理非交易日）
current_date="$START_DATE"
success_count=0
fail_count=0

while [[ "$current_date" < "$END_DATE" ]] || [[ "$current_date" == "$END_DATE" ]]; do
  # 跳过周末（简化判断）
  day_of_week=$(date -j -f "%Y-%m-%d" "$current_date" "+%u" 2>/dev/null || echo 0)
  if [[ "$day_of_week" -ge 6 ]]; then
    echo "[-] $current_date (周末，跳过)"
    current_date=$(date -j -v+1d -f "%Y-%m-%d" "$current_date" "+%Y-%m-%d")
    continue
  fi
  
  echo "[*] 补录 $current_date ..."
  
  # 批量计算（一次请求包含所有样本股）
  payload=$(jq -n --arg date "$current_date" --argjson symbols "$(printf '%s\n' "${SYMBOLS[@]}" | jq -R . | jq -s .)" \
    '{symbols: $symbols, date: $date}')
  
  response=$(curl -s -X POST "$API_URL/api/compute/factors" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1 || echo '{"success":false,"error":"curl_failed"}')
  
  if echo "$response" | jq -e '.success' >/dev/null 2>&1; then
    factor_count=$(echo "$response" | jq -r '.results | length')
    echo "    ✓ 完成，计算 $factor_count 只股票"
    ((success_count++))
  else
    error=$(echo "$response" | jq -r '.error // "unknown"' 2>/dev/null || echo "parse_error")
    echo "    ✗ 失败: $error"
    ((fail_count++))
  fi
  
  # 下一天
  current_date=$(date -j -v+1d -f "%Y-%m-%d" "$current_date" "+%Y-%m-%d")
  
  # 限速（避免打爆API）
  sleep 1
done

echo ""
echo "[✓] 补录完成"
echo "    成功: $success_count 天"
echo "    失败: $fail_count 天"

if [[ $fail_count -gt 0 ]]; then
  exit 1
fi
