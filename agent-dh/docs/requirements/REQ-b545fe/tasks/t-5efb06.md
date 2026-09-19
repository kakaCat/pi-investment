# t-5efb06 端到端验证 + 文档更新

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
端到端验证 + 文档更新

## 背景摘要（context）
（待补充）

## 范围
- 阶段：test
- 端侧：doc

## 验收标准
测试需求 byStage 包含全部6个经过节点；流程图节点全部有token；pnpm test/typecheck/build:client 全绿；docs/architecture/reqboard-token-usage.md 已更新

## 实施方案（implementation）
执行验证步骤：(1) cd packages/pages/dsh-pmboard && pnpm run build:client；(2) 重启插件（launchctl kickstart 或 stop.sh+start.sh）；(3) 新建测试需求走全流程 draft→brainstorming→...→archived；(4) curl GET /dashboard/api/reqboard/requirements/:id/token 核对 byStage；(5) 浏览器打开需求详情页目视流程图；(6) 运行 pnpm test && pnpm typecheck；(7) 更新 docs/architecture/reqboard-token-usage.md §落点说明为「全部5条迁移路径统一经 transitionRequirement 结算」。结果附 verification.md。

## 上游产出摘要（dependsSummary）
- MoveRequirement 改用迁移助手
- AskConfirm 改用迁移助手
- rollup 改用迁移助手 + 可选快照提供者
- AcceptSheet 归档 + verdicts 打回改用迁移助手
- HTTP 路由快照接入（routers/tasks.ts）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-18T16:55:03.049Z，窗口 session-2b82d910-6ab6-453d-9f0c-ffad83413851）

端到端验证完成：全测试通过 + 类型检查通过 + 文档已更新

### 完成项

- 修复 token-transition-helper.test.ts 的 TypeScript 错误（statusHistory 可能 undefined + 缺失字段）
- 移除 MoveRequirement.ts 未使用的 import（recordStatus, StageKey）
- pnpm typecheck 通过（0 errors）
- pnpm test 全绿（1242/1242 tests passed, 97 test files）
- pnpm build:client 成功
- 更新 docs/architecture/reqboard-token-usage.md：添加 REQ-b545fe 实施细节（唯一助手+5条路径+HTTP接入）

### 改动文件

- `packages/pages/dsh-pmboard/tests/token-transition-helper.test.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`
- `docs/architecture/reqboard-token-usage.md`

### 下一步

推进到 done → 需求自动进入 accepting 验收

---
