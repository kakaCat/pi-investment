# 系统架构总结

## 🏗️ 完整层次结构

```
用户层
  ↓
应用层 (Web V2, 飞书应用)
  ↓
Agent-ts (策略 Agent + 121+ 工具)
  ↓
┌─────────────────┬─────────────────┐
│ 💰 金融业务层    │ 🌐 基础设施层    │
│ Portfolio       │ Agent OS        │
│ Trade           │ (通知网关)       │
│ Market Data     │                 │
│ Strategy        │                 │
│ Risk            │                 │
└─────────────────┴─────────────────┘
  ↓                       ↓
业务数据库          基础设施数据库
  ↓                       ↓
外部服务 (交易所、数据商、飞书/Slack/Email)
```

---

## 🎯 Agent OS 的定位

### **是什么**
✅ **基础设施网关** (Infrastructure Gateway)  
✅ **统一通知中台** (Notification Middleware)  
✅ **横切关注点服务** (Cross-cutting Concern Service)

### **不是什么**
❌ 不是金融业务服务  
❌ 不是 Agent 本身  
❌ 不是前端应用

### **职责**
- 🌐 统一通知入口
- 📡 路由到不同渠道 (飞书/Slack/Email)
- 💾 配置管理 (数据库驱动)
- 📊 日志记录 (完整审计)
- 🔌 Provider 抽象 (易于扩展)

---

## 📊 关键分层

### **金融业务层** 💰
- **职责**: 核心业务逻辑
- **服务**: Portfolio, Trade, Market Data, Strategy, Risk
- **数据**: portfolios, trades, orders, strategies...
- **调用方**: Agent-ts, Web V2, 飞书应用

### **基础设施层** 🌐  
- **职责**: 横切关注点
- **服务**: Agent OS (通知网关)
- **数据**: notification_providers, notification_channels, notification_logs
- **调用方**: 所有需要发送通知的服务

---

## 🔄 典型流程

### **盘前准备**
```
Agent-ts
  ↓ 调用金融工具
Portfolio Service → 查询持仓
Market Data Service → 获取行情
Risk Service → 评估风险
  ↓ 返回数据
Agent-ts 分析 + 生成报告
  ↓ 调用通知工具
Agent OS → 路由到飞书
  ↓
用户在飞书群看到报告
```

### **风险告警**
```
Agent-ts 监控
  ↓ 发现风险
Risk Service → 计算风险
  ↓
Agent-ts 生成告警
  ↓
Agent OS → 发送红色卡片
  ↓
用户立即收到告警
```

---

## ✅ 设计原则

### **1. 关注点分离**
- 金融业务服务专注业务
- Agent OS 专注通知
- 互不干扰

### **2. 复用性**
- 金融服务被多个应用调用
- Agent OS 为所有服务提供通知

### **3. 独立演进**
- 添加新策略不影响通知
- 添加新渠道不影响业务

### **4. 可测试性**
- 业务服务独立测试
- 通知服务独立测试

---

## 🎯 核心价值

**Agent OS 作为基础设施网关**:
- ✅ 解耦应用和外部通信平台
- ✅ 统一配置和日志管理
- ✅ 易于扩展新渠道
- ✅ 提供标准化 HTTP API

**金融业务层**:
- ✅ 专注核心业务逻辑
- ✅ 不关心通知细节
- ✅ 可被多个应用复用

---

**完整架构图**: [SYSTEM-ARCHITECTURE-DIAGRAM.md](SYSTEM-ARCHITECTURE-DIAGRAM.md)
