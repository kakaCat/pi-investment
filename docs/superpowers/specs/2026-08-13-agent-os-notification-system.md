# Agent OS 通知系统设计

> **创建时间**: 2026-08-13  
> **补充**: 飞书/微信/X 等外部通知渠道集成

---

## 1. 问题定义

### 当前缺失
- Agent 完成任务后，用户不在电脑前 → 无法及时知道
- 重要事件（交易执行、风险告警）→ 需要推送到手机
- 多渠道支持：飞书（当前）、微信（未来）、X（未来）、邮件、短信

### 设计目标
- **统一通知抽象**：Agent OS 不关心是飞书还是微信，只需 `notify(user, message)`
- **渠道可插拔**：新增通知渠道不改 OS 核心代码
- **优先级路由**：紧急告警 → 飞书 + 短信，普通通知 → 飞书
- **模板化**：不同事件类型有不同的消息模板

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       Agent OS Core                              │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Notification Manager (Go)                                 │  │
│  │                                                            │  │
│  │  notify(user, event_type, payload, priority)              │  │
│  │    │                                                       │  │
│  │    ├─▶ 路由规则匹配                                       │  │
│  │    ├─▶ 模板渲染                                           │  │
│  │    ├─▶ 选择渠道（飞书 / 微信 / X / 邮件）                │  │
│  │    └─▶ 调用对应 Driver                                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          │                                       │
│                          │ gRPC / HTTP                           │
└──────────────────────────┼───────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│Feishu Driver │  │ WeChat Driver│  │  X Driver    │
│(Python/Go)   │  │  (Python)    │  │  (Python)    │
│Port: 50053   │  │ Port: 50054  │  │ Port: 50055  │
│              │  │              │  │              │
│飞书 Bot API  │  │企业微信 API  │  │Twitter API   │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 2.2 数据流

```
Event 发生 (任务完成、交易执行、风险告警)
   │
   ▼
Agent OS 核心组件触发通知
   │
   ▼
Notification Manager
   ├─ 查询用户配置（user_id → 通知偏好）
   ├─ 匹配路由规则（event_type + priority → channels）
   ├─ 渲染消息模板
   └─ 并发调用多个 Driver
         ├─▶ Feishu Driver → 飞书 Bot API
         ├─▶ WeChat Driver → 企业微信 API
         └─▶ Email Driver  → SMTP
   │
   ▼
记录通知历史（notification_logs 表）
```

---

## 3. 核心组件设计

### 3.1 Notification Manager (Go)

```go
// internal/kernel/notification/manager.go
package notification

import (
    "context"
    "fmt"
    "sync"
)

type NotificationManager struct {
    drivers map[string]NotificationDriver  // "feishu" -> FeishuDriver
    router  *NotificationRouter
    logger  *zap.Logger
}

type NotificationDriver interface {
    Send(ctx context.Context, req *SendRequest) error
    Name() string
    IsHealthy() bool
}

type SendRequest struct {
    UserID      string
    Title       string
    Message     string
    Priority    Priority
    EventType   string
    Metadata    map[string]interface{}
}

type Priority string
const (
    PriorityLow      Priority = "low"
    PriorityNormal   Priority = "normal"
    PriorityHigh     Priority = "high"
    PriorityCritical Priority = "critical"
)

// Notify 发送通知（核心方法）
func (m *NotificationManager) Notify(
    ctx context.Context,
    userID string,
    eventType string,
    payload map[string]interface{},
    priority Priority,
) error {
    // 1. 查询用户配置
    userConfig, err := m.getUserConfig(userID)
    if err != nil {
        return fmt.Errorf("failed to get user config: %w", err)
    }
    
    // 2. 路由：根据 event_type + priority 选择渠道
    channels := m.router.Route(eventType, priority, userConfig)
    m.logger.Info("Routing notification",
        zap.String("user", userID),
        zap.String("event", eventType),
        zap.Strings("channels", channels))
    
    // 3. 渲染消息模板
    title, message, err := m.renderTemplate(eventType, payload)
    if err != nil {
        return fmt.Errorf("failed to render template: %w", err)
    }
    
    // 4. 并发发送到多个渠道
    var wg sync.WaitGroup
    errors := make(chan error, len(channels))
    
    for _, channel := range channels {
        driver, ok := m.drivers[channel]
        if !ok || !driver.IsHealthy() {
            m.logger.Warn("Driver not available", zap.String("channel", channel))
            continue
        }
        
        wg.Add(1)
        go func(drv NotificationDriver) {
            defer wg.Done()
            
            req := &SendRequest{
                UserID:    userID,
                Title:     title,
                Message:   message,
                Priority:  priority,
                EventType: eventType,
                Metadata:  payload,
            }
            
            if err := drv.Send(ctx, req); err != nil {
                m.logger.Error("Failed to send notification",
                    zap.String("channel", drv.Name()),
                    zap.Error(err))
                errors <- err
            }
        }(driver)
    }
    
    wg.Wait()
    close(errors)
    
    // 5. 记录通知历史
    m.logNotification(userID, eventType, channels, len(errors) > 0)
    
    // 如果所有渠道都失败，返回错误
    if len(errors) == len(channels) {
        return fmt.Errorf("all channels failed")
    }
    
    return nil
}
```

### 3.2 Notification Router

```go
// internal/kernel/notification/router.go
package notification

type NotificationRouter struct {
    rules []RoutingRule
}

type RoutingRule struct {
    EventTypes []string   // ["task.completed", "task.failed"]
    Priority   Priority
    Channels   []string   // ["feishu", "email"]
}

// Route 根据事件类型和优先级选择渠道
func (r *NotificationRouter) Route(
    eventType string,
    priority Priority,
    userConfig *UserConfig,
) []string {
    // 默认规则
    var channels []string
    
    switch priority {
    case PriorityCritical:
        // 紧急：飞书 + 短信 + 邮件
        channels = []string{"feishu", "sms", "email"}
        
    case PriorityHigh:
        // 高优先级：飞书 + 邮件
        channels = []string{"feishu", "email"}
        
    case PriorityNormal:
        // 普通：飞书
        channels = []string{"feishu"}
        
    case PriorityLow:
        // 低优先级：仅记录，不推送
        channels = []string{}
    }
    
    // 用户自定义规则覆盖
    if userConfig.NotificationRules != nil {
        for _, rule := range userConfig.NotificationRules {
            if contains(rule.EventTypes, eventType) {
                channels = rule.Channels
                break
            }
        }
    }
    
    // 过滤用户禁用的渠道
    filtered := []string{}
    for _, ch := range channels {
        if !contains(userConfig.DisabledChannels, ch) {
            filtered = append(filtered, ch)
        }
    }
    
    return filtered
}
```

### 3.3 消息模板

```go
// internal/kernel/notification/template.go
package notification

var templates = map[string]MessageTemplate{
    "task.completed": {
        Title:   "任务完成",
        Message: "任务「{{.task_name}}」已成功完成\n耗时: {{.duration}}秒\nToken: {{.token_consumed}}",
    },
    "task.failed": {
        Title:   "❌ 任务失败",
        Message: "任务「{{.task_name}}」执行失败\n错误: {{.error_message}}",
    },
    "trading.executed": {
        Title:   "🔔 交易执行",
        Message: "{{.action}} {{.symbol}} {{.quantity}}股 @ ¥{{.price}}",
    },
    "risk.alert": {
        Title:   "🚨 风险告警",
        Message: "{{.alert_type}}: {{.message}}\n当前持仓: {{.position}}\n浮动亏损: {{.loss}}",
    },
    "quota.exceeded": {
        Title:   "⚠️ 配额超限",
        Message: "Agent「{{.agent_id}}」今日 Token 配额已用尽\n已用: {{.used}} / {{.quota}}",
    },
}

type MessageTemplate struct {
    Title   string
    Message string
}

func (m *NotificationManager) renderTemplate(
    eventType string,
    payload map[string]interface{},
) (string, string, error) {
    tmpl, ok := templates[eventType]
    if !ok {
        // 兜底模板
        return "系统通知", fmt.Sprintf("%v", payload), nil
    }
    
    title := renderString(tmpl.Title, payload)
    message := renderString(tmpl.Message, payload)
    
    return title, message, nil
}

func renderString(template string, data map[string]interface{}) string {
    result := template
    for key, value := range data {
        placeholder := fmt.Sprintf("{{.%s}}", key)
        result = strings.ReplaceAll(result, placeholder, fmt.Sprint(value))
    }
    return result
}
```

---

## 4. 通知驱动实现

### 4.1 Feishu Driver (Python gRPC)

```python
# drivers/feishu_driver/main.py
import grpc
from concurrent import futures
import requests
import json

from proto import notification_pb2
from proto import notification_pb2_grpc

class FeishuDriver(notification_pb2_grpc.NotificationDriverServicer):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        
    def Send(self, request, context):
        """发送飞书消息"""
        try:
            # 构造飞书消息卡片
            card = self._build_card(
                title=request.title,
                message=request.message,
                priority=request.priority,
                metadata=json.loads(request.metadata_json)
            )
            
            # 调用飞书 Webhook
            resp = requests.post(
                self.webhook_url,
                json={"msg_type": "interactive", "card": card},
                timeout=10
            )
            
            if resp.status_code != 200:
                return notification_pb2.SendResponse(
                    success=False,
                    error=f"Feishu API error: {resp.status_code}"
                )
            
            return notification_pb2.SendResponse(success=True)
            
        except Exception as e:
            return notification_pb2.SendResponse(
                success=False,
                error=str(e)
            )
    
    def _build_card(self, title, message, priority, metadata):
        """构造飞书消息卡片"""
        # 根据优先级选择颜色
        color_map = {
            "low": "grey",
            "normal": "blue",
            "high": "orange",
            "critical": "red"
        }
        color = color_map.get(priority, "blue")
        
        card = {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": color
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": message}
                }
            ]
        }
        
        # 添加操作按钮（如果有任务 ID）
        if "execution_id" in metadata:
            card["elements"].append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看详情"},
                        "url": f"http://localhost:3001/tasks/{metadata['task_id']}/executions/{metadata['execution_id']}",
                        "type": "primary"
                    }
                ]
            })
        
        return card

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # 从环境变量读取 Webhook URL
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")
    
    notification_pb2_grpc.add_NotificationDriverServicer_to_server(
        FeishuDriver(webhook_url),
        server
    )
    
    server.add_insecure_port('[::]:50053')
    server.start()
    print("Feishu Driver started on port 50053")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
```

#### gRPC Proto 定义

```protobuf
// drivers/proto/notification.proto
syntax = "proto3";

package notification;

service NotificationDriver {
  rpc Send(SendRequest) returns (SendResponse);
  rpc Ping(PingRequest) returns (PingResponse);
}

message SendRequest {
  string user_id = 1;
  string title = 2;
  string message = 3;
  string priority = 4;     // low / normal / high / critical
  string event_type = 5;
  string metadata_json = 6; // JSON string
}

message SendResponse {
  bool success = 1;
  string error = 2;
}

message PingRequest {}
message PingResponse {
  bool healthy = 1;
}
```

### 4.2 Go 侧调用 Feishu Driver

```go
// internal/drivers/feishu/client.go
package feishu

import (
    "context"
    "encoding/json"
    
    "google.golang.org/grpc"
    pb "agent-os/drivers/proto"
)

type FeishuDriver struct {
    conn   *grpc.ClientConn
    client pb.NotificationDriverClient
}

func NewFeishuDriver(addr string) (*FeishuDriver, error) {
    conn, err := grpc.Dial(addr, grpc.WithInsecure())
    if err != nil {
        return nil, err
    }
    
    return &FeishuDriver{
        conn:   conn,
        client: pb.NewNotificationDriverClient(conn),
    }, nil
}

func (d *FeishuDriver) Send(ctx context.Context, req *SendRequest) error {
    metadataJSON, _ := json.Marshal(req.Metadata)
    
    resp, err := d.client.Send(ctx, &pb.SendRequest{
        UserId:       req.UserID,
        Title:        req.Title,
        Message:      req.Message,
        Priority:     string(req.Priority),
        EventType:    req.EventType,
        MetadataJson: string(metadataJSON),
    })
    
    if err != nil {
        return err
    }
    
    if !resp.Success {
        return fmt.Errorf("feishu send failed: %s", resp.Error)
    }
    
    return nil
}

func (d *FeishuDriver) Name() string {
    return "feishu"
}

func (d *FeishuDriver) IsHealthy() bool {
    ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
    defer cancel()
    
    resp, err := d.client.Ping(ctx, &pb.PingRequest{})
    return err == nil && resp.Healthy
}
```

### 4.3 WeChat Driver（未来）

```python
# drivers/wechat_driver/main.py
# 类似 Feishu Driver 结构
# 调用企业微信 API: https://qyapi.weixin.qq.com/cgi-bin/webhook/send
```

### 4.4 X (Twitter) Driver（未来）

```python
# drivers/x_driver/main.py
# 调用 Twitter API v2: https://api.twitter.com/2/tweets
```

---

## 5. 配置文件

### 5.1 OS 配置

```yaml
# configs/agent-os.yaml
notification:
  enabled: true
  drivers:
    feishu:
      grpc_addr: "localhost:50053"
      enabled: true
    wechat:
      grpc_addr: "localhost:50054"
      enabled: false  # 未来启用
    x:
      grpc_addr: "localhost:50055"
      enabled: false
    email:
      smtp_host: "smtp.gmail.com"
      smtp_port: 587
      enabled: false
```

### 5.2 用户通知配置

```yaml
# configs/user-notifications.yaml
users:
  - user_id: "yunpeng"
    feishu_user_id: "ou_xxx"  # 飞书 Open ID
    wechat_user_id: "xxx"     # 企业微信 User ID
    
    # 自定义路由规则
    notification_rules:
      - event_types: ["task.completed", "task.failed"]
        channels: ["feishu"]
      
      - event_types: ["trading.executed", "risk.alert"]
        channels: ["feishu", "sms"]  # 交易和风险推送短信
      
      - event_types: ["quota.exceeded"]
        channels: ["email"]  # 配额告警发邮件
    
    # 禁用渠道
    disabled_channels: []
    
    # 免打扰时段
    quiet_hours:
      enabled: true
      start: "22:00"
      end: "08:00"
      allow_critical: true  # 紧急告警仍推送
```

---

## 6. 使用示例

### 6.1 任务完成通知

```go
// internal/kernel/scheduler/executor.go
func (e *Executor) executeTask(...) error {
    // ... 执行任务
    
    // 任务完成，发送通知
    e.notificationMgr.Notify(context.Background(),
        task.Owner,  // "fin-agent" 对应的 user_id
        "task.completed",
        map[string]interface{}{
            "task_name":      task.Name,
            "task_id":        task.ID,
            "execution_id":   exec.ID,
            "duration":       exec.DurationSec,
            "token_consumed": exec.TokenConsumed,
        },
        notification.PriorityNormal,
    )
    
    return nil
}
```

飞书收到的消息：
```
┌────────────────────────────────────┐
│ 任务完成                            │  (蓝色标题)
├────────────────────────────────────┤
│ 任务「daily_recall_audit」已成功完成 │
│ 耗时: 45秒                          │
│ Token: 1200                         │
│                                     │
│ [查看详情] (按钮)                   │
└────────────────────────────────────┘
```

### 6.2 风险告警通知

```go
// internal/kernel/risk/monitor.go
func (m *RiskMonitor) checkRisk() {
    if position.Loss > threshold {
        m.notificationMgr.Notify(context.Background(),
            "yunpeng",
            "risk.alert",
            map[string]interface{}{
                "alert_type": "止损触发",
                "message":    "600519.SH 浮亏超过 10%",
                "position":   "100 股",
                "loss":       "-15000 元",
            },
            notification.PriorityCritical,  // 紧急
        )
    }
}
```

飞书收到的消息：
```
┌────────────────────────────────────┐
│ 🚨 风险告警                         │  (红色标题)
├────────────────────────────────────┤
│ 止损触发: 600519.SH 浮亏超过 10%    │
│ 当前持仓: 100 股                    │
│ 浮动亏损: -15000 元                 │
└────────────────────────────────────┘
```

同时发送短信到手机（因为是 PriorityCritical）

### 6.3 配额超限通知

```go
// internal/kernel/resource/manager.go
func (m *Manager) CheckQuota(agentID string) bool {
    if usage.TokenUsed >= quota.TokenPerDay {
        m.notificationMgr.Notify(context.Background(),
            "yunpeng",
            "quota.exceeded",
            map[string]interface{}{
                "agent_id": agentID,
                "used":     usage.TokenUsed,
                "quota":    quota.TokenPerDay,
            },
            notification.PriorityHigh,
        )
        return false
    }
    return true
}
```

---

## 7. 数据库 Schema

```sql
-- 通知历史表
CREATE TABLE notification_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    
    channels TEXT[],              -- ['feishu', 'email']
    success BOOLEAN NOT NULL,
    
    metadata JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notification_user ON notification_logs(user_id);
CREATE INDEX idx_notification_event ON notification_logs(event_type);
CREATE INDEX idx_notification_time ON notification_logs(created_at DESC);

-- 用户通知配置表
CREATE TABLE user_notification_configs (
    user_id VARCHAR(50) PRIMARY KEY,
    
    feishu_user_id VARCHAR(100),
    wechat_user_id VARCHAR(100),
    email VARCHAR(200),
    phone VARCHAR(20),
    
    notification_rules JSONB,     -- 自定义路由规则
    disabled_channels TEXT[],
    
    quiet_hours JSONB,            -- {enabled: true, start: "22:00", end: "08:00"}
    
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 8. 系统架构图（更新）

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Human User                                     │
└───────────┬────────────────────────────┬────────────────────────────┘
            │                            │
            │ Web 浏览器                 │ 飞书 / 微信 / X
            ▼                            ▼
┌─────────────────────┐      ┌─────────────────────────────────────┐
│   web-frontend      │      │  Notification Channels               │
│   (Vue3)            │      │  - 飞书消息卡片                      │
└──────────┬──────────┘      │  - 微信企业号消息                    │
           │                  │  - X (Twitter) 私信                  │
           │ HTTP             │  - 邮件                              │
           ▼                  │  - 短信                              │
┌─────────────────────────────────────────────────────────────────────┐
│                      Agent OS (Go)                                   │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Core Services                                                   │ │
│  │  Scheduler │ Resource Mgr │ Memory │ Decision │ ...            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                          │ 触发通知                                  │
│  ┌────────────────────────▼──────────────────────────────────────┐ │
│  │ Notification Manager                                           │ │
│  │  - 路由规则匹配                                                │ │
│  │  - 模板渲染                                                    │ │
│  │  - 渠道选择                                                    │ │
│  └────────────────┬──────────────┬──────────────┬─────────────────┘ │
└───────────────────┼──────────────┼──────────────┼───────────────────┘
                    │ gRPC         │ gRPC         │ gRPC
                    ▼              ▼              ▼
          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
          │Feishu Driver │ │WeChat Driver │ │  X Driver    │
          │(Python)      │ │(Python)      │ │(Python)      │
          │Port: 50053   │ │Port: 50054   │ │Port: 50055   │
          └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                 │                │                │
                 ▼                ▼                ▼
          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
          │飞书 Bot API  │ │企业微信 API  │ │Twitter API   │
          │(外部)        │ │(外部)        │ │(外部)        │
          └──────────────┘ └──────────────┘ └──────────────┘
```

---

## 9. 实施路径

### MVP（Phase 1）：飞书通知
- [ ] Notification Manager 核心框架
- [ ] Feishu Driver (Python gRPC)
- [ ] 3 个事件类型：task.completed、task.failed、risk.alert
- [ ] 基础路由规则（按优先级）
- [ ] 消息模板

### Phase 2：多渠道支持
- [ ] WeChat Driver（企业微信）
- [ ] Email Driver（SMTP）
- [ ] SMS Driver（阿里云短信）
- [ ] 用户自定义路由规则

### Phase 3：高级特性
- [ ] 免打扰时段
- [ ] 消息聚合（5 分钟内同类型消息合并）
- [ ] 通知历史查询 API
- [ ] web-frontend 通知配置页

---

## 10. 关键决策点

### 决策 1：为什么用 gRPC Driver 而不是直接调 API？

**理由**：
- **隔离性**：飞书 API Token 等敏感信息不进 OS 核心
- **可插拔**：新增渠道只需加 Driver，不改 OS
- **容错性**：Driver 崩溃不影响 OS 核心
- **语言自由**：Driver 可以用 Python（飞书 SDK 丰富）

### 决策 2：为什么需要 Notification Manager？

**理由**：
- **统一抽象**：OS 核心组件只需调 `notify()`，不关心飞书还是微信
- **路由规则**：不同事件、不同优先级走不同渠道
- **失败重试**：一个渠道失败，自动尝试其他渠道
- **审计日志**：所有通知记录到数据库

### 决策 3：为什么需要优先级？

**理由**：
- **避免打扰**：普通任务完成 → 只推飞书
- **紧急响应**：风险告警 → 飞书 + 短信双重保障
- **成本控制**：短信按条收费，只用于紧急场景

---

## 11. 与现有架构的集成

### 在 Scheduler 中集成

```go
// internal/kernel/scheduler/executor.go
func (e *Executor) executeTask(...) error {
    // 执行任务
    err := e.doExecute(...)
    
    // 发送通知
    if err != nil {
        e.notificationMgr.Notify(ctx, task.Owner, "task.failed", 
            map[string]interface{}{
                "task_name": task.Name,
                "error_message": err.Error(),
            },
            notification.PriorityHigh)
    } else {
        e.notificationMgr.Notify(ctx, task.Owner, "task.completed",
            map[string]interface{}{
                "task_name": task.Name,
                "duration": exec.DurationSec,
                "token_consumed": exec.TokenConsumed,
            },
            notification.PriorityNormal)
    }
    
    return err
}
```

### 在 Resource Manager 中集成

```go
// internal/kernel/resource/manager.go
func (m *Manager) CheckQuota(agentID string) bool {
    if usage.TokenUsed >= quota.TokenPerDay {
        m.notificationMgr.Notify(ctx, m.getUserID(agentID), "quota.exceeded",
            map[string]interface{}{
                "agent_id": agentID,
                "used": usage.TokenUsed,
                "quota": quota.TokenPerDay,
            },
            notification.PriorityHigh)
        return false
    }
    return true
}
```

### 在 agent-ts 中集成（可选）

```typescript
// agent-ts 也可以直接调用 OS 的通知 API
await fetch('http://localhost:8080/api/notification/send', {
  method: 'POST',
  body: JSON.stringify({
    user_id: 'yunpeng',
    event_type: 'custom.event',
    payload: {...},
    priority: 'normal'
  })
});
```

---

## 12. 你的决策点

1. **飞书 Webhook URL 怎么配置？**
   - 环境变量？配置文件？数据库？

2. **用户如何绑定飞书账号？**
   - 手动在配置文件写 `feishu_user_id`？
   - web-frontend 提供绑定页面？

3. **MVP 包含哪些通知类型？**
   - 建议：task.completed, task.failed, risk.alert
   - 你还需要哪些？

4. **优先级策略合理吗？**
   - Critical → 飞书 + 短信
   - High → 飞书 + 邮件
   - Normal → 飞书
   - Low → 不推送

5. **什么时候实施？**
   - MVP 同步做（Week 3）？
   - Phase 2 再加（Week 5+）？

告诉我你的想法！
