# 运维指引：盯盘通知频道（webhook 分群）

> REQ-260924104605-ad0a · 2026-09-24 · 面向运维/值班同学，步骤均可复制执行

## 1. 这是什么

盯盘通知（触发卡、超时/升级聚合卡、处置结论回执）经 **Agent OS（:8080）** 按「逻辑频道码 →
webhook」路由到飞书群。映射存在 PostgreSQL `public.notification_channels.config` JSON 里，
**每次发送实时读库（无缓存），改表立即生效，不需要重启任何服务**。

当前映射（FR-1 终态）：

| 频道 code（10 个） | 目标群 | webhook 尾号 |
|---|---|---|
| watch_symbol / watch_market / entry_signal / exit_manage / risk_stop / position_ops / rule_governance / market_state / system_ops / decision_inbox | 盯盘专用群 | `…60d879` |
| alerts / reports / trading | 原共享群（不动） | `…172829` |

quantsys-v2 侧只认逻辑频道码（`variables["os_channel"]`），**不认 webhook**；换群/回滚只改
Agent OS 这张表，应用代码零改动。

## 2. 日常操作（脚本都在 scripts/watch-channel-drill.sh）

```bash
S=agent-dh/docs/requirements/REQ-260924104605-ad0a/scripts/watch-channel-drill.sh

# 体检：断言渠道表 = 新映射（10 行盯盘群 / 3 行原群），不符退出 1
$S assert

# 发一条探针消息到 watch_symbol 并打印投递日志（验证当前落到哪个群）
$S probe my-check        # 标签用 ASCII（经部分 shell 层传参会损坏多字节字符）
```

## 3. 换群（新机器人 → 新群）

1. 在飞书新群添加自定义机器人，拿到新 webhook；
2. 更新 10 行盯盘频道：
   ```sql
   UPDATE notification_channels
   SET config = jsonb_set(config, '{webhook}', '"<新 webhook>"'), updated_at = now()
   WHERE code IN ('watch_symbol','watch_market','entry_signal','exit_manage','risk_stop',
                  'position_ops','rule_governance','market_state','system_ops','decision_inbox');
   ```
3. `$S probe after-change` 发探针，确认投递日志 `status=sent` 且新群可见；
4. `$S assert` 会失败（它钉死的是 …60d879）——换群后请同步更新脚本里的 `WATCH_WEBHOOK`。

## 4. 回滚（盯盘群出问题，临时并回原群）

```bash
$S rollback      # 10 行盯盘频道 webhook → …172829（原共享群）
$S probe rollback-check
# 确认原群可见、日志 status=sent
$S restore       # 事后恢复 → …60d879（盯盘群）
$S probe restore-check
$S assert        # 必须回到 ASSERT OK
```

回滚只影响 10 个盯盘频道；alerts/reports/trading 三行始终不动。

## 5. 排查「消息没收到」

1. `$S assert` 看映射是否被改乱；
2. 查投递日志：
   ```sql
   SELECT c.code, l.status, l.error, l.created_at
   FROM notification_logs l JOIN notification_channels c ON c.id = l.channel_id
   ORDER BY l.created_at DESC LIMIT 10;
   ```
   - `status=failed`：`error` 列有飞书返回（机器人被删/群解散/限流）；
   - 日志都没有：问题在 Agent OS 之前（quantsys-v2 facade 降级直飞书时会标
     `degraded_reason=agent_os_unreachable`，查 quantsys-v2 日志）；
3. Agent OS 健康：`curl -s http://127.0.0.1:8080/api/v1/notifications/channels | head`。

## 6. 已验证基线（2026-09-24 回滚演练）

- 回滚后探针 `ef464627-2068-48e4-ac80-e4546e348a80`：watch_symbol → …172829，status=sent（原群可见）；
- 恢复后探针 `e8a7c137-091c-4861-a9dd-8244255a0619`：watch_symbol → …60d879，status=sent（盯盘群可见）；
- 演练前后 `$S assert` 均 ASSERT OK（13 行映射正确）。

