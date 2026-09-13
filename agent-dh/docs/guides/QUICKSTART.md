---
id: guides-quickstart
title: Agent-DH 快速开始指南
type: guide
status: living
updated: 2026-09-13
owners: [agent-dh]
tags: [guide]
---

# Agent-DH 快速开始指南

本指南将帮助你在 5 分钟内启动并运行 Agent-DH 系统。

---

## 前置要求

- Node.js 20+
- Go 1.21+
- Python 3.11+
- PostgreSQL 14+
- pnpm 8+

---

## 快速启动

### 1. 启动数据库

```bash
# 创建数据库
psql -U postgres
CREATE DATABASE agent_os;
CREATE DATABASE quant_investment;

# 运行 Agent OS 迁移
cd agent-os
psql -U postgres -d agent_os -f migrations/010_create_agent_registry.sql
```

### 2. 启动 Agent OS（Go）

```bash
cd agent-os

# 配置环境变量
cat > .env << EOF
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agent_os
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
PORT=8080
EOF

# 编译并运行
go build -o agent-os cmd/server/main.go
./agent-os
```

验证：访问 `http://localhost:8080/health`

### 3. 启动 QuantsysV2（Python）

```bash
cd quantsys-v2

# 配置环境变量
cat > .env << EOF
PGHOST=localhost
PGPORT=5432
PGDATABASE=quant_investment
PGUSER=your_user
PGPASSWORD=your_password
EOF

# 安装依赖
pip install -r requirements.txt

# 启动服务
python adapters/inbound/fastapi_app/main.py
```

验证：访问 `http://localhost:5001/docs`

### 4. 启动 Agent-DH（TypeScript）

```bash
cd agent-dh

# 安装依赖
pnpm install

# 构建
pnpm build

# 配置环境变量
export AGENT_OS_BASE_URL=http://localhost:8080
export QUANTSYS_V2_BASE_URL=http://localhost:5001

# 运行 CLI
cd apps/cli
node dist/index.mjs
```

---

## 验证安装

### 测试 Agent OS

```bash
# 注册 Agent
curl -X POST http://localhost:8080/api/v1/registry/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent-001",
    "type": "worker",
    "capabilities": ["test"]
  }'

# 查询 Agent
curl http://localhost:8080/api/v1/registry/agents/available
```

### 测试 QuantsysV2

```bash
# 搜索股票
curl http://localhost:5001/api/stocks/search?q=平安

# 列出策略
curl http://localhost:5001/api/strategies/list
```

### 测试 Agent-DH Client

创建测试文件 `test-client.mjs`:

```javascript
import { AgentDHClient } from '@pi-investment/agent-dh-client';

const client = AgentDHClient.createDefault();

// 测试 Agent OS
try {
  const agent = await client.agentOS.registry.register({
    agent_id: 'demo-agent-001',
    type: 'worker',
    capabilities: ['demo'],
  });
  console.log('✅ Agent registered:', agent);

  const agents = await client.agentOS.registry.listActive();
  console.log('✅ Active agents:', agents.length);

  await client.agentOS.registry.unregister({
    agent_id: 'demo-agent-001',
  });
  console.log('✅ Agent unregistered');
} catch (error) {
  console.error('❌ Agent OS error:', error.message);
}

// 测试 QuantsysV2
try {
  const stocks = await client.quantsysV2.searchStocks('平安');
  console.log('✅ Found stocks:', stocks.length);

  const strategies = await client.quantsysV2.listStrategies();
  console.log('✅ Found strategies:', strategies.length);
} catch (error) {
  console.error('❌ QuantsysV2 error:', error.message);
}
```

运行：
```bash
node test-client.mjs
```

---

## 使用示例

### 示例 1：创建一个简单的 Agent

```typescript
import { InvestmentAgentLoop } from '@pi-investment/investment-agent-loop';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { Context } from '@deepseek-ai/cordis';

async function main() {
  // 创建 Cordis 上下文
  const ctx = new Context();

  // 创建 Agent OS 客户端
  const osClient = new AgentOSClient({
    baseURL: 'http://localhost:8080',
  });

  // 创建 Agent Loop
  const agentLoop = new InvestmentAgentLoop(ctx, {
    osClient,
    agentType: 'worker',
    capabilities: ['data-analysis'],
  });

  // 创建 Agent
  const agent = await agentLoop.create('my-session', {
    agentId: 'my-worker-001',
    type: 'worker',
    capabilities: ['data-analysis'],
  });

  console.log('Agent created:', agent.getInfo());

  // 执行任务
  const result = await agent.executeTask('task-001', {
    action: 'analyze',
    symbol: '600000.SH',
  });

  console.log('Task result:', result);

  // 清理
  await agentLoop.stopAll();
}

main().catch(console.error);
```

### 示例 2：策略回测

```typescript
import { AgentDHClient } from '@pi-investment/agent-dh-client';

async function backtestStrategy() {
  const client = AgentDHClient.createDefault();

  // 列出可用策略
  const strategies = await client.quantsysV2.listStrategies({
    source: 'builtin',
  });

  console.log('Available strategies:', strategies.length);

  // 回测第一个策略
  const result = await client.quantsysV2.backtestStrategy({
    strategy_id: strategies[0].id,
    symbol: '600000.SH',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    initial_capital: 100000,
  });

  console.log('Backtest Result:');
  console.log(`  Total Return: ${result.total_return}%`);
  console.log(`  Annual Return: ${result.annual_return}%`);
  console.log(`  Sharpe Ratio: ${result.sharpe_ratio}`);
  console.log(`  Max Drawdown: ${result.max_drawdown}%`);
  console.log(`  Win Rate: ${result.win_rate}%`);
  console.log(`  Total Trades: ${result.total_trades}`);
}

backtestStrategy().catch(console.error);
```

### 示例 3：股票池管理

```typescript
import { AgentDHClient } from '@pi-investment/agent-dh-client';

async function managePool() {
  const client = AgentDHClient.createDefault();

  // 创建股票池
  const pool = await client.quantsysV2.createPool({
    name: 'My Test Pool',
    description: 'A pool for testing',
  });

  console.log('Pool created:', pool);

  // 添加成员
  await client.quantsysV2.addPoolMember(pool.id, {
    symbol: '600000.SH',
    metadata: { reason: 'manual_add' },
  });

  await client.quantsysV2.addPoolMember(pool.id, {
    symbol: '600519.SH',
    metadata: { reason: 'manual_add' },
  });

  // 查询成员
  const members = await client.quantsysV2.getPoolMembers(pool.id);
  console.log('Pool members:', members);

  // 刷新股票池
  await client.quantsysV2.refreshPool(pool.id);
  console.log('Pool refreshed');
}

managePool().catch(console.error);
```

---

## 常见问题

### Q: Agent OS 启动失败

**A**: 检查数据库连接和迁移：
```bash
# 测试数据库连接
psql -U your_user -d agent_os -c "SELECT 1"

# 检查表是否存在
psql -U your_user -d agent_os -c "\dt"
```

### Q: QuantsysV2 启动失败

**A**: 检查 Python 环境和依赖：
```bash
# 检查 Python 版本
python --version  # 应该是 3.11+

# 重新安装依赖
pip install -r requirements.txt --force-reinstall
```

### Q: Agent 注册失败

**A**: 检查 Agent OS 服务是否运行：
```bash
curl http://localhost:8080/health

# 查看 Agent OS 日志
tail -f agent-os.log
```

### Q: 回测失败

**A**: 检查 QuantsysV2 数据：
```bash
# 检查是否有 K 线数据
curl http://localhost:5001/api/stocks/klines?symbol=600000.SH&start_date=2024-01-01&end_date=2024-12-31

# 如果没有数据，运行数据更新
cd quantsys-v2
python scripts/update_klines_recommended.py
```

---

## 开发工具

### 查看 Agent 状态

```bash
# Agent OS
curl http://localhost:8080/api/v1/registry/agents/available | jq

# 查看 Agent 详情
curl http://localhost:8080/api/v1/registry/agents/{agent_id} | jq
```

### 查看任务执行

```bash
# 查看数据库中的任务
psql -U your_user -d agent_os -c "SELECT * FROM agent_tasks ORDER BY assigned_at DESC LIMIT 10"
```

### 监控心跳

```bash
# 查看最近的心跳
psql -U your_user -d agent_os -c "SELECT * FROM agent_heartbeats ORDER BY received_at DESC LIMIT 10"
```

---

## 下一步

1. **阅读文档**
   - `CLAUDE.md` - 完整开发指南（推荐）
   - `docs/rfcs/` - 设计提案
   - `docs/guides/` - 操作指南

2. **查看示例**
   - `examples/simple-agent.ts` - 简单 Agent
   - `examples/backtest-agent.ts` - 回测 Agent
   - `examples/pool-manager-agent.ts` - 股票池管理

3. **构建你的 Agent**
   - 使用 `InvestmentAgentLoop` 创建自定义 Agent
   - 实现你的业务逻辑
   - 集成 QuantsysV2 的交易功能

---

## 获取帮助

- **文档**: `agent-dh/docs/`
- **示例**: `agent-dh/examples/`
- **问题**: 查看常见问题或提交 Issue

---

祝你使用愉快！🚀

---

## 相关页面

- [启动与停止（STARTUP）](STARTUP.md)
- [profile 模板说明](../../profiles/investment/README.md)
- [示例目录](../../examples/README.md)
- [定时巡检清单](routine-checks.md)
