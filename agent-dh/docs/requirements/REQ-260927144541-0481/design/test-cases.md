---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7]
---

# 测试用例（REQ-260927144541-0481）

> 覆盖矩阵与用例表；执行证据在实施节点写 test-evidence.md。新测试文件头部 20 行内须带 `// serves: FR-x`。

## 覆盖矩阵 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 -->

| 功能点 | 单元 | 集成 | 故障注入 | 回归 |
|---|---|---|---|---|
| FR-1 链入口收口 | ✅ | ✅ | ✅（别名一致性） | ✅ |
| FR-2 返回体对齐 | ✅ | — | ✅（未声明键） | ✅ |
| FR-3 task_tree | ✅ | ✅ | ✅（未绑定/无子卡） | ✅ |
| FR-4 task_status 换源 | ✅ | ✅ | ✅（缺 lastRun） | ✅ |
| FR-5 角色报错 + acceptance | ✅ | ✅ | ✅（非法边/死通道） | ✅ |
| FR-6 超时归位 | ✅（静态） | — | — | ✅ |
| FR-7 门禁固化 | ✅ | ✅ | ✅（注入未声明键） | ✅ |

## 用例表 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 -->

| 用例 | 类型 | 被测 | 步骤 | 预期 | serves |
|---|---|---|---|---|---|
| TC-1 | 正向 | I-1 | 传 task_id 调 `task_run` | 返回 `job_id/run_id/status='dispatched'`，键全部已声明 | FR-1, FR-2 |
| TC-2 | 反向 | I-1 | 不传任何 id 且未绑定 | `REQBOARD_NO_BOUND_REQ` | FR-1 |
| TC-3 | 正向 | I-2 | 调 `task_execute` | 返回体与 TC-1 同形；`req.autoRun=true` 已写 | FR-1 |
| TC-4 | 故障注入 | FR-2 | 给某工具临时加未声明返回键 | `output-contract` 变红 | FR-2, FR-7 |
| TC-5 | 正向 | I-3 | 对含 4 张子卡的父卡调 `task_tree` | `subtasks.length=4` 且按链序；每项含 stageKind/status | FR-3 |
| TC-6 | 边界 | I-3 | 对未开工（无子卡）的父卡调用 | `subtasks=[]` + note 说明尚未展开 | FR-3 |
| TC-7 | 反向 | I-3 | 传别的窗口的任务 | `REQBOARD_NOT_BOUND_TO_WINDOW` | FR-3 |
| TC-8 | 正向 | I-4 | 对跑过链的子卡调 `task_status` | 读到真实 `run.ok`；不依赖 `## Workflow` | FR-4 |
| TC-9 | 故障注入 | I-4 | 卡片无 `lastRun` | `run` 缺省，不报错、不伪造 | FR-4 |
| TC-10 | 反向 | I-5 | 用 legacy 边（如 `in_progress→in_review`）推父卡 | 报错含「父卡」与合法边 | FR-5 |
| TC-11 | 正向 | I-5 | `task_move(task_id, acceptance=…)`（仅 acceptance） | 台账 `task.acceptance` 更新 + 卡文档同步 | FR-5 |
| TC-12 | 静态 | FR-6 | `grep timeoutInteractiveMs` 任务/链级工具体 | 无命中 | FR-6 |
| TC-13 | 回归 | FR-7 | `tools-schema` 构造全部工具 | 0 抛错 | FR-7 |

## 故障注入 <!-- serves: FR-2, FR-4, FR-5, FR-7 -->

| 注入点 | 注入方式 | 预期 |
|---|---|---|
| 契约门禁 | 临时给 `defineAdvanceTool` 加未声明键 | 门禁红（只测成功路径不算） |
| 死通道 | 保留 `acceptance` 不接线 | TC-11 必红（证明它真的接线了） |
| 死数据源 | 不写 `## Workflow` | TC-8 仍绿（证明不再依赖它） |
