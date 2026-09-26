# 拆分计划文档

**需求ID**: REQ-260926205654-163a  
**创建时间**: 2026-09-26

---

## 1. 代码层面变更盘点

### 1.1 修改的文件

**文件路径**：`packages/web/dsh-pmboard/src/shared/protocol.ts`

**修改内容**：
- 修改 `formatTimestamp` 函数（第1137-1145行）
- 年份字段：从2位改为4位（`yy` -> `YYYY`）
- 删除秒字段：移除 `ss` 变量的定义和使用
- 更新函数注释

### 1.2 新增的文件

无新增文件。

### 1.3 删除的文件

无删除文件。

---

## 2. 任务拆分与依赖

### 任务列表

本需求改动极小（单函数3行代码），拆分为2个任务：

| 任务ID | 任务名称 | 阶段 | 端侧 | 依赖 | 预计耗时 |
|--------|---------|------|------|------|---------|
| t1 | 修改编号生成函数 | implement | backend | - | 10分钟 |
| t2 | 验证编号格式 | test | fullstack | t1 | 15分钟 |

### 依赖关系

```
t1 (修改代码)
  └─> t2 (验证测试)
```

---

## 3. 任务详细说明

### Task 1: 修改编号生成函数
«serves: FR-1»

**key**: t1  
**title**: 修改 formatTimestamp 函数实现4位年份格式  
**phase**: implement  
**side**: backend  
**depends_on**: []  
**requirement_refs**: ["FR-1"]

**description**:
修改 `packages/web/dsh-pmboard/src/shared/protocol.ts` 中的 `formatTimestamp` 函数，将时间戳格式从 `YYMMDDHHmmss` 改为 `YYYYMMDDHHmm`。

**implementation**:
1. 打开文件 `packages/web/dsh-pmboard/src/shared/protocol.ts`
2. 定位到 `formatTimestamp` 函数（第1137-1145行）
3. 修改第1138行：`const yy = date.getFullYear().toString().slice(-2)` 改为 `const YYYY = date.getFullYear().toString()`
4. 删除第1143行：`const ss = date.getSeconds().toString().padStart(2, '0')`
5. 修改第1144行：`return \`\${yy}\${MM}\${DD}\${HH}\${mm}\${ss}\`` 改为 `return \`\${YYYY}\${MM}\${DD}\${HH}\${mm}\``
6. 更新第1136行注释：`YYMMDDHHmmss（精确到秒）` 改为 `YYYYMMDDHHmm（4位年份，精确到分钟）`
7. 保存文件

**acceptance**:
- 代码修改完成：`formatTimestamp` 函数已按要求修改
- 语法检查通过：`cd packages/web/dsh-pmboard && pnpm run build` 无错误
- 变更验证：使用 `git diff` 确认改动符合预期（3行改动+1行注释）

---

### Task 2: 验证新格式编号
«serves: FR-2»

**key**: t2  
**title**: 验证新需求编号格式为 REQ-YYYYMMDDHHmm-xxxx  
**phase**: test  
**side**: fullstack  
**depends_on**: [t1]

**description**:
重启 DSH 服务，创建测试需求，验证生成的编号格式为 `REQ-YYYYMMDDHHmm-xxxx`（14位时间戳，4位年份，不含秒）。

**implementation**:
1. 重启 DSH 服务应用代码变更：
   ```bash
   cd agent-dh && ./scripts/restart-with-build.sh
   ```
2. 等待服务启动完成（约30秒）
3. 创建测试需求：
   - 方式1：通过 Web UI 调用 `reqboard_capture`
   - 方式2：通过看板手动创建需求
4. 记录生成的需求编号
5. 验证编号格式：
   - 检查编号格式匹配正则：`^REQ-\d{14}-[0-9a-f]{4}$`
   - 检查年份为4位：前4位应为 `2026`
   - 检查不含秒：同一分钟创建多个需求，时间戳部分应相同
6. 验证旧需求兼容性：
   - 访问已存在的旧格式需求（如 `REQ-260926205654-163a`）
   - 确认需求详情正常显示，功能正常

**acceptance**:
- 新编号格式正确：生成的编号格式为 `REQ-YYYYMMDDHHmm-xxxx`
- 年份验证通过：时间戳前4位为完整年份（如 `2026`）
- 不含秒验证通过：同一分钟内创建的多个需求，时间戳部分相同（14位）
- 向后兼容验证通过：旧格式需求（2位年份）仍可正常访问和操作
- 功能回归通过：需求创建、状态推进、任务管理等功能正常


---

### Task 3: 验证旧格式兼容性
«serves: FR-3»

**key**: t3  
**title**: 确认旧格式需求编号仍可正常使用  
**phase**: test  
**side**: fullstack  
**depends_on**: [t1]

**description**:
验证旧格式需求编号（2位年份+秒，如 REQ-260926205654-163a）仍可正常访问和操作，确保向后兼容。

**implementation**:
1. 在看板中搜索旧格式需求：REQ-260926205654-163a
2. 打开需求详情页
3. 检查需求信息显示正常
4. 尝试查看需求的评论、任务等
5. 验证无格式相关错误
6. 确认旧需求可正常推进状态

**acceptance**:
- 旧格式需求可正常访问：看板能找到并打开
- 详情显示正常：标题、描述、状态等信息完整
- 功能正常：评论、任务、状态推进等功能可用
- 无报错：整个过程无格式相关错误

---

## 4. 边界校验

### 4.1 不超范围

✅ 本拆分计划严格按照设计文档执行：
- 只修改 `formatTimestamp` 函数
- 只改动3行代码（年份+秒字段+注释）
- 不涉及其他函数或模块

### 4.2 卡可独立验收

✅ 每个任务都可独立验收：
- **t1**：代码改动完成 + 编译通过
- **t2**：编号格式验证通过 + 兼容性验证通过

### 4.3 与设计无矛盾

✅ 拆分计划完全对齐设计文档：
- 修改点：design/implementation.md 定义的3行改动
- 验收标准：design/test-cases.md 定义的测试用例
- 兼容性：design/architecture.md 定义的向后兼容要求

---

## 5. 风险与缓解

### 5.1 代码风险

**风险**：TypeScript 编译错误

**缓解**：
- t1 的验收标准包含编译检查
- 改动极简单（3行），语法错误概率极低

### 5.2 功能风险

**风险**：编号生成异常或系统功能受影响

**缓解**：
- t2 包含完整的功能验证和回归测试
- 保持向后兼容，旧编号继续有效

### 5.3 回滚方案

如遇问题可快速回滚：
```bash
git checkout HEAD~1 -- packages/web/dh-pmboard/src/shared/protocol.ts
cd agent-dh && ./scripts/restart-with-build.sh
```

---

## 6. 验收门禁

**全部任务完成后的整体验收标准**：

1. ✅ 代码改动符合设计：3行改动（年份+秒字段+注释）
2. ✅ 新编号格式正确：`REQ-YYYYMMDDHHmm-xxxx`
3. ✅ 向后兼容验证通过：旧编号仍可用
4. ✅ 功能回归通过：需求管理功能正常
5. ✅ 无编译错误或运行时异常

---

## 7. 总结

**改动规模**：极小（1个文件，1个函数，3行代码）  
**任务数量**：2个（修改 + 验证）  
**预计总耗时**：25分钟  
**风险等级**：低

本拆分计划已充分考虑设计文档的所有要求，确保改动最小化、验收可证伪、向后兼容。
