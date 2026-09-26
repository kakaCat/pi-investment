# 需求追溯性模板改进总结

> 改进日期：2026-09-26  
> 改进范围：dsh-pmboard 内置模板（templates/）  
> 改进目标：建立完整的四级追溯链（需求 → 设计 → 任务 → 测试）

---

## 📋 改进概述

### 核心理念

建立**完整的四级追溯链**，确保每一层都明确声明"我在服务/实现上一层的哪些条款"：

```
需求文档（requirement.md）
  FR-1, FR-2, FR-3...
    ↓ serves（设计参考需求）
设计文档（design/*.md）
  章节 1.1, 2.3... `serves: FR-1`
    ↓ implements（任务参考设计）
任务卡（tasks/*.md）
  范围 - 设计落点：design/architecture#1.1
    ↓ covers（测试覆盖任务）
测试用例（tests/*.md）
  TC-1 `covers: t-xxx` `validates: FR-1`
```

---

## 🎯 关键改进点

### 1. 统一设计文档的标注方式（方式 A：行内标注）

**❌ 删除**：front-matter 的 `requirement_refs`（冗余且隐藏）
```yaml
---
requirement_refs: [FR-1, FR-2]  # 删除这种方式
---
```

**✅ 采用**：章节级行内标注（直观且精确）
```markdown
## 1. 工具删除架构 \`serves: FR-1\`

### 1.1 删除工具目录 \`serves: FR-1\`
删除三个手动工具目录...

### 1.2 修改配置文件 \`serves: FR-2, FR-6\`
修改 stage-configs.ts...
```

**优点**：
- 直观：每个章节旁边就能看到它服务哪个 FR
- 精确：不同章节可以服务不同的 FR
- 灵活：一个章节可以服务多个 FR

---

### 2. 任务卡添加设计追溯

**改进前（断层）**：
```markdown
## 解决什么问题

（未填写——开工前补充这张卡要解决的业务问题）  # 永远是空的！

## 范围
- 阶段：implement
- 端侧：backend
```

**改进后（完整追溯）**：
```markdown
## 解决什么问题

**实现设计方案**：{{DESIGN_REFERENCE}}

**需求背景**：{{REQUIREMENT_BACKGROUND}}

**设计方案摘要**：
{{DESIGN_SUMMARY}}

**预期影响**：
{{EXPECTED_IMPACT}}

## 范围
- 阶段：{{TASK_PHASE}}
- 端侧：{{TASK_SIDE}}
- 需求条款：{{REQUIREMENT_REFS}}
- 设计落点：{{DESIGN_SERVES}}  ← 新增！引用设计章节
- 覆盖用例：{{TEST_CASES}}
```

**关键字段**：
- `{{DESIGN_REFERENCE}}`：如 `design/architecture.md § 1.1`
- `{{DESIGN_SERVES}}`：如 `design/architecture#1.1, design/interfaces#2.3`

---

### 3. 测试用例添加追溯标注

**新增标注**：
```markdown
### TC-1: 工具删除验证 \`covers: t-354ea0\` \`validates: FR-1\`

**测试目标**：验证三个工具目录已物理删除

**测试任务**：t-354ea0 删除工具目录
**验证需求**：FR-1 删除过时工具
**验证设计**：design/architecture.md § 1.1
```

---

## 📐 完整追溯链示例

### Level 1: 需求文档

```markdown
## 功能点

- **FR-1 删除过时工具**：删除 DecomposeTool/MoveTool/TaskMoveTool 及其代码
- **FR-2 Dive Armed 默认化**：新需求默认 armed 模式
```

---

### Level 2: 设计文档（design/architecture.md）

```markdown
# 架构设计

## 1. 工具删除架构 \`serves: FR-1\`

### 1.1 删除工具目录结构 \`serves: FR-1\`
物理删除三个手动工具目录：
- DecomposeTool/
- MoveTool/
- TaskMoveTool/

### 1.2 删除 use-case 层代码 \`serves: FR-1\`
删除业务逻辑文件：
- Decompose.ts
- MoveRequirement.ts
- MoveTask.ts

## 2. 配置变更 \`serves: FR-2\`

### 2.1 创建默认值改为 armed \`serves: FR-2\`
reqboard_create/capture 默认 dive.activation = 'armed'
```

---

### Level 3: 任务卡（tasks/t-354ea0.md）

```markdown
# t-354ea0 删除工具目录

## 在做什么
删除 DecomposeTool/MoveTool/TaskMoveTool 三个工具目录

## 解决什么问题

**实现设计方案**：design/architecture.md § 1.1 "删除工具目录结构"

**需求背景**：FR-1 要求删除过时的手动工具，因为已被 Dive Armed 自动模式替代

**设计方案摘要**：
物理删除三个工具目录及其所有文件，从工具注册文件中移除导出，
确保 DSH 启动时不再加载这些工具。

**预期影响**：
- 工具列表中不再显示 reqboard_decompose/move/task_move
- 已有依赖这些工具的代码需要迁移到 Dive 模式

## 范围
- 阶段：implement
- 端侧：backend
- 需求条款：FR-1
- 设计落点：design/architecture#1.1
- 覆盖用例：TC-1

## 得到什么结果
运行命令验证三个工具目录已删除：
\`\`\`bash
ls packages/web/dsh-pmboard/src/tools/ | grep -E '(Decompose|Move|TaskMove)'
# 返回空 = 成功
\`\`\`
```

---

### Level 4: 测试用例（tests/test-evidence.md）

```markdown
# 测试证据文档

## TC-1: 工具目录删除验证 \`covers: t-354ea0\` \`validates: FR-1\`

**测试任务**：t-354ea0 删除工具目录
**验证需求**：FR-1 删除过时工具
**验证设计**：design/architecture.md § 1.1

**测试步骤**：
\`\`\`bash
ls packages/web/dsh-pmboard/src/tools/ | \
  grep -E '(Decompose|Move|TaskMove)' || \
  echo "PASS: 工具目录已删除"
\`\`\`

**预期结果**：返回 "PASS: 工具目录已删除"
**实际结果**：✅ PASS
**执行时间**：2026-09-25 16:53:21
```

---

## 🔧 模板占位符说明

### 任务卡模板占位符

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `{{TASK_ID}}` | 任务 ID | t-354ea0 |
| `{{TASK_TITLE}}` | 任务标题 | 删除工具目录 |
| `{{TASK_DESCRIPTION}}` | 在做什么 | 删除 DecomposeTool/MoveTool/TaskMoveTool 三个工具目录 |
| `{{DESIGN_REFERENCE}}` | 设计方案引用 | design/architecture.md § 1.1 "删除工具目录结构" |
| `{{REQUIREMENT_BACKGROUND}}` | 需求背景 | FR-1 要求删除过时的手动工具... |
| `{{DESIGN_SUMMARY}}` | 设计方案摘要 | 物理删除三个工具目录及其所有文件... |
| `{{EXPECTED_IMPACT}}` | 预期影响 | 工具列表中不再显示 reqboard_decompose... |
| `{{TASK_PHASE}}` | 阶段 | implement / test / doc |
| `{{TASK_SIDE}}` | 端侧 | frontend / backend / fullstack |
| `{{REQUIREMENT_REFS}}` | 需求条款 | FR-1, FR-2 |
| `{{DESIGN_SERVES}}` | 设计落点 | design/architecture#1.1, design/interfaces#2.3 |
| `{{TEST_CASES}}` | 覆盖用例 | TC-1, TC-3 |
| `{{ACCEPTANCE_CRITERIA}}` | 验收标准 | 运行命令验证... |
| `{{IMPLEMENTATION_PLAN}}` | 实施方案 | 按照设计方案 design/architecture.md § 1.1: ... |
| `{{DEPENDS_SUMMARY}}` | 上游产出摘要 | （依赖任务的输出） |
| `{{EXECUTOR_HINT}}` | 执行方式提示 | 优先新窗口或 subagent 执行 |

---

## 📊 改进效果对比

| 维度 | 改进前 | 改进后 |
|------|--------|--------|
| **设计标注** | front-matter 隐藏 + 章节行内 | 纯章节行内（直观） |
| **任务追溯** | 直接跳到 FR（断层） | 引用设计章节（完整） |
| **问题描述** | 永远是空模板 | 自动填充设计方案 |
| **测试追溯** | 无标注 | covers + validates 双追溯 |
| **追溯可见性** | 只能看 FR ← 任务 | 完整四级链路 |

---

## 🚀 下一步：代码实现

模板已更新，现在需要修改代码来填充这些占位符：

1. **reqboard_decompose**：生成任务卡时
   - 解析设计文档的 `serves` 标注
   - 提取服务对应 FR 的设计章节
   - 自动填充 `{{DESIGN_REFERENCE}}`、`{{DESIGN_SUMMARY}}` 等

2. **覆盖度检查**：三级检查
   - Level 1: 需求 ← 设计（所有 FR 都有设计章节）
   - Level 2: 设计 ← 任务（所有设计章节都有任务实现）
   - Level 3: 任务 ← 测试（所有任务都有测试覆盖）

3. **reqboard_status**：显示完整追溯链
   - 设计覆盖度统计
   - 实施覆盖度统计
   - 测试覆盖度统计
   - 未覆盖项的明确提示

---

## ✅ 总结

### 核心改变

1. **统一为方式 A**：章节级行内标注 `serves: FR-x`（删除 front-matter）
2. **补全追溯链**：任务卡添加"设计落点"字段（`{{DESIGN_SERVES}}`）
3. **自动填充**："解决什么问题"不再是空模板（自动引用设计方案）
4. **测试追溯**：测试用例添加 `covers` 和 `validates` 标注

### 设计原则

- **单一数据源**：章节级标注是唯一来源
- **就近原则**：追溯信息写在最相关的地方
- **自动化优先**：能自动填充的就不要手工维护
- **直观可见**：行内标注比隐藏的 front-matter 更直观

---

**模板改进完成！** 🎉

下一步需要修改代码实现（reqboard_decompose / content-gate-wiring / reqboard_status）
来支持这些新的占位符和追溯检查。
