# 飞书集成 + 通知系统实施计划

**日期**: 2026-08-14  
**目标**: 解决飞书集成优化和通知系统设计

---

## 📋 待解决的问题

### **问题 2: 飞书集成优化**
- Agent OS Feishu Driver 的 `user` vs `channel` 混淆
- 需要统一为数据库驱动的配置

### **问题 3: 通知系统设计**
- 程序模板 vs Agent 生成的选择
- 如何设计才符合 Agent 的工作方式

---

## 🎯 解决方案

### **方案概述**

```
┌─────────────────────────────────────────────┐
│  数据库层                                    │
│  - notification_channels (通知渠道)         │
│  - notification_providers (飞书/Slack...)   │
├─────────────────────────────────────────────┤
│  通知服务层                                  │
│  - NotificationService (统一接口)           │
│  - FeishuProvider (飞书实现)                │
├─────────────────────────────────────────────┤
│  Agent 工具层                                │
│  - notification_send (简单发送)             │
│  - notification_list_channels (查询渠道)     │
└─────────────────────────────────────────────┘
```

**核心理念**:
1. ✅ 配置存数据库（动态可配）
2. ✅ Agent 自由生成内容（不用程序模板）
3. ✅ 统一的 Provider 抽象（支持飞书/Slack/邮件）

---

## 📊 数据库设计（简化版）

### **表 1: notification_providers**

```sql
CREATE TABLE notification_providers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(32) NOT NULL UNIQUE,    -- 'feishu', 'slack', 'email'
    name VARCHAR(100) NOT NULL,           -- '飞书', 'Slack', '邮件'
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',            -- 提供商级别配置
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 初始数据
INSERT INTO notification_providers (code, name, config) VALUES
('feishu', '飞书', '{
  "bot": {
    "app_id": "cli_xxx",
    "app_secret": "xxx"
  }
}');
```

---

### **表 2: notification_channels**

```sql
CREATE TABLE notification_channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_id UUID NOT NULL REFERENCES notification_providers(id),
    code VARCHAR(64) NOT NULL UNIQUE,     -- 'trading', 'alerts', 'reports'
    name VARCHAR(100) NOT NULL,            -- '交易群', '告警群', '报告群'
    description TEXT,
    enabled BOOLEAN DEFAULT true,
    config JSONB NOT NULL,                 -- 渠道配置（webhook URL 等）
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_channels_provider ON notification_channels(provider_id);
CREATE INDEX idx_channels_code ON notification_channels(code);

-- 初始数据
INSERT INTO notification_channels (provider_id, code, name, description, config) VALUES
(
    (SELECT id FROM notification_providers WHERE code='feishu'),
    'trading',
    '交易群',
    '接收交易信号和执行确认',
    '{
      "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/trading_xxx"
    }'
),
(
    (SELECT id FROM notification_providers WHERE code='feishu'),
    'alerts',
    '告警群',
    '接收风险预警和系统异常',
    '{
      "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/alerts_xxx"
    }'
);
```

---

### **表 3: notification_logs**

```sql
CREATE TABLE notification_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id UUID NOT NULL REFERENCES notification_channels(id),
    title VARCHAR(255),
    content TEXT,
    status VARCHAR(32) NOT NULL,           -- 'pending', 'sent', 'failed'
    message_id VARCHAR(255),               -- 提供商返回的消息 ID
    error TEXT,
    metadata JSONB DEFAULT '{}',
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_logs_channel ON notification_logs(channel_id);
CREATE INDEX idx_logs_status ON notification_logs(status);
CREATE INDEX idx_logs_created ON notification_logs(created_at DESC);
```

---

## 🔧 代码实现

### **1. Go Service 层（Agent OS）**

```go
// internal/service/notification_service.go

package service

import (
    "context"
    "encoding/json"
    "github.com/google/uuid"
)

type NotificationService struct {
    repo NotificationRepository
}

type SendRequest struct {
    Channel  string                 `json:"channel"`
    Title    string                 `json:"title"`
    Content  string                 `json:"content"`
    Color    string                 `json:"color,omitempty"`
    Urgency  string                 `json:"urgency,omitempty"`
    Metadata map[string]interface{} `json:"metadata,omitempty"`
}

type SendResult struct {
    LogID     string `json:"log_id"`
    Success   bool   `json:"success"`
    Error     string `json:"error,omitempty"`
    MessageID string `json:"message_id,omitempty"`
}

func (s *NotificationService) Send(ctx context.Context, req SendRequest) (*SendResult, error) {
    // 1. 从数据库获取 channel
    channel, err := s.repo.GetChannelByCode(ctx, req.Channel)
    if err != nil {
        return nil, err
    }
    if !channel.Enabled {
        return &SendResult{Success: false, Error: "channel disabled"}, nil
    }

    // 2. 获取 provider
    provider, err := s.repo.GetProvider(ctx, channel.ProviderID)
    if err != nil {
        return nil, err
    }

    // 3. 创建日志记录
    logID := uuid.New().String()
    err = s.repo.CreateLog(ctx, &NotificationLog{
        ID:        logID,
        ChannelID: channel.ID,
        Title:     req.Title,
        Content:   req.Content,
        Status:    "pending",
        Metadata:  req.Metadata,
    })
    if err != nil {
        return nil, err
    }

    // 4. 发送消息（根据 provider 类型）
    var messageID string
    var sendErr error

    switch provider.Code {
    case "feishu":
        messageID, sendErr = s.sendFeishu(channel.Config, req)
    default:
        sendErr = fmt.Errorf("unsupported provider: %s", provider.Code)
    }

    // 5. 更新日志
    if sendErr != nil {
        s.repo.UpdateLog(ctx, logID, "failed", "", sendErr.Error())
        return &SendResult{
            LogID:   logID,
            Success: false,
            Error:   sendErr.Error(),
        }, nil
    }

    s.repo.UpdateLog(ctx, logID, "sent", messageID, "")
    return &SendResult{
        LogID:     logID,
        Success:   true,
        MessageID: messageID,
    }, nil
}

func (s *NotificationService) sendFeishu(config map[string]interface{}, req SendRequest) (string, error) {
    webhook := config["webhook"].(string)
    
    colorMap := map[string]string{
        "blue":   "blue",
        "green":  "green",
        "red":    "red",
        "orange": "orange",
        "grey":   "grey",
    }
    color := colorMap[req.Color]
    if color == "" {
        color = "blue"
    }

    card := map[string]interface{}{
        "msg_type": "interactive",
        "card": map[string]interface{}{
            "header": map[string]interface{}{
                "title":    map[string]string{"tag": "plain_text", "content": req.Title},
                "template": color,
            },
            "elements": []map[string]interface{}{
                {
                    "tag":  "div",
                    "text": map[string]string{"tag": "lark_md", "content": req.Content},
                },
            },
        },
    }

    body, _ := json.Marshal(card)
    resp, err := http.Post(webhook, "application/json", bytes.NewBuffer(body))
    if err != nil {
        return "", err
    }
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)

    if code, ok := result["code"].(float64); ok && code == 0 {
        if data, ok := result["data"].(map[string]interface{}); ok {
            if msgID, ok := data["message_id"].(string); ok {
                return msgID, nil
            }
        }
        return "", nil
    }

    return "", fmt.Errorf("feishu error: %v", result["msg"])
}

func (s *NotificationService) ListChannels(ctx context.Context) ([]Channel, error) {
    return s.repo.ListChannels(ctx)
}
```

---

### **2. CLI 命令（Agent OS）**

```go
// internal/cmd/notify.go

package cmd

import (
    "github.com/spf13/cobra"
)

var notifyCmd = &cobra.Command{
    Use:   "notify",
    Short: "Send notifications",
}

var notifySendCmd = &cobra.Command{
    Use:   "send",
    Short: "Send a notification",
    RunE: func(cmd *cobra.Command, args []string) error {
        channel, _ := cmd.Flags().GetString("channel")
        title, _ := cmd.Flags().GetString("title")
        content, _ := cmd.Flags().GetString("content")
        color, _ := cmd.Flags().GetString("color")

        service := getNotificationService()
        result, err := service.Send(cmd.Context(), SendRequest{
            Channel: channel,
            Title:   title,
            Content: content,
            Color:   color,
        })
        if err != nil {
            return err
        }

        if result.Success {
            fmt.Printf("✅ Sent successfully (log_id: %s)\n", result.LogID)
        } else {
            fmt.Printf("❌ Failed: %s\n", result.Error)
        }
        return nil
    },
}

var notifyListCmd = &cobra.Command{
    Use:   "list",
    Short: "List available channels",
    RunE: func(cmd *cobra.Command, args []string) error {
        service := getNotificationService()
        channels, err := service.ListChannels(cmd.Context())
        if err != nil {
            return err
        }

        fmt.Println("CODE      NAME       PROVIDER  STATUS")
        fmt.Println("─────────────────────────────────────")
        for _, ch := range channels {
            status := "✅"
            if !ch.Enabled {
                status = "❌"
            }
            fmt.Printf("%-10s %-10s %-10s %s\n", ch.Code, ch.Name, ch.ProviderName, status)
        }
        return nil
    },
}

func init() {
    notifySendCmd.Flags().String("channel", "", "Channel code (required)")
    notifySendCmd.Flags().String("title", "", "Title (required)")
    notifySendCmd.Flags().String("content", "", "Content (required)")
    notifySendCmd.Flags().String("color", "blue", "Color (blue/green/red/orange/grey)")
    notifySendCmd.MarkFlagRequired("channel")
    notifySendCmd.MarkFlagRequired("title")
    notifySendCmd.MarkFlagRequired("content")

    notifyCmd.AddCommand(notifySendCmd)
    notifyCmd.AddCommand(notifyListCmd)
    rootCmd.AddCommand(notifyCmd)
}
```

---

### **3. Agent-ts 工具（TypeScript）**

```typescript
// agent-ts/src/infrastructure/tools/notification-tools.ts

export const notificationSendTool = {
  name: 'notification_send',
  description: `发送通知消息到指定渠道。你应该先生成好消息内容，然后调用此工具发送。
  
渠道说明：
- trading: 交易群（交易信号、执行确认）
- alerts: 告警群（风险预警、系统异常）
- reports: 报告群（日报、周报）`,
  
  inputSchema: {
    type: 'object',
    properties: {
      channel: {
        type: 'string',
        enum: ['trading', 'alerts', 'reports'],
        description: '渠道代码'
      },
      title: {
        type: 'string',
        description: '消息标题'
      },
      content: {
        type: 'string',
        description: '消息内容（支持 Markdown 格式）'
      },
      color: {
        type: 'string',
        enum: ['blue', 'green', 'red', 'orange', 'grey'],
        description: '卡片颜色（可选，默认 blue）'
      }
    },
    required: ['channel', 'title', 'content']
  },
  
  async execute(args: {
    channel: string;
    title: string;
    content: string;
    color?: string;
  }) {
    const agentOsUrl = process.env.AGENT_OS_URL || 'http://127.0.0.1:8080';
    
    const response = await fetch(`${agentOsUrl}/api/notifications/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(args)
    });
    
    const result = await response.json();
    
    if (result.success) {
      return `✅ 通知已发送到 ${args.channel} 群（日志ID: ${result.log_id}）`;
    } else {
      return `❌ 发送失败: ${result.error}`;
    }
  }
};

export const notificationListChannelsTool = {
  name: 'notification_list_channels',
  description: '查询可用的通知渠道列表',
  
  inputSchema: {
    type: 'object',
    properties: {},
    required: []
  },
  
  async execute() {
    const agentOsUrl = process.env.AGENT_OS_URL || 'http://127.0.0.1:8080';
    
    const response = await fetch(`${agentOsUrl}/api/notifications/channels`);
    const channels = await response.json();
    
    return `可用渠道：\n${channels.map((ch: any) => 
      `- ${ch.code}: ${ch.name} (${ch.provider_name}) ${ch.enabled ? '✅' : '❌'}`
    ).join('\n')}`;
  }
};
```

---

## 🎯 Agent 使用示例

### **场景 1: 每日盘前报告**

```typescript
// Agent 工作流程

// 1. 收集数据
const marketData = await agent.callTool('market_status', {});
const signals = await agent.callTool('signal_scan', { timeframe: 'today' });
const portfolio = await agent.callTool('portfolio_status', {});
const risks = await agent.callTool('risk_check', {});

// 2. Agent 分析和生成内容
agent.think(`
我收集了：
- 市场状态: ${marketData.status}
- 投资信号: ${signals.length} 个
- 风险点: ${risks.length} 个

我应该：
1. 只突出高置信度的信号（>80%）
2. 如果有紧急风险，优先展示
3. 用简洁的语言
`);

const report = await agent.generate(`
生成今日盘前准备报告。

数据：
- 市场: ${JSON.stringify(marketData)}
- 信号: ${JSON.stringify(signals.slice(0, 10))}
- 风险: ${JSON.stringify(risks)}
- 持仓: ${JSON.stringify(portfolio)}

要求：
1. 标题用 emoji
2. 突出 2-3 个重点机会
3. 风险提示简洁
4. 总长度 <500 字
5. Markdown 格式
`);

// 3. Agent 发送
await agent.callTool('notification_send', {
  channel: 'trading',
  title: '🌅 盘前准备 - 2026-08-14',
  content: report,
  color: 'blue'
});
```

**Agent 生成的内容示例**:

```markdown
🔥 重点关注

**600519.SH 贵州茅台** (置信度 85%)
技术面突破：MA5上穿MA20，MACD转正
资金面配合：成交量放大 30%
建议：优先配置

**000858.SZ 五粮液** (置信度 78%)
超卖反弹：RSI 从 28 回升
支撑位确认：再次站上 ¥180
建议：适量参与

⚠️ 风险提示
大盘昨日下跌 1.2%，今日需谨慎

📊 持仓状况
可用资金：¥20万
持仓数：10只
```

---

## 📋 实施步骤

### **Phase 1: 数据库和基础服务（3天）**

**Day 1: 数据库**
- [ ] 创建 3 张表的迁移脚本
- [ ] 插入初始数据（feishu provider + 2 个 channels）
- [ ] 测试数据库查询

**Day 2: Go Service**
- [ ] 实现 NotificationService
- [ ] 实现 NotificationRepository
- [ ] 实现 Feishu 发送逻辑
- [ ] 单元测试

**Day 3: CLI 命令**
- [ ] 实现 `agent-os notify send`
- [ ] 实现 `agent-os notify list`
- [ ] 集成测试

---

### **Phase 2: Agent-ts 集成（2天）**

**Day 4: Agent 工具**
- [ ] 实现 `notification_send` 工具
- [ ] 实现 `notification_list_channels` 工具
- [ ] 注册到工具库

**Day 5: 迁移现有代码**
- [ ] 迁移 `FeishuNotificationService` 使用新工具
- [ ] 更新定时任务
- [ ] 端到端测试

---

### **Phase 3: 管理界面（可选，2天）**

**Day 6: API**
- [ ] GET /api/notifications/channels
- [ ] POST /api/notifications/channels
- [ ] PUT /api/notifications/channels/:code
- [ ] GET /api/notifications/logs

**Day 7: Web 页面**
- [ ] 渠道列表页面
- [ ] 渠道编辑页面
- [ ] 发送日志页面

---

## 📊 迁移策略

### **向后兼容**

保留现有代码，逐步迁移：

```typescript
// agent-ts/src/services/feishu-notification.service.ts

export class FeishuNotificationService {
  // 旧方法（保留，标记为 deprecated）
  /** @deprecated Use notification_send tool instead */
  async sendDailyReport(data: any) {
    // 内部改为调用新工具
    return agent.callTool('notification_send', {
      channel: 'trading',
      title: '📊 每日报告',
      content: this.renderReport(data)
    });
  }
  
  // 新方法
  private renderReport(data: any): string {
    // 生成报告内容
  }
}
```

---

## ✅ 验收标准

### **功能验收**

```bash
# 1. 列出渠道
agent-os notify list
# 预期：显示 trading, alerts 等渠道

# 2. 发送通知
agent-os notify send --channel trading --title "测试" --content "测试内容"
# 预期：飞书收到消息

# 3. Agent 使用
# 在 agent-ts 中让 Agent 发送通知
# 预期：Agent 能成功调用 notification_send 工具
```

### **数据验证**

```sql
-- 查询渠道
SELECT * FROM notification_channels;

-- 查询日志
SELECT * FROM notification_logs ORDER BY created_at DESC LIMIT 10;

-- 查询成功率
SELECT 
  channel_id,
  COUNT(*) as total,
  SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) as success
FROM notification_logs
GROUP BY channel_id;
```

---

## 🎯 总结

### **解决了什么问题**

**问题 2（飞书集成）**:
- ✅ 统一 user/channel 为数据库驱动的 channels
- ✅ 配置存数据库，动态可配
- ✅ Provider 抽象，易于扩展

**问题 3（通知系统）**:
- ✅ Agent 自由生成内容（不用程序模板）
- ✅ 简单的发送工具
- ✅ Agent 保持控制权

### **核心设计原则**

1. **Agent First**: Agent 生成内容，工具只负责发送
2. **数据驱动**: 配置存数据库，动态可配
3. **统一抽象**: Provider 模式，支持多种通知渠道
4. **可追溯**: 所有通知都有日志

---

**这个实施计划是否可行？需要我立即开始 Phase 1 吗？**
