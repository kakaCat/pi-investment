# 飞书集成实现计划

**日期**: 2026-03-30
**目标**: 为 pi-investment 添加飞书 Bot 功能，复用现有 CronService

---

## 📋 需求分析

### 核心功能
1. 飞书 WebSocket 长连接接收消息
2. 每个 chatId 独立 session（多群隔离）
3. 对话历史持久化到 `.pi-invest/sessions/{chatId}/`
4. 定时任务通过 CronService 触发，结果推送到飞书
5. 支持 "stop" 命令取消任务

### 技术选型
- SDK: `@larksuiteoapi/node-sdk`
- Session 管理: 复用现有 `SessionFactory` + `SessionIdMapper`
- Cron: 复用现有 `CronService`（不引入 node-cron）
- 工具集: 复用 `invest-tools.ts` 的所有工具

---

## 🏗️ 架构设计

```
飞书 WebSocket
    ↓
feishu.ts (入口)
    ↓
FeishuSessionManager (多 session 管理)
    ↓
SessionFactory → Agent Loop → Tools
    ↓
CronService (定时触发) → 结果推送到飞书
```

### 目录结构

```
src/api/
├── feishu.ts                    # 飞书入口（200 行）
└── feishu-session-manager.ts   # Session 管理（150 行）

.pi-invest/
├── FEISHU_CRON.json            # 飞书定时任务配置
└── sessions/
    └── {chatId}/
        ├── log.jsonl           # 完整对话历史
        └── context.json        # Agent 上下文
```

---

## 📝 实现任务拆分

### Task 1: 安装依赖和环境配置
- [ ] `npm install @larksuiteoapi/node-sdk`
- [ ] 更新 `.env.example` 添加 `FEISHU_APP_ID`, `FEISHU_APP_SECRET`
- [ ] 更新 `package.json` 添加 `"feishu": "tsx src/api/feishu.ts"`

### Task 2: FeishuSessionManager
**文件**: `src/api/feishu-session-manager.ts`

**职责**:
- 管理多个 chatId 的 session（Map<chatId, AgentSession>）
- 消息去重（记录已处理的 message_id）
- 队列机制（同一 chatId 串行，跨 chatId 并行）
- 持久化对话历史到 `.pi-invest/sessions/{chatId}/log.jsonl`
- 支持 abort() 取消当前任务

**核心方法**:
```typescript
class FeishuSessionManager {
  private sessions = new Map<string, AgentSession>();
  private processing = new Map<string, boolean>();
  private messageIds = new Set<string>();

  async processMessage(chatId: string, msgId: string, text: string): Promise<string>
  async abort(chatId: string): Promise<boolean>
  isDuplicate(msgId: string): boolean
  isProcessing(chatId: string): boolean
}
```

**参考**: piagent 的 `ChannelSessionManager`，但简化为直接使用 `SessionFactory`

### Task 3: feishu.ts 入口
**文件**: `src/api/feishu.ts`

**职责**:
- 初始化飞书 WebSocket 客户端
- 事件分发（接收消息 → SessionManager）
- 发送回复到飞书
- 集成 CronService（定时任务触发）
- 优雅退出

**核心流程**:
```typescript
// 1. 初始化
const client = new lark.Client({ appId, appSecret });
const sessionManager = new FeishuSessionManager();
const cronService = new CronService(...);

// 2. 消息处理
dispatcher.register({
  "im.message.receive_v1": async (data) => {
    const text = JSON.parse(data.message.content).text;
    const chatId = data.message.chat_id;

    // stop 命令
    if (text === "stop") {
      await sessionManager.abort(chatId);
      return;
    }

    // 处理消息
    const reply = await sessionManager.processMessage(chatId, msgId, text);
    await sendReply(chatId, reply);
  }
});

// 3. Cron 触发
cronService.onJob = async (payload) => {
  if (payload.kind === "agent_turn" && payload.chatId) {
    const reply = await sessionManager.processMessage(
      payload.chatId,
      `cron-${Date.now()}`,
      payload.message
    );
    await sendReply(payload.chatId, reply);
  }
};

// 4. 启动
wsClient.start({ eventDispatcher: dispatcher });
cronService.start();
```

### Task 4: FEISHU_CRON.json 配置
**文件**: `.pi-invest/FEISHU_CRON.json`

```json
{
  "jobs": [
    {
      "id": "feishu-morning-brief",
      "name": "飞书早报",
      "enabled": false,
      "schedule": {
        "kind": "cron",
        "expr": "0 9 * * 1-5"
      },
      "payload": {
        "kind": "agent_turn",
        "chatId": "oc_REPLACE_WITH_YOUR_CHAT_ID",
        "message": "生成今日投资建议：1) 市场概览 2) 持仓分析 3) 风险提示"
      }
    }
  ]
}
```

### Task 5: 类型扩展
**文件**: `src/services/cron/cron-service.ts`

扩展 `CronJobPayload` 类型：
```typescript
export interface CronJobPayload {
  kind: "agent_turn" | "daily_review" | "system_event" | "stop_loss_alert";
  message?: string;
  text?: string;
  chatId?: string;  // ← 新增：飞书 chatId
}
```

---

## 🔍 关键技术点

### 1. Session 隔离
每个 chatId 独立 session，使用 `SessionIdMapper` 生成唯一 sessionId：
```typescript
const sessionId = SessionIdMapper.getOrCreate(`feishu-${chatId}`);
```

### 2. 消息去重
使用 Set 记录已处理的 message_id：
```typescript
if (this.messageIds.has(msgId)) return;
this.messageIds.add(msgId);
```

### 3. 队列机制
同一 chatId 串行处理（避免并发冲突）：
```typescript
if (this.processing.get(chatId)) {
  // 排队等待
}
this.processing.set(chatId, true);
try {
  // 处理消息
} finally {
  this.processing.set(chatId, false);
}
```

### 4. Cron 触发飞书消息
在 `feishu.ts` 中监听 CronService 的 job 执行：
```typescript
const cronService = new CronService(
  cronFile,
  piDir,
  async (payload) => {
    if (payload.chatId) {
      const reply = await sessionManager.processMessage(...);
      await sendReply(payload.chatId, reply);
    }
  }
);
```

---

## ✅ 验收标准

1. **基础功能**
   - [ ] 飞书发送消息，Bot 能正常回复
   - [ ] 多个群同时发消息，互不干扰
   - [ ] 发送 "stop" 能取消当前任务

2. **定时任务**
   - [ ] 配置 FEISHU_CRON.json 后，定时推送消息到飞书
   - [ ] 定时任务的输出（市场分析）能正确发送到指定群

3. **持久化**
   - [ ] 对话历史保存到 `.pi-invest/sessions/{chatId}/log.jsonl`
   - [ ] 重启后能恢复对话上下文

4. **错误处理**
   - [ ] 网络异常时自动重连
   - [ ] Agent 执行失败时返回友好错误提示

---

## 📦 交付物

1. `src/api/feishu.ts` - 飞书入口（~200 行）
2. `src/api/feishu-session-manager.ts` - Session 管理（~150 行）
3. `.pi-invest/FEISHU_CRON.json` - 定时任务配置模板
4. `package.json` - 新增 `feishu` 启动脚本
5. `.env.example` - 新增飞书环境变量说明
6. `README.md` - 新增飞书使用文档

---

## 🚀 启动方式

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 FEISHU_APP_ID 和 FEISHU_APP_SECRET

# 2. 启动飞书 Bot
npm run feishu

# 3. 在飞书群中发送消息测试
```

---

## 📚 参考资料

- piagent 实现: `/Users/mac/Documents/ai/piagent/src/api/feishu.ts`
- 飞书开放平台: https://open.feishu.cn/
- 现有 CronService: `src/services/cron/cron-service.ts`
