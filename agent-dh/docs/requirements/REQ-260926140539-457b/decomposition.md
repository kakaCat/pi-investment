---
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
---

# REQ-260926140539-457b 拆分计划

> 需求：RTM YAML 追溯基础设施 - Dive 模式自动化的数据底座  
> 类型：feature | 拆分日期：2026-09-26

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

> 本表为「任务 ↔ 需求根编号」绑定的规范载体（TaskRecord 不存该绑定）。
> 常规由 decompose 自动生成；因 reqboard_decompose 已在 REQ-260925234037-1503 下线，
> 本表由窗口在拆分阶段依已批准的 20 张任务卡对照补齐，任务编号为台账真实 id。
> 每行一条绑定：根编号列只放一个编号（解析器 collectIds 只取首个）。

| 根编号 | 任务编号 | 任务标题 |
| --- | --- | --- |
| FR-1 | t-8c8edc | 实现 RTM TypeScript 类型定义 |
| FR-1 | t-e57e00 | 实现 RTM 文件读写与版本控制 |
| FR-1 | t-93f4da | 实现全局生命周期 RTM 生成 |
| FR-1 | t-46064e | 实现需求分析节点 RTM 生成 |
| FR-1 | t-ca2228 | 实现设计节点 RTM 生成 |
| FR-1 | t-a30145 | 实现拆分节点 RTM 生成 |
| FR-1 | t-c4fa59 | 实现实施节点 RTM 生成（汇总 + 任务详情目录） |
| FR-1 | t-20151a | 实现验收节点 RTM 生成 |
| FR-1 | t-37e870 | 完整流程端到端测试 |
| FR-2 | t-93f4da | 实现全局生命周期 RTM 生成 |
| FR-2 | t-46064e | 实现需求分析节点 RTM 生成 |
| FR-2 | t-ca2228 | 实现设计节点 RTM 生成 |
| FR-2 | t-a30145 | 实现拆分节点 RTM 生成 |
| FR-2 | t-c4fa59 | 实现实施节点 RTM 生成（汇总 + 任务详情目录） |
| FR-2 | t-20151a | 实现验收节点 RTM 生成 |
| FR-2 | t-152423 | 在 reqboard_create 触发 rtm-lifecycle.yml 生成 |
| FR-2 | t-6019b3 | 在 reqboard_submit 各类型触发对应 RTM 生成 |
| FR-2 | t-54248f | 确认产物后更新 RTM 的 confirmed 状态 |
| FR-2 | t-6eeacf | 任务状态变更时更新 rtm-implementing.yml |
| FR-2 | t-eb31cc | 子任务汇报时更新任务详情文件的 workflow |
| FR-2 | t-37e870 | 完整流程端到端测试 |
| FR-3 | t-25c956 | 实现 FR/serves/implements/covers 标注解析 |
| FR-3 | t-46064e | 实现需求分析节点 RTM 生成 |
| FR-3 | t-37e870 | 完整流程端到端测试 |
| FR-4 | t-25c956 | 实现 FR/serves/implements/covers 标注解析 |
| FR-4 | t-3ca532 | 实现四级追溯映射构建 |
| FR-4 | t-ca2228 | 实现设计节点 RTM 生成 |
| FR-4 | t-a30145 | 实现拆分节点 RTM 生成 |
| FR-4 | t-20151a | 实现验收节点 RTM 生成 |
| FR-4 | t-37e870 | 完整流程端到端测试 |
| FR-5 | t-0bf4ae | 实现三层覆盖度自动计算 |
| FR-5 | t-ca2228 | 实现设计节点 RTM 生成 |
| FR-5 | t-a30145 | 实现拆分节点 RTM 生成 |
| FR-5 | t-20151a | 实现验收节点 RTM 生成 |
| FR-5 | t-37e870 | 完整流程端到端测试 |
| FR-6 | t-e57e00 | 实现 RTM 文件读写与版本控制 |
| FR-6 | t-54248f | 确认产物后更新 RTM 的 confirmed 状态 |
| FR-6 | t-6eeacf | 任务状态变更时更新 rtm-implementing.yml |
| FR-6 | t-eb31cc | 子任务汇报时更新任务详情文件的 workflow |
| FR-7 | t-cf2b22 | 实现 StageOverview 的 RTM 读取接口 |
| FR-7 | t-66d23c | 增强 assembleStageOverview 合并 RTM 追溯数据 |
| FR-7 | t-37e870 | 完整流程端到端测试 |
| FR-8 | t-c010b8 | 编写 RTM 使用文档和 Dive 模式集成示例 |
| FR-9 | t-e57e00 | 实现 RTM 文件读写与版本控制 |
| FR-10 | t-c4fa59 | 实现实施节点 RTM 生成（汇总 + 任务详情目录） |
| FR-10 | t-37e870 | 完整流程端到端测试 |
| FR-11 | t-c4fa59 | 实现实施节点 RTM 生成（汇总 + 任务详情目录） |
| FR-11 | t-eb31cc | 子任务汇报时更新任务详情文件的 workflow |

## 改动盘点

### 新增文件

#### 核心实现（agent-dh/packages/tools/reqboard/src/）

1. **rtm/** - RTM 生成与管理模块
   - `rtm/types.ts` - RTM 数据类型定义
   - `rtm/generator.ts` - RTM 生成逻辑（7 个触发点）
   - `rtm/lifecycle-generator.ts` - 生成 rtm-lifecycle.yml
   - `rtm/brainstorming-generator.ts` - 生成 rtm-brainstorming.yml
   - `rtm/design-generator.ts` - 生成 rtm-design.yml
   - `rtm/decomposing-generator.ts` - 生成 rtm-decomposing.yml
   - `rtm/implementing-generator.ts` - 生成 rtm-implementing.yml（汇总文件 + 任务详情目录）
   - `rtm/accepting-generator.ts` - 生成 rtm-accepting.yml
   - `rtm/parser.ts` - 文档解析器（提取 FR/serves/implements/covers）
   - `rtm/coverage-calculator.ts` - 覆盖度统计
   - `rtm/traceability-builder.ts` - 追溯关系构建
   - `rtm/file-io.ts` - RTM 文件读写（版本控制、原子写入）

2. **stage-overview/** - StageOverview 集成
   - `stage-overview/rtm-reader.ts` - RTM 读取接口
   - `stage-overview/assembler.ts` - 增强 assembleStageOverview

#### 测试文件（agent-dh/packages/tools/reqboard/tests/）

3. **rtm.test.ts** - RTM 生成与更新测试
4. **rtm-parser.test.ts** - 文档解析测试
5. **rtm-coverage.test.ts** - 覆盖度统计测试
6. **rtm-e2e.test.ts** - 端到端测试（完整流程）

### 修改文件

#### reqboard 工具集成

1. **agent-dh/packages/tools/reqboard/src/index.ts**
   - 导入 RTM 生成器模块
   - 在现有工具的执行逻辑中插入 RTM 触发点

2. **agent-dh/packages/tools/reqboard/src/tools/reqboard-create.ts**
   - `execute()` 结尾调用 `generateLifecycleRTM()`

3. **agent-dh/packages/tools/reqboard/src/tools/reqboard-submit.ts**
   - `kind=requirement` 门禁通过后调用 `generateBrainstormingRTM()`
   - `kind=design` 门禁通过后调用 `generateDesignRTM()`
   - `kind=plan` 批准后调用 `generateDecomposingRTM()` + `generateImplementingRTM()`
   - `kind=verification` 门禁通过后调用 `generateAcceptingRTM()`

4. **agent-dh/packages/tools/reqboard/src/tools/reqboard-ask-confirm.ts**
   - 确认后更新对应 RTM 的 artifacts[].confirmed 状态
   - 更新 rtm-lifecycle.yml 节点状态

5. **agent-dh/packages/tools/reqboard/src/tools/reqboard-task-move.ts**
   - 任务状态变更时更新 rtm-implementing.yml 和任务详情文件

6. **agent-dh/packages/tools/reqboard/src/tools/reqboard-task-report.ts**
   - 子任务汇报时更新任务详情文件的 workflow 字段

#### StageOverview 集成

7. **agent-dh/packages/tools/reqboard/src/stage-overview.ts**
   - `assembleStageOverview()` 增强：读取 RTM 并合并追溯数据

#### 类型定义

8. **agent-dh/packages/tools/reqboard/src/types.ts**
   - 添加 `StageOverviewTraceability` 类型定义

### 配置文件（无需修改）

- RTM 文件路径统一为 `docs/requirements/REQ-xxx/rtm-*.yml`
- 无需修改 cordis.yml 或其他配置

---

## 任务列表

### Phase 1: 接口与数据契约（先行）

#### t1: RTM 数据类型定义
- **标题**: 实现 RTM TypeScript 类型定义
- **phase**: doc
- **side**: backend
- **depends_on**: []
- **serves**: FR-1
- **implements**: design/data-model.md#RTM 数据结构
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/types.ts`
  2. 定义所有 RTM YAML 结构的 TypeScript 接口：
     - `RTMMetadata` - 元数据（requirement_id / version / generated_at）
     - `RTMLifecycle` - 全局生命周期
     - `RTMBrainstorming` - 需求分析节点
     - `RTMDesign` - 设计节点
     - `RTMDecomposing` - 拆分节点
     - `RTMImplementing` - 实施节点（汇总文件）
     - `RTMTaskDetail` - 单个任务详情（workflow）
     - `RTMAccepting` - 验收节点
     - `Traceability` - 追溯映射
     - `Coverage` - 覆盖度统计
  3. 导出所有类型
- **acceptance**:
  - 运行 `cd agent-dh && pnpm build`，TypeScript 编译通过
  - 类型文件包含所有 6 个 RTM 节点 + lifecycle 的完整接口定义
  - 接口字段与 design/data-model.md 一致

#### t2: RTM 文件 I/O 接口
- **标题**: 实现 RTM 文件读写与版本控制
- **phase**: implement
- **side**: backend
- **depends_on**: [t1]
- **serves**: FR-1, FR-6, FR-9
- **implements**: design/interfaces.md#文件 I/O 接口
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/file-io.ts`
  2. 实现函数：
     - `readRTM<T>(filePath: string): T | null` - 读取 RTM YAML
     - `writeRTM<T>(filePath: string, data: T): void` - 原子写入（临时文件 + rename）
     - `getRTMPath(reqId: string, stage: string): string` - 获取 RTM 文件路径
     - `ensureRTMDir(reqId: string): void` - 确保需求目录存在
  3. 使用 js-yaml 序列化/反序列化
  4. 错误处理：文件不存在返回 null，YAML 格式错误记录日志
- **acceptance**:
  - 编写单元测试：创建临时目录，写入 RTM，读取验证内容一致
  - 测试版本号递增：连续写入 2 次，验证 version 从 1 → 2
  - 测试错误处理：读取不存在的文件返回 null，不抛异常

---

### Phase 2: 核心生成逻辑（依赖 Phase 1）

#### t3: 文档解析器
- **标题**: 实现 FR/serves/implements/covers 标注解析
- **phase**: implement
- **side**: backend
- **depends_on**: [t1]
- **serves**: FR-3, FR-4
- **implements**: design/architecture.md#文档解析器
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/parser.ts`
  2. 实现函数：
     - `parseFRList(requirementMd: string): FR[]` - 提取 `**FR-N:` 标记
     - `parseServesAnnotations(designMd: string): Map<string, string[]>` - 提取 `serves: FR-1, FR-2`
     - `parseImplementsAnnotations(taskJson: Task[]): Map<string, string[]>` - 从 design_serves 字段提取
     - `parseCoversAnnotations(testMd: string): Map<string, string[]>` - 提取 `covers: t-xxx`
  3. 使用正则表达式匹配标注
  4. 返回结构化数据（id / title / source / line）
- **acceptance**:
  - 单元测试：解析包含 3 个 FR 的文档，验证提取正确
  - 测试 serves 标注：`serves: FR-1, FR-2` 解析为 `["FR-1", "FR-2"]`
  - 测试边界情况：空文档返回空列表，无标注返回空 Map

#### t4: 追溯关系构建器
- **标题**: 实现四级追溯映射构建
- **phase**: implement
- **side**: backend
- **depends_on**: [t3]
- **serves**: FR-4
- **implements**: design/architecture.md#追溯关系构建
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/traceability-builder.ts`
  2. 实现函数：
     - `buildFRToDesign(frs: FR[], servesMap: Map<string, string[]>): Map<string, string[]>`
     - `buildDesignToTasks(designs: Design[], tasks: Task[]): Map<string, string[]>`
     - `buildTaskToTests(tasks: Task[], coversMap: Map<string, string[]>): Map<string, string[]>`
     - `buildFRToTasks(frToDesign: Map, designToTasks: Map): Map<string, string[]>` - 间接映射
  3. 算法：遍历标注，反向构建映射
- **acceptance**:
  - 单元测试：模拟数据（3 FR, 4 设计, 5 任务），验证映射正确
  - 测试间接映射：FR-1 → design#1.1 → t-001，验证 frToTasks 包含 FR-1 → [t-001]
  - 运行 `pnpm test rtm-parser.test.ts`，所有测试通过

#### t5: 覆盖度统计器
- **标题**: 实现三层覆盖度自动计算
- **phase**: implement
- **side**: backend
- **depends_on**: [t4]
- **serves**: FR-5
- **implements**: design/architecture.md#覆盖度统计
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/coverage-calculator.ts`
  2. 实现函数：
     - `calculateDesignCoverage(frs: FR[], frToDesign: Map): Coverage`
     - `calculateImplementationCoverage(designs: Design[], designToTasks: Map): Coverage`
     - `calculateTestingCoverage(tasks: Task[], taskToTests: Map): Coverage`
  3. 返回：total / covered / uncovered / rate
  4. 算法：统计映射中有值的项 / 总项数
- **acceptance**:
  - 单元测试：3 FR，2 有设计 → 覆盖度 67%，uncovered = [FR-3]
  - 测试 100% 覆盖：所有 FR 都有设计 → rate = 100, uncovered = []
  - 运行 `pnpm test rtm-coverage.test.ts`，所有测试通过

---

### Phase 3: RTM 生成器实现（依赖 Phase 2）

#### t6: rtm-lifecycle.yml 生成器
- **标题**: 实现全局生命周期 RTM 生成
- **phase**: implement
- **side**: backend
- **depends_on**: [t2, t5]
- **serves**: FR-1, FR-2
- **implements**: design/architecture.md#RTM 生成逻辑 - 触发点 1
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/lifecycle-generator.ts`
  2. 实现 `generateLifecycleRTM(reqId: string): void`
  3. 生成骨架：current_stage = draft，所有节点 status = pending
  4. 调用 writeRTM 保存到 `docs/requirements/REQ-xxx/rtm-lifecycle.yml`
- **acceptance**:
  - 单元测试：调用生成器，验证文件存在且内容正确
  - 验证节点列表：包含 draft / brainstorming / design / decomposing / implementing / accepting / done
  - 验证初始状态：current_stage = draft，所有节点 pending

#### t7: rtm-brainstorming.yml 生成器
- **标题**: 实现需求分析节点 RTM 生成
- **phase**: implement
- **side**: backend
- **depends_on**: [t3, t5, t6]
- **serves**: FR-1, FR-2, FR-3
- **implements**: design/architecture.md#RTM 生成逻辑 - 触发点 2
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/brainstorming-generator.ts`
  2. 实现 `generateBrainstormingRTM(reqId: string): void`
  3. 读取 requirement.md，调用 parseFRList 提取 FR
  4. 构建 outputs.requirements 和空 fr_to_design 映射
  5. 保存到 `docs/requirements/REQ-xxx/rtm-brainstorming.yml`
- **acceptance**:
  - 集成测试：创建测试需求，requirement.md 包含 3 个 FR
  - 调用生成器，验证 rtm-brainstorming.yml 包含 3 个 FR
  - 验证 fr_to_design 为空对象 `{}`

#### t8: rtm-design.yml 生成器
- **标题**: 实现设计节点 RTM 生成
- **phase**: implement
- **side**: backend
- **depends_on**: [t3, t4, t5, t7]
- **serves**: FR-1, FR-2, FR-4, FR-5
- **implements**: design/architecture.md#RTM 生成逻辑 - 触发点 4
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/design-generator.ts`
  2. 实现 `generateDesignRTM(reqId: string): void`
  3. 扫描 `design/*.md`，解析章节和 serves 标注
  4. 调用 buildFRToDesign 构建映射
  5. 调用 calculateDesignCoverage 计算覆盖度
  6. 保存到 `docs/requirements/REQ-xxx/rtm-design.yml`
- **acceptance**:
  - 集成测试：创建测试设计文档（2 个章节，serves FR-1 和 FR-2）
  - 调用生成器，验证 design_sections 包含 2 个章节
  - 验证 fr_to_design 映射：FR-1 → [design/arch#1.1]
  - 验证覆盖度：total_frs = 3, covered_frs = 2, rate = 67%

#### t9: rtm-decomposing.yml 生成器
- **标题**: 实现拆分节点 RTM 生成
- **phase**: implement
- **side**: backend
- **depends_on**: [t4, t5, t8]
- **serves**: FR-1, FR-2, FR-4, FR-5
- **implements**: design/architecture.md#RTM 生成逻辑 - 触发点 5
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/decomposing-generator.ts`
  2. 实现 `generateDecomposingRTM(reqId: string): void`
  3. 从任务台账读取 tasks，提取 design_serves 字段
  4. 调用 buildDesignToTasks 构建映射
  5. 调用 calculateImplementationCoverage 计算覆盖度
  6. 保存到 `docs/requirements/REQ-xxx/rtm-decomposing.yml`
- **acceptance**:
  - 集成测试：创建测试任务（5 个任务，覆盖 4 个设计章节）
  - 调用生成器，验证 tasks 包含 5 个任务
  - 验证 design_to_tasks 映射：design#1.1 → [t-001]
  - 验证覆盖度：total_designs = 4, covered_designs = 4, rate = 100%

#### t10: rtm-implementing.yml 生成器
- **标题**: 实现实施节点 RTM 生成（汇总文件 + 任务详情目录）
- **phase**: implement
- **side**: backend
- **depends_on**: [t2, t9]
- **serves**: FR-1, FR-2, FR-10, FR-11
- **implements**: design/architecture.md#RTM 生成逻辑 - 触发点 5/6
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/implementing-generator.ts`
  2. 实现 `generateImplementingRTM(reqId: string): void`
     - 生成汇总文件：rtm-implementing.yml（只含统计 + 任务 id 列表）
     - 为每个任务生成详情文件：rtm-implementing/t-xxx.yml（含 workflow）
  3. 实现 `updateTaskDetail(reqId: string, taskId: string, updates: Partial<RTMTaskDetail>): void`
     - 更新单个任务文件（只写变化的那个文件）
  4. Workflow 初始化：根据任务的 phase 字段决定需要哪些子阶段
     - phase=implement → 只有 implement 阶段
     - phase=doc → doc + implement + test + commit
     - 完整任务 → doc → ui → analysis → implement → test → review → commit
  5. 保存到 `docs/requirements/REQ-xxx/rtm-implementing.yml` 和 `rtm-implementing/*.yml`
- **acceptance**:
  - 集成测试：批准拆分计划（5 个任务）
  - 调用生成器，验证汇总文件存在：tasks_total = 5, tasks_todo = 5
  - 验证任务详情目录：`ls rtm-implementing/` 包含 5 个 t-xxx.yml
  - 验证 workflow 初始化：backend 任务无 ui 阶段，frontend 任务有 ui 阶段
  - 测试更新：调用 updateTaskDetail 更新 t-001，验证只有 t-001.yml 被修改

#### t11: rtm-accepting.yml 生成器
- **标题**: 实现验收节点 RTM 生成
- **phase**: implement
- **side**: backend
- **depends_on**: [t3, t4, t5, t10]
- **serves**: FR-1, FR-2, FR-4, FR-5
- **implements**: design/architecture.md#RTM 生成逻辑 - 触发点 7
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/rtm/accepting-generator.ts`
  2. 实现 `generateAcceptingRTM(reqId: string): void`
  3. 扫描测试文档，解析 covers 标注
  4. 调用 buildTaskToTests 构建映射
  5. 调用 calculateTestingCoverage 计算覆盖度
  6. 保存到 `docs/requirements/REQ-xxx/rtm-accepting.yml`
- **acceptance**:
  - 集成测试：创建测试用例文档（2 个测试，covers t-001 和 t-002）
  - 调用生成器，验证 test_cases 包含 2 个测试
  - 验证 task_to_tests 映射：t-001 → [TC-1]
  - 验证覆盖度：total_tasks = 5, tested_tasks = 2, rate = 40%

---

### Phase 4: Reqboard 工具集成（依赖 Phase 3）

#### t12: reqboard-create 集成
- **标题**: 在 reqboard_create 触发 rtm-lifecycle.yml 生成
- **phase**: implement
- **side**: backend
- **depends_on**: [t6]
- **serves**: FR-2
- **implements**: design/interfaces.md#reqboard_create 集成
- **implementation**:
  1. 修改 `agent-dh/packages/tools/reqboard/src/tools/reqboard-create.ts`
  2. 在 `execute()` 结尾，需求创建成功后
  3. 调用 `generateLifecycleRTM(requirementId)`
  4. 错误处理：RTM 生成失败记录日志，不影响需求创建
- **acceptance**:
  - 集成测试：调用 reqboard_create 创建需求
  - 验证 rtm-lifecycle.yml 自动生成
  - 验证文件内容：current_stage = draft

#### t13: reqboard-submit 集成（requirement/design/plan/verification）
- **标题**: 在 reqboard_submit 各类型触发对应 RTM 生成
- **phase**: implement
- **side**: backend
- **depends_on**: [t7, t8, t9, t11]
- **serves**: FR-2
- **implements**: design/interfaces.md#reqboard_submit 集成
- **implementation**:
  1. 修改 `agent-dh/packages/tools/reqboard/src/tools/reqboard-submit.ts`
  2. 在各 kind 的门禁检查通过后插入 RTM 生成：
     - `kind=requirement` → `generateBrainstormingRTM()`
     - `kind=design` → `generateDesignRTM()`
     - `kind=plan` 批准后 → `generateDecomposingRTM()` + `generateImplementingRTM()`
     - `kind=verification` → `generateAcceptingRTM()`
  3. 错误处理：RTM 生成失败记录日志，不影响提交流程
- **acceptance**:
  - 集成测试：完整流程测试
  - 提交需求文档 → 验证 rtm-brainstorming.yml 生成
  - 提交设计文档 → 验证 rtm-design.yml 生成
  - 批准拆分计划 → 验证 rtm-decomposing.yml 和 rtm-implementing.yml 生成
  - 提交验收材料 → 验证 rtm-accepting.yml 生成

#### t14: reqboard-ask-confirm 集成（产物确认状态更新）
- **标题**: 确认产物后更新 RTM 的 confirmed 状态
- **phase**: implement
- **side**: backend
- **depends_on**: [t2, t13]
- **serves**: FR-2, FR-6
- **implements**: design/interfaces.md#reqboard_ask_confirm 集成
- **implementation**:
  1. 修改 `agent-dh/packages/tools/reqboard/src/tools/reqboard-ask-confirm.ts`
  2. 在用户确认产物后（`confirmed=true`）：
     - `kind=requirement` → 更新 rtm-brainstorming.yml 的 artifacts[0].confirmed
     - `kind=design` → 更新 rtm-design.yml 的 artifacts[].confirmed
     - `target=plan` → 更新 rtm-lifecycle.yml 的 stages.decomposing.status = completed
  3. 使用 readRTM + 修改 + writeRTM（版本号 +1）
- **acceptance**:
  - 集成测试：提交需求文档 → 确认 → 验证 rtm-brainstorming.yml 的 confirmed = true
  - 验证版本号递增：确认前 version = 1，确认后 version = 2

#### t15: reqboard-task-move 集成（任务状态同步）
- **标题**: 任务状态变更时更新 rtm-implementing.yml
- **phase**: implement
- **side**: backend
- **depends_on**: [t10, t13]
- **serves**: FR-2, FR-6
- **implements**: design/interfaces.md#reqboard_task_move 集成
- **implementation**:
  1. 修改 `agent-dh/packages/tools/reqboard/src/tools/reqboard-task-move.ts`
  2. 在任务状态变更后：
     - 调用 `updateTaskDetail(reqId, taskId, { status: newStatus })` 更新单个任务文件
     - 重新统计 tasks_done / tasks_in_progress / tasks_todo
     - 更新汇总文件 rtm-implementing.yml
  3. 只写变化的文件（单个任务文件 + 汇总文件）
- **acceptance**:
  - 集成测试：开工任务 t-001（todo → in_progress）
  - 验证 rtm-implementing/t-001.yml 的 status = in_progress，started_at 已写入
  - 验证汇总文件：tasks_in_progress = 1, tasks_todo = 4
  - 完成任务 t-001 → 验证 tasks_done = 1

#### t16: reqboard-task-report 集成（子任务 workflow 更新）
- **标题**: 子任务汇报时更新任务详情文件的 workflow
- **phase**: implement
- **side**: backend
- **depends_on**: [t10, t15]
- **serves**: FR-2, FR-6, FR-11
- **implements**: design/interfaces.md#reqboard_task_report 集成
- **implementation**:
  1. 修改 `agent-dh/packages/tools/reqboard/src/tools/reqboard-task-report.ts`
  2. 在汇报时：
     - 推断当前子阶段（doc / ui / analysis / implement / test / review / commit）
     - 调用 `updateTaskDetail(reqId, taskId, { workflow: [...] })` 更新 workflow
     - 标记当前子阶段为 done，记录 completed_at
  3. 算法：根据 summary 关键词推断阶段（"编写文档" → doc，"实现功能" → implement）
- **acceptance**:
  - 集成测试：任务 t-001 开工 → 汇报"编写任务文档" → 汇报"实现功能"
  - 验证 rtm-implementing/t-001.yml 的 workflow[0].phase = doc, status = done
  - 验证 workflow[3].phase = implement, status = in_progress
  - 验证 workflow_done = 1, workflow_total = 7

---

### Phase 5: StageOverview 集成（依赖 Phase 4）

#### t17: StageOverview RTM 读取器
- **标题**: 实现 StageOverview 的 RTM 读取接口
- **phase**: implement
- **side**: backend
- **depends_on**: [t2]
- **serves**: FR-7
- **implements**: design/interfaces.md#StageOverview 集成
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/src/stage-overview/rtm-reader.ts`
  2. 实现函数：
     - `readStageRTM(reqId: string, stage: string): any | null` - 读取当前节点 RTM
     - `readLifecycleRTM(reqId: string): RTMLifecycle | null` - 读取全局 RTM
  3. 错误处理：文件不存在返回 null，降级到实时解析
- **acceptance**:
  - 单元测试：创建测试 RTM 文件，调用读取器，验证返回正确
  - 测试降级模式：删除 RTM 文件，调用读取器返回 null

#### t18: StageOverview assembler 增强
- **标题**: 增强 assembleStageOverview 合并 RTM 追溯数据
- **phase**: implement
- **side**: backend
- **depends_on**: [t17]
- **serves**: FR-7
- **implements**: design/interfaces.md#StageOverview 集成
- **implementation**:
  1. 修改 `agent-dh/packages/tools/reqboard/src/stage-overview.ts`
  2. 在 `assembleStageOverview()` 中：
     - 调用 readLifecycleRTM 和 readStageRTM
     - 如果 RTM 存在，合并追溯数据到 `stages[stage].body`
     - 添加 `traceability` 字段：fr_to_design / design_to_tasks / task_to_tests
     - 添加 `coverage` 字段：design / implementation / testing
  3. 保持向后兼容：RTM 不存在时使用原逻辑
- **acceptance**:
  - 集成测试：创建测试需求（含完整 RTM）
  - 调用 assembleStageOverview，验证返回包含 traceability 字段
  - 验证追溯链：FR-1 → design#1.1 → t-001 → TC-1
  - 验证覆盖度：design.rate = 100%, implementation.rate = 100%, testing.rate = 40%

---

### Phase 6: 端到端测试与文档（依赖 Phase 5）

#### t19: 端到端测试
- **标题**: 完整流程端到端测试
- **phase**: test
- **side**: backend
- **depends_on**: [t18]
- **serves**: FR-1, FR-2, FR-3, FR-4, FR-5, FR-7, FR-10
- **implements**: design/test-cases.md#端到端测试
- **implementation**:
  1. 创建 `agent-dh/packages/tools/reqboard/tests/rtm-e2e.test.ts`
  2. 测试完整流程：
     - 创建需求 → 验证 rtm-lifecycle.yml
     - 提交需求文档 → 验证 rtm-brainstorming.yml（3 个 FR）
     - 提交设计文档 → 验证 rtm-design.yml（覆盖度 67%）
     - 批准拆分计划 → 验证 rtm-decomposing.yml 和 rtm-implementing.yml
     - 任务状态变更 → 验证 rtm-implementing.yml 更新
     - 提交验收材料 → 验证 rtm-accepting.yml（测试覆盖度 40%）
  3. 验证追溯链完整性：FR-1 → design#1.1 → t-001 → TC-1
  4. 验证性能：读取 2 个 RTM < 5ms
- **acceptance**:
  - 运行 `pnpm test rtm-e2e.test.ts`，所有测试通过
  - 验证生成的 7 个 RTM 文件格式正确
  - 验证追溯关系完整：所有 FR 都能追溯到测试用例

#### t20: 使用文档与示例
- **标题**: 编写 RTM 使用文档和 Dive 模式集成示例
- **phase**: doc
- **side**: doc
- **depends_on**: [t19]
- **serves**: FR-8
- **implements**: design/use-cases.md#Dive 模式使用示例
- **implementation**:
  1. 创建 `agent-dh/docs/guides/rtm-usage.md`
  2. 内容包括：
     - RTM 文件结构说明
     - 7 个触发点说明
     - Dive 模式如何读取 RTM（代码示例）
     - 节点输入包注入规则
     - 压缩模式使用示例
  3. 代码示例：展示 Dive 模式读取 RTM 并做决策的完整流程
- **acceptance**:
  - 文档包含所有 7 个触发点的说明
  - 包含至少 3 个 Dive 模式代码示例
  - 文档通过 markdown lint 检查

---

## 依赖关系图

```
Phase 1 (接口/契约先行):
  t1 (类型定义) ────┐
                   ├──→ t2 (文件 I/O)
                   │
                   ├──→ t3 (文档解析器)
                   │        ↓
                   │    t4 (追溯构建) ──→ t5 (覆盖度统计)
                   │
Phase 2 (核心逻辑):
  t2, t5 ──→ t6 (lifecycle 生成器)
  t3, t5, t6 ──→ t7 (brainstorming 生成器)
  t3, t4, t5, t7 ──→ t8 (design 生成器)
  t4, t5, t8 ──→ t9 (decomposing 生成器)
  t2, t9 ──→ t10 (implementing 生成器)
  t3, t4, t5, t10 ──→ t11 (accepting 生成器)

Phase 3 (工具集成):
  t6 ──→ t12 (reqboard-create 集成)
  t7, t8, t9, t11 ──→ t13 (reqboard-submit 集成)
  t2, t13 ──→ t14 (reqboard-ask-confirm 集成)
  t10, t13 ──→ t15 (reqboard-task-move 集成)
  t10, t15 ──→ t16 (reqboard-task-report 集成)

Phase 4 (StageOverview):
  t2 ──→ t17 (RTM 读取器)
  t17 ──→ t18 (assembler 增强)

Phase 5 (测试/文档):
  t18 ──→ t19 (E2E 测试)
  t19 ──→ t20 (使用文档)
```

---

## 验收标准

### 全局验收（t19 完成后）

1. **端到端测试通过**：运行 `pnpm test rtm-e2e.test.ts`，所有测试通过
2. **性能达标**：Dive 模式读取 2 个 RTM < 5ms（vs 现在 ~500ms）
3. **追溯完整性**：所有 FR 都能追溯到测试用例（FR → 设计 → 任务 → 测试）
4. **数据一致性**：RTM 的任务状态与台账一致
5. **文件结构正确**：生成的 RTM 文件格式符合 design/rtm-schema.md

### 门禁检查（自动化）

1. **设计覆盖度门禁**：提交设计文档时，coverage.design.rate 必须 = 100%
2. **实施覆盖度门禁**：批准拆分计划时，coverage.implementation.rate 必须 = 100%
3. **测试覆盖度门禁**：提交验收材料时，coverage.testing.rate 必须 >= 80%

---

## 风险与缓解

### 风险1：TypeScript 类型复杂度

**风险**：RTM 数据结构嵌套深，类型定义可能出错

**缓解**：
- t1 先行，所有后续任务依赖它
- 单元测试覆盖所有类型的序列化/反序列化
- 使用 Zod 进行运行时校验（可选）

### 风险2：文档解析鲁棒性

**风险**：用户可能不按规范写标注，导致解析失败

**缓解**：
- t3 实现时充分测试边界情况
- 解析失败时标记为未覆盖，不崩溃
- 提供友好的错误提示

### 风险3：并发更新冲突

**风险**：多个任务同时更新 rtm-implementing.yml

**缓解**：
- t10 使用拆分文件结构（汇总 + 任务详情目录）
- 更新只写变化的任务文件，减少冲突
- 版本号检测（可选）

---

## 实施顺序建议

1. **Week 1**: Phase 1 (t1-t2) + Phase 2 前半 (t3-t5)
2. **Week 2**: Phase 2 后半 (t6-t11)
3. **Week 3**: Phase 3 (t12-t16)
4. **Week 4**: Phase 4-5 (t17-t20)

**关键路径**：t1 → t3 → t4 → t5 → t8 → t9 → t10 → t15 → t16 → t19

---

## 后续演进

### Phase 2（未来优化，不在本次范围）

- 追溯链可视化（图形展示）
- 实时校验机制
- 批量迁移存量需求

### Phase 3（未来扩展，不在本次范围）

- 跨需求追溯（依赖关系）
- 影响分析（修改波及面）
- 智能建议（覆盖度优化建议）
