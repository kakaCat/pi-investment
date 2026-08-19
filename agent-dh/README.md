# Agent-DH

**Agent-DH** 是 PI Investment 系统的 DSH (DeepSeek Harness) 投资分析 Profile，提供基于 AI 的投资决策能力。

## 🎯 项目定位

Agent-DH **不是独立应用**，而是一个 **DSH Profile**，包含：
- **14 个投资插件包**（48 个 AI 工具）
- **DSH Profile 配置**（插件加载、系统提示词）
- **TypeScript 源码**（编译后供 DSH 使用）

通过 DSH 框架运行，提供 Web UI、CLI、TUI 等多种交互方式。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────┐
│  DSH Framework (deepseek-harness)               │
│  • Plugin system (cordis)                       │
│  • Web UI / CLI / TUI                           │
│  • LLM integration (DeepSeek)                   │
└─────────────────────────────────────────────────┘
       ↑ loads
┌─────────────────────────────────────────────────┐
│  Agent-DH Profile (~/.dsh/profiles/investment)  │
│  • 14 investment plugins (48 tools)             │
│  • Investment system prompt                     │
│  • QuantsysV2 backend config                    │
└─────────────────────────────────────────────────┘
       ↑ implements
┌─────────────────────────────────────────────────┐
│  Agent-DH Packages (this repository)            │
│  • TypeScript plugin source code                │
│  • 14 plugin packages in packages/              │
│  • Built and linked to DSH profile              │
└─────────────────────────────────────────────────┘
       ↓ calls
┌─────────────────────────────────────────────────┐
│  QuantsysV2 Backend (Python, port 5001)         │
│  • Stock data, K-lines, financials              │
│  • Strategy backtesting                         │
│  • Trading execution                            │
└─────────────────────────────────────────────────┘
```

## ✨ 核心功能

### 投资数据工具（8个）
- 实时行情、K线数据、财务数据
- 宏观经济、北向资金、市场情绪
- 股票池管理、策略列表

### 交易工具（6个）
- 账户信息、持仓查询
- 交易执行、交易监控
- 算法交易、对账

### 智能工具（3个）
- 盯盘规则、盯盘管理
- 市场告警

### 竞争分析（3个）
- 对手行为分析
- 战场评估
- 操纵检测

### 其他工具（28个）
- 市场分析、风险控制、策略执行
- 因子分析、模型预测、记忆系统
- 进化系统、调度器、通知、数据管理

**完整工具列表**: 见 [CLAUDE.md](./CLAUDE.md)

## 🚀 快速开始

### 前置要求

- **Node.js** 20+
- **pnpm** 8+
- **DSH** (DeepSeek Harness) 已安装
- **QuantsysV2** 后端运行中（端口 5001）
- **DeepSeek API Key**

### 1. 构建插件

```bash
cd agent-dh

# 安装依赖
pnpm install

# 构建所有插件（TypeScript → JavaScript）
pnpm build
```

### 2. 配置 DSH Profile

DSH Profile 位于 `~/.dsh/profiles/investment/`，已配置为引用本仓库的插件：

```json
{
  "dependencies": {
    "@pi-investment/investment": "file:../../../pi-investment/agent-dh/packages/investment",
    "@pi-investment/trading": "file:../../../pi-investment/agent-dh/packages/trading",
    ...
  }
}
```

### 3. 启动投资 Agent

```bash
# 设置 API Key
export DEEPSEEK_API_KEY=sk-...

# 启动 DSH investment profile（默认端口 13080）
cd ~/.dsh/profiles/investment
./start.sh

# 或指定端口
./start.sh 13081
```

访问 Web UI: `http://localhost:13080`

### 4. 停止服务

```bash
# 查找进程
lsof -ti:13080

# 停止
kill <PID>
```

## 📦 项目结构

```
agent-dh/
├── packages/                    # 14 个投资插件包（TypeScript）
│   ├── investment/              # 投资数据工具（8个工具）
│   ├── trading/                 # 交易工具（6个工具）
│   ├── intelligence/            # 智能工具（3个工具）
│   ├── competition/             # 竞争分析（3个工具）
│   ├── market/                  # 市场分析（3个工具）
│   ├── risk/                    # 风险控制（3个工具）
│   ├── strategy/                # 策略工具（6个工具）
│   ├── factor/                  # 因子分析（2个工具）
│   ├── model/                   # 模型工具（3个工具）
│   ├── memory/                  # 记忆系统（3个工具）
│   ├── evolution/               # 进化系统（2个工具）
│   ├── scheduler/               # 调度器（1个工具）
│   ├── notification/            # 通知系统（2个工具）
│   ├── data-manager/            # 数据管理（2个工具）
│   ├── quantsys-v2-client/      # QuantsysV2 API 客户端
│   └── agent-os-client/         # Agent OS API 客户端（遗留）
│
├── profiles/investment/         # DSH Profile 配置模板
│   ├── start.sh                # 启动脚本
│   ├── cordis.yml              # 插件配置
│   └── README.md               # Profile 说明
│
├── docs/                        # 项目文档
├── examples/                    # 使用示例
├── CLAUDE.md                    # Claude Code 开发指南
└── package.json                 # Monorepo 配置
```

## 💻 开发指南

### 添加新工具到现有插件

1. 编辑插件源码（如 `packages/investment/src/index.ts`）
2. 重新构建：`cd packages/investment && pnpm build`
3. 重启 DSH profile

### 创建新插件包

详见 [CLAUDE.md](./CLAUDE.md) 的 "Creating a New Plugin Package" 章节。

### 开发工作流

```bash
# 1. 修改插件代码
vim packages/investment/src/index.ts

# 2. 重新构建
pnpm build

# 3. 重启 DSH profile
lsof -ti:13080 | xargs kill
cd ~/.dsh/profiles/investment && ./start.sh
```

## 📚 文档

- **[CLAUDE.md](./CLAUDE.md)** - 完整的开发指南（推荐阅读）
- [Profile README](./profiles/investment/README.md) - DSH Profile 说明
- [项目总结](./docs/project-summary.md) - 项目概览
- [开发阶段报告](./docs/) - Phase 1-4 完成报告

## 🧪 测试

```bash
# 运行所有测试
pnpm test

# 运行特定包的测试
cd packages/investment
pnpm test
```

## 🔧 常用命令

```bash
# 安装依赖
pnpm install

# 构建所有包
pnpm build

# 代码检查
pnpm lint

# 类型检查
pnpm typecheck
```

## 📊 技术栈

- **框架**: @deepseek-ai/cordis (DSH 核心)
- **插件系统**: DSH Plugin API
- **语言**: TypeScript
- **构建**: TypeScript Compiler
- **包管理**: pnpm workspace
- **测试**: vitest
- **后端**: QuantsysV2 (Python/FastAPI)

## 🎯 端口分配

- **13080** - DSH investment profile (Web UI)
- **5001** - QuantsysV2 backend (Python)
- **8080** - Agent OS (Go, 遗留)

## ⚠️ 重要说明

### Agent-DH 不是独立应用

- ❌ **不要** 在 agent-dh 中创建 HTTP 服务器
- ❌ **不要** 使用 `apps/cli/`（已删除，是遗留代码）
- ❌ **不要** 运行 `npm run dev`（已移除）

### 正确的使用方式

- ✅ 开发 DSH 插件（TypeScript）
- ✅ 使用 `pnpm build` 编译
- ✅ 通过 DSH profile 运行（`~/.dsh/profiles/investment/`）
- ✅ 保持 `cordis.yml` 与 profile 配置同步

## 🔗 相关项目

- **[QuantsysV2](../quantsys-v2)** - 量化交易后端（Python）
- **[Agent OS](../agent-os)** - Agent 管理服务（Go，遗留）
- **[DSH](https://github.com/deepseek-ai/dsh)** - DeepSeek Harness 框架

## 📄 许可证

MIT

---

**Status**: ✅ Active DSH profile with 14 investment plugins (48 tools)

**Version**: 0.1.1

**Last Updated**: 2026-08-19
