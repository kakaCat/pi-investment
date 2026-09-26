# REQ-260926140539-457b 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v2

**交付结论**：交付结论（v2，含补实现）：RTM YAML 数据底座按 20 张卡落地后，复核 requirement.md 发现首轮卡表漏了 4 项明确要求的能力，已补齐：① FR-8 节点输入包装配 + 压缩模式（新增 packages/tools/reqboard/src/dive/node-input.ts）；② FR-8 Dive 决策（新增 dive/decision.ts）；③ FR-2/FR-5 覆盖度硬门禁接线（设计 100% 拒提交 / 实施 100% 拒批准 / 测试 ≥80% 拒验收；存量直种需求沿用本仓 isLegacy 口径豁免；RTM 缺失不拦截）；④ 修复测试文档发现口径（原不扫 tests/ → 本仓真实需求测试覆盖度恒为 0%）。新增 12 条单测；reqboard 套件 12→13 文件、83→95 测试全绿，包级 tsc exit 0；dsh-pmboard 全量回归失败集合 41 文件 / 197 用例，与改动前逐一致（零新增回归），包级 tsc 错误数 149 不变。真实需求数据门禁读数：设计 100%（11/11）、实施 100%（94/94）、测试 95%（19/20），Dive 决策 can_proceed=true → next_stage=done。仍未做（请人裁决）：FR-11 Agent Teams 并行执行受阻于本构建宿主能力（deps.jobs 未装配，AdvanceTool 报 DSH_JOBS_UNAVAILABLE；装配它会连锁启用「批准即自动拆分」，属产品决策）；ReqboardDiveManager.getActiveRequirement 仍是 return null 桩，Dive 自动闭环未接；实施门禁在「先批准后落库」流程下 total=0 空转；源码已接线但 :13080 未 rebuild/restart，线上尚未自动生成 rtm-*.yml。改动仍为工作区未提交状态（未 commit）。

## 1. 验收列表

### v2-1 · 实现 RTM TypeScript 类型定义

**验收内容**：【实现 RTM TypeScript 类型定义】验收：运行 `cd agent-dh/packages/tools/reqboard && pnpm build` 编译通过无报错；检查 src/rtm/types.ts 包含所有接口定义；执行 `grep -c "export interface" src/rtm/types.ts` 返回 >= 10

**操作步骤**：
1. 运行 `cd agent-dh/packages/tools/reqboard && pnpm build` 编译通过无报错
2. 检查 src/rtm/types.ts 包含所有接口定义
3. 执行 `grep -c "export interface" src/rtm/types.ts` 返回 >= 10

**预期结果**：按上述步骤执行后满足验收标准：运行 `cd agent-dh/packages/tools/reqboard && pnpm build` 编译通过无报错；检查 src/rtm/types.ts 包含所有接口定义；执行 `grep -c "export interface" src/rtm/types.ts` 返回 >= 10

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-2 · 实现 RTM 文件读写与版本控制

**验收内容**：【实现 RTM 文件读写与版本控制】验收：运行 `pnpm test file-io.test.ts` 通过；测试写入后读取内容一致；测试连续写入 2 次 version 从 1 递增到 2；测试读取不存在文件返回 null

**操作步骤**：
1. 运行 `pnpm test file-io.test.ts` 通过
2. 测试写入后读取内容一致
3. 测试连续写入 2 次 version 从 1 递增到 2
4. 测试读取不存在文件返回 null

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test file-io.test.ts` 通过；测试写入后读取内容一致；测试连续写入 2 次 version 从 1 递增到 2；测试读取不存在文件返回 null

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-3 · 实现 FR/serves/implements/covers 标注解析

**验收内容**：【实现 FR/serves/implements/covers 标注解析】验收：运行 `pnpm test rtm-parser.test.ts` 通过；解析 "**FR-1: 功能点" 返回 [{id:"FR-1",...}]；解析 "serves: FR-1, FR-2" 返回 ["FR-1","FR-2"]；空文档返回空数组

**操作步骤**：
1. 运行 `pnpm test rtm-parser.test.ts` 通过
2. 解析 "**FR-1: 功能点" 返回 [{id:"FR-1",...}]
3. 解析 "serves: FR-1, FR-2" 返回 ["FR-1","FR-2"]
4. 空文档返回空数组

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test rtm-parser.test.ts` 通过；解析 "**FR-1: 功能点" 返回 [{id:"FR-1",...}]；解析 "serves: FR-1, FR-2" 返回 ["FR-1","FR-2"]；空文档返回空数组

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-4 · 实现四级追溯映射构建

**验收内容**：【实现四级追溯映射构建】验收：运行 `pnpm test traceability-builder.test.ts` 通过；输入 3 FR + 4 设计章节 + 5 任务验证映射正确；buildFRToTasks 正确计算 FR-1 → design#1.1 → t-001 传递关系

**操作步骤**：
1. 运行 `pnpm test traceability-builder.test.ts` 通过
2. 输入 3 FR + 4 设计章节 + 5 任务验证映射正确
3. buildFRToTasks 正确计算 FR-1 → design#1.1 → t-001 传递关系

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test traceability-builder.test.ts` 通过；输入 3 FR + 4 设计章节 + 5 任务验证映射正确；buildFRToTasks 正确计算 FR-1 → design#1.1 → t-001 传递关系

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-5 · 实现三层覆盖度自动计算

**验收内容**：【实现三层覆盖度自动计算】验收：运行 `pnpm test rtm-coverage.test.ts` 通过；3 FR 中 2 有设计返回 rate 0.67 且 uncovered=["FR-3"]；100% 覆盖返回 rate=1.0 且 uncovered=[]

**操作步骤**：
1. 运行 `pnpm test rtm-coverage.test.ts` 通过
2. 3 FR 中 2 有设计返回 rate 0.67 且 uncovered=["FR-3"]
3. 100% 覆盖返回 rate=1.0 且 uncovered=[]

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test rtm-coverage.test.ts` 通过；3 FR 中 2 有设计返回 rate 0.67 且 uncovered=["FR-3"]；100% 覆盖返回 rate=1.0 且 uncovered=[]

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-6 · 实现全局生命周期 RTM 生成

**验收内容**：【实现全局生命周期 RTM 生成】验收：运行 `pnpm test lifecycle-generator.test.ts` 通过；调用 generateLifecycleRTM 后 rtm-lifecycle.yml 存在；执行 `yq .lifecycle.current_stage` 返回 "draft"；`yq .lifecycle.stages | keys | length` 返回 7

**操作步骤**：
1. 运行 `pnpm test lifecycle-generator.test.ts` 通过
2. 调用 generateLifecycleRTM 后 rtm-lifecycle.yml 存在
3. 执行 `yq .lifecycle.current_stage` 返回 "draft"
4. `yq .lifecycle.stages | keys | length` 返回 7

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test lifecycle-generator.test.ts` 通过；调用 generateLifecycleRTM 后 rtm-lifecycle.yml 存在；执行 `yq .lifecycle.current_stage` 返回 "draft"；`yq .lifecycle.stages | keys | length` 返回 7

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-7 · 实现需求分析节点 RTM 生成

**验收内容**：【实现需求分析节点 RTM 生成】验收：运行 `pnpm test brainstorming-generator.test.ts` 通过；含 3 个 FR 的 requirement.md 调用生成器后 `yq .outputs.requirements | length` 返回 3；`yq .traceability.fr_to_design` 返回空对象

**操作步骤**：
1. 运行 `pnpm test brainstorming-generator.test.ts` 通过
2. 含 3 个 FR 的 requirement.md 调用生成器后 `yq .outputs.requirements | length` 返回 3
3. `yq .traceability.fr_to_design` 返回空对象

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test brainstorming-generator.test.ts` 通过；含 3 个 FR 的 requirement.md 调用生成器后 `yq .outputs.requirements | length` 返回 3；`yq .traceability.fr_to_design` 返回空对象

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-8 · 实现设计节点 RTM 生成

**验收内容**：【实现设计节点 RTM 生成】验收：运行 `pnpm test design-generator.test.ts` 通过；2 个设计文档调用生成器后 `yq .outputs.design_sections | length` 返回 2；`yq .traceability.fr_to_design.FR-1[0]` 含 "design/"；`yq .coverage.design.rate` 返回 0.67

**操作步骤**：
1. 运行 `pnpm test design-generator.test.ts` 通过
2. 2 个设计文档调用生成器后 `yq .outputs.design_sections | length` 返回 2
3. `yq .traceability.fr_to_design.FR-1[0]` 含 "design/"
4. `yq .coverage.design.rate` 返回 0.67

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test design-generator.test.ts` 通过；2 个设计文档调用生成器后 `yq .outputs.design_sections | length` 返回 2；`yq .traceability.fr_to_design.FR-1[0]` 含 "design/"；`yq .coverage.design.rate` 返回 0.67

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-9 · 实现拆分节点 RTM 生成

**验收内容**：【实现拆分节点 RTM 生成】验收：运行 `pnpm test decomposing-generator.test.ts` 通过；5 个任务调用生成器后 `yq .outputs.tasks | length` 返回 5；`yq .traceability.design_to_tasks."design#1.1"[0]` 含 "t-"；`yq .coverage.implementation.rate` 返回 1.0

**操作步骤**：
1. 运行 `pnpm test decomposing-generator.test.ts` 通过
2. 5 个任务调用生成器后 `yq .outputs.tasks | length` 返回 5
3. `yq .traceability.design_to_tasks."design#1.1"[0]` 含 "t-"
4. `yq .coverage.implementation.rate` 返回 1.0

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test decomposing-generator.test.ts` 通过；5 个任务调用生成器后 `yq .outputs.tasks | length` 返回 5；`yq .traceability.design_to_tasks."design#1.1"[0]` 含 "t-"；`yq .coverage.implementation.rate` 返回 1.0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-10 · 实现实施节点 RTM 生成（汇总 + 任务详情目录）

**验收内容**：【实现实施节点 RTM 生成（汇总 + 任务详情目录）】验收：运行 `pnpm test implementing-generator.test.ts` 通过；5 个任务生成后 `yq .status.tasks_total` 返回 5；`ls rtm-implementing/*.yml | wc -l` 返回 5；backend 任务 workflow 不含 ui 阶段；updateTaskDetail 后 `git diff` 仅该任务文件变化

**操作步骤**：
1. 运行 `pnpm test implementing-generator.test.ts` 通过
2. 5 个任务生成后 `yq .status.tasks_total` 返回 5
3. `ls rtm-implementing/*.yml | wc -l` 返回 5
4. backend 任务 workflow 不含 ui 阶段
5. updateTaskDetail 后 `git diff` 仅该任务文件变化

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test implementing-generator.test.ts` 通过；5 个任务生成后 `yq .status.tasks_total` 返回 5；`ls rtm-implementing/*.yml | wc -l` 返回 5；backend 任务 workflow 不含 ui 阶段；updateTaskDetail 后 `git diff` 仅该任务文件变化

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-11 · 实现验收节点 RTM 生成

**验收内容**：【实现验收节点 RTM 生成】验收：运行 `pnpm test accepting-generator.test.ts` 通过；2 个测试用例调用生成器后 `yq .outputs.test_cases | length` 返回 2；`yq .traceability.task_to_tests."t-001"[0]` 含 "TC-"；`yq .coverage.testing.rate` 返回 0.4

**操作步骤**：
1. 运行 `pnpm test accepting-generator.test.ts` 通过
2. 2 个测试用例调用生成器后 `yq .outputs.test_cases | length` 返回 2
3. `yq .traceability.task_to_tests."t-001"[0]` 含 "TC-"
4. `yq .coverage.testing.rate` 返回 0.4

**预期结果**：按上述步骤执行后满足验收标准：运行 `pnpm test accepting-generator.test.ts` 通过；2 个测试用例调用生成器后 `yq .outputs.test_cases | length` 返回 2；`yq .traceability.task_to_tests."t-001"[0]` 含 "TC-"；`yq .coverage.testing.rate` 返回 0.4

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-12 · 在 reqboard_create 触发 rtm-lifecycle.yml 生成

**验收内容**：【在 reqboard_create 触发 rtm-lifecycle.yml 生成】验收：运行集成测试 `pnpm test reqboard-create-integration.test.ts` 通过；调用 reqboard_create 后 rtm-lifecycle.yml 存在；`yq .lifecycle.current_stage` 返回 "draft"

**操作步骤**：
1. 运行集成测试 `pnpm test reqboard-create-integration.test.ts` 通过
2. 调用 reqboard_create 后 rtm-lifecycle.yml 存在
3. `yq .lifecycle.current_stage` 返回 "draft"

**预期结果**：按上述步骤执行后满足验收标准：运行集成测试 `pnpm test reqboard-create-integration.test.ts` 通过；调用 reqboard_create 后 rtm-lifecycle.yml 存在；`yq .lifecycle.current_stage` 返回 "draft"

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-13 · 在 reqboard_submit 各类型触发对应 RTM 生成

**验收内容**：【在 reqboard_submit 各类型触发对应 RTM 生成】验收：运行集成测试 `pnpm test reqboard-submit-integration.test.ts` 通过；kind=requirement 后 rtm-brainstorming.yml 存在；kind=design 后 rtm-design.yml 存在；kind=plan 批准后 rtm-decomposing.yml 与 rtm-implementing.yml 都存在；kind=verification 后 rtm-accepting.yml 存在

**操作步骤**：
1. 运行集成测试 `pnpm test reqboard-submit-integration.test.ts` 通过
2. kind=requirement 后 rtm-brainstorming.yml 存在
3. kind=design 后 rtm-design.yml 存在
4. kind=plan 批准后 rtm-decomposing.yml 与 rtm-implementing.yml 都存在
5. kind=verification 后 rtm-accepting.yml 存在

**预期结果**：按上述步骤执行后满足验收标准：运行集成测试 `pnpm test reqboard-submit-integration.test.ts` 通过；kind=requirement 后 rtm-brainstorming.yml 存在；kind=design 后 rtm-design.yml 存在；kind=plan 批准后 rtm-decomposing.yml 与 rtm-implementing.yml 都存在；kind=verification 后 rtm-accepting.yml 存在

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-14 · 确认产物后更新 RTM 的 confirmed 状态

**验收内容**：【确认产物后更新 RTM 的 confirmed 状态】验收：运行集成测试 `pnpm test reqboard-ask-confirm-integration.test.ts` 通过；确认需求文档后 `yq .artifacts[0].confirmed rtm-brainstorming.yml` 返回 true；`yq .metadata.version` 从 1 变为 2

**操作步骤**：
1. 运行集成测试 `pnpm test reqboard-ask-confirm-integration.test.ts` 通过
2. 确认需求文档后 `yq .artifacts[0].confirmed rtm-brainstorming.yml` 返回 true
3. `yq .metadata.version` 从 1 变为 2

**预期结果**：按上述步骤执行后满足验收标准：运行集成测试 `pnpm test reqboard-ask-confirm-integration.test.ts` 通过；确认需求文档后 `yq .artifacts[0].confirmed rtm-brainstorming.yml` 返回 true；`yq .metadata.version` 从 1 变为 2

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-15 · 任务状态变更时更新 rtm-implementing.yml

**验收内容**：【任务状态变更时更新 rtm-implementing.yml】验收：运行集成测试 `pnpm test reqboard-task-move-integration.test.ts` 通过；t-001 开工后 `yq .task.status rtm-implementing/t-001.yml` 返回 "in_progress" 且 started_at 非空；汇总文件 tasks_in_progress=1、tasks_todo=4；完成后 tasks_done=1

**操作步骤**：
1. 运行集成测试 `pnpm test reqboard-task-move-integration.test.ts` 通过
2. t-001 开工后 `yq .task.status rtm-implementing/t-001.yml` 返回 "in_progress" 且 started_at 非空
3. 汇总文件 tasks_in_progress=1、tasks_todo=4
4. 完成后 tasks_done=1

**预期结果**：按上述步骤执行后满足验收标准：运行集成测试 `pnpm test reqboard-task-move-integration.test.ts` 通过；t-001 开工后 `yq .task.status rtm-implementing/t-001.yml` 返回 "in_progress" 且 started_at 非空；汇总文件 tasks_in_progress=1、tasks_todo=4；完成后 tasks_done=1

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-16 · 子任务汇报时更新任务详情文件的 workflow

**验收内容**：【子任务汇报时更新任务详情文件的 workflow】验收：运行集成测试 `pnpm test reqboard-task-report-integration.test.ts` 通过；汇报"编写任务文档"后 `yq .task.workflow[0].phase` 返回 "doc"、status 返回 "done"；汇报"实现功能"后 workflow[3].status 返回 "in_progress"；`yq .task.workflow_done` 返回 1

**操作步骤**：
1. 运行集成测试 `pnpm test reqboard-task-report-integration.test.ts` 通过
2. 汇报"编写任务文档"后 `yq .task.workflow[0].phase` 返回 "doc"、status 返回 "done"
3. 汇报"实现功能"后 workflow[3].status 返回 "in_progress"
4. `yq .task.workflow_done` 返回 1

**预期结果**：按上述步骤执行后满足验收标准：运行集成测试 `pnpm test reqboard-task-report-integration.test.ts` 通过；汇报"编写任务文档"后 `yq .task.workflow[0].phase` 返回 "doc"、status 返回 "done"；汇报"实现功能"后 workflow[3].status 返回 "in_progress"；`yq .task.workflow_done` 返回 1

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-17 · 实现 StageOverview 的 RTM 读取接口

**验收内容**：【实现 StageOverview 的 RTM 读取接口】验收：运行单元测试 `pnpm test rtm-reader.test.ts` 通过；readStageRTM 返回含 outputs/traceability/coverage 的对象；文件删除后返回 null 且不抛异常

**操作步骤**：
1. 运行单元测试 `pnpm test rtm-reader.test.ts` 通过
2. readStageRTM 返回含 outputs/traceability/coverage 的对象
3. 文件删除后返回 null 且不抛异常

**预期结果**：按上述步骤执行后满足验收标准：运行单元测试 `pnpm test rtm-reader.test.ts` 通过；readStageRTM 返回含 outputs/traceability/coverage 的对象；文件删除后返回 null 且不抛异常

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-18 · 增强 assembleStageOverview 合并 RTM 追溯数据

**验收内容**：【增强 assembleStageOverview 合并 RTM 追溯数据】验收：运行集成测试 `pnpm test stage-overview-rtm-integration.test.ts` 通过；assembleStageOverview 返回对象含 stages[stage].traceability；traceability.fr_to_design["FR-1"] 含设计章节引用；coverage.design.rate 为 0-1 数字

**操作步骤**：
1. 运行集成测试 `pnpm test stage-overview-rtm-integration.test.ts` 通过
2. assembleStageOverview 返回对象含 stages[stage].traceability
3. traceability.fr_to_design["FR-1"] 含设计章节引用
4. coverage.design.rate 为 0-1 数字

**预期结果**：按上述步骤执行后满足验收标准：运行集成测试 `pnpm test stage-overview-rtm-integration.test.ts` 通过；assembleStageOverview 返回对象含 stages[stage].traceability；traceability.fr_to_design["FR-1"] 含设计章节引用；coverage.design.rate 为 0-1 数字

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-19 · 完整流程端到端测试

**验收内容**：【完整流程端到端测试】验收：运行端到端测试 `pnpm test rtm-e2e.test.ts` 通过；完整流程后 7 个 RTM 文件均生成且格式正确；FR-1 → design#1.1 → t-001 → TC-1 追溯链完整；读取 2 个 RTM 文件耗时 < 5ms

**操作步骤**：
1. 运行端到端测试 `pnpm test rtm-e2e.test.ts` 通过
2. 完整流程后 7 个 RTM 文件均生成且格式正确
3. FR-1 → design#1.1 → t-001 → TC-1 追溯链完整
4. 读取 2 个 RTM 文件耗时 < 5ms

**预期结果**：按上述步骤执行后满足验收标准：运行端到端测试 `pnpm test rtm-e2e.test.ts` 通过；完整流程后 7 个 RTM 文件均生成且格式正确；FR-1 → design#1.1 → t-001 → TC-1 追溯链完整；读取 2 个 RTM 文件耗时 < 5ms

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-20 · 编写 RTM 使用文档和 Dive 模式集成示例

**验收内容**：【编写 RTM 使用文档和 Dive 模式集成示例】验收：创建 agent-dh/docs/guides/rtm-usage.md；文档含 7 个触发点完整说明；含至少 3 个 Dive 模式代码示例；执行 `npx markdownlint docs/guides/rtm-usage.md` 通过

**操作步骤**：
1. 创建 agent-dh/docs/guides/rtm-usage.md
2. 文档含 7 个触发点完整说明
3. 含至少 3 个 Dive 模式代码示例
4. 执行 `npx markdownlint docs/guides/rtm-usage.md` 通过

**预期结果**：按上述步骤执行后满足验收标准：创建 agent-dh/docs/guides/rtm-usage.md；文档含 7 个触发点完整说明；含至少 3 个 Dive 模式代码示例；执行 `npx markdownlint docs/guides/rtm-usage.md` 通过

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-21 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-24 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- docs/requirements/REQ-260926140539-457b/reviews/self-review.md
- docs/requirements/REQ-260926140539-457b/tests/test-evidence.md
- packages/tools/reqboard/src/dive/node-input.ts
- packages/tools/reqboard/src/dive/decision.ts
- packages/tools/reqboard/tests/rtm/dive-integration.test.ts
- npx vitest run packages/tools/reqboard/tests → Test Files 13 passed (13) / Tests 95 passed (95)
- cd packages/tools/reqboard && npx tsc -p tsconfig.json → exit 0
- npx vitest run packages/web/dsh-pmboard/tests → Test Files 41 failed | 136 passed (180) / Tests 197 failed | 1750 passed（与改动前逐一致，零新增回归）
- 离线真实数据门禁读数（同一生成器代码 + .dsh-data/dsh-reqboard.json）：design 100% pass / implementation 100% pass / testing 95% pass；Dive 决策 next_stage=done

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v2-1 | 实现 RTM TypeScript 类型定义 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:44 |
| v2-2 | 实现 RTM 文件读写与版本控制 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:44 |
| v2-3 | 实现 FR/serves/implements/covers 标注解析 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:44 |
| v2-4 | 实现四级追溯映射构建 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:44 |
| v2-5 | 实现三层覆盖度自动计算 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:44 |
| v2-6 | 实现全局生命周期 RTM 生成 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-7 | 实现需求分析节点 RTM 生成 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-8 | 实现设计节点 RTM 生成 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-9 | 实现拆分节点 RTM 生成 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-10 | 实现实施节点 RTM 生成（汇总 + 任务详情目录） | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-11 | 实现验收节点 RTM 生成 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-12 | 在 reqboard_create 触发 rtm-lifecycle.yml 生成 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-13 | 在 reqboard_submit 各类型触发对应 RTM 生成 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-14 | 确认产物后更新 RTM 的 confirmed 状态 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-15 | 任务状态变更时更新 rtm-implementing.yml | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-16 | 子任务汇报时更新任务详情文件的 workflow | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-17 | 实现 StageOverview 的 RTM 读取接口 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-18 | 增强 assembleStageOverview 合并 RTM 追溯数据 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-19 | 完整流程端到端测试 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-20 | 编写 RTM 使用文档和 Dive 模式集成示例 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-21 | 需求级验收 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
| v2-24 | 需求级验收 | ✓ 通过 | human/session-c5ea210f-afc3-4735-a4d1-f9058b378363 | 2026-09-26 21:45 |
