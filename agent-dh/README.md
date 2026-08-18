# Agent-DH

**Agent-DH** 是一个基于 [DeepSeek Harness (DSH)](https://github.com/deepseek-ai/dsh) 的分布式 Agent 管理系统，为 PI Investment 自主投资 AI Agent 提供基础设施支持。

## 🎯 项目目标

提供一个完整的分布式 Agent 管理系统，包括：
- **Agent 注册和生命周期管理**
- **智能任务路由和负载均衡**
- **健康监控和自动恢复**
- **与量化交易系统深度集成**

## 🏗️ 系统架构

```
Agent-DH (TypeScript)  →  Agent OS (Go)  →  PostgreSQL
      ↓                         ↓
  Investment Loop        Task Router
  CLI Tools             Load Balancer
      ↓                  Health Checker
QuantsysV2 (Python) ────────────────────→  Trading/Analysis
```

## ✨ 核心特性

### Agent 管理
- ✅ 分布式 Agent 注册
- ✅ 心跳监控（30秒间隔）
- ✅ 自动健康检查（2分钟超时）
- ✅ 状态管理（idle/busy/offline/error）
- ✅ 能力标注和查询

### 任务路由
- ✅ 基于能力的智能匹配
- ✅ 多能力要求支持
- ✅ 任务分配和执行跟踪
- ✅ 4 种负载均衡策略

### 负载均衡
- ✅ **least-load** - 最少负载优先（默认）
- ✅ **round-robin** - 轮询分配
- ✅ **random** - 随机选择
- ✅ **capability** - 能力优先

### 交易集成
- ✅ 策略管理和回测
- ✅ 参数优化
- ✅ 股票池管理
- ✅ 信号生成
- ✅ 市场数据和分析

## 🚀 快速开始

### 前置要求

- Node.js 20+
- Go 1.21+
- Python 3.11+
- PostgreSQL 14+
- pnpm 8+

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd agent-dh

# 安装依赖
pnpm install

# 构建
pnpm build
```

### 启动服务

1. **启动 Agent OS**（Go）
```bash
cd ../agent-os
go run cmd/server/main.go
# 访问 http://localhost:8080
```

2. **启动 QuantsysV2**（Python）
```bash
cd ../quantsys-v2
python adapters/inbound/fastapi_app/main.py
# 访问 http://localhost:5001
```

3. **运行 Agent-DH CLI**
```bash
cd agent-dh/apps/cli
export AGENT_OS_BASE_URL=http://localhost:8080
export QUANTSYS_V2_BASE_URL=http://localhost:5001
node dist/index.mjs
```

详细步骤请查看 [QUICKSTART.md](./QUICKSTART.md)

## 📦 包结构

```
agent-dh/
├── packages/
│   ├── agent-os-client/          # Agent OS 客户端
│   ├── quantsys-v2-client/       # QuantsysV2 客户端
│   ├── agent-dh-client/          # 统一客户端入口
│   └── investment-agent-loop/    # Agent 框架
├── apps/
│   └── cli/                      # CLI 工具
└── docs/                         # 文档
```

## 💻 使用示例

### 创建 Agent

```typescript
import { InvestmentAgentLoop } from '@pi-investment/investment-agent-loop';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { Context } from '@deepseek-ai/cordis';

const ctx = new Context();
const osClient = new AgentOSClient({
  baseURL: 'http://localhost:8080',
});

const agentLoop = new InvestmentAgentLoop(ctx, {
  osClient,
  agentType: 'worker',
  capabilities: ['data-analysis', 'backtest'],
});

const agent = await agentLoop.create('session-001', {
  agentId: 'worker-001',
  type: 'worker',
  capabilities: ['data-analysis'],
});

await agent.executeTask('task-001', { action: 'analyze' });
await agentLoop.stopAll();
```

### 策略回测

```typescript
import { AgentDHClient } from '@pi-investment/agent-dh-client';

const client = AgentDHClient.createDefault();

const result = await client.quantsysV2.backtestStrategy({
  strategy_id: 1,
  symbol: '600000.SH',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  initial_capital: 100000,
});

console.log(`Total Return: ${result.total_return}%`);
console.log(`Sharpe Ratio: ${result.sharpe_ratio}`);
```

更多示例请查看 [examples/](./examples/) 目录。

## 📚 文档

- [快速开始指南](./QUICKSTART.md) - 5分钟上手
- [项目总结](./docs/project-summary.md) - 完整概览
- [Phase 1 报告](./docs/phase-1-completion-report.md) - 框架搭建
- [Phase 2 报告](./docs/phase-2-completion-report.md) - Agent OS Registry
- [Phase 3 报告](./docs/phase-3-completion-report.md) - Client SDK

## 🧪 测试

```bash
# 运行所有测试
pnpm test

# 运行特定包的测试
cd packages/investment-agent-loop
pnpm test

# 查看测试覆盖率
pnpm test -- --coverage
```

## 🔧 开发

```bash
# 安装依赖
pnpm install

# 构建所有包
pnpm build

# 开发模式（watch）
pnpm dev

# 代码检查
pnpm lint
```

## 📊 技术栈

### Agent-DH (TypeScript)
- **框架**: @deepseek-ai/cordis (DSH 核心)
- **HTTP**: axios
- **构建**: tsdown (rolldown)
- **包管理**: pnpm workspace
- **测试**: vitest

### Agent OS (Go)
- **框架**: Gin (HTTP), sqlx (数据库)
- **数据库**: PostgreSQL
- **架构**: 六边形架构

### QuantsysV2 (Python)
- **框架**: FastAPI
- **数据库**: PostgreSQL
- **领域**: 量化交易、回测

## 🎯 路线图

### ✅ 已完成
- Phase 1: 框架搭建（Week 1-2）
- Phase 2: Agent OS Registry（Week 3）
- Phase 3: Client SDK（Week 4）

### 🔜 计划中
- 集成测试和 E2E 测试
- 监控和日志系统
- Agent 自动恢复
- 多区域部署支持

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](./CONTRIBUTING.md)（待创建）。

## 📄 许可证

MIT

## 🙏 致谢

- [DeepSeek Harness (DSH)](https://github.com/deepseek-ai/dsh) - Agent 框架
- [QuantsysV2](../quantsys-v2) - 量化交易系统
- [Agent OS](../agent-os) - Registry 服务

---

**Status**: ✅ 核心基础设施完成，准备投入使用

**Version**: 0.1.0

**Last Updated**: 2026-08-18
