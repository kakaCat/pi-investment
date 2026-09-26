---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9]
---

# 用例设计（REQ-260925110957-552d）

> 端到端场景、用户旅程、边界情况。

## 用例 1：正常投递与完成 <!-- serves: FR-1, FR-2, FR-3, FR-9 -->

**场景**：agent 投递一个父卡，链在后台跑完，收到通知。

**前置条件**：
- 需求处于 implementing 状态
- 父卡 status=todo，有 3 张子卡（全部 todo）
- `ctx.jobs` 可用，`deps.workflow` 可用

**步骤**：

1. **agent 调用工具**
   ```typescript
   const r = await tools.reqboard_task_run({ task_id: 't-parent1' });
   ```

2. **立即返回（< 1s）**
   ```json
   {
     "success": true,
     "dispatched": true,
     "job_id": "reqboard-1",
     "run_id": "550e8400-e29b-41d4-a716-446655440000",
     "requirement_id": "REQ-abc123",
     "task_id": "t-parent1",
     "running": [],
     "next_ready": ["t-sub1", "t-sub2", "t-sub3"]
   }
   ```

3. **agent 继续工作**（不等链跑完）
   - 可用 `job_list` 查看后台任务
   - 可用 `reqboard_run_status` 查询进度

4. **链在后台循环**
   - 开工父卡（OPEN_PARENT）
   - 按写集分批跑子卡（RUN_SUBTASK，批内并发）
   - 每步写 checkpoint 到台账
   - 全部子卡完成 → 收尾父卡（FINALIZE_PARENT）
   - 全部父卡完成 → 需求进验收（ROLLUP）

5. **完成通知**（agent 收到）
   ```
   background job reqboard-1 (reqboard: REQ REQ-abc123) finished [status: completed]
   Done; job_output.
   ```

6. **agent 读取结果**
   ```typescript
   const out = await tools.job_output({ job_id: 'reqboard-1' });
   // 链已跑完，需求已进验收
   ```

**后置条件**：
- 父卡 status=done
- 3 张子卡全部 done
- 需求 status=accepting
- 台账 `advance.runId` 保留（历史查询用）

**验收**：A1（< 1s 返回）、A2（收到通知）、A9（台账有运行态）。

---

## 用例 2：查询运行态 <!-- serves: FR-2, FR-9 -->

**场景**：agent 投递后想知道「跑到哪了」。

**步骤**：

1. **投递**
   ```typescript
   const r = await tools.reqboard_task_run({ task_id: 't-parent1' });
   const runId = r.run_id;
   ```

2. **查询运行态**（立即查询，不等跑完）
   ```typescript
   const status = await tools.reqboard_run_status({ run_id: runId });
   ```

3. **返回快照**
   ```json
   {
     "requirement_id": "REQ-abc123",
     "run_id": "550e8400-...",
     "status": "running",
     "current_step": 5,
     "current_subtask": "t-sub2",
     "next_ready": ["t-sub3"],
     "job_status": "running",
     "heartbeat_at": 1695012345678
   }
   ```

4. **解读**
   - 链正在跑（status=running）
   - 当前第 5 步，在执行 t-sub2
   - 下一批 ready 子卡是 t-sub3
   - 原生 job 状态也是 running
   - 最后心跳 1 秒前（健康）

**验收**：A2（运行态可查）、A9（台账有 runId/stepIndex/currentSubtaskId）。

---

## 用例 3：中断后恢复 <!-- serves: FR-3, FR-5, FR-6 -->

**场景**：链跑到一半，进程崩溃（或调用方 abort），重启后链继续。

**步骤**：

1. **投递并跑到一半**
   ```typescript
   const r = await tools.reqboard_task_run({ task_id: 't-parent1' });
   // 链开始跑，子卡 t-sub1 进入 in_progress
   ```

2. **模拟崩溃**（进程重启，或调用方 abort）
   - 子卡 t-sub1 status=in_progress，但无活跃执行记录
   - 台账 `advance.heartbeatAt` 停留在崩溃前

3. **启动恢复扫描**（profile 启动时自动触发）
   ```typescript
   await scanAndResume(deps);
   ```

4. **孤儿识别与回收**
   - 选择器识别 t-sub1 为孤儿（`now - claimedAt > 15min && !hasActiveExecution`）
   - 事件 = RECLAIM_ORPHAN
   - t-sub1 退回 todo + attempt+1

5. **链继续**
   - 下一次选择器选中 t-sub1（已回到 todo）
   - 重新执行 t-sub1
   - 链正常走到 ROLLUP

**后置条件**：
- t-sub1 status=done，attempt=1（第二次尝试成功）
- 链没有停摆（noopStreak 未累到 5）
- 需求进验收

**验收**：A3（中断后续跑不卡）、A4（恢复扫描不 start_failed）、A5（孤儿被回收）。

---

## 用例 4：写集并行 <!-- serves: FR-4, FR-5 -->

**场景**：两张写集不交的子卡并行执行（时间窗重叠）。

**前置条件**：
- 父卡有 3 张子卡：
  - t-sub1：`filesPlanned: ['src/a.ts']`
  - t-sub2：`filesPlanned: ['src/b.ts']`（与 t-sub1 不冲突）
  - t-sub3：`filesPlanned: ['src/a.ts']`（与 t-sub1 冲突）

**步骤**：

1. **投递**
   ```typescript
   await tools.reqboard_task_run({ task_id: 't-parent1' });
   ```

2. **选择器分批**
   - 第一批：t-sub1, t-sub2（写集不交，可并行）
   - 第二批：t-sub3（与第一批冲突，等第一批完成）

3. **第一批并行执行**
   - 引擎调用 `parallel([agent(prompt1), agent(prompt2)])`
   - t-sub1 与 t-sub2 的执行时间窗**重叠**

4. **第二批串行执行**
   - 第一批完成后，选择器选中 t-sub3
   - t-sub3 在 t-sub1 完成**之后**开始

**观测**：
- t-sub1.executions[0].startedAt = 100
- t-sub1.executions[0].endedAt = 200
- t-sub2.executions[0].startedAt = 105（与 t-sub1 重叠）
- t-sub2.executions[0].endedAt = 210
- t-sub3.executions[0].startedAt = 220（在 t-sub1 之后）

**验收**：A5（时间窗重叠/不重叠）。

---

## 用例 5：写集未声明（降级） <!-- serves: FR-4 -->

**场景**：旧台账，任务无 `filesPlanned` 字段。

**前置条件**：
- 台账 `schemaVersion=7`（旧版本）
- 子卡无 `filesPlanned` 字段

**步骤**：

1. **投递**
   ```typescript
   await tools.reqboard_task_run({ task_id: 't-parent1' });
   ```

2. **选择器行为**
   - 读取 `task.filesPlanned` → undefined
   - 视作「写集未知」
   - 每张子卡单独成批（全串行，安全降级）

3. **执行**
   - 子卡一张一张跑（无并行）
   - 行为与旧版本一致

**后置条件**：
- 链跑完，结果正确
- 性能无提升（全串行），但**不出错**

**验收**：A7（旧台账读取后行为不变）。

---

## 用例 6：schema 产出 <!-- serves: FR-7 -->

**场景**：模型产出不符合 schema，引擎拒绝。

**步骤**：

1. **子卡脚本生成**（带 schema）
   ```typescript
   const script = generateSubtaskScript({
     stageKind: 'implement',
     stageLabel: '实施',
     prompt: '...'
   });
   ```

2. **脚本内容**
   ```javascript
   const out = await agent(prompt, {
     schema: {
       type: 'object',
       properties: {
         filesChanged: { type: 'array', items: { type: 'string' } },
         completed: { type: 'array', items: { type: 'string' } },
         evidence: { type: 'array', items: { type: 'string' } }
       }
     }
   });
   ```

3. **模型产出不符合**（如返回字符串而非对象）
   - 引擎 schema 校验失败
   - `outcome.ok = false`，reason 含 'schema'

4. **子卡失败**
   - `executeSubtask` 返回 `{ok: false, reason: '...schema...'}`
   - 子卡退回 todo + attempt+1
   - 链暂停（fail → pauseRequirement）

**后置条件**：
- 子卡 status=todo，attempt=1
- 需求 autoRun=false（暂停）
- agent 收到告警通知

**验收**：A6（schema 产出路径）。

---

## 用例 7：重复投递（幂等） <!-- serves: FR-1 -->

**场景**：agent 重复调用 `reqboard_task_run`（误操作或重试）。

**步骤**：

1. **第一次投递**
   ```typescript
   const r1 = await tools.reqboard_task_run({ task_id: 't-parent1' });
   expect(r1.dispatched).toBe(true);
   expect(r1.run_id).toBe('uuid-1');
   ```

2. **第二次投递**（链还在跑）
   ```typescript
   const r2 = await tools.reqboard_task_run({ task_id: 't-parent1' });
   ```

3. **返回拒绝**
   ```json
   {
     "success": false,
     "dispatched": false,
     "task_id": "t-parent1",
     "reason": "该需求已有 run 在跑（runId=uuid-1）",
     "existing_run_id": "uuid-1",
     "existing_job_id": "reqboard-1"
   }
   ```

4. **agent 行为**
   - 读取 `existing_job_id`，用 `job_output` 查询既有 job
   - 不重复投递（幂等保证）

**验收**：A1（幂等认领）。

---

## 用例 8：依赖缺失（降级） <!-- serves: FR-1 -->

**场景**：`ctx.jobs` 不可用（profile 配置错误）。

**步骤**：

1. **投递**
   ```typescript
   const r = await tools.reqboard_task_run({ task_id: 't-parent1' });
   ```

2. **返回显式失败**
   ```json
   {
     "success": false,
     "dispatched": false,
     "task_id": "t-parent1",
     "reason": "后台任务系统不可用（ctx.jobs=undefined）"
   }
   ```

3. **不静默降级**
   - **不会**回退到旧的同步执行
   - agent 收到明确错误，可报告给人

**验收**：A1（依赖缺失显式失败）。

---

## 用例 9：工具终止（job_kill） <!-- serves: FR-1, A11 -->

**场景**：agent 中途决定不跑了，用 `job_kill` 终止。

**步骤**：

1. **投递**
   ```typescript
   const r = await tools.reqboard_task_run({ task_id: 't-parent1' });
   const jobId = r.job_id;
   ```

2. **agent 决定终止**
   ```typescript
   await tools.job_kill({ job_id: jobId, reason: '需求取消' });
   ```

3. **链在下一步停下**
   - 后台循环检测 `signal.aborted`
   - 写 checkpoint（停在哪一步）
   - 返回 `{status: 'killed'}`

4. **台账落盘**
   - 需求 `advance.pausedReason = 'killed by user'`
   - 当前子卡保持原状（下次可续跑）

**后置条件**：
- job 状态 = killed
- 链停住，可恢复（不是死链）

**验收**：A11（原生 job_kill 终止）。

---

## 用例 10：看板观测 <!-- serves: FR-9 -->

**场景**：人在看板上查看链运行态。

**步骤**：

1. **agent 投递**
   ```typescript
   await tools.reqboard_task_run({ task_id: 't-parent1' });
   ```

2. **看板渲染**（HTTP 路由读台账）
   ```typescript
   GET /api/reqboard/requirements/REQ-abc123
   ```

3. **返回运行态**
   ```json
   {
     "id": "REQ-abc123",
     "status": "implementing",
     "advance": {
       "runId": "uuid-1",
       "currentSubtaskId": "t-sub2",
       "stepIndex": 5,
       "heartbeatAt": 1695012345678
     },
     "tasks": [...]
   }
   ```

4. **看板显示**
   - 需求卡片显示「运行中」徽章
   - 当前子卡高亮
   - 进度条：5 / 20 步

**验收**：A9（台账与看板可见运行态）。

---

## 边界用例 <!-- serves: FR-3, FR-5 -->

### B1: 孤儿阈值边界 <!-- serves: FR-5 -->

**场景**：子卡 in_progress 刚好 15 分钟，是否算孤儿？

**判定**：`now - claimedAt > 15min` → 严格大于，15 分钟整不算孤儿。

### B2: 空写集 <!-- serves: FR-4 -->

**场景**：`filesPlanned = []`（空数组）。

**行为**：视作「未声明」，单独成批（全串行）。

### B3: 写集规范化 <!-- serves: FR-4 -->

**场景**：`filesPlanned = ['./src/a.ts', 'src/b.ts/', 'src/c.ts']`。

**规范化**：
- 去除前导 `./`：`src/a.ts`
- 去除尾随 `/`：`src/b.ts`
- 保持：`src/c.ts`

**结果**：`['src/a.ts', 'src/b.ts', 'src/c.ts']`

### B4: 最大步数（详细说明） <!-- serves: FR-1, FR-3 -->

**场景**：链跑了 20 步还没完（大需求，5+ 父卡，每个 5-10 张子卡）。

**行为**：
- 循环退出（`for i < 20` 结束）
- 返回 `{status: 'completed', stopped: 'max_steps'}`
- 台账 `advance.pausedReason = 'max_steps_reached'`
- job 状态 = completed（不是 failed，因为是正常结束）

**续跑**：
- agent 收到完成通知，读 `stopped='max_steps'`
- 立即再次调用 `reqboard_task_run`（幂等检查放行，因为前一个 run 已终止）
- 新 run 从当前台账状态继续（checkpoint 保证续跑点正确）

**实际容量示例**：
- 小需求（1 父卡 + 3 子卡）：1(OPEN) + 1(RUN_BATCH) + 1(FINALIZE) + 1(ROLLUP) = **4 事件**
- 中需求（2 父卡，每个 5 子卡，分 2 批）：2×(1 + 2 + 1) + 1 = **9 事件**
- 大需求（5 父卡，每个 8 子卡，分 3 批）：5×(1 + 3 + 1) + 1 = **26 事件** → 需 2 次 run

**注意**：批次计数是关键
- 写集并行后，一批算一个 RUN_SUBTASK 事件（不是批内每张卡都算）
- 10 张子卡全不冲突 → 1 批 → 1 事件
- 10 张子卡全冲突 → 10 批 → 10 事件

### B5: 全部子卡 canceled <!-- serves: FR-3, FR-5 -->

**场景**：父卡 in_progress，子卡全部 canceled。

**行为**：
- 选择器选中 FINALIZE_PARENT
- 父卡收尾（filesChanged = []）
- 父卡 done

---

## 用例 11：超大需求分段续跑 <!-- serves: FR-1, FR-3 -->

**场景**：需求有 5 个父卡，每个 8 张子卡，总共需要 26 个事件（超出 20 步上限）。

**前置条件**：
- 需求 status=implementing
- 5 个父卡，每个 8 张子卡（写集分 3 批）
- 预计事件数：5×(1 OPEN + 3 RUN_SUBTASK + 1 FINALIZE) + 1 ROLLUP = 26

**步骤**：

1. **第一次投递**
   ```typescript
   const r1 = await tools.reqboard_task_run({ task_id: 't-parent1' });
   ```

2. **跑了 20 步后停下**
   - 完成：3 个父卡（每个 5 事件）+ 部分第 4 个父卡 = 20 事件
   - 返回：`{status: 'completed', stopped: 'max_steps'}`
   - job 状态：completed（不是 failed）

3. **agent 收到通知**
   ```
   background job reqboard-1 finished [status: completed]
   stopped: max_steps_reached (跑了 20 步上限，需续跑)
   ```

4. **agent 立即续跑**
   ```typescript
   const r2 = await tools.reqboard_task_run({ task_id: 't-parent1' });
   // 幂等检查：前一个 run 已终止 → 允许新 run
   ```

5. **第二次 run 从断点继续**
   - 选择器从当前台账状态开始（第 4 个父卡的剩余子卡）
   - 再跑 6 步完成剩余工作
   - 返回：`{status: 'completed', stopped: 'rollup'}`

**后置条件**：
- 全部 5 个父卡 done
- 需求 status=accepting
- 总共 2 次 run，无人工干预

**验收**：
- 第一次 run 正常终止（不报错）
- 第二次 run 能立即投递（幂等检查放行）
- 台账 checkpoint 保证续跑点正确

---

## 用户旅程总结 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

### 投递 → 通知 → 查询（正常路径） <!-- serves: FR-1, FR-2, FR-3 -->

1. agent 调 `reqboard_task_run` → < 1s 返回 `{dispatched, job_id, run_id}`
2. agent 继续工作（不等链跑完）
3. 链在后台跑（按写集分批并行）
4. 跑完后 agent 收到 notice
5. agent 用 `job_output` 读结果

### 中断 → 恢复（容错路径） <!-- serves: FR-3, FR-5, FR-6 -->

1. 链跑到一半，进程崩溃
2. 子卡孤儿（in_progress 但无活跃执行）
3. 重启后 `scanAndResume` 触发恢复
4. 孤儿被回收（退回 todo）
5. 链继续跑到 ROLLUP

### 查询 → 终止（主动干预） <!-- serves: FR-2 -->

1. agent 投递后想知道进度 → 调 `reqboard_run_status`
2. 看到「跑到第 5 步，在执行 t-sub2」
3. 决定不等了 → 调 `job_kill`
4. 链在下一步停下并落台账