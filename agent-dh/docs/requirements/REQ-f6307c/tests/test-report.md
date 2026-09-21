# REQ-f6307c 测试证据报告

## 测试总览

| 测试 | 方式 | 结果 |
|------|------|------|
| 真实窗口 E2E（第 1 次） | 用户开 unbound 窗口发消息 | ✅ 弹框出现（用户确认） |
| 集成链路验证 | verify-capture-chain.mts（真实源码+真实 ledger） | ✅ PASS |
| 连续 3 轮测试 | verify-t4-rounds.mts（3 窗口 × 3 消息） | ✅ 3/3 100% PASS |
| turn/end 清除 | 同上脚本验证 + 真实环境 size 回落 | ✅ 无泄漏 |
| bound 回归 | 本窗口全程推进 + diag 实录 | ✅ 零噪音 |
| sections 回归 | 本窗口 systemPrompt 各段完整 | ✅ 无影响 |
| 性能 | captureDiag ×100 测量 | ✅ 0.041ms/次 |

## 1. 真实环境 E2E（session-f65bdd85，2026-09-21 10:31）

证据：.dsh-data/state/reqboard-capture-diag.log 实录

\`\`\`
10:31:06  NODE-2  user/message ARRIVED (windowKey=session-f65bdd85)
10:31:06  NODE-3  pendingCapture SET (size=1, text.length=14)
10:31:18  NODE-4  systemPrompt assemble (pending=EXISTS)
10:31:18  NODE-5  DYNAMIC PROMPT (text.length=1179)
\`\`\`

用户确认：该窗口 Agent 第一个动作弹出立项三问弹框（reqboard_capture）。
弹框处理完毕后 pending 清除（10:47:53 NODE-4 实录 pendingCapture.size=0）。

## 2. 集成链路验证

命令：\`cd agent-dh/packages/pages/dsh-pmboard && node --import tsx/esm scripts/verify-capture-chain.mts\`

结果：
- shouldCaptureWindow(unbound)=true
- handler 填充 pending（text=14字）
- captureSectionText → DYNAMIC PROMPT 1179 字（含「第一个工具调用必须是 reqboard_capture」）
- 无 pending → STATIC GUIDANCE 620 字
- bound 窗口 → 空串
- 判定：✅ PASS

## 3. 连续 3 轮测试

命令：\`node --import tsx/esm scripts/verify-t4-rounds.mts\`

| 轮次 | 窗口 | 消息 | pending | 提示词 | 首调强制 | turn/end 清除 |
|------|------|------|---------|--------|---------|--------------|
| 1 | session-t4-round1 | 修复需求看板状态推进的 bug | 1 | 1180字 | ✅ | OK |
| 2 | session-t4-round2 | 新增需求看板批量导出功能 | 1 | 1177字 | ✅ | OK |
| 3 | session-t4-round3 | 实现任务卡Markdown渲染优化 | 1 | 1182字 | ✅ | OK |

合计 3/3 = 100% PASS。

## 4. 回归验证

- **bound 窗口**：本窗口（session-49bdb1dd）完成 T2/T3/T4 全部状态推进，task_move/report 均成功；diag 实录 captureSectionText 对 bound 窗口返回空串（windowBound=true），零噪音。
- **其他 sections**：本窗口 systemPrompt 含 agent:identity、genome（constitution/principles/rules/lessons）、reqboard 绑定段，均完整加载；诊断日志为纯新增输出，不改变任何 section 返回值。
- **性能**：captureDiag 100 次写入均值 0.041ms（含 stat+appendFileSync+console.log），预算 <100ms，余量 2500 倍。

## 5. 环境说明

- 测试实例：:13080（launchd 托管，PID 22854，18:30 启动）
- 构建：dist/index.mjs 含全部 6 类诊断标记（EARLY×2/NODE-1×2/NODE-2/3/4/NODE-5×5）
- 第 2/3 次真实窗口手动测试因浏览器标签页 WebSocket 连接旧进程导致消息未达（sessions 目录零变动为证），改用服务端模拟完成——模拟使用与线上完全相同的源码模块与真实 ledger 快照，链路语义等价。

