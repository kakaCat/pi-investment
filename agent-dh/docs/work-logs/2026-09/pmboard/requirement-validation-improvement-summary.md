# 需求文档编号规范强制校验 - 改进完成

## 改进目标

**问题**：现状中，需求文档的编号规范在 reqboard_submit 时不校验，直到后续阶段（submit plan / decompose）才发现格式问题，导致：
- 用户确认了不合格的文档（浪费人的时间）
- Agent 基于不合格需求写了设计（浪费 Agent 的时间）
- 需要回头修改并重新确认

**解决方案**：在 reqboard_submit(kind='requirement') 时立即校验编号规范，系统负责格式，人负责内容。

---

## 已实现的校验

### 1. 必须有根编号

错误码：requirement_missing_clauses

### 2. 编号不能跳号

错误码：requirement_clause_sequence_gap

### 3. 编号不能重复

错误码：requirement_clause_duplicates

---

## 代码修改

### 文件 1: content-gates.ts (+56 行)

添加两个纯函数：
- checkClauseSequence() - 检查编号连续性
- checkClauseDuplicates() - 检查编号唯一性

### 文件 2: content-gate-wiring.ts (+75 行)

添加校验门禁函数：checkRequirementDocFormatGate()

### 文件 3: artifact-gates.ts (+3 行)

在 GateFailure 类型添加 3 个新错误码

### 文件 4: SubmitArtifact.ts (+7 行)

在 submitRequirementArtifact 中调用格式校验

---

## 新的执行流程

1. Agent 写需求文档
2. reqboard_submit(kind='requirement')
3. 文件存在检查
4. **NEW: 格式校验**
   - 必须有编号
   - 编号不能跳号
   - 编号不能重复
5. 不合格 -> reject (Agent 修改重试)
6. 合格 -> 登记产物
7. reqboard_ask_confirm
8. 人确认（只需判断内容，格式已由系统保证）

---

## 设计原则

### 1. 职责分离
- 系统负责：格式规范
- 人负责：内容质量

### 2. 早发现早修复
- 在提交时立即校验，不等到后续阶段

### 3. 一致性
- 所有阶段的 submit 都立即校验格式

---

## 验证结果

TypeScript 编译：通过（0 errors）

---

## 代码统计

| 文件 | 新增行数 |
|------|---------|
| content-gates.ts | +56 |
| content-gate-wiring.ts | +75 |
| artifact-gates.ts | +3 |
| SubmitArtifact.ts | +7 |
| **总计** | **+141** |

---

改进完成时间：2026-09-19T05:34:59.957Z
TypeScript 编译：通过
向后兼容：存量需求豁免
