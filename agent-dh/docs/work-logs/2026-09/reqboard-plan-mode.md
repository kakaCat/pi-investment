# 项目看板：计划模式（plan mode）——拆分前必须先有计划且获批

- **日期**：2026-09-13
- **窗口**：w-1cee2467（session-1cee2467-95f9-46ec-9cd8-8577932e7060）
- **分支**：feat/reqboard-plan → main
- **用户要求（原文）**：「如何拆分需要agent介入的 / 我希望的是 https://github.com/obra/superpowers 这个skill的plan模式版本你懂」

## 需求解读（对齐 superpowers）

superpowers 的核心是**三段式 + 一道硬闸**：brainstorming（把想法谈成设计，HARD GATE：人批准前不动手）→ writing-plans（计划文档：每个任务给 Files / Interfaces / bite-sized 步骤 / 验收）→ executing-plans（按任务逐项执行、逐项验证）。
本项目原先的拆分缺的正是中间那一段：agent 可以直接落库任务卡，**人唯一的把关点只剩「已拆分」这个状态**，看不到粒度、依赖与验收标准的取舍。

## 实现

### 1. 闸门从"状态"移到"计划"
- `PlanRecord`：path（计划文档）+ summary（人读这段决定批不批）+ tasks（任务表：key/title/phase/side/depends_on/acceptance）+ 提交/批准/退回留痕。
- 新工具 `reqboard_plan_submit`：窗口 agent 提交计划 → 泳道卡面「计划待批」。
- 人工裁决路由：`POST /req/plan/approve`、`/req/plan/reject`（退回必须给理由）；看板计划卡上「批准计划 / 退回计划」。
- **HARD GATE（代码级）**：未批准时 `reqboard_decompose` 直接拒绝 `REQBOARD_PLAN_NOT_APPROVED`。
- **批了 A 不能落库 B**：落库内容以批准的计划为准；显式传 tasks 时 key 集合必须一致，否则 `REQBOARD_PLAN_MISMATCH`。
- **重新提交作废旧批准**：改过的方案不能沿用上一轮的点头。

### 2. 粒度写在计划里
任务表在提交计划时就定死（含依赖 DAG 与验收标准），批准即批准拆分方案；decompose 退化为"落库批准过的东西"，不再二次创作。计划提交时即校验：key 唯一、依赖只能指向计划内 key、无自依赖、标题非空。

### 3. Skill（用户点名要的形态）
`agent-dh/skills/reqboard-plan/SKILL.md`：plan 模式 SOP——三类路径判定（Spike/Bounded/Architectural）+ HARD GATE + 计划文档结构 + 任务 right-sizing（"评审者可能只拒其一"的切分判据）+ bite-sized TDD 步骤 + 用户批准 → 落库 → 逐任务执行（留证据、停止条件、反模式清单）+ 与 superpowers 的映射表。

### 4. 口径一致性
绑定窗口提示段（capture.ts）注入同一套计划纪律：评审阶段先写计划、请人批准、再拆分；已批准后的在途状态仍由 agent 自行推进（保留 2026-09-11 用户裁定：不让人点中间步骤）。

## 验证

- **单测 167 passed / 13 files**（新增 plan-mode.test.ts 9 例：未提交/未批准被拒、批准后落库等于批准内容、批 A 落库 B 被拒、退回可重提、退回必须给理由、计划结构校验、越权；decompose-tools.test.ts 重写为边界组 6 例；client-view.test.ts 新增计划卡渲染 4 例）。
- 路由级：批准/退回走真 HTTP 全链路（假 req/res），证明闸门在服务端而非提示词。
- 类型检查：与 main 基线逐条比对，唯一差异仍是 Cannot find name 'window' 这一类既有噪声（11 → 16 处，DOM lib 未纳入 root tsconfig）。
- client 产物重建：lib/client.js 58387 bytes，含 dsh-pm-plan(19) / plan-approve / plan-reject / plan-pending。

## 生效方式

- client 半（计划卡、批准按钮、卡面 chip）→ 刷新页面即生效。
- host 半（新工具、计划闸门、裁决路由）→ 重启 13080。
- skill（reqboard-plan）→ 放在 agent-dh/skills，装载根已注册，会话内可直接用 skill 工具加载。

## 遗留 / 可调项

- 计划闸门目前是**强制**的（无批准不可拆）。若某些轻量需求想跳过，可加配置开关，但建议保留默认强制。
- 计划文档本身不在 ledger 里（只存路径 + 摘要 + 任务表），文档内容随需求的 git 工作区走。
