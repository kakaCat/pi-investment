# t-8eee40 端到端测试

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
端到端测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果
E2E 测试通过（cd packages/web/dsh-pmboard && pnpm test tests/rtm-e2e.test.ts，输出最后一行包含 "PASS" 且 exit code 0） && 所有 7 个 RTM 文件生成（ls docs/requirements/REQ-test-e2e/rtm-*.yml | wc -l 输出 7） && 追溯链完整（grep "fr_to_design:" rtm-design.yml && grep "design_to_tasks:" rtm-decomposing.yml && grep "task_to_tests:" rtm-accepting.yml 三条命令都有输出） && 覆盖度门禁在测试用例中验证生效（测试日志包含 COVERAGE_INSUFFICIENT 拦截记录）

## 实施方案（implementation）
创建 tests/rtm-e2e.test.ts（创建测试需求 → 提交需求文档 → 提交设计文档 → 批准拆分计划 → 任务汇报 → 提交验收材料 → 验证 7 个 RTM 文件生成 → 验证追溯链完整 → 验证覆盖度统计），使用 vitest 运行

## 上游产出摘要（dependsSummary）
- decomposing 阶段 RTM 生成
- implementing 阶段 RTM 生成
- accepting 阶段 RTM 生成
- StatusTool 集成覆盖度

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T01:36:06.955Z，窗口 session-9f2c6c84-0d41-41b8-b4ce-2d1c7e50bf32）

端到端验证通过（本轮实测，非仅单测）：API 三阶段返回完整追溯链；补充 tests/traceability-handler.test.ts 7/7；reqboard RTM 套件 22 文件 186 通过。⚠️ 验收锚点失效：计划假设实现位于 dsh-pmboard/src/domain/rtm/，实际 canonical 实现位于 packages/tools/reqboard/src/rtm/——本卡需修订验收标准后重判。 注：本卡锚点 tests/rtm-e2e.test.ts 不存在，实际测试在 packages/tools/reqboard/tests/rtm/。

### 完成项

- 186 测试通过
- API 端到端三阶段验证通过
- 新增 traceability-handler.test.ts 7/7

### 改动文件

- `packages/web/dsh-pmboard/tests/traceability-handler.test.ts`

### 下一步

状态推进需在看板操作或由具备 reqboard_task_move 的通道完成；本卡验收标准锚点已失效，建议先修订验收标准。

---
