# Agent-TS → Agent-DH 能力迁移设计（能力重定位方案）

**版本**: 1.0.0
**日期**: 2026-08-18
**状态**: 待评审
**前置文档**: [2026-08-18-agent-dh-architecture-design.md](2026-08-18-agent-dh-architecture-design.md)、[2026-08-18-agent-dh-implementation-plan.md](../plans/2026-08-18-agent-dh-implementation-plan.md)

---

## 0. 本文档的定位

旧实施计划的 Phase 6（"每周照搬 15-20 个工具，共 110 个"）是**同构搬运思路**，本文档推翻该思路，给出**能力重定位（re-homing）方案**：agent-ts 的每一项能力，先问"它在 agent-dh 架构中的正确归属层是哪"，再决定迁移方式。

**两个基本事实**（2026-08-18 实地核查）：

1. **跨 SDK 换平台**：agent-ts 建在 `@mariozechner/pi-coding-agent` SDK 家族（pi-agent-core/pi-ai/pi-tui v0.73.1），工具为 TypeBox schema + `execute(toolCallId, params, signal, onUpdate, ctx)`；agent-dh 建在 DSH 上（cordis 插件 + `defineTool` + ToolRegistry）。工具外壳必须重写，但 agent-ts 的 `sdk-facade` 隔离模式使业务内核（API 调用、validators、formatters）可完整提起。
2. **agent-ts 约 25,450 行工具代码中大部分是"框架轮子"**：最大的工具是自我管护类（`backend-control` 860 行、`scheduler_manage` 533、`restart_agent` 411、`claude_code` 369），加上进程内 compaction 服务、大结果落盘、内存调度器、8 层 prompt 组装器、subagent/plan 服务——DSH 与 agent-os 已原生提供这些能力，**正确做法是删除而非迁移**。

---

## 1. 能力重定位总表

### A. 删除：DSH 原生替代

| agent-ts 现有能力 | DSH 原生替代 | 说明 |
|---|---|---|
| agent loop / session 管理 | `dsh-agent` + `dsh-agent-loop` + `dsh-session` | InvestmentAgentLoop 只保留 Registry 注册/心跳薄集成 |
| 会话持久化 | `dsh-session-persistence-jsonl` + `dsh-session-query-sqlite` | 事件溯源 |
| compaction 服务（src/services/compaction 整个目录） | `dsh-compaction` + `dsh-compaction-basic` + `dsh-compaction-tool-result-pruner` | 删除自研实现 |
| 大结果落盘 tool-response-handler | `dsh-spill` + `dsh-spill-local` | 框架级"超限落盘+定位符"，工具零改造 |
| 8 层 system prompt builder | `dsh-system-prompt` 注册表 + `dsh-persona` | Identity/Soul → persona；Memory/Runtime/Channel → 自定义 section provider |
| subagent / plan 服务 | `dsh-subagent*` / `dsh-workflow` / `dsh-goal` | 原生后台子代理、fork、编排 |
| LLM port/adapter + 重试 | `dsh-llm-deepseek` + `dsh-llm-retry` | model_switch 工具 → dsh 模型选择配置 |
| 工具权限/审批 | `dsh-permission-presets` + ToolRegistry guards + `dsh-user-approval` | agent-ts 缺权限层，属白捡升级 |

### B. 下沉：交给 agent-os 服务

| agent-ts 现有能力 | 去向 | 依据 |
|---|---|---|
| 内存调度器 + 4 个 cron 任务 | agent-os Scheduler（cron+DAG+webhook 唤醒，已建成） | 内存调度器是技术债（重启丢任务）；agent-dh 内部仅用 `dsh-schedule` 做会话级提醒 |
| 记忆/回忆服务（memory/recall） | agent-os Memory（向量+BM25） | agent-ts 已有 `agent-os-provider.ts`，方向已验证，迁移 = provider 变唯一路径 |
| 决策审计 + ExperienceAccumulator 存储 | agent-os Decision system | 决策记录本就是 agent-os 职责 |
| 飞书通知 | agent-os Notification（WP-6 飞书 driver 已完成） | 通知是平台能力 |
| 技能共享 | agent-os Skill Hub（WP-14） | 技能跨 agent 复用 |

### C. Re-wrap：业务工具进 agent-dh 插件包（保留内核，换外壳，做收敛）

**收敛关键**：利用 DSH code-mode——`dsh-tools` 的 `renderToolsSdk` 可把 typed client 渲染成 SDK，模型经 `run_code` 写代码调用（runtime: `dsh-code-runtime-worker-thread`）。110 个工具按三类分流：

| 类别 | 占比(估) | 典型 | 迁移方式 |
|---|---|---|---|
| ① 薄 API 转发（无逻辑） | ~60% | data_fetch_dividend/macro/north_flow、indicator CRUD、model_list | **不做工具**；补齐 quantsys-v2-client 后渲染成 SDK 暴露给 code-mode |
| ② 含领域逻辑 | ~30% | data_fetch_quote（交易时段/多源 fallback）、kline、pool_manage、portfolio_trade | `defineTool` re-wrap：validators/formatters/业务规则原样保留 |
| ③ 含决策智能 | ~10% | opportunity_scan(527行)、factor_attribution(462)、barra(433)、strategy_discovery(411)、pool_battlefield、opponent_behavior | **重点迁移**：决策上下文（why/suggested action/game context）随逻辑一起搬 |

插件包划分：`plugin-data` / `plugin-strategy` / `plugin-pool` / `plugin-portfolio` / `plugin-analysis` / `plugin-risk` / `plugin-intelligence`（博弈类）/ `plugin-quantsys-sdk`（code-mode SDK 提供者）。

**净效果**：工具数 110 → 约 30 个真工具 + 1 个 SDK。system prompt 工具体积大幅缩小，新增 quantsys API 不再需要写工具。

### D. 搬运：prompt/技能资产（格式适配）

- 10 个 `skills/*.md` → `agent-dh/skills/`，frontmatter 适配 `dsh-skill` 格式
- 4 个定时任务 prompt 模板 → agent-os 任务定义
- Identity/Soul 文案 → `dsh-persona` 配置

### E. 淘汰（明确不迁移）

`backend_control`（改 ops 脚本）、`restart_agent`（进程 supervisor）、`claude_code`（dsh-subagent 取代）、CLI adapters（已禁用）、`InMemorySchedulerStore`、pi SDK 适配层、`model_switch` 工具（变配置）。

---

## 2. 工具定义外壳对照（Re-wrap 规范）

**agent-ts（PiToolDefinition + TypeBox）**：

```typescript
export const dataFetchQuoteTool: ToolDefinition = {
  name: "data_fetch_quote",
  description: "获取股票实时行情...",
  parameters: Type.Object({
    symbol: Type.String({ description: "A股6位数字（如 600519）" }),
    source: Type.Optional(Type.Union([...])),
  }),
  execute: async (_toolCallId, params) => { /* 业务内核：保留 */ },
};
```

**agent-dh（defineTool + ValueSchemaSpec）**：

```typescript
import { defineTool } from '@deepseek-ai/dsh-tools';

export const quoteTool = defineTool({
  name: 'data_fetch_quote',
  description: '获取股票实时行情...',
  parameters: {
    symbol: { type: 'string', description: 'A股6位数字（如 600519）', required: true },
    source: { type: 'string', enum: ['realtime', 'db', 'auto'], description: '...' },
  },
  output: {
    schema: { type: 'object', properties: { /* ... */ }, additionalProperties: true },
    render: (args, value) => [{ type: 'text', text: formatForModel(value) }],
  },
  timeoutMs: 10000,
  execute: async (args, exec) => { /* 同一个业务内核，参数从 args 取 */ },
});
```

要点：
- `output: { schema, render }` **强制**（register 时校验，缺了抛 TypeError）
- object schema 必须显式 `additionalProperties`
- `execute(args, exec)` 的 args 已按 schema 验证且有类型推导
- 业务内核（QuantV2Client 调用、detectMarket、isTradingTime、formatters）从 agent-ts 原样提起
- 大结果不再需要 handleToolResponse 包装——dsh-spill 在框架层处理

---

## 3. 迁移路线（替换旧计划 Phase 6/7）

| 阶段 | 内容 | 工期 | 验收 |
|---|---|---|---|
| **M0 前置修复** | ① 修 agent-os P2 Go Registry（编译/接路由/测试）；② quantsys-v2-client 补齐 agent-ts 实际使用的 API 面；③ code-mode spike（run_code 调 SDK 跑通真实查询） | 1-2 周 | Go build+测试过、client 覆盖清单达标、spike 报告 |
| **M1 骨架接通** | CLI 接真 dsh-agent-loop + session 持久化 + compaction + spill + 8 层 prompt 映射 + 10 个技能文件 | 1-2 周 | CLI 真实对话可用、会话可恢复、技能可调用 |
| **M2 工具收敛迁移** | ②③ 类按域 re-wrap + plugin-quantsys-sdk 渲染 ① 类；每域 vitest + register smoke 测试 | 2-3 周 | 约 30 工具 + SDK 全部通过测试 |
| **M3 自主性下沉** | agent-os 调度接入（4 cron 任务+webhook 唤醒）、记忆/决策审计切 agent-os、飞书通知走 agent-os | 1-2 周 | 定时任务端到端跑通 |
| **M4 双轨与切换** | 与 agent-ts 并行同任务对比、灰度切换、淘汰 E 类 | 1-2 周 | 结果一致性达标、agent-ts 下线 |

**总计 6-9 周**（旧 Phase 6+7 为 8 周），删除约 1/3 代码迁移量。

## 4. 前置事实核查记录（M0 输入）

- **agent-os Registry 坏点**（2026-08-18 核查）：`internal/handlers/registry_handler.go`、`internal/repository/postgres_agent_repository.go`、`internal/service/{registry_service,task_router,load_balancer,health_checker}.go` 使用错误 module 路径（`github.com/yourusername/agent-os`，应为 `github.com/pi-investment/agent-os`）、未声明依赖（gin、sqlx，项目实际用 gorilla/mux + database/sql）。路由未接入 `internal/api/http_server.go`（现有模式：handler 实现 `RegisterRoutes(api)`，在 `NewHTTPServer` 中挂载 mux.Router）。
- **quantsys-v2 API 面**：约 451 个 route 装饰器、60+ 路由模块（`quantsys-v2/adapters/inbound/api/routes/`）。补齐范围**不是全量 451**，而是 agent-ts `QuantV2Client`（`agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`）实际调用的端点清单。
- **DSH code-mode 已验证存在**：`dsh-tools` 导出 `renderToolsSdk` / `jsonSchemaToTs`；`RUN_CODE_NAME = "run_code"`；code-mode 需要 code runtime（`dsh-code-runtime-worker-thread` 已发布）；ToolRegistry `register()` 强制校验 `output {schema, render}`。
- **DSH 调度**：`dsh-schedule`（"Agent-scoped durable after, at, and fixed-rate reminders over the session event log"）负责会话内提醒；cron 级调度归 agent-os。

## 5. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| code-mode 不可靠（模型写代码调 SDK 失败率高） | ① 类收敛方案失效 | M0 spike 先验证；失败则退回"薄工具也逐个 defineTool"（+2 周） |
| P2 Registry 修复牵扯面大 | M3 阻塞 | M0 第一项任务，独立可验收 |
| ③ 类工具决策上下文丢失 | 系统智能退化 | 每工具迁移附"决策上下文对照清单"（输入/输出/why/suggested action 逐项比对） |
| 双轨期 quantsys API 漂移 | agent-dh client 失真 | client 生成/半生成；`npm run check:tool-refs` 类 sanity check 引入 agent-dh |

## 6. 与旧计划的关系

- 旧 Phase 1-3：已完成（P2 后端部分按 M0-① 返工）
- 旧 Phase 4（工具插件）：按本文档 C 类方案调整范围后执行（9 个工具均属②类，可直接开工）
- 旧 Phase 5（Worker）：并入 M3（调度下沉方案）
- 旧 Phase 6（110 工具照搬）：**废止**，按 M2 执行
- 旧 Phase 7（生产切换）：并入 M4

---

## 变更历史

| 日期 | 变更 |
|---|---|
| 2026-08-18 | 初版：能力重定位方案，废止旧 Phase 6 照搬思路 |
