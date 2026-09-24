# Workflow-PTC 修复指南

## 问题总结

PM 插件 (dsh-pmboard) 的自动任务执行链依赖 `workflow-ptc` 服务，但当前运行时 `ctx.workflowEngine` 服务不可用，导致所有子卡执行失败：

```
stopReason=engine_unavailable
```

## 根本原因

1. **dsh-web-app bundle 默认禁用** `workflow-ptc`
2. **配置覆盖顺序问题**：配置加载顺序是 base → bundle → profile，profile 中的 `disabled: false` 可能没有生效
3. **服务注入依赖**：`PtcWorkflowEngine` 继承 `WorkflowEngine`，应该提供 `workflowEngine` 服务，但实际未注入

## 🔧 修复方案

### 方案 A：立即修复（推荐，5分钟）

```bash
cd /Users/yunpeng/pi-investment/agent-dh

# 1. 确认配置正确
grep -A 2 "workflow-ptc" .dsh-data/profiles/agent-dh/cordis.patch.yml

# 应该显示：
# - id: workflow-ptc
#   disabled: false

# 2. 如果没有或 disabled: true，手动修改
# 编辑 .dsh-data/profiles/agent-dh/cordis.patch.yml
# 找到 workflow-ptc 行，确保 disabled: false

# 3. 重启服务
./scripts/restart-with-build.sh

# 4. 等待服务启动完成（约30秒）

# 5. 验证（在浏览器或 curl）
curl -s http://localhost:13080/api/plugins | python3 -m json.tool | grep -A 5 workflow-ptc

# 或在 Agent 会话中检查：
# reqboard_status()
# 应该看到 workflow engine 相关信息
```

### 方案 B：检查 Agent Preset 覆盖

```bash
# Agent preset 可能覆盖了配置
# 检查 investment preset
cat .dsh-data/.agent-presets/investment/cordis.patch.yml 2>/dev/null
cat config/agent-presets/investment/cordis.patch.yml 2>/dev/null

# 如果 preset 中也有 workflow-ptc 且 disabled: true
# 需要在 preset 中也改为 false
```

### 方案 C：临时降级方案（workflow 无法修复时）

如果 workflow-ptc 确实无法启用，可以修改 pmboard 使用简化执行模式：

```typescript
// packages/web/dsh-pmboard/src/application/use-cases/ExecuteTask.ts

// 在 executeSubtask 函数中添加降级逻辑：
async function executeSubtask(deps, input) {
  // 检测 workflow engine 可用性
  if (deps.workflow === undefined || workflowEngineSvc === undefined) {
    // 降级：直接执行任务，不走 subagent
    return await executeTaskDirectly(deps, input);
  }
  
  // 正常流程...
}

// 简化执行函数
async function executeTaskDirectly(deps, input) {
  // 1. 读取任务卡
  // 2. 调用相关工具
  // 3. 生成 report
  // 4. 返回结果
}
```

## 📊 验证步骤

### 1. 检查服务加载

```bash
# 查看服务器日志
tail -100 .dsh-data/state/server.log | grep -i "workflow"

# 应该看到：
# [INFO] workflow-ptc plugin loaded
# [DEBUG] workflowEngine service ready
```

### 2. 测试 API

```bash
curl -s http://localhost:13080/api/plugins | grep -A 10 workflow-ptc

# 应该返回：
# {
#   "id": "workflow-ptc",
#   "name": "@deepseek-ai/dsh-workflow-ptc",
#   "disabled": false,
#   ...
# }
```

### 3. 运行测试需求

创建一个简单的测试需求：

```
1. 在 PM 看板创建需求
2. 进入 implementing 阶段
3. 创建一个简单任务（如"打印 hello world"）
4. 触发 reqboard_task_run
5. 观察 docs/requirements/REQ-xxx/advance-log.md

# 成功标志：
- [RUN_SUBTASK] ... ok：子卡 done
- 不再出现 engine_unavailable
```

## 🎯 预期结果

修复后的完整执行流程：

```
1. 需求进入 implementing (autoRun=true)
   ↓
2. AdvanceChain 自动循环
   ↓
3. OPEN_PARENT → 父卡开工，展开4张子卡
   ↓
4. RUN_SUBTASK → 调用 workflow.start
   ↓
5. PtcWorkflowEngine 启动独立 workflow run
   ↓
6. 子代理在独立上下文执行任务
   ↓
7. 返回结构化产出 (filesChanged/completed/evidence)
   ↓
8. 凭证门校验通过
   ↓
9. 子卡 → done
   ↓
10. 重复 4-9 直到所有子卡完成
   ↓
11. FINALIZE_PARENT → 父卡收尾
   ↓
12. ROLLUP → implementing → accepting
```

## 🚨 常见问题

### Q1: 重启后仍然 engine_unavailable

**A:** 检查以下几点：

1. `cordis.patch.yml` 是否真的被修改并保存
2. 是否使用了正确的重启脚本（`restart-with-build.sh`）
3. 查看日志是否有加载错误
4. 检查 preset 是否覆盖了配置

### Q2: 看到 "Cannot read 'session'"

**A:** 这是 workflow 脚本中访问 `ctx.session` 导致的。需要确保：

1. workflow-ptc 版本 >= 0.1.6-alpha.2
2. pmboard 生成的 workflow 脚本正确
3. subagent provider 配置正确

### Q3: workflow 执行被 cancelled

**A:** 可能是超时或手动中断。检查：

1. `workflow-ptc` 配置中的 `syncTimeoutMs`
2. 任务是否过于复杂
3. 是否有其他进程中断了执行

## 📝 配置参考

### 完整的 workflow-ptc 配置

```yaml
- id: workflow-ptc
  disabled: false
  config:
    provider: default
    maxConcurrentAgents: 4  # 并发子代理数
    maxTotalAgents: 16      # 总子代理数上限
    maxItemsPerCall: 100
    syncTimeoutMs: 120000   # 2分钟超时
```

### PMBoard 的依赖配置

```typescript
// packages/web/dsh-pmboard/src/index.ts
ctx.inject(['workflowEngine'], (wfCtx) => {
  workflowEngineSvc = wfCtx?.workflowEngine;
  logger.debug(
    workflowEngineSvc === undefined
      ? 'workflowEngine service 不可用（子卡执行将显式失败）'
      : 'workflowEngine service ready (reqboard_task_run 子卡执行可用)'
  );
});
```

## 🔍 调试技巧

### 1. 启用详细日志

```bash
# 启动时加 --verbose 参数
./scripts/start.sh --verbose
```

### 2. 实时监控日志

```bash
tail -f .dsh-data/state/server.log | grep -i "workflow\|engine\|pmboard"
```

### 3. 检查 advance-log.md

```bash
# 查看最近的需求执行日志
find docs/requirements -name "advance-log.md" -exec tail -20 {} \;
```

## 📚 相关文档

- RFC 014: Requirement Board
- docs/architecture/workflow-stages.md
- docs/architecture/pmboard-code-flow.md
- packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts

---

**最后更新**: 2024-01-XX
**维护者**: PM 插件团队
