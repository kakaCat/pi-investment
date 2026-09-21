# REQ-9494f9 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|--------|---------|--------|------|------|
| FR-1 | t1 | t-90d985 | 修 buildNudgeMessage 信封并让调用点传 plugin | todo |
| FR-2 | t2 | t-673e77 | 补催办消息形状回归测试 | todo |
| FR-4 | t3 | t-f0dcf2 | 修复 session-6faac762 脏 inbox 并核验控制流恢复 | todo |
| FR-5 | t3 | t-f0dcf2 | 修复 session-6faac762 脏 inbox 并核验控制流恢复 | todo |
| FR-3 | t4 | t-0f54a6 | 审计全仓投递形状并归档验证证据 | todo |
| FR-6 | t4 | t-0f54a6 | 审计全仓投递形状并归档验证证据 | todo |

## §2 任务清单

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-90d985 | 修 buildNudgeMessage 信封并让调用点传 plugin | implement | backend | - | cd agent-dh && npx tsx -e "import {buildNudgeMessage} from './packages/solve-kit/src/host.ts'; const m:any=buildNudgeMessage({eventId:'x',title:'t',attempt:1,total:3,actorWindow:'w-a',panel:'执行看板',plugin:'dashboard-execution'}); console.log(typeof m.id, m.role, m.source.kind, m.content[0].type)" → 输出 string user plugin text |
| t2 | t-673e77 | 补催办消息形状回归测试 | test | backend | t-90d985 | cd agent-dh && npx vitest run packages/solve-kit/tests/nudge-message.test.ts → 全绿；故障注入：把 buildNudgeMessage 临时改回返回字符串后同命令必须变红。 |
| t3 | t-f0dcf2 | 修复 session-6faac762 脏 inbox 并核验控制流恢复 | implement | backend | t-90d985 | ① 解压该 session 日志折叠 inbox 投影后 next-turn 为空（不含字符串）；② 全量扫描 315 个 session 的 inserted:"[" 命中 0；③ :13080 健康检查通过，浏览器任意窗口控制台无 [session-controller] control stream failed。 |
| t4 | t-0f54a6 | 审计全仓投递形状并归档验证证据 | review | doc | t-673e77, t-f0dcf2 | grep -rn 'followup(' packages/*/src 中每个调用点的实参均为对象信封（或 createUserMessage），无字符串；docs/requirements/REQ-9494f9/verification.md 存在且 AC-1..AC-6 每条都有命令/输出或证据路径。 |
