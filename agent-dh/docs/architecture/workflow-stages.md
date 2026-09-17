# 项目看板流程节点定义

**唯一事实源**：本文件是流程节点的权威定义。所有代码、文档、原型必须引用此定义。

## 流程节点（7态）

| 顺序 | 节点名称 | 英文标识 | 说明 | 下一阶段按钮文字 |
|------|---------|---------|------|-----------------|
| 1 | 立项 | draft | 需求立项，填写基本信息 | → 需求分析 |
| 2 | 需求分析 | brainstorming | 分析问题、探讨方案 | → 技术设计 |
| 3 | 技术设计 | planning | 编写技术方案、实施计划 | → 拆分 |
| 4 | 拆分 | decomposing | 拆解任务、建立DAG | → 实施 |
| 5 | 实施 | implementing | 执行任务、开发功能 | → 验收 |
| 6 | 验收 | accepting | 提交交付物、人工验收 | → 归档 |
| 7 | 归档 | archived | 归档文档、合并知识库 | - |

## 状态映射（后端兼容）

后端数据库可能使用的旧状态名：

| 后端状态 | 对应节点 | 说明 |
|---------|---------|------|
| draft | 立项 | - |
| brainstorming | 需求分析 | 旧名"头脑风暴" |
| planning | 技术设计 | 旧名"计划" |
| decomposing | 拆分 | - |
| implementing | 实施 | 旧名"执行" |
| accepting | 验收 | - |
| done | 归档 | 旧名"完成"（后端终态） |
| archived | 归档 | 后端新终态，优先使用 |

**前端显示规则**：
- 前端统一显示新节点名称（立项、需求分析、技术设计、拆分、实施、验收、归档）
- 后端返回 `done` 或 `archived` 都显示为"归档"
- 按钮文字格式：`→ [下一节点名称]`

## 进度点颜色（8态兼容）

详情页的8态进度点需要兼容"完成"态（done状态但未归档）：

| 节点 | 颜色 | 说明 |
|------|------|------|
| 立项 | #9aa4b2 | 灰色 |
| 需求分析 | #f0a020 | 橙色 |
| 技术设计 | #c2255c | 粉红 |
| 拆分 | #8e44ad | 紫色 |
| 实施 | #4a7dff | 蓝色 |
| 验收 | #17a2b8 | 青色 |
| 完成 | #28a745 | 绿色（过渡态，done但未archived） |
| 归档 | #28a745 | 绿色（最终态，已archived） |

## 泳道视图规则

- **显示6个泳道**：立项、需求分析、技术设计、拆分、实施、验收
- **不显示"归档"泳道**：已归档需求在"验收"泳道置灰显示
- **后端状态为 done 的需求**：显示在"验收"泳道，标记"等待归档"

## 引用规范

### 前端代码
```typescript
// ❌ 错误：硬编码节点名
const status = '头脑风暴';

// ✅ 正确：从常量导入
import { WORKFLOW_STAGES } from '@/constants/workflow';
const status = WORKFLOW_STAGES.BRAINSTORMING.label; // "需求分析"
```

### 后端代码
```python
# ❌ 错误：散落的状态定义
STATUS_CHOICES = [('draft', '立项'), ('brainstorming', '头脑风暴')]

# ✅ 正确：引用统一定义
from constants.workflow import WORKFLOW_STAGES
# WORKFLOW_STAGES = [
#   {'key': 'draft', 'label': '立项', 'next_label': '需求分析'},
#   ...
# ]
```

### 原型/文档
```html
<!-- ❌ 错误：手写节点名 -->
<span>头脑风暴</span>

<!-- ✅ 正确：注释引用权威定义 -->
<!-- 流程节点定义见：docs/architecture/workflow-stages.md -->
<span>需求分析</span>
```

## 变更流程

修改流程节点定义时：

1. **先改本文件**（唯一事实源）
2. **更新常量文件**（前端 `workflow.ts` / 后端 `workflow.py`）
3. **更新所有引用**（代码、文档、原型）
4. **运行测试**（确保无遗漏）
5. **提交 PR**（附变更影响分析）

## 文件位置

- **本定义文件**：`docs/architecture/workflow-stages.md`
- **前端常量**：`packages/pages/dsh-pmboard/src/constants/workflow.ts`
- **后端常量**：`quantsys-v2/constants/workflow.py`（如有）

---

**创建时间**：2026-01-XX  
**最后更新**：2026-01-XX  
**维护者**：项目看板团队


---

## 工具面（2026-09-17 收敛后：13 → 9）

REQ-47939a 把 reqboard 的 13 个工具收敛为 9 个。**收敛只改入口数量**——每个入口的语义、拒绝条件、
错误码与消息文案与收敛前逐一对应。本节是**现行 API 面**的唯一描述；本文件与 RFC/work-logs 里
历史叙述中出现的旧工具名（`reqboard_plan_submit`/`reqboard_verify_submit` 等）是**当时的事实记录**，
按"history 只增不改"原则不予改写。

| 收敛后工具 | 覆盖原入口 |
|-----------|-----------|
| `reqboard_create` | create |
| `reqboard_status` | status |
| `reqboard_move` | move |
| `reqboard_decompose` | decompose |
| `reqboard_task_move` | task_move |
| `reqboard_task_report` | task_report |
| `reqboard_submit(kind=requirement\|plan\|verification\|archive)` | requirement_submit / plan_submit / verify_submit / archive_submit —— 壳合并，**内里仍是四个独立用例**，按 kind 表驱动分派（不是一个大 if；由 `tests/tools-dispatch.test.ts` 断言） |
| `reqboard_ask_confirm` | ask_confirm + confirm_artifact（弹框落章与文字证据落章合并为一条路） |
| `reqboard_accept_sheet` | accept_sheet（逐项弹框验收 + 断点续验 + 未过项自动返工） |

## 各阶段职责规范（REQ-2e9473 t18/W7 · 六要素）

> 每阶段六要素：**目标 / 入口 / 活动 / 产物 / 出口门 / 禁止事项**。
> 本规范是**流程语义**的事实源；其**提示词文本载体**自 REQ-422af1 起迁到分片库
> `packages/pages/dsh-pmboard/src/domain/prompt/`（唯一取词入口 `resolveStagePrompt()`，见下节
> 「提示词加载路由」）；旧的 `STAGE_PROMPTS` 直取路径已物理删除（双入口会绕过路由）。
> 修改流程语义时两处必须同步（代码是执行体，本文件是事实源）。

### 1 立项 draft
- **目标**：确认"这件事值得做"
- **入口**：识别到新工作
- **活动**：两问弹框（需求名称 + 类型）→ `reqboard_create`
- **产物**：REQ 台账卡片（sourceSessionId 落窗口）
- **出口门**：窗口接手即自动进需求分析（R1 派生推进，无人工门）
- **禁止**：谈方案、动代码

### 2 需求分析 brainstorming（superpowers 式方法论）
- **目标**：把"要什么"谈清楚（问题/约束/成功标准/边界）
- **入口**：立项确认后自动注入需求分析提示词（capture-hook 即时 + systemPrompt 每回合）
- **活动（九步检查表）**：①探索项目上下文 → ②范围评估先行（多子系统先拆）→ ③澄清提问（一次性一个问题，弹框）→ ④2-3 方案对比（带推荐）→ ⑤分节呈现设计（每节确认）→ ⑥写 requirement.md → ⑦文档自查（占位符/矛盾/模糊/蔓延）→ ⑧用户审阅（`reqboard_ask_confirm`）→ ⑨推进
- **产物**：requirement.md（过程产物落目录即自动登记，W4）
- **出口门**：人工门——需求文档确认（三通道：弹框/看板/核验后文字）
- **禁止**：写技术设计、写任务拆分；未经确认不得进入实现动作（HARD-GATE，代码级 artifact_not_confirmed）

### 3 技术设计 planning（代码层面的设计，产物是一套文档）
- **目标**：在代码层面回答"怎么做"
- **入口**：需求文档已确认
- **活动**：①数据层（是否改表/schema）②设计模式与框架选型（优先现成框架）③代码规范 ④UI/前端实现与样式 ⑤测试用例内容 ⑥提交前自查
- **产物**：**一套技术设计文档**（按主题分：design/architecture.md、design/ui.md、design/test-cases.md…）
- **出口门**：人工门——计划批准（`reqboard_ask_confirm` target=plan）
- **禁止**：工作流划分/工作量预估（属拆分）；写实现代码；**产出最终任务 DAG**（W7 边界：任务卡在拆分阶段创作）

### 4 拆分 decomposing（代码层面变更盘点 + 任务卡创作）
- **目标**：把技术设计转成可执行任务 DAG
- **入口**：计划已批准
- **活动**：①对照需求+技术设计盘点**新增/修改/删除**（接口/功能/文件，精确到模块）②工作流划分+工作量预估 ③任务卡四要素创作（做什么/怎么做[implementation]/可证伪验收标准/依赖）④`reqboard_decompose` 落库
- **产物**：decomposition.md + 任务卡（tasks/t-xxx.md，薄卡被代码级拒绝）
- **出口门**：人工门——拆分确认（`reqboard_ask_confirm` kind=decomposition；防"批了 A 落库 B"）
- **禁止**：薄卡落库；与技术设计矛盾时**退回技术设计改计划**，不二次创作

### 5 实施 implementing（文档驱动执行）
- **目标**：照卡执行并交付
- **入口**：拆分已确认
- **活动**：①开工先写 implementation.md（步骤/顺序/验证方式）②`task_move(in_progress)` 领任务卡全文 ③执行 ④`reqboard_task_report` 汇报（files_changed 自动上浮）⑤收尾生成验收文档
- **产物**：交付物 + 每任务完工记录 + implementation.md
- **出口门**：全部任务 done → **自动**进验收（R2 派生推进，无人工推）；done 有凭证门（汇报/真实动作/非批量/构建新鲜度）
- **禁止**：批量关任务、无凭证 done、范围蔓延（超实施卡声明文件 → 警告进验收单）

### 6 验收 accepting（逐项验收单 + 断点续验）
- **目标**：人对证据**逐项**裁决
- **入口**：全部任务 done 自动进入
- **活动**：①`reqboard_submit(kind=verification)` 生成逐项验收单（每任务验收标准+需求级标准，逐项带证据）②人逐项打勾（通过/不通过+意见；`reqboard_accept_sheet` 逐项弹框）③不通过项 → 打回 + 自动生成返工任务
- **产物**：版本化验收单（v1/v2…，历史进 sheetHistory）
- **出口门**：全过 → 人工门「验收通过」→ 直接归档；有未过 → 打回 implementing
- **禁止**：agent 自判通过；空话证据；编造证据路径（代码级校验）

### 7 归档 archived
- **目标**：知识沉淀进项目文档
- **入口**：验收通过（自动进入，无需人再点）
- **活动**：`reqboard_submit(kind=archive)` 补材料（目录/文档清单/合并去向/索引/说明书更新点）
- **产物**：归档材料 + merged_into **真实写入**对应项目文档
- **出口门**：材料齐（代码级必填项校验）
- **禁止**：只挪目录不合并内容；漏登目录内文件（返回 unlisted_files 警告）

---

**新增/更新**：2026-09-17（REQ-2e9473 t18/W7）；与 STAGE_PROMPTS + host 闸门同源。
2026-09-17（REQ-422af1 t12）：补「提示词加载路由」一节，并注明阶段提示词文本载体已从 STAGE_PROMPTS 迁到分片库。

---

## 提示词加载路由（REQ-422af1 · 2026-09-17 落地）

> 本节是"每个节点注入哪份提示词"的**现行事实源**。实现细节见
> [design/architecture.md](../requirements/REQ-422af1/design/architecture.md)（§4 回退链 / §7 门禁）与
> [design/fragments.md](../requirements/REQ-422af1/design/fragments.md)（§6 类型差异写法 / §8 预算 / §9 编写规范）；
> 拆分口径见 [decomposition.md](../requirements/REQ-422af1/decomposition.md)（§5 t7 口径 / §8 落地记录）。
> 代码在 `packages/pages/dsh-pmboard/src/domain/prompt/`，注入点只调唯一入口 `resolveStagePrompt()`。

### 1 语义：节点即选择器，不需要 skill 匹配

状态机已经决定"当前是哪个节点"，因此**不需要任何 skill 检索/匹配机制**——到哪个节点就注入
哪个节点的内容（**披露 = 按节点注入**：按节点分批、注入时按预算裁剪）。这对应"仪式强度"由
**难度**决定（同一节点两档），与节点身份无关：heavy 档直接采用 superpowers **原文**（vendor，
不改写），light 档为自写精简。附属 skill（TDD / subagent-driven-development / worktrees /
dispatching-parallel-agents / requesting+receiving-code-review / systematic-debugging /
writing-skills / using-superpowers）设计为挂在**节点内子步骤**上按需披露；本阶段**只落盘、尚未注册为分片**
（注册即需被路由或 include 命中，否则违反门禁 4"无孤岛"）。

### 2 路由键与 5 级回退链（难度优先于类型）

路由键 = `stage/difficulty/category`（示例 `brainstorming/heavy/feature`；未指定的维度写 `*`）：
**stage** ∈ 六节点（brainstorming / planning / decomposing / implementing / accepting / archived）；
**difficulty** ∈ `light` / `heavy`；**category** ∈ `feature` / `bug` / `doc` / `refactor` / `spike` / `chore`。

回退链按表顺序取**首个命中**层；**② 先于 ③ = 难度优先于类型**：

| 层 | 路由 | 含义 |
|---|------|------|
| ① | `(stage, difficulty, category)` | 精确命中 |
| ② | `(stage, difficulty, *)` | 该类型无专属 → 用**难度档** |
| ③ | `(stage, *, category)` | 该难度无专属 → 用**类型档** |
| ④ | `(stage, *, *)` | 该节点兜底档 |
| ⑤ | `(*, *, *)` | **全局铁律——恒并入（合并，不是替代）**，且永远排在 ①-④ 选中内容之后 |

①-④ 命中层级记 1-4，只有 ①-④ 全空才记 5。同 id 片段只注入一次（include 展开后去重）；
include 指向不存在的 id 时**响亮抛错**，不静默跳过。分片元数据契约（id/stage/difficulty/category/
priority/text/include）见 `docs/requirements/REQ-422af1/design/fragments.md` §1。

### 3 分片目录结构

    packages/pages/dsh-pmboard/src/domain/prompt/
      index.ts  router.ts  budget.ts  types.ts  chain.ts   唯一入口 + 回退解析 + 预算 + 类型 + 链声明
      fragments/brainstorming/light.md                    六节点轻档（自写；另有 planning|decomposing|implementing|accepting|archived）
      fragments/brainstorming/heavy.md                    六节点重档（5 节点 = vendor 原文逐字节镜像；decomposing 自写完整档）
      fragments/brainstorming/heavy/overrides.md          附加片段（floor；5 节点有，decomposing 无）
      fragments/common/iron-rules.md                      ⑤ 全局铁律（floor）
      vendor/superpowers/brainstorming/SKILL.md           superpowers 原文 14 份（逐字节，不改写）
      vendor/superpowers/ATTRIBUTION.md                   来源 / 版本 / 许可 / 抓取时点
      generated/fragments.ts                              构建期内联产物（运行时只读内存，不读盘）
    scripts/inline-prompt-fragments.mjs                   生成器（md → 内联 TS）
    scripts/check-prompt-fragments.mjs                    源/产物同步门禁

分片 **id = 路径去扩展名**（如 `brainstorming/heavy`、`brainstorming/heavy/overrides`、`common/iron-rules`）；
每个分片至少被一条路由命中（否则门禁 4 判孤岛）。作者态是 md、构建期内联为常量，两者由门禁 6 锁死。

### 4 vendor 来源（superpowers）

| 项 | 值 |
|---|---|
| 仓库 | `obra/superpowers`（`origin/main`） |
| commit / tag | `b36e0829c6d0140e93cfef2ca599b1b07d4a7797` = **v6.3.0** |
| 许可 | **MIT**（Copyright (c) 2025 Jesse Vincent），全文见 `packages/pages/dsh-pmboard/src/domain/prompt/vendor/superpowers/ATTRIBUTION.md` |
| 份数 | **14 份** `SKILL.md`（该仓 skills/ 全量） |
| 抓取时点 | **2026-09-17 22:42:44 CST**（`git show origin/main:<skill>/SKILL.md` 逐字节落盘，无改写） |
| heavy 主 skill 映射 | brainstorming→brainstorming；planning→writing-plans；implementing→executing-plans；accepting→verification-before-completion；archived→finishing-a-development-branch |
| 口径例外 | **decomposing 在 14 份里无对应 skill**（没有"拆分/任务 DAG/卡质量"内容）→ heavy 为**自写完整档**，不做"与原文逐字一致"断言 |

### 5 注入顺序与单次注入预算

单次注入顺序**固定三段**：

1. **vendor 原文**（heavy 主 skill 全文，**不裁**）或轻档自写内容；
2. **overrides 附加片段**（`priority=floor`，不可裁）——承载本仓口径：节点交棒行、落盘路径、
   **显式否掉 server/http 与浏览器本体**、把 skill 里的 create-a-task 映射到 reqboard 任务卡、闸门与节点归属；
3. **`packages/pages/dsh-pmboard/src/domain/prompt/fragments/common/iron-rules.md` 铁律**（floor，永不裁）。

**单次注入预算 `DEFAULT_PROMPT_BUDGET = 24000` 字符**（口径 = 字符数，token 的代理指标）。由来：
heavy 档**主 skill 全文不裁**（裁正文等于把 heavy 降回"要点版"），实测最大解析结果 **17,193 字符**
（`brainstorming/heavy/feature`，tsx 实测 2026-09-17），P0 期的 **8000** 装不下 → T7 上调为 **24000**
（= 实测上限 + 余量），并已回写 `docs/requirements/REQ-422af1/design/fragments.md` §8。裁剪只作用于非 floor 片段，按优先级从低到高裁；
**连保底（floor）都超预算时返回结构化 `overBudget`（reason=floor-exceeds-budget）而不静默裁保底**——
响亮失败优于静默降级。

### 6 六条门禁（`packages/pages/dsh-pmboard/tests/prompt-gates.test.ts`，每条都能变红）

| # | 门禁 | 判据 |
|---|------|------|
| 1 | 覆盖完整 | 6×2×6 全部解析非空（0 例空串）；⑤ 铁律层存在且每次解析都并入 |
| 2 | 工具名一致 | 注入文本里的 `reqboard_*` ⊆ 实际注册集合（∩ 上方「工具面」的 9 个入口） |
| 3 | 预算上限 | 默认预算下 charCount ≤ 24000；极小预算返回结构化 `overBudget` 而非静默裁保底 |
| 4 | 片段唯一 + 无孤岛 | 分片 id 不重复；每个分片至少被一条路由命中 |
| 5 | 链声明完整 | 每节点有「下一步：<next> —— 用 <tool>」声明，且 next ∈ 状态机合法后继（`packages/pages/dsh-pmboard/src/domain/prompt/chain.ts` 与分片文本一致） |
| 6 | 源/产物同步 | `packages/pages/dsh-pmboard/src/domain/prompt/fragments/**/*.md` 与 `packages/pages/dsh-pmboard/src/domain/prompt/generated/fragments.ts` 逐字节一致；每份 `packages/pages/dsh-pmboard/src/domain/prompt/fragments/<stage>/heavy.md` 与 vendor 原文逐字节一致 |

> `docs/requirements/REQ-422af1/design/architecture.md` §7 另列第 7 条「自足性」（节点产物含五字段头部），检查对象是**节点产物**
> 而非本取词链，由产物门禁承担；既有四条机械门禁（layer-boundary / size-budget / typecheck / message-hygiene）继续必须绿。

### 7 六节点两档实现状态（REQ-422af1 t7，2026-09-17 落地）

| 节点 | light | heavy | heavy 来源 | light 字符 | heavy 字符 |
|------|:----:|:----:|-----------|----------:|----------:|
| brainstorming | ✅ | ✅ | vendor brainstorming | 1,218 | 17,193 |
| planning | ✅ | ✅ | vendor writing-plans | 946 | 8,207 |
| decomposing | ✅ | ✅ | **自写完整档**（无对应 skill） | 855 | 1,641 |
| implementing | ✅ | ✅ | vendor executing-plans | 925 | 3,723 |
| accepting | ✅ | ✅ | vendor verification-before-completion | 922 | 4,701 |
| archived | ✅ | ✅ | vendor finishing-a-development-branch | 897 | 8,956 |

字符数 = `resolveStagePrompt({stage, difficulty})` 的 `charCount`（含 overrides + 铁律；tsx 实测 2026-09-17）。
分片记录共 **126 条** = 18 份源分片（6 light + 6 heavy + 5 overrides + 1 铁律，`category='*'`、`priority='floor'`）
+ **36 份类型档正文**（③ 层，六节点 × bug/refactor/feature/spike/doc/chore）+ **72 条 ① 层路由壳**
（`text=''` + `include=[节点档(, overrides), 类型档]`）。

因此：`(stage, difficulty, *)` 命中 ②（难度档）；`(stage, difficulty, category)` 命中 ① 并合成
**节点内容 + 类型差异 + ⑤ 铁律**；`(stage, *, category)` 命中 ③（类型兜底）。
类型档已于 **t8 落地**——本页初稿写"属 P2 尚未落地"是当时的中间状态，t12 复核时已按实际产物更正。
六节点 light(855-1,218) < heavy(1,641-17,193) 6/6。

### 8 注入点与本路由的关系

注入点只有两处，**都调 `resolveStagePrompt()`**（INV-1 单点化）：
`packages/pages/dsh-pmboard/src/application/internal/capture-section.ts`（每回合 systemPrompt 组装）
与 `packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts`（状态转移后即时注入）；
`STAGE_PROMPTS` / `stagePromptFor` 直取写法已**物理删除**（双入口会绕过路由），
现仅保留键类型与常量（`packages/pages/dsh-pmboard/src/domain/stage/StagePromptSpec.ts`）。
每次注入按十字段留痕到**运行时文件** `<dshHome>/state/prompt-injection-log.json`（ring buffer 保留最近 500 条、
原子写；该文件运行时生成，不在仓库内）：`at / windowKey / stage / difficulty / category / routeKey / hitLevel / fragmentIds / charCount / trimmed`，
让"这次到底注入了什么"可被人核查。

---

