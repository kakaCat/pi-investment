# 三 Agent 领域拆分 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 单通用 agent 拆为金融/进化/记忆三领域 Agent，提示词、工具、记忆三层硬隔离，对用户仍是统一系统。

**Architecture:** 工具注册表分组（编译期常量）+ RoleProfile 声明 + 会话工厂按 agentKind 装配（工具过滤/提示词变体/模型档位）；协作走共享 PG + 记忆库，无消息总线。

**Tech Stack:** agent-ts (TypeScript/jest ESM)

**Spec:** `docs/superpowers/specs/2026-08-13-agent-domain-split.md`

---

**全局执行顺序与并行图：[`2026-08-13-execution-order.md`](./2026-08-13-execution-order.md)**（双泳道：k3 + 单一执行模型；波次推进）

---

## 多模型执行使用说明

与召回计划同一套用法：复制【通用执行规则】+ 任务全文 → 新会话执行模型 → 报告 → Claude 验收。

### 【通用执行规则】（每个提示词开头必附，逐字复制）

````
你在 /Users/yunpeng/pi-investment monorepo 工作。规则（违反=返工）：
1. 必须先建独立 worktree 再改代码：
   git worktree add .claude/worktrees/<任务编号> -b feat/<任务编号>
   cd 进去后立刻 git rebase main。禁止在主工作区直接改代码。
   agent-ts 测试前：ln -s /Users/yunpeng/pi-investment/agent-ts/node_modules agent-ts/node_modules
2. 只准创建/修改本任务【Files】列出的文件。发现必须改其他文件 → 停下来在报告里说明，不许自作主张。
3. 接口/字段名/常量名与本任务契约逐字一致。不许自创字段、不许"顺手改进"契约、不许重构无关代码。
4. 测试命令：cd agent-ts && npm test -- <pattern>（裸 npx jest 会误报 TS1378，禁止）。
5. 涉及现有代码的断言，先读文件验证再写。禁止凭印象描述代码行为。
6. 验收命令必须真跑，报告里贴完整输出。跑不过就停下来报告，不许跳过。
7. 完成后报告格式：分支名 / 改动文件清单 / 每条验收命令的输出 / 与契约的偏差（没有就写"无"）。
8. 不要执行 git push、不要合并回 main——验收由 Claude 做。
````

### 【Claude 验收规程】

对契约逐字核对 → 亲自跑验收命令 → 回查事实源 → merge-back 合并或打回。A0-T1 额外：逐组审查工具归类（分组错=后面全错）。

---

## 标记约定

**执行者标记**（每个任务标题内）：
- `【k3】` = Claude 亲做（架构判断/跨层契约类，不委派）
- `【执行模型】` = 可委派其他模型执行（k3 按验收规程终审后合并）

**状态标记**（任务标题末尾，执行过程中更新）：
- `⬜` 未开始 ｜ `🔄` 进行中 ｜ `👀` 待 k3 验收 ｜ `✅` 验收通过已合并 ｜ `❌` 打回（附原因）

## 任务总览

| 任务 | 执行者 | 状态 | 依赖 |
|---|---|---|---|
| A0-T1 工具注册表分组 | 执行模型 | ✅ | 无 |
| A0-T2 RoleProfile 声明 | 执行模型 | ✅ | 无 |
| A0-T3 会话工厂装配（总闸门） | **k3** | ✅ a84b949 | A0-T1 + A0-T2 |
| A1-T1 recall_audit 工具+记忆 Agent | 执行模型 | ✅ d871ac5（+修复 0a95bed） | 召回 P1-T4 + A0-T3 |
| A1-T2 每日召回审计任务 | 执行模型 | ⬜ | A1-T1（prompt 文案 k3 审） |
| A2-T1 进化提示词+skill 读写工具 | 执行模型 | ✅ bed1b79（+修复 6023338） | A0-T3（提示词文案 k3 审） |
| A2-T2 weekly_evolution 迁移 | **k3** | ✅ ee4c26e（干跑审计记录实证） | A2-T1 |
| A3-T1 渠道 Channel 层微调 | 执行模型+k3修复 | ✅ a542e4a（r2：k3 亲修兼容+接线） | A0-T3 |

---

## 并行执行图

```
轨道A (其他模型): A0-T1（工具分组）──┐
轨道B (其他模型): A0-T2（profiles）──┼→ A0-T3（Claude 会话工厂）→ A1/A2/A3
轨道C (其他模型): A1-T1（记忆Agent）── 依赖：召回计划 P1-T4 已合并 + A0-T3
轨道D (其他模型): A2-T1（进化提示词+skill工具）── 依赖：A0-T3
轨道E (Claude):   A2-T2（weekly_evolution 迁移）── 依赖：A2-T1
轨道F (其他模型): A3-T1（渠道微调）── 依赖：A0-T3

A ∥ B 可并行（文件不相交）。A0-T3 是总闸门。
本计划与召回计划可整体并行（唯一依赖：A1-T1 需要召回 P1-T4 的 API）。
```

---

## A0：地基

### A0-T1：工具注册表分组【执行模型｜轨道A｜✅ cb16423】

**Files:**
- Create: `agent-ts/src/infrastructure/tools/groups.ts`
- Modify: `agent-ts/src/infrastructure/tools/index.ts`（仅追加 export，不重排现有数组）
- Test: `agent-ts/src/infrastructure/tools/groups.test.ts`

**契约（逐字）：**

```typescript
// groups.ts
import { allCustomTools } from './index.js';

/** 共享基础组：所有 agent 都可用 */
export const SHARED_BASE_TOOLS = [ /* 任务/计划/记忆读写等，见归类规则 */ ] as const;
/** 金融 Agent 工具组（执行主体） */
export const FIN_TOOLS = [ /* ... */ ] as const;
/** 进化 Agent 工具组 */
export const EVOLUTION_TOOLS = [ /* ... */ ] as const;
/** 记忆 Agent 工具组 */
export const MEMORY_TOOLS = [ /* ... */ ] as const;
```

**归类规则**（按工具名逐一对号入座；拿不准的放 FIN_TOOLS 并在报告里列出"存疑清单"，不许自创第五组）：
- `MEMORY_TOOLS`：`memory_search`、`memory_write`、`memory_manage`（若存在，以 index.ts 实际名为准）
- `EVOLUTION_TOOLS`：`evolution` 前缀全部 + `fitness`/` leaderboard` 类（以实际名称为准）+ `claude_code`
- `SHARED_BASE_TOOLS`：任务/计划类（`plan_task`、`task_*`）、`restart_agent`、`scheduler_manage`、`model_switch`
- `FIN_TOOLS`：其余全部（数据/交易/分析/池/风控/盯盘…默认归属）

**等价性测试（groups.test.ts，必须包含）：**

```typescript
import { allCustomTools } from './index.js';
import { SHARED_BASE_TOOLS, FIN_TOOLS, EVOLUTION_TOOLS, MEMORY_TOOLS } from './groups.js';

test('四组无交集且并集等于 allCustomTools', () => {
  const groups = [SHARED_BASE_TOOLS, FIN_TOOLS, EVOLUTION_TOOLS, MEMORY_TOOLS];
  const names = groups.flatMap(g => g.map((t: any) => t.name));
  expect(new Set(names).size).toBe(names.length); // 无重复
  expect(new Set(names)).toEqual(new Set(allCustomTools.map((t: any) => t.name))); // 全覆盖
});
```

- [ ] **Step 1:** 先读 `index.ts` 的 `allCustomTools` 全部工具名，列出归类草稿（报告附草稿）。
- [ ] **Step 2:** 写等价性测试 → `npm test -- groups` 确认失败（groups.ts 不存在）。
- [ ] **Step 3:** 实现 groups.ts（import 工具对象进组，不是复制定义）。
- [ ] **Step 4:** `npm test -- groups` 过 + `npm test -- tools` 回归过。
- [ ] **Step 5:** Commit：`refactor(tools): allCustomTools 四组拆分（FIN/EVOLUTION/MEMORY/SHARED），等价性测试锁定`。

---

### A0-T2：RoleProfile 声明【执行模型｜轨道B｜✅ fa4a057】

**Files:**
- Create: `agent-ts/src/domain/agent-roles/types.ts`
- Create: `agent-ts/src/domain/agent-roles/profiles.ts`
- Test: `agent-ts/src/domain/agent-roles/profiles.test.ts`

**契约（逐字）：**

```typescript
// types.ts
export type AgentKind = 'fin' | 'evolution' | 'memory';
export type ModelPreference = 'flash' | 'pro' | 'inherit';

export interface RoleProfile {
  kind: AgentKind;
  promptVariant: string;          // 提示词变体标识（A0-T3 使用）
  toolGroup: 'FIN' | 'EVOLUTION' | 'MEMORY';  // 对应 groups.ts 组名；SHARED_BASE 恒有
  modelPreference: ModelPreference;
  memoryWriteScopes: string[];    // 可写的记忆 scope 前缀
}
```

```typescript
// profiles.ts
import type { AgentKind, RoleProfile } from './types.js';

export const ROLE_PROFILES: Record<AgentKind, RoleProfile> = {
  fin: {
    kind: 'fin',
    promptVariant: 'fin',
    toolGroup: 'FIN',
    modelPreference: 'inherit',
    memoryWriteScopes: ['daily', 'experience', 'watch', 'portfolio', 'global'],
  },
  evolution: {
    kind: 'evolution',
    promptVariant: 'evolution',
    toolGroup: 'EVOLUTION',
    modelPreference: 'pro',
    memoryWriteScopes: ['evolution'],
  },
  memory: {
    kind: 'memory',
    promptVariant: 'memory',
    toolGroup: 'MEMORY',
    modelPreference: 'flash',
    memoryWriteScopes: ['memory', 'recall-audit'],
  },
};

export function getProfile(kind: AgentKind): RoleProfile {
  const p = ROLE_PROFILES[kind];
  if (!p) throw new Error(`unknown agent kind: ${kind}`);
  return p;
}
```

- [ ] **Step 1:** 测试：三种 kind 各断言 toolGroup/modelPreference；`getProfile('fin')` 不抛；非法 kind 抛错。
- [ ] **Step 2:** `npm test -- agent-roles` 确认失败 → 实现 → 全过。
- [ ] **Step 3:** Commit：`feat(agent-roles): 三 Agent RoleProfile 声明（工具组/模型/记忆scope）`。

---

### A0-T3：会话工厂 agentKind 装配【k3｜总闸门｜✅ a84b949】

**Files:**
- Modify: `agent-ts/src/infrastructure/session/session-factory.ts`（或 createSession 所在文件，实施时定位）
- Modify: `agent-ts/src/core/agent/system-prompt.ts`（builder 加 agentKind，变体机制）
- Test: 新增 `agent-ts/src/domain/agent-roles/assembly.test.ts`

**契约：**
- `createSession({ agentKind = 'fin' })`：按 profile 过滤工具（SHARED_BASE + 对应组）+ 提示词变体 + 模型档位（经 services/llm 会话级，**不动全局 llm-state.json**）。
- **fin 等价性铁律**：`agentKind:'fin'`（默认）的会话工具列表、系统提示词与现状**逐字节一致**——assembly.test.ts 用快照/逐项 diff 锁定。
- 结构性测试：`agentKind:'memory'` 会话工具列表不含任何 `trade_*`/`pool_manage` 写工具名。
- [ ] 验收：上述测试 + `npm test` 全量（对照基线）。

---

## A1：记忆 Agent【轨道C，依赖召回计划 P1-T4 + A0-T3】

### A1-T1：`recall_audit` 工具 + 记忆 Agent 会话接入【执行模型｜轨道C｜✅ d871ac5（+修复 0a95bed）】

**Files:**
- Create: `agent-ts/src/infrastructure/tools/memory/recall-audit-tool.ts`
- Modify: `agent-ts/src/infrastructure/tools/index.ts` + `groups.ts`（新工具归 MEMORY_TOOLS）
- Create: `agent-ts/src/prompts/memory-agent.md`（或提示词变体所在约定位置，实施时与 A0-T3 对齐）
- Test: `agent-ts/src/infrastructure/tools/memory/recall-audit-tool.test.ts`

**契约：**
- 工具名 `recall_audit`，参数 `{action: 'list'|'stats'|'feedback', ...}`：
  - `list`：GET `/api/memory/recall-audit`（透传筛选参数）
  - `stats`：GET `/api/memory/recall-audit/stats`
  - `feedback`：POST `/{id}/feedback`，body `{memory_id, feedback, feedback_by:'agent'}`（**agent 标注硬编码 feedback_by='agent'**）
- mock 模式参照现有 quant 工具测试（unstable_mockModule runQuantV2 或 fetch mock，以该工具实际 HTTP 层为准——实施时读 `quant-v2-client.ts` 决定走 runQuantV2 还是 fetch，报告说明选择）。
- [ ] 验收：三 action 测试全过 + `npm test -- groups` 等价性仍过（新工具已归组）。

### A1-T2：每日召回审计任务注册【执行模型｜轨道C｜⬜｜依赖 A1-T1，prompt 文案 k3 审】

**Files:** Modify `agent-ts/src/services/scheduler/init-agent-tasks.ts`
- [ ] 新增任务 `daily_recall_audit`（cron `0 19 * * *`，agentKind='memory'，prompt 含完整工作流：拉 stats→逐条初标→低置信标 needs_review→写日报到记忆 evolution/memory scope）。prompt 文案 Claude 审。
- [ ] 验收：`scheduler_manage` list 含新任务；手动 trigger 一次，PG 审计表出现 `feedback_by='agent'` 的记录（需已有审计数据，否则干跑验证 prompt 到达）。

---

## A2：进化 Agent

### A2-T1：进化提示词 + skill 读写工具【执行模型｜轨道D｜✅ bed1b79】

**Files:**
- Create: `agent-ts/src/prompts/evolution-agent.md`
- Create: `agent-ts/src/infrastructure/tools/evolution/skill-file-tool.ts`（读/改 `skills/*.md`，改动前自动 git worktree + 改后跑 `npm run check:tool-refs`）
- Modify: `groups.ts` + `index.ts`（归 EVOLUTION_TOOLS）
- Test: 对应测试

**提示词必须包含的纪律条款（Claude 审文案）：** ① 代码改动必须 worktree；② 测试先行；③ autoExecute 默认关，只提方案不自动执行；④ skill 可直改但改后必跑 check:tool-refs；⑤ 禁止改交易规则参数（双轨契约：agent_virtual vs advisory 不互相统一）。
- [ ] 验收：提示词含五条款（Claude 逐条核）；skill-file 工具测试过（含 worktree 创建失败时的报错路径）。

### A2-T2：weekly_evolution 迁移 + 提案-评审接线【k3｜轨道E｜✅ ee4c26e】
- [ ] `weekly_evolution`（周日 20:00）改 agentKind='evolution'；产出写 evolution 域记忆；**不自动执行任何变更**——产出为提案，人工/Claude 评审后落地。
- [ ] 验收：周日任务干跑一次，evolution 域有提案记录，代码库零改动。

---

## A3：金融 Agent 渠道微调【轨道F，依赖 A0-T3】

### A3-T1：Channel 层按渠道差异化【执行模型｜轨道F｜✅ a542e4a（r2 k3 亲修）】

**Files:** Modify `agent-ts/src/services/intelligence/system-prompt-builder.ts`（仅 Channel 层组装处）+ 测试
- [ ] 契约：Channel 层只改语气/格式（飞书：简短、无表格；TUI：完整；web：markdown 完整），**禁止放业务规则**。
- [ ] 验收：三渠道提示词快照 diff 仅 Channel 段不同（测试锁定）。

---

## Self-Review 记录

- Spec 覆盖：§3.1 工具隔离→A0-T1/T3；§3.2 提示词→A0-T3/A2-T1/A3-T1；§3.3 记忆隔离→A0-T2（scope 声明）+ A1-T1（工具层校验留待 A1 实施时评估，若 memory 工具需感知 agentKind 则作为 A1-T1 子步骤，报告说明）；§4 协作→A2-T2；角色清单→A0-T2。
- 已知留白（有意）：记忆 scope 写权限的工具层强制点在 A1-T1 实施时定（依赖 A0-T3 的会话形态），已标注。
- 类型一致性：AgentKind/RoleProfile/toolGroup 名贯穿 T2/T3/A1。
