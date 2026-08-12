# T2 (W1.5b) 实施总结 - Agent 侧周日蒸馏任务

**工单**: docs/superpowers/plans/2026-08-12-execution-tickets.md T2（W1.5b）
**完成时间**: 2026-08-12
**状态**: ✅ 已完成

## 实施内容

### 1. 任务定义文件
- **文件**: [agent-ts/src/services/scheduler/tasks/memory-distill-task.ts](../../agent-ts/src/services/scheduler/tasks/memory-distill-task.ts)
- **内容**: `WEEKLY_MEMORY_DISTILL_PROMPT` - 周日蒸馏任务提示词
- **功能**: 
  - 第一步：调用 `runQuantV2('memory_distill_inputs', { days: 7 })` 获取输入
  - 第二步：基于输入蒸馏规则候选（必须附 evidence_ids）
  - 第三步：调用 `runQuantV2('memory_distill_candidates', { candidates })` 提交
  - 第四步：用 `decision_record` 汇报结果

### 2. 任务注册
- **文件**: [agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts](../../agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts)
- **修改**: 新增 `weekly_memory_distill` 任务
  - **调度**: `0 21 * * 0` (每周日 21:00)
  - **类型**: `agent_turn`
  - **位置**: 在 `weekly_evolution` (20:00) 之后，避免冲突

### 3. 命令映射注册
- **文件**: [agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts](../../agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts)
- **修改**: 在 `V2_ROUTES` 中新增：
  ```typescript
  "memory_distill_inputs":     { path: "/api/memory/distill/inputs",     method: "GET" },
  "memory_distill_candidates": { path: "/api/memory/distill/candidates", method: "POST" },
  ```

### 4. 任务摘要列表
- **文件**: [agent-ts/src/services/scheduler/init-agent-tasks.ts](../../agent-ts/src/services/scheduler/init-agent-tasks.ts)
- **修改**: 在任务摘要过滤器中新增 `weekly_memory_distill`

### 5. 单元测试
- **文件**: [agent-ts/src/services/memory/distill-task.test.ts](../../agent-ts/src/services/memory/distill-task.test.ts)
- **测试覆盖**:
  - ✅ 正确调用 `memory_distill_inputs` (days=7)
  - ✅ 正确调用 `memory_distill_candidates` 提交候选
  - ✅ 空候选数组处理
  - ✅ 无证据候选跳过逻辑
  - ✅ API 错误处理
- **结果**: 5/5 测试通过

### 6. 验证脚本
- **文件**: [agent-ts/scripts/verify-distill-task.ts](../../agent-ts/scripts/verify-distill-task.ts)
- **功能**: 端到端验证蒸馏流程
- **验证结果**:
  - ✅ 成功获取输入数据 (4 episodes, 51 decisions)
  - ✅ 成功提交候选 (saved: 1, skipped: 0)
  - ✅ 数据库记录验证通过 (source='distiller', status='testing')

## 验收标准

### ✅ 代码质量
- `npm test -- --testPathPattern "distill-task"` → 5/5 通过
- `npm run check:tool-refs` → 全部通过

### ✅ API 集成
- GET `/api/memory/distill/inputs?days=7` → 返回 episodes 和 decisions
- POST `/api/memory/distill/candidates` → 保存候选到数据库

### ✅ 数据库验证
```sql
SELECT id,title,status,source FROM quant.memory_entries WHERE source='distiller' ORDER BY id DESC LIMIT 5;
```
结果显示新记录已正确插入（status='testing', source='distiller'）

## 部署步骤

### 1. Agent 重启
```bash
cd agent-ts
# 重启 agent 以加载新任务定义
npm run dev
```

### 2. 任务初始化
```bash
# 在 agent REPL 中执行
node src/services/scheduler/init-agent-tasks.ts
```
或者等待 agent 启动时自动加载。

### 3. 手动触发测试（可选）
```bash
# 在 agent REPL 中手动触发任务
# 或等待周日 21:00 自动执行
```

## 遗留事项

**无** - T2 已按计划完成。

## 依赖关系

- **依赖**: T1 (W1.5a) - Backend API 已实现 ✅
- **被依赖**: 无

## 参考

- **设计文档**: docs/superpowers/plans/2026-08-12-execution-tickets.md
- **Backend API**: quantsys-v2/adapters/inbound/fastapi_app/routes/memory_distill_async.py
- **Backend 测试**: quantsys-v2/tests/domain/memory/test_distill_routes.py
