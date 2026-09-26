# 测试策略

**需求**: REQ-260925234037-1503  
**版本**: 1.0  
**更新**: 2026-09-25



### 工具删除验证测试 `serves: FR-1`


#### TC-1.1: 工具目录删除验证 `serves: FR-1`

**测试目的**：确认工具目录已完全删除

**测试步骤**：
```bash
# 验证目录不存在
! test -d packages/web/dsh-pmboard/src/tools/DecomposeTool
! test -d packages/web/dsh-pmboard/src/tools/MoveTool
! test -d packages/web/dsh-pmboard/src/tools/TaskMoveTool

# 验证 use-case 文件不存在
! test -f packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts
! test -f packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts
! test -f packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts
```

**期望结果**：所有命令返回成功（exit 0）


#### TC-1.2: 工具注册清理验证 `serves: FR-1`

**测试目的**：确认工具已从注册表移除

**测试步骤**：
```bash
# 验证 tools/index.ts 不包含已删除工具
! grep -q 'defineDecomposeTool' packages/web/dsh-pmboard/src/tools/index.ts
! grep -q 'defineMoveTool' packages/web/dsh-pmboard/src/tools/index.ts
! grep -q 'defineTaskMoveTool' packages/web/dsh-pmboard/src/tools/index.ts
```

**期望结果**：grep 无匹配（exit 1）


#### TC-1.3: 工具调用错误测试 `serves: FR-1`

**测试目的**：确认已删除工具调用返回正确错误

**测试方法**：运行时测试

**测试步骤**：
```typescript
// 尝试调用已删除工具
try {
  await tools.reqboard_decompose({ requirement_id: 'test' })
  throw new Error('应该抛出错误')
} catch (error) {
  assert(error.message.includes('unknown tool'))
  assert(error.message.includes('reqboard_decompose'))
}
```

**期望结果**：抛出 "unknown tool: reqboard_decompose" 错误



### Dive Armed 默认化测试 `serves: FR-2`


#### TC-2.1: reqboard_create 固定 armed 测试 `serves: FR-2`

**测试目的**：确认创建需求固定为 armed

**测试步骤**：
```typescript
const result = await tools.reqboard_create({
  title: 'Test Requirement',
  category: 'feature'
})

const req = await getRequirement(result.requirement_id)
assert(req.dive.activation === 'armed')
assert(req.dive.phase === 'idle')
assert(req.dive.roundsInStage === 0)
```

**期望结果**：dive.activation 固定为 'armed'


#### TC-2.2: dive_mode 参数移除测试 `serves: FR-2`

**测试目的**：确认 dive_mode 参数已移除

**测试步骤**：
```typescript
// 传递 dive_mode 参数应该被忽略或报错
const result = await tools.reqboard_create({
  title: 'Test Requirement',
  category: 'feature',
  dive_mode: 'disarmed'  // 已移除的参数
})

// 验证仍然创建为 armed
const req = await getRequirement(result.requirement_id)
assert(req.dive.activation === 'armed')
```

**期望结果**：
- 选项1：参数被忽略，创建为 armed
- 选项2：返回参数错误


#### TC-2.3: reqboard_capture 固定 armed 测试 `serves: FR-2`

**测试目的**：确认立项弹框创建的需求为 armed

**测试方法**：集成测试（需要人工或模拟弹框）

**测试步骤**：
1. 调用 reqboard_capture
2. 在弹框中填写必填项（不包含 dive_mode）
3. 确认创建
4. 验证创建的需求为 armed

**期望结果**：dive.activation = 'armed'



### 工具提示词优化测试 `serves: FR-3`


#### TC-3.1: reqboard_task_run 提示词验证 `serves: FR-3`

**测试目的**：确认提示词包含 Dive Armed 说明

**测试步骤**：
```bash
# 验证提示词文件包含关键说明
grep -q 'Dive Armed' packages/web/dsh-pmboard/src/tools/TaskExecuteTool/prompt.ts
grep -q '核心执行入口' packages/web/dsh-pmboard/src/tools/TaskExecuteTool/prompt.ts
```

**期望结果**：grep 有匹配（exit 0）


#### TC-3.2: reqboard_clear_pause 提示词验证 `serves: FR-3`

**测试目的**：确认提示词包含 break glass 说明

**测试步骤**：
```bash
grep -q 'break glass' packages/web/dsh-pmboard/src/tools/ClearPauseTool/prompt.ts
grep -q '紧急干预' packages/web/dsh-pmboard/src/tools/ClearPauseTool/prompt.ts
```

**期望结果**：grep 有匹配（exit 0）


#### TC-3.3: reqboard_status dive 状态显示测试 `serves: FR-3`

**测试目的**：确认 status 返回 dive 状态

**测试步骤**：
```typescript
const status = await tools.reqboard_status({})
const req = status.open_requirements[0]

assert(req.dive !== undefined)
assert(req.dive.activation === 'armed')
assert(['idle', 'active', 'paused'].includes(req.dive.phase))
assert(typeof req.dive.roundsInStage === 'number')
```

**期望结果**：返回完整 dive 状态



### 错误提示优化测试 `serves: FR-4`


#### TC-4.1: 友好错误消息测试 `serves: FR-4`

**测试目的**：确认工具调用错误返回友好提示

**测试步骤**：
```typescript
try {
  await tools.reqboard_decompose({ ... })
} catch (error) {
  assert(error.message.includes('已删除'))
  assert(error.message.includes('reqboard_task_run'))
  assert(error.message.includes('Dive Armed'))
}
```

**期望结果**：错误消息包含引导信息



### 文档清理测试 `serves: FR-5`


#### TC-5.1: 手动模式文档删除验证 `serves: FR-5`

**测试目的**：确认手动模式文档已删除

**测试步骤**：
```bash
# 验证文档不包含 disarmed 说明
! grep -r 'disarmed' docs/guides/dive-mode-usage.md
! grep -r 'armed vs disarmed' docs/guides/dive-mode-usage.md
! grep -r '手动模式' docs/guides/dive-mode-usage.md

# 验证文档包含 Dive Armed 说明
grep -q 'Dive Armed' docs/guides/dive-mode-usage.md
grep -q '唯一工作方式' docs/guides/dive-mode-usage.md
```

**期望结果**：
- 不包含 disarmed 相关内容
- 包含 Dive Armed 说明



### accepting 配置修复测试 `serves: FR-6`


#### TC-6.1: autoExecute 配置验证 `serves: FR-6`

**测试目的**：确认 accepting.autoExecute = true

**测试步骤**：
```bash
# 验证配置文件
grep -A 4 'accepting:' packages/web/dsh-pmboard/src/application/dive/stage-configs.ts | grep 'autoExecute: true'
```

**期望结果**：grep 有匹配（exit 0）


#### TC-6.2: 验收自动归档集成测试 `serves: FR-6`

**测试目的**：确认验收通过后自动归档

**测试方法**：E2E 测试

**测试步骤**：
1. 创建测试需求（armed）
2. 完成全流程到 accepting 阶段
3. 提交验收材料并通过
4. 验证需求自动推进到 archived

**期望结果**：
- 验收通过后无需手动调用 move
- 需求状态自动变为 archived

## E2E 测试 <!-- serves: FR-1, FR-2, FR-6 -->


### E2E-1: 完整 Dive Armed 流程测试 `serves: FR-2`

**测试目的**：验证完整的 Dive Armed 工作流程

**测试步骤**：

1. **创建需求**
```typescript
const result = await tools.reqboard_create({
  title: 'E2E Test Feature',
  category: 'feature'
})
// 验证：dive.activation = 'armed'
```

2. **需求分析阶段**
```typescript
// 编写需求文档
await tools.reqboard_submit({ kind: 'requirement', ... })
await tools.reqboard_ask_confirm({ target: 'artifact', kind: 'requirement' })
// 验证：自动推进到 design
```

3. **设计阶段**
```typescript
// 编写设计文档
await tools.reqboard_submit({ kind: 'design', ... })
await tools.reqboard_ask_confirm({ target: 'artifact', kind: 'design' })
// 验证：自动推进到 decomposing
```

4. **拆分阶段**
```typescript
// 编写拆分计划
await tools.reqboard_submit({ kind: 'plan', ... })
await tools.reqboard_ask_confirm({ target: 'plan' })
// 验证：自动拆分并推进到 implementing
```

5. **实施阶段**（关键：不使用已删除工具）
```typescript
// 使用 task_run 执行任务
await tools.reqboard_task_run({ task_id: '...' })
// 验证：父子卡自动执行
// 验证：任务完成后自动推进到 accepting
```

6. **验收阶段**
```typescript
// 提交验收材料
await tools.reqboard_submit({ kind: 'verification', ... })
// 人工验收通过
// 验证：自动推进到 archived（FR-6）
```

**期望结果**：
- ✅ 全流程无需调用 decompose/move/task_move
- ✅ 只使用 task_run 完成任务执行
- ✅ 验收通过自动归档


### E2E-2: 错误恢复测试 `serves: FR-4`

**测试目的**：验证 clear_pause 紧急干预

**测试步骤**：
1. 创建需求并推进到 implementing
2. 模拟执行异常（任务失败）
3. Dive 流程暂停（phase = paused）
4. 调用 clear_pause 恢复
5. 验证流程继续

**期望结果**：
- ✅ clear_pause 成功恢复
- ✅ 流程继续执行

## 性能测试 <!-- serves: FR-1 -->


### PERF-1: 工具加载性能 `serves: FR-1, FR-2`

**测试目的**：确认删除工具后加载更快

**测试方法**：
```bash
# 测量工具加载时间
time node packages/web/dsh-pmboard/dist/index.js
```

**期望结果**：
- 加载时间减少（工具数量从 17 → 14）
- 内存占用减少

## 回归测试 <!-- serves: FR-1, FR-2, FR-3 -->


### REGR-1: 现有需求兼容性测试 `serves: FR-1, FR-2, FR-3`

**测试目的**：确认现有需求不受影响

**测试步骤**：
1. 查询现有 disarmed 需求
2. 验证读取正常
3. 验证状态推进正常（如果处于进行中）

**期望结果**：
- ✅ 现有需求数据完整
- ✅ disarmed 需求正常工作


### REGR-2: 保留工具功能测试 `serves: FR-1, FR-2, FR-3`

**测试目的**：确认保留工具功能不变

**测试清单**：
- ✅ reqboard_create 正常创建
- ✅ reqboard_capture 正常立项
- ✅ reqboard_status 正常查询
- ✅ reqboard_task_run 正常执行
- ✅ reqboard_submit 正常提交
- ✅ reqboard_ask_confirm 正常确认
- ✅ reqboard_accept_sheet 正常验收

**期望结果**：所有保留工具功能不变

## 测试执行计划 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 -->


### 单元测试 `serves: FR-1, FR-2`
- 工具删除验证（TC-1.x）
- 接口变更测试（TC-2.x）
- 配置验证（TC-6.1）


### 集成测试 `serves: FR-1, FR-2`
- 提示词验证（TC-3.x）
- 错误提示测试（TC-4.x）
- 验收自动归档（TC-6.2）


### E2E 测试 `serves: FR-1, FR-2, FR-6`
- 完整流程测试（E2E-1）
- 错误恢复测试（E2E-2）


### 回归测试 `serves: FR-1, FR-2, FR-3`
- 现有需求兼容性（REGR-1）
- 保留工具功能（REGR-2）


### 性能测试 `serves: FR-1, FR-2`
- 工具加载性能（PERF-1）

## 验收标准 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 -->


### 必须通过的测试 `serves: FR-1, FR-2`

1. **工具删除验证**（TC-1.x）：全部通过
2. **Dive Armed 默认化**（TC-2.x）：全部通过
3. **accepting 配置修复**（TC-6.x）：全部通过
4. **E2E 完整流程**（E2E-1）：全部通过
5. **回归测试**（REGR-x）：全部通过


### 可选测试 `serves: FR-1, FR-2`

- 性能测试（PERF-1）：参考数据
- 错误恢复测试（E2E-2）：验证 clear_pause 功能

## 测试环境 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 -->


### 环境准备 `serves: FR-1, FR-2`

```bash
# 1. 构建项目
cd agent-dh
pnpm build

# 2. 启动服务
./scripts/start.sh --port 13081

# 3. 准备测试数据
# 创建测试需求、任务等
```


### 清理 `serves: FR-1, FR-2`

```bash
# 删除测试数据
# 恢复环境
```