# feishu_notify 工具使用指南

## 功能概述

`feishu_notify` 是一个用于向飞书发送通知消息的 Agent 工具，支持多种消息类型和紧急程度。

## 支持的消息类型

### 1. 文本消息 (text)
发送纯文本消息。

**参数**：
- `messageType`: `"text"`
- `content`: 消息内容（必需）
- `mentionUser`: 是否 @ 用户（可选，默认 false）

**示例**：
```typescript
{
  messageType: "text",
  content: "市场异动：上证指数突破 3200 点",
  mentionUser: true
}
```

### 2. 卡片消息 (card)
发送富文本卡片，支持 Markdown 格式。

**参数**：
- `messageType`: `"card"`
- `title`: 卡片标题（必需）
- `content`: 卡片内容，支持 Markdown（必需）
- `urgency`: 紧急程度 - `"normal"` | `"high"` | `"critical"`（可选）
- `actionButtons`: 操作按钮列表（可选）

**示例**：
```typescript
{
  messageType: "card",
  title: "持仓告警",
  content: "**股票**: 贵州茅台 (600519)\n**当前价格**: 1850.00\n**跌幅**: -3.5%",
  urgency: "high",
  actionButtons: [
    { label: "查看详情", url: "https://..." }
  ]
}
```

### 3. 告警消息 (alert)
发送告警通知。

**参数**：
- `messageType`: `"alert"`
- `title`: 告警标题（必需）
- `content`: 告警内容（必需）
- `urgency`: 紧急程度（可选）
- `mentionUser`: 是否 @ 用户（可选）

**示例**：
```typescript
{
  messageType: "alert",
  title: "风险预警",
  content: "持仓集中度过高，建议分散投资",
  urgency: "critical",
  mentionUser: true
}
```

### 4. 每日报告 (daily_report)
发送每日投资报告。

**参数**：
- `messageType`: `"daily_report"`
- `content`: 报告内容（必需）
- `data`: 报告数据对象（必需）

**data 字段**：
```typescript
{
  date?: string;           // 日期
  sh_index_change?: string; // 上证指数变化
  sz_index_change?: string; // 深证成指变化
  north_flow?: string;      // 北向资金流向
  daily_pnl?: string;       // 今日收益
  total_return?: string;    // 总收益率
  position_count?: number;  // 持仓数量
  new_signals?: number;     // 新增信号
  opportunities?: number;   // 优质机会
  risk_alerts?: string[];   // 风险提醒
  detail_url?: string;      // 详情链接
  signals_url?: string;     // 信号链接
}
```

### 5. 每周报告 (weekly_report)
发送每周投资报告。

**参数**：
- `messageType`: `"weekly_report"`
- `content`: 报告内容（必需）
- `data`: 报告数据对象（必需）

**data 字段**：
```typescript
{
  week?: number;            // 周数
  weekly_return?: string;   // 周收益率
  max_drawdown?: string;    // 最大回撤
  win_rate?: string;        // 交易胜率
  cumulative_return?: string; // 累计收益
  strategies?: any[];       // 策略表现
  outlook?: object;         // 下周展望
  detail_url?: string;      // 详情链接
  export_url?: string;      // 导出链接
}
```

### 6. 盘前报告 (premarket_report)
发送盘前准备报告。

**参数**：
- `messageType`: `"premarket_report"`
- `content`: 报告内容（必需）
- `data`: 报告数据对象（必需）

## 通用参数

### urgency（紧急程度）
- `"normal"`: 普通消息（蓝色）
- `"high"`: 重要消息（橙色）
- `"critical"`: 紧急消息（红色）

### actionButtons（操作按钮）
```typescript
{
  label: string;    // 按钮文本
  url?: string;     // 跳转链接
  action?: string;  // 动作类型
}
```

## 配置方式

### 方式 1: Webhook 模式（推荐）

1. 在飞书群聊中创建自定义 Bot
2. 获取 Webhook URL
3. 添加到 `.env` 文件：
```bash
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

### 方式 2: App 模式

1. 配置飞书 App ID 和 Secret（已配置）
2. Bot 会自动从对话中获取 chat_id
3. 通过 Agent 对话调用工具

### 方式 3: 手动指定 Chat ID

```bash
FEISHU_CHAT_ID=oc_xxx
```

## 使用示例

### 在 Agent 中调用

Agent 会自动调用此工具发送通知，无需手动配置。

### 编程调用

```typescript
import { feishuNotifyTool } from './infrastructure/tools/notification/feishu-notify-tool.js';

// 发送文本消息
const result = await feishuNotifyTool.execute('call-id', {
  messageType: 'text',
  content: '测试消息'
});

// 发送卡片消息
const result = await feishuNotifyTool.execute('call-id', {
  messageType: 'card',
  title: '市场异动',
  content: '**上证指数**: +2.5%\n**深证成指**: +3.1%',
  urgency: 'high'
});

// 发送日报
const result = await feishuNotifyTool.execute('call-id', {
  messageType: 'daily_report',
  content: '每日报告',
  data: {
    date: '2026-06-24',
    sh_index_change: '+1.5%',
    daily_pnl: '+5000',
    new_signals: 3
  }
});
```

## 返回值

```typescript
{
  content: [
    { type: "text", text: "成功/失败消息" }
  ],
  details: {
    success: boolean;      // 是否成功
    message: string;       // 结果消息
    messageType?: string;  // 消息类型
    timestamp?: string;    // 时间戳
    error?: string;        // 错误信息（如果失败）
  }
}
```

## 错误处理

工具会优雅处理以下情况：

1. **服务未配置**：返回失败但不抛出异常
2. **必需参数缺失**：返回参数错误信息
3. **网络错误**：捕获并返回错误信息
4. **发送失败**：返回失败状态

## 测试脚本

### 验证工具定义
```bash
npx tsx src/scripts/verify-feishu-tool.ts
```

### 集成测试（降级模式）
```bash
npx tsx src/scripts/test-feishu-service-integration.ts
```

### 真实发送测试（需要配置）
```bash
# Webhook 模式
npx tsx src/scripts/test-feishu-integration.ts

# App API 模式
npx tsx src/scripts/test-feishu-real-send.ts
```

## 故障排查

### 问题：消息发送失败
- 检查 `FEISHU_WEBHOOK_URL` 是否配置
- 检查 Webhook URL 是否有效
- 检查网络连接

### 问题：卡片消息报错
- 确保提供了 `title` 参数
- 检查 `content` 是否为有效 Markdown

### 问题：报告消息报错
- 确保提供了 `data` 参数
- 检查 `data` 对象包含必要字段

## 技术细节

- **工具类型**：`ToolDefinition`
- **参数 Schema**：`@sinclair/typebox`
- **服务实现**：`FeishuNotificationService`
- **消息格式**：飞书 Bot Webhook API

## 相关文件

- 工具实现：`src/infrastructure/tools/notification/feishu-notify-tool.ts`
- 服务层：`src/services/feishu-notification.service.ts/feishu-notification-service.ts`
- 工具注册：`src/infrastructure/tools/index.ts`
- 测试脚本：`src/scripts/test-feishu-*.ts`
