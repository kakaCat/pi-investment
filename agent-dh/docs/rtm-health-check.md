# RTM 健康检查与失败提醒功能

## 问题
之前 RTM（Requirements Traceability Matrix，需求追溯矩阵）生成失败时只打印 `console.warn`，没有明显的错误提示，导致：
- 用户不知道 RTM 文件缺失
- 无法追踪生成失败的原因
- 后续操作时才发现问题，难以定位

## 解决方案
实现了完整的 RTM 健康检查和失败提醒机制：

### 1. 失败记录（`state/rtm-failures.json`）
RTM 生成失败时自动记录到 `.dsh-data/state/rtm-failures.json`：
```json
[
  {
    "requirement_id": "REQ-260926205654-163a",
    "trigger": "create",
    "timestamp": 1727366400000,
    "error": "deps.docs.workspaceRoot is not a function",
    "attempts": 3
  }
]
```

### 2. 健康检查（`reqboard_status` 返回 `rtm_health`）
查询需求状态时自动检查 RTM 文件完整性：

```typescript
{
  "rtm_health": {
    "healthy": false,
    "missing_files": ["rtm-lifecycle.yml", "rtm-brainstorming.yml"],
    "last_failure": {
      "trigger": "create",
      "error": "deps.docs.workspaceRoot is not a function",
      "timestamp": 1727366400000,
      "attempts": 3
    },
    "retry_available": false  // 失败次数>=3 时禁用重试
  }
}
```

### 3. 自动清除（成功后清理失败记录）
RTM 生成成功后自动清除该需求的失败记录。

## 使用方式

### Agent 使用
调用 `reqboard_status` 查看需求状态时，会自动包含 `rtm_health` 字段：

```javascript
const status = await tools.reqboard_status()

if (status.rtm_health && !status.rtm_health.healthy) {
  console.log("⚠️ RTM 文件不完整：")
  console.log("缺失文件：", status.rtm_health.missing_files)
  
  if (status.rtm_health.last_failure) {
    console.log("最近失败：", status.rtm_health.last_failure.error)
    console.log("失败次数：", status.rtm_health.last_failure.attempts)
  }
  
  if (status.rtm_health.retry_available) {
    console.log("✅ 可以重试修复")
    // 可以尝试重新提交产物来触发 RTM 生成
  } else {
    console.log("❌ 失败次数过多，需要人工介入")
  }
}
```

### 人工查看
查看失败记录：
```bash
cat .dsh-data/state/rtm-failures.json | jq
```

### 手动修复
如果 RTM 生成一直失败，可以手动检查：
1. 需求目录是否存在：`docs/requirements/REQ-xxx/`
2. 错误日志：查看 `console.warn` 输出
3. 依赖是否正常：`deps.docs` 和 `deps.repo` 是否注入

## 触发点
RTM 生成会在以下时机自动触发：
- 立项（`reqboard_create`/`reqboard_capture`）
- 提交需求文档（`reqboard_submit(kind=requirement)`）
- 提交设计文档（`reqboard_submit(kind=design)`）
- 确认产物（`reqboard_ask_confirm(target=artifact)`）
- 批准计划（`reqboard_ask_confirm(target=plan)`）
- 提交验收材料（`reqboard_submit(kind=verification)`）

## 文件说明
- `packages/web/dsh-pmboard/src/application/internal/rtm-health.ts` - 健康检查模块
- `packages/web/dsh-pmboard/src/application/internal/rtm-yaml.ts` - 失败记录逻辑
- `packages/web/dsh-pmboard/src/application/query/QueryState.ts` - 状态查询集成
- `.dsh-data/state/rtm-failures.json` - 失败记录文件（运行时生成）

## 测试
```bash
cd packages/web/dsh-pmboard
pnpm test rtm-health.test.ts
```

## 限制
- 只保留最近 100 条失败记录
- 连续失败 3 次后标记为不可重试（需要人工介入）
- 失败记录在成功生成后自动清除
