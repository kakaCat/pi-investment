# Agent Gateway 与 Session 资产化设计

- **日期**: 2026-07-22
- **状态**: 已批准（用户逐节确认）
- **范围**: Phase 1 —— 通道统一 + session 结构化事件流 + v2 持久化与诊断 API + decision 联动 + legacy 导入
- **不在本次范围**: Phase 2 进程合并（dev/feishu/wake 单进程）、Phase 3 幂等去重与入站审计、web 可视化页面（下一个 spec，使用本次的 API）

## 1. 背景与问题

agent-ts 目前有 4 个各自独立的入站通道，无统一网关：

| 通道 | 入口 | session 管理 |
|---|---|---|
| CLI/TUI (`npm run dev`) | src/index.ts | 第三套路径（本次不动） |
| 飞书 (`npm run feishu`) | src/api/feishu.ts（lark WSClient 长连接） | FeishuSessionManager |
| Wake (`npm run wake`) | src/api/wake-channel.ts（Express :3001） | ChannelSessionManager |
| Web API（遗留管理面） | src/api/web/server.ts | 无 |

实证的问题：

1. **三份会话状态互不可见**：飞书 session 存 `~/.pi-invest/sessions/`，wake 存 `~/.pi-invest/wake-sessions/`。v2 唤醒 agent 做的分析，飞书里问不到——agent"失忆"。
2. **两份 95% 相同的 manager 代码已行为分叉**：
   - abort 时 FeishuSessionManager reject 排队 promise；ChannelSessionManager 直接丢弃导致调用方悬挂（wake `/wake/abort` 现有 bug）
   - ChannelSessionManager 有 `cleanupIdleSessions`、extractReply 处理 string 内容；FeishuSessionManager 有 `shutdown()`；互补但互不拥有
3. **每加一个通道就要第三次复制粘贴**（FeishuSessionManager 连类名都是飞书专用的）。
4. **会话目录命名无规范**：无通道前缀、无 agent 标识，无法统一寻址。
5. **端口冲突**：wake channel 默认 3001、web/server.ts 默认 `API_PORT||3001`、web-frontend Vite dev 3001，三方争抢。
6. **`/wake` 无鉴权**。
7. **session 未被当作资产**：用户明确要求 session 是"查看 agent 工作质量的日志、记忆与进化的根据、web 可视化 agent 智能表现的数据源"。当前只存对话文本，无结构化的工具调用/耗时/成败记录，v2 和 web 都无法消费。

参考架构：OpenClaw 的 gateway-first 设计（单进程控制面、channel adapter → 标准化 envelope、canonical session key、per-lane 命令队列、token 鉴权、JSONL 会话持久化）。本项目借鉴其通道抽象与会话寻址，不借鉴其 WS RPC 协议、设备配对、node registry（过度设计）。

## 2. 决策记录（用户已确认）

| 决策点 | 选择 | 备选（未选） |
|---|---|---|
| 优化范围 | 只做 Phase 1 | Phase 1+2、全部三个 Phase |
| 会话组织 | 渠道隔离（`agent:main:{channel}:{peerId}`），与 OpenClaw 一致 | 主会话共享（wake 事件进入飞书主会话） |
| 合并方案 | 方案 B：完整 adapter 层（InboundEvent + ChannelAdapter） | 方案 A：最小合并；方案 C：只修端口/token |
| 迁移方式 | 一次性 cutover，删除 FeishuSessionManager，git revert 回滚 | 渐进双轨、留 shim |
| 存储模型 | 本地结构化 JSONL 为权威源 + 异步同步到 v2 | 直写 v2；只落本地 |
| 旧 session 数据 | 导入脚本迁移（标记 legacy），不抛弃 | 不迁移 |

## 3. 架构

```
┌───────────────────────── agent-ts 进程 ─────────────────────────┐
│  FeishuAdapter ──→┐                              ┌── lark API 回复
│  (lark WSClient)  │   InboundEvent               │
│                   ↓                              │
│  WakeAdapter ────→  AgentGateway                  │
│  (Express :3002)  │   • dispatch(event)          │
│  token 鉴权        │   • 消息去重 (messageId)      │
│                   │   • 一个 ChannelSessionManager│
│                   ↓                              │
│              Agent Session (按 sessionKey 隔离)    │
│                   │ 结构化事件 → events.jsonl（权威）│
│                   ↓                              │
│              SessionSyncer ──批量 POST──→ quantsys-v2
│              (断点续传/退避重试)                    │
└─────────────────────────────────────────────────┘
                          ↓
            quant.agent_sessions / quant.agent_session_events
                          ↓
            GET /api/sessions/* （诊断 API） → web（下一个 spec）
```

### 3.1 新目录 `agent-ts/src/api/gateway/`

| 文件 | 职责 |
|---|---|
| `types.ts` | `InboundEvent`、`ChannelAdapter` 接口、`SessionEvent` 类型、配置类型 |
| `session-key.ts` | `buildSessionKey(channel, peerId)` → `agent:main:{channel}:{peerId}` |
| `gateway.ts` | `AgentGateway`：持有一个增强版 ChannelSessionManager，暴露 `dispatch(event): Promise<string>`、`abort(sessionKey)` |
| `session-factory.ts` | 从 feishu.ts / wake-channel.ts 抽取的公共逻辑：createTrackedSession + beforePrompt（autoRecall、readDailyMemory、buildAgentSystemPrompt） |
| `session-events.ts` | 轻量事件总线 `sessionEvents.emit(sessionKey, event)` + 写 events.jsonl；`setSessionContext(sessionKey, sessionDir)`（扩展现有 setSessionDataDir 机制） |
| `session-syncer.ts` | 批量推送、退避重试、断点续传 |
| `channel-session-manager.ts` | 从 `src/api/` 移入并增强：补 `shutdown()`、abort 时 reject 排队 promise |
| `adapters/feishu-adapter.ts` | lark WSClient 收发 ↔ InboundEvent 规范化；保留"任务处理中，消息已排队"UX |
| `adapters/wake-adapter.ts` | Express :3002，token 中间件，`{event, task_id, data, session_id}` → InboundEvent（含现有 buildPromptFromEvent 逻辑） |

### 3.2 核心接口

```typescript
interface InboundEvent {
  channel: 'feishu' | 'wake';
  peerId: string;              // feishu: chatId; wake: session_id || 'default'
  messageId: string;           // 去重键
  text: string;                // 已规范化的 prompt 文本
  event?: string;              // wake 事件类型（market_alert 等）
  data?: Record<string, any>;  // 原始载荷（审计用）
}

interface ChannelAdapter {
  readonly name: string;
  start(dispatch: (event: InboundEvent) => Promise<string>,
        isProcessing: (sessionKey: string) => boolean): void;
  shutdown(): void;
}
```

入口统一为 `startGateway({ adapters: [...] })`：Phase 1 两个进程各自实例化 Gateway + 自己的 adapter；Phase 2 进程合并时只需把两个 adapter 放进同一个数组，零重构。

### 3.3 通道适配器原则

适配器只做"翻译 + 传输"，不碰 session、不拼系统提示词。`buildPromptFromEvent`（wake 事件→提示词）作为规范化逻辑保留在 wake adapter 内。

## 4. Session 事件模型（核心资产）

### 4.1 事件类型

```typescript
type SessionEvent =
  | { type: 'session_start';   sessionKey, channel, peerId, agentId }
  | { type: 'user_message';    messageId, text, event?, data? }
  | { type: 'tool_call';       toolName, params, durationMs, success, error?, resultSummary }
  | { type: 'assistant_reply'; text, replyLength }
  | { type: 'error';           stage, message }
  | { type: 'session_idle';    reason }
```

每个事件带 `seq`（会话内单调递增）+ `timestamp`。`seq` 是同步断点依据与幂等键。

工具调用事件的采集：工具在 session 内部执行，manager 包不住，因此加轻量事件总线；工具层与 session 包装层都可发事件，manager 统一落盘。现有 `setSessionDataDir` 扩展为 `setSessionContext(sessionKey, sessionDir)`，使工具能感知所属会话。

### 4.2 本地存储（权威源）

```
~/.pi-invest/agent-sessions/agent:main:feishu:oc_xxx/
├── events.jsonl        # 追加写，一行一个事件（含 seq）
└── context.json        # 元数据：状态、计数器、最后活跃时间
```

旧目录 `sessions/`、`wake-sessions/` 废弃但保留在磁盘。代码一次性 cutover，不留双轨；`feishu-session-manager.ts` 直接删除（唯一调用方是 feishu.ts，编译器验证无隐藏引用），回滚靠 git revert。

### 4.3 旧数据导入

`scripts/import-legacy-sessions.ts`：扫描旧目录，把 `log.jsonl`/`conversation.log` 合成 `session_start/user_message/assistant_reply` 事件写入新模型（工具调用细节不可恢复，标记 `legacy: true`）。一次性脚本。

### 4.4 decision 联动

`decision_record` 工具自动从 session 上下文取 `sessionKey` 写入；v2 侧 `agent_decisions` 表加 `session_key` 列。形成闭环：

```
session 事件流 ←──session_key──→ 决策记录 ←──→ 盈亏结果
```

"决策在什么上下文做出 → 结果如何 → 吸取什么教训"全链可溯，是进化功能与 web 决策回放的数据基础。

## 5. 同步机制（SessionSyncer）

- 每个 agent 进程内嵌，与 Gateway 同生命周期
- 事件在写 events.jsonl 的同时推给 syncer 内存队列；每 5s 或满 20 条批量 `POST /api/sessions/events`
- **幂等**：v2 端 `UNIQUE(session_key, seq)` 去重，重复推送安全
- **断点续传**：`agent-sessions/.sync-state.json` 记录每个 sessionKey 的 `lastSyncedSeq`；进程重启或 v2 长时间宕机后从断点续传，一条不丢
- **不阻塞主链路**：sync 失败只记日志 + 指数退避，绝不影响消息处理；本地 events.jsonl 永远完整
- **双通道无冲突**：Phase 1 两进程各自同步自己通道的 sessionKey 前缀；Phase 2 合并后天然一个 syncer

## 6. v2 存储与 API

### 6.1 表结构

迁移文件 `infrastructure/persistence/migrations/create_agent_session_tables.sql`：

```sql
quant.agent_sessions (
  session_key      TEXT PRIMARY KEY,        -- agent:main:feishu:oc_xxx
  channel          TEXT NOT NULL,
  peer_id          TEXT NOT NULL,
  agent_id         TEXT NOT NULL DEFAULT 'main',
  started_at       TIMESTAMPTZ NOT NULL,
  last_active_at   TIMESTAMPTZ NOT NULL,
  status           TEXT NOT NULL,           -- active / idle
  message_count    INT DEFAULT 0,
  tool_call_count  INT DEFAULT 0,
  error_count      INT DEFAULT 0
)

quant.agent_session_events (
  id           BIGSERIAL PRIMARY KEY,
  session_key  TEXT NOT NULL REFERENCES quant.agent_sessions(session_key),
  seq          INT NOT NULL,
  event_type   TEXT NOT NULL,
  payload      JSONB NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL,
  UNIQUE(session_key, seq)
)

ALTER TABLE quant.agent_decisions ADD COLUMN session_key TEXT;
```

### 6.2 API（Flask 蓝图 `routes/agent_sessions.py`）

| 端点 | 用途 |
|---|---|
| `POST /api/sessions/events` | 批量接收事件（syncer 用），幂等 upsert，维护 agent_sessions 计数器；单条校验失败跳过该条返回部分成功 |
| `GET /api/sessions` | 会话列表（活跃时间倒序，channel 过滤） |
| `GET /api/sessions/{key}` | 会话详情 + 计数器 |
| `GET /api/sessions/{key}/events` | 事件流（分页，event_type 过滤）——web 会话回放数据源 |
| `GET /api/sessions/{key}/diagnosis` | 诊断：工具成功率、耗时分布、错误聚类、关联 decision 及结果 |

diagnosis 在 service 层（`application/services/session_service.py`）纯 SQL 聚合，不存冗余：
- 工具成功率 = success tool_call / 总 tool_call
- 耗时分布 = avg/percentile(durationMs)，标出慢工具
- 错误聚类 = 按 error message 分组计数
- 决策联动 = `SELECT * FROM agent_decisions WHERE session_key = ?`

按"返回洞察"原则附解读，如 `{"tool_success_rate": 0.72, "insight": "成功率偏低，data_fetch_financial 失败 8 次均为超时，建议检查数据源"}`。

## 7. 端口与鉴权

**端口**：wake channel 固定 `127.0.0.1:3002`。

| 位置 | 改动 |
|---|---|
| agent-ts wake-adapter.ts | 默认端口 3001→3002，`WAKE_CHANNEL_PORT` 可覆盖 |
| agent-ts .env.example | 新增 `WAKE_CHANNEL_PORT=3002`、`WAKE_TOKEN=` |
| v2 agent_notification_service.py | 默认 `AGENT_API_URL` → `http://127.0.0.1:3002`，发送 `X-Wake-Token` header |
| v2 .env.automation.example | 新增 `AGENT_API_TOKEN=` |
| agent-ts CLAUDE.md 固定端口表 | 加 `agent wake channel: 127.0.0.1:3002` |

**鉴权**（轻量，不抄设备配对）：
- `WAKE_TOKEN` 已配置 → 强制校验 `X-Wake-Token`，不匹配 401；未配置 → 放行 + 启动警告（dev 不挡路）
- v2 读 `AGENT_API_TOKEN` 发送；`/wake`、`/wake/abort` 校验，`/wake/health` 公开

## 8. 错误处理

| 层 | 策略 |
|---|---|
| Adapter | 飞书回复失败 → 记 error 事件不重试；wake HTTP 错误 → 4xx/5xx + 结构化 error body |
| Gateway dispatch | session prompt 抛错 → reject 给 adapter，adapter 告知用户，记 error 事件 |
| Manager | abort reject 排队 promise（修悬挂 bug）；单条消息失败不影响队列后续 |
| Syncer | 失败只记日志 + 退避，永不阻塞消息处理 |
| v2 ingest | 单条校验失败跳过，不整批拒绝 |

## 9. 测试策略（TDD）

**agent-ts（Jest）**：
- `session-key.test.ts` — key 构造、特殊字符
- `gateway.test.ts` — dispatch 创建/复用会话、去重、abort reject、shutdown
- `session-events.test.ts` — events.jsonl 写入、seq 单调、工具事件采集
- `session-syncer.test.ts` — 批量推送、失败重试、断点续传
- `wake-adapter.test.ts` — 401/400/成功/abort 契约
- `feishu-adapter.test.ts` — 消息规范化
- `decision-record-tool.test.ts` — 补充：自动携带 sessionKey

**quantsys-v2（pytest）**：
- `test_agent_session_routes.py` — ingest 幂等、计数器、各查询端点
- diagnosis 聚合正确性（构造已知事件集断言指标）

**端到端验证**：`npm run wake` + v2 `send_reminder`，确认事件 v2 → wake → session → events.jsonl → 同步回 v2 → `GET /api/sessions` 可查。

## 10. 改动清单

**agent-ts**：
- 新增 `src/api/gateway/`（types / session-key / gateway / session-factory / session-events / session-syncer / channel-session-manager / adapters×2）
- `feishu.ts`、`start-wake-channel.ts` 重写为薄启动文件
- 删除 `feishu-session-manager.ts`（其测试迁移为 gateway 测试）
- `decision-record-tool.ts` 自动携带 sessionKey
- 新增 `scripts/import-legacy-sessions.ts`
- `.env.example`、CLAUDE.md 端口表

**quantsys-v2**：
- `infrastructure/persistence/migrations/create_agent_session_tables.sql`
- `adapters/inbound/api/routes/agent_sessions.py`（注册进 server.py）
- `application/services/session_service.py`
- `agent_notification_service.py` 端口/token
- `.env.automation.example`

**已知代价**：cutover 后飞书进行中对话上下文清零（渠道会话为短期缓存，长期记忆在 memory/ 与 v2 数据库，可接受）。
