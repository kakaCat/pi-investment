# 功能点结构化方案：从混乱到清晰

## 💡 核心思想

**一个功能点 = 一个独立的结构化文件**

```
docs/requirements/<REQ>/
├── requirement.md           # 需求主文档（概述 + 索引）
├── functional-requirements/ # 功能点目录
│   ├── FR-1-async-jobs.md       # 功能点1：独立文件
│   ├── FR-2-query-status.md     # 功能点2：独立文件
│   ├── FR-3-checkpoint.md       # 功能点3：独立文件
│   ├── ...
│   └── FR-9-observability.md    # 功能点9：独立文件
├── design/                  # 设计文档
├── tasks/                   # 任务卡
└── decomposition.md         # 拆分计划（引用功能点文件）
```

---

## 🎯 优势分析

### 当前方式的问题

**requirement.md 大杂烩模式**：
```markdown
## 3. 功能点

### FR-1: 后台任务投递
目标：...（50行）
验收：...（20行）

### FR-2: 运行态查询
目标：...（40行）
验收：...（15行）

...（累计300+行，难以维护）
```

**问题**：
- ❌ 一个文件太长，难以定位
- ❌ 功能点之间混在一起
- ❌ 拆分时无法精确引用
- ❌ 验收时需要来回翻阅
- ❌ 修改一个功能点影响整个文件

### 结构化方式的优势

**功能点独立文件模式**：
```
FR-1-async-jobs.md         # 100行，专注一个功能
FR-2-query-status.md       # 80行，专注一个功能
...
```

**优势**：
- ✅ **原子性**：一个文件 = 一个功能点，职责清晰
- ✅ **可追溯**：任务卡直接引用文件路径
- ✅ **易验收**：逐个文件验收，进度清晰
- ✅ **易维护**：修改互不影响
- ✅ **可复用**：功能点文件可在多个需求间共享
- ✅ **强类型**：文件名即功能点 ID

---

## 📐 功能点文件模板

### 模板：functional-requirements/FR-N-title.md

```markdown
# FR-N: 功能点标题（一句话）

> **元信息**  
> 编号：FR-N  
> 需求：REQ-xxxxxx  
> 优先级：P0 / P1 / P2  
> 状态：pending / accepted / implementing / done  
> 创建：YYYY-MM-DD  
> 更新：YYYY-MM-DD

---

## 1. 功能描述

### 1.1 目标（What）

**用一句话说**：这个功能要达成什么。

**详细说明**：
- 解决什么问题？
- 为谁解决？
- 当前痛点是什么？

### 1.2 价值（Why）

- **用户价值**：用户得到什么好处
- **系统价值**：系统改善什么指标
- **优先级理由**：为什么现在做

### 1.3 边界（Scope）

**包含**：
- ✅ 做什么
- ✅ 覆盖哪些场景

**不包含**：
- ❌ 不做什么
- ❌ 延后到哪个版本

---

## 2. 功能规格

### 2.1 输入输出

**输入**：
- 参数1：类型、取值范围、约束
- 参数2：...

**输出**：
- 返回值：类型、格式
- 副作用：状态变更、通知

### 2.2 行为规格

**正常流程**：
1. 步骤1
2. 步骤2
3. ...

**异常流程**：
- 错误场景1 → 处理方式
- 错误场景2 → 处理方式

### 2.3 约束条件

**性能约束**：
- 响应时间：< 1s
- 并发支持：100 QPS

**数据约束**：
- 最大任务数：1000
- 保留时长：30天

---

## 3. 验收标准（可证伪）

### 3.1 功能验收

- [ ] **A1**：调用 X 接口，参数 Y，返回 Z
- [ ] **A2**：状态从 S1 变更到 S2
- [ ] **A3**：数据库写入记录 R

### 3.2 质量验收

- [ ] **Q1**：单测覆盖率 > 80%
- [ ] **Q2**：集成测试通过
- [ ] **Q3**：性能测试达标

### 3.3 文档验收

- [ ] **D1**：API 文档更新
- [ ] **D2**：使用指南补充

---

## 4. 依赖关系

### 4.1 前置依赖

- **FR-X**：必须先完成 X，因为...
- **技术债 T-Y**：必须先清理 Y

### 4.2 后续影响

- **FR-Z**：完成后可以继续 Z
- **模块 M**：会影响模块 M 的接口

---

## 5. 实施建议

### 5.1 技术方案要点

- 关键技术选型：用 X 而不是 Y，因为...
- 风险点：注意 Z 可能导致...
- 性能优化：在 W 处缓存...

### 5.2 拆分建议

建议拆成以下任务：
- **t1**：基础类型定义（依赖：无）
- **t2**：核心逻辑实现（依赖：t1）
- **t3**：集成测试（依赖：t2）

### 5.3 测试要点

- **边界测试**：空输入、最大值
- **并发测试**：100个并发请求
- **失败恢复**：中途异常能否恢复

---

## 6. 变更历史

| 日期 | 版本 | 变更内容 | 变更人 |
|------|------|---------|--------|
| 2026-09-25 | v1.0 | 初始版本 | Agent |
| 2026-09-26 | v1.1 | 补充边界约束 | Human |

---

## 7. 接收状态

> **机器维护区域，请勿手改**

### 接收任务

- [ ] **t-abc123** - 任务标题1
- [ ] **t-def456** - 任务标题2

### 接收统计

- 总任务数：2
- 已完成：0
- 进行中：0
- 待开始：2

### 状态更新

- 2026-09-25：FR-N 由任务 t-abc123 接收
- 2026-09-26：任务 t-abc123 完成
```

---

## 🔄 工作流变化

### 旧流程（单文件模式）

```
1. 写 requirement.md（300行大杂烩）
   ↓
2. 拆分时在 decomposition.md 写 RTM 表
   ↓
3. 落库时 requirement_refs = []（因为没工具支持）
   ↓
4. 验收时功能点"未被接收"
   ↓
5. 手动核对需求文档和任务
```

### 新流程（结构化模式）

```
1. 写 requirement.md（概述 + 索引）
   ↓
2. 每个功能点写独立文件 FR-N-xxx.md
   ↓
3. 拆分时任务直接引用文件路径
   task.requirement_refs = ["FR-1", "FR-3"]
   task.requirement_files = [
     "functional-requirements/FR-1-async-jobs.md",
     "functional-requirements/FR-3-checkpoint.md"
   ]
   ↓
4. 工具自动验证：文件存在 + 所有 FR 都被接收
   ↓
5. 验收时逐个文件检查验收项
   ↓
6. 验收完成后功能点文件标记 status: done
```

---

## 🛠️ 工具支持

### 修改1：requirement.md 模板变化

**旧模板**：
```markdown
## 3. 功能点

### FR-1: 后台任务投递
...（50行）

### FR-2: 运行态查询
...（40行）
```

**新模板**：
```markdown
## 3. 功能点索引

本需求包含 9 个功能点，详见各自文件：

| 编号 | 标题 | 优先级 | 状态 | 文件 |
|------|------|--------|------|------|
| FR-1 | 后台任务投递 | P0 | 🔴 pending | [FR-1-async-jobs.md](functional-requirements/FR-1-async-jobs.md) |
| FR-2 | 运行态查询 | P1 | 🔴 pending | [FR-2-query-status.md](functional-requirements/FR-2-query-status.md) |
| FR-3 | checkpoint 管理 | P0 | 🔴 pending | [FR-3-checkpoint.md](functional-requirements/FR-3-checkpoint.md) |
| ... | ... | ... | ... | ... |

### 快速导航

- **核心功能**（P0）：FR-1、FR-3、FR-4
- **查询功能**（P1）：FR-2、FR-9
- **容错恢复**（P0）：FR-5
- **测试验证**（P1）：FR-6、FR-8
- **工具改造**（P1）：FR-7

详细内容见各功能点文件。
```

### 修改2：拆分工具 schema 增强

**SubmitTool.ts**：
```typescript
requirement_refs: {
  type: 'array',
  items: { type: 'string', pattern: '^FR-[0-9]+$' },
  description: '本任务实现的功能点编号'
},

// ✅ 新增：功能点文件路径（可选，用于验证）
requirement_files: {
  type: 'array',
  items: { type: 'string' },
  description: '功能点文件路径（如 ["functional-requirements/FR-1-async-jobs.md"]）'
}
```

### 修改3：覆盖门禁增强

**Decompose.ts**：
```typescript
// 覆盖门禁增强版
function validateCoverage(requirement, tasks) {
  // 1. 检查所有功能点文件是否存在
  const frFiles = glob('functional-requirements/FR-*.md')
  if (frFiles.length === 0) {
    warn('未找到功能点文件，回退到单文件模式')
    return validateCoverageLegacy(requirement, tasks)
  }
  
  // 2. 提取功能点 ID（从文件名）
  const allFRs = frFiles.map(f => {
    const match = f.match(/FR-([0-9]+)/)
    return match ? `FR-${match[1]}` : null
  }).filter(Boolean)
  
  // 3. 检查任务覆盖
  const covered = new Set()
  for (const task of tasks) {
    for (const fr of task.requirement_refs || []) {
      covered.add(fr)
    }
  }
  
  // 4. 找出未覆盖的
  const uncovered = allFRs.filter(fr => !covered.has(fr))
  if (uncovered.length > 0) {
    reject(
      `功能点 ${uncovered.join(', ')} 未被任何任务接收。` +
      `每个任务的 requirement_refs 必须声明它实现了哪些功能点。`,
      'REQBOARD_INCOMPLETE_COVERAGE'
    )
  }
  
  // 5. 验证引用的功能点文件存在
  for (const task of tasks) {
    for (const fr of task.requirement_refs || []) {
      const expectedFile = `functional-requirements/${fr}-*.md`
      const found = frFiles.some(f => f.startsWith(`functional-requirements/${fr}-`))
      if (!found) {
        reject(
          `任务 ${task.key} 引用了不存在的功能点 ${fr}，` +
          `期望文件：${expectedFile}`,
          'REQBOARD_INVALID_FR_REF'
        )
      }
    }
  }
}
```

### 修改4：验收单生成增强

**Submit.ts (kind=verification)**：
```typescript
// 生成验收单时，从功能点文件提取验收项
async function generateAcceptanceSheet(requirement) {
  const frFiles = glob(`docs/requirements/${requirement.id}/functional-requirements/FR-*.md`)
  
  const items = []
  for (const file of frFiles) {
    const content = await readFile(file)
    
    // 提取功能点 ID
    const frId = extractFRId(file) // FR-1, FR-2, ...
    
    // 提取验收标准（## 3. 验收标准 部分）
    const acceptanceCriteria = extractSection(content, '验收标准')
    
    // 解析验收项（- [ ] **A1**: ...）
    const criteria = parseAcceptanceCriteria(acceptanceCriteria)
    
    for (const criterion of criteria) {
      items.push({
        id: `${frId}-${criterion.id}`, // FR-1-A1, FR-1-A2, ...
        title: `${frId}: ${criterion.title}`,
        expectation: criterion.expectation,
        source: file,
        verdict: null, // 待验收
        verdictReason: null
      })
    }
  }
  
  return {
    version: 1,
    items,
    createdAt: Date.now()
  }
}
```

---

## 📊 效果对比

### 旧方式问题重现

**场景**：REQ-260925110957-552d

```
问题链：
1. requirement.md 包含 9 个功能点（300行混在一起）
2. 拆分时手写 RTM 表（仅文档，无数据）
3. 任务 requirement_refs = []（工具不支持）
4. 功能点全部 🔴 未被接收
5. 验收时无法生成功能点验收项
6. 验收人说"拆分有问题"
```

### 新方式效果

**场景**：未来的需求

```
流程：
1. 写 requirement.md 概述 + 索引表
2. 写 9 个功能点文件（FR-1.md 到 FR-9.md）
3. 每个文件包含：目标、规格、验收标准、拆分建议
4. 拆分时任务引用功能点 ID + 文件路径
5. 覆盖门禁自动检查：
   ✅ 所有功能点文件存在
   ✅ 所有功能点被任务接收
   ✅ 引用的功能点文件有效
6. 验收时从功能点文件提取验收项
7. 逐个功能点文件验收：
   FR-1: 3个验收项全部通过 ✅
   FR-2: 2个验收项全部通过 ✅
   ...
8. 所有功能点验收通过 → 自动归档
```

---

## 🚀 迁移计划

### 阶段1：模板和工具（1周）

**Week 1**：
- [ ] 创建功能点文件模板
- [ ] 修改 requirement.md 主模板（索引表）
- [ ] 修改 SubmitTool schema（requirement_files）
- [ ] 修改 Decompose 覆盖门禁（文件验证）
- [ ] 修改 Submit 验收单生成（从文件提取）
- [ ] 单测 + 集成测试

### 阶段2：试点需求（1周）

**Week 2**：
- [ ] 选一个新需求试点
- [ ] 按新模板编写功能点文件
- [ ] 走完整流程（拆分 → 实施 → 验收）
- [ ] 收集反馈和问题
- [ ] 调整模板和工具

### 阶段3：全面推广（持续）

**Week 3+**：
- [ ] 更新需求编写指南
- [ ] 更新提示词（要求功能点独立文件）
- [ ] 历史需求可选迁移（不强制）
- [ ] 新需求强制使用新模板

---

## 💡 最佳实践

### 1. 功能点文件命名

**规范**：`FR-<编号>-<简短标题>.md`

**好的例子**：
- ✅ `FR-1-async-jobs.md`
- ✅ `FR-2-query-status.md`
- ✅ `FR-3-checkpoint-manager.md`

**不好的例子**：
- ❌ `FR1.md`（缺少标题）
- ❌ `async-jobs.md`（缺少编号）
- ❌ `FR-1.md`（缺少标题，难以区分）

### 2. 功能点粒度

**一个功能点 = 一个用户可感知的完整能力**

**好的粒度**：
- ✅ FR-1: 后台任务投递（工具调用 → 返回 job_id）
- ✅ FR-2: 运行态查询（查询接口 → 返回进度）

**不好的粒度**：
- ❌ 过粗：FR-1: 后台执行系统（涵盖5个子功能）
- ❌ 过细：FR-1: 注册任务到 ctx.jobs（太技术细节）

### 3. 验收标准要可证伪

**可证伪的例子**：
- ✅ 调用 `reqboard_task_run`，返回 `{dispatched: true, job_id: "reqboard-1"}`
- ✅ 数据库 tasks 表写入 `runId` 字段
- ✅ 执行时间 < 1s（95% 分位）

**不可证伪的例子**：
- ❌ 系统运行良好
- ❌ 用户体验提升
- ❌ 性能优化

### 4. 接收状态自动更新

**机制**：
- 拆分时：任务声明 `requirement_refs = ["FR-1"]`
- 系统自动：在 `FR-1-xxx.md` 的"接收状态"区写入任务引用
- 任务完成时：更新"已完成"计数
- 所有任务完成：功能点 status: done

**不要手动改接收状态区**：
- 由系统自动维护
- 类似 requirement.md 的 `reqboard:marks` 区

---

## 🎯 总结

### 核心改进

| 维度 | 旧方式 | 新方式 | 改进 |
|------|--------|--------|------|
| 文件结构 | 单个大文件 | 功能点独立文件 | ✅ 原子化 |
| 可追溯性 | RTM 表（文档） | requirement_refs + 文件路径 | ✅ 强类型 |
| 覆盖检查 | 无 | 门禁自动验证 | ✅ 自动化 |
| 验收粒度 | 任务级 | 功能点级 | ✅ 精确化 |
| 维护成本 | 高（大文件） | 低（小文件） | ✅ 可维护 |

### 关键价值

1. **拆分更精确**：任务与功能点的映射从"文档说明"变成"数据引用"
2. **验收更清晰**：逐个功能点文件验收，进度一目了然
3. **维护更简单**：修改一个功能点不影响其他
4. **复用更容易**：功能点文件可在多个需求间共享
5. **自动化更强**：工具可以验证文件存在、覆盖完整性

### 实施建议

- ✅ **立即开始**：下一个新需求就用新模板
- ✅ **不强制迁移**：历史需求保持原样
- ✅ **逐步完善**：根据使用反馈调整模板
- ✅ **工具先行**：先实现工具支持，再推广模板
