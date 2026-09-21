# t-b2bb6b 其余 8 张业务卡片（submit/ask_confirm/status/capture/memory_write/decision_audit/portfolio_trade/watch_manage）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
其余 8 张业务卡片（submit/ask_confirm/status/capture/memory_write/decision_audit/portfolio_trade/watch_manage）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
npx vitest run 中 9 卡 summarize 四档用例（正常/缺字段/畸形/error 态）全绿；每张卡解析失败路径断言返回 fallbackRow 结构

## 实施方案（implementation）
rows/ 下每工具一个文件；中文映射从 shared.ts 取；每张卡导出游离 summarize 纯函数供单测

## 上游产出摘要（dependsSummary）
- 骨架接线：bizToolviews 注册入口 + BizRow 布局 + task_move 示范卡

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T03:24:36.533Z，窗口 session-85447f15-ee57-44ef-8fd0-d8526111c0b3）

其余 8 张业务卡片完成（submit/ask_confirm/status/capture/memory_write/decision_audit/portfolio_trade/watch_manage），9 卡全部注册进 BIZ_CARDS；四档单测 34/34 绿（含每卡畸形输入返回 null → fallbackRow 的断言）；顺手过了消息卫生棘轮门禁（新增消息全部 fmt/模板字面量化）

### 完成项

- rows/ 下 8 个新卡片文件，每卡游离 summarize 纯函数
- toolviews/index.ts：BIZ_CARDS 9 张全注册
- tests/toolviews-cards.test.ts：34 用例（正常/缺字段/畸形/error 四档 + FR-2 两两不同判据 + FR-4 null→fallbackRow）
- 修复棘轮门禁：client/tools 层 13 处中文拼接 → fmt/模板字面量

### 改动文件

- `packages/pages/dsh-pmboard/src/client/toolviews/rows/submit.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/rows/ask-confirm.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/rows/status.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/rows/capture.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/rows/memory-write.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/rows/decision-audit.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/rows/trade.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/rows/watch-manage.ts`
- `packages/pages/dsh-pmboard/src/client/toolviews/index.ts`
- `packages/pages/dsh-pmboard/tests/toolviews-cards.test.ts`

### 下一步

t2/t4 待重启后做 GUI 实测关门

---
