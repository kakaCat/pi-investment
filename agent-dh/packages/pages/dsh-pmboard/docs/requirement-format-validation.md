# 需求文档格式校验测试

## 测试场景

### ✅ 场景 1：合格的需求文档

```markdown
## 功能需求

### FR-1: 用户登录
用户可以使用用户名和密码登录系统。

**验收标准**：
- AC-1.1: 输入正确用户名和密码可成功登录
- AC-1.2: 密码错误提示"用户名或密码错误"

### FR-2: 数据导出
用户可以导出数据为 CSV 格式。

**验收标准**：
- AC-2.1: 点击"导出"按钮生成 CSV 文件
- AC-2.2: CSV 文件包含所有必要字段

## 非功能需求

### NFR-1: 性能要求
系统响应时间应在 2 秒内。
```

✅ **通过原因**：
- 有根编号（FR-1, FR-2, NFR-1）
- 编号连续（没有跳号）
- 编号唯一（没有重复）

---

### ❌ 场景 2：缺少编号

```markdown
## 功能需求

### 用户登录
用户可以使用用户名和密码登录系统。

### 数据导出
用户可以导出数据为 CSV 格式。
```

❌ **拒绝原因**：`requirement_missing_clauses`
> 需求文档缺少功能编号。请为每个功能点添加编号（格式：### FR-1: 功能名称）

---

### ❌ 场景 3：编号跳号

```markdown
## 功能需求

### FR-1: 用户登录
...

### FR-3: 数据导出
（缺少 FR-2）
...

### FR-5: 权限管理
（缺少 FR-4）
...
```

❌ **拒绝原因**：`requirement_clause_sequence_gap`
> 需求编号不连续（跳号）——FR-2、FR-4。请补上缺失的编号，或调整现有编号使其连续

---

### ❌ 场景 4：编号重复

```markdown
## 功能需求

### FR-1: 用户登录
...

### FR-2: 数据导出
...

### FR-1: 权限管理
（重复了 FR-1）
...
```

❌ **拒绝原因**：`requirement_clause_duplicates`
> 需求编号重复——FR-1（出现2次）。每个编号只能出现一次，请检查并合并重复的条款

---

## 调用时机

```
Agent 写需求文档
    ↓
reqboard_submit(kind='requirement')
    ↓
🚨 checkRequirementDocFormatGate()  ← 新增！
    ↓
❌ 不合格 → reject (Agent 修改重试)
✅ 合格 → 登记产物
    ↓
reqboard_ask_confirm
    ↓
👤 人只需判断内容是否正确
    （格式已由系统保证）
```

## 新增的错误码

| 错误码 | 含义 | 触发条件 |
|--------|------|----------|
| `requirement_missing_clauses` | 缺少功能编号 | 文档中没有 FR-/BUG-/... 等根编号 |
| `requirement_clause_sequence_gap` | 编号不连续 | FR-1 → FR-3（缺 FR-2） |
| `requirement_clause_duplicates` | 编号重复 | 同一编号出现多次 |

## 文件修改清单

1. **content-gates.ts** (+56 行)
   - `checkClauseSequence()` - 检查编号连续性
   - `checkClauseDuplicates()` - 检查编号唯一性

2. **content-gate-wiring.ts** (+75 行)
   - `checkRequirementDocFormatGate()` - 需求文档格式校验门禁

3. **artifact-gates.ts** (+3 行)
   - 添加 3 个新错误码到 `GateFailure` 类型

4. **SubmitArtifact.ts** (+7 行)
   - 在 `submitRequirementArtifact` 中调用格式校验
