# CLAUDE.md - Agent-DH (DSH Investment Profile)

This file provides guidance to Claude Code when working with the Agent-DH project.

## Project Overview

**Agent-DH** 是 PI Investment 系统的 DSH (DeepSeek Harness) Profile，提供基于 AI 的投资分析和决策能力。

**关键理解**：Agent-DH 不是独立应用，而是一个 **DSH Profile**，通过 DSH 框架加载和运行。

## Architecture

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
│  • System prompt for investment analysis        │
│  • Configuration for quantsys-v2 backend        │
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

## Project Structure

```
agent-dh/
├── packages/                    # 14 个投资插件包（TypeScript 源码）
│   ├── investment/              # 投资数据工具（8个工具）
│   │   └── src/index.ts        # 行情、K线、财务、股票池、策略等
│   ├── trading/                 # 交易工具（6个工具）
│   │   └── src/index.ts        # 账户、持仓、交易执行、监控等
│   ├── intelligence/            # 智能工具（3个工具）
│   │   └── src/index.ts        # 盯盘规则、市场告警等
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
│   ├── (quantsys-v2-client 已迁移至仓库顶层 ../../quantsys-v2-client，插件经 file: 依赖引用)
│   └── agent-os-client/         # Agent OS API 客户端（遗留）
│
├── profiles/investment/         # DSH Profile 配置模板
│   ├── start.sh                # 启动脚本（拷贝到 ~/.dsh/profiles/investment/）
│   ├── cordis.yml              # 基础配置
│   └── README.md               # Profile 说明
│
├── docs/                        # 项目文档
│   ├── AUTONOMY-SYSTEM.md       # 自主能力总览
│   ├── WHY-NO-DIST.md           # 为何部分插件无 dist
│   ├── self-restart-behavior.md # 自修复重启行为
│   ├── rfcs/                    # RFC 设计提案 003-008
│   ├── architecture/            # 架构决策
│   ├── guides/                  # 操作指南
│   ├── protocols/               # 协议规范
│   └── work-logs/2026-08/       # 进度与总结（仅汇总）
│
├── examples/                    # 使用示例
├── scripts/                     # 工具脚本
└── package.json                 # Monorepo 配置
```

## How It Works

### 1. Plugin Development (This Repository)

Develop TypeScript plugins in `packages/`:

```bash
# Install dependencies
pnpm install

# Build all packages (TypeScript → JavaScript)
pnpm build

# Watch mode for development
cd packages/investment
pnpm dev  # If the package has a dev script
```

### 2. DSH Profile Installation (~/.dsh/profiles/investment/)

The DSH profile at `~/.dsh/profiles/investment/` references these packages:

```json
{
  "dependencies": {
    "@pi-investment/investment": "file:../../../pi-investment/agent-dh/packages/investment",
    "@pi-investment/trading": "file:../../../pi-investment/agent-dh/packages/trading",
    ...
  }
}
```

When you run `pnpm build` in agent-dh, the built JavaScript is immediately available to the DSH profile (via file: links).

### 3. DSH Profile Startup

The profile is started via DSH:

```bash
# Using the start script (recommended)
cd ~/.dsh/profiles/investment
./start.sh              # Default port 13080
./start.sh 13081        # Custom port

# Or using dsh command directly
dsh --profile investment --port 13080
```

This launches:
- DSH framework with web UI
- All 14 investment plugins (48 tools)
- Investment-focused system prompt
- Connection to quantsys-v2 backend (port 5001)

## Plugin Overview

### Core Investment Plugins

| Plugin | Tools | Description |
|--------|-------|-------------|
| `@pi-investment/investment` | 8 | 行情、K线、财务、宏观、北向资金、市场情绪、股票池、策略列表 |
| `@pi-investment/trading` | 6 | 账户信息、持仓、交易执行、交易监控、算法交易、对账 |
| `@pi-investment/intelligence` | 3 | 盯盘规则、盯盘管理、市场告警 |
| `@pi-investment/competition` | 3 | 对手行为、战场评估、操纵检测 |
| `@pi-investment/market` | 3 | 市场风格、行业分析、筹码分析 |
| `@pi-investment/risk` | 3 | 风险控制、风险指标、Barra分解 |
| `@pi-investment/strategy` | 6 | 策略执行、机会扫描、筛选、轮动提案、轮动模拟、轮动执行 |
| `@pi-investment/factor` | 2 | 因子计算、因子分析 |
| `@pi-investment/model` | 3 | 模型预测、模型训练、模型评估 |
| `@pi-investment/memory` | 3 | 记忆搜索、记忆写入、经验记录 |
| `@pi-investment/evolution` | 2 | 进化运行、进化排行榜 |
| `@pi-investment/scheduler` | 1 | 调度器管理 |
| `@pi-investment/notification` | 2 | 飞书通知、通用通知 |
| `@pi-investment/data-manager` | 2 | 数据质量报告、数据管理 |
| `@pi-investment/lifecycle` | 5 | 自修复重启 + 自我认知：self_restart/self_finalize/self_status（git wip 安全网、启动失败自动回滚、启动后自动续跑）+ self_system_prompt/self_info（获取自己的系统提示词与自身全景信息） |

### Infrastructure Packages

| Package | Purpose |
|---------|---------|
| `@pi-investment/quantsys-v2-client` | HTTP client for quantsys-v2 API |
| `@pi-investment/agent-os-client` | HTTP client for Agent OS (legacy, not actively used) |

## Development Workflow

### Adding a New Tool to a Plugin

1. **Edit the plugin source** (e.g., `packages/investment/src/index.ts`)，在 `registerTools()` 里注册：

```typescript
import { defineTool } from '@deepseek-ai/dsh-tools';

ctx.tools.register(defineTool({
  name: 'my_new_tool',
  description: '用于：获取XXX数据。例如：查询某股票的XXX信息。',
  parameters: {
    symbol: { type: 'string', description: '股票代码，例如：600000.SH', required: true },
  },
  output: {
    schema: {
      type: 'object',
      properties: {
        result: { type: 'string', description: '结果' },
      },
      additionalProperties: true,
    },
    render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },
  timeoutMs: 10000,
  execute: async (args: any) => {
    return { result: 'data' } as any;
  },
} as any));
```

**⚠️ Schema 铁律（dsh-tools rc7 起，违反则 DSH 启动即崩，UNSUPPORTED_SCHEMA）：**

1. **每个 `type: 'object'` 节点必须显式写 `additionalProperties: true` 或 `false`**——包括 `parameters`/`output.schema` 的任意嵌套层级（properties 里的、items 里的，无一例外）。自由键值 map 写 `true`。
2. 对象节点只允许 `type`/`properties`/`additionalProperties` + 注解键（`description`/`title`/`default`/`examples`），其他键（如 `required: []` 数组）不被 DSL 支持；必填在参数属性上用 `required: true` 标记。
3. 写完必须跑冒烟测试验证：`cd agent-dh && npx vitest run tests/plugin-schema.smoke.test.ts`（构造即编译全部工具 schema，新插件要加进测试里的 PLUGINS 列表）。

2. **Rebuild the package**（tsx 模式下可选）:

```bash
cd packages/investment
pnpm build
```

3. **Restart DSH profile** (if running):

```bash
# Find and kill the running instance
lsof -ti:13080 | xargs kill

# Restart
cd ~/.dsh/profiles/investment
./start.sh
```

### Creating a New Plugin Package

1. **Create package directory**:

```bash
mkdir -p packages/my-plugin/src
cd packages/my-plugin
```

2. **Create package.json**:

```json
{
  "name": "@pi-investment/my-plugin",
  "version": "0.1.0",
  "description": "My custom plugin",
  "type": "module",
  "main": "./src/index.ts",
  "exports": {
    ".": {
      "import": "./src/index.ts",
      "types": "./src/index.ts"
    }
  },
  "dependencies": {
    "@deepseek-ai/cordis": "workspace:^",
    "@deepseek-ai/dsh-tools": "workspace:^",
    "@pi-investment/quantsys-v2-client": "workspace:*"
  }
}
```

3. **Create src/index.ts**（Service 类模式，参照 `packages/scheduler/src/index.ts`）：

```typescript
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';

export default class MyPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
    }).default({} as any),
  }).default({} as any)

  constructor(ctx: Context, config: any) {
    super(ctx, 'my-plugin');
    this.registerTools();
  }

  private registerTools() {
    this.ctx.tools.register(defineTool({
      name: 'my_tool',
      description: '...',
      parameters: {},
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 10000,
      execute: async () => ({ ok: true } as any),
    } as any));
  }
}
```

注意遵守上面的 **Schema 铁律**（每个 object 节点显式 `additionalProperties`）。

4. **Add to DSH profile** (`~/.dsh/profiles/investment/package.json`):

```json
{
  "dependencies": {
    "@pi-investment/my-plugin": "file:../../../pi-investment/agent-dh/packages/my-plugin"
  }
}
```

5. **Add to profile config** (`~/.dsh/profiles/investment/cordis.patch.yml`):

```yaml
- insert:
    - id: my-plugin
      name: '@pi-investment/my-plugin'
      config:
        quantsysV2:
          baseURL: http://localhost:5001
```

6. **链接进 profile**（注意：profile 目录不在 agent-dh workspace 内，`pnpm install` 会因 `workspace:^` 协议报错，必须手动建符号链接）：

```bash
ln -sfn /Users/yunpeng/pi-investment/agent-dh/packages/my-plugin \
  ~/.dsh/profiles/investment/node_modules/@pi-investment/my-plugin
# 新插件的依赖链接由 agent-dh 根目录的 pnpm install 生成：
cd agent-dh && pnpm install
```

## dsh-tools SDK 支持范围（2026-08-31 实测整理）

> 来源：`@deepseek-ai/dsh-tools`（deepseek-harness `packages/core/tools`）。本 profile 实际运行版本 **0.1.1-rc.2**；agent-dh 各包 `pnpm link` 的 workspace 版本为 **0.1.0-rc.7**（API 面一致，schema DSL 行为相同）。新增/修改工具前先读本节，避免踩已修复的坑。

### 核心 API（插件 ctx 注入的服务 `tools`）

| API | 作用 | 要点 |
|-----|------|------|
| `ctx.tools.register(definition)` | 注册工具 | 必须含规范 `output` 声明；同层重名抛错；`timeoutMs` 须为正有限数；随调用方 fiber dispose |
| `ctx.tools.defineTool(spec)` | **推荐入口** | 类型化参数 schema（扁平 `parameters` 对象）+ 自动参数校验 + 纯输出投影器 |
| `ctx.tools.presentAs(mode)` | agent 级呈现模式 | `native`（函数定义）/ `code`（run_code 传输）/ `both`；仅 agent 作用域可调 |
| `ctx.tools.restrict(filter)` | agent 作用域允许/拒绝掩码 | 仅 agent 作用域可调；实时可见性组合，**非权限边界** |
| `ctx.tools.get(name, scope)` | 按名解析（含遮蔽） | 被 restrict 排除的视为不存在 |
| `ctx.tools.schemas(scope)` | 列出可见工具 schema | 不含 execute |
| `ctx.tools.guard(guard)` | 单调执行守卫 | 返回理由=拒绝；后续 waterfall 无法翻案 |
| `ctx.tools.execute(exec)` | 无损快照执行流水线 | 参数冻结→策略→分发→结果快照 |
| `ctx.tools.executionMode(exec)` | 并发分类 | 仅 `isConcurrencySafe(args)` 精确返回 `true` 才并行，否则独占 |

### 配置与呈现

- `tools.mode: native（默认）| code | both`——进程级呈现方式；`code` 模式提供保留的 `run_code` 传输 + `tools:sdk` 段 + `tools:code-only` 规则（模型直接调其他工具会被解析为 UNKNOWN_TOOL）
- `ctx.systemPrompt.tools()` 自动把工具 schema 注入系统提示词组装

### 执行流水线（注册后每次调用）

`tools/pre-execute`（允许/拒绝/询问门禁）→ 单调守卫 → `tools/execute`（包装层：超时/重试/指标；只能替换 signal）→ `tools/post-execute`（可替换 content 或 value、附加上下文）→ 工具定义 `finalizeContent`（仅替换 content，对所有规范化结果恰好跑一次）→ `tools/result`（只读观测事件）

### 类型化参数 schema DSL（defineTool 的 parameters）

**支持**：`string`、`number`、`integer`、`boolean`、`null`、`array`、`object`、`json`（仅作者用）、恰好一个分支的 `oneOf`；标量 `enum`/`const` 值必须符合声明类型。

**铁律（实测踩坑，违反会被 API 惰性拒绝或注册失败）**：
1. **扁平参数**：`parameters` 是 `{ paramName: {type, description, required?} }` 的扁平对象，**不是标准 JSON Schema 根**；`defineTool` 负责转换。裸 `ctx.tools.register(flatParams)` 会把扁平 schema 直接透传给模型 API → "Invalid schema for function ... got type null"
2. **每个显式 object 必须声明 `additionalProperties: true|false`**；无 properties 的封闭对象只接受 `{}`；隐式参数根保持开放默认
3. **系统不应用默认值**——schema 里的 `default` 不会被运行时注入，安全相关默认值（如 dry_run）必须在 execute 内显式兜底
4. schema 记录只接受可枚举字符串键；数组必须稠密普通数组
5. 执行前校验失败 → `ToolArgsError`（INVALID_ARGS），走普通错误结果路径

### 输出 schema 强制子集（JsonSchemaNode）

- 允许：任意 JSON 根、仅注解节点、恰好一个分支的 `oneOf`；注解须保持无损 JSON
- `assertSupportedJsonSchema()` 拒绝不受支持构造；`validateJsonSchemaValue()` 返回带路径违规
- **模型侧约束（实测）**：输出 schema 不要用 `type: 'null'` 分支（deepseek API 拒绝）；字段可能为 null 时声明 `{type:'object', additionalProperties:true}` 并在返回时省略该键（BaseTool 的 sanitizeForJson 会删除 undefined 键）
- 返回值必须是输出 schema 声明的规范 JSON（lossless：无 undefined/NaN）

### 取消 / 超时 / 并发

- **取消是协作式**：`exec.signal`（AbortSignal）必填只读；工具主体负责观测并在工作停止后结算；取消时机区分 `ABORTED_BEFORE_DISPATCH` / `ABORTED` / `TOOL_TIMEOUT`
- `timeoutMs`：正数且有限，**策略元数据，模型不可见**
- `isConcurrencySafe(args)`：只有精确 `true` 才允许并发分发；并发主体不得改动父级拥有状态

### 工具自有 UI 呈现

- `presentCall()` / `presentResult()` 纯函数返回呈现意图：`generic` / `terminal` / `diff` / `search`（grep/glob 结果）/ `read`（带行号文件读取）/ `web`（检索）卡片；返回 undefined 走通用回退
- `output.presentationMeta(args, value)` 派生持久化 JSON 元数据（随 tool/result 回放；规范值不持久化）
- 参考实现：`dsh-tool-bash`、`dsh-tool-fs`

### 关键类型速查

`ToolDefinition`、`ToolExecutionInput`、`ToolExecutionToken`（不透明 Symbol）、`ToolExecution`（只读视图）、`ToolRunContext`（`deferContext` 延迟注入上下文）、`ToolExecutionResult`（判别联合：成功带 value / 失败带 error）、`PreToolDecision`（allow/deny/ask）、`PostToolDecision`、`ToolGuard`

### MCP

每个 MCP 服务器用一个插件；发现工具后用服务器的 schema 调 `ctx.tools.register()`。

## Configuration Files

### agent-dh/cordis.yml (Template - Standalone Format)

Located at `agent-dh/cordis.yml`, this is a **reference template** showing all plugins and configurations in standalone format. It defines:
- DSH core plugins (settings, credentials, LLM)
- Investment plugins with their configs
- Agent loop configuration
- System prompt for investment analysis

**Note**: This file uses **standalone cordis format** (flat list of plugins) and is **not directly used** by DSH.

### ~/.dsh/profiles/investment/cordis.patch.yml (Active - Patch Format)

This is the **active configuration** used by DSH when running the investment profile. It uses **patch format** (with `insert:` directives) to overlay plugins on top of DSH base bundles.

**Key differences from cordis.yml**:
- Uses `- insert:` blocks to add plugins
- Does NOT include DSH core plugins (settings, credentials, LLM) - those come from `@deepseek-ai/dsh-base` bundle
- Only includes investment-specific plugins and overrides

**Example patch format**:
```yaml
- insert:
    - id: investment
      name: '@pi-investment/investment'
      config:
        quantsysV2:
          baseURL: http://localhost:5001
```

**To update the active configuration**:
1. Edit `~/.dsh/profiles/investment/cordis.patch.yml` directly (recommended), OR
2. Regenerate from `cordis.yml` template (requires conversion to patch format)

## Environment Variables

### Required

- `DEEPSEEK_API_KEY` - DeepSeek API key for LLM
- `OPENAI_API_KEY` - Same as DEEPSEEK_API_KEY (for compatibility)

### Optional

- `QUANTSYS_V2_API_URL` - QuantsysV2 backend URL (default: `http://localhost:5001`)
- `AGENT_OS_BASE_URL` - Agent OS URL (legacy, not actively used)

## Common Tasks

### Start the Investment Agent

```bash
# Ensure quantsys-v2 is running on port 5001
cd ../quantsys-v2
python start_all.py

# Start the DSH investment profile
cd ~/.dsh/profiles/investment
./start.sh 13080
```

Access the web UI at `http://localhost:13080`

### Stop the Investment Agent

```bash
# Find the process
lsof -ti:13080

# Kill it
kill <PID>
```

### Rebuild All Plugins

**Note**: Rebuilding is **optional** in tsx mode. DSH loads TypeScript source directly.

```bash
cd agent-dh
pnpm build  # Only needed if you want pre-built .mjs files
```

**Why some packages don't have dist/?**: See [docs/WHY-NO-DIST.md](./docs/WHY-NO-DIST.md)

### Check Plugin Status

```bash
# List all packages
ls -la packages/

# Check if a package is built
ls -la packages/investment/dist/  # Should contain .js files
```

### Update Profile Configuration

**Recommended**: Edit the active configuration directly:

```bash
# Edit the active patch file
vim ~/.dsh/profiles/investment/cordis.patch.yml

# Restart the profile to apply changes
lsof -ti:13080 | xargs kill
cd ~/.dsh/profiles/investment && ./start.sh
```

**Alternative**: Update the template and regenerate (advanced):

```bash
# 1. Edit the template
vim agent-dh/cordis.yml

# 2. Convert to patch format and apply (requires manual conversion)
# Note: cordis.yml uses standalone format, cordis.patch.yml uses patch format
# You need to wrap plugin entries in "- insert:" blocks

# 3. Restart the profile
```

## Important Notes

### ❌ What NOT to Do

- **DO NOT** create HTTP servers in agent-dh packages (they are DSH plugins, not standalone apps)
- **DO NOT** use `apps/cli/` (removed - was legacy demo code)
- **DO NOT** run `npm run dev` in agent-dh root (removed - was for legacy CLI)

### ✅ What TO Do

- **DO** develop plugins as DSH plugin packages
- **DO** use `pnpm build` to compile TypeScript
- **DO** test via the DSH profile (`~/.dsh/profiles/investment/`)
- **DO** keep `cordis.yml` in sync with `~/.dsh/profiles/investment/cordis.patch.yml`

### Port Allocation

- **13080** - DSH investment profile (web UI)
- **5001** - QuantsysV2 backend (Python)
- **8080** - Agent OS (Go, legacy)

### Dependencies

Agent-DH plugins depend on:
- **DSH framework** (`@deepseek-ai/cordis`, `@deepseek-ai/dsh-*`)
- **QuantsysV2 backend** (must be running on port 5001)
- **DeepSeek API** (requires API key)

## Troubleshooting

### Plugin Not Loading

1. Check if package is built: `ls packages/<plugin>/dist/`
2. Check if profile links are correct: `cat ~/.dsh/profiles/investment/package.json`
3. Check DSH logs for errors

### Tool Not Available

1. Verify tool is exported in plugin's `src/index.ts`
2. Verify plugin is listed in `cordis.patch.yml`
3. Restart the DSH profile

### QuantsysV2 Connection Failed

1. Check if quantsys-v2 is running: `lsof -ti:5001`
2. Check `QUANTSYS_V2_API_URL` environment variable
3. Test API manually: `curl http://localhost:5001/api/stocks/search?q=平安`

## 自修复重启与自我认知（lifecycle 插件）

lifecycle 插件提供两类能力（共 5 个工具）：

**自修复闭环**：`self_restart` / `self_finalize` / `self_status`  
**自我认知**：`self_system_prompt` / `self_info`

- `self_system_prompt`：获取自己的完整系统提示词（sections + 变量 + 可见工具清单 + 渲染后的最终文本），基于 dsh-system-prompt 的 `ctx.systemPrompt.assemble()`，支持 agent 作用域组装
- `self_info`：自身全景信息（身份/版本、进程 pid/运行时长/内存、git 状态、生命周期状态、工具统计、关键配置）

自修复闭环：agent 可通过 `self_restart(reason, resume_task)` 重启自身，实现"改代码 → 重启生效 → 自动续跑验证 → 合并"：

- **检查点**：重启前未提交的 `agent-dh/` 改动自动提交到 `agent-self/*` wip 分支；基线分支保持干净
- **重启器**：`scripts/self-restart.ts`（detached 独立进程，自包含、只依赖 node 内置模块）负责 kill → `start.sh` 拉起 → :13080 健康检查
- **自动回滚**：启动失败（120s 端口不通）自动 `git checkout <base>` 回滚重拉，失败的 wip 分支保留供复盘；回滚后也失败则标记 dead 等人工
- **自动续跑**：新进程启动后 lifecycle 插件读 `pending-resume.json`，通过 `ctx.agents` + `agent.followup()` 向 investor 注入续跑消息（与 DSH schedule 包同款投递模式）
- **收尾**：验证通过调 `self_finalize(merge)` 合回基线并更新 last-known-good；失败可调 `self_finalize(rollback)`
- **护栏**：每小时最多 10 次重启（2026-08-20 起，原 3 次；高频自修复验证场景下 3 次偏紧）、`restarting.lock` 防重入、同一任务连挂 2 次提示停止自动重试
- **状态文件**：`~/.dsh/profiles/investment/state/`（pending-resume.json、restart-result.json、last-known-good、restart-counter.json）
- **配置项**：repoRoot / agentDhRoot / profileDir / port / agentId / maxRestartsPerHour（见 cordis.patch.yml 的 lifecycle 段）

设计文档：[docs/rfcs/002-agent-dh-self-restart.md](../../docs/rfcs/002-agent-dh-self-restart.md)

### Build Errors

```bash
# Clean and rebuild
cd agent-dh
rm -rf node_modules packages/*/node_modules packages/*/dist
pnpm install
pnpm build
```

## Related Documentation

- [DSH Framework](https://github.com/deepseek-ai/dsh) - DeepSeek Harness documentation
- [QuantsysV2](../quantsys-v2/CLAUDE.md) - Backend service documentation
- [PI Investment Root](../CLAUDE.md) - Overall system architecture
- [Profile README](profiles/investment/README.md) - Profile-specific documentation

## Version History

- 2026-08-19: lifecycle 代码审查修复（50cb6084）：限流检查移到拿锁前（原拒绝路径泄漏锁致永久变砖）；重启器每次拉起前预写 restart-result（原时序竞争会让 rolled_back 误报成功）；锁 >15min stale 接管；状态读容错+原子写；self_finalize 幂等
- 2026-08-19: 修复 investment/market 插件 schema 缺 additionalProperties 导致的全量启动崩溃；新增 tests/plugin-schema.smoke.test.ts 门禁；重写工具/插件开发样例为 defineTool + Service 模式并记录 Schema 铁律
- 2026-08-19: Added `@pi-investment/lifecycle` 自修复重启插件（RFC 002，E2E 验证通过）
- 2026-08-19: Removed legacy `apps/cli/`, clarified DSH profile architecture
- 2026-08-18: Initial DSH profile setup with 14 plugins (48 tools)
- 2026-08-18: Migrated from standalone CLI to DSH profile

---

**Status**: ✅ Active DSH profile with 14 investment plugins

**Version**: 0.1.1

**Last Updated**: 2026-08-19

## 自主能力系统（2026-08-20 新增）

Agent-DH 现已具备**自我学习、知识蒸馏、持续进化**能力。

### 核心插件

#### @pi-investment/learning ✨ NEW
自我学习引擎：
- `learning_track` - 追踪经验（自动拦截工具调用）
- `learning_analyze` - 分析模式，生成改进建议
- `learning_distill` - 知识蒸馏（复杂推理 → 简单规则）
- `learning_apply` - 应用改进，集成 self_restart

**特性**：
- 自动追踪关键工具（portfolio_trade, strategy_execute 等）
- 计算奖励信号（盈亏/成功率/反馈）
- 持久化到 memory 系统
- 安全应用：dry_run → 确认 → 重启验证

**完整文档**: [docs/AUTONOMY-SYSTEM.md](./docs/AUTONOMY-SYSTEM.md)  
**设计文档**: [docs/rfcs/003-self-learning-distillation.md](./docs/rfcs/003-self-learning-distillation.md)

---

## 自主能力体系完整设计（2026-08-20）

Agent-DH 现已完成**完整自主能力体系**的架构设计。

### 📚 核心文档

1. **`docs/AUTONOMY-SYSTEM.md`** - 自主能力总览（能力矩阵、学习循环）
2. **`docs/rfcs/003-self-learning-distillation.md`** - 学习系统设计
3. **`docs/rfcs/005-self-evolving-agent.md`** - 自进化 Agent 设计
4. **`docs/rfcs/006-prompt-genome-sections.md`** - 提示词基因组切分
5. **`docs/rfcs/007-genome-manager.md`** - genome_manager 工具化
6. **`docs/rfcs/008-validation-gate.md`** - 验证门设计

> 注：未实现的 RFC（004 诊断插件、009 公告板生命周期、010 窗口-OS 生命周期）设计文档已从 `docs/` 移除；已实现的 RFC 见 `docs/rfcs/`（003/005/006/007/008）。

### 🎯 当前状态

- ✅ **已实现**: 30.2% (lifecycle + memory + learning 基础)
- 📋 **设计完成**: 100% (完整 12 周规划)
- 🚀 **待启动**: Sprint 1 - Diagnostics Plugin

### 下一步

由其他 Agent 按照 RFC 004 实施 Diagnostics 插件。

---

## 多实例生命周期铁律（2026-08-21 起）

同机运行多个 dsh 实例（主实例 :3080 / investment :13080 / 其他 profile）时，停止实例必须**精确到实例**，历史上模糊停止曾误杀其他 agent：

1. **禁止 `pkill -f 'dsh web'` / `killall node`** 等模糊匹配——会命中所有 dsh 实例
2. **lsof 查端口必须带 `-sTCP:LISTEN`**——不带会把连着该端口页面的浏览器进程（Chrome Helper）也杀掉
3. **每个实例**：`start.sh` 写 `state/server.pid` + `state/server.port`；停止走 `stop.sh`（pidfile + 监听校验 + 端口兜底，防 PID 复用误杀）
4. self_restart 按 PID 精确停止，天然安全；手动停实例一律用该实例的 stop.sh

## Agent 身份系统（2026-08-21 起）

每个 agent 必须有**唯一 ID 和名字**，提高自我认知与协作可区分性：

- **注册表**：`~/.dsh/profiles/investment/agents.json`（instance + agents[]：id/name/role/primary/alias_of）
- **提示词**：lifecycle 插件注册 `agent:identity` 段（order 5，宪法段之前），身份不进基因组、不参与进化
- **self_info**：identity 块来自注册表
- **经验署名**：learning 自动追踪的 context.agent 带 id/name/instance
- **通知署名**：feishu_notify/notification_send 外发消息自动带 `—— {name} ({id})` 署名
- 新分身加入时：在 agents.json 注册后再接入
