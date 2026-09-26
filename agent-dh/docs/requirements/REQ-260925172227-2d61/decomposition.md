# REQ-260925172227-2d61: REQ流水线拆分与验收问题修复 - 拆分计划

## 目标
修复 REQ 流水线的 RTM（需求追踪矩阵）支持，实现从需求分析到验收的完整追踪链条。核心改动：
1. **decompose 阶段**：填充 task_coverage（任务接收 FR），校验覆盖度 100%
2. **submit 阶段**：从 FR 文件提取验收标准，填充 acceptance_tracking
3. **accept_sheet 阶段**：更新 acceptance_tracking 状态，检查验收门禁，触发自动归档

## 做法
按照 architecture.md 的三阶段设计，逐步修改：
1. **数据模型卡**：扩展 rtm.yaml 结构（task_coverage / acceptance_tracking）
2. **接口卡**：定义工具的输入输出契约（decompose / submit / accept_sheet）
3. **实现卡**：实现 FR 文件扫描、覆盖校验、验收追踪、门禁检查
4. **测试卡**：E2E 测试验证完整流程

## 改动盘点

### 新增文件
- `agent-dh/packages/tools/reqboard/src/rtm/rtm-manager.ts` - RTM 管理器（扫描 FR 文件、填充/更新 task_coverage / acceptance_tracking）
- `agent-dh/packages/tools/reqboard/src/rtm/fr-parser.ts` - FR 文件解析器（提取验收标准）
- `agent-dh/packages/tools/reqboard/src/rtm/coverage-checker.ts` - 覆盖度检查器（校验所有 FR 被接收）
- `agent-dh/packages/tools/reqboard/src/rtm/acceptance-gate.ts` - 验收门禁（检查通过条件、触发归档）
- `agent-dh/packages/tools/reqboard/tests/rtm/rtm-manager.test.ts` - RTM 管理器单元测试
- `agent-dh/packages/tools/reqboard/tests/e2e/rtm-full-flow.test.ts` - RTM 完整流程 E2E 测试

### 修改文件
- `agent-dh/packages/tools/reqboard/src/tools/reqboard-decompose.ts` - decompose 工具：新增 task_coverage 填充逻辑
- `agent-dh/packages/tools/reqboard/src/tools/reqboard-submit.ts` - submit 工具：新增 acceptance_tracking 填充逻辑（kind=verification）
- `agent-dh/packages/tools/reqboard/src/tools/reqboard-accept-sheet.ts` - accept_sheet 工具：新增 acceptance_tracking 更新逻辑
- `agent-dh/packages/tools/reqboard/src/tools/reqboard-status.ts` - status 工具：新增 FR 覆盖度和验收进度显示
- `agent-dh/packages/tools/reqboard/src/types/rtm.ts` - RTM 类型定义（TaskCoverage / AcceptanceTracking）

### 数据模型扩展
- `rtm.yaml` 新增字段：
  - `task_coverage[]` - 任务覆盖追踪（task_id / covers_frs / covers_acceptance）
  - `acceptance_tracking[]` - 验收追踪（acceptance_id / status / evidence / judged_at）
  - `coverage_rules` - 覆盖规则（all_frs_covered / all_acceptance_covered）
  - `acceptance_gate` - 验收门禁（pass_condition / auto_archive）

## 任务表

### t1: 数据模型 - RTM 类型定义
**phase**: doc  
**side**: backend  
**depends_on**: []

**implementation**:
1. 创建 `packages/tools/reqboard/src/types/rtm.ts`
2. 定义接口：
   - `TaskCoverage`: task_id, task_key, covers_frs, covers_acceptance, assigned_at
   - `AcceptanceTracking`: acceptance_id, fr_id, status, evidence, judged_at, judged_by, user_feedback
   - `CoverageRule`: rule, check
   - `AcceptanceGate`: pass_condition, fail_action, auto_archive
3. 扩展 `RequirementData` 接口：新增 task_coverage / acceptance_tracking / coverage_rules / acceptance_gate 字段
4. 导出所有类型到 `packages/tools/reqboard/src/types/index.ts`

**acceptance**:
执行：`cat packages/tools/reqboard/src/types/rtm.ts`  
期望：文件存在，包含 TaskCoverage / AcceptanceTracking / CoverageRule / AcceptanceGate 接口定义，每个字段有 JSDoc 注释

---

### t2: 工具实现 - FR 文件解析器
**phase**: implement  
**side**: backend  
**depends_on**: [t1]

**implementation**:
1. 创建 `packages/tools/reqboard/src/rtm/fr-parser.ts`
2. 实现 `parseFRFile(filePath: string): FRMetadata`：
   - 读取 FR 文件，提取 front-matter（priority）
   - 提取第 3 章"验收标准"的所有 A1-A4 验收项（正则匹配 `- **FR-X-A[1-4]**:`）
   - 返回：{ id, title, priority, acceptance_criteria: [{ id, description, verification }] }
3. 实现 `scanFRDirectory(reqDir: string): FRMetadata[]`：
   - 扫描 `functional-requirements/*.md` 所有文件
   - 调用 parseFRFile 解析每个文件
   - 返回 FR 元数据列表

**acceptance**:
执行：`npx vitest run packages/tools/reqboard/tests/rtm/fr-parser.test.ts`  
期望：
1. parseFRFile 能正确提取 FR-1 的 title/priority/acceptance（4 项 A1-A4）
2. scanFRDirectory 能扫描到 3 个 FR 文件（FR-1/FR-2/FR-3）
3. 测试用例覆盖：正常文件 / 缺 front-matter / 缺验收标准章节

---

### t3: 工具实现 - RTM 管理器（核心）
**phase**: implement  
**side**: backend  
**depends_on**: [t1, t2]

**implementation**:
1. 创建 `packages/tools/reqboard/src/rtm/rtm-manager.ts`
2. 实现 `RTMManager` 类：
   - `fillTaskCoverage(reqData, tasks)`: 填充 task_coverage
     - 遍历 tasks，从 requirement_refs 提取 covers_frs
     - 扫描 FR 文件，提取每个 FR 的验收标准
     - 填充 covers_acceptance（所有 FR-X-A* 验收项）
     - 返回填充后的 task_coverage 数组
   - `fillAcceptanceTracking(reqData, frMetadata)`: 填充 acceptance_tracking
     - 遍历所有 FR 的验收标准，生成 acceptance_tracking 记录
     - status 初始为 pending，evidence/judged_at/judged_by 为 null
   - `updateAcceptanceTracking(reqData, judgements)`: 更新 acceptance_tracking
     - 根据 judgements (acceptance_id → passed/failed/feedback) 更新状态
     - 记录 judged_at（时间戳）和 judged_by（用户 ID）
3. 单元测试覆盖所有方法

**acceptance**:
执行：`npx vitest run packages/tools/reqboard/tests/rtm/rtm-manager.test.ts`  
期望：
1. fillTaskCoverage: 输入 2 个任务（t1 covers FR-1, t2 covers FR-2/FR-3），输出 task_coverage 包含 2 项，covers_acceptance 正确填充
2. fillAcceptanceTracking: 输入 3 个 FR（共 12 个验收项），输出 12 条 pending 记录
3. updateAcceptanceTracking: 输入 judgements（10 passed, 2 failed），更新后状态正确

---

### t4: 工具实现 - 覆盖度检查器
**phase**: implement  
**side**: backend  
**depends_on**: [t1, t3]

**implementation**:
1. 创建 `packages/tools/reqboard/src/rtm/coverage-checker.ts`
2. 实现 `CoverageChecker` 类：
   - `checkCoverage(reqData, frMetadata)`: 检查覆盖度
     - 提取所有 FR id 列表
     - 提取 task_coverage 中所有 covers_frs
     - 计算未覆盖的 FR（unreceived_clauses）
     - 返回：{ total_frs, covered_frs, unreceived_clauses, coverage_rate }
   - `validateCoverage(reqData, frMetadata)`: 验证覆盖度 100%
     - 调用 checkCoverage
     - 如果 coverage_rate < 100%，抛出错误（包含 unreceived_clauses 列表）

**acceptance**:
执行：`npx vitest run packages/tools/reqboard/tests/rtm/coverage-checker.test.ts`  
期望：
1. checkCoverage: 输入 3 个 FR（task_coverage 只覆盖 2 个），返回 unreceived_clauses = [FR-3], coverage_rate = 67%
2. validateCoverage: 覆盖度 < 100% 时抛出错误，错误信息包含 "未覆盖的 FR: FR-3"

---

### t5: 工具实现 - 验收门禁
**phase**: implement  
**side**: backend  
**depends_on**: [t1, t3]

**implementation**:
1. 创建 `packages/tools/reqboard/src/rtm/acceptance-gate.ts`
2. 实现 `AcceptanceGate` 类：
   - `checkGate(reqData)`: 检查验收门禁
     - 统计 acceptance_tracking 的 status（passed/failed/pending 各多少）
     - 计算 pass_rate = passed / total
     - 判断 gate_status（passed: 100%, blocked: <100%）
     - 返回：{ total, passed, failed, pending, pass_rate, gate_status, block_reason, failed_items }
   - `shouldAutoArchive(reqData)`: 判断是否自动归档
     - 调用 checkGate，检查 gate_status === 'passed'
     - 返回 boolean

**acceptance**:
执行：`npx vitest run packages/tools/reqboard/tests/rtm/acceptance-gate.test.ts`  
期望：
1. checkGate: 输入 12 个验收项（10 passed, 2 failed），返回 pass_rate=83%, gate_status=blocked, failed_items 包含 2 项
2. checkGate: 输入 12 个验收项（12 passed），返回 pass_rate=100%, gate_status=passed
3. shouldAutoArchive: gate_status=passed 时返回 true

---

### t6: 工具集成 - reqboard_decompose 填充 task_coverage
**phase**: implement  
**side**: backend  
**depends_on**: [t1, t2, t3, t4]

**implementation**:
1. 修改 `packages/tools/reqboard/src/tools/reqboard-decompose.ts`
2. 在任务落库后，调用 RTMManager.fillTaskCoverage：
   - 传入 reqData 和 tasks 参数
   - 获取 task_coverage 数组
   - 调用 CoverageChecker.validateCoverage（确保 100% 覆盖）
   - 写入 rtm.yaml 的 task_coverage 字段
3. 返回值新增 `coverage_check` 字段（total_frs / covered_frs / unreceived_clauses / coverage_rate）
4. 如果覆盖度 < 100%，返回 warning 但不阻断（用户可以手动补全）

**acceptance**:
执行：`npx vitest run packages/tools/reqboard/tests/tools/reqboard-decompose.test.ts`  
期望：
1. 测试用例"完全覆盖"：2 个任务覆盖 3 个 FR，返回 coverage_rate=100%，task_coverage 正确写入 rtm.yaml
2. 测试用例"部分覆盖"：2 个任务只覆盖 2 个 FR，返回 coverage_rate=67%, unreceived_clauses=[FR-3], warning 存在

---

### t7: 工具集成 - reqboard_submit 填充 acceptance_tracking
**phase**: implement  
**side**: backend  
**depends_on**: [t1, t2, t3]

**implementation**:
1. 修改 `packages/tools/reqboard/src/tools/reqboard-submit.ts`
2. 在 `kind=verification` 分支，调用 RTMManager.fillAcceptanceTracking：
   - 扫描 FR 文件，获取 frMetadata
   - 调用 fillAcceptanceTracking，生成 acceptance_tracking 记录（status=pending）
   - 写入 rtm.yaml 的 acceptance_tracking 字段
3. 返回值新增 `acceptance_tracking_count` 字段（生成了多少条验收记录）

**acceptance**:
执行：`npx vitest run packages/tools/reqboard/tests/tools/reqboard-submit.test.ts`  
期望：
1. 测试用例"提交验收"：3 个 FR（12 个验收项），返回 acceptance_tracking_count=12，rtm.yaml 包含 12 条 pending 记录
2. 测试用例"续验"：上版 2 项 failed，本次只生成这 2 项（不重复生成 passed 项）

---

### t8: 工具集成 - reqboard_accept_sheet 更新 acceptance_tracking
**phase**: implement  
**side**: backend  
**depends_on**: [t1, t3, t5]

**implementation**:
1. 修改 `packages/tools/reqboard/src/tools/reqboard-accept-sheet.ts`
2. 在用户裁决后，调用 RTMManager.updateAcceptanceTracking：
   - 传入 judgements（acceptance_id → status / feedback）
   - 更新 rtm.yaml 的 acceptance_tracking 状态
3. 调用 AcceptanceGate.checkGate，检查门禁
4. 如果 shouldAutoArchive() 返回 true，自动调用 reqboard_move(to='archived')
5. 返回值新增 `gate_check` 字段（total / passed / failed / pass_rate / gate_status）

**acceptance**:
执行：`npx vitest run packages/tools/reqboard/tests/tools/reqboard-accept-sheet.test.ts`  
期望：
1. 测试用例"部分通过"：12 项验收（10 passed, 2 failed），返回 gate_status=blocked, archived=false
2. 测试用例"全部通过"：12 项验收（12 passed），返回 gate_status=passed, archived=true，需求状态变为 archived

---

### t9: 工具集成 - reqboard_status 显示 FR 覆盖度和验收进度
**phase**: implement  
**side**: backend  
**depends_on**: [t1, t3, t4, t5]

**implementation**:
1. 修改 `packages/tools/reqboard/src/tools/reqboard-status.ts`
2. 新增 `fr_coverage` 字段：
   - 调用 CoverageChecker.checkCoverage
   - 返回：{ total_frs, covered_frs, unreceived_clauses, coverage_rate }
3. 新增 `fr_acceptance_progress` 字段：
   - 调用 AcceptanceGate.checkGate
   - 返回：{ total, passed, failed, pending, pass_rate, gate_status }

**acceptance**:
执行：`npx vitest run packages/tools/reqboard/tests/tools/reqboard-status.test.ts`  
期望：
1. 返回包含 fr_coverage（total_frs=3, covered_frs=2, unreceived_clauses=[FR-3], coverage_rate=67%）
2. 返回包含 fr_acceptance_progress（total=12, passed=10, failed=2, pass_rate=83%, gate_status=blocked）

---

### t10: E2E 测试 - RTM 完整流程
**phase**: test  
**side**: fullstack  
**depends_on**: [t6, t7, t8, t9]

**implementation**:
1. 创建 `packages/tools/reqboard/tests/e2e/rtm-full-flow.test.ts`
2. 模拟完整流程：
   - 创建需求（3 个 FR 文件，12 个验收项）
   - 调用 reqboard_decompose（2 个任务，覆盖 3 个 FR）
   - 检查 task_coverage 填充正确，coverage_rate=100%
   - 调用 reqboard_submit(kind=verification)
   - 检查 acceptance_tracking 填充正确（12 条 pending）
   - 调用 reqboard_accept_sheet（10 passed, 2 failed）
   - 检查 acceptance_tracking 更新正确，gate_status=blocked
   - 处理返工卡，重新提交验收
   - 调用 reqboard_accept_sheet（12 passed）
   - 检查 gate_status=passed，需求自动归档

**acceptance**:
执行：`npx vitest run packages/tools/reqboard/tests/e2e/rtm-full-flow.test.ts`  
期望：
1. 完整流程测试通过（所有断言成功）
2. 覆盖 3 个关键路径：拆分填充 → 提交填充 → 验收更新 → 门禁通过 → 自动归档
3. 测试用例运行时间 < 5s

---

### t11: 文档 - RTM 使用指南
**phase**: doc  
**side**: doc  
**depends_on**: [t10]

**implementation**:
1. 创建 `docs/guides/rtm-user-guide.md`
2. 包含章节：
   - RTM 是什么（需求追踪矩阵）
   - FR 文件格式规范（7 章结构，验收标准必须可证伪）
   - 如何使用（decompose → submit → accept_sheet 的完整流程）
   - 如何读取 RTM 数据（reqboard_status 查看覆盖度和验收进度）
   - 故障排查（覆盖度 < 100% / 验收门禁未通过）

**acceptance**:
执行：`cat docs/guides/rtm-user-guide.md`  
期望：文件存在，包含 5 个章节，每个章节有示例代码和截图说明

---

## 依赖关系图

```
t1 (类型定义)
  ├─→ t2 (FR 解析器)
  │     └─→ t3 (RTM 管理器)
  │           ├─→ t4 (覆盖度检查器)
  │           ├─→ t5 (验收门禁)
  │           ├─→ t6 (decompose 集成) ──┐
  │           ├─→ t7 (submit 集成) ─────┤
  │           └─→ t8 (accept_sheet 集成)│
  ├─→ t4 ──→ t9 (status 集成) ──────────┤
  ├─→ t5 ─────────────────────────────┘
  └─→ t10 (E2E 测试)
        └─→ t11 (文档)
```

## 验收标准汇总

| 任务 | 验收方式 | 可证伪性 |
|-----|---------|---------|
| t1 | 检查文件存在，接口定义完整 | ✅ 文件路径可验证 |
| t2 | 单元测试通过（3 个用例） | ✅ 测试命令可执行 |
| t3 | 单元测试通过（3 个方法） | ✅ 测试命令可执行 |
| t4 | 单元测试通过（2 个用例） | ✅ 测试命令可执行 |
| t5 | 单元测试通过（3 个用例） | ✅ 测试命令可执行 |
| t6 | 集成测试通过（2 个用例） | ✅ 测试命令可执行 |
| t7 | 集成测试通过（2 个用例） | ✅ 测试命令可执行 |
| t8 | 集成测试通过（2 个用例） | ✅ 测试命令可执行 |
| t9 | 集成测试通过（2 个字段） | ✅ 测试命令可执行 |
| t10 | E2E 测试通过（完整流程） | ✅ 测试命令可执行 |
| t11 | 文档存在，包含 5 章节 | ✅ 文件路径可验证 |

**总计 11 个任务，所有验收标准可证伪。**

---

**文档版本**: v1.0  
**创建时间**: 2026-09-25  
**作者**: Agent (session-18ecbbd5)
