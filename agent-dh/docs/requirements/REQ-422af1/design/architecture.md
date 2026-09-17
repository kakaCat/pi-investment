# REQ-422af1 技术设计 · 架构（提示词加载路由 + 同窗口节点隔离）

> 阶段：planning · 窗口 w-41e7e4cd · 上游：requirement.md（§1-§5 已确认）

## 1. 设计目标（与需求不变量对齐）

| 需求 | 设计落点 |
|------|---------|
| G1 路由唯一入口 | `resolveStagePrompt()` —— 注入点只此一处（INV-1） |
| G2 每节点≥2 档 + 按类型分化 | 分片按 (stage, difficulty, category) 组织，回退链解析（INV-2） |
| G3 串成链 | 每节点分片必含「下一步」声明，门禁校验（INV-4） |
| G4 省 token | 注入预算 + 保底优先级（INV-3）；编写不限、注入有闸 |
| G5 可审计 | 注入留痕（routeKey/命中层级/片段 id/字符数）（INV-6） |
| G6 上下文可丢弃 | 节点输入包自足（INV-8） |
| G7 同窗口遗弃上下文 | surface 整段替换（§5 执行模型） |
| 工具名一致 | 注入文本里的 reqboard_* ∈ 注册集合（INV-5） |

## 2. 数据层：是否改表 / 改 schema

**结论：不动台账 schema（保持 schemaVersion=5），不新增表。** 理由：本需求是"取词 + 注入 + 上下文管理"，产物是提示词分片，不是业务记录。

唯一新增的持久物 = **注入留痕**（INV-6 要求可查）。落点取舍：

| 方案 | 取舍 |
|------|------|
| 写入台账 dsh-reqboard.json | 否——会让"提示词路由"耦合业务台账版本，且高频写入放大文件 |
| **落 state 目录的 ring buffer 文件（`prompt-injection-log.json`，保留最近 N=500 条）** | **采用**——与台账解耦、容量有界、可 cat/grep 直接查 |
| 只写 console | 否——不可查历史，等于没有审计 |

ring buffer 每条记录：`{ at, windowKey, stage, difficulty, category, routeKey, hitLevel, fragmentIds[], charCount, budgetTrimmed[] }`。

## 3. 模块与目录

    packages/pages/dsh-pmboard/src/domain/prompt/
      index.ts                 对外唯一入口 resolveStagePrompt()，重导出类型
      router.ts                回退链解析 + 去重 + 调用 budget 裁剪 + 生成留痕
      budget.ts                注入预算与保底优先级（保底：清单/闸门/红旗）
      types.ts                 StagePromptRequest / ResolvedPrompt / Fragment / FragmentMeta
      fragments/               分片源（人工编写，见 design/fragments.md）
        common/…               全局铁律、红旗表、清单纪律
        brainstorming/ planning/ decomposing/ implementing/ accepting/ archived/
          {light,heavy}.md                        每个节点两档（六个节点全都有）
          {bug,refactor,feature,spike,doc,chore}.md 类型档（P2 覆盖全部节点）
      vendor/superpowers/<skill>/SKILL.md       superpowers 原文（v6.3.0 / b36e082 / MIT）
      vendor/superpowers/ATTRIBUTION.md         来源、版本、许可、抓取时点
      generated/fragments.ts   构建期把 fragments/**.md 内联为常量（不入库、由脚本生成）
    scripts/inline-prompt-fragments.mjs   生成器（读 md → 写 generated）
    scripts/check-prompt-fragments.mjs    一致性门禁（源改了没重建即红）

**为什么 md 作者态 + 构建期内联**：这批文本要长期人工打磨（人和 agent 都要读写），md 优于 TS 模板串；而"确定性注入"要求编译进产物、不许运行时读盘（本仓有过"读盘失败静默降级"的事故）。两者用"生成 + 门禁"连接。

**分层（沿用 REQ-47939a 四层，机械门禁 tests/layer-boundary.test.ts 必须继续绿）**：domain/prompt 是纯函数（无 I/O、无 node:、无 Date.now）；读盘只出现在 scripts/（构建期）；注入点仍在 application/adapters 既有位置。

## 4. 解析算法与契约

    resolveStagePrompt(req: StagePromptRequest): ResolvedPrompt
      req  = { stage, difficulty, category, budget?: number }
      返回 { text, fragmentIds, routeKey, hitLevel, charCount, trimmed }

回退链（INV-2，难度优先于类型）：

    ① (stage, difficulty, category)  精确
    ② (stage, difficulty, *)
    ③ (stage, *, category)
    ④ (stage, *, *)
    ⑤ (*, *, *)                        全局铁律（必须存在，且只放铁律）

裁剪规则（INV-3）：按片段优先级从低到高裁，`priority: floor` 的三类（清单/闸门/红旗）**永不裁**；**heavy 档的主 skill 原文同样不裁**（裁它等于把 heavy 降级成要点版）；若连保底都超预算，**返回超预算而不静默裁保底**（响亮失败优于静默降级，对齐本仓既有教训）。

去重：同 id 片段只注入一次（`fragment.include` 引用可能重复）。

**层级合成语义（t8 实施暴露的澄清，2026-09-17 补记）**：回退链是"**取首个命中层**"，因此"只挂③层的类型档会被②层的节点档抢先命中而永远拿不到"。解决办法不是改 router（那会破坏"难度优先于类型"契约），而是在**生成期合成 include-only 路由壳**：

    <stage>/<category>.md            类型档正文（注册在 ③ 层）
    <stage>/<difficulty>/<category>  ① 层路由壳：text=''，include=[节点难度档(, heavy/overrides), 类型档]

于是 (stage,difficulty,category) 命中 ①，注入 = **节点内容 + 类型差异 + ⑤ 铁律**；(stage,*,category) 仍是被 include 命中的可用分片（不成孤岛）。这条语义是"路由只负责选中、合成靠 include"的直接推论，后续加新轴时沿用。

## 5. 节点执行模型：同窗口 surface 整段替换

需求 D-10/G7：同一窗口内遗弃模型可见上下文，替换内容 = 下一节点输入包。

**实现取舍（planning 必须给定论，此处给默认选择 + 依据）**：

| 路线 | 说明 | 判定 |
|------|------|------|
| (A) 直接用 surface 原语 | `session.append('user/message', …, { surfaceOp: { op: 'replace', startSeq, endSeq } })`；替换内容我们自己拼（节点输入包） | **默认**——内容语义正确（遗弃而非摘要），且不依赖 LLM |
| (B) 借 compaction 的 compactRegion | 框架守不变量，但替换内容由摘要后端生成 | 仅当 (A) 被框架不变量拒绝、且找不到合规边界时退用 |

**(A) 的三条纪律**：

1. **先落盘再遗弃**：产物写进文档/台账之后才做替换（丢上下文前状态已在盘上）。
2. **边界必须配对平衡**：起止落在 tool 调用/结果成对处；复用 `@deepseek-ai/dsh-compaction` 导出的 `toolPairingBalancedBefore/After` 做检查，不平衡则**不替换并告警**（响亮失败）。
3. **只在轮次边界执行**：节点结算点（agent 空闲、无活动轮次）执行；活动轮次/未配对工具调用时跳过并留痕。
4. **跳过受保护的系统首节点**（t9 实测硬约束）：surface 节点 0 是系统提示词，`user/message` 不可遮蔽它——只有 `system/message` 且恰为单节点可改写。故合法区间 = 首个非 system 节点 → 末尾，结果是 `[系统段, 输入包]`（与需求 §3.6 ③ 一致）。原 step ② 写"起=本会话首条"是错的，已按实测修正。
5. **框架耦合只在 adapters**：application 层禁 import @deepseek-ai/*（既有机械门禁）；`@deepseek-ai/dsh-compaction` 在本包依赖树不可解析 → 边界配对检查（toolPairingBalancedBefore/After 的等价算法）在 adapters 内移植并注明来源；t10 的隔离动作必须移出 session 事件派发（监听器内同步 append 会被拒）。

**失败与降级（D-12）**：触达不了 Session/agent → 弹框请人开新窗口并给出节点输入包（人可操作等价路径）；再不行 → 同窗口只做文档自足 + 重注入（不省钱但不丢正确性）。三条路径都不静默。

## 6. 注入点单点化（INV-1）

现状两处注入：`application/internal/capture-section.ts`（每回合 systemPrompt 组装）与 `adapters/CaptureHook.ts`（状态转移后）。改动：两处都改为调用 `resolveStagePrompt()`，并把 `STAGE_PROMPTS[stage]` 直取**删掉**（机械检查：grep 直取写法必须 0 命中）。

## 7. 门禁（每条都要能红）

| # | 门禁 | 判据 | 故障注入验证方式 |
|---|------|------|------------------|
| 1 | 覆盖完整 | 任意 (stage,difficulty,category) 解析非空；⑤ 铁律层存在 | 删掉某个 (stage,*) 兜底分片 → 红 |
| 2 | 工具名一致 | 注入文本中的 reqboard_* ⊆ 注册集合 | 插入 `reqboard_legacy_probe` → 红（既有测试已具备） |
| 3 | 预算上限 | 单次注入 charCount ≤ 预算（或响亮超限） | 调低测试预算 → 返回超限标记而非静默裁保底 |
| 4 | 片段唯一 + 无孤岛 | id 不重复；每个分片至少被一条路由命中 | 加一个不被任何路由引用的分片 → 红 |
| 5 | 链声明完整 | 每节点分片含「下一步：<next> —— 用 <tool>」，且 next ∈ 状态机合法后继 | 删一行「下一步」→ 红 |
| 6 | 源/产物同步 | fragments/**.md 与 generated/fragments.ts 一致 | 改 md 不跑生成 → 红 |
| 7 | 自足性（INV-8） | 节点产物含五字段头部 | 删任一字段 → 红（对需求文档与任务卡模板做检查） |

既有四条门禁（layer-boundary / size-budget ≤400 行 / typecheck / message-hygiene）继续必须绿。

## 8. UI / 前端

本需求的 UI 面很小，但有一条必须做：**节点输入包与「遗弃」事实要让人看得见**。

- 会话视图本来就是 surface 的渲染——替换后同一窗口里历史消失、只剩新节点输入包；这是"人可见的遗弃"，与设计一致（效果需实测确认，见 test-cases）。
- 看板侧：需求详情显示「当前节点 + 本次注入的 routeKey/片段数/字符数」（读留痕 ring buffer），让"注入了什么"可被人核查，而不是只存在于日志。
- 不新增页面、不改现有版式；只加一个只读信息块（遵循本包既有渲染函数与 escape 纪律）。

## 9. 代码规范

- 命名：分片文件 `kebab-case.md`，id = 路径去扩展名（`brainstorming/heavy`）；路由键 `stage/difficulty/category`，通配写 `*`。
- 分层：domain 纯函数；I/O 只在 adapters/scripts；工具层不得出现状态字面量（既有机械门禁）。
- 错误处理：解析失败/预算超限/边界不平衡一律**响亮返回结构化错误**，禁止静默回退到空串。
- 文件 ≤400 行（既有 size-budget 门禁）；消息卫生门禁（fmt/clip/标签单源）继续适用。

## 10. 不做（本需求边界）

- 不实现 Visual Companion 本体，只实现"提议独立成一弹"的交互约束。
- 不改 category 的现有职责（启用哪些节点/哪些门），不动状态机与 rollup。
- 不在本阶段产出最终任务 DAG（W7 边界：任务卡在 decomposing 阶段创作）。
- 不引入新的第三方依赖（生成器用 node 内置 + 仓库既有 tsx）。
