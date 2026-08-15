# Agent OS 在整个系统中的位置

**日期**: 2026-08-14  
**当前架构**: 统一通知网关

---

## 🏗️ 完整系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│  用户层 (Users)                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  投资者       │  │  运维人员     │  │  开发者       │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
└─────────┼──────────────────┼──────────────────┼──────────────────────────┘
          │                  │                  │
          ↓                  ↓                  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  应用层 (Applications)                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  Web V2      │  │  飞书应用     │  │  其他客户端   │                  │
│  │  (前端界面)   │  │  (飞书机器人) │  │  (移动端等)   │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                  │                          │
│         │  查看报告/交易   │  接收通知        │  调用 API               │
│         │                  │                  │                          │
└─────────┼──────────────────┼──────────────────┼──────────────────────────┘
          │                  │                  │
          ↓                  ↓                  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  Agent-ts (Agent)                                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  📊 策略 Agent                                                      │ │
│  │  - 分析市场                                                         │ │
│  │  - 生成交易信号                                                     │ │
│  │  - 生成报告                                                         │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  🛠️ Agent 工具箱 (121+ tools)                                      │ │
│  │  金融业务工具:                                                      │ │
│  │  - portfolio_status (查询持仓)                                     │ │
│  │  - portfolio_trade (执行交易)                                      │ │
│  │  - data_fetch_quote (获取行情)                                     │ │
│  │  - data_fetch_kline (获取K线)                                      │ │
│  │  - strategy_backtest (策略回测)                                    │ │
│  │  - risk_analysis (风险分析)                                        │ │
│  │  基础设施工具:                                                      │ │
│  │  - notification_send (发送通知) ⭐ 新增                            │ │
│  │  - feishu_notify (废弃)                                            │ │
│  │  - ...                                                              │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────┬───────────────────────────┬────────────────────────────────────┘
          │                           │
          │ 调用金融业务服务           │ 调用基础设施服务
          │                           │
          ↓                           ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  💰 金融业务服务层 (Financial Services)                                  │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Portfolio Service (持仓管理)                                      │ │
│  │  - 查询持仓                                                         │ │
│  │  - 更新持仓                                                         │ │
│  │  - 计算收益                                                         │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Trade Service (交易执行)                                          │ │
│  │  - 下单                                                             │ │
│  │  - 撤单                                                             │ │
│  │  - 查询订单                                                         │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Market Data Service (行情数据)                                    │ │
│  │  - 实时行情                                                         │ │
│  │  - 历史数据                                                         │ │
│  │  - K线数据                                                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Strategy Service (策略服务)                                       │ │
│  │  - 策略回测                                                         │ │
│  │  - 信号生成                                                         │ │
│  │  - 策略评估                                                         │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Risk Service (风险管理)                                           │ │
│  │  - 风险指标计算                                                     │ │
│  │  - 风险预警                                                         │ │
│  │  - 仓位控制                                                         │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  🌐 Agent OS (统一基础设施网关) ⭐ 核心位置                              │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  HTTP API Server (:8080)                                           │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │  API Endpoints                                               │ │ │
│  │  │  POST /api/v1/notifications/send     发送通知               │ │ │
│  │  │  GET  /api/v1/notifications/channels 查询渠道               │ │ │
│  │  │  GET  /api/v1/notifications/logs     查询日志               │ │ │
│  │  │  GET  /api/v1/notifications/providers 查询提供商            │ │ │
│  │  │  GET  /health                         健康检查               │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  CLI                                                               │ │
│  │  agent-os notify send/list/logs                                   │ │
│  │  (HTTP wrapper - 调用上面的 API)                                  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  业务层                                                            │ │
│  │  NotificationService                                              │ │
│  │  - 通知路由                                                        │ │
│  │  - 日志记录                                                        │ │
│  │  - 重试机制                                                        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Provider Registry (提供商注册中心)                               │ │
│  │  - 动态加载 Provider                                               │ │
│  │  - 自动注册机制                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Providers (通知提供商)                                            │ │
│  │  ┌─────────┬─────────┬─────────┬─────────┬─────────────────────┐ │ │
│  │  │ Feishu  │ Slack   │ Email   │ SMS     │ Telegram/Discord... │ │ │
│  │  └─────────┴─────────┴─────────┴─────────┴─────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────┬───────────────────┬─────────────────────┬────────────────────┘
          │                   │                     │
          ↓                   ↓                     ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  数据层 (Database)                                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL (quant_investment)                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │  💰 金融业务表                                                │ │ │
│  │  │  - portfolios           (持仓)                                │ │ │
│  │  │  - trades               (交易记录)                            │ │ │
│  │  │  - orders               (订单)                                │ │ │
│  │  │  - strategies           (策略)                                │ │ │
│  │  │  - signals              (交易信号)                            │ │ │
│  │  │  - market_data          (行情数据)                            │ │ │
│  │  │  - risk_metrics         (风险指标)                            │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │  🌐 基础设施表 (Agent OS)                                     │ │ │
│  │  │  - notification_providers  (通知提供商配置)                  │ │ │
│  │  │  - notification_channels   (通知渠道配置)                    │ │ │
│  │  │  - notification_logs       (发送日志)                        │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
          │                   │                     │
          ↓                   ↓                     ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  外部服务 (External Services)                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  飞书         │  │  Slack       │  │  邮件服务器   │                  │
│  │  (Feishu)    │  │              │  │  (SMTP)      │                  │
│  │  Webhook API │  │  Webhook API │  │              │                  │
│  └──────┬───────┘  └──────────────┘  └──────────────┘                  │
└─────────┼──────────────────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  最终用户 (End Users)                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  飞书群       │  │  Slack 频道  │  │  邮箱         │                  │
│  │  (用户查看)   │  │              │  │              │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Agent OS 的核心位置

### **定位**: **统一通知网关 (Unified Notification Gateway)**

Agent OS 在系统中扮演的角色：

1. **统一入口**
   - 所有应用通过 Agent OS 发送通知
   - 不直接对接飞书/Slack/Email

2. **路由中心**
   - 根据 channel 路由到不同渠道
   - 根据 provider 调用不同服务

3. **配置中心**
   - 渠道配置存数据库
   - 动态可调整

4. **日志中心**
   - 所有通知都有日志
   - 便于追踪和审计

---

## 🔄 完整业务流程示例

### **流程 1: Agent 盘前准备流程**

```
1. 定时任务触发 (每天 8:30)
   Cron → Agent-ts
   ↓
2. Agent 调用金融业务工具收集数据
   portfolio_status()        → 查询当前持仓
   data_fetch_quote()        → 获取最新行情
   market_analysis()         → 分析市场情绪
   risk_analysis()           → 评估风险指标
   ↓
3. Agent 调用金融业务服务
   Portfolio Service → 返回持仓明细
   Market Data Service → 返回行情数据
   Risk Service → 返回风险指标
   ↓
4. Agent 智能分析和生成内容
   - 分析持仓盈亏
   - 识别交易机会
   - 评估风险状况
   - 生成 Markdown 报告
   ↓
5. Agent 调用通知工具
   notification_send({
     channel: 'trading',
     title: '🌅 盘前准备 - 2026-08-14',
     content: `
       **持仓概况**
       - 总资产: ¥1,050,000 (+2.5%)
       - 持仓: 11只
       
       **今日机会**
       - 600519.SH 突破买点
       - 000858.SZ 回调买点
       
       **风险提示**
       - 市场波动率上升
       - 建议减仓科技股
     `
   })
   ↓
6. 通知工具调用 Agent OS
   POST http://agent-os:8080/api/v1/notifications/send
   ↓
7. Agent OS 查询数据库配置
   SELECT * FROM notification_channels WHERE code='trading'
   → {"webhook": "https://open.feishu.cn/..."}
   ↓
8. Agent OS 调用 Feishu Provider
   FeishuProvider.Send(config, message)
   ↓
9. 发送到飞书
   POST https://open.feishu.cn/open-apis/bot/v2/hook/...
   ↓
10. 用户在飞书群看到盘前准备报告
```

---

### **流程 2: Agent 风险告警流程**

```
1. Agent 实时监控 (每分钟)
   watch_manage() → 监控持仓风险
   ↓
2. Agent 发现风险
   检测到: 600519.SH 跌破止损位
   ↓
3. Agent 调用风险服务
   Risk Service → 计算风险敞口
   Portfolio Service → 查询持仓数量
   ↓
4. Agent 生成告警
   notification_send({
     channel: 'alerts',
     title: '⚠️ 风险告警',
     content: `
       **触发条件**: 600519.SH 跌破止损位
       **当前价格**: ¥1,180 (-3.2%)
       **止损价**: ¥1,200
       **持仓**: 1000股
       **建议**: 立即止损
     `,
     color: 'red'
   })
   ↓
5. Agent OS 处理
   → 查询 alerts 渠道配置
   → 调用 Feishu Provider
   → 发送到飞书告警群
   ↓
6. 用户立即收到告警
   飞书群 → 红色卡片 → 提醒音
```

---

### **流程 3: 交易执行 + 通知流程**

```
1. Agent 生成交易信号
   strategy_signal() → 买入信号: 000858.SZ
   ↓
2. Agent 调用交易工具
   portfolio_trade({
     symbol: '000858.SZ',
     action: 'buy',
     quantity: 1000,
     price: 15.20
   })
   ↓
3. 交易工具调用交易服务
   Trade Service → 下单
   ↓
4. 交易服务执行
   - 验证资金
   - 提交订单
   - 返回订单号
   ↓
5. Agent 等待订单成交
   order_status(order_id) → 'filled'
   ↓
6. Agent 发送通知
   notification_send({
     channel: 'trading',
     title: '✅ 交易执行',
     content: `
       **股票**: 000858.SZ (五粮液)
       **操作**: 买入
       **数量**: 1000股
       **价格**: ¥15.20
       **金额**: ¥15,200
       **订单**: #20260814001
     `,
     color: 'green'
   })
   ↓
7. Agent OS → 飞书
   ↓
8. 用户确认交易执行成功
```

---

### **流程 4: 每日报告生成流程**

```
1. 定时任务 (每天 17:00 收盘后)
   ↓
2. Agent 收集全天数据
   portfolio_status()        → 持仓
   portfolio_trade_history() → 交易记录
   portfolio_pnl()           → 盈亏统计
   market_summary()          → 市场概况
   ↓
3. Agent 调用多个金融服务
   Portfolio Service → 持仓和收益
   Trade Service → 交易明细
   Market Data Service → 行情数据
   Strategy Service → 策略表现
   ↓
4. Agent 生成报告
   - 分析持仓变化
   - 统计交易情况
   - 计算收益率
   - 评估策略表现
   - 生成详细 Markdown
   ↓
5. Agent 发送到报告群
   notification_send({
     channel: 'reports',
     title: '📊 每日报告 - 2026-08-14',
     content: `(3000字详细报告)`
   })
   ↓
6. Agent OS → 飞书报告群
   ↓
7. 用户查看每日总结
```

---

### **流程 5: Web V2 用户主动查询流程**

```
1. 用户在 Web V2 点击"查看持仓"
   ↓
2. Web V2 调用后端 API
   GET /api/portfolio
   ↓
3. 后端调用 Agent-ts 工具
   (通过某种方式，或者直接调用 Portfolio Service)
   ↓
4. Portfolio Service 查询数据库
   SELECT * FROM portfolios WHERE user_id=...
   ↓
5. 返回持仓数据
   Portfolio Service → Web 后端 → 前端
   ↓
6. 用户在 Web V2 看到持仓列表
```

---

### **流程 6: 飞书用户交互流程**

```
1. 用户在飞书群 @机器人
   "@机器人 查询持仓"
   ↓
2. 飞书发送 Webhook 到飞书应用
   POST /webhook
   ↓
3. 飞书应用解析命令
   识别: "查询持仓"
   ↓
4. 飞书应用调用 Agent-ts 或直接调用服务
   portfolio_status()
   ↓
5. 获取持仓数据
   Portfolio Service → 返回数据
   ↓
6. 飞书应用调用 Agent OS
   notification_send({
     channel: 'trading',
     title: '📊 持仓查询结果',
     content: `(持仓明细)`
   })
   ↓
7. Agent OS → 飞书
   ↓
8. 用户在飞书群看到回复
```

```
1. Agent-ts 调用工具
   agent.call('notification_send', {
     channel: 'trading',
     title: '盘前准备',
     content: '...'
   })
   ↓
2. 工具通过 HTTP 调用 Agent OS
   POST http://agent-os:8080/api/v1/notifications/send
   ↓
3. Agent OS 查询数据库
   SELECT * FROM notification_channels WHERE code='trading'
   SELECT * FROM notification_providers WHERE id=...
   ↓
4. Agent OS 调用 Provider
   provider := registry.Get("feishu")
   provider.Send(config, message)
   ↓
5. Feishu Provider 发送 Webhook
   POST https://open.feishu.cn/open-apis/bot/v2/hook/...
   ↓
6. 飞书群收到消息
   用户在飞书群看到通知
   ↓
7. Agent OS 记录日志
   INSERT INTO notification_logs (...)
```

---

### **流程 2: Web V2 发送通知**

```
1. Web 前端调用 Agent OS API
   fetch('http://agent-os:8080/api/v1/notifications/send', {
     method: 'POST',
     body: JSON.stringify({
       channel: 'alerts',
       title: '用户反馈',
       content: '...'
     })
   })
   ↓
2. Agent OS 处理（同上）
   ↓
3. 飞书群收到消息
```

---

### **流程 3: 飞书应用发送通知**

```
1. 飞书机器人收到消息
   用户在飞书群 @机器人
   ↓
2. 飞书应用调用 Agent OS API
   POST http://agent-os:8080/api/v1/notifications/send
   ↓
3. Agent OS 处理（同上）
   ↓
4. 发送到其他渠道（如 Slack、Email）
```

---

## 🌐 多渠道场景

### **场景 1: 飞书作为输入和输出**

```
飞书群用户 → 飞书机器人 → 飞书应用
    ↓
调用 Agent OS API
    ↓
Agent OS 路由到 trading 渠道
    ↓
发送到飞书 trading 群（输出）
```

**关键**: Agent OS 作为中间层，解耦输入和输出

---

### **场景 2: Agent 自动通知到多个渠道**

```
Agent 分析完成
    ↓
调用 notification_send (channel: 'trading')
    ↓
Agent OS → 飞书 trading 群

同时

调用 notification_send (channel: 'alerts')
    ↓
Agent OS → 飞书 alerts 群
```

---

### **场景 3: 跨平台通知**

```
Agent 检测到风险
    ↓
调用 notification_send (channel: 'emergency')
    ↓
Agent OS 查询配置
    ↓
emergency 渠道配置了多个 provider:
    - Feishu (飞书)
    - Slack
    - Email
    - SMS
    ↓
Agent OS 并发发送到所有渠道
    ↓
用户在飞书、Slack、邮件、短信都收到
```

---

## 📊 各组件的职责

### **💰 金融业务服务层 (Financial Services Layer)**

**职责**: 核心金融业务逻辑

**服务列表**:
- **Portfolio Service** - 持仓管理
- **Trade Service** - 交易执行
- **Market Data Service** - 行情数据
- **Strategy Service** - 策略服务
- **Risk Service** - 风险管理

**特点**:
- ✅ 专注金融业务
- ✅ 独立可测试
- ✅ 可被多个应用调用

**数据库**:
```
portfolios      (持仓)
trades          (交易记录)
orders          (订单)
strategies      (策略)
signals         (交易信号)
market_data     (行情数据)
risk_metrics    (风险指标)
```

**调用方**:
- Agent-ts (通过工具)
- Web V2 (通过 API)
- 飞书应用 (通过 API)

---

### **Agent-ts**
- 📊 **职责**: 智能分析、决策、生成内容
- 🛠️ **工具**: 
  - 金融业务工具 (portfolio_*, trade_*, data_*, strategy_*, risk_*)
  - 基础设施工具 (notification_send)
- 🔗 **对接**: 
  - 调用金融业务服务
  - 调用 Agent OS HTTP API

---

### **Agent OS** ⭐
- 🌐 **职责**: 统一基础设施网关
- 🎯 **定位**: 基础设施层 (Infrastructure Layer)
- 📡 **功能**: 
  - HTTP API Server
  - 路由通知到不同渠道
  - 管理 Provider
  - 记录日志
- 🔗 **对接**: 
  - 上游: Agent-ts, Web V2, 飞书应用
  - 下游: Feishu, Slack, Email, SMS...

**数据库**:
```
notification_providers  (提供商配置)
notification_channels   (渠道配置)
notification_logs       (发送日志)
```

---

### **Web V2**
- 🖥️ **职责**: 前端界面
- 📊 **功能**: 
  - 显示报告
  - 手动触发通知
  - 查询持仓/交易
- 🔗 **对接**: 
  - 调用金融业务服务
  - 调用 Agent OS HTTP API

---

### **飞书应用**
- 💬 **职责**: 飞书机器人
- 📨 **功能**: 
  - 接收飞书消息
  - 处理用户指令
  - 发送通知
- 🔗 **对接**: 
  - 接收: 飞书 Webhook
  - 调用: 金融业务服务
  - 发送: 调用 Agent OS HTTP API

---

### **数据库 (PostgreSQL)**
- 💾 **职责**: 数据持久化
- 📊 **分类**: 
  - 💰 金融业务表 (portfolios, trades, orders...)
  - 🌐 基础设施表 (notification_*)
- 🔗 **对接**: 
  - 金融业务服务读写业务表
  - Agent OS 读写基础设施表

---

### **飞书 (Feishu)**
- 💬 **职责**: 外部通信平台
- 📨 **功能**: 
  - 接收 Webhook 消息
  - 显示在飞书群
- 🔗 **对接**: Agent OS Feishu Provider

---

## 🎯 层次关系总结

### **金融业务层 vs 基础设施层**

```
┌─────────────────────────────────────────┐
│  应用层                                  │
│  Agent-ts | Web V2 | 飞书应用           │
└──────────┬─────────────┬────────────────┘
           │             │
           ↓             ↓
┌──────────────────┐  ┌──────────────────┐
│ 💰 金融业务层    │  │ 🌐 基础设施层    │
│                  │  │                  │
│ Portfolio Service│  │ Agent OS         │
│ Trade Service    │  │ - 通知网关       │
│ Market Data Svc  │  │ - 日志          │
│ Strategy Service │  │ - 监控          │
│ Risk Service     │  │                  │
└──────────┬───────┘  └────────┬─────────┘
           │                   │
           ↓                   ↓
┌──────────────────┐  ┌──────────────────┐
│ 💰 业务数据库    │  │ 🌐 基础设施数据库│
│                  │  │                  │
│ portfolios       │  │ notification_*   │
│ trades           │  │                  │
│ orders           │  │                  │
│ ...              │  │                  │
└──────────────────┘  └──────────────────┘
```

---

### **职责边界**

| 层次 | 职责 | 不负责 |
|---|---|---|
| **金融业务层** | 持仓、交易、行情、策略、风险 | ❌ 不负责通知发送 |
| **基础设施层** | 通知、日志、监控、配置 | ❌ 不负责业务逻辑 |
| **应用层** | 用户交互、流程编排 | ❌ 不直接操作数据库 |

---

### **为什么要分层？**

#### **1. 关注点分离 (Separation of Concerns)**

**金融业务服务**:
```go
// 只关心业务逻辑
func (s *PortfolioService) GetPosition(symbol string) (*Position, error) {
    return s.repo.GetPosition(symbol)
}
```

**不需要关心**:
- ❌ 如何发送通知
- ❌ 发到飞书还是 Slack
- ❌ 通知格式

**Agent OS**:
```go
// 只关心通知路由
func (s *NotificationService) Send(channel, message) error {
    provider := s.getProvider(channel)
    return provider.Send(message)
}
```

**不需要关心**:
- ❌ 持仓怎么计算
- ❌ 交易怎么执行
- ❌ 业务规则

---

#### **2. 复用性 (Reusability)**

**金融业务服务可以被多个应用调用**:
```
Agent-ts → Portfolio Service
Web V2 → Portfolio Service
飞书应用 → Portfolio Service
移动端 → Portfolio Service
```

**Agent OS 可以为多个业务服务**:
```
Portfolio Service → Agent OS (发送持仓通知)
Trade Service → Agent OS (发送交易通知)
Risk Service → Agent OS (发送风险告警)
其他服务 → Agent OS (发送任何通知)
```

---

#### **3. 独立演进 (Independent Evolution)**

**金融业务层**:
- 添加新策略 ✅
- 修改风险算法 ✅
- 不影响通知系统 ✅

**基础设施层**:
- 添加 Slack Provider ✅
- 添加 Email Provider ✅
- 不影响金融业务 ✅

---

#### **4. 测试独立性 (Testability)**

**金融业务服务测试**:
```go
// 不需要启动 Agent OS
func TestPortfolioService(t *testing.T) {
    service := NewPortfolioService(mockRepo)
    position, err := service.GetPosition("600519.SH")
    assert.NoError(t, err)
}
```

**Agent OS 测试**:
```go
// 不需要真实的金融数据
func TestNotificationService(t *testing.T) {
    service := NewNotificationService(mockRepo)
    err := service.Send("trading", "Test")
    assert.NoError(t, err)
}
```

---

## 🎯 Agent OS 的价值

### **1. 解耦 (Decoupling)**

**之前**:
```
Agent → 直接调用飞书 API
Web → 直接调用飞书 API
```

**问题**:
- 每个应用都要实现飞书集成
- 配置散落各处
- 无法统一管理

**现在**:
```
Agent → Agent OS → 飞书
Web → Agent OS → 飞书
```

**优势**:
- 统一接口
- 统一配置
- 统一日志

---

### **2. 可扩展 (Extensibility)**

**添加新渠道**:
```
// 只需添加 Provider
type SlackProvider struct{}
func init() { provider.Register(&SlackProvider{}) }
```

**不需要改**:
- ❌ Agent 代码
- ❌ Web 代码
- ❌ API 代码

---

### **3. 统一治理 (Governance)**

**Agent OS 统一提供**:
- ✅ 认证/授权
- ✅ 限流/熔断
- ✅ 日志/审计
- ✅ 监控/告警

---

### **4. 多租户 (Multi-tenancy)**

**未来可以支持**:
```
POST /api/v1/notifications/send
Headers: X-Tenant-ID: tenant_a

Agent OS 根据 tenant_id 路由到不同配置
```

---

## 🔮 未来扩展

### **扩展 1: 更多 Provider**

```
Feishu   ✅ 已实现
Slack    ⏰ 待实现
Email    ⏰ 待实现
SMS      ⏰ 待实现
Telegram ⏰ 待实现
Discord  ⏰ 待实现
钉钉     ⏰ 待实现
企业微信  ⏰ 待实现
```

---

### **扩展 2: 更多功能**

```
✅ 发送通知
✅ 查询渠道
✅ 查询日志
⏰ 批量发送
⏰ 定时发送
⏰ 模板管理
⏰ 订阅管理
⏰ 通知统计
```

---

### **扩展 3: 更多客户端**

```
✅ Agent-ts
✅ Web V2
✅ 飞书应用
✅ CLI
⏰ 移动端
⏰ 桌面应用
⏰ 第三方集成
```

---

## 📐 架构特点总结

### **Agent OS 是什么？**

✅ **统一通知网关** (Unified Notification Gateway)  
✅ **中台服务** (Middleware Service)  
✅ **API Gateway** (专注于通知领域)

### **Agent OS 不是什么？**

❌ 不是前端应用  
❌ 不是 Agent 本身  
❌ 不是飞书/Slack 本身

### **Agent OS 的位置**

```
应用层 (Agent, Web, 飞书应用)
    ↓
中台层 (Agent OS) ⭐ 在这里
    ↓
服务层 (Feishu, Slack, Email)
```

---

**这个架构清晰吗？还有什么需要补充的？**
