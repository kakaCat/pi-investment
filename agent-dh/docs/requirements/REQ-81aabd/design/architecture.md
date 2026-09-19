---
req_id: REQ-81aabd
title: 设计 · 架构：设计文档种类的归因链路与「只加呈现」的边界
serves: FR-3, FR-4, FR-5
---

# 设计 · 架构（REQ-81aabd）

## 1. 分层与数据流（serves: FR-3, FR-4, FR-5）

`design/*.md` 从"躺在地板上"到"看板上逐份 已交/未交"经过四层，每层只做一件事：

| # | 层 | 职责 | 关键符号 |
|---|----|------|----------|
| 1 | domain | **分类**：相对路径 → 产物种类 | `kindForRelPath()` |
| 2 | adapters | **归因 + 补登**：扫需求目录，把未登记的 `design/*.md` 写进台账 | `syncReqArtifacts()` → `ArtifactSync.ts` |
| 3 | application | **装配**：把"要求哪些"与"交了哪些"合成逐份状态 | `designDocStatus()` → `QueryStageDetail.ts` |
| 4 | client | **渲染**：逐份 ✅ 已交 / ⬜ 未交 | `renderDesignBody()` |

数据流：`docs/requirements/<REQ>/design/*.md` →（同步）→ 需求台账 `artifacts[]` →
（查询）→ `DesignStageBody.designDocs[]` →（渲染）→ 面板 DOM。
**没有反向写**：面板不写文件、不改台账。

## 2. 为什么不改门禁（serves: FR-3, FR-4）

分类模板里只有 feature / refactor 要求设计文档（2~4 份），bug / spike / doc / chore **零要求**。
若把 `design` 加进 `STAGE_ARTIFACT_REQUIREMENTS`（必备产物）或 `ARTIFACT_CONFIRM_GATES`（确认门），
四类需求会凭空多出一道卡点——**误伤的正是最轻量的那四类**。

因此本方案给 `design` 的定位是**展示种类**：
- 进 `ALL_ARTIFACT_KINDS`（否则 `reqboard_submit` 的 kind 校验会拒收）；
- **不进** `STAGE_ARTIFACT_REQUIREMENTS`、`ARTIFACT_CONFIRM_GATES`；
- 不参与"文档交齐"判定（交齐仍由提交时的 `missingCategoryDocs()` 负责）。

这条边界由单测锁死（见 `design/test-cases.md`），避免后来者"顺手补齐"。

## 3. 追溯链顺序（serves: FR-3）

面板的追溯链 `TRACE_CHAIN_ORDER` 插入 `design`：

```
requirement → design → plan → decomposition → task_detail → verification → archive
```

顺序即语义顺序：先有需求（做什么），再有设计（怎么做），然后是拆分计划（做哪些步骤）、
任务卡（每步的实施）、验收、归档。**渲染缺口标记的循环读的是 `STAGE_ARTIFACT_REQUIREMENTS`**，
不读本数组——所以插入 `design` 不会让"缺哪一环"的提示变多。

## 4. 兼容与回滚（serves: FR-3, FR-5, FR-7）

| 场景 | 行为 |
|------|------|
| 存量需求（`artifacts` 为空） | 不出错；首次同步即补登，历史文件自动归位 |
| 旧条目 `kind='notes'` 且 `autoDiscovered: true` | 同步时按当前规则**回填**为 `design`（FR-5） |
| 人工登记的产物（无 `autoDiscovered`） | **不覆盖**，人的声明优先 |
| 非 `.md` 设计附件（`design/*.html`） | 仍归 `notes`（不假装是文档） |
| 回滚 | 回填只改 `kind`/`stage` 两个字段，回滚版本后下次同步按旧规则重算即可，无数据损坏 |
| 存量台账状态键 `planning` | 运行时读路径**零兼容**；由 `scripts/migrate-ledger.ts` v6→v7 一次性归一为 `design`（FR-7），不靠读时兜底 |

## 5. 已知取舍（serves: FR-4）

- `designDocs` 缺失时（老服务/老协议）客户端回退为原有的"模板名清单"渲染，避免面板空白。
- 逐份状态是**按分类模板的要求集**对照台账，不扫描文件系统实时状态：
  面板看到的是"已登记 = 已交"。文件存在但未被同步时会在下次同步补上（这是刻意选择：
  面板不做 IO，避免每次渲染打盘）。
