---
requirement_id: REQ-260926140539-457b
design_type: use-cases
version: 1.0
serves: FR-7, FR-8, FR-11
---

# RTM 系统使用场景设计

## 目标 serves: FR-7, FR-8, FR-11

定义 RTM 系统的典型使用场景，包括 Dive 模式自动决策、会话节点追溯展示、Agent Teams 并行任务执行等，确保设计满足实际使用需求。

---

## 场景 1：Dive 模式自动推进 serves: FR-8
### 参与者 serves: FR-8

- Dive 模式（AI Agent）

### 前置条件 serves: FR-8

- 需求已进入 design 阶段
- 设计文档已提交并生成 RTM

### 主流程 serves: FR-8

1. **Dive 启动决策循环**
   - 读取 rtm-lifecycle.yml（~1ms）
   - 获取当前阶段：design
   
2. **读取节点 RTM**
   - 读取 rtm-design.yml（~1ms）
   - 获取设计覆盖度统计
   
3. **基于覆盖度决策**
   - 如果 coverage.design.rate === 100%
     - 输出："所有 FR 都有设计，可以准备拆分"
     - 建议推进到 decomposing 阶段
   - 否则
     - 输出："还有 N 个 FR 缺少设计"
     - 列出 uncovered FR 列表
     - 建议补充设计

4. **执行决策**
   - Dive 自动补充设计或推进到下一阶段

### 后置条件 serves: FR-8

- Dive 完成决策（总耗时 < 5ms）
- 需求状态更新

### 性能指标 serves: FR-8, FR-10

- **延迟**：< 5ms（vs 原来 500ms）
- **提升**：250x

---

## 场景 2：会话节点追溯展示 serves: FR-7
### 参与者 serves: FR-7

- 用户（通过 Web UI）
- StageOverview API

### 前置条件 serves: FR-8

- 需求已进入 implementing 阶段
- RTM 文件已生成

### 主流程 serves: FR-8

1. **用户打开会话节点**
   - 点击会话右上角的需求节点图标
   
2. **请求追溯数据**
   - 前端调用 `GET /api/stage-overview/:id`
   - 后端读取 rtm-implementing.yml
   
3. **展示追溯 Tab**
   - **需求层**：显示 5 个 FR
   - **设计层**：显示 8 个设计章节 + fr_to_design 映射
   - **任务层**：显示 5 个任务 + design_to_tasks 映射
   - **测试层**：显示 8 个测试用例 + task_to_tests 映射
   - **覆盖度**：设计 100%、实施 100%、测试 80%

4. **用户交互**
   - 点击 FR-1 → 高亮关联的设计章节
   - 点击设计章节 → 高亮关联的任务
   - 点击任务 → 高亮关联的测试用例

### 后置条件 serves: FR-8

- 用户看到完整的四级追溯链
- 用户了解当前覆盖度情况

### 界面示例 serves: FR-7

```
┌─────────────────────────────────────┐
│ 追溯链                               │
├─────────────────────────────────────┤
│ 📋 需求层（5个FR）                   │
│   ✅ FR-1: RTM 文件结构              │
│   ✅ FR-2: RTM 生成逻辑              │
│   ✅ FR-3: 数据同步机制              │
│   ...                                │
├─────────────────────────────────────┤
│ 📐 设计层（8个章节）                 │
│   design/arch#1.1 → [FR-1, FR-2]     │
│   design/data#2.1 → [FR-3]           │
│   ...                                │
├─────────────────────────────────────┤
│ 🔧 任务层（5个任务）                 │
│   t-354ea0 (in_progress)             │
│     → design/arch#1.1 → FR-1         │
│     workflow: implement (3/7)        │
│   ...                                │
├─────────────────────────────────────┤
│ ✅ 测试层（8个用例）                 │
│   TC-1 → t-354ea0 → FR-1             │
│   ...                                │
├─────────────────────────────────────┤
│ 📊 覆盖度统计                        │
│   设计: 100% (5/5) ✅                │
│   实施: 100% (8/8) ✅                │
│   测试: 80% (4/5) ⚠️                 │
└─────────────────────────────────────┘
```

---

## 场景 3：验收门禁检查 serves: FR-5
### 参与者 serves: FR-8

- AI Agent
- RTMValidator（门禁检查器）

### 前置条件 serves: FR-8

- 需求已完成实施
- Agent 准备提交验收材料

### 主流程 serves: FR-8

1. **Agent 提交验收**
   - 调用 `reqboard_submit(kind=verification)`
   
2. **生成 RTM**
   - 解析测试文档提取 covers 标注
   - 构建 task_to_tests 映射
   
3. **门禁检查**
   - 计算测试覆盖度：4/5 = 80%
   - 检查阈值：80% ≥ 80% ✅
   
4. **通过门禁**
   - 生成 rtm-accepting.yml
   - 登记验收产物
   - 需求进入 accepting 状态

### 替代流程：覆盖度不足 serves: FR-5

3a. **门禁拒绝**
   - 计算测试覆盖度：3/5 = 60%
   - 检查阈值：60% < 80% ❌
   
4a. **返回错误**
   - 错误消息："测试覆盖度不足 (60%)，以下任务缺少测试用例："
   - 列出未覆盖任务：[t-f0e25a, t-d29db5]
   - 建议："请补充测试用例使覆盖度达到 ≥80% 后重新提交"

5a. **Agent 补充测试**
   - 编写测试用例覆盖缺失任务
   - 重新提交验收

### 后置条件 serves: FR-8

- 测试覆盖度 ≥ 80%
- 需求进入验收状态

---

## 场景 4：需求修改后 RTM 更新 serves: FR-6
### 参与者 serves: FR-8

- AI Agent
- RTMGenerator（增量更新）

### 前置条件 serves: FR-8

- 需求已进入 design 阶段
- 用户提出设计修改意见

### 主流程 serves: FR-8

1. **用户反馈**
   - "FR-3 的需求定义不清楚，需要重新讨论"
   
2. **Agent 判断**
   - 这是需求问题，不是设计问题
   - 需要回退到 brainstorming 阶段

3. **修改需求文档**
   - 与用户重新讨论 FR-3
   - 修改 requirement.md
   
4. **重新提交**
   - 调用 `reqboard_submit(kind=requirement)`
   
5. **RTM 增量更新**
   - 重新解析 requirement.md
   - 检测变化：FR-3 定义已更新
   - 更新 rtm-brainstorming.yml
   - version: 1 → 2
   
6. **连锁更新**
   - 设计覆盖度重新计算（FR-3 可能需要补充设计）
   - 下游任务标记为待同步

### 后置条件 serves: FR-8

- requirement.md 已更新
- rtm-brainstorming.yml version +1
- 设计覆盖度重新计算

---

## 场景 5：Agent Teams 并行任务执行 serves: FR-11
### 参与者 serves: FR-11

- Dive（Team Lead）
- Worker-1、Worker-2、Worker-3（持久化 Agent）

### 前置条件 serves: FR-8

- 需求已进入 implementing 阶段
- 拆分计划已批准
- rtm-implementing.yml 骨架已生成

### 主流程 serves: FR-8

#### Phase 1：Dive 初始化 serves: FR-8, FR-11

1. **创建 Worker Agents**
   ```typescript
   await spawn_teammate({ name: 'worker-1', ... });
   await spawn_teammate({ name: 'worker-2', ... });
   await spawn_teammate({ name: 'worker-3', ... });
   ```

2. **创建共享任务**
   - 为每个任务的每个子阶段创建 team_task
   - 设置 blocked_by（双层依赖：任务级 + 子阶段级）
   ```typescript
   team_task_create({
     subject: 'T1-doc',
     blocked_by: []  // Wave 1，立即 ready
   });
   team_task_create({
     subject: 'T1-implement',
     blocked_by: ['T1-doc']  // 等 T1-doc
   });
   team_task_create({
     subject: 'T3-doc',
     blocked_by: ['T1-commit']  // 等 T1 完成
   });
   ```

3. **启动 Worker 循环**
   ```typescript
   send_message('worker-1', '开始执行');
   send_message('worker-2', '开始执行');
   send_message('worker-3', '开始执行');
   ```

#### Phase 2：Worker 自动执行 serves: FR-11

4. **Worker-1 工作循环**
   ```typescript
   while (true) {
     // 列出 ready 任务
     const tasks = await team_task_list({ 
       status: 'pending', 
       ready: true 
     });
     
     if (tasks.length === 0) break;
     
     // Claim 第一个
     const task = tasks[0];
     await team_task_update({ 
       task_id: task.id, 
       action: 'claim' 
     });
     
     // 执行子阶段
     await executeSubphase(task);
     
     // 完成
     await team_task_update({ 
       task_id: task.id, 
       action: 'complete' 
     });
     // DSH 自动解锁依赖它的任务
   }
   ```

5. **并行执行**
   - Worker-1 执行 T1-doc
   - Worker-2 执行 T2-doc（并行）
   - Worker-3 执行 T4-doc（并行）
   
6. **依赖解锁**
   - T1-doc 完成 → T1-implement 变为 ready
   - Worker-1 自动 claim T1-implement

#### Phase 3：Dive 监控 serves: FR-11

7. **事件驱动监控**
   ```typescript
   while (true) {
     // 等待变化（阻塞，零轮询）
     const result = await wait_agent({ timeout: 300000 });
     
     // 检查进度
     const tasks = await team_task_list();
     const completed = tasks.filter(t => t.status === 'completed').length;
     console.log(`进度：${completed}/${tasks.length}`);
     
     // 全部完成
     if (completed === tasks.length) break;
     
     // 假死检测（5分钟心跳）
     if (result.timedOut) {
       checkForStuckWorkers();
     }
   }
   ```

8. **假死恢复**
   - 检测到 Worker-2 卡在 T2-implement > 30 分钟
   - interrupt_agent('worker-2')
   - team_task_update({ action: 'release' })
   - send_message('worker-2', '重启')

9. **所有任务完成**
   - Dive 调用 reqboard_move('implementing', 'accepting')
   - 自动进入验收阶段

### 后置条件 serves: FR-8

- 所有任务完成
- rtm-implementing.yml 更新为最终状态
- 需求自动推进到 accepting

### 性能优势 serves: FR-10

- **零轮询成本**：wait_agent 事件驱动
- **自动负载均衡**：Worker 先到先得
- **自动依赖解锁**：DSH 原生 blocked_by
- **假死自动恢复**：5 分钟心跳检测

---

## 场景 6：RTM 文件缺失降级 serves: FR-9
### 参与者 serves: FR-8

- Dive 模式
- RTMGenerator（降级模式）

### 前置条件 serves: FR-8

- 需求已进入 design 阶段
- rtm-design.yml 文件被意外删除

### 主流程 serves: FR-8

1. **Dive 尝试读取 RTM**
   ```typescript
   const rtm = await readYAML('rtm-design.yml');
   ```

2. **文件读取失败**
   - 错误：File not found

3. **降级到实时生成**
   ```typescript
   console.warn('RTM 文件读取失败，降级到实时生成');
   const generator = new RTMGenerator({ reqboardPath, reqDir });
   await generator.generateDesign(requirementId);
   ```

4. **重新读取**
   ```typescript
   const rtm = await readYAML('rtm-design.yml');
   ```

5. **继续决策**
   - Dive 基于重新生成的 RTM 继续决策
   - 用户无感知

### 后置条件 serves: FR-8

- RTM 文件已重新生成
- Dive 继续正常工作

### 性能影响 serves: FR-10

- 首次读取：~500ms（实时生成）
- 后续读取：~2ms（正常流程）

---

## 非功能需求验证 serves: FR-9, FR-10
### 性能需求 serves: FR-9, FR-10
serves: FR-10

| 场景 | 目标 | 验证方式 |
|-----|------|---------|
| Dive 决策 | < 5ms | 场景 1 性能测试 |
| 追溯查询 | < 5ms | 场景 2 API 响应测试 |
| 任务更新 | < 10ms | 场景 5 并发更新测试 |

### 可用性需求 serves: FR-7

| 场景 | 目标 | 验证方式 |
|-----|------|---------|
| RTM 缺失 | 自动降级 | 场景 6 降级测试 |
| 数据不一致 | 优先台账 | 场景 4 数据同步测试 |
| 并发冲突 | 无数据损坏 | 场景 5 并发测试 |

### 可扩展性需求 serves: FR-1

| 场景 | 目标 | 验证方式 |
|-----|------|---------|
| 新增 FR | 增量更新 | 场景 4 变更测试 |
| 任务并行 | 自动负载均衡 | 场景 5 Worker 测试 |

---

## 验收口径 serves: FR-1, FR-2, FR-3, FR-4, FR-5
### 场景测试通过标准 serves: FR-7, FR-8, FR-11

```bash
npm test -- use-cases.test.ts

# 预期：
serves: FR-1
# ✓ 场景 1：Dive 模式决策 < 5ms
serves: FR-1
# ✓ 场景 2：追溯 Tab 正确展示
serves: FR-1
# ✓ 场景 3：门禁正确拒绝/通过
serves: FR-1
# ✓ 场景 4：RTM 正确增量更新
serves: FR-1
# ✓ 场景 5：Agent Teams 正确并行执行
serves: FR-1
# ✓ 场景 6：降级模式正常工作
serves: FR-1
```

### 用户体验验证 serves: FR-1

- ✅ Dive 决策响应快速（< 5ms 感知不到延迟）
- ✅ 追溯链清晰可见（四级层次分明）
- ✅ 门禁错误提示友好（明确指出缺失项）
- ✅ 降级模式透明（用户无感知）
- ✅ 并行执行高效（Worker 自动负载均衡）