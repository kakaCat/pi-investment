# 测试策略

## 1. 测试目标（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
### 1.1 单元测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**目标**：每个模块独立测试，覆盖率 > 80%

**范围**：
- RTMManager 各方法
- FRFileParser 各方法
- 数据验证逻辑

### 1.2 集成测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**目标**：验证工具集成点正确

**范围**：
- reqboard_create → RTMManager.init
- reqboard_decompose → RTMManager.addTaskCoverage
- reqboard_submit → RTMManager.fillAcceptanceTracking

### 1.3 端到端测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**目标**：完整流程跑通

**范围**：
- 需求创建 → 拆分 → 实施 → 验收 → 归档

---

## 2. 单元测试用例（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
### 2.1 RTMManager.init() 测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`rtm-manager.test.ts`

**用例**：

1. **正常流程**
   - 输入：有效的 requirementId + 包含 5 个 FR 文件的目录
   - 预期：rtm.yaml 生成，包含 5 个 functional_requirements
   - 验证：检查文件存在、格式正确、FR 数量

2. **目录为空**
   - 输入：functional-requirements/ 目录为空
   - 预期：返回错误 `NO_FR_FILES`
   - 验证：检查错误码和错误信息

3. **FR 文件格式错误**
   - 输入：FR 文件缺少必要章节
   - 预期：警告但继续（不阻塞初始化）
   - 验证：检查 warnings 字段

4. **重复初始化**
   - 输入：rtm.yaml 已存在
   - 预期：覆盖旧文件（或返回已存在提示）
   - 验证：检查文件内容更新

---

### 2.2 RTMManager.validate() 测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`rtm-manager.test.ts`

**用例**：

1. **所有 FR 文件完整**
   - 输入：5 个完整的 FR 文件
   - 预期：`frFilesExist = true`, `missingFiles = []`
   - 验证：检查返回结果

2. **FR 文件缺失**
   - 输入：rtm.yaml 引用 FR-3，但文件不存在
   - 预期：`missingFiles = ['FR-3']`
   - 验证：检查缺失文件列表

3. **FR 文件缺少章节**
   - 输入：FR-1 文件缺少"5. 实施建议"
   - 预期：`incompleteFiles` 包含 FR-1
   - 验证：检查缺失章节列表

4. **验收标准不可证伪**
   - 输入：FR-2-A3 的 verification 为"系统性能良好"（空话）
   - 预期：`unfalsifiableAcceptance` 包含 FR-2-A3
   - 验证：检查不可证伪列表

---

### 2.3 RTMManager.addTaskCoverage() 测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`rtm-manager.test.ts`

**用例**：

1. **正常覆盖**
   - 输入：3 个任务，每个接收不同的 FR
   - 预期：task_coverage 包含 3 条记录，`coverageRate = 100%`
   - 验证：检查覆盖记录和覆盖率

2. **部分覆盖**
   - 输入：有 5 个 FR，但只有 3 个被任务接收
   - 预期：`unreceivedClauses = ['FR-4', 'FR-5']`, `coverageRate = 60%`
   - 验证：检查未覆盖 FR 列表

3. **引用不存在的 FR**
   - 输入：任务 requirementRefs = ['FR-999']
   - 预期：警告但继续（不阻塞拆分）
   - 验证：检查 warnings 字段

4. **空 requirementRefs**
   - 输入：任务 requirementRefs = []
   - 预期：该任务不计入覆盖（基础设施任务）
   - 验证：检查 covers_frs 为空

---

### 2.4 RTMManager.trackTaskStatus() 测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`rtm-manager.test.ts`

**用例**：

1. **状态变更**
   - 输入：任务从 todo → in_progress
   - 预期：task_coverage 中 status 更新，started_at 填充
   - 验证：检查状态和时间戳

2. **完成任务**
   - 输入：任务从 in_progress → done
   - 预期：completed_at 填充
   - 验证：检查完成时间戳

3. **任务不存在**
   - 输入：taskId 不在 task_coverage 中
   - 预期：返回错误 `TASK_NOT_FOUND`
   - 验证：检查错误码

---

### 2.5 RTMManager.fillAcceptanceTracking() 测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`rtm-manager.test.ts`

**用例**：

1. **正常填充**
   - 输入：有 5 个 FR，每个 4 个验收标准
   - 预期：acceptance_tracking 包含 20 条记录，status 全为 pending
   - 验证：检查记录数和初始状态

2. **重复填充**
   - 输入：acceptance_tracking 已存在
   - 预期：覆盖（或合并）
   - 验证：检查记录数

---

### 2.6 RTMManager.updateAcceptanceTracking() 测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`rtm-manager.test.ts`

**用例**：

1. **全部通过**
   - 输入：20 个验收项全部 passed
   - 预期：`gateStatus = 'passed'`, `passRate = 100%`
   - 验证：检查门禁状态

2. **部分失败**
   - 输入：18 passed, 2 failed
   - 预期：`gateStatus = 'blocked'`, `failedItems.length = 2`
   - 验证：检查失败项列表

3. **分批审核**
   - 输入：第一批 5 个 passed，第二批 3 个 failed
   - 预期：状态正确更新，门禁仍为 blocked
   - 验证：检查累计状态

---

### 2.7 RTMManager.query() 测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`rtm-manager.test.ts`

**用例**：

1. **查询覆盖度**
   - 输入：`options.includeCoverage = true`
   - 预期：返回 frCoverage 列表
   - 验证：检查每个 FR 的 covered 状态

2. **按 FR 查询**
   - 输入：`options.frId = 'FR-1'`
   - 预期：只返回 FR-1 的相关信息
   - 验证：检查结果只包含 FR-1

3. **查询任务进度**
   - 输入：`options.includeProgress = true`
   - 预期：返回 taskProgress 列表（按 FR 分组）
   - 验证：检查每个 FR 的进度百分比

---

### 2.8 FRFileParser 测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`fr-parser.test.ts`

**用例**：

1. **扫描 FR 文件**
   - 输入：包含 5 个 FR-*.md 的目录
   - 预期：返回 5 个文件路径
   - 验证：检查文件数量和路径格式

2. **解析 FR 文件**
   - 输入：有效的 FR-1-xxx.md
   - 预期：返回 FRMetadata（id/title/priority/acceptance_criteria）
   - 验证：检查提取的元数据

3. **提取验收标准**
   - 输入：FR 文件包含 4 个验收标准（A1-A4）
   - 预期：返回 4 个 AcceptanceCriterion
   - 验证：检查验收标准数量和格式

4. **更新第 7 章**
   - 输入：FR 文件 + 任务 ID + 任务标题
   - 预期：第 7 章追加一行记录
   - 验证：读取文件检查新增内容

---

## 3. 集成测试用例（serves: FR-1, FR-3, FR-5, FR-6）
### 3.1 需求创建 → RTM 初始化（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`integration.test.ts`

**流程**：
1. 调用 `reqboard_create({ title: 'Test Req', category: 'feature' })`
2. 检查返回结果包含 `rtm.initialized = true`
3. 检查 `rtm.yaml` 文件存在
4. 检查 `rtm.yaml` 包含 functional_requirements

---

### 3.2 任务拆分 → 填充 task_coverage（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`integration.test.ts`

**流程**：
1. 调用 `reqboard_decompose({ tasks: [...] })`
2. 检查返回结果包含 `taskCoverage`
3. 检查 `rtm.yaml` 的 task_coverage 字段已填充
4. 检查 `coverageCheck.coverageRate = 100%`

---

### 3.3 验收提交 → 填充 acceptance_tracking（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`integration.test.ts`

**流程**：
1. 调用 `reqboard_submit({ kind: 'verification', evidence: [...] })`
2. 检查返回结果包含 `totalAcceptance`
3. 检查 `rtm.yaml` 的 acceptance_tracking 字段已填充
4. 检查所有项 `status = 'pending'`

---

### 3.4 验收审核 → 更新 acceptance_tracking（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`integration.test.ts`

**流程**：
1. 调用 `reqboard_accept_sheet({ ... })`
2. 用户选择"通过"
3. 检查 `rtm.yaml` 对应项 `status = 'passed'`
4. 检查 `gateCheck.gateStatus = 'passed'`（全部通过时）

---

## 4. 端到端测试用例（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
### 4.1 完整流程（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**测试文件**：`e2e.test.ts`

**流程**：

1. **需求创建**
   - 调用 `reqboard_create`
   - 验证 rtm.yaml 生成

2. **设计提交**
   - 创建 5 个 FR 文件
   - 调用 `reqboard_submit(kind='design')`
   - 验证校验通过

3. **任务拆分**
   - 调用 `reqboard_decompose`（5 个任务覆盖 5 个 FR）
   - 验证 task_coverage 填充
   - 验证 coverageRate = 100%

4. **任务执行**
   - 调用 `reqboard_task_move`（5 个任务依次完成）
   - 验证任务状态更新
   - 验证 FR 文件第 7 章更新

5. **验收提交**
   - 调用 `reqboard_submit(kind='verification')`
   - 验证 acceptance_tracking 填充（20 项）

6. **验收审核**
   - 调用 `reqboard_accept_sheet`（分 4 批，每批 5 项）
   - 全部选"通过"
   - 验证 gateStatus = 'passed'
   - 验证需求自动归档

7. **查询验证**
   - 调用 `reqboard_status`
   - 验证返回 frCoverage（100%）
   - 验证返回 taskProgress（100%）
   - 验证返回 acceptanceProgress（100%）

---

## 5. 性能测试（serves: FR-1, FR-3, FR-7）
### 5.1 FR 文件扫描性能（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**目标**：扫描 10 个 FR 文件 < 500ms

**测试**：
- 准备 10 个 FR 文件（每个 ~5KB）
- 调用 `RTMManager.init()`
- 测量扫描时间

### 5.2 查询性能（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**目标**：查询 RTM 状态 < 100ms

**测试**：
- 准备包含 10 个 FR、50 个任务、40 个验收项的 rtm.yaml
- 调用 `RTMManager.query()`
- 测量查询时间

---

## 6. 错误场景测试（serves: FR-1, FR-2, FR-3）
### 6.1 FR 文件缺失（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景**：rtm.yaml 引用的 FR 文件不存在

**预期**：
- `validate()` 返回 `missingFiles`
- 设计阶段无法推进到拆分

### 6.2 覆盖度不足（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景**：有 FR 未被任务接收

**预期**：
- `addTaskCoverage()` 返回 `unreceivedClauses`
- 拆分不阻塞（警告级别）

### 6.3 验收失败（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景**：部分验收项 status = 'failed'

**预期**：
- `updateAcceptanceTracking()` 返回 `gateStatus = 'blocked'`
- 不触发自动归档
- 生成返工卡

---

## 7. 测试执行计划（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
### 7.1 测试顺序（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
1. **单元测试**（开发阶段同步）
   - RTMManager 各方法
   - FRFileParser 各方法

2. **集成测试**（集成阶段）
   - 工具集成点

3. **端到端测试**（完成后）
   - 完整流程

4. **性能测试**（优化阶段）
   - 扫描性能
   - 查询性能

### 7.2 测试工具（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
- **单元测试框架**：Jest / Vitest
- **断言库**：expect
- **Mock 工具**：Jest mock / Sinon
- **性能测试**：console.time() / performance.now()

### 7.3 覆盖率目标（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
- **单元测试**：> 80%
- **集成测试**：核心流程 100%
- **端到端测试**：主流程 100%

---

## 8. 测试数据准备（serves: FR-1, FR-2, FR-3）
### 8.1 测试用 FR 文件（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**位置**：`tests/fixtures/functional-requirements/`

**文件**：
- FR-1-test-feature.md
- FR-2-test-feature.md
- FR-3-test-feature.md
- FR-4-test-feature.md
- FR-5-test-feature.md

**内容**：包含完整的 7 个章节 + 4 个验收标准

### 8.2 测试用 rtm.yaml（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**位置**：`tests/fixtures/rtm.yaml`

**内容**：包含 5 个 FR、3 个任务、20 个验收项的完整示例

---

**文档版本**: v1.0  
**最后更新**: 2026-09-25  
**作者**: Agent