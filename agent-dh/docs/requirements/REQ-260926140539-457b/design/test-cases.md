---
requirement_id: REQ-260926140539-457b
design_type: test-strategy
version: 1.0
serves: FR-9, FR-10
---

# RTM 系统测试策略

## 目标 serves: FR-9, FR-10

定义 RTM 系统的完整测试策略，包括单元测试、集成测试、性能测试、异常测试和端到端测试，确保系统鲁棒性和性能达标。

---

## 测试层次 serves: FR-1, FR-2, FR-3, FR-9
### 1. 单元测试（Unit Tests） serves: FR-9, FR-10
serves: FR-1, FR-2, FR-3

**范围**：核心类和函数

**测试框架**：Vitest

**覆盖目标**：≥ 80%

#### RTMGenerator 类测试 serves: FR-2

```typescript
describe('RTMGenerator', () => {
  test('generateLifecycle - 应创建 lifecycle 文件', async () => {
    const generator = new RTMGenerator({ reqboardPath, reqDir });
    await generator.generateLifecycle('REQ-test');
    
    const lifecycle = await readYAML('rtm-lifecycle.yml');
    expect(lifecycle.requirement.id).toBe('REQ-test');
    expect(lifecycle.lifecycle.stages).toBeDefined();
  });
  
  test('generateBrainstorming - 应提取 FR 列表', async () => {
    await generator.generateBrainstorming('REQ-test');
    
    const rtm = await readYAML('rtm-brainstorming.yml');
    expect(rtm.outputs.requirements).toHaveLength(3);
    expect(rtm.outputs.requirements[0].id).toBe('FR-1');
  });
  
  test('generateDesign - 应构建 fr_to_design 映射', async () => {
    await generator.generateDesign('REQ-test');
    
    const rtm = await readYAML('rtm-design.yml');
    expect(rtm.traceability.fr_to_design['FR-1']).toBeDefined();
  });
});
```

#### RTMParser 类测试 serves: FR-3

```typescript
describe('RTMParser', () => {
  test('parseRequirementFRs - 应正确提取 FR', () => {
    const content = '**FR-1: 文件结构\n**FR-2: 生成逻辑';
    const frs = parser.parseRequirementFRs(content);
    
    expect(frs).toHaveLength(2);
    expect(frs[0].id).toBe('FR-1');
    expect(frs[0].title).toBe('文件结构');
  });
  
  test('parseDesignSections - 应提取 serves 标注', () => {
    const files = [{
      path: 'design/arch.md',
      content: '## 1.1 架构\nserves: FR-1, FR-2'
    }];
    
    const sections = parser.parseDesignSections(files);
    expect(sections[0].serves).toEqual(['FR-1', 'FR-2']);
  });
});
```

#### RTMValidator 类测试 serves: FR-9

```typescript
describe('RTMValidator', () => {
  test('validateDesignCoverage - 100% 覆盖应通过', () => {
    const frs = [{ id: 'FR-1' }, { id: 'FR-2' }];
    const mapping = new Map([
      ['FR-1', ['design#1.1']],
      ['FR-2', ['design#2.1']]
    ]);
    
    const coverage = validator.validateDesignCoverage(frs, mapping);
    expect(coverage.rate).toBe(100);
    expect(coverage.uncovered).toEqual([]);
  });
  
  test('checkGate - 设计覆盖度 < 100% 应拒绝', () => {
    const coverage = { rate: 67, uncovered: ['FR-3'] };
    const result = validator.checkGate('design', coverage);
    
    expect(result.passed).toBe(false);
    expect(result.message).toContain('FR-3');
  });
});
```

---

### 2. 集成测试（Integration Tests） serves: FR-2, FR-7

**范围**：模块间交互和触发点集成

#### reqboard 工具集成测试 serves: FR-2

```typescript
describe('reqboard RTM Integration', () => {
  test('reqboard_submit(design) - 应自动生成 RTM', async () => {
    const result = await reqboardSubmit({
      kind: 'design',
      requirement_id: 'REQ-test'
    });
    
    expect(result.success).toBe(true);
    expect(fs.existsSync('rtm-design.yml')).toBe(true);
  });
  
  test('覆盖度门禁 - 应拒绝不足 100% 的设计', async () => {
    // 准备：只覆盖 2/3 的 FR
    await expect(reqboardSubmit({
      kind: 'design',
      requirement_id: 'REQ-test'
    })).rejects.toThrow('设计覆盖度不足');
  });
  
  test('reqboard_task_move - 应同步更新 RTM', async () => {
    await reqboardTaskMove({
      task_id: 't-test',
      to: 'in_progress'
    });
    
    const taskRTM = await readYAML('rtm-implementing/t-test.yml');
    expect(taskRTM.task.status).toBe('in_progress');
  });
});
```

#### StageOverview API 集成测试 serves: FR-7

```typescript
describe('StageOverview API', () => {
  test('GET /api/stage-overview/:id - 应返回 traceability', async () => {
    const response = await fetch(`/api/stage-overview/REQ-test`);
    const data = await response.json();
    
    expect(data.traceability).toBeDefined();
    expect(data.traceability.fr_to_design).toBeDefined();
    expect(data.coverage).toBeDefined();
  });
  
  test('RTM 缺失时应降级到实时生成', async () => {
    // 删除 RTM 文件
    fs.unlinkSync('rtm-design.yml');
    
    const response = await fetch(`/api/stage-overview/REQ-test`);
    expect(response.status).toBe(200);
    
    // 验证已重新生成
    expect(fs.existsSync('rtm-design.yml')).toBe(true);
  });
});
```

---

### 3. 性能测试（Performance Tests） serves: FR-8, FR-10

**目标**：验证 250x 性能提升

```typescript
describe('RTM Performance', () => {
  test('Dive 决策延迟 < 5ms', async () => {
    const start = performance.now();
    
    const lifecycle = await readYAML('rtm-lifecycle.yml');
    const stageRTM = await readYAML('rtm-design.yml');
    const decision = makeDiveDecision('design', stageRTM);
    
    const duration = performance.now() - start;
    expect(duration).toBeLessThan(5);
  });
  
  test('任务状态更新 < 10ms', async () => {
    const start = performance.now();
    
    await generator.updateTaskStatus('REQ-test', 't-test', {
      status: 'in_progress'
    });
    
    const duration = performance.now() - start;
    expect(duration).toBeLessThan(10);
  });
  
  test('追溯链查询 < 5ms', async () => {
    const start = performance.now();
    
    const rtm = await readYAML('rtm-design.yml');
    const chain = buildTraceabilityChain('FR-1', rtm);
    
    const duration = performance.now() - start;
    expect(duration).toBeLessThan(5);
  });
});
```

**基准对比测试**：

```typescript
describe('Performance Comparison', () => {
  test('RTM vs 实时解析 - 应有 250x 提升', async () => {
    // 实时解析（原方案）
    const start1 = performance.now();
    const data1 = await parseDocumentsRealtime();
    const duration1 = performance.now() - start1;
    
    // RTM 读取（新方案）
    const start2 = performance.now();
    const data2 = await readRTM('rtm-design.yml');
    const duration2 = performance.now() - start2;
    
    const speedup = duration1 / duration2;
    expect(speedup).toBeGreaterThan(200); // 至少 200x
  });
});
```

---

### 4. 异常测试（Error Handling Tests） serves: FR-9

**范围**：错误处理和降级模式

```typescript
describe('RTM Error Handling', () => {
  test('RTM 文件缺失 - 应自动重新生成', async () => {
    fs.unlinkSync('rtm-design.yml');
    
    const rtm = await readRTMWithFallback('rtm-design.yml', 'REQ-test');
    expect(rtm).toBeDefined();
    expect(fs.existsSync('rtm-design.yml')).toBe(true);
  });
  
  test('YAML 格式错误 - 应记录错误不崩溃', async () => {
    fs.writeFileSync('rtm-design.yml', 'invalid: [yaml');
    
    await expect(readYAML('rtm-design.yml')).rejects.toThrow();
    // 系统应继续运行
  });
  
  test('并发更新 - 应使用文件锁防冲突', async () => {
    const updates = Array.from({ length: 10 }, (_, i) => 
      generator.updateTaskStatus('REQ-test', 't-test', {
        status: 'in_progress',
        workflow: [{ phase: 'implement', status: 'in_progress' }]
      })
    );
    
    await Promise.all(updates);
    
    // 验证最终状态一致
    const taskRTM = await readYAML('rtm-implementing/t-test.yml');
    expect(taskRTM.task.status).toBe('in_progress');
  });
  
  test('数据不一致 - 应优先信任台账', async () => {
    // RTM 显示 in_progress，台账显示 done
    const reqboard = await readReqboard();
    const task = reqboard.tasks.find(t => t.id === 't-test');
    task.status = 'done';
    await writeReqboard(reqboard);
    
    // 重新生成 RTM
    await generator.generateImplementing('REQ-test');
    
    const rtm = await readYAML('rtm-implementing/t-test.yml');
    expect(rtm.task.status).toBe('done'); // 以台账为准
  });
});
```

---

### 5. 端到端测试（E2E Tests） serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-7

**范围**：完整需求流程

```typescript
describe('RTM End-to-End', () => {
  test('完整需求流程 - 7 个触发点', async () => {
    // 1. 立项
    await reqboardCreate({
      title: 'E2E Test Requirement',
      category: 'feature'
    });
    expect(fs.existsSync('rtm-lifecycle.yml')).toBe(true);
    
    // 2. 提交需求
    await reqboardSubmit({
      kind: 'requirement',
      requirement_id: 'REQ-e2e'
    });
    expect(fs.existsSync('rtm-brainstorming.yml')).toBe(true);
    
    // 3. 确认需求
    await reqboardAskConfirm({
      target: 'artifact',
      kind: 'requirement',
      requirement_id: 'REQ-e2e'
    });
    
    // 4. 提交设计
    await reqboardSubmit({
      kind: 'design',
      requirement_id: 'REQ-e2e'
    });
    expect(fs.existsSync('rtm-design.yml')).toBe(true);
    
    const designRTM = await readYAML('rtm-design.yml');
    expect(designRTM.coverage.design.rate).toBe(100);
    
    // 5. 批准计划
    await reqboardAskConfirm({
      target: 'plan',
      requirement_id: 'REQ-e2e'
    });
    expect(fs.existsSync('rtm-decomposing.yml')).toBe(true);
    expect(fs.existsSync('rtm-implementing.yml')).toBe(true);
    
    // 6. 任务状态变更
    await reqboardTaskMove({
      task_id: 't-e2e-1',
      to: 'in_progress'
    });
    
    const taskRTM = await readYAML('rtm-implementing/t-e2e-1.yml');
    expect(taskRTM.task.status).toBe('in_progress');
    
    // 7. 提交验收
    await reqboardSubmit({
      kind: 'verification',
      requirement_id: 'REQ-e2e'
    });
    expect(fs.existsSync('rtm-accepting.yml')).toBe(true);
    
    const acceptingRTM = await readYAML('rtm-accepting.yml');
    expect(acceptingRTM.coverage.testing.rate).toBeGreaterThanOrEqual(80);
  });
});
```

---

### 6. Agent Teams 并行测试 serves: FR-11

```typescript
describe('Agent Teams Parallel Execution', () => {
  test('应创建 Worker 和共享任务', async () => {
    // 启动 Dive
    const agents = await tools.list_agents();
    expect(agents.filter(a => a.name.startsWith('worker-'))).toHaveLength(3);
    
    // 验证共享任务
    const tasks = await tools.team_task_list();
    expect(tasks.tasks.length).toBeGreaterThan(0);
  });
  
  test('Worker 应自动 claim ready 任务', async () => {
    const readyTasks = await tools.team_task_list({
      status: 'pending',
      ready: true
    });
    
    expect(readyTasks.tasks.length).toBeGreaterThan(0);
    
    // Worker 自动 claim
    await sleep(1000);
    
    const inProgressTasks = await tools.team_task_list({
      status: 'in_progress'
    });
    
    expect(inProgressTasks.tasks.length).toBeGreaterThan(0);
  });
  
  test('Dive 应通过 wait_agent 监控进度', async () => {
    const result = await tools.wait_agent({ timeout_ms: 5000 });
    expect(result.timedOut).toBe(false);
    
    // 检查任务完成情况
    const tasks = await tools.team_task_list();
    const completed = tasks.tasks.filter(t => t.status === 'completed');
    expect(completed.length).toBeGreaterThan(0);
  });
});
```

---

## 测试数据准备 serves: FR-1, FR-2, FR-3, FR-4, FR-5
### 测试需求模板 serves: FR-1
serves: FR-1

```markdown
# REQ-test: RTM 测试需求
serves: FR-1

**FR-1: 文件结构**
实现 RTM 文件结构

**FR-2: 生成逻辑**
实现 RTM 生成逻辑

**FR-3: 数据同步**
实现数据同步机制
```

### 测试设计文档 serves: FR-1

```markdown
## 1.1 文件结构设计 serves: FR-1
## 1.2 生成逻辑设计 serves: FR-1
## 2.1 同步机制设计 serves: FR-2
serves: FR-3
```

---

## 测试环境 serves: FR-1
### 本地开发环境 serves: FR-1
serves: FR-1

```bash
cd agent-dh
npm install
npm test
```

### CI/CD 环境 serves: FR-1

```yaml
# .github/workflows/test.yml
serves: FR-1
name: RTM Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
      - run: npm install
      - run: npm test -- --coverage
      - run: npm run test:e2e
```

---

## 覆盖率目标 serves: FR-5

| 类型 | 目标 | 当前 |
|-----|------|------|
| 单元测试 | ≥ 80% | TBD |
| 集成测试 | ≥ 70% | TBD |
| E2E 测试 | 100% 关键路径 | TBD |

---

## 验收口径 serves: FR-1, FR-2, FR-3, FR-4, FR-5
### 测试通过标准 serves: FR-9, FR-10

```bash
# 所有测试通过
serves: FR-1
npm test

# 预期：
serves: FR-1
# ✓ 单元测试：50+ 用例全部通过
serves: FR-1
# ✓ 集成测试：20+ 用例全部通过
serves: FR-1
# ✓ 性能测试：Dive 决策 < 5ms
serves: FR-1
# ✓ 异常测试：降级模式正常工作
serves: FR-1
# ✓ E2E 测试：完整流程通过
serves: FR-1
```

### 性能基准验证 serves: FR-10

```bash
npm run test:performance

# 预期：
serves: FR-1
# ✓ Dive 决策：500ms → 2ms（250x）
serves: FR-1
# ✓ 任务更新：100ms → 10ms（10x）
serves: FR-1
# ✓ 追溯查询：200ms → 5ms（40x）
serves: FR-1
```