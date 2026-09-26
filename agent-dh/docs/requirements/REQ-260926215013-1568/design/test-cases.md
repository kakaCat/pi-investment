---
req_id: REQ-260926215013-1568
kind: design
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
---

# 测试用例设计 · Dive 对齐 Goal driver

**需求**: REQ-260926215013-1568

主测试文件（新建）：`tests/dive-manager-alignment.test.ts`。
**文件头必须写** `// serves: FR-1, FR-2, … FR-11`（前 20 行内），否则验收面会出现「孤儿用例」项。

## 对齐单测（主命令） «serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11»

构造方式：内存 `ReqboardRepository` fake（`snapshot/read/mutate`）+ fake `agents`（可切 `status`）+ 可编排 `checkpoint()` promise +
记录型 `logger`/`deliverMessage`。`roundLimitFor` 用真实 `stage-configs`。

| 用例ID | 场景 | 输入 → 期望（可证伪） | 实际文件 | serves |
|--------|------|------------------------|----------|--------|
| TC-01 | pre-step 竞态栅栏 | 预留后把需求 `version+1` → `onPreStep` 返回 `{kind:'reject'}`；同批另一条已认领消息回到 `nextStep`（原顺序） | tests/dive-manager-alignment.test.ts | FR-1 |
| TC-02 | inbox 竞争让位 | 预留 `queued` 后 `onInboxInserted(人类消息)` → `competingQueued` 真、attempt.stale 真；`onIdle` 后 `deliverMessage` 调用数为 0 | tests/dive-manager-alignment.test.ts | FR-2 |
| TC-03 | 耐久检查点 | `checkpoint()` 挂起 → 不投递；`checkpoint()` reject → 该需求 `dive.activation==='disarmed'` 且 `warn` 命中 | tests/dive-manager-alignment.test.ts | FR-3 |
| TC-04 | 驱动串行化与合并触发 | 连发 3 次触发 → 驱动体执行 1 次；驱动体抛错 → 无未捕获异常/未处理 rejection（`process.on('unhandledRejection')` 计数 0）且 `warn` | tests/dive-manager-alignment.test.ts | FR-4 |
| TC-05 | teardown fail-closed | `teardown()` 后触发 → 不投递；在飞 attempt 被 `cancel({kind:'parent'})`；`whenIdle` 被 await | tests/dive-manager-alignment.test.ts | FR-5 |
| TC-06 | 驱动点 = 整 agent 空闲 | agent `running` 时 `onRequirementMoved` → 不投递；切 `idle` + `onIdle` → 投递一次 | tests/dive-manager-alignment.test.ts | FR-6 |
| TC-07 | reservation → admission 计数 | 预留后 `onInboxDiscarded` → `roundsInStage` 不变；`user/message(id=messageId)` → 恰好 +1；重复同 id 事件 → 仍 +1 | tests/dive-manager-alignment.test.ts | FR-7 |
| TC-08 | 回合上限终态 | `roundsInStage === maxRounds` → `dive.phase==='paused'` 且 `pausedReason==='round-limit'` + comment + 一次 warn；再 `onIdle` 不投递 | tests/dive-manager-alignment.test.ts | FR-8 |
| TC-09 | 异常收尾三形态 | `turn/end(max-tokens)` → disarmed；`turn/end(aborted)` 且 `claimed` → attempt.cancelled，空闲后 `phase='paused'/pausedReason='aborted'`；`agent/error` → disarmed | tests/dive-manager-alignment.test.ts | FR-9 |
| TC-10 | source/内容不变量 | 伪造 `source.round` 不符 或 `content` 与登记不等 → pre-step `reject`，`warn` 含拒绝原因 | tests/dive-manager-alignment.test.ts | FR-10 |
| TC-11 | 可观测（失败响亮） | 起轮/拒绝/让位/检查点失败/终态/teardown 六条路径各有对应 level 的日志记录（无留痕即失败） | tests/dive-manager-alignment.test.ts | FR-11 |

## 回归用例 «serves: FR-6, FR-7, FR-9»

| 套件 | 期望 | 实际文件 | serves |
|------|------|----------|--------|
| 采集/簿记半未回归 | 全绿 | tests/capture-hook.test.ts | FR-6 |
| 两路订阅装配与响亮失败 | 全绿 | tests/dive-session-driver-wiring.test.ts | FR-6, FR-11 |
| idle 驱动点/节点结算 | 全绿 | tests/isolate-node-context.test.ts | FR-6 |
| 断点补写 | 全绿 | tests/interruption-checkpoint.test.ts | FR-9 |
| 类型检查 | 错误数 ≤ 改动前基线 | (tsc --noEmit) | FR-7 |

## 验收口径（命令与期望输出） «serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11»

主命令：

```bash
cd agent-dh/packages/web/dsh-pmboard && npx vitest run tests/dive-manager-alignment.test.ts
```

期望：`Test Files  1 passed`，`Tests` 数 ≥ 11 且 `failed 0`（每个 FR 至少一条断言；FR-11 为跨路径留痕断言）。

回归：

```bash
cd agent-dh/packages/web/dsh-pmboard && npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts
npx tsc --noEmit -p tsconfig.json     # 包级错误数不得高于改动前基线
```

期望：三个套件 `passed`、`failed 0`；tsc 错误数不超过改动前基线（改动前先把基线错误数记录下来作为对照）。

## 边界与反例（刻意不测） «serves: FR-6, FR-8»

- **不测「长期不空闲时改到别处跑」**：不空闲就不跑是目标行为，不存在兜底路径可测。
- **不测真实 DSH agent loop 端到端**：监听器形状用 fake 端口覆盖；真实宿主行为由回归套件与线上重启验证（见 architecture §迁移）。
- **不测 arming 流程**：本轮不改「谁来 armed」的语义，测试直接在 fake 台账构造 `armed+active`。
