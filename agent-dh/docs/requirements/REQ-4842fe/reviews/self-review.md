---
req_id: REQ-4842fe
doc: reviews/self-review
status: submitted
date: 2026-09-21
---

# REQ-4842fe 自审（交付前）

## 1. 对着需求逐条自查

| 需求条款 | 落点 | 自评 |
|---|---|---|
| FR-1 / FR-1b 按卡类型落子卡 + 显式 stages 逃生舱口 | domain/task/SubtaskTemplate.ts（映射表数据化 + 受控枚举） | ✅ 有单测（subtask-template.test.ts） |
| FR-2 子卡字段（parentId/stageKind/attempt，全可缺省） | shared/protocol.ts + 兼容读 | ✅ 老台账照读（兼容用例在全量内） |
| FR-3 父卡开工懒展开 | MoveTask 同事务落子卡 + 留痕 | ✅ lazy-expand.test.ts |
| FR-4 逐卡执行 = 一次 workflow run | reqboard_task_run → AdvanceChain → WorkflowRunner 端口 | ✅ execute-task / workflow-script-contract |
| FR-5 子卡四态收紧 | domain/task/TaskStatus.ts + 角色入参 | ✅ subtask-status.test.ts |
| FR-6 子卡凭证口径 | application/internal/support.ts（run 证据 + 文件 mtime） | ✅ 在 execute-task 用例内 |
| FR-7 / FR-13 失败即暂停 + 弹框三选一 + 不发飞书 | AdvanceChain 失败分支 + FailureAlert（弹框指令壳）+ HandleFailure | ✅ failure-handling.test.ts（8 例） |
| FR-8 父卡收尾与 rollup | AdvanceChain FINALIZE_PARENT / ROLLUP | ✅ advance-chain.test.ts |
| FR-9 / FR-10 并发上限与冲突两级防线 | domain/limits.ts + Decompose 冲突拦截 + 运行期 mtime 兜底 | ✅ concurrency-limits.test.ts |
| FR-11 / FR-12 事件链自动驱动 + 控制面 | AdvanceChain + autoRun/advance + POST /req/autorun + 看板徽标与按钮 | ✅ auto-chain-approval / client-subtask-view |
| FR-14 / FR-15 返工回上游 + 卡片修订留痕 | RequirementStatus 增 implementing→design；rework-update + revisions | ✅ failure-handling 内 |
| FR-16 会话内弹框交互 | 批准计划弹框写明"批准后自动拆分并开跑"；失败弹框三选一 | ✅ 门合并见 auto-chain-approval |

## 2. 我自己不放心的地方（诚实边界）

1. **线上未生效**：:13080 仍加载旧 dist，本需求的实时行为要重启后才算数——本次材料全部来自源码 + 构建产物，不是线上观测。
2. **并发窗口的代码**：src/adapters/FailureAlert.ts 的"弹框指令壳"（popupInstructionFor）由第二个窗口在 03:03 加入；本窗口只把它的 6 行拼接式文案改成「数组 + join + fmt」（行为不变）以过消息卫生门禁，其设计意图仅经复述核对，未做二次评审。
3. **看板"目视验收"**：单测覆盖了徽标/子卡链/进度/按钮的 HTML 与分支，但没有真人点过页面；bundle 已重建并过哨兵，仍需刷新页面确认。
4. **条款映射缺口**：拆分未把计划 FR 写入 TaskRecord.requirementRefs，需求「条款接收状态」表 16 条全红（用户裁定记账不修）。不影响功能，但下次必须修。

## 3. 结论

按需求逐条对齐、全量 1512 例绿、真实台账副本渲染零异常。建议通过验收，同时把 §2.1（重启生效）与 §2.4（条款映射）作为两笔已知欠账带入归档材料。
