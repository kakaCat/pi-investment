#!/usr/bin/env bash
# REQ-260924104605-ad0a 盯盘渠道演练脚本（FR-1 回归断言 + 回滚/恢复 + 探针）
#
# 用法：
#   watch-channel-drill.sh assert        断言渠道表 = 新映射（10 行盯盘群 / 3 行原群），不符退出 1
#   watch-channel-drill.sh rollback      10 行盯盘频道 webhook 改回原群（…172829）
#   watch-channel-drill.sh restore       10 行盯盘频道 webhook 改回盯盘群（…60d879）
#   watch-channel-drill.sh probe <标签>  经 Agent OS 发一条探针消息到 watch_symbol 并打印投递日志
#
# Agent OS 每次发送都实时读 notification_channels（service.Send→GetChannelByCode，
# 无缓存），UPDATE 立即生效——回滚/恢复不需要重启任何服务。
# 注意：macOS 自带 bash 3.2 在 UTF-8 locale 下会把多字节字符并入变量名解析，
# 因此脚本内变量一律写 ${var} 花括号形式（尤其变量后紧跟中文标点时）。
set -euo pipefail

PSQL=${PSQL:-"psql -h 127.0.0.1 -U yunpeng -d quant_investment"}
AGENT_OS=${AGENT_OS_URL:-http://127.0.0.1:8080}
WATCH_WEBHOOK='https://open.feishu.cn/open-apis/bot/v2/hook/c990fd00-399b-487d-98ac-7257c660d879'
LEGACY_WEBHOOK='https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-35fc-4142-90c2-3a3933172829'
WATCH_CODES="'watch_symbol','watch_market','entry_signal','exit_manage','risk_stop','position_ops','rule_governance','market_state','system_ops','decision_inbox'"
LEGACY_CODES="'alerts','reports','trading'"

cmd_assert() {
  local watch_new watch_legacy legacy_ok
  watch_new=$($PSQL -Atc "SELECT count(*) FROM notification_channels WHERE code IN ($WATCH_CODES) AND config->>'webhook' = '$WATCH_WEBHOOK'")
  watch_legacy=$($PSQL -Atc "SELECT count(*) FROM notification_channels WHERE code IN ($WATCH_CODES) AND config->>'webhook' = '$LEGACY_WEBHOOK'")
  legacy_ok=$($PSQL -Atc "SELECT count(*) FROM notification_channels WHERE code IN ($LEGACY_CODES) AND config->>'webhook' = '$LEGACY_WEBHOOK'")
  echo "盯盘频道→盯盘群(…60d879): $watch_new/10；盯盘频道→原群(…172829): $watch_legacy/10；原频道→原群: $legacy_ok/3"
  if [ "$watch_new" = "10" ] && [ "$watch_legacy" = "0" ] && [ "$legacy_ok" = "3" ]; then
    echo "ASSERT OK：渠道表 = 新映射（FR-1）"
  else
    echo "ASSERT FAIL：渠道表偏离新映射" >&2
    $PSQL -c "SELECT code, right(config->>'webhook',6) AS webhook_tail FROM notification_channels ORDER BY code"
    exit 1
  fi
}

cmd_update() { # $1=目标 webhook $2=动作名
  $PSQL -c "UPDATE notification_channels
            SET config = jsonb_set(config, '{webhook}', '\"$1\"'), updated_at = now()
            WHERE code IN ($WATCH_CODES)"
  echo "$2 完成：10 行盯盘频道 webhook → …${1: -6}"
}

cmd_probe() { # $1=标签
  local tag="${1:-probe}" title resp log_id
  title="【演练】盯盘渠道探针 $tag"
  resp=$(curl -sS -X POST "$AGENT_OS/api/v1/notifications/send" \
    -H 'Content-Type: application/json' \
    -d "{\"channel\":\"watch_symbol\",\"title\":\"$title\",\"content\":\"回滚演练探针（${tag}）。收到本消息的群 = 当前 watch_symbol 指向的群。\",\"urgency\":\"low\"}")
  echo "发送响应: $resp"
  log_id=$(echo "$resp" | sed -n 's/.*"log_id"[":]*"\([^"]*\)".*/\1/p')
  sleep 1
  $PSQL -c "SELECT c.code, right(c.config->>'webhook',6) AS webhook_tail, l.status, l.sent_at
            FROM notification_logs l JOIN notification_channels c ON c.id = l.channel_id
            WHERE l.id = '$log_id'::uuid"
}

case "${1:-}" in
  assert)   cmd_assert ;;
  rollback) cmd_update "$LEGACY_WEBHOOK" "回滚" ;;
  restore)  cmd_update "$WATCH_WEBHOOK" "恢复" ;;
  probe)    cmd_probe "${2:-}" ;;
  *) echo "用法: $0 assert|rollback|restore|probe <标签>" >&2; exit 2 ;;
esac

