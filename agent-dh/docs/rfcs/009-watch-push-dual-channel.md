# RFC 009：盯盘推送双通道方案（direct 直推 / agent 判断分流）

- 状态：Draft（待评审）
- 日期：2026-08-31
- 作者：investor (w-5b8aac2a)
- 关联：quantsys-v2 WatchEngine / agent-dh lifecycle / notification 插件

## 1. 背景与问题

实测确认（2026-08-31）：盯盘推送全链路断链。

- watch_triggers 1410 条触发记录，`notified` 全部 = false，日志零条唤醒记录
- 根因 1：`quantsys-v2/.env` 的 `AGENT_API_URL=http://127.0.0.1:3002` 指向已停运的旧 agent-ts Wake Gateway（3002 无进程）
- 根因 2：当前 Agent 在 DSH 13080，无 `/wake` 端点（POST 405），agent-dh 插件无 wake 事件处理实现
- 根因 3：WS 广播目标 5003 无监听（前端实时刷新失效）

**新需求**：盯盘触发应分两种处理，避免所有触发都唤醒 Agent 烧 token：

| 类型 | 含义 | 示例 |
|---|---|---|
| **direct（价格提醒）** | 纯价格/条件通知，无需 Agent 判断 | 某股突破 20 元、跌破止损位提醒 |
| **agent（需要判断）** | 触发后需 Agent 综合分析再决策/通知 | 持仓浮亏达止损线、突破后是否减仓 |

## 2. 现状架构

```
WatchEngine tick()（5001，交易时段 60s/10s）
  └─ WatchNotifier.notify(rule, cond, quote, result)
       ├─ AgentNotificationService → POST {AGENT_API_URL}/wake   ← 死链 3002
       ├─ WS 广播 → 127.0.0.1:5003/broadcast/market_data          ← 无监听
       └─ WatchTriggerRepository.record → watch_triggers          ✅ 唯一正常
```

可用现成通道（无需新建）：

- **OS 记忆库信箱 + lifecycle 轮询投递**（"schedule 暂时用"）：OS 8080 `POST /api/v1/memory` 写入 tag=`office:reminder:{window}` 的记忆 → lifecycle `setupOsReminderPoller` 每 60s 轮询 → 找到在线窗口 `followup()` 注入（离线时自动创建新窗口代执行）→ 防重复投递（delivered 留痕）
- **飞书 webhook 直发**：`cordis.patch.yml` notification 插件已配置 `feishuWebhooks['*']`，quantsys-v2 也可直接读 `.env` 的 `FEISHU_WEBHOOK_URL` 调 webhook（`feishu_service.py` 已有 `send_text/send_alert`）

## 3. 方案设计

### 3.1 规则模型扩展：notify_mode

`quant.watch_rules` 增加 `notify_mode` 字段（`direct` / `agent`，默认 `direct`）：

```sql
ALTER TABLE quant.watch_rules ADD COLUMN notify_mode varchar(16) NOT NULL DEFAULT 'direct';
```

- **direct**：触发后引擎直接推飞书，不唤醒 Agent，零 token 消耗
- **agent**：触发后写入 OS 信箱唤醒 Agent，Agent 判断后决策/通知（消耗 token）

存量规则迁移：止损/止盈/持仓类（如歌尔 id38、万集 id52、中铝 id60）→ `agent`；纯价格提醒 → `direct`。

### 3.2 双通道推送

```
WatchEngine tick() 触发
  │
  ├─ notify_mode=direct ──→ WatchNotifier.direct()
  │                          ├─ FeishuService.send_text（webhook 直发，0 token）
  │                          └─ record(notified=true, channel=direct)
  │
  └─ notify_mode=agent ───→ WatchNotifier.agent()
                             ├─ OS 信箱写入（memory_write, tag=office:reminder:w-xxx, content={task,prompt,fired_at}）
                             ├─ lifecycle 60s 轮询 → followup 注入在线窗口（离线→代执行窗口）
                             ├─ Agent 收到【盯盘触发】→ 查行情/持仓 → 判断 → feishu_notify 决策
                             └─ record(notified=true, channel=agent, agent_response=...)
```

### 3.3 改造点清单

**quantsys-v2（Python）**

| 文件 | 改动 |
|---|---|
| `watch_rule_repository.py` | ORM 加 `notify_mode` 字段 |
| `watch_engine/notifier.py` | `notify()` 按 `rule.notify_mode` 分流 direct/agent；direct 调 FeishuService |
| `agent_notification_service.py` | 新增 `notify_agent_via_mailbox(event, data, window)`：写 OS 记忆库（POST /api/v1/memory，tag=`office:reminder:{window}`），替代死链 wake；保留原 wake 方法兼容 |
| `watch_async.py` CRUD | 规则创建/更新支持 `notify_mode` |
| `.env` | `AGENT_API_URL` 保留但不再指向 3002；新增 `FEISHU_WEBHOOK_URL`（复用 cordis.patch.yml 的 webhook 值） |

**agent-dh（TypeScript）**

| 文件 | 改动 |
|---|---|
| `packages/intelligence/.../WatchManageTool.ts` | watch_manage 增加 `notify_mode` 参数（direct/agent） |
| `packages/lifecycle/src/index.ts` | （已具备）轮询投递直接复用；无改动 |
| `packages/notification` | 无需改动（Agent 判断后调 feishu_notify 已有） |

**OS 信箱写入端（quantsys 调 8080）**

```http
POST http://127.0.0.1:8080/api/v1/memory
{ "title": "watch trigger", "content": JSON.stringify({
    "task": "watch_triggered",
    "prompt": "【盯盘触发·需判断】...规则/价格/条件/消息...",
    "fired_at": "2026-08-31T15:21:40Z",
    "payload": {...}
  }),
  "namespace": "data",
  "tags": ["office:reminder:w-<窗口编码>"] }
```

lifecycle 轮询 `office:reminder:w-xxx` 自动接管投递（在线窗口 followup / 离线创建代执行窗口）。

## 4. 验证计划

1. 建 direct 测试规则（必触发条件）→ 观察飞书收到 + watch_triggers `notified=true, channel=direct`
2. 建 agent 测试规则（必触发）→ 观察 OS 信箱写入 → lifecycle 轮询 → 窗口收到【盯盘触发】→ Agent 响应 → 落库
3. 存量规则迁移确认（止损类=agent，价格提醒=direct）
4. 清理测试规则

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| lifecycle 轮询依赖在线窗口；离线时延迟 | 已有"创建新窗口代执行"兜底 |
| OS 8080 宕机时信箱写入失败 | lifecycle osWrite outbox 防丢机制；quantsys 侧记录失败重试 |
| 飞书 webhook 直发无 Agent 过滤 | direct 只用于纯价格提醒；需判断的必须 agent 模式 |
| 存量规则误分类 | 迁移时人工确认分类清单 |

## 6. 后续演进（不在本期）

- 5003 WS 广播补监听（前端实时刷新）
- direct 通道支持多 webhook/渠道配置
- agent 通道触发频率控制（cooldown 已存在，可调）

## 7. 实施中发现并根治的问题（2026-09-01）

| 问题 | 根因 | 修复 |
|---|---|---|
| FeishuService 初始化崩溃 | legacy `get_config()` 返回空 dict，`'dict' object has no attribute 'external'` | 改为读 pydantic settings（`.env FEISHU_WEBHOOK_URL`），direct 通道 E2E 验证通过 |
| structlog 调用 TypeError | `logger.error(..., event=event)` 中 `event` 是 structlog 保留关键字，与 kwargs 冲突 | 改名 `event_name=event`（agent_notification_service 4 处） |
| **OS memory Search 忽略 tag 参数**（关键） | `memory_web_repository.go` Search SQL 仅 `(title ILIKE $1 OR content ILIKE $1)`，无 tag 过滤；handler 不读 `tag` 参数 | Go 侧根治：handler 读 tag → `MemorySearchRequest.Tag` → SQL 加 `AND $n = ANY(tags)`（与 List 同款写法）；`LIMIT` 改参数化。agent-os 已重建重启（PID 39414） |

### 根治 tag 过滤的额外收益

修复前 lifecycle 轮询的 tag 参数完全被忽略，实际按全库 `q` 模糊匹配，存在两个隐藏 bug（修复后自动消除）：

1. **跨窗口误投递**：myWindow 查询 `q=reminder` 会命中全库所有含 "reminder" 的记录（无 tag 过滤），可能把 A 窗口的提醒投递给 B 窗口。修复后 `tag=office:reminder:w-xxx` 精确隔离。
2. **重复投递**：防重投的 exec 查询 `q=delivered` 同样全库匹配，投递标记超过 top_k(100) 时旧标记被挤出 → 已投递记录被再次投递。修复后 `tag=office:reminder:exec` 精确命中。

### 规避方案 → 根治方案的演进

- **当时（临时）**：quantsys 信箱 title 加 `watch_reminder` 可检索前缀 + lifecycle 用 `q=watch_reminder` 查询，绕过 tag 失效。
- **现在（根治后）**：tag 过滤真正生效，`q=watch_reminder&tag=office:reminder:watch` 双条件 AND 精确命中。title 前缀保留（无害，作为 q 命中条件）。

### 验证记录

- `go build ./...` + `go test ./...`（13 包全过；含新增 tag 透传回归用例）
- 实测 `q=tagtest&tag=office:reminder:watch` 只命中 watch tag 记录（3 组对照全部符合预期）
- agent 通道回归：写 watch 记录 → lifecycle 30 秒内投递 → `delivered` 留痕（executor=direct 在线窗口）✅
- 测试数据已清理（tagtest / 999999 / 000241 等）
