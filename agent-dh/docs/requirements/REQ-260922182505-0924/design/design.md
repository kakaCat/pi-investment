---
requirement_refs: BUG-1, BUG-2
---

# 设计 · REQ-260922182505-0924 删除 triage 遗留兼容路径

## 目标 `serves: BUG-1, BUG-2`

把 M2 旧流程的 triage 兼容层从"仍在装配运行"变成"不存在"：交互层（路由/前端面板/立项前置检查）全删，台账字段冻结只读；另删 3 个 .bak 垃圾文件。可证伪：grep 清零 + triage 路由 404 + 全量回归无新增失败。

## 核心取舍：删行为、留数据 `serves: BUG-1`

台账 `triages` 字段、`TriageRecord` 类型、JsonLedgerRepository 读写管道、RollupSpec/rollup 的 triage 读取**全部保留冻结**——存量 2 条已 resolve 记录照常加载，rollup 的"人工建卡留立项"语义不变（无 pending 卡时本就无操作）。只删"还会产生行为"的部分。依据：台账兼容是硬约束（破坏性读改写曾被验收 4 锁死），而冻结数组的迭代成本为零。

## 改动面（21 个 src 文件的处置表） `serves: BUG-1, BUG-2`

删文件：routers/triage.ts、support.ts.bak2/.bak3/.bak4。删代码：routes.ts（4 挂载+import）、window.ts（2 判定函数）、capture-section.ts（pending 检查分支）、support.ts（findPending）、CaptureRequirement（前置检查③）、QueryState（pending 用法）、StatusTool（pending 展示）、Predicates（isPendingTriage/isResolvedTriage，仅剩 triage.ts 引用）、board-mount（triage 视图状态机约 30 处）、views/board.ts（buildTriage+tab）、api.ts（4 接口）、types.ts（TriageList/TriageRecord 客户端类型）、styles/base.ts（triage CSS）、view.ts（1 处）。仅注释不动：CaptureHook、index.ts、SessionMessageFilter（注释里的 triage 字样是历史说明，保留）。
