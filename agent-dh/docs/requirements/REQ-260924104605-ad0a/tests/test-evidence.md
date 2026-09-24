# 测试证据：盯盘通知改版（REQ-260924104605-ad0a）

> 2026-09-24 · 主检出 /Users/yunpeng/pi-investment（合并后）· 服务已重启生效

## 1. 单元/回归测试

```
$ cd quantsys-v2 && PYTHONPATH=$PWD POLARS_MAX_THREADS=4 venv/bin/python -m pytest tests/notification/ tests/watch/ -q
============================== 89 passed in 0.43s ==============================
```

覆盖：
- tests/notification/test_agent_channel_registration.py（4 例，联调修复钉案）
- tests/notification/test_watch_receipt_routing.py / test_watch_target_routing.py（t3 路由）
- tests/notification/test_legacy_render_compat.py（5 例，旧渲染兼容）
- tests/watch/test_receipt_grouping.py（9 例，聚合）
- tests/watch/test_close_receipt.py（8 例，三要素+路由标签）
- tests/application/test_sla_job.py（含 group_cards 统计）

## 2. 集成验证五步（真实链路，2026-09-24 盘中）

### ① 触发落盯盘群、alerts 群无
规则 217（600519 恒真 price>1）触发：
```
watch_symbol | sent | 盯盘触发 - 600519 | wh=60d879 | 2026-09-24 14:18:14
alerts 群同时段新增：0
```

### ② 停 Agent OS 降级直飞书
launchctl bootout 停 :8080 后规则 219（000001）触发，日志链：
```
14:20:07 发送通知（带降级） primary=agent fallback=feishu
14:20:07 AgentChannel: Connection refused localhost:8080
14:20:07 主渠道发送失败，降级到备用渠道（error=无法连接到 Agent OS）
14:20:08 飞书发送成功 / 降级渠道发送成功 channel=feishu
```
metadata 降级标注（degraded/degraded_reason=agent_os_unreachable）由
test_agent_channel_registration 钉住。Agent OS 已恢复（health_ok=true）。

### ③ close 收三要素卡
POST /api/watch/todos/39/close（terminal=handled, action_kind=no_action, next_condition=...）：
```
receipt.sent=true；落点 watch_symbol→60d879（14:26:11 sent）
卡片：结论：已处置（不动）/ 原因：t7 集成验证③… / 后续意见：NEXT price<1150 重新评估买点
```

### ④ 3 超时→1 张聚合卡
造 3 条 L3 超时待办（600030/600031/600032），SLA 巡检：
```
scanned:13 timeout:3 alerts:3 group_cards:1
投递日志：risk_stop | sent | 超时回执 | 60d879 | 14:33:02（仅 1 张）
watch_receipts：todo 41/42/43 同 batch:timeout:202609241433，channel=risk_stop，sent
```

### ⑤ pytest 全绿
见 §1（89 passed）。

## 3. 回滚演练（t6，同日早些时候）

```
$ scripts/watch-channel-drill.sh assert   → ASSERT OK（10/10→60d879，3/3→172829）
$ rollback                                → UPDATE 10
$ probe rollback-old-group                → log ef464627：watch_symbol→172829 sent（原群可见）
$ restore                                 → UPDATE 10
$ probe restore-watch-group               → log e8a7c137：watch_symbol→60d879 sent（盯盘群可见）
$ assert                                  → ASSERT OK
```

## 4. 终态核验

- drill assert：盯盘 10/10→…60d879、盯盘→原群 0/10、legacy 3/3→…172829
- Agent OS :8080 health_ok=true；quantsys-v2 pid 46747 health_ok=true
- 合成数据已清理（规则 217/218/219 删除，待办 39/41/42/43 删除）
