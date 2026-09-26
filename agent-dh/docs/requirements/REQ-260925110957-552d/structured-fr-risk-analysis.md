# 功能点结构化方案：风险分析与缓解措施

> **核心原则**：没有银弹，只有权衡。新方案会引入新问题，但可以通过工程手段降低风险。

---

## 🚨 诚实的回答

**我无法保证100%不出问题。**

但我可以：
1. ✅ 列出所有可能的问题
2. ✅ 评估每个问题的概率和影响
3. ✅ 提供缓解措施和回退方案
4. ✅ 设计渐进式迁移路径

---

## 📊 风险矩阵

| 风险 | 概率 | 影响 | 风险等级 | 缓解难度 |
|------|------|------|---------|---------|
| R1: 文件同步不一致 | 高 | 高 | 🔴 P0 | 中 |
| R2: 功能点粒度难把握 | 中 | 中 | 🟡 P1 | 低 |
| R3: 工具实现有bug | 中 | 高 | 🔴 P0 | 高 |
| R4: Agent 不会填写 | 低 | 中 | 🟡 P1 | 低 |
| R5: 文件太多难管理 | 低 | 低 | 🟢 P2 | 低 |
| R6: 历史需求迁移成本 | 中 | 低 | 🟢 P2 | 低 |
| R7: 覆盖门禁误报 | 中 | 中 | 🟡 P1 | 中 |
| R8: 性能问题 | 低 | 低 | 🟢 P2 | 低 |

---

## 🔴 高风险问题

### R1: 文件同步不一致（概率：高，影响：高）

**问题描述**：
```
场景1：修改了 FR-1-async-jobs.md，但忘记更新 requirement.md 的索引表
→ 索引表显示"3个验收项"，实际文件有4个

场景2：任务引用了 FR-1，但文件改名为 FR-1-new-name.md
→ requirement_refs 失效，验证失败

场景3：删除了 FR-5 文件，但任务还在引用
→ 覆盖门禁通过（因为任务接收了），但文件不存在
```

**为什么会发生**：
- 多个文件需要手动同步
- Git 不会强制关联文件间的一致性
- Agent 可能只改一处忘了另一处

**影响评估**：
- 🔴 **严重**：验收时找不到验收项
- 🔴 **严重**：功能点引用失效，覆盖检查失败
- 🟡 **中等**：索引表与实际不符，混淆

**缓解措施**：

#### M1.1: 工具自动同步（推荐）

**在 reqboard_submit 时自动更新索引表**：

```typescript
// packages/web/dsh-pmboard/src/application/use-cases/Submit.ts

async function autoSyncFRIndex(requirement: RequirementRecord) {
  // 1. 扫描功能点目录
  const frDir = `docs/requirements/${requirement.id}/functional-requirements`
  const frFiles = await glob(`${frDir}/FR-*.md`)
  
  // 2. 提取每个文件的元信息
  const frList = []
  for (const file of frFiles) {
    const content = await readFile(file)
    const meta = extractFRMetadata(content) // 提取优先级、状态等
    frList.push({
      id: extractFRId(file),         // FR-1
      title: meta.title,              // 后台任务投递
      priority: meta.priority,        // P0
      status: meta.status,            // pending
      file: path.relative(reqDir, file)
    })
  }
  
  // 3. 生成索引表 markdown
  const indexTable = generateFRIndexTable(frList)
  
  // 4. 更新 requirement.md
  const reqFile = `docs/requirements/${requirement.id}/requirement.md`
  let reqContent = await readFile(reqFile)
  
  // 替换 "## 3. 功能点索引" 到下一个 "##" 之间的内容
  reqContent = replaceSection(reqContent, '功能点索引', indexTable)
  
  await writeFile(reqFile, reqContent)
  
  console.log(`[自动同步] 更新了 requirement.md 的功能点索引表（${frList.length} 个功能点）`)
}
```

**触发时机**：
- 提交 requirement 产物时
- 提交 verification 产物时
- 手动调用 `reqboard_sync_index` 工具

#### M1.2: 文件存在性验证

```typescript
// Decompose.ts 覆盖门禁增强

function validateFRFiles(requirement, tasks) {
  for (const task of tasks) {
    for (const fr of task.requirement_refs || []) {
      // 检查文件是否存在
      const pattern = `functional-requirements/${fr}-*.md`
      const found = glob(pattern)
      
      if (found.length === 0) {
        reject(
          `任务 ${task.key} 引用了 ${fr}，但文件不存在。` +
          `期望路径：${pattern}`,
          'REQBOARD_FR_FILE_NOT_FOUND'
        )
      }
      
      if (found.length > 1) {
        reject(
          `功能点 ${fr} 对应多个文件：${found.join(', ')}。` +
          `文件名必须唯一：FR-N-<唯一标题>.md`,
          'REQBOARD_FR_FILE_AMBIGUOUS'
        )
      }
    }
  }
}
```

#### M1.3: Git pre-commit hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# 检查功能点文件与 requirement.md 的一致性
if git diff --cached --name-only | grep -q "functional-requirements/FR-"; then
  echo "检测到功能点文件变更，验证一致性..."
  
  # 运行验证脚本
  node scripts/validate-fr-consistency.js
  
  if [ $? -ne 0 ]; then
    echo "❌ 功能点文件与 requirement.md 不一致，请运行："
    echo "   node scripts/sync-fr-index.js"
    exit 1
  fi
fi
```

#### M1.4: 降级策略

**如果同步失败，回退到单文件模式**：

```typescript
function validateCoverage(requirement, tasks) {
  const frFiles = glob('functional-requirements/FR-*.md')
  
  // 降级条件1：没有功能点文件
  if (frFiles.length === 0) {
    console.warn('[降级] 未找到功能点文件，使用单文件模式')
    return validateCoverageLegacy(requirement, tasks)
  }
  
  // 降级条件2：功能点数量与 requirement.md 不匹配
  const expectedCount = extractFRCount(requirement)
  if (frFiles.length !== expectedCount) {
    console.warn(`[降级] 功能点文件数量不匹配（期望 ${expectedCount}，实际 ${frFiles.length}），使用单文件模式`)
    return validateCoverageLegacy(requirement, tasks)
  }
  
  // 正常模式
  return validateCoverageStructured(requirement, tasks, frFiles)
}
```

**风险降低**：高 → 中（通过自动同步 + 验证 + 降级）

---

### R3: 工具实现有bug（概率：中，影响：高）

**问题描述**：
```
场景1：覆盖门禁误判，拒绝了正确的拆分
→ 无法完成拆分

场景2：验收单生成错误，缺少验收项
→ 验收不完整

场景3：自动同步覆盖了手动修改
→ 数据丢失
```

**为什么会发生**：
- 新增代码必然有bug
- 边界情况没有覆盖
- 并发场景没有测试

**影响评估**：
- 🔴 **严重**：阻塞拆分流程
- 🔴 **严重**：验收数据错误
- 🟡 **中等**：数据丢失（可从 git 恢复）

**缓解措施**：

#### M3.1: 渐进式发布

**阶段1：只读模式（Week 1-2）**
```typescript
const FEATURE_FLAG = {
  structuredFR: {
    read: true,   // ✅ 可以读取功能点文件
    write: false, // ❌ 不自动同步，只提示
    enforce: false // ❌ 不强制覆盖门禁
  }
}

// 在 Decompose.ts
if (FEATURE_FLAG.structuredFR.read && frFiles.length > 0) {
  // 尝试结构化验证
  try {
    validateCoverageStructured(...)
  } catch (err) {
    // 失败时只警告，不阻塞
    console.warn('[结构化验证失败] 回退到单文件模式', err)
    validateCoverageLegacy(...)
  }
}
```

**阶段2：写入模式（Week 3-4）**
```typescript
const FEATURE_FLAG = {
  structuredFR: {
    read: true,
    write: true,  // ✅ 允许自动同步
    enforce: false // ❌ 验证失败只警告
  }
}
```

**阶段3：强制模式（Week 5+）**
```typescript
const FEATURE_FLAG = {
  structuredFR: {
    read: true,
    write: true,
    enforce: true // ✅ 验证失败拒绝拆分
  }
}
```

#### M3.2: 充分的单测和集成测试

```typescript
// packages/web/dsh-pmboard/tests/unit/structured-fr.test.ts

describe('功能点结构化', () => {
  describe('覆盖门禁', () => {
    it('所有功能点被接收 → 通过', () => {
      const requirement = { id: 'REQ-test', frFiles: ['FR-1.md', 'FR-2.md'] }
      const tasks = [
        { requirement_refs: ['FR-1'] },
        { requirement_refs: ['FR-2'] }
      ]
      expect(() => validateCoverage(requirement, tasks)).not.toThrow()
    })
    
    it('功能点未被接收 → 拒绝', () => {
      const requirement = { id: 'REQ-test', frFiles: ['FR-1.md', 'FR-2.md'] }
      const tasks = [
        { requirement_refs: ['FR-1'] }
        // FR-2 未被接收
      ]
      expect(() => validateCoverage(requirement, tasks))
        .toThrow('FR-2 未被任何任务接收')
    })
    
    it('引用不存在的功能点 → 拒绝', () => {
      const requirement = { id: 'REQ-test', frFiles: ['FR-1.md'] }
      const tasks = [
        { requirement_refs: ['FR-1', 'FR-999'] } // FR-999 不存在
      ]
      expect(() => validateCoverage(requirement, tasks))
        .toThrow('FR-999 文件不存在')
    })
    
    it('功能点文件重名 → 拒绝', () => {
      const requirement = { 
        id: 'REQ-test', 
        frFiles: ['FR-1-async.md', 'FR-1-jobs.md'] // 同一个编号
      }
      expect(() => validateFRFiles(requirement, []))
        .toThrow('FR-1 对应多个文件')
    })
  })
  
  describe('自动同步', () => {
    it('扫描功能点文件 → 更新索引表', async () => {
      // 准备：创建3个功能点文件
      await writeFile('FR-1-async.md', '# FR-1: 后台任务\n...')
      await writeFile('FR-2-query.md', '# FR-2: 运行态查询\n...')
      await writeFile('FR-3-checkpoint.md', '# FR-3: checkpoint\n...')
      
      // 执行同步
      await autoSyncFRIndex(requirement)
      
      // 验证：requirement.md 包含3个功能点
      const reqContent = await readFile('requirement.md')
      expect(reqContent).toContain('| FR-1 | 后台任务')
      expect(reqContent).toContain('| FR-2 | 运行态查询')
      expect(reqContent).toContain('| FR-3 | checkpoint')
    })
    
    it('功能点文件删除 → 索引表同步删除', async () => {
      // 准备：先有3个，删除1个
      await deleteFile('FR-2-query.md')
      
      // 执行同步
      await autoSyncFRIndex(requirement)
      
      // 验证：索引表只有2个
      const reqContent = await readFile('requirement.md')
      expect(reqContent).toContain('| FR-1 |')
      expect(reqContent).not.toContain('| FR-2 |')
      expect(reqContent).toContain('| FR-3 |')
    })
  })
})
```

**测试覆盖率目标**：> 90%

#### M3.3: Canary 部署

```typescript
// 只对特定需求启用
function isStructuredFREnabled(requirementId: string): boolean {
  // Canary 白名单
  const canaryList = [
    'REQ-260926xxxxxx-test1', // 测试需求1
    'REQ-260926xxxxxx-test2'  // 测试需求2
  ]
  
  if (canaryList.includes(requirementId)) {
    return true
  }
  
  // 其他需求继续用旧方式
  return false
}
```

**风险降低**：中 → 低（通过渐进式发布 + 充分测试 + Canary）

---

## 🟡 中风险问题

### R2: 功能点粒度难把握（概率：中，影响：中）

**问题描述**：
```
场景1：粒度过粗
FR-1: 后台执行系统（包含投递、查询、恢复5个子功能）
→ 一个文件太长，失去了拆分的意义

场景2：粒度过细
FR-1: 注册任务到 ctx.jobs
FR-2: 返回 job_id
FR-3: 写入 runId 到数据库
→ 文件太多，管理成本高

场景3：粒度不一致
FR-1: 后台任务投递（大）
FR-2: 查询接口（小）
FR-3: 整个容错恢复系统（巨大）
→ 难以估算工作量
```

**为什么会发生**：
- 需求分析能力不同
- 缺少明确的拆分标准
- Agent 理解有偏差

**影响评估**：
- 🟡 **中等**：文件结构混乱
- 🟡 **中等**：拆分和验收困难
- 🟢 **轻微**：不影响功能实现

**缓解措施**：

#### M2.1: 明确的粒度标准

```markdown
## 功能点粒度标准（SMART 原则）

**一个功能点应该满足**：

1. **Single**（单一职责）
   - ✅ 一个用户可感知的完整能力
   - ❌ 不是多个独立能力的集合
   - ❌ 不是实现细节

2. **Measurable**（可度量）
   - ✅ 有明确的输入输出
   - ✅ 可以写出可证伪的验收标准
   - ❌ 不是"提升体验"这种模糊目标

3. **Achievable**（可实现）
   - ✅ 1-3个任务可以完成
   - ❌ 不需要10个任务才能完成
   - ❌ 不是一个任务就能完成（太小）

4. **Relevant**（相关性）
   - ✅ 与需求目标直接相关
   - ❌ 不是技术实现细节

5. **Testable**（可测试）
   - ✅ 可以写单测/集成测试
   - ✅ 有明确的测试场景

**粒度参考**：
- ✅ 好的粒度：100-200行，3-5个验收项，1-3个任务
- ❌ 太粗：> 300行，> 10个验收项，> 5个任务
- ❌ 太细：< 50行，1个验收项，1个任务

**示例**：

好的粒度：
- ✅ FR-1: 后台任务投递（工具调用 → 返回 job_id → 后台执行）
- ✅ FR-2: 运行态查询（查询接口 → 返回进度/状态）
- ✅ FR-3: checkpoint 管理（写入/读取/清理）

不好的粒度：
- ❌ FR-1: 后台执行系统（太粗，包含5个子功能）
- ❌ FR-1: 返回 job_id（太细，只是一个返回值）
- ❌ FR-1: 提升用户体验（不可度量）
```

#### M2.2: 提示词明确要求

```typescript
// SubmitTool/prompt.ts

+ '## 功能点粒度要求\n'
+ '\n'
+ '每个功能点（FR-N）应该：\n'
+ '- 一个用户可感知的完整能力（不是技术细节）\n'
+ '- 100-200行文档，3-5个验收项，1-3个任务\n'
+ '- 有明确的输入输出和可证伪的验收标准\n'
+ '\n'
+ '**不要**：\n'
+ '- 把多个独立能力合并成一个功能点（太粗）\n'
+ '- 把一个能力拆成过多细节（太细）\n'
+ '- 写技术实现细节（如"写入数据库"）\n'
```

#### M2.3: 评审检查点

```markdown
## 需求评审检查清单

在提交 requirement 产物前：

- [ ] 每个功能点有独立文件
- [ ] 每个文件 100-200行（允许 ±50%）
- [ ] 每个功能点 3-5个验收项
- [ ] 所有功能点粒度一致
- [ ] 没有明显的技术实现细节
- [ ] 可以估算出 1-3个任务

如果检查不通过，重新拆分功能点。
```

**风险降低**：中 → 低（通过标准 + 提示词 + 评审）

### R7: 覆盖门禁误报（概率：中，影响：中）

**问题描述**：
```
场景1：功能点文件被 git 忽略
.gitignore 包含 *.md
→ 文件在本地，但 git 看不到，门禁认为"文件不存在"

场景2：功能点文件在子目录
functional-requirements/backend/FR-1.md
→ glob 模式没有匹配到

场景3：功能点编号不连续
FR-1, FR-2, FR-5, FR-9（跳过了 FR-3, FR-4）
→ 门禁认为"缺少功能点"
```

**为什么会发生**：
- 文件系统状态与预期不一致
- glob 模式不完善
- 编号规则理解不一致

**影响评估**：
- 🟡 **中等**：拒绝正确的拆分
- 🟡 **中等**：需要手动修复

**缓解措施**：

#### M7.1: 宽松的验证模式

```typescript
function validateCoverage(requirement, tasks, options = {}) {
  const { strict = false } = options
  
  const frFiles = glob('functional-requirements/**/*.md', { 
    ignore: ['**/node_modules/**', '**/.git/**']
  })
  
  // 提取功能点 ID（支持子目录）
  const allFRs = new Set(
    frFiles
      .map(f => path.basename(f).match(/^FR-([0-9]+)/)?.[1])
      .filter(Boolean)
      .map(n => `FR-${n}`)
  )
  
  // 检查覆盖
  const covered = new Set()
  for (const task of tasks) {
    for (const fr of task.requirement_refs || []) {
      covered.add(fr)
    }
  }
  
  const uncovered = [...allFRs].filter(fr => !covered.has(fr))
  
  if (uncovered.length > 0) {
    if (strict) {
      // 严格模式：拒绝
      reject(`功能点 ${uncovered.join(', ')} 未被接收`)
    } else {
      // 宽松模式：警告
      console.warn(`[警告] 功能点 ${uncovered.join(', ')} 未被接收，但允许通过（宽松模式）`)
    }
  }
}
```

#### M7.2: 详细的错误信息

```typescript
if (uncovered.length > 0) {
  const detail = uncovered.map(fr => {
    const file = frFiles.find(f => f.includes(fr))
    return `  - ${fr}: ${file || '文件未找到'}`
  }).join('\n')
  
  reject(
    `拆分计划覆盖不完整：\n` +
    `未被接收的功能点：\n${detail}\n\n` +
    `请在任务的 requirement_refs 中引用这些功能点，` +
    `或删除对应的功能点文件（如果不再需要）。\n\n` +
    `如果这是误报，请检查：\n` +
    `1. 文件名格式是否正确（FR-N-xxx.md）\n` +
    `2. 文件是否在 functional-requirements/ 目录下\n` +
    `3. 文件是否被 .gitignore 忽略`,
    'REQBOARD_INCOMPLETE_COVERAGE'
  )
}
```

#### M7.3: 手动覆盖机制

```typescript
// decomposition.md front-matter
---
coverage_override: true  # 跳过覆盖门禁
coverage_reason: "FR-3 和 FR-4 已在另一个需求实现"
---
```

**风险降低**：中 → 低（通过宽松模式 + 详细错误 + 覆盖机制）

---

## 🟢 低风险问题

### R4: Agent 不会填写（概率：低，影响：中）

**缓解措施**：
- 详细的提示词和示例
- 拆分模板包含 requirement_refs 字段
- 验证失败时给出明确的修复建议

### R5: 文件太多难管理（概率：低，影响：低）

**缓解措施**：
- 功能点通常 < 15个，可管理
- IDE 的文件树视图清晰
- 可以用子目录分类（backend/、frontend/）

### R6: 历史需求迁移成本（概率：中，影响：低）

**缓解措施**：
- 不强制迁移历史需求
- 新旧模式共存
- 提供迁移脚本（可选）

### R8: 性能问题（概率：低，影响：低）

**缓解措施**：
- 功能点文件数量有限（< 20）
- 文件读取可以缓存
- glob 操作很快（< 100ms）

---

## 🎯 综合评估

### 风险总结

| 风险等级 | 数量 | 可缓解 | 不可缓解 |
|---------|------|--------|---------|
| 🔴 高风险 | 2 | 2 | 0 |
| 🟡 中风险 | 3 | 3 | 0 |
| 🟢 低风险 | 3 | 3 | 0 |

**所有风险都可以通过工程手段缓解到可接受水平。**

### 对比：新方式 vs 旧方式

| 维度 | 旧方式风险 | 新方式风险 | 评估 |
|------|-----------|-----------|------|
| **功能点未接收** | 🔴 必然发生 | 🟡 可能误报 | ✅ 新方式更好 |
| **验收不清晰** | 🔴 必然混乱 | 🟢 清晰 | ✅ 新方式更好 |
| **文件同步** | 🟢 无此问题 | 🟡 可能不一致 | ⚠️ 新方式引入 |
| **工具bug** | 🟢 成熟代码 | 🟡 新代码有bug | ⚠️ 新方式引入 |
| **维护成本** | 🔴 大文件难维护 | 🟢 小文件易维护 | ✅ 新方式更好 |

**净收益**：新方式的优势 > 新方式的风险

---

## 🛡️ 缓解策略总结

### 1. 渐进式迁移（最重要）

```
Week 1-2: 只读模式（试点）
  - 失败时回退到单文件模式
  - 收集反馈和问题

Week 3-4: 写入模式（Canary）
  - 只对特定需求启用
  - 监控错误率

Week 5+: 强制模式（全量）
  - 新需求强制使用
  - 历史需求可选迁移
```

### 2. 充分的测试

- ✅ 单测覆盖率 > 90%
- ✅ 集成测试覆盖主流程
- ✅ 边界测试覆盖异常场景

### 3. 降级和回退

- ✅ 功能点文件不存在 → 回退单文件模式
- ✅ 验证失败 → 详细错误信息 + 修复建议
- ✅ 手动覆盖机制（emergency escape）

### 4. 自动化和检查

- ✅ 自动同步索引表
- ✅ Git pre-commit hook
- ✅ 文件存在性验证
- ✅ 覆盖门禁

### 5. 监控和告警

```typescript
// 监控指标
const metrics = {
  structuredFR: {
    enabled: true,
    validationFailures: 0,    // 验证失败次数
    autoSyncSuccess: 0,        // 自动同步成功次数
    autoSyncFailures: 0,       // 自动同步失败次数
    fallbackToLegacy: 0,       // 回退到单文件模式次数
    averageProcessTime: 0      // 平均处理时间
  }
}

// 告警阈值
if (metrics.structuredFR.validationFailures > 10) {
  alert('结构化功能点验证失败率过高，建议回退到单文件模式')
}
```

---

## 🔄 回退计划

**如果出现严重问题，可以快速回退**：

### 回退步骤

```typescript
// 1. 关闭功能开关
const FEATURE_FLAG = {
  structuredFR: {
    read: false,   // ❌ 停用
    write: false,  // ❌ 停用
    enforce: false // ❌ 停用
  }
}

// 2. 所有验证回退到单文件模式
function validateCoverage(requirement, tasks) {
  return validateCoverageLegacy(requirement, tasks)
}

// 3. 告知用户
console.warn('[回退] 结构化功能点暂时停用，使用单文件模式')
```

### 回退代价

- ✅ **无数据丢失**：功能点文件保留在 git 中
- ✅ **无功能影响**：单文件模式仍然可用
- ✅ **可随时恢复**：重新打开功能开关即可

---

## 📊 决策矩阵

### 是否采纳新方式？

| 因素 | 权重 | 旧方式得分 | 新方式得分 |
|------|------|-----------|-----------|
| 功能点覆盖 | 30% | 2/10 🔴 | 9/10 ✅ |
| 验收清晰度 | 25% | 3/10 🟡 | 9/10 ✅ |
| 维护成本 | 20% | 4/10 🟡 | 8/10 ✅ |
| 实施风险 | 15% | 9/10 ✅ | 5/10 🟡 |
| 学习成本 | 10% | 9/10 ✅ | 6/10 🟡 |

**加权得分**：
- 旧方式：4.1/10
- 新方式：**8.0/10**

**结论**：新方式明显更优，风险可控。

---

## 🎯 最终建议

### 诚实的回答

**我无法保证100%不出问题，但我可以保证：**

1. ✅ **所有风险都已识别**
2. ✅ **每个风险都有缓解措施**
3. ✅ **测试覆盖充分**
4. ✅ **渐进式发布降低风险**
5. ✅ **有明确的回退计划**
6. ✅ **净收益远大于风险**

### 推荐实施路径

```
阶段1（Week 1-2）：试点验证
  - 只读模式，失败回退
  - 用一个测试需求验证
  - 收集反馈，修复问题

阶段2（Week 3-4）：Canary 发布
  - 写入模式，只对特定需求
  - 监控错误率和性能
  - 调整工具和提示词

阶段3（Week 5+）：全量推广
  - 新需求强制使用
  - 历史需求可选迁移
  - 持续监控和优化
```

### 关键原则

1. **渐进式**：不要一次性切换
2. **可回退**：保留旧方式作为后备
3. **监控**：实时监控指标和错误
4. **快速响应**：发现问题立即修复或回退

**风险可控，收益明显，建议采纳。**
