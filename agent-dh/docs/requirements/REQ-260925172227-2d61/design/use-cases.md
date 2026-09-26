# 使用场景

## 1. 需求分析阶段使用场景（serves: FR-1）
### 1.1 创建新需求并初始化 RTM（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**角色**：PM / Agent

**场景描述**：
创建一个新的 feature 需求，系统自动扫描 FR 文件并生成 RTM。

**前置条件**：
- 已准备好 FR 文件（放在 `functional-requirements/` 目录）
- FR 文件包含标准的 7 个章节

**操作步骤**：

1. 调用 `reqboard_create`：
   ```typescript
   const result = await reqboard_create({
     title: 'REQ流水线拆分与验收问题修复',
     category: 'feature',
     summary: '让 REQ 流水线支持功能点独立文件结构 + RTM 自动化'
   });
   ```

2. 系统自动执行：
   - 扫描 `functional-requirements/` 目录
   - 解析每个 FR 文件（提取 id/title/priority/acceptance_criteria）
   - 生成 `rtm.yaml` 文件

3. 检查结果：
   ```typescript
   if (result.rtm?.initialized) {
     console.log(`RTM 已初始化，包含 ${result.rtm.frCount} 个功能点`);
   }
   ```

**预期结果**：
- `rtm.yaml` 文件已创建
- `functional_requirements` 字段包含所有 FR 的元数据
- `coverage_rules` 和 `acceptance_gate` 已定义

---

## 2. 设计阶段使用场景（serves: FR-2）
### 2.1 提交设计文档并校验 FR 文件（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**角色**：Agent / 开发者

**场景描述**：
设计文档编写完成后，提交并校验 FR 文件的完整性。

**前置条件**：
- 需求已创建，RTM 已初始化
- 设计文档已编写（`design/` 目录）

**操作步骤**：

1. 调用 `reqboard_submit(kind='design')`：
   ```typescript
   const result = await reqboard_submit({
     kind: 'design'
   });
   ```

2. 系统自动校验：
   - 检查所有 FR 文件是否存在
   - 检查 FR 文件是否包含完整章节
   - 检查验收标准是否可证伪

3. 检查校验结果：
   ```typescript
   const validation = result.designValidation;
   if (!validation.frFilesExist) {
     console.error('缺失的 FR 文件:', validation.missingFiles);
   }
   if (validation.incompleteFiles.length > 0) {
     console.warn('不完整的 FR 文件:', validation.incompleteFiles);
   }
   ```

**预期结果**：
- `frFilesExist = true`
- `missingFiles = []`
- `incompleteFiles = []`
- 可以推进到拆分阶段

---

## 3. 拆分阶段使用场景（serves: FR-3）
### 3.1 拆分任务并填充 task_coverage（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**角色**：Agent / PM

**场景描述**：
将需求拆分为多个任务，系统自动记录任务覆盖关系并校验覆盖度。

**前置条件**：
- 设计文档已确认
- 拆分计划已准备好

**操作步骤**：

1. 调用 `reqboard_decompose`：
   ```typescript
   const result = await reqboard_decompose({
     tasks: [
       {
         key: 't1',
         title: '实现 RTM 初始化',
         requirementRefs: ['FR-1'],  // 接收 FR-1
         implementation: '...',
         acceptance: '...'
       },
       {
         key: 't2',
         title: '实现 RTM 校验',
         requirementRefs: ['FR-2'],  // 接收 FR-2
         implementation: '...',
         acceptance: '...'
       },
       // ... 更多任务
     ]
   });
   ```

2. 系统自动执行：
   - 为每个任务填充 `task_coverage`
   - 从 FR 文件提取对应的验收标准
   - 计算覆盖度

3. 检查覆盖度：
   ```typescript
   const check = result.coverageCheck;
   console.log(`覆盖率: ${check.coverageRate}%`);
   
   if (check.unreceivedClauses.length > 0) {
     console.warn('未覆盖的 FR:', check.unreceivedClauses);
     // 建议补充任务或调整任务的 requirementRefs
   }
   ```

**预期结果**：
- `task_coverage` 已填充
- `coverageRate = 100%`
- `unreceivedClauses = []`

---

## 4. 实施阶段使用场景（serves: FR-4）
### 4.1 追踪任务状态（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**角色**：Agent

**场景描述**：
任务执行过程中，系统自动追踪任务状态并更新 FR 文件。

**前置条件**：
- 任务已拆分
- 开始执行任务

**操作步骤**：

1. 任务开始时，调用 `reqboard_task_move`：
   ```typescript
   await reqboard_task_move({
     taskId: 't-xxx',
     to: 'in_progress',
     reason: '开始实现 RTM 初始化'
   });
   ```

2. 系统自动更新：
   - `task_coverage` 中的 `status = 'in_progress'`
   - `started_at` 填充当前时间戳

3. 任务完成时：
   ```typescript
   await reqboard_task_move({
     taskId: 't-xxx',
     to: 'done',
     reason: 'RTM 初始化已完成并测试通过'
   });
   
   // 系统自动更新 FR 文件第 7 章
   // FR-1.md 的"接收状态"章节会追加：
   // - **任务 t-xxx**（实现 RTM 初始化）：✅ 已接收（2026-09-25）
   ```

**预期结果**：
- `task_coverage` 中状态正确更新
- FR 文件第 7 章包含接收记录
- 可查询任务进度

---

## 5. 验收阶段使用场景（serves: FR-5, FR-6）
### 5.1 提交验收并填充 acceptance_tracking（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**角色**：Agent

**场景描述**：
任务全部完成后，提交验收材料，系统生成验收单。

**前置条件**：
- 所有任务已完成
- 准备好验收证据

**操作步骤**：

1. 调用 `reqboard_submit(kind='verification')`：
   ```typescript
   const result = await reqboard_submit({
     kind: 'verification',
     summary: '所有功能已实现并测试通过',
     evidence: [
       '单元测试覆盖率 85%',
       '集成测试全部通过',
       'E2E 测试完整流程验证通过'
     ]
   });
   ```

2. 系统自动执行：
   - 从 FR 文件提取所有验收标准（FR-1-A1, FR-1-A2, ...）
   - 填充 `acceptance_tracking`（每项 `status = 'pending'`）

3. 检查验收单：
   ```typescript
   console.log(`生成 ${result.totalAcceptance} 个验收项`);
   ```

**预期结果**：
- `acceptance_tracking` 已填充
- 需求状态变为 `accepting`
- 等待人工审核

---

### 5.2 人工审核并更新 acceptance_tracking（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**角色**：人工审核者

**场景描述**：
审核每个验收项，标记通过或失败。

**前置条件**：
- 验收单已生成
- 审核者已准备好

**操作步骤**：

1. 调用 `reqboard_accept_sheet`（分批审核）：
   ```typescript
   // 第一批：审核 FR-1 的 4 个验收项
   const result1 = await reqboard_accept_sheet({
     batchSize: 4
   });
   
   // 用户在弹框中选择：
   // - FR-1-A1: 通过
   // - FR-1-A2: 通过
   // - FR-1-A3: 通过
   // - FR-1-A4: 通过
   ```

2. 系统自动更新：
   - `acceptance_tracking` 中对应项 `status = 'passed'`
   - 填充 `judgedAt` 和 `judgedBy`

3. 继续审核下一批：
   ```typescript
   // 第二批：审核 FR-2 的 4 个验收项
   const result2 = await reqboard_accept_sheet({
     batchSize: 4
   });
   
   // 如果有未通过项：
   // - FR-2-A2: 改进（需要修改）
   //   用户反馈："测试覆盖不足，需要补充边界用例"
   ```

4. 检查门禁状态：
   ```typescript
   const gateCheck = result2.gateCheck;
   
   if (gateCheck.gateStatus === 'passed') {
     console.log('验收全部通过，自动归档');
   } else {
     console.log(`阻塞原因: ${gateCheck.blockReason}`);
     console.log('失败项:', gateCheck.failedItems);
     // 生成返工卡，Agent 处理后重新审核
   }
   ```

**预期结果**：
- 全部通过：`gateStatus = 'passed'`，需求自动归档
- 部分失败：`gateStatus = 'blocked'`，生成返工卡

---

## 6. 全流程查询场景（serves: FR-7）
### 6.1 查询 RTM 状态（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**角色**：Agent / PM

**场景描述**：
随时查询需求的 RTM 状态，了解覆盖度、任务进度、验收进度。

**前置条件**：
- 需求已创建

**操作步骤**：

1. 查询覆盖度：
   ```typescript
   const result = await reqboard_status({});
   
   const coverage = result.frCoverage;
   coverage.forEach(fr => {
     console.log(`${fr.frId}: ${fr.covered ? '✅ 已覆盖' : '❌ 未覆盖'}`);
     if (fr.covered) {
       console.log(`  接收任务: ${fr.coveredBy.join(', ')}`);
     }
   });
   ```

2. 查询任务进度：
   ```typescript
   const progress = result.taskProgress;
   progress.forEach(fr => {
     console.log(`${fr.frId}: ${fr.progress}% 完成`);
     console.log(`  总任务: ${fr.totalTasks}, 已完成: ${fr.completedTasks}`);
   });
   ```

3. 查询验收进度：
   ```typescript
   const acceptance = result.acceptanceProgress;
   acceptance.forEach(fr => {
     console.log(`${fr.frId}: 通过率 ${fr.passRate}%`);
     console.log(`  通过: ${fr.passed}, 失败: ${fr.failed}, 待审: ${fr.pending}`);
   });
   ```

**预期结果**：
- 实时查看需求的完整追踪状态
- 识别瓶颈（覆盖不足/任务滞后/验收阻塞）

---

## 7. 异常场景处理（serves: FR-1, FR-2, FR-3）
### 7.1 FR 文件缺失（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景描述**：
`rtm.yaml` 引用的 FR 文件不存在。

**处理方式**：

1. 校验时检测：
   ```typescript
   const result = await reqboard_submit({ kind: 'design' });
   
   if (result.designValidation.missingFiles.length > 0) {
     console.error('缺失的 FR 文件:', result.designValidation.missingFiles);
     // 阻止推进到拆分阶段
   }
   ```

2. 用户操作：
   - 补充缺失的 FR 文件
   - 或删除 `rtm.yaml` 中的引用

---

### 7.2 覆盖度不足（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景描述**：
有 FR 未被任务接收。

**处理方式**：

1. 拆分时检测：
   ```typescript
   const result = await reqboard_decompose({ tasks: [...] });
   
   if (result.coverageCheck.unreceivedClauses.length > 0) {
     console.warn('未覆盖的 FR:', result.coverageCheck.unreceivedClauses);
     console.warn(`覆盖率: ${result.coverageCheck.coverageRate}%`);
   }
   ```

2. 用户决策：
   - 补充任务接收未覆盖的 FR
   - 或确认某些 FR 不需要任务（如纯文档 FR）

---

### 7.3 验收失败（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景描述**：
部分验收项未通过。

**处理方式**：

1. 审核时标记失败：
   ```typescript
   // 用户在弹框中选择"改进"并填写反馈
   const result = await reqboard_accept_sheet({ batchSize: 5 });
   
   if (result.failed > 0) {
     console.log('返工卡:', result.reworkTasks);
     // Agent 根据用户反馈修改代码
   }
   ```

2. 修复后重新审核：
   ```typescript
   // 修复完成后，继续调用 reqboard_accept_sheet
   // 只审核上次失败的项（rework_only = true）
   ```

---

**文档版本**: v1.0  
**最后更新**: 2026-09-25  
**作者**: Agent