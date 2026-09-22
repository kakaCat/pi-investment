# CLAUDE.md - Agent-DH (DSH Investment Profile)

This file provides guidance to Claude Code when working with the Agent-DH project.

> **认知入口（先读）**：[agent-dh Wiki](docs/README.md)——子项目说明书与大纲（9 卷：架构/工具契约/账户交易/
> 数据后端/自主能力/页面插件/需求流水线/运维排障/证据附录），每卷页面可独立读懂并互相链接。

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
│  Agent-DH Profile（项目内 profile：agent-dh）   │
│  • 数据目录 = agent-dh/.dsh-data/（DSH_HOME）   │
│  • 投资插件包（packages/，经 cordis 配置注册）  │
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
├── packages/                    # 投资插件包（两级技术域，对齐 deepseek-harness，RFC 015）
│   ├── tools/                  # host 工具插件（17 个）
│   │   ├── investment/         #   投资数据工具（8个工具）：行情、K线、财务、股票池、策略等
│   │   ├── trading/            #   交易工具（6个工具）：账户、持仓、交易执行、监控等
│   │   ├── intelligence/       #   智能工具（3个工具）：盯盘规则、市场告警等
│   │   ├── competition/ market/ risk/ strategy/ factor/ memory/ evolution/
│   │   ├── scheduler/ notification/ data-manager/ learning/ genome/ lifecycle/ evolver/
│   ├── web/                    # 页面插件（7 个）：bulletin/dsh-pmboard/execution/genome/holdings/page-kit/web-liveness
│   ├── client/                 # API 客户端库（agent-dh-client）
│   ├── runtime/                # 运行时/管理包（agent-os-manager、investment-agent-loop、quantsys-v2-manager、solve-kit）
│   ├── core/                   # core-tool（三段式接口类型规范）
│   ├── (quantsys-v2-client 已迁移至仓库顶层 ../../quantsys-v2-client，插件经 file: 依赖引用)
│
├── apps/web/                    # Web 应用入口（布局对齐 deepseek-harness apps/web）：
│   │                            #   src/main.ts 浏览器入口（AppWebEntry + desktop boot 注入）、
│   │                            #   src/node-module-stub.ts（node:module 浏览器桩，与 dsh 逐字一致）、
│   │                            #   index.html/public/ vite 构建输入、tests/ 全部测试；
│   │                            #   dist/ 即 :13080 供应的 shell（pnpm override link:apps/web，
│   │                            #   dsh-web-app 按包名解析到它）；裸 vite dev 被守卫拒绝是设计
│   │                            #   如此，开发走 pnpm dev（= vite build --watch，server stat-poll
│   │                            #   发现 dist 变化会广播浏览器重载）
├── packages/bundle/             # 业务域 bundle（dsh.bundle.patch 载体，无代码）：插件页卡片的数据源，
│   ├── bundle-stock/           #   「股票投资」10 行：investment/market/factor/data-manager/trading/strategy/risk/competition/intelligence/quantsys-v2-manager
│   ├── bundle-evolution/       #   「学习与进化」6 行：memory/learning/evolution/evolver/genome/lifecycle
│   └── bundle-platform/        #   「平台通用」5 行：notification(飞书)/scheduler/dsh-pmboard/web-liveness/agent-os-manager
│                                 #   新增插件的行加进对应业务域 bundle（REQ-260922133113-ebc5）
├── config/cordis.yml            # Profile 配置模板（start.sh 据此补全 .dsh-data 内的活动配置）
├── .dsh-data/                   # DSH_HOME = 数据目录（项目内托管，不入库）：
│   │                            #   agents.json / dsh-reqboard.json / .credentials.yaml / state/
│   └── profiles/agent-dh/       #   活动 profile 脚手架（start.sh 生成，含活动 cordis.patch.yml）
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
cd packages/tools/investment
pnpm dev  # If the package has a dev script
```

### 2. 项目内 Profile（agent-dh/.dsh-data/）

**2026-09-14 起 profile 不再放 `~/.dsh/profiles/investment/`**（该目录已清空删除）。现役布局：

- **profile 名 = `agent-dh`**（项目内 profile），DSH_HOME = 数据目录 = `agent-dh/.dsh-data/`；
- 活动 profile 脚手架在 `.dsh-data/profiles/agent-dh/`，由 `scripts/start.sh` 从 `config/cordis.yml` 模板补全生成；
- agents.json、dsh-reqboard.json、.credentials.yaml、state/ 等全部活数据都在 `.dsh-data/`。

插件依赖通过 agent-dh 根 `package.json` 的 workspace/file 引用指向 `packages/` 源码：

⚠️ **`pnpm build` 不是部署，`pnpm install` 更不是。** 别以为改完代码就生效了 —— 2026-09-11 的事故正是这么来的。

- profile 的 `@pi-investment/*` 依赖**必须是**指向仓库源码的**符号链接**。此时改源码 → 重启即生效（tsx 直载 TS）。
- 但 `pnpm install` 会把它们换回**硬链接副本**。硬链接只在"没人替换过该文件"时同步：任何一次 Write/Edit（写临时文件再 rename）都会换掉 inode、断链，profile 静默停在旧版本，**且没有任何报错**。
- 更隐蔽的是它会**部分**过期：没被编辑过的文件仍保持硬链接、看起来"是同步的"，被编辑过的才落后 —— 于是很容易误判成"已经部署好了"。

因此发版/部署的正确入口是：

```bash
# 体检（有漂移则退出码 1，可用于 CI）
python3 agent-dh/scripts/relink-profile.py --check

# 把副本换回符号链接（旧的先备份到 .deploy-backup/<时间戳>/）
python3 agent-dh/scripts/relink-profile.py

# 重启（:13080 由 launchd 托管，kill 会被 KeepAlive 拉回来）
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh
```

`agent-dh/scripts/restart-with-build.sh` 已把这三步串起来，正常发版走它即可。

### 3. DSH Profile Startup

统一启动入口在仓库内（`scripts/start.sh`，也是 launchd 作业与 self-restart 拉起的同一份）：

```bash
# Using the start script (recommended)
cd agent-dh
./scripts/start.sh              # Default port 13080
./scripts/start.sh --port 13081 # Custom port

# Or using dsh command directly
dsh --profile agent-dh --port 13080
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

1. **Edit the plugin source** (e.g., `packages/tools/investment/src/index.ts`)，在 `registerTools()` 里注册：

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
3. 写完必须跑冒烟测试验证：`cd agent-dh && npx vitest run apps/web/tests/plugin-schema.smoke.test.ts`（构造即编译全部工具 schema，新插件要加进测试里的 PLUGINS 列表）。

2. **Rebuild the package**（tsx 模式下可选）:

```bash
cd packages/tools/investment
pnpm build
```

3. **Restart DSH profile** (if running):

重启统一走仓库内入口 `scripts/start.sh`：当 :13080 由 launchd 作业 `com.pi-investment.dsh`
托管（KeepAlive）时它会自动转交 `launchctl kickstart -k`——**不要 kill**，kill 会被 launchd
立刻拉起，随后再手工启动必然 `EADDRINUSE`（2026-09-11 事故）。

```bash
# 重启（托管时脚本内部自动走 kickstart；未托管时直接拉起）
cd agent-dh && ./scripts/start.sh

# 调试端口（独立于托管实例）
./scripts/start.sh --port 13081
```

### Creating a New Plugin Package

1. **Create package directory**:

```bash
mkdir -p packages/tools/my-plugin/src
cd packages/tools/my-plugin
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

3. **Create src/index.ts**（Service 类模式，参照 `packages/tools/scheduler/src/index.ts`）：

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

4. **Add to agent-dh 根 `package.json`**（workspace 依赖）:

```json
{
  "dependencies": {
    "@pi-investment/my-plugin": "workspace:*"
  }
}
```

5. **Add to 对应业务域 bundle 的 patch**（2026-09-22 起，REQ-260922133113-ebc5；股票投资→`packages/bundle/bundle-stock/cordis.patch.yml`，自主能力→`bundle-evolution/`，通用能力→`bundle-platform/`）：

```yaml
    - id: my-plugin
      name: '@pi-investment/my-plugin'
      config:
        quantsysV2:
          baseURL: http://localhost:5001
```

⚠️ 不要再加进 `config/cordis.yml`：投资插件行已全部迁入伞 bundle（bundle 层），用户层只放
对 bundle 行的覆盖（disabled/config 微调）。两处同 id 会被插件管理器判 unaddressable。

6. **生成链接并核验**：

```bash
# 新插件的依赖链接由 agent-dh 根目录的 pnpm install 生成：
cd agent-dh && pnpm install

# 统一成符号链接 —— 别手写 ln，pnpm install 可能产生硬链接副本，
# 而那些副本会在文件被编辑后静默停在旧版本（见上文「⚠️ pnpm build 不是部署」）
python3 agent-dh/scripts/relink-profile.py
```

## Configuration Files

### agent-dh/config/cordis.yml (Template - 配置源)

位于 `agent-dh/config/cordis.yml`，是 profile 配置的**唯一来源模板**。它定义：
- Agent preset（investment：内置 standard 去掉 delegation 组）
- 投资插件清单及各自 config
- 禁用有 bug 的插件
- Agent loop / system prompt 配置

`scripts/start.sh` 启动时把缺失项从本模板补全到活动配置（`--force-config` 强制全覆盖）。

### agent-dh/cordis.yml (历史参考)

仓库根的旧版 standalone 格式配置，保留作参考，**不直接参与加载**。

### packages/bundle/*/cordis.patch.yml (Bundle 层 - 投资插件行真身)

2026-09-22（REQ-260922133113-ebc5）起，21 行投资插件按业务域分三个标准 bundle 加载：
`bundle-stock`（股票投资 10 行，含盯盘/quantsys-v2 管理）、`bundle-evolution`（学习与进化 6 行）、
`bundle-platform`（平台通用 5 行：飞书通知/调度/看板/页面自愈/agent-os-manager）。
profile 清单注册**两处都要写**（2026-09-22 实测踩坑）：
- `dsh.profile.bundles` —— 决定 bundle 层是否**加载**（boot 组装）
- `dependencies`（`link:../../../packages/bundle/<包>`）—— 决定插件管理页是否**显示**：
  客户端过滤为 `!BUILTIN && (installed || optional || error)`，而 `installed` 直接取自
  profile `dependencies`（官方 OPTIONAL_BUNDLES 硬编码只含两个实验包）。**只写 bundles 不写
  dependencies = 插件在运行但插件页看不见**（本次故障根因，排查耗时长，勿再踩）。

DSH 侧边栏「插件」页据此显示三张业务卡，行级可开关（开关写入用户层覆盖）。
bundle 包无代码、无 main，只是 patch 载体；飞书通知属通用能力，固定在 platform 域，不进业务域。
管理页对这三个包会显示「卸载」按钮（removable），**不要点**——卸载会走 pnpm 改 profile 依赖。

### .dsh-data/profiles/agent-dh/cordis.patch.yml (Active)

DSH 实际加载的活动配置（patch 格式，`- insert:` 叠加在 `@deepseek-ai/dsh-base` bundle 之上），
由 start.sh 从 `config/cordis.yml` 生成/补全。日常改配置优先改模板 `config/cordis.yml` 再重启；
紧急情况下可直接改活动配置，但要记得回同步到模板，否则下次 `--force-config` 会被覆盖。

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

# Start the DSH investment profile（仓库内统一入口）
cd agent-dh
./scripts/start.sh 13080
```

Access the web UI at `http://localhost:13080`

### Stop the Investment Agent

```bash
# 本实例的专用停机脚本（pidfile + 监听校验；托管端口内部走 launchctl bootout）
cd agent-dh && ./scripts/stop.sh

# 恢复运行
cd agent-dh && ./scripts/start.sh
```

**不要用 `kill`**：KeepAlive 会立刻把它拉起来，`kill` 看起来成功但服务还在跑（静默失效）。
真正停机必须 `launchctl bootout gui/$(id -u)/com.pi-investment.dsh`，`stop.sh` 已经这么做了。

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
ls -la packages/tools/investment/dist/  # Should contain .js files
```

### Update Profile Configuration

**Recommended**: 改模板后重启（模板是唯一来源，活动配置由 start.sh 生成）:

```bash
# 1. Edit the template
vim agent-dh/config/cordis.yml

# 2. Restart the profile to apply changes
cd agent-dh && ./scripts/start.sh        # 托管时自动转 kickstart
# 需要强制用模板全覆盖活动配置时：./scripts/start.sh --force-config
```

**Alternative**: 紧急情况下直接改活动配置 `.dsh-data/profiles/agent-dh/cordis.patch.yml`，
重启生效——但事后必须回同步到 `config/cordis.yml`，否则下次 `--force-config` 会被模板覆盖。

## Important Notes

### ❌ What NOT to Do

- **DO NOT** create HTTP servers in agent-dh packages (they are DSH plugins, not standalone apps)
- **DO NOT** use `apps/cli/` (removed - was legacy demo code)
- **DO NOT** run `npm run dev` in agent-dh root (removed - was for legacy CLI)

### ✅ What TO Do

- **DO** develop plugins as DSH plugin packages
- **DO** use `pnpm build` to compile TypeScript
- **DO** test via the DSH profile（`cd agent-dh && ./scripts/start.sh`，数据在 `.dsh-data/`）
- **DO** keep 配置模板 `config/cordis.yml` 与活动配置 `.dsh-data/profiles/agent-dh/cordis.patch.yml` 语义一致（改活动配置后回同步模板）

### Architecture Rules (Mandatory)

#### Notification Architecture

**All notifications MUST go through `NotificationFacade`. Direct calls to Feishu SDK are FORBIDDEN.**

- Application layer can only import `application.notification.NotificationFacade`
- NEVER import `infrastructure.notification.channels.*`
- New notification types MUST extend `NotificationFacade` first

**Reference:** `pi-investment/CLAUDE.md` - "Architecture Rules (Mandatory)" section

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
2. Check if dependency links are correct: `ls -la node_modules/<plugin>`（应为指向 packages/ 的符号链接；体检用 `python3 scripts/relink-profile.py --check`）
3. Check DSH logs for errors

### Tool Not Available

1. Verify tool is exported in plugin's `src/index.ts`
2. Verify plugin is listed in 对应业务域 bundle 的 patch `packages/bundle/<域>/cordis.patch.yml`（bundle 层；用户层只放覆盖）
3. Restart the DSH profile（`./scripts/start.sh`）

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
- **状态文件**：`agent-dh/.dsh-data/state/`（pending-resume.json、restart-result.json、last-known-good、restart-counter.json）
- **配置项**：repoRoot / agentDhRoot / profileDir / port / agentId / maxRestartsPerHour（见 `config/cordis.yml` 的 lifecycle 段）

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

## Version History

- 2026-09-22: 插件 bundle 化（REQ-260922133113-ebc5）——投资插件行从用户层裸 insert 迁入三个
  业务域 bundle（`packages/bundle/bundle-stock|bundle-evolution|bundle-platform`，dsh.bundle.patch
  规范），接入 DSH 插件管理页；profile 清单注册，start.sh 脚手架同步；config/cordis.yml 用户层只留覆盖项
- 2026-09-22: apps/web 成为 :13080 实际供应的 shell——pnpm.overrides 的 `@deepseek-ai/dsh-web-frontend`
  改 `link:apps/web`（dsh-web-app 按包名 require.resolve 落到 apps/web）；`pnpm dev` 改 dsh 式
  watch 构建（裸 vite serve 被 rejectStandaloneServe 守卫拒绝是设计如此）；restart-with-build.sh
  纳入 apps/web 的 vite 暂存构建/换装/产物校验（含 --check 模式）
- 2026-09-20: profile 布局更新——`~/.dsh/profiles/investment/` 已删除，现役为项目内 profile（名 agent-dh，DSH_HOME=数据目录 `agent-dh/.dsh-data/`）；启动/停机统一走 `scripts/start.sh` / `scripts/stop.sh`；配置源 = `config/cordis.yml`，活动配置 = `.dsh-data/profiles/agent-dh/cordis.patch.yml`
- 2026-08-19: lifecycle 代码审查修复（50cb6084）：限流检查移到拿锁前（原拒绝路径泄漏锁致永久变砖）；重启器每次拉起前预写 restart-result（原时序竞争会让 rolled_back 误报成功）；锁 >15min stale 接管；状态读容错+原子写；self_finalize 幂等
- 2026-08-19: 修复 investment/market 插件 schema 缺 additionalProperties 导致的全量启动崩溃；新增 plugin-schema.smoke.test.ts 门禁（现位于 apps/web/tests/）；重写工具/插件开发样例为 defineTool + Service 模式并记录 Schema 铁律
- 2026-08-19: Added `@pi-investment/lifecycle` 自修复重启插件（RFC 002，E2E 验证通过）
- 2026-08-19: Removed legacy `apps/cli/`, clarified DSH profile architecture
- 2026-08-18: Initial DSH profile setup with 14 plugins (48 tools)
- 2026-08-18: Migrated from standalone CLI to DSH profile

---

**Status**: ✅ Active DSH profile（项目内 profile：agent-dh，:13080）

**Version**: 0.1.2

**Last Updated**: 2026-09-20

## 自主能力系统（2026-08-20 新增）

Agent-DH 现已具备**自我学习、知识蒸馏、持续进化**能力。

### 核心插件

#### @pi-investment/learning ✨ NEW
自我学习引擎：
- `learning_track` - 追踪经验（自动拦截工具调用）
- `learning_analyze` - 分析模式，生成改进建议
- `learning_distill` - 知识蒸馏（复杂推理 → 简单规则；2026-09-03 起蒸馏即落库 kind=rule/status=testing）
- `learning_apply` - 应用改进（2026-09-03 起真实语义：已蒸馏规则 testing→active 转正；dry_run 模拟、幂等、诚实失败；已下线不实的 self_restart 集成承诺）

**特性**：
- 自动追踪关键工具（portfolio_trade, strategy_execute 等）
- 计算奖励信号（盈亏/成功率/反馈）
- 持久化到 memory 系统
- 规则生命周期：distill 落库 testing → apply 转正 active（状态在记忆内容信封内，PATCH 重写推进）

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

同机运行多个 dsh 实例（主实例 :3080 / agent-dh :13080 / 其他 profile）时，停止实例必须**精确到实例**，历史上模糊停止曾误杀其他 agent：

1. **禁止 `pkill -f 'dsh web'` / `killall node`** 等模糊匹配——会命中所有 dsh 实例
2. **lsof 查端口必须带 `-sTCP:LISTEN`**——不带会把连着该端口页面的浏览器进程（Chrome Helper）也杀掉
3. **每个实例**：`start.sh` 写 `state/server.pid` + `state/server.port`；停止走 `stop.sh`（pidfile + 监听校验 + 端口兜底，防 PID 复用误杀）
4. self_restart 按 PID 精确停止，天然安全；手动停实例一律用该实例的 stop.sh
5. **:13080 归 launchd 管**（`com.pi-investment.dsh`，KeepAlive + RunAtLoad）：重启只能
   `launchctl kickstart -k`，停止只能 `launchctl bootout`。`kill` / `kill -9` 会被 launchd
   秒级拉起（ThrottleInterval 从"上次拉起"起算，对长跑实例等于立即重启），紧接着的手工
   `./start.sh` 必然 `EADDRINUSE`（2026-09-11 事故）。脚本已内置互斥：`start.sh` 遇托管
   端口会转交 kickstart，`stop.sh` 会走 bootout，手工执行是安全的

## Agent 身份系统（2026-08-21 起）

每个 agent 必须有**唯一 ID 和名字**，提高自我认知与协作可区分性：

- **注册表**：`agent-dh/.dsh-data/profiles/agent-dh/agents.json`（= profileDir/agents.json；instance + agents[]：id/name/role/primary/alias_of。注意 `.dsh-data/agents.json` 是旧副本，别读错）
- **提示词**：lifecycle 插件注册 `agent:identity` 段（order 5，宪法段之前），身份不进基因组、不参与进化
- **self_info**：identity 块来自注册表
- **经验署名**：learning 自动追踪的 context.agent 带 id/name/instance
- **通知署名**：feishu_notify/notification_send 外发消息自动带 `—— {name} ({id})` 署名
- 新分身加入时：在 agents.json 注册后再接入
