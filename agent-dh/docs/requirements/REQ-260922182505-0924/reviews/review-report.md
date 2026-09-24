---
requirement_refs: BUG-1, BUG-2
---

# 代码评审报告 · REQ-260922182505-0924

> 评审人：w-9faaac35（实施窗口自评 + diff 逐项核对）｜评审时点：2026-09-22T12:34:29.182Z
> 评审对象：dsh-pmboard 包 src/ + tests/ 的全部改动（git diff 逐文件核对）
> **结论：通过**（可提交验收）

## 1. 根因与修复点对应（bug 类型档：根因不清不许动手）

根因（requirement.md 已锁定）：M2 自动分类流程 2026-09 退役时只删了实现本体，兼容层
（triage 路由 + 前端面板 + pending 建议卡判定）保留用于"处理遗留卡"；遗留卡 2026-09-08
前已全部处理完毕（台账实证 pending=0），兼容层失去存在意义但无人删除。

修复点与根因一一对应：
- 路由层：`routers/triage.ts` 整文件删除 + `routes.ts` 4 挂载点摘除 → 修"GET /triage 仍可用"
- 判定层：`window.ts` hasPendingSuggestion/pendingSuggestionFor + `support.ts` findPending +
  `CaptureRequirement.ts` REQBOARD_PENDING_TRIAGE 前置检查 → 修"对着尸体站岗"
- 前端层：`api.ts` 4 接口、`board.ts` buildTriage、`board-mount.ts` 视图状态机与 action、
  `types.ts` 客户端类型、`styles/base.ts` CSS、`view.ts` 导出 → 修"前端面板残留"
- 垃圾文件：`support.ts.bak2/.bak3/.bak4` 删除 → BUG-2

## 2. 顺手重构检查（类型档红线）

diff 逐文件核对结果：**无夹带**。
- 全部 src/ 改动均为 triage 代码摘除，或其必然伴随的描述同步（4 处单行文案：
  index.ts 注册日志、CaptureHook 运行日志与注释、gate-wiring 注释、protocol.ts 注释口径）。
- 冻结面零语义变化（diff 实证）：protocol.ts / JsonLedgerRepository.ts / rollup.ts /
  RollupSpec.ts / ports.ts 的台账契约与管道**一行未动**（protocol.ts 仅 1 行注释口径更新，
  因原文"路由仍兼容"已成错误陈述）。
- ⚠️ 工作区同时存在 templates/ 目录大量 M/D 与 REQ-260922133212-dd5b/verification.md 改动
  ——**均不属本需求**（其他工作线在途改动，本窗口零触碰），验收时请勿计入本 diff 评审范围。
  本需求改动清单 = git diff 中 dsh-pmboard/src/** 与 dsh-pmboard/tests/** 与
  docs/requirements/REQ-260922182505-0924/** 三部分。

## 3. 保留面复核（删行为留数据）

- 台账 `triages` 字段、`TriageRecord` 类型、JsonLedgerRepository 读写管道、
  RollupSpec/rollup 的 triage 锚点读取：全部保留（存量 2 条 resolved 记录照常加载，
  migration v4 fixture 测试 9/9 绿为锁定证据）。
- `isWindowBound`/`openRequirementsFor` 的 triage 锚点逻辑保留：历史 confirmed 记录
  仍是窗口→需求绑定的数据锚点，删除会破坏存量绑定判定——与设计"冻结数据通道"一致。
- 删除后行为变化点（有意为之，已在设计声明）：
  captureSectionText/shouldCaptureWindow/CaptureHook 不再因遗留 pending 卡压制捕获引导；
  reqboard_status 不再返回 has_pending/pending_triage_id 字段；
  REQBOARD_PENDING_TRIAGE 拒绝码不再可能触发（无生产端）。

## 4. 风险与残余项

- 现役 :13080 实例仍运行旧代码（launchd 托管，重启即生效）——已在验收材料声明。
- 浏览器目测渲染无法由 agent 执行，已提供产物级等价证据（bundle 0 处 triage 引用 +
  状态接口 200 + 页面行为与现役实例逐点一致），验收单列人工目测项。
