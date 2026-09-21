# REQ-f6307c 拆分计划 · 修复 Agent 多次跳过立项弹框的问题

## 一、改动盘点

### 1.1 新增文件
无新增文件（仅修改现有代码）

### 1.2 修改文件

#### (1) src/index.ts（节点1：Hook 订阅）
- **改动位置**：第 233-312 行（Hook 订阅与装配区域）
- **改动内容**：添加订阅成功检查日志
- **改动类型**：新增日志输出

#### (2) src/adapters/CaptureHook.ts（节点2、节点3：事件处理）
- **改动位置**：
  - 第 164-309 行（事件处理器入口与 pendingCapture 填充）
  - handler 入口：添加事件到达日志
  - shouldCaptureWindow 调用后：添加判定结果与 pendingCapture 状态日志
- **改动内容**：添加事件触发与状态填充日志
- **改动类型**：新增日志输出

#### (3) src/gate-wiring.ts（节点4：systemPrompt 组装）
- **改动位置**：第 88-119 行（systemPrompt section 注册）
- **改动内容**：添加 windowKey 提取与 pending 状态日志
- **改动类型**：新增日志输出

#### (4) src/application/internal/capture-section.ts（节点5：提示词生成）
- **改动位置**：第 52-283 行（captureSectionText 函数）
- **改动内容**：添加最终文本长度与返回空串原因日志
- **改动类型**：新增日志输出

#### (5) 根据诊断结果修复的文件（待诊断后确定）
- 可能修复位置：
  - src/gate-wiring.ts（windowKey 提取逻辑）
  - src/adapters/CaptureHook.ts（生命周期管理）
  - src/application/internal/window.ts（判断逻辑）

### 1.3 删除文件
无删除文件

---

## 二、任务表

### T1 - 添加诊断日志（节点1-5）

**key**: t1  
**title**: 在 Hook 注入链路的 5 个关键节点添加诊断日志  
**phase**: implement  
**side**: backend
**requirement_refs**: [BUG-1]  
**depends_on**: []  

**implementation**:

1. **节点1（src/index.ts）**：Hook 订阅检查
   - 位置：`wireSystemPrompt()` 函数内，订阅返回后
   - 日志内容：订阅是否成功、返回的 dispose 函数是否存在
   - 格式：`ctx.logger('pmboard').debug('reqboard-capture: hook subscribed', { success, hasDispose })`

2. **节点2（src/adapters/CaptureHook.ts）**：事件到达检查
   - 位置：`handler` 函数入口（第一行）
   - 日志内容：`user/message` 事件是否到达、windowKey、消息文本长度
   - 格式：`this.logger.debug('reqboard-capture: user/message event received', { windowKey, textLength })`

3. **节点3（src/adapters/CaptureHook.ts）**：pendingCapture 填充检查
   - 位置：`shouldCaptureWindow` 判断后、`pending.set()` 调用后
   - 日志内容：判定结果、pendingCapture.size、当前 windowKey、消息节选
   - 格式：`this.logger.debug('reqboard-capture: capture decision', { shouldCapture, pendingSize, windowKey, textPreview })`

4. **节点4（src/gate-wiring.ts）**：systemPrompt 组装检查
   - 位置：`captureSectionText` 调用处，在 `assembleContext` 传递时
   - 日志内容：提取的 windowKey、pending 是否存在、assembleContext 的关键字段
   - 格式：`ctx.logger('pmboard').debug('reqboard-capture: systemPrompt assembly', { windowKey, hasPending, contextKeys })`

5. **节点5（src/application/internal/capture-section.ts）**：提示词生成检查
   - 位置：`captureSectionText` 函数返回前
   - 日志内容：最终文本长度、返回空串的原因（窗口已绑定/无 pending/判定为不需要）
   - 格式：`debug('reqboard-capture: section text', { textLength, emptyReason, windowKey })`

**acceptance**:
1. 在 unbound 窗口发送"修复 XX"消息
2. 检查日志输出，确认 5 个节点都有日志
3. 日志格式统一，包含关键状态信息
4. 日志清晰显示每个环节的状态（触发/未触发、值/undefined）

---

### T2 - 诊断测试与断链定位

**key**: t2  
**title**: 执行诊断测试，找到链路断链位置  
**phase**: test  
**side**: fullstack
**requirement_refs**: [BUG-1]  
**depends_on**: [t1]  

**implementation**:

1. **启动 DSH**：`cd ../../../ && ./scripts/start.sh --port 13081`（避免干扰生产端口）
2. **准备测试窗口**：
   - 打开 http://localhost:13081
   - 确认窗口状态为 unbound（调用 `reqboard_status` 确认 `bound: false`）
3. **发送测试消息**："修复股票池刷新逻辑"
4. **收集日志**：
   - 查看控制台日志，grep `reqboard-capture`
   - 记录 5 个节点的日志输出
5. **分析断链位置**：
   - 节点1 无日志 → Hook 订阅失败
   - 节点2 无日志 → 事件未到达 handler
   - 节点3 无日志或 `shouldCapture: false` → 判定逻辑问题
   - 节点4 无日志或 `windowKey: undefined` → windowKey 提取失败
   - 节点5 返回空串但前 4 节点正常 → 生成逻辑问题

**acceptance**:
1. 测试日志完整收集（保存到 `docs/requirements/REQ-f6307c/diagnostic-log.txt`）
2. 明确指出断链位置（哪个节点未触发或返回异常）
3. 记录断链原因假设（为 T3 提供修复方向）

---

### T3 - 修复断链问题

**key**: t3  
**title**: 根据诊断结果修复 Hook 注入链路  
**phase**: implement  
**side**: backend
**requirement_refs**: [BUG-2]  
**depends_on**: [t2]  

**implementation**:

根据 T2 诊断结果，修复对应问题。可能的修复方向：

**方向A：windowKey 提取失败**（节点4 问题）
- 文件：`src/gate-wiring.ts`
- 修复：检查 `windowKeyFromContext(assembleContext)` 实现
- 验证：assembleContext 是否包含 agent.id 或 scope
- 修改：调整提取逻辑，确保正确获取窗口标识

**方向B：snapshot() 状态不一致**（节点3→4 之间）
- 文件：`src/adapters/CaptureHook.ts`
- 修复：确保 pendingCapture 的生命周期跨越状态变化
- 验证：Hook 判定时 unbound，systemPrompt 组装时已 bound
- 修改：调整 pending 清除时机或增加状态锁定

**方向C：判断逻辑误判**（节点3 问题）
- 文件：`src/application/internal/window.ts`
- 修复：调整 `shouldCaptureWindow` 判断条件
- 验证：检查 `isWindowBound` 和 `hasPendingSuggestion` 的实现
- 修改：添加容错或调整判断顺序

**方向D：事件订阅失败**（节点1-2 问题）
- 文件：`src/index.ts`
- 修复：检查 `ctx.on('session/event')` 订阅逻辑
- 验证：返回的 dispose 函数是否正确保存
- 修改：确保订阅在正确的生命周期时机执行

**通用修复步骤**：
1. 根据诊断日志确定具体断链位置
2. 阅读相关代码，理解原有逻辑
3. 实施修复（最小化改动原则）
4. 添加必要的防御性检查
5. 保留诊断日志（便于未来排障）

**acceptance**:
1. 修复后重新测试相同用例（unbound 窗口 + "修复 XX"）
2. 日志显示所有 5 个节点都正常
3. 节点5 返回的文本长度 > 0（提示词已生成）
4. LLM 确实看到了动态注入的提示词（从响应中验证）
5. Agent 第一个工具调用是 `reqboard_capture`

---

### T4 - 回归测试与验收

**key**: t4  
**title**: 连续测试与回归验证  
**phase**: test  
**side**: fullstack
**requirement_refs**: [BUG-1, BUG-2]  
**depends_on**: [t3]  

**implementation**:

**1. 连续成功率测试**：
- 重启 DSH，清空状态
- 在 3 个不同的 unbound 窗口，分别发送：
  - "修复账户信息显示 bug"
  - "新增股票池批量导入功能"
  - "实现策略回测报告导出"
- 验证每次都触发 `reqboard_capture` 弹框
- 成功率要求：3/3（100%）

**2. 回归测试**：
- **bound 窗口推进流程**：
  - 在已立项窗口继续对话
  - 确认不会重复注入捕获提示词
  - 确认正常推进需求流程
- **其他 systemPrompt sections**：
  - 检查 genome sections（principles/rules/lessons）正常加载
  - 检查 agent:identity 段正常显示
- **性能测试**：
  - 测量添加日志前后的启动时间差异
  - 确认 < 100ms 增量

**3. 清理工作**：
- 删除测试端口的 `.dsh-data/` 目录
- 停止测试实例
- 保留诊断日志到需求目录

**acceptance**:
1. 连续 3 次测试 100% 成功率
2. bound 窗口推进流程正常
3. 其他 systemPrompt sections 不受影响
4. 性能无明显下降（< 100ms）
5. 诊断日志已保存到 `docs/requirements/REQ-f6307c/diagnostic-log.txt`

---

## 三、依赖关系

```
t1 (添加诊断日志)
 ↓
t2 (诊断测试与断链定位)
 ↓
t3 (修复断链问题)
 ↓
t4 (回归测试与验收)
```

---

## 四、风险与注意事项

### 4.1 风险点

1. **T2 诊断可能需要多次迭代**
   - 初次诊断可能不足以定位根因
   - 可能需要添加更细粒度的日志
   - 缓解：T1 日志设计已覆盖关键路径

2. **T3 修复可能涉及多个文件**
   - 断链可能不是单点问题
   - 可能需要调整多处代码
   - 缓解：按设计文档的"潜在修复方向"逐项排查

3. **回归测试覆盖不全**
   - 可能遗漏边界场景
   - 缓解：T4 已包含 bound/unbound 两类窗口测试

### 4.2 注意事项

1. **日志级别使用 debug**
   - 避免生产环境噪音
   - 需要时可通过环境变量开启

2. **保留诊断日志**
   - 便于未来类似问题排查
   - 不影响正常性能（debug 级别默认不输出）

3. **修复原则**
   - 最小化改动
   - 优先修复而非重构
   - 保持现有架构不变

---

## 五、验收总结

### 整体验收标准

- [ ] 诊断日志已添加（5 个节点）
- [ ] 断链位置已定位
- [ ] 断链问题已修复
- [ ] LLM 能看到动态注入的提示词
- [ ] Agent 调用 `reqboard_capture` 弹框
- [ ] 连续 3 次测试 100% 成功
- [ ] bound 窗口推进流程正常
- [ ] 其他 systemPrompt sections 不受影响
- [ ] 性能无明显下降

### 交付物

1. 修改后的源代码（4-5 个文件）
2. 诊断日志样本（`docs/requirements/REQ-f6307c/diagnostic-log.txt`）
3. 修复说明文档（`docs/requirements/REQ-f6307c/fix-summary.md`）