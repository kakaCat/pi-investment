# Agent 盘前准备流程 - 两种架构模式对比

**日期**: 2026-08-14  
**问题**: Agent 如何与金融业务服务交互？

---

## 🎯 两种架构模式

### **模式 1: Agent 主动调用 (当前实现)** ⭐ 推荐

```
Agent-ts (主导)
  ↓ 主动调用
portfolio_status() → Portfolio Service → 返回数据
  ↓ 主动调用
data_fetch_quote() → Market Data Service → 返回数据
  ↓ 主动调用
risk_analysis() → Risk Service → 返回数据
  ↓
Agent 分析所有数据
  ↓
Agent 生成报告
  ↓
notification_send() → Agent OS → 飞书
```

**特点**:
- ✅ **Agent 完全控制流程**
- ✅ **Agent 决定调用什么、何时调用**
- ✅ **Agent 可以根据中间结果调整后续步骤**
- ✅ **实现简单**

---

### **模式 2: 业务服务调用 Agent 决策 (更复杂)**

```
定时任务触发
  ↓
盘前准备服务 (PreMarketService)
  ↓ 收集所有数据
Portfolio Service → 持仓数据
Market Data Service → 行情数据
Risk Service → 风险数据
Strategy Service → 策略数据
  ↓ 汇总所有数据
PreMarketService 构建完整上下文
  ↓ 调用 Agent 决策
Agent-ts.analyze({
  portfolio: {...},
  marketData: {...},
  risk: {...},
  strategy: {...}
})
  ↓
Agent 返回决策
{
  recommendation: "...",
  report: "...",
  actions: [...]
}
  ↓
PreMarketService 执行决策
  ↓
notification_send() → Agent OS → 飞书
```

**特点**:
- ⚠️ **业务服务控制流程**
- ⚠️ **Agent 只负责分析和决策**
- ⚠️ **需要预先收集所有数据**
- ⚠️ **实现复杂**

---

## 📊 详细对比

### **模式 1: Agent 主动调用 (Tool-based)**

#### **优势** ✅

**1. Agent 完全自主**
```typescript
// Agent 自己决定流程
async function preMarketPreparation() {
  // 1. 先看持仓
  const portfolio = await agent.call('portfolio_status');
  
  // 2. 根据持仓，只获取持仓股票的行情
  const quotes = await Promise.all(
    portfolio.positions.map(p => 
      agent.call('data_fetch_quote', { symbol: p.symbol })
    )
  );
  
  // 3. 如果发现某只股票波动大，深入分析
  if (quotes.some(q => q.volatility > 0.05)) {
    const riskDetail = await agent.call('risk_analysis_detail');
  }
  
  // 4. Agent 智能决定下一步
  // ...
}
```

**Agent 可以动态调整流程！**

---

**2. 灵活的决策链**
```typescript
// Agent 可以根据中间结果决定是否继续
const portfolio = await agent.call('portfolio_status');

if (portfolio.totalValue < 1000000) {
  // 小资金，简单分析
  const simpleReport = await generateSimpleReport();
  return simpleReport;
} else {
  // 大资金，深度分析
  const marketData = await agent.call('data_fetch_quote', {...});
  const risk = await agent.call('risk_analysis', {...});
  const strategy = await agent.call('strategy_backtest', {...});
  const detailedReport = await generateDetailedReport();
  return detailedReport;
}
```

**Agent 根据情况智能决策！**

---

**3. 实现简单**
```typescript
// Agent 工具定义
export const portfolioStatusTool: ToolDefinition = {
  name: "portfolio_status",
  execute: async () => {
    const service = getPortfolioService();
    return await service.getStatus();
  }
};

// Agent 直接调用
const portfolio = await agent.call('portfolio_status');
```

**工具层薄薄一层，非常简单！**

---

**4. 错误处理容易**
```typescript
try {
  const portfolio = await agent.call('portfolio_status');
} catch (error) {
  // Agent 可以决定如何处理错误
  // 1. 重试
  // 2. 跳过
  // 3. 使用缓存数据
  // 4. 告警用户
  await agent.call('notification_send', {
    channel: 'alerts',
    title: '数据获取失败',
    content: '无法获取持仓数据，使用昨日数据'
  });
  
  const cachedPortfolio = await getCachedData();
}
```

**Agent 智能处理异常！**

---

#### **劣势** ⚠️

**1. 多次调用开销**
```
Agent → portfolio_status (1 次 HTTP/RPC 调用)
Agent → data_fetch_quote (N 次调用，N = 持仓数量)
Agent → risk_analysis (1 次调用)
Agent → strategy_signal (1 次调用)

总计: 10+ 次调用
```

**但是**:
- 网络延迟通常 < 10ms (内网)
- Agent 可以并发调用 (Promise.all)
- 实际总耗时 < 100ms

---

**2. Agent 需要知道有哪些工具**

**但是**:
- 这正是 Tool-based Agent 的设计！
- Agent 通过工具目录发现工具
- 121+ 工具已经存在

---

### **模式 2: 业务服务调用 Agent (Decision-as-a-Service)**

#### **优势** ✅

**1. 数据收集集中**
```go
// PreMarketService 一次性收集所有数据
func (s *PreMarketService) Prepare() (*Report, error) {
    // 并发收集所有数据
    var wg sync.WaitGroup
    var portfolio *Portfolio
    var marketData *MarketData
    var risk *Risk
    
    wg.Add(3)
    go func() { portfolio = s.portfolioSvc.GetStatus(); wg.Done() }()
    go func() { marketData = s.marketDataSvc.GetQuotes(); wg.Done() }()
    go func() { risk = s.riskSvc.Analyze(); wg.Done() }()
    wg.Wait()
    
    // 构建完整上下文
    context := buildContext(portfolio, marketData, risk)
    
    // 调用 Agent 决策
    decision := s.agentClient.Analyze(context)
    
    return decision.Report, nil
}
```

**一次性收集，减少往返次数**

---

**2. 业务服务控制流程**
```go
// 业务逻辑在服务层
func (s *PreMarketService) Prepare() {
    // 1. 收集数据（业务服务控制）
    data := s.collectData()
    
    // 2. 调用 Agent 分析
    decision := s.agent.Analyze(data)
    
    // 3. 执行决策（业务服务控制）
    if decision.ShouldTrade {
        s.tradeSvc.Execute(decision.TradeOrders)
    }
    
    // 4. 发送通知（业务服务控制）
    s.notificationSvc.Send(decision.Report)
}
```

**流程固定，可预测**

---

#### **劣势** ⚠️

**1. Agent 失去自主性**
```go
// Agent 只能分析预先给定的数据
func (a *Agent) Analyze(context *Context) *Decision {
    // ❌ Agent 不能主动获取更多数据
    // ❌ Agent 不能根据中间结果调整流程
    // ❌ Agent 只是一个"分析函数"
    
    // 只能基于给定的 context 做分析
    recommendation := a.analyzeMarket(context.MarketData)
    report := a.generateReport(context)
    
    return &Decision{
        Recommendation: recommendation,
        Report: report,
    }
}
```

**Agent 变成了被动的"分析器"！**

---

**2. 预先收集所有数据（浪费）**
```go
// 必须预先收集所有数据
portfolio := s.portfolioSvc.GetStatus()
marketData := s.marketDataSvc.GetAllQuotes()  // 所有股票
risk := s.riskSvc.Analyze()                   // 完整风险分析
strategy := s.strategySvc.GetAllSignals()     // 所有策略信号

// ❌ 即使 Agent 可能只需要其中一部分
// ❌ 浪费计算和带宽
```

---

**3. 实现复杂**

**需要实现**:
```
1. PreMarketService (新服务)
2. Agent HTTP API (Agent 作为服务)
3. 完整的上下文构建
4. Agent 结果解析
5. 决策执行逻辑
```

**对比**:
- 模式 1: 只需要薄薄的工具层
- 模式 2: 需要厚重的协调层

---

**4. Agent 无法动态决策**
```go
// 预先收集数据
context := buildContext(portfolio, marketData, risk)

// ❌ Agent 发现需要更多数据，但已经太晚了
decision := agent.Analyze(context)

// ❌ Agent: "我需要 600519.SH 的更详细历史数据"
// ❌ 但数据已经收集完了，无法回头
```

---

**5. 错误处理困难**
```go
// 收集数据时出错
portfolio, err := s.portfolioSvc.GetStatus()
if err != nil {
    // ❌ 整个流程中断？
    // ❌ 还是用默认值？
    // ❌ Agent 无法参与决策
    return nil, err
}

// 对比模式 1: Agent 可以智能处理
// Agent: "获取失败？那我用缓存数据，并告警用户"
```

---

## 🎯 OpenClaw 的选择

### **OpenClaw 使用模式 1: Tool-based**

```python
# OpenClaw Agent
class Agent:
    def __init__(self, tools):
        self.tools = tools  # Tool registry
    
    async def run(self, task):
        # Agent 主动调用工具
        while not task.done:
            # 1. Agent 思考下一步
            next_action = self.think()
            
            # 2. Agent 选择工具
            tool = self.tools.get(next_action.tool_name)
            
            # 3. Agent 调用工具
            result = await tool.execute(next_action.params)
            
            # 4. Agent 根据结果决定下一步
            task.update(result)
```

**OpenClaw 的理念**: **Agent 应该是主动的、自主的**

---

## 🏗️ 推荐架构

### **推荐使用模式 1: Agent 主动调用**

#### **为什么？**

**1. 符合 Agent 设计理念**
- Agent = 自主智能体
- Agent 应该主动探索和决策
- 不是被动的"分析函数"

---

**2. 灵活性**
```typescript
// Agent 可以根据情况调整流程

// 场景 1: 小资金账户
if (portfolio.totalValue < 100000) {
  // 简单流程
  const quote = await agent.call('data_fetch_quote');
  return generateSimpleReport(quote);
}

// 场景 2: 大资金账户
else if (portfolio.totalValue > 10000000) {
  // 深度分析
  const quote = await agent.call('data_fetch_quote');
  const risk = await agent.call('risk_analysis');
  const strategy = await agent.call('strategy_backtest');
  const manipulation = await agent.call('manipulation_detect');
  return generateDetailedReport({quote, risk, strategy, manipulation});
}

// 场景 3: 高风险持仓
else if (portfolio.risk > 0.8) {
  // 风险优先
  const risk = await agent.call('risk_analysis_detail');
  const hedge = await agent.call('hedge_strategy');
  return generateRiskReport({risk, hedge});
}
```

**Agent 根据情况智能调整！**

---

**3. 实现简单**

**只需要薄薄的工具层**:
```typescript
// agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.ts
export const portfolioStatusTool: ToolDefinition = {
  name: "portfolio_status",
  description: "查询当前持仓状态",
  parameters: Type.Object({}),
  execute: async (_toolCallId, _params: any) => {
    const service = getPortfolioService();
    const status = await service.getStatus();
    return {
      content: [{ type: "text", text: JSON.stringify(status) }]
    };
  }
};
```

**就这么简单！**

---

**4. 易于扩展**

**添加新工具**:
```typescript
// 1. 创建工具
export const newTool: ToolDefinition = {
  name: "new_tool",
  execute: async () => { /* ... */ }
};

// 2. 注册到 catalog
// 完成！

// Agent 自动发现并可以使用
```

---

**5. 错误处理灵活**
```typescript
// Agent 可以智能处理错误
try {
  const portfolio = await agent.call('portfolio_status');
} catch (error) {
  // Agent 决定如何处理
  if (error.code === 'TIMEOUT') {
    // 重试
    const portfolio = await agent.call('portfolio_status');
  } else if (error.code === 'SERVICE_DOWN') {
    // 使用缓存
    const portfolio = await getCachedData();
    // 告警
    await agent.call('notification_send', {
      channel: 'alerts',
      title: '服务异常',
      content: '使用缓存数据'
    });
  } else {
    // 降级
    return generateMinimalReport();
  }
}
```

---

## 💡 混合模式（可选）

### **模式 3: 混合 - 同时支持两种**

```typescript
// 方式 1: Agent 主动调用（默认）
const portfolio = await agent.call('portfolio_status');
const quote = await agent.call('data_fetch_quote');
agent.analyze();

// 方式 2: 批量数据接口（可选）
const allData = await agent.call('premarket_data_batch');
// 返回: { portfolio, marketData, risk, strategy }
agent.analyze(allData);
```

**实现**:
```typescript
// 添加一个批量工具
export const premarketDataBatchTool: ToolDefinition = {
  name: "premarket_data_batch",
  description: "一次性获取盘前所有数据（批量优化）",
  execute: async () => {
    // 并发获取所有数据
    const [portfolio, marketData, risk, strategy] = await Promise.all([
      getPortfolioService().getStatus(),
      getMarketDataService().getQuotes(),
      getRiskService().analyze(),
      getStrategyService().getSignals()
    ]);
    
    return {
      portfolio,
      marketData,
      risk,
      strategy
    };
  }
};
```

**优势**:
- ✅ 默认使用灵活的工具模式
- ✅ 需要性能优化时使用批量模式
- ✅ Agent 可以选择使用哪种方式

---

## ✅ 最终推荐

### **使用模式 1: Agent 主动调用（Tool-based）**

**理由**:
1. ✅ **符合 Agent 设计理念** - Agent 是自主的
2. ✅ **灵活性** - Agent 可以动态调整流程
3. ✅ **实现简单** - 薄薄的工具层
4. ✅ **易于扩展** - 添加新工具很容易
5. ✅ **OpenClaw 的选择** - 行业最佳实践

**模式 2 的问题**:
1. ❌ Agent 失去自主性
2. ❌ 预先收集所有数据（浪费）
3. ❌ 实现复杂
4. ❌ 无法动态决策
5. ❌ 错误处理困难

---

### **如果真的需要性能优化**

**使用混合模式**:
- 默认: Agent 主动调用（灵活）
- 可选: 批量数据接口（性能）

**但是**:
- 先不要过早优化
- 模式 1 的性能已经足够好
- 内网调用延迟 < 10ms
- Agent 可以并发调用

---

**你觉得哪种模式更适合？我推荐模式 1（当前实现）！**
