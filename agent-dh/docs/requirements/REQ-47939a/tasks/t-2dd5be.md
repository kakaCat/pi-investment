# t-2dd5be HTTP 路由改薄（删除重复状态校验）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
HTTP 路由改薄（删除重复状态校验）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
npx vitest run tests/routes-rollup.test.ts tests/reqboard.test.ts tests/api-client.test.ts 全绿；src/http/routes.ts 存在且该文件内 grep 不到 status === 字面量比较（状态判断只在 domain）。

## 实施方案（implementation）
src/host/routes.ts → src/http/routes.ts + src/http/routers/{requirements,tasks,stages,verdicts,artifacts,triage}.ts；删除原 :285/:347/:355 的重复状态校验改为调用例（错误→HTTP 状态映射集中一处）；既有路由测试指向新入口。验证：npx vitest run tests/routes-rollup.test.ts tests/reqboard.test.ts tests/api-client.test.ts。

## 上游产出摘要（dependsSummary）
- 用例层落地（12 用例 + 3 查询投影）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T12:23:03.137Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

t7 复核通过，且复核中发现并修复了层边界门禁的洞（只查 === 漏 !==）：门禁分三层口径收紧，25 处 statusIs(x,字面量) 改为按意图命名的 domain 判定，转移目标/初始状态收进 domain 常量；故障注入实测可红。

### 完成项

- 发起窗口独立复核：路由三件 + layer-boundary → 46 passed 起点；修复后全量 611 passed / 1 failed
- 🔴 发现门禁洞：src/http/ 有 8 处 status !== … 未被告警（原正则只匹配 ===），另有 25 处 statusIs(x, 状态字面量) 属"运算符进 domain、规则留适配层"
- 修复①：门禁改三层口径（任意算子 / 判定器实参 / 任何独立状态名字面量），状态名名单从 domain 的 REQ_TRANSITIONS/TASK_TRANSITIONS 动态取（手抄名单会漂移——我的第一版探针就漏了 in_progress）
- 修复②：domain/status/Predicates.ts 重写为按意图命名判定（isAccepting/isVerifiableStage/isUnfinishedTask/countDoneTasks…），删除通用比较器
- 修复③：INITIAL/REWORK/ACCEPTED/CANCELED 需求状态与 INITIAL_TASK_STATUS 收进 domain 常量，适配层不再决定初始态与转移目标
- 故障注入实测：注入原洞形态 r.status !== 'accepting' → 门禁红；还原后 9/9 绿
- 复核确认历史事故：subagent 自报覆盖 host/routes.ts，经消息字面量账比对 HEAD 版与新 http/ 目录 —— 旧 60 条 / 新 60 条 / 旧有新无 0，判定未丢内容；三处路由前置守卫按零行为变更保留（改为经 domain 判定）

### 改动文件

- `docs/requirements/REQ-47939a/verification.md`
- `packages/pages/dsh-pmboard/src/domain/status/Predicates.ts`
- `packages/pages/dsh-pmboard/src/domain/requirement/RequirementStatus.ts`
- `packages/pages/dsh-pmboard/src/http/routers/verdicts.ts`
- `packages/pages/dsh-pmboard/tests/layer-boundary.test.ts`

### 下一步

t8 复核后 t9 收口（删 host/ 并存实现 + 尺寸门禁）。

---
