# 飞书集成调研报告

**日期**: 2026-08-14  
**目标**: 理清飞书的两种使用场景及最佳实践

---

## 📊 当前系统中的飞书功能

### 场景 1️⃣: 用户通过飞书与 Agent 聊天（双向交互）

**位置**: `agent-ts/src/api/feishu.ts` + `feishu-adapter.ts`

**实现方式**: 飞书开放平台 **App Token** (非 Webhook)

**技术架构**:
```
用户在飞书群 → 飞书服务器 → WebSocket → agent-ts → LLM → agent-ts → 飞书 API → 用户看到回复
```

**关键代码**:
```typescript
// 1. 启动 WebSocket 监听飞书消息
const client = new lark.Client({ 
  appId: process.env.FEISHU_APP_ID,
  appSecret: process.env.FEISHU_APP_SECRET 
});

const wsClient = new lark.WSClient({ appId, appSecret });
wsClient.start({ eventDispatcher: dispatcher });

// 2. 接收消息事件
dispatcher.register({
  "im.message.receive_v1": async (data) => {
    const inbound = normalizeFeishuMessage(data.message);
    const reply = await handlers.dispatch(inbound); // 调用 agent
    await sendReply(inbound.peerId, reply);        // 回复到飞书
  }
});

// 3. 发送回复
await client.im.message.create({
  params: { receive_id_type: "chat_id" },
  data: {
    receive_id: chatId,
    msg_type: "interactive",  // 发送卡片消息
    content: JSON.stringify(card),
  }
});
```

**所需配置**:
```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
```

**所需权限**:
- ✅ `im:message` (读取和发送消息)
- ✅ `im:message.group_at_msg` (接收群 @ 消息)
- ✅ `im:chat` (获取群列表)

**特点**:
- ✅ 双向通信（接收 + 发送）
- ✅ 支持多个群聊
- ✅ 支持私聊
- ✅ WebSocket 长连接，实时响应
- ✅ 可以知道是谁发的消息（peerId）
- ❌ 需要企业认证（免费应用也支持，但有限额）

---

### 场景 2️⃣: Agent 主动发送通知到飞书群（单向推送）

**位置**: 
- `agent-ts/src/services/feishu-notification.service.ts`
- `agent-os/drivers/feishu-driver/` (WP-6)

**实现方式**: 飞书 **Webhook URL** (群机器人)

**技术架构**:
```
agent-ts 定时任务/事件触发 → HTTP POST → Webhook URL → 飞书群收到消息
```

**关键代码**:
```typescript
// agent-ts 中的实现
private async send(payload: any): Promise<boolean> {
  const response = await axios.post(this.webhookUrl, payload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: 10000,
  });
  return response.data?.code === 0;
}

// 发送卡片
await this.send({
  msg_type: 'interactive',
  card: {
    header: { title: { content: '每日报告' }, template: 'blue' },
    elements: [{ tag: 'div', text: { tag: 'lark_md', content: '...' } }]
  }
});
```

**所需配置**:
```bash
# 单个 Webhook（通用）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 多个 Webhook（不同用途）
FEISHU_WEBHOOK_TRADING=https://open.feishu.cn/open-apis/bot/v2/hook/yyy
FEISHU_WEBHOOK_ALERTS=https://open.feishu.cn/open-apis/bot/v2/hook/zzz
```

**获取方式**:
1. 在飞书群聊中
2. 点击右上角 ⚙️ → 群设置 → 群机器人
3. 添加自定义机器人
4. 复制 Webhook 地址

**特点**:
- ✅ 超级简单（只需一个 URL）
- ✅ 无需企业认证
- ✅ 无需配置权限
- ✅ 适合单向通知
- ❌ 只能发送，不能接收
- ❌ 不知道是哪个群（URL 自带群信息）
- ❌ 一个 Webhook = 一个群

---

## 🔍 两种方案对比

| 特性 | App Token (场景1) | Webhook (场景2) |
|---|---|---|
| **用途** | 双向聊天 | 单向通知 |
| **配置难度** | ⭐⭐⭐ 中等 | ⭐ 简单 |
| **企业认证** | 需要（免费版可用） | 不需要 |
| **权限申请** | 需要多个权限 | 不需要 |
| **消息接收** | ✅ 支持 | ❌ 不支持 |
| **消息发送** | ✅ 支持 | ✅ 支持 |
| **多群支持** | ✅ 统一管理 | 需要多个 Webhook |
| **用户识别** | ✅ 可以知道是谁 | ❌ 不知道 |
| **实时性** | ✅ WebSocket | ✅ HTTP 即时 |
| **成本** | 免费（有限额） | 完全免费 |

---

## 🎯 推荐架构设计

### 场景划分

**场景 1: 交互式对话** → 使用 **App Token**
- ✅ 用户问 agent："今天有什么投资机会？"
- ✅ Agent 回复具体分析
- ✅ 用户追问："600519 怎么样？"
- ✅ Agent 继续回答

**场景 2: 自动通知** → 使用 **Webhook**
- ✅ Agent 定时发送每日报告
- ✅ Agent 检测到重要信号推送告警
- ✅ 交易执行完成后发送确认
- ✅ 系统状态变化通知

---

## 💡 统一架构方案

### 方案 A: 混合使用（推荐）✅

**设计原则**: 各司其职，互不干扰

```typescript
// 场景 1: 飞书聊天 Bot (App Token)
// 位置: agent-ts/src/api/feishu.ts
startFeishuBot() {
  // WebSocket 监听 + 双向通信
  // 用于: 用户与 agent 对话
}

// 场景 2: 飞书通知服务 (Webhook)
// 位置: agent-ts/src/services/feishu-notification.service.ts
class FeishuNotificationService {
  // HTTP POST 单向推送
  // 用于: agent 主动发送报告/告警
}
```

**配置示例**:
```bash
# Bot 配置（场景 1: 聊天）
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# Webhook 配置（场景 2: 通知）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/general
FEISHU_WEBHOOK_TRADING=https://open.feishu.cn/open-apis/bot/v2/hook/trading
FEISHU_WEBHOOK_ALERTS=https://open.feishu.cn/open-apis/bot/v2/hook/alerts
```

**优点**:
- ✅ 各司其职，职责清晰
- ✅ 互不干扰，配置独立
- ✅ Bot 挂掉不影响通知
- ✅ Webhook 简单可靠

**缺点**:
- ⚠️ 需要维护两套配置
- ⚠️ 可能在不同群中（Bot 群 vs Webhook 群）

---

### 方案 B: 统一使用 App Token

**设计原则**: 一套 API 解决所有问题

```typescript
// 统一飞书服务
class UnifiedFeishuService {
  private client: lark.Client;
  
  // 场景 1: 接收消息（通过 WebSocket）
  listenMessages() { ... }
  
  // 场景 2: 主动发送（通过 im.message.create）
  async sendToChat(chatId: string, content: string) {
    await this.client.im.message.create({
      params: { receive_id_type: "chat_id" },
      data: {
        receive_id: chatId,
        msg_type: "interactive",
        content: JSON.stringify(card),
      }
    });
  }
}
```

**配置示例**:
```bash
# 只需要 App 配置
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# 指定通知目标群
FEISHU_CHAT_ID_GENERAL=oc_xxx
FEISHU_CHAT_ID_TRADING=oc_yyy
FEISHU_CHAT_ID_ALERTS=oc_zzz
```

**优点**:
- ✅ 统一配置，简化管理
- ✅ 可以发送到任意群（包括私聊）
- ✅ 可以知道消息发送状态
- ✅ 支持更多功能（如 @ 某人）

**缺点**:
- ⚠️ 需要配置 chat_id（不如 Webhook 直观）
- ⚠️ 需要企业认证
- ⚠️ 单点故障（App Token 过期则全挂）

---

### 方案 C: 根据环境变量自动选择

**设计原则**: 优雅降级

```typescript
class SmartFeishuService {
  private appClient?: lark.Client;
  private webhookUrl?: string;
  
  constructor() {
    // 尝试初始化 App Token
    if (process.env.FEISHU_APP_ID && process.env.FEISHU_APP_SECRET) {
      this.appClient = new lark.Client({ ... });
    }
    
    // 尝试初始化 Webhook
    this.webhookUrl = process.env.FEISHU_WEBHOOK_URL;
  }
  
  async send(target: string, content: string) {
    // 优先使用 App Token（功能更强大）
    if (this.appClient && isChatId(target)) {
      return await this.sendViaApp(target, content);
    }
    
    // 降级到 Webhook
    if (this.webhookUrl) {
      return await this.sendViaWebhook(content);
    }
    
    throw new Error('No Feishu configuration available');
  }
}
```

**优点**:
- ✅ 自动选择最佳方案
- ✅ 配置灵活
- ✅ 优雅降级

**缺点**:
- ⚠️ 逻辑复杂
- ⚠️ 可能混淆用户

---

## 🎯 最终推荐

### **推荐方案 A（混合使用）** ✅

**理由**:
1. **职责清晰**: 聊天是聊天，通知是通知
2. **简单可靠**: Webhook 超级简单，App Token 功能强大
3. **现有架构**: 当前系统已经是这样设计的
4. **最佳实践**: 业界主流方案

**具体建议**:

#### 1. Agent OS 的 Feishu Driver (WP-6) 定位

**用途**: 作为 Agent OS 的**通知子系统**

```bash
# 专注于单向推送通知
agent-os notify send --target trading --title "交易信号" --message "..."
agent-os notify send --target alerts --title "风险告警" --message "..."
```

**配置**:
```yaml
# agent-os/config.yaml
notifications:
  feishu:
    targets:
      trading: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
      alerts: "https://open.feishu.cn/open-apis/bot/v2/hook/yyy"
      general: "https://open.feishu.cn/open-apis/bot/v2/hook/zzz"
```

#### 2. Agent-ts 的 Feishu Bot 定位

**用途**: 作为 Agent 的**交互界面**

```typescript
// 启动飞书聊天 Bot
startFeishuBot();

// 用户可以通过飞书与 agent 对话
用户: "@Pi Investment 今天有什么投资机会？"
Agent: "根据最新分析，发现以下机会..."
```

**配置**:
```bash
# agent-ts/.env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
```

#### 3. Agent-ts 的 Notification Service 定位

**用途**: Agent 主动发送**结构化报告**

```typescript
// 每日报告、周报等定时任务
await feishuService.sendDailyReport({
  total_assets: 1000000,
  cash: 200000,
  holdings_count: 10,
  total_pnl: 50000,
  total_pnl_pct: 5.2
});
```

**配置**:
```bash
# agent-ts/.env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/reports
```

---

## 📋 整合优化建议

### 优化 1: Agent OS Feishu Driver 改进

**当前问题**: `user` vs `channel` 语义混淆

**改进方案**: 统一为 `target` 概念

```python
# notification_manager.py
class NotificationManager:
    def __init__(self):
        self.targets = {
            'trading': os.getenv('FEISHU_WEBHOOK_TRADING'),
            'alerts': os.getenv('FEISHU_WEBHOOK_ALERTS'),
            'reports': os.getenv('FEISHU_WEBHOOK_REPORTS'),
        }
    
    def send(self, target: str, title: str, message: str, color: str = "blue"):
        webhook_url = self.targets.get(target)
        if not webhook_url:
            raise ValueError(f"Target not found: {target}")
        
        api = FeishuAPI(webhook_url=webhook_url)
        return api.send_card(title=title, content=message, color=color)
```

---

### 优化 2: 添加 Agent OS 的 App Token 支持（可选）

如果需要更强大的功能（如私聊、@ 用户），可以扩展：

```python
# feishu_client.py
class FeishuClient:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None
    
    async def get_token(self):
        """获取 tenant_access_token"""
        ...
    
    async def send_to_chat(self, chat_id: str, card: dict):
        """发送消息到指定群"""
        token = await self.get_token()
        await requests.post(
            'https://open.feishu.cn/open-apis/im/v1/messages',
            headers={'Authorization': f'Bearer {token}'},
            params={'receive_id_type': 'chat_id'},
            json={
                'receive_id': chat_id,
                'msg_type': 'interactive',
                'content': json.dumps(card)
            }
        )
```

**CLI 命令**:
```bash
# Webhook 模式（简单）
agent-os notify webhook --target trading --title "..." --message "..."

# App 模式（高级）
agent-os notify app --chat-id oc_xxx --title "..." --message "..."
```

---

## 🚀 实施步骤

### Phase 1: 现有系统梳理（立即）

1. ✅ 确认 agent-ts 的飞书 Bot 正常运行
2. ✅ 确认 agent-os 的 Feishu Driver (WP-6) 正常工作
3. ✅ 确认 agent-ts 的 Notification Service 正常发送

### Phase 2: 优化 Agent OS Feishu Driver（本周）

1. ✅ 合并 `user` 和 `channel` 为 `target`
2. ✅ 更新 CLI 命令
3. ✅ 更新文档

### Phase 3: 文档完善（本周）

创建 `FEISHU-INTEGRATION.md`，说明：
- 两种使用场景
- 配置方法
- 最佳实践
- 常见问题

### Phase 4: 可选增强（下周）

1. Agent OS 添加 App Token 支持
2. 统一 agent-ts 和 agent-os 的飞书配置
3. 添加更多通知模板

---

## 📚 配置示例

### 完整配置文件

```bash
# .env

# ============================================
# 飞书聊天 Bot (agent-ts)
# 用途: 用户通过飞书与 agent 对话
# ============================================
FEISHU_APP_ID=cli_a1b2c3d4e5f6
FEISHU_APP_SECRET=xxx_your_app_secret_xxx

# ============================================
# 飞书通知 Webhook (agent-ts & agent-os)
# 用途: agent 主动发送通知
# ============================================

# 通用报告群
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/general_xxx

# 交易信号群
FEISHU_WEBHOOK_TRADING=https://open.feishu.cn/open-apis/bot/v2/hook/trading_xxx

# 风险告警群
FEISHU_WEBHOOK_ALERTS=https://open.feishu.cn/open-apis/bot/v2/hook/alerts_xxx

# ============================================
# 可选: 指定 Chat ID (用于 App Token 模式)
# ============================================
FEISHU_CHAT_ID_GENERAL=oc_xxx_general
FEISHU_CHAT_ID_TRADING=oc_xxx_trading
FEISHU_CHAT_ID_ALERTS=oc_xxx_alerts
```

---

## ✅ 总结

### 核心结论

1. **两种机制，各司其职**:
   - App Token (WebSocket) → 双向聊天
   - Webhook (HTTP) → 单向通知

2. **当前架构已经正确**:
   - agent-ts 已实现两种机制
   - agent-os 只需关注通知（Webhook）

3. **需要优化的地方**:
   - Agent OS 合并 user/channel 为 target
   - 完善文档说明使用场景

4. **不需要大改**:
   - 现有架构合理
   - 只需小幅优化和文档完善

---

**下一步**: 是否立即实施 **Phase 2**（优化 Agent OS Feishu Driver）？
