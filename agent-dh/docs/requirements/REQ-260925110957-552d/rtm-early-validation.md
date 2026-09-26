# RTM 表前置校验方案：从拆分前移到文档提交

## 💡 核心思想

**在提交需求文档（requirement）时就校验 RTM 表的完整性和正确性，而不是等到拆分时才发现问题。**

---

## 🎯 问题分析

### 当前问题

**校验时机太晚**：
```
1. 写需求文档（包含 FR-1 到 FR-9）
2. 提交 requirement 产物 ✅（无校验）
3. 人工确认 ✅
4. 写拆分计划（decomposition.md）
5. 提交 plan 产物 ✅（无校验）
6. 人工批准 ✅
7. reqboard_decompose 落库 ❌（发现问题：requirement_refs 为空）
   └─ 太晚了！浪费了大量时间
```

**后果**：
- ❌ 拆分时才发现功能点缺失
- ❌ 需要回退重写拆分计划
- ❌ 浪费时间，降低效率

### 理想流程

**校验前置到文档提交**：
```
1. 写需求文档（包含 FR-1 到 FR-9）
2. 写功能点文件（FR-1.md 到 FR-9.md）
3. 提交 requirement 产物
   └─ 校验1：功能点文件是否存在 ✅
   └─ 校验2：功能点文件格式是否正确 ✅
4. 人工确认 ✅
5. 写拆分计划（decomposition.md）
   └─ 包含 RTM 表（任务 → 功能点映射）
6. 提交 plan 产物
   └─ 校验3：RTM 表覆盖是否完整 ✅
   └─ 校验4：任务的 requirement_refs 是否填写 ✅
7. 人工批准 ✅
8. reqboard_decompose 落库 ✅（一定成功）
```

**优势**：
- ✅ 问题早发现（提交时而非拆分时）
- ✅ 反馈快（几秒而非几小时）
- ✅ 成本低（重写文档而非重新拆分）

---

## 🛠️ 实施方案

### 修改1：requirement 产物提交时校验功能点文件

**文件**：`packages/web/dsh-pmboard/src/application/use-cases/Submit.ts`

**位置**：`kind='requirement'` 分支

**修改前**：
```typescript
if (kind === 'requirement') {
  // 只登记产物，不做校验
  registerArtifact(requirement, {
    stage: 'brainstorming',
    kind: 'requirement',
    path: args.path,
    summary: args.summary
  })
}
```

**修改后**：
```typescript
if (kind === 'requirement') {
  // ✅ 校验1：功能点文件结构
  const frValidation = await validateFunctionalRequirements(
    requirement.id, 
    args.path
  )
  
  if (!frValidation.valid) {
    reject(
      `需求文档提交失败：功能点文件校验不通过\n` +
      `错误：${frValidation.errors.join('\n')}\n\n` +
      `建议：${frValidation.suggestions.join('\n')}`,
      'REQBOARD_FR_VALIDATION_FAILED'
    )
  }
  
  // 校验通过，登记产物
  registerArtifact(requirement, {
    stage: 'brainstorming',
    kind: 'requirement',
    path: args.path,
    summary: args.summary,
    frValidation // 记录校验结果
  })
  
  // 记录功能点清单（供后续 plan 校验使用）
  requirement.functionalRequirements = frValidation.frList
}
```

#### 校验函数实现

```typescript
/**
 * 校验功能点文件结构
 */
async function validateFunctionalRequirements(
  requirementId: string,
  requirementDocPath: string
): Promise<FRValidationResult> {
  const errors: string[] = []
  const warnings: string[] = []
  const suggestions: string[] = []
  
  // 1. 读取需求文档，提取功能点列表
  const reqDoc = await docs.read(requirementDocPath)
  const frListFromDoc = extractFRList(reqDoc) // 从索引表提取
  
  // 2. 扫描功能点目录
  const frDir = `docs/requirements/${requirementId}/functional-requirements`
  const frFiles = await glob(`${frDir}/FR-*.md`)
  
  // 校验2.1：功能点目录是否存在
  if (frFiles.length === 0 && frListFromDoc.length > 0) {
    errors.push(
      `需求文档声明了 ${frListFromDoc.length} 个功能点，` +
      `但 ${frDir} 目录不存在或为空`
    )
    suggestions.push(
      `请为每个功能点创建独立文件：` +
      `functional-requirements/FR-N-<title>.md`
    )
    return { valid: false, errors, warnings, suggestions, frList: [] }
  }
  
  // 3. 从文件名提取功能点 ID
  const frListFromFiles = frFiles.map(file => {
    const match = path.basename(file).match(/^FR-([0-9]+)/)
    return match ? `FR-${match[1]}` : null
  }).filter(Boolean)
  
  // 校验3.1：文件名格式
  const invalidFiles = frFiles.filter(file => {
    return !path.basename(file).match(/^FR-[0-9]+-[a-z0-9-]+\.md$/)
  })
  if (invalidFiles.length > 0) {
    errors.push(
      `功能点文件名格式不正确：${invalidFiles.join(', ')}\n` +
      `正确格式：FR-N-<title>.md（如 FR-1-async-jobs.md）`
    )
  }
  
  // 校验3.2：文件名重复
  const duplicates = findDuplicateFRs(frListFromFiles)
  if (duplicates.length > 0) {
    errors.push(
      `功能点编号重复：${duplicates.join(', ')}\n` +
      `每个功能点编号只能对应一个文件`
    )
  }
  
  // 4. 对比文档与文件
  const missingInFiles = frListFromDoc.filter(fr => !frListFromFiles.includes(fr))
  const missingInDoc = frListFromFiles.filter(fr => !frListFromDoc.includes(fr))
  
  // 校验4.1：文档声明了但文件缺失
  if (missingInFiles.length > 0) {
    errors.push(
      `需求文档索引表包含 ${missingInFiles.join(', ')}，` +
      `但对应的文件不存在`
    )
    suggestions.push(
      `请为这些功能点创建文件，或从索引表中删除`
    )
  }
  
  // 校验4.2：文件存在但文档未声明
  if (missingInDoc.length > 0) {
    warnings.push(
      `功能点文件 ${missingInDoc.join(', ')} 存在，` +
      `但需求文档索引表中未包含（将自动同步）`
    )
    // 自动同步到索引表
    await autoSyncFRIndex(requirementId)
  }
  
  // 5. 校验每个功能点文件的内容
  const frList: FRMetadata[] = []
  for (const file of frFiles) {
    const content = await docs.read(file)
    const validation = validateFRFileContent(file, content)
    
    if (!validation.valid) {
      errors.push(`${path.basename(file)}: ${validation.error}`)
    } else {
      frList.push(validation.metadata)
    }
  }
  
  // 返回结果
  return {
    valid: errors.length === 0,
    errors,
    warnings,
    suggestions,
    frList
  }
}

/**
 * 校验单个功能点文件的内容
 */
function validateFRFileContent(
  filePath: string,
  content: string
): FRFileValidation {
  const errors: string[] = []
  
  // 必须包含的章节
  const requiredSections = [
    '## 1. 功能描述',
    '## 2. 功能规格',
    '## 3. 验收标准'
  ]
  
  for (const section of requiredSections) {
    if (!content.includes(section)) {
      errors.push(`缺少必需章节：${section}`)
    }
  }
  
  // 验收标准必须可证伪
  const acceptanceSection = extractSection(content, '3. 验收标准')
  if (acceptanceSection) {
    const criteria = parseAcceptanceCriteria(acceptanceSection)
    if (criteria.length === 0) {
      errors.push(`验收标准章节为空或格式不正确`)
    }
    
    // 检查是否可证伪
    for (const c of criteria) {
      if (isVague(c.expectation)) {
        errors.push(
          `验收标准 ${c.id} 不可证伪："${c.expectation}"\n` +
          `应该包含具体的命令、输入、输出、指标`
        )
      }
    }
  }
  
  // 提取元信息
  const metadata = extractFRMetadata(content)
  
  return {
    valid: errors.length === 0,
    error: errors.join('; '),
    metadata
  }
}
```

---

### 修改2：plan 产物提交时校验 RTM 表

**文件**：`packages/web/dsh-pmboard/src/application/use-cases/Submit.ts`

**位置**：`kind='plan'` 分支

**修改前**：
```typescript
if (kind === 'plan') {
  // 只校验任务表结构，不校验 requirement_refs
  const tasks = normalizePlanTasks(args.tasks ?? [])
  assertDagAcyclic(tasks)
  
  // 登记计划
  requirement.plan = {
    path: args.path,
    summary: args.summary,
    submittedAt: nowTs,
    tasks
  }
}
```

**修改后**：
```typescript
if (kind === 'plan') {
  const tasks = normalizePlanTasks(args.tasks ?? [])
  assertDagAcyclic(tasks)
  
  // ✅ 校验2：RTM 表覆盖完整性
  const rtmValidation = validateRTMCoverage(requirement, tasks)
  
  if (!rtmValidation.valid) {
    reject(
      `拆分计划提交失败：RTM 表覆盖不完整\n` +
      `错误：${rtmValidation.errors.join('\n')}\n\n` +
      `当前覆盖：\n${rtmValidation.coverageReport}\n\n` +
      `建议：${rtmValidation.suggestions.join('\n')}`,
      'REQBOARD_RTM_INCOMPLETE'
    )
  }
  
  // 校验通过，登记计划
  requirement.plan = {
    path: args.path,
    summary: args.summary,
    submittedAt: nowTs,
    tasks,
    rtmValidation // 记录 RTM 校验结果
  }
}
```

#### RTM 表校验函数

```typescript
/**
 * 校验 RTM 表覆盖完整性
 */
function validateRTMCoverage(
  requirement: RequirementRecord,
  tasks: PlanTask[]
): RTMValidationResult {
  const errors: string[] = []
  const warnings: string[] = []
  const suggestions: string[] = []
  
  // 1. 获取功能点清单（从 requirement 产物）
  const allFRs = requirement.functionalRequirements?.map(fr => fr.id) ?? []
  
  if (allFRs.length === 0) {
    // 如果没有功能点清单，尝试从文件扫描
    const frFiles = glob(`docs/requirements/${requirement.id}/functional-requirements/FR-*.md`)
    allFRs.push(...frFiles.map(f => extractFRId(f)))
  }
  
  if (allFRs.length === 0) {
    warnings.push('未找到功能点清单，跳过 RTM 覆盖检查')
    return { valid: true, warnings, errors: [], suggestions: [], coverageReport: '' }
  }
  
  // 2. 从任务中收集 requirement_refs
  const covered = new Set<string>()
  const taskCoverage = new Map<string, string[]>() // task.key → FRs
  
  for (const task of tasks) {
    const refs = task.requirement_refs ?? []
    
    // 校验2.1：任务必须声明 requirement_refs
    if (refs.length === 0) {
      errors.push(
        `任务 ${task.key} (${task.title}) 缺少 requirement_refs 字段\n` +
        `每个任务必须声明它实现了哪些功能点`
      )
    }
    
    // 校验2.2：引用的功能点必须存在
    for (const fr of refs) {
      if (!allFRs.includes(fr)) {
        errors.push(
          `任务 ${task.key} 引用了不存在的功能点：${fr}\n` +
          `有效的功能点：${allFRs.join(', ')}`
        )
      }
      covered.add(fr)
    }
    
    taskCoverage.set(task.key, refs)
  }
  
  // 3. 检查覆盖完整性
  const uncovered = allFRs.filter(fr => !covered.has(fr))
  
  if (uncovered.length > 0) {
    errors.push(
      `功能点 ${uncovered.join(', ')} 未被任何任务接收\n` +
      `每个功能点至少要被一个任务的 requirement_refs 引用`
    )
    
    suggestions.push(
      `请在任务的 requirement_refs 中添加这些功能点，` +
      `或从功能点目录中删除对应文件（如果不再需要）`
    )
  }
  
  // 4. 生成覆盖报告
  const coverageReport = generateCoverageReport(allFRs, taskCoverage)
  
  // 5. 检查覆盖质量
  const overCovered = allFRs.filter(fr => {
    const count = Array.from(taskCoverage.values()).filter(refs => refs.includes(fr)).length
    return count > 3 // 一个功能点被超过3个任务引用
  })
  
  if (overCovered.length > 0) {
    warnings.push(
      `功能点 ${overCovered.join(', ')} 被过多任务引用（>3个）\n` +
      `可能粒度太粗，建议拆分成更小的功能点`
    )
  }
  
  return {
    valid: errors.length === 0,
    errors,
    warnings,
    suggestions,
    coverageReport
  }
}

/**
 * 生成覆盖报告
 */
function generateCoverageReport(
  allFRs: string[],
  taskCoverage: Map<string, string[]>
): string {
  const lines: string[] = []
  
  lines.push('RTM 覆盖矩阵：')
  lines.push('')
  lines.push('| 功能点 | 接收任务 | 状态 |')
  lines.push('|--------|---------|------|')
  
  for (const fr of allFRs) {
    const tasks = Array.from(taskCoverage.entries())
      .filter(([_, refs]) => refs.includes(fr))
      .map(([key, _]) => key)
    
    const status = tasks.length > 0 ? '✅ 已接收' : '🔴 未接收'
    const taskList = tasks.length > 0 ? tasks.join(', ') : '—'
    
    lines.push(`| ${fr} | ${taskList} | ${status} |`)
  }
  
  lines.push('')
  lines.push(`覆盖统计：${covered.size}/${allFRs.length} (${(covered.size / allFRs.length * 100).toFixed(0)}%)`)
  
  return lines.join('\n')
}
```

---

### 修改3：decompose 时的双重保险

**文件**：`packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`

**修改**：
```typescript
// 在 decompose 时再次检查（双重保险）
export async function executeDecompose(deps, args, exec) {
  // ... 前置检查 ...
  
  // ✅ 双重保险：再次检查 RTM 覆盖
  // 正常情况下 plan 提交时已经检查过，这里是最后一道防线
  const rtmValidation = validateRTMCoverage(target, draft)
  
  if (!rtmValidation.valid) {
    // 这种情况理论上不应该发生（plan 提交时已拦截）
    console.error('[异常] decompose 时发现 RTM 覆盖不完整，plan 提交时应该拦截')
    
    reject(
      `拆分失败：RTM 表覆盖不完整\n` +
      `${rtmValidation.errors.join('\n')}\n\n` +
      `这是一个异常情况，请报告此问题`,
      'REQBOARD_RTM_INCOMPLETE'
    )
  }
  
  // ... 落库 ...
}
```

---

## 📊 校验时机对比

### Before（当前方式）

```
时间线：
T0: 写需求文档（30分钟）
T1: 提交 requirement 产物（❌ 无校验）
T2: 人工确认（5分钟）
T3: 写拆分计划（60分钟）
T4: 提交 plan 产物（❌ 无校验）
T5: 人工批准（10分钟）
T6: reqboard_decompose 落库
    ↓
    ❌ 发现：requirement_refs 为空
    ↓
    回退到 T3，重写拆分计划（60分钟）
    ↓
    总耗时：30 + 60 + 60 = 150分钟
```

### After（前置校验）

```
时间线：
T0: 写需求文档（30分钟）
T1: 写功能点文件（30分钟）
T2: 提交 requirement 产物
    ↓
    ✅ 校验功能点文件（2秒）
    ↓
    ❌ 发现：FR-5.md 缺失
    ↓
    补写 FR-5.md（10分钟）
    ↓
T3: 重新提交 requirement 产物
    ↓
    ✅ 校验通过
    ↓
T4: 人工确认（5分钟）
T5: 写拆分计划（60分钟）
T6: 提交 plan 产物
    ↓
    ✅ 校验 RTM 表（2秒）
    ↓
    ❌ 发现：FR-5 未被任务接收
    ↓
    补充任务引用（5分钟）
    ↓
T7: 重新提交 plan 产物
    ↓
    ✅ 校验通过
    ↓
T8: 人工批准（10分钟）
T9: reqboard_decompose 落库
    ↓
    ✅ 一定成功（双重保险已检查）
    ↓
    总耗时：30 + 30 + 10 + 60 + 5 = 135分钟
```

**节省时间**：150 - 135 = **15分钟**

**更重要的是**：
- ✅ 问题早发现（提交时而非拆分时）
- ✅ 反馈快（2秒而非等到落库）
- ✅ 心理负担小（改文档而非重新拆分）

---

## 🎯 校验层次

### 三层防护

```
第1层：requirement 产物提交时
  ├─ 功能点文件是否存在
  ├─ 文件名格式是否正确
  ├─ 文件内容是否完整
  └─ 验收标准是否可证伪

第2层：plan 产物提交时
  ├─ 任务是否声明 requirement_refs
  ├─ 引用的功能点是否存在
  ├─ 所有功能点是否被接收
  └─ 生成 RTM 覆盖报告

第3层：decompose 落库时
  └─ 双重保险（理论上不应该失败）
```

---

## 📝 用户体验

### 提交 requirement 时

```typescript
// Agent 调用
reqboard_submit({
  kind: 'requirement',
  requirement_id: 'REQ-xxx',
  path: 'docs/requirements/REQ-xxx/requirement.md',
  summary: '需求已完成，包含9个功能点'
})

// 成功返回
{
  success: true,
  artifact: { kind: 'requirement', ... },
  frValidation: {
    valid: true,
    frCount: 9,
    frList: ['FR-1', 'FR-2', ..., 'FR-9'],
    warnings: [
      'FR-5-checkpoint.md 超过200行，建议拆分'
    ]
  },
  note: '已登记 requirement 产物，功能点文件校验通过（9个功能点）'
}

// 失败返回
{
  error: 'REQBOARD_FR_VALIDATION_FAILED',
  message: '需求文档提交失败：功能点文件校验不通过',
  errors: [
    'FR-3-checkpoint.md 缺少必需章节：## 3. 验收标准',
    'FR-5-orphan.md 存在但需求文档索引表中未包含'
  ],
  suggestions: [
    '请在 FR-3-checkpoint.md 中补充验收标准章节',
    '请将 FR-5 添加到 requirement.md 的功能点索引表'
  ]
}
```

### 提交 plan 时

```typescript
// Agent 调用
reqboard_submit({
  kind: 'plan',
  requirement_id: 'REQ-xxx',
  path: 'docs/requirements/REQ-xxx/decomposition.md',
  summary: '拆分计划已完成，23个任务',
  tasks: [
    {
      key: 't1',
      title: '领域类型定义',
      requirement_refs: ['FR-3', 'FR-4', 'FR-9'], // ✅ 有引用
      ...
    },
    ...
  ]
})

// 成功返回
{
  success: true,
  plan: { ... },
  rtmValidation: {
    valid: true,
    coverage: '9/9 (100%)',
    coverageReport: '
      | FR-1 | t3, t9, t10, t13, t17, t19 | ✅ 已接收 |
      | FR-2 | t11, t18, t19 | ✅ 已接收 |
      ...
    '
  },
  note: '已提交拆分计划，RTM 表覆盖完整（9/9, 100%）'
}

// 失败返回
{
  error: 'REQBOARD_RTM_INCOMPLETE',
  message: '拆分计划提交失败：RTM 表覆盖不完整',
  errors: [
    '任务 t5 (写集冲突检测) 缺少 requirement_refs 字段',
    '功能点 FR-8 未被任何任务接收'
  ],
  coverageReport: '
    | FR-1 | t3, t9, t10 | ✅ 已接收 |
    ...
    | FR-8 | — | 🔴 未接收 |
    
    覆盖统计：8/9 (89%)
  ',
  suggestions: [
    '请在任务 t5 中添加 requirement_refs 字段',
    '请添加任务接收 FR-8，或从功能点目录删除 FR-8-deploy.md'
  ]
}
```

---

## 🔧 提示词更新

### requirement 阶段提示词

```
## 需求文档结构要求

1. **主文档**：requirement.md
   - 需求概述
   - 功能点索引表（自动生成）
   - 边界和约束

2. **功能点文件**：functional-requirements/FR-N-<title>.md
   - 每个功能点一个独立文件
   - 文件名格式：FR-<编号>-<英文标题>.md
   - 必须包含章节：功能描述、功能规格、验收标准

3. **提交前检查**：
   - [ ] 功能点索引表完整
   - [ ] 每个功能点有独立文件
   - [ ] 文件名格式正确
   - [ ] 验收标准可证伪

提交时会自动校验，不通过会拒绝提交。
```

### decomposing 阶段提示词

```
## 拆分计划要求

1. **任务定义必须包含**：
   - key: 任务引用键
   - title: 任务标题
   - **requirement_refs: 实现的功能点编号（必填）**
   - stages: 阶段列表
   - acceptance: 验收标准
   - implementation: 实施方案

2. **RTM 表覆盖要求**：
   - 每个任务必须声明 requirement_refs
   - 每个功能点至少被一个任务接收
   - 引用的功能点必须存在

3. **提交前检查**：
   - [ ] 所有任务都有 requirement_refs
   - [ ] 所有功能点都被接收
   - [ ] RTM 覆盖报告完整

提交时会自动校验 RTM 表，覆盖不完整会拒绝提交。
```

---

## 📊 效果预期

### 指标对比

| 指标 | Before | After | 改进 |
|------|--------|-------|------|
| requirement_refs 缺失率 | 100% | < 5% | ✅ 95% |
| 拆分失败率 | 50% | < 10% | ✅ 80% |
| 返工次数 | 2-3次 | 0-1次 | ✅ 70% |
| 平均返工时间 | 60分钟 | 10分钟 | ✅ 83% |
| 问题发现时间 | 拆分时 | 提交时 | ✅ 提前2小时 |

### 用户反馈预期

**Before**：
> "拆分花了2小时，结果落库时说 requirement_refs 为空，又要重写😭"

**After**：
> "提交 requirement 时就提示 FR-5 文件缺失，补了10分钟就通过了✅"
> "提交 plan 时立即看到覆盖报告，FR-8 未接收，补了5分钟搞定✅"

---

## 🎯 总结

### 核心改进

1. **校验前置**：从拆分时前移到文档提交时
2. **快速反馈**：2秒而非2小时
3. **成本降低**：改文档而非重新拆分
4. **三层防护**：requirement → plan → decompose

### 实施优先级

| 修改 | 优先级 | 工作量 | 收益 |
|------|--------|--------|------|
| requirement 产物校验 | P0 | 4小时 | 🔴 高 |
| plan 产物 RTM 校验 | P0 | 6小时 | 🔴 高 |
| decompose 双重保险 | P1 | 1小时 | 🟡 中 |
| 提示词更新 | P1 | 1小时 | 🟡 中 |

**总计**：约12小时

### 与结构化方案的关系

- ✅ **互补**：前置校验 + 结构化文件 = 完整方案
- ✅ **独立**：可以先实施前置校验，再实施结构化
- ✅ **增强**：结构化文件让校验更简单（文件名即 ID）
