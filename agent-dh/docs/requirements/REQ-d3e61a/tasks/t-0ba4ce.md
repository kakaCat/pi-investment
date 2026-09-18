# t-0ba4ce 证据锚到编号：证据能定位到条款

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
证据锚到编号：证据能定位到条款

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
清空某张卡的 evidence 后重新结单 → 返回拒绝（凭证门）；evidence 可定位到编号时返回通过

## 实施方案（implementation）
扩展结单校验：evidence 须带编号引用；沿用既有 REQBOARD_NO_EVIDENCE 风格返回结构化拒绝

## 上游产出摘要（dependsSummary）
- 编号串联：给一个编号能查到上下游

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-18T14:42:41.019Z，窗口 session-e1fc9bb5-906c-4d20-92fc-cbd5f3e2a512）

T-6 证据锚到编号完成：新增「结单证据必须可定位」规则（含条款编号 或 命令/路径/数据锚点；空话与空证据一律拦），接线走 TaskMoveTool 薄壳绕开被占的 support.ts；状态判定下沉到 application 层（被架构门禁抓到后修正）。

### 完成项

- 规则层：content-gate-wiring 新增 EVIDENCE_ANCHOR + evidenceAnchorGap + doneEvidenceAnchorFailure。判据——证据含本卡交付的条款编号，或含可核验锚点（命令/路径/数据查询/通过计数）；"测试通过""已完成"这类空话无法定位到条款 = 没证据
- **只在有 RTM 绑定时生效**（clauseIds 非空）：没有绑定的需求无从判"该定位到哪条"，不做追溯惩罚——与其它内容闸门同语义，也是既有测试零回归的关键
- 接线：走 TaskMoveTool 薄壳（自有）在 done 之前校验，绕开被占用的 support.ts（assertDoneEvidence 在彼处）。读文件异步而改台账在同步回调里，故必须先算
- **被架构门禁抓到并修正**：第一版在工具壳里写了 `a.to === 'done'` —— layer-boundary 与 tools-dispatch 两条门禁同时报"tools/ 内不得出现状态字面量（状态判断只在 domain/application）"。已把状态判定整体下沉到 application 层的 doneEvidenceAnchorFailure，薄壳只调用不判断
- tests/evidence-anchor.test.ts 13 条：规则七条（含"空话 vs 可定位"对照与锚点模式守卫）+ 接线六条（**验收场景：清空 evidence 后结单 → 返回缺口**、空话被拦、可定位通过、非结单目标态不校验、无绑定不拦、未知任务不拦）
- 全量 1135 passed / 失败回到基线 6 个、tsc 改动面 0 错误、尺寸门禁与层边界门禁全绿、client 产物重建且与备份逐字节一致

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/content-gate-wiring.ts`
- `packages/pages/dsh-pmboard/src/tools/TaskMoveTool/TaskMoveTool.ts`
- `packages/pages/dsh-pmboard/tests/evidence-anchor.test.ts`

### 下一步

剩余：T-13 分类文档集（拟用空闲新模块 + SubmitArtifact 接线绕开被占的 protocol.ts）、T-5 看板尾项、T-14/T-17/T-18（依赖 T-13）。

---
