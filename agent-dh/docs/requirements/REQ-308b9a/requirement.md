---
req_id: REQ-308b9a
title: 验收阶段补齐：回退实施 + 不可验收项记录 + verification.md 生成（R-7）
category: feature
status: design
owner: w-7cfa4169
created: 2026-09-20
business_value: 验收是"交付是否可信"的唯一闸门——缺回退则缺陷带病归档，缺不可验收项记录则未验内容静默消失，缺验收文档则人只能盲勾弹框
risk_level: medium
---

# REQ-308b9a 阶段 6 验收补齐（回退实施 / 不可验收项记录 / 验收文档生成）

> **本需求是 PRD `REQ-99b58f《修复 PM 插件生命周期流程（文档+代码）》` 的「阶段 6 验收」子集落地。**
> **编号沿用 PRD 体系**：FR-7 / AC-7.x **保持 PRD 原文**；两条订正新增 FR-8 / FR-9。
>
> 节名说明：PRD 用「需求概述/功能需求/非功能需求」，而本仓现行文档标准（`category-doc-sets.ts`）
> 要求 feature 根文档必含 **产品定义 / 用户与角色 / 功能点 / 边界** —— 故本需求在保留 PRD 内容与编号的同时，
> **按现行标准组织节名**（PRD 自身缺这四节，先于该标准）。
>
> - PRD：`docs/requirements/REQ-99b58f/requirement.md`（brainstorming，仅 requirement.md）
> - 节点名以 `docs/architecture/workflow-stages.md`（唯一事实源）为准；
>   PRD 正文的 `planning`/「技术设计」是 REQ-81aabd 改名前的旧值，现行为 `design`/「设计」。
> - **本文档只回答「做什么」**；数据契约、校验实现、渲染契约在 design 阶段 `design/*.md`。

---

## 1. 需求概述

### 1.1 背景

用户对 PRD 阶段 6（验收）提出两条订正（原文）：

> 「验收缺少回退到实施里，验收失败应该回退到实施里解决问题」
> 「不能验收的内容要有记录，不是所有的都验收才可以通过」

三条缺口，均有代码级实证：

| # | 缺口 | 现状实证 |
|---|---|---|
| 1 | 验收失败**无回退**：裁决只记录、不改需求状态 | `application/internal/verdicts.ts:133`、`verdicts.ts:161-171` |
| 2 | **无可验收项记录 + 不允许部分通过**：项只有 `pending/passed/failed`；归档要求全 passed | `shared/protocol.ts:540`、`application/use-cases/AcceptSheet.ts:48-53` |
| 3 | **verification.md 只是骨架**：无操作步骤/预期结果/文档完整性检查/结果表 | `application/use-cases/SubmitVerification.ts:172-187` |

### 1.2 目标

补齐阶段 6 的**出口条件**：失败可回退修复、不可验收内容留痕、验收有可执行的文档而非盲勾弹框。

### 1.3 范围

代码限 `packages/pages/dsh-pmboard/`（domain/application/tools/client/http）；文档同步 PRD 与指南。

### 1.4 阶段 6 验收流程总览

```
阶段 6：验收（accepting）
  做什么：
  ✓ reqboard_submit(kind=verification) 生成逐项验收单 + verification.md
  ✓ 人逐项裁决（通过 / 不通过+意见 / 不可验收+原因）
  ✓ 不通过项 → 回退 implementing + 自动生成返工任务   ← FR-8 补齐
  ✓ 不可验收项 → 记录在案、不阻断通过                  ← FR-9 补齐

  产物：verification.md（验收列表 / 测试报告 / 文档完整性检查 / 验收结果表）
  出口门（人工门）：全部项已裁决（无 pending）→「验收通过」→ 归档；有 failed → 自动回退实施
  状态：archived（归档）
```

---

## 2. 产品定义

**产品**：项目看板的**阶段 6（验收）环节**——它回答"这次交付是否可信"，是进入归档前的唯一人工闸门。

它必须回答三个问题（三缺一即闸门形同虚设）：

| 问题 | 缺了会怎样 | 本需求对应 |
|---|---|---|
| 交付物**能不能照着验**？ | 人只能对着弹框盲勾 | **FR-7** verification.md（操作步骤/预期结果） |
| 验**不过**的怎么办？ | 缺陷带病归档 | **FR-8** 自动回退实施 + 返工卡 |
| **验不了**的怎么办？ | 未验内容静默消失 | **FR-9** `not_verifiable` 记录 + 部分通过 |

**一句话**：让"未验 / 不可验 / 验不过"三种状态**都可见、可追溯、有出口**。

---

## 3. 用户与角色

| 角色 | 在本需求里的位置 | 能做什么 / 不能做什么 |
|---|---|---|
| **人（审核者）** | 唯一有权操作验收裁决 | 逐项裁决（通过 / 不通过+意见 / 不可验收+原因）；点「验收通过」（人工门）。**不能**被 agent 代办 |
| **窗口 agent（交付方）** | 提交材料、维护任务 | 调 `reqboard_submit(kind='verification')` 交材料；调 `reqboard_accept_sheet` 触发弹框。**不能**代替人点"通过" |
| **看板插件（系统）** | 载体 | 生成 verification.md、执行文档完整性检查、失败自动回退、全程留痕 |

---

## 4. 功能点

### FR-7: 验收文档生成（阶段 6）【PRD 原文，编号保持】

**功能描述**：阶段 6 自动生成 `verification.md`，含验收列表、操作步骤、预期结果，
替代当前只有弹框验收的做法。

**verification.md 结构**（PRD 原文）：

```markdown
# 验收文档

## 1. 验收列表
### FR-1: 用户名密码登录
**验收内容**：用户可以使用用户名和密码登录系统
**操作步骤**：
1. 打开登录页 http://localhost:3000/login
2. 输入用户名：testuser
3. 输入密码：Test123456
4. 点击"登录"按钮
**预期结果**：
- 登录成功
- 跳转到首页
- 显示用户信息
**实际结果**：（待填写）
**验收状态**：⬜ 待验收

## 2. 测试报告
- 单元测试：37/37 通过，覆盖率 85%

## 3. 文档完整性检查
✓ requirement.md 存在 …（9 类）

## 4. 验收结果
| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| FR-1 | 用户名密码登录 | ✓ 通过 | user | 2026-01-15 14:30 |

**验收结论**：全部通过 ✅
```

**验收流程**：
1. Agent 提交验收材料（`reqboard_submit kind='verification'`）
2. 后端自动生成 verification.md
3. 后端执行文档完整性检查
4. 后端生成验收单（从需求文档提取验收项）
5. Agent 调用 `reqboard_accept_sheet` 逐项验收
6. 用户操作验收（按操作步骤执行，确认预期结果）
7. 全部通过后更新 verification.md 的验收结果表

**验收标准**（PRD 原文编号）：
- AC-7.1: reqboard_submit(kind='verification') 自动生成 verification.md
- AC-7.2: verification.md 包含所有功能需求的验收项（FR-1/FR-2...）
- AC-7.3: 每个验收项包含操作步骤和预期结果
- AC-7.4: 自动执行文档完整性检查（检查 9 类文档）
- AC-7.5: 文档缺失时阻止验收并提示补充
- AC-7.6: reqboard_accept_sheet 弹框包含操作步骤
- AC-7.7: 验收完成后自动更新 verification.md 的验收结果表
- AC-7.8: 验收结果表包含：编号/验收项/状态/验收人/验收时间

> 操作步骤/预期结果**来源**（brainstorming 决策）：从任务卡 `acceptance`（含「怎么验」）+ 需求级 AC 派生，
> 不新增人工录入字段。

### FR-8: 验收失败回退实施（新增，**推翻 REQ-a8d582 FR-2**）

**功能描述**：逐项裁决出现 `failed` 时，系统**自动**把需求回退到 `implementing` 并按不通过项生成返工任务；
不再要求人额外点「退回返工」。

- 决策来源：brainstorming 弹框，用户选择「恢复自动回退」。
- 返工任务规格复用 `domain/workflow/AcceptanceSheetSpec.ts` 的 `reworkSpecsFor`（规则单点）。

**验收标准**：
- AC-8.1: 提交含 `failed` 的裁决后，需求状态自动变为 `implementing`（无需人再点按钮）。
- AC-8.2: 每个 `failed` 项自动生成一张返工任务卡（`status=todo`，含 implementation 与可证伪 acceptance）。
- AC-8.3: 自动回退与返工卡在**同一笔 mutate** 内完成（原子），不得"状态改了卡没建"。
- AC-8.4: 回退写入状态事件（statusHistory，含 actor/reason）+ 评论留痕；token 快照结算不丢失。
- AC-8.5: `not_verifiable` 项**不触发**回退（只有 `failed` 触发）。

### FR-9: 不可验收项记录 + 允许部分通过（新增）

**功能描述**：验收项新增一等状态 `not_verifiable`（不可验收/不适用，须带原因）；
「验收通过」判据从"全 passed"改为"**全部项已裁决**（无 `pending`）"。

- 决策来源：brainstorming 弹框推荐项「全部项已裁决（无 pending）即可通过；不可验收项计为已裁决并留痕」。
- 语义：`not_verifiable` = 该项**无法按要求验**（环境缺失/不适用/被裁剪），但**必须有人看过并给出原因**。

**验收标准**：
- AC-9.1: `VerificationItem.status` 扩展为 `pending | passed | failed | not_verifiable`。
- AC-9.2: 标记 `not_verifiable` 必填原因（意见），无原因拒绝记录。
- AC-9.3: 「验收通过」放行条件 = 无 `pending` 项。
- AC-9.4: `not_verifiable` 项在 verification.md 验收结果表显式列出（状态列写明"不可验收"+原因）。
- AC-9.5: 只要有 `pending` 项，「验收通过」被代码级拒绝（防未验项静默消失）。
- AC-9.6: 老验收单（无 `not_verifiable`）可正常读取与续验（向后兼容）。

---

## 5. 非功能需求

### NFR-1: 向后兼容性
历史验收单（`pending/passed/failed`）必须可读、可续验；不得因新增枚举值导致反序列化失败或旧单无法归档。

### NFR-2: 规则单点
"是否可归档 / 是否回退"的判定、返工任务规格、验收单生成规则必须落在 `domain/`（`workflow/AcceptanceSheetSpec.ts` 邻近），适配层不得各写一份。

### NFR-3: 文档完整性检查口径
AC-7.4 的"9 类文档"必须与本仓实际文档标准对齐（`docs/architecture/documentation-standard.md`、`requirement-archive.md`），不另造清单；缺项提示须指名补哪一份。

---

## 6. 状态机变更

### 6.1 需求状态（RequirementStatus）
**不变**。只改 `accepting ⇄ implementing` 的**迁移触发者**：从"人点退回返工"改为"出现 failed 自动回退"。

### 6.2 验收项状态（VerificationItem.status）
`pending | passed | failed` → **`pending | passed | failed | not_verifiable`**。

---

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-7 | ✅ 已完成（有证据） | t-552eeb、t-df5d0c、t-0c40e9、t-3935ea、t-1fa603 |
| FR-8 | ✅ 已完成（有证据） | t-20a647、t-6ccc5c、t-3935ea、t-1fa603 |
| FR-9 | ✅ 已完成（有证据） | t-b45ad8、t-3935ea、t-1fa603 |

> 无未接收条款（3 条全部有落点）。

<!-- reqboard:marks:end -->

## 7. 边界

**做**：
1. FR-7 verification.md 结构化生成（AC-7.1~7.8）
2. FR-8 自动回退 + 返工卡（AC-8.1~8.5）
3. FR-9 `not_verifiable` + 全部已裁决即通过（AC-9.1~9.6）

**不做**：
1. 不改需求状态集本身（accepting/implementing/archived）
2. 不新增"操作步骤/预期结果"人工录入字段（FR-7 走派生）
3. 不重做看板验收面板整体 UI（除弹框补操作步骤、按钮可见性随 FR-8 适配）
4. 阶段 7（归档）不在本需求范围（按 PRD 原样）

---

## 8. 实施影响分析

**影响范围**：`shared/protocol.ts`（枚举）、`domain/workflow/AcceptanceSheetSpec.ts`（判据/返工规格）、
`application/internal/verdicts.ts`（回退）、`application/use-cases/{AcceptSheet,SubmitVerification}.ts`、
`tools/AcceptSheetTool`、`client/views/*`。

**风险与缓解**：
1. **与 REQ-a8d582 冲突**（其 FR-2 被本需求推翻，且其代码改动当前仍未提交）→ 先合入基线再改，不触碰他人未提交改动。
2. **弹框题干过长**（`AskConfirm.ts:42` 未按 `popupQuestionMax(220)` 截短，已实测挤出选项）→ 随 AC-7.6 一并修。

---

## 9. 待确认与开放问题

1. 与 REQ-a8d582 未提交改动的合入顺序。
2. FR-9 与 AC-7.6 交互：弹框"不可验收"选项的文案与长度。
3. "9 类文档"的本仓实际映射清单在 design 阶段核对（见 `design/data-model.md` §5）。
