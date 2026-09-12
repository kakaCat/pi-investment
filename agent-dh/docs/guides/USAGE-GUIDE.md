# Agent-DH 使用指南

**版本**: v0.1.1  
**更新日期**: 2026-08-18

---

## 🎯 可用性状态

### ✅ 完全可用的功能

#### 1. QuantsysV2 客户端

所有 QuantsysV2 相关功能**完全可用**：

```typescript
import { AgentDHClient } from '@pi-investment/agent-dh-client';

const client = AgentDHClient.createDefault();

// ✅ 股票搜索
const stocks = await client.quantsysV2.searchStocks('平安');

// ✅ 策略管理
const strategies = await client.quantsysV2.listStrategies({ source: 'builtin' });

// ✅ 策略回测
const result = await client.quantsysV2.backtestStrategy({
  strategy_id: 1,
  symbol: '600000.SH',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  initial_capital: 100000,
});

// ✅ 股票池管理
const pools = await client.quantsysV2.listPools();
const pool = await client.quantsysV2.createPool({
  name: '高ROE价值池',
  description: 'ROE > 15%',
});

// ✅ 信号生成
const signals = await client.quantsysV2.generateSignals({
  strategy_id: 1,
  symbols: ['600519.SH'],
  date: '2024-12-01',
});

// ✅ 市场数据
const quote = await client.quantsysV2.getQuote('600000.SH');
const marketStyle = await client.quantsysV2.getMarketStyle();
```

**状态**: ✅ **完全可用，生产就绪**

#### 2. 输入验证

所有客户端 API 的**输入验证**完全可用：

```typescript
// ✅ 参数验证会立即生效
try {
  await client.agentOS.registry.register({
    agent_id: '',  // ❌ 立即抛出错误
    type: 'worker',
    capabilities: [],
  });
} catch (error) {
  console.log(error.message);
  // "agent_id is required and cannot be empty"
}

try {
  await client.agentOS.registry.heartbeat({
    agent_id: 'test',
    status: 'invalid',  // ❌ 立即抛出错误
  });
} catch (error) {
  console.log(error.message);
  // "Invalid status: invalid. Must be one of: idle, busy, offline, error"
}
```

**状态**: ✅ **完全可用，已验证**

#### 3. HTTP 请求重试

自动重试机制**完全可用**：

```typescript
// ✅ 所有请求失败会自动重试 3 次
// 网络临时故障会自动恢复
await client.quantsysV2.listStrategies();

// 重试日志示例：
// [QuantsysV2Client] Retrying request (1/3): GET /api/strategies/list
// [QuantsysV2Client] Retrying request (2/3): GET /api/strategies/list
```

**状态**: ✅ **完全可用，已集成**

---

### ⚠️ 需要后端支持的功能

#### 1. Agent OS Registry API

这些功能需要 Agent OS 实现 HTTP API：

```typescript
// ⚠️ 目前返回 404，需要 Agent OS 实现
await client.agentOS.registry.register({...});
await client.agentOS.registry.heartbeat({...});
await client.agentOS.registry.updateStatus({...});
await client.agentOS.registry.unregister({...});
await client.agentOS.registry.listActive();
await client.agentOS.registry.findByCapabilities({...});
```

**状态**: ⚠️ **客户端已就绪，等待后端实现**

**原因**: Agent OS 目前还没有实现完整的 Registry HTTP 服务。

#### 2. Investment Agent Loop

依赖 Agent OS Registry API：

```typescript
// ⚠️ 依赖 Registry API
import { InvestmentAgentLoop } from '@pi-investment/investment-agent-loop';

const agentLoop = new InvestmentAgentLoop(ctx, {
  osClient: client.agentOS,
  agentType: 'worker',
  capabilities: ['test'],
});

// 这会调用 Registry API，目前会失败
const agent = await agentLoop.create('session-001', {...});
```

**状态**: ⚠️ **代码已就绪，等待 Agent OS**

---

## 🚀 立即可用的场景

### 场景 1: 量化策略开发

**完全可用** - 使用 QuantsysV2 客户端进行策略开发和回测：

```typescript
import { AgentDHClient } from '@pi-investment/agent-dh-client';

async function developStrategy() {
  const client = AgentDHClient.createDefault();
  
  // 1. 搜索股票
  const stocks = await client.quantsysV2.searchStocks('科技');
  
  // 2. 列出策略
  const strategies = await client.quantsysV2.listStrategies({
    source: 'builtin',
  });
  
  // 3. 回测策略
  for (const stock of stocks.slice(0, 5)) {
    const result = await client.quantsysV2.backtestStrategy({
      strategy_id: strategies[0].id,
      symbol: stock.symbol,
      start_date: '2024-01-01',
      end_date: '2024-12-31',
    });
    
    console.log(`${stock.name}: 收益率 ${result.total_return}%`);
  }
}
```

### 场景 2: 股票池管理

**完全可用** - 创建和管理股票池：

```typescript
async function manageStockPool() {
  const client = AgentDHClient.createDefault();
  
  // 1. 创建股票池
  const pool = await client.quantsysV2.createPool({
    name: '高成长科技股',
    description: '营收增长 > 30%',
  });
  
  // 2. 添加成员
  await client.quantsysV2.addPoolMember(pool.id, {
    symbol: '600519.SH',
    metadata: { reason: '高ROE' },
  });
  
  // 3. 查询成员
  const members = await client.quantsysV2.getPoolMembers(pool.id);
  console.log(`股票池有 ${members.length} 个成员`);
}
```

### 场景 3: 市场数据分析

**完全可用** - 获取市场数据和分析：

```typescript
async function analyzeMarket() {
  const client = AgentDHClient.createDefault();
  
  // 1. 获取实时行情
  const quote = await client.quantsysV2.getQuote('600000.SH');
  console.log(`价格: ${quote.price}, 涨跌幅: ${quote.change_pct}%`);
  
  // 2. 获取市场风格
  const marketStyle = await client.quantsysV2.getMarketStyle();
  console.log(`市场风格: ${marketStyle.style}`);
  
  // 3. 筹码分布分析
  const chipDist = await client.quantsysV2.getChipDistribution('600000.SH');
  console.log(`筹码集中度: ${chipDist.concentration}`);
}
```

---

## 📋 等待 Agent OS 实现的清单

### 需要实现的 API 端点

1. **POST** `/api/v1/registry/agents/register`
   - 注册 Agent

2. **POST** `/api/v1/registry/agents/heartbeat`
   - 发送心跳

3. **POST** `/api/v1/registry/agents/update-status`
   - 更新状态

4. **POST** `/api/v1/registry/agents/unregister`
   - 注销 Agent

5. **GET** `/api/v1/registry/agents/available`
   - 查询活跃 Agent

6. **POST** `/api/v1/registry/agents/find-by-capabilities`
   - 按能力查找

### Agent OS 实现指南

Agent OS 需要实现的 Handler（已有代码）：

```go
// internal/handlers/registry_handler.go
// 这些代码已经存在，需要在 main.go 中注册路由

func (h *RegistryHandler) Register(c *gin.Context)
func (h *RegistryHandler) Heartbeat(c *gin.Context)
func (h *RegistryHandler) UpdateStatus(c *gin.Context)
func (h *RegistryHandler) Unregister(c *gin.Context)
func (h *RegistryHandler) ListActive(c *gin.Context)
func (h *RegistryHandler) FindByCapabilities(c *gin.Context)
```

**注意**: Agent OS 的后端服务代码已经写好了，只需要在启动时注册这些 HTTP 路由。

---

## 🔧 临时解决方案

### 方案 1: 使用 QuantsysV2 功能

目前可以**完全使用** QuantsysV2 的所有功能，这已经覆盖了大部分投资相关的需求。

### 方案 2: 等待 Agent OS 完成

Agent-DH 客户端已经**100% 就绪**，包括：
- ✅ 完整的类型定义
- ✅ 输入验证
- ✅ HTTP 重试
- ✅ 错误处理

只要 Agent OS 实现 HTTP API，Agent-DH 就可以**立即使用**，无需修改。

### 方案 3: Mock 测试

可以使用 Mock 数据进行开发和测试：

```typescript
// 使用 Mock Registry Client（用于测试）
import { MockRegistryClient } from '@pi-investment/investment-agent-loop/test';

const mockClient = new MockRegistryClient();
const agentLoop = new InvestmentAgentLoop(ctx, {
  osClient: mockClient as any,
  agentType: 'worker',
  capabilities: ['test'],
});

// 可以正常开发和测试逻辑
const agent = await agentLoop.create('session-001', {...});
```

---

## ✅ 推荐使用方式

### 现在（v0.1.1）

**推荐使用 QuantsysV2 客户端进行量化开发**：

```typescript
import { AgentDHClient } from '@pi-investment/agent-dh-client';

const client = AgentDHClient.createDefault();

// ✅ 所有 QuantsysV2 功能都可以用
await client.quantsysV2.searchStocks('科技');
await client.quantsysV2.backtestStrategy({...});
await client.quantsysV2.listPools();
```

**优点**:
- ✅ 完全可用，生产就绪
- ✅ 40+ API 方法
- ✅ 包含输入验证和重试机制
- ✅ 覆盖策略、回测、股票池、信号、市场数据

### 未来（Agent OS 完成后）

可以使用完整的 Agent 管理功能：

```typescript
// 等 Agent OS 实现后立即可用
await client.agentOS.registry.register({...});
await agentLoop.create('session-001', {...});
```

---

## 📞 总结

### ✅ 可以做什么

1. **策略开发和回测** - 完全可用
2. **股票池管理** - 完全可用
3. **市场数据分析** - 完全可用
4. **信号生成** - 完全可用
5. **输入验证** - 已集成
6. **HTTP 重试** - 已集成

### ⏳ 等待完成

1. **Agent 注册和管理** - 等待 Agent OS HTTP API
2. **Agent Loop** - 等待 Agent OS HTTP API

### 🎯 结论

**Agent-DH v0.1.1 的 QuantsysV2 部分完全可用，可以立即开始量化策略开发。**

Agent Registry 部分的客户端代码已经完全就绪（包括所有改进），只等 Agent OS 实现 HTTP API 就可以使用。

---

**状态**: ✅ 部分可用（QuantsysV2 100% 可用）  
**版本**: v0.1.1  
**更新**: 2026-08-18
