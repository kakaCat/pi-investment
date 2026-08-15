# Agent 与通知系统对接分析

**问题**: Agent 是否需要直接对接通知系统？

---

## 🤔 三种架构方案对比

### **方案 A: Agent 直接调用 CLI（当前方案）**

```
Agent (agent-ts)
    ↓
执行 CLI 命令
    ↓
agent-os notify send
    ↓
NotificationService
    ↓
Provider (Feishu/Slack/Email)
```

**优点**:
- ✅ 实现简单
- ✅ 无需网络依赖
- ✅ 本地部署

**缺点**:
- ❌ Agent 需要知道 agent-os 二进制路径
- ❌ CLI 调用有性能开销
- ❌ 不适合分布式部署

---

### **方案 B: Agent 调用 HTTP API（推荐）**

```
Agent (agent-ts)
    ↓
HTTP 请求
    ↓
agent-os serve (HTTP API)
    ↓
NotificationService
    ↓
Provider (Feishu/Slack/Email)
```

**优点**:
- ✅ **标准化接口**（HTTP/REST）
- ✅ **分布式友好**（Agent 和 OS 可以分开部署）
- ✅ **多语言支持**（任何语言都能调用 HTTP API）
- ✅ **易于监控**（HTTP 日志、指标）
- ✅ **适合微服务**

**缺点**:
- ⚠️ 需要运行 HTTP 服务器
- ⚠️ 网络依赖

---

### **方案 C: Agent 直接调用 Go Service（耦合）**

```
Agent (agent-ts)
    ↓
调用 Go 库（通过 FFI/CGO）
    ↓
NotificationService
    ↓
Provider
```

**优点**:
- ✅ 性能最高

**缺点**:
- ❌ **强耦合**（Agent 和 OS 必须在一起）
- ❌ 跨语言调用复杂
- ❌ 不适合分布式

---

## 🎯 推荐方案：混合架构

### **架构设计**

```
┌─────────────────────────────────────────────────────────┐
│  Agent (agent-ts)                                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │  notification_send 工具                         │    │
│  │  优先使用 HTTP API，降级到 CLI                  │    │
│  └─────────────────────────────────────────────────┘    │
└──────────────┬────────────────────┬─────────────────────┘
               ↓                    ↓
         HTTP API (推荐)        CLI (降级)
               ↓                    ↓
┌─────────────────────────────────────────────────────────┐
│  Agent OS                                                │
│  ┌──────────────┐        ┌──────────────────────────┐   │
│  │ serve 命令   │        │ notify send 命令         │   │
│  │ (HTTP 服务器)│        │ (CLI)                    │   │
│  └──────┬───────┘        └──────┬───────────────────┘   │
│         └───────────────────────┘                        │
│                    ↓                                     │
│         NotificationService                              │
│                    ↓                                     │
│         Provider Registry                                │
│                    ↓                                     │
│         Feishu | Slack | Email                           │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 实现方式

### **Agent 工具实现（智能降级）**

```typescript
// agent-ts/src/infrastructure/tools/notification/notification-tools.ts

export const notificationSendTool: ToolDefinition = {
  name: "notification_send",
  description: "发送通知（优先使用 API，降级到 CLI）",
  
  async execute(_toolCallId, params: any) {
    const { channel, title, content, color = 'blue' } = params;
    
    // 1. 尝试 HTTP API（推荐）
    try {
      return await sendViaAPI(params);
    } catch (error) {
      console.log('API 不可用，降级到 CLI');
      
      // 2. 降级到 CLI
      try {
        return await sendViaCLI(params);
      } catch (cliError) {
        return {
          content: [{ 
            type: "text" as const, 
            text: `❌ 发送失败: API 和 CLI 都不可用` 
          }]
        };
      }
    }
  }
};

// HTTP API 调用
async function sendViaAPI(params: any): Promise<any> {
  const agentOsUrl = process.env.AGENT_OS_API_URL || 'http://localhost:8080';
  
  const response = await fetch(`${agentOsUrl}/api/v1/notifications/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    timeout: 5000  // 5 秒超时
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  const result = await response.json();
  
  return {
    content: [{ 
      type: "text" as const, 
      text: `✅ 通知已发送到 ${params.channel} 群（via API）` 
    }],
    details: { success: true, method: 'api', ...result }
  };
}

// CLI 调用（降级）
async function sendViaCLI(params: any): Promise<any> {
  const { exec } = await import('child_process');
  const { promisify } = await import('util');
  const execAsync = promisify(exec);
  
  const agentOsBin = process.env.AGENT_OS_BIN || '../agent-os/agent-os';
  
  const cmd = `${agentOsBin} notify send --channel ${params.channel} --title "${params.title}" --content "${params.content}" --color ${params.color}`;
  
  const { stdout } = await execAsync(cmd, {
    env: { ...process.env, PGDATABASE: 'quant_investment' }
  });
  
  const logIdMatch = stdout.match(/Log ID: ([a-f0-9-]+)/);
  
  return {
    content: [{ 
      type: "text" as const, 
      text: `✅ 通知已发送到 ${params.channel} 群（via CLI）` 
    }],
    details: { success: true, method: 'cli', logId: logIdMatch?.[1] }
  };
}
```

---

### **环境变量配置**

```bash
# .env (agent-ts)

# 优先使用 API（推荐）
AGENT_OS_API_URL=http://localhost:8080

# 降级到 CLI（如果 API 不可用）
AGENT_OS_BIN=../agent-os/agent-os

# 数据库（CLI 需要）
PGDATABASE=quant_investment
```

---

### **启动方式**

#### **开发环境（本地）**

```bash
# Terminal 1: 启动 Agent OS API 服务器
cd agent-os
./agent-os serve --port 8080

# Terminal 2: 运行 Agent
cd agent-ts
npm run dev
```

#### **生产环境（推荐）**

```bash
# 使用 systemd 或 docker 运行 Agent OS API
docker run -d -p 8080:8080 agent-os serve

# Agent 通过 HTTP API 调用
# 环境变量: AGENT_OS_API_URL=http://agent-os:8080
```

#### **单机环境（降级）**

```bash
# 不启动 API 服务器
# Agent 自动降级到 CLI
# 环境变量: AGENT_OS_BIN=/usr/local/bin/agent-os
```

---

## 🎯 各种场景对比

### **场景 1: 本地开发**

**推荐**: HTTP API
```bash
agent-os serve --port 8080  # 后台运行
# Agent 通过 localhost:8080 调用
```

---

### **场景 2: 生产环境（单机）**

**推荐**: HTTP API + systemd
```bash
# /etc/systemd/system/agent-os.service
[Service]
ExecStart=/usr/local/bin/agent-os serve --port 8080
```

---

### **场景 3: 生产环境（分布式）**

**推荐**: HTTP API + K8s
```yaml
# agent-os-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: agent-os
spec:
  ports:
  - port: 8080
  selector:
    app: agent-os
```

Agent 通过 Service 调用：
```
AGENT_OS_API_URL=http://agent-os.default.svc.cluster.local:8080
```

---

### **场景 4: 离线/边缘设备**

**推荐**: CLI（降级）
```bash
# 没有网络，API 不可用
# Agent 自动降级到 CLI
AGENT_OS_BIN=/usr/local/bin/agent-os
```

---

## ✅ 最终设计决策

### **Agent 对接方式**

**主要方式**: **HTTP API**（推荐）
- ✅ 标准化
- ✅ 分布式友好
- ✅ 易于监控

**降级方式**: **CLI**
- ✅ 离线可用
- ✅ 简单部署

---

### **实施优先级**

**Phase 4A: HTTP API（必须）**
- [ ] 实现 HTTP Server
- [ ] 实现 API endpoints
- [ ] 添加 serve 命令

**Phase 4B: Agent 工具改造（必须）**
- [ ] 实现 HTTP API 调用
- [ ] 保留 CLI 降级
- [ ] 智能切换逻辑

**Phase 4C: Provider 抽象（推荐）**
- [ ] Provider 接口
- [ ] Provider Registry
- [ ] Slack/Email Provider

---

## 🎯 回答你的问题

### **"agent 是否也需要对接这个？"**

**回答**: **是的，必须对接！**

**方式**: 
1. ✅ **主要**: HTTP API（标准、分布式）
2. ✅ **降级**: CLI（离线、简单）

**理由**:
- Agent 是通知系统的**主要用户**
- 需要标准化接口（HTTP）
- 需要降级方案（CLI）
- 适应不同部署场景

---

**你希望我立即实施哪个 Phase？**
1. Phase 4A: HTTP API（对外接口）
2. Phase 4B: Agent 工具改造（智能降级）
3. Phase 4C: Provider 抽象（可扩展性）

还是**全部一起做**？
