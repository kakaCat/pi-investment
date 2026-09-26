# REQ-260926140539-457b: RTM YAML 追溯基础设施 - Dive 模式自动化的数据底座

## 边界

### 做什么

1. **实现 RTM YAML 文件结构**：每个节点一个 RTM 文件（rtm-lifecycle.yml + 6 个节点 RTM）
2. **生成和更新逻辑**：在需求流程的 7 个关键触发点自动生成/更新 RTM
3. **数据同步机制**：从台账和文档提取数据，保证 RTM 与台账的基础数据一致
4. **追溯关系索引**：解析文档中的 serves/implements/covers 标注，构建四级追溯链
5. **覆盖度统计**：自动计算设计/实施/测试覆盖度
6. **StageOverview 集成**：使会话节点可以读取 RTM 追溯数据

### 不做什么

- **不改变台账结构**：dsh-reqboard.json 保持现有结构，RTM 是增强而非替代
- **不改变文档格式**：requirement.md / design/*.md / tasks/*.md 格式保持不变
- **不记录 workflow 细节**：任务的子阶段执行流程继续放任务卡文档，不进 RTM
- **不实时同步**：RTM 是快照模式（版本号标记），不做实时双向同步
- **不自动合并冲突**：多 Agent 并发修改同一 RTM 时，后写覆盖前写（文件级锁）

### 边界理由

- **轻量级集成**：RTM 作为缓存层，不破坏现有架构
- **性能优先**：快照模式避免实时同步的复杂性，满足 Dive 模式的性能需求（250x 提升）
- **职责分离**：RTM 只记录追溯关系，不替代台账的唯一事实来源地位

---

## 产品定义

### 一句话

为 Dive armed 模式提供"仪表盘"数据，通过 RTM YAML 记录需求流程的节点状态和四级追溯链，使自动化决策从 500ms 加速到 2ms。

### 核心价值

**Dive 模式的性能瓶颈**：
- 现状：每次决策需要读取+解析多个文档（requirement.md + design/*.md + tasks.json），实时构建追溯映射，耗时 ~500ms
- 问题：无法快速感知状态，难以实现快速自动化循环

**RTM YAML 解决方案**：
- 缓存索引：追溯关系预先建好，读取只需 ~1ms
- 状态快照：节点状态、任务进度一目了然
- 覆盖度统计：自动计算设计/实施/测试覆盖度

**性能提升**：250x（500ms → 2ms）

### 使用场景

1. **Dive 模式自动决策**：读取 rtm-lifecycle.yml 和当前节点 RTM，快速判断下一步动作
2. **会话节点追溯展示**：用户点击会话右上角节点 → 追溯 Tab 显示完整追溯链
3. **验收门禁检查**：提交验收材料时，自动检查追溯完整性和覆盖度
4. **需求修改同步**：修改设计文档后，RTM 自动重新生成追溯关系

---

## 用户与角色

### 主要用户

1. **Dive armed 模式**（AI Agent）
   - 需要：快速读取节点状态、追溯关系、覆盖度统计
   - 使用：每次决策循环读取 RTM（~1ms），判断是否可以推进

2. **会话节点前端**（用户查看）
   - 需要：显示需求的完整追溯链和覆盖度
   - 使用：用户点击节点 → StageOverview 读取 RTM → 追溯 Tab 展示

3. **Reqboard 工具**（后端系统）
   - 需要：在需求流程的关键节点生成/更新 RTM
   - 使用：reqboard_submit / reqboard_task_move 等工具触发 RTM 更新

### 使用场景

#### 需求流水线节点流程图（Dive 模式数据来源）

```
┌───────────────────────────────────────────────────────────────────────────┐
│          需求流水线各节点流程 - RTM 数据生成与 Dive 模式决策                 │
│   (draft → brainstorming → design → decomposing → implementing → accepting) │
└───────────────────────────────────────────────────────────────────────────┘


节点零：draft（立项）
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 立项（reqboard_create）
      │
      ├─→ 创建需求记录：
      │      requirement_id: REQ-260926140539-457b
      │      title: "RTM YAML 追溯基础设施"
      │      category: feature
      │      status: draft
      │
      ├─→ 生成 rtm-lifecycle.yml：
      │      lifecycle:
      │         current_stage: draft
      │         stages:
      │            draft: { status: in_progress }
      │            brainstorming: { status: pending }
      │            design: { status: pending }
      │            decomposing: { status: pending }
      │            implementing: { status: pending }
      │            accepting: { status: pending }
      │            done: { status: pending }
      │
      ├─→ 绑定窗口：
      │      本窗口绑定该需求（bound: true）
      │
      └─→ 阶段1 完成标志：
             • reqboard_create 调用成功
             • rtm-lifecycle.yml 已生成到 docs/requirements/REQ-xxx/
             • 需求状态：draft
             • 窗口绑定状态：bound = true
             • 可在看板"draft"泳道看到该需求
             ↓
   [阶段2] Dive 自动化准备
      │
      ├─→ 压缩上下文（调用压缩工具）：
      │      • 压缩历史对话上下文
      │      • 保留关键信息（用户意图、立项原因）
      │      • 释放 token 空间（为后续节点留空间）
      │
      ├─→ 注入阶段提示词：
      │      • brainstorming 阶段提示词（需求分析纪律）
      │      • requirement.md 模板链接
      │      • 轻档清单（L1-L5）
      │      • G2 条款定义规则（FR-N 格式）
      │
      └─→ 读取 rtm-lifecycle.yml：
             • current_stage: draft
             • 下一步: brainstorming
             
      阶段2 完成标志：
         • 上下文已压缩（历史对话 token 减少）
         • brainstorming 阶段提示词已注入
         • requirement.md 模板已注入
         • 轻档清单已注入
         • RTM 数据已读取（current_stage: draft）
         • Dive 模式准备就绪，可以开始讨论
             ↓
   [阶段3] Dive 自动开始讨论
      │
      ├─→ AI 自动发起需求讨论：
      │      "我们来讨论一下这个需求的边界和功能点..."
      │      （基于注入的提示词，引导用户明确需求）
      │
      ├─→ 与用户交互（多轮对话）：
      │      • 确定边界（做什么、不做什么）
      │      • 明确产品定义（一句话目标）
      │      • 定义用户与角色
      │      • 列举功能点（FR-1, FR-2, ...）
      │
      └─→ 讨论完成，编写需求文档：
             • 写入 docs/requirements/REQ-xxx/requirement.md
             • 调用 reqboard_submit(kind=requirement)
             • 进入 brainstorming 阶段的"生成 RTM"流程
             
      阶段3 完成标志：
         • AI 已发起需求讨论
         • 与用户完成多轮对话
         • 边界、产品定义、用户角色、功能点已明确
         • requirement.md 已编写完成
         • reqboard_submit(kind=requirement) 调用成功
         • 需求进入 brainstorming 阶段


节点一：brainstorming（需求分析）
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 编写需求文档
      │
      ├─→ 编写 requirement.md：
      │      定义边界、产品定义、用户与角色、功能点
      │      编写 FR-1, FR-2, FR-3, ...
      │
      └─→ 提交：reqboard_submit(kind=requirement)
             
      阶段1 完成标志：
         • requirement.md 已编写并提交
         • reqboard_submit 调用成功
         • 文档通过 G2 门禁（FR 格式、必填节检查）
             ↓
   [阶段2] 生成 RTM（门禁通过后）
      │
      ├─→ 生成 rtm-brainstorming.yml：
      │      • 解析 requirement.md 提取 FR 列表
      │      • 初始化 fr_to_design 空映射
      │      outputs:
      │         requirements:
      │            - { id: FR-1, title: "...", source: "requirement.md#120" }
      │            - { id: FR-2, title: "...", source: "requirement.md#145" }
      │
      └─→ 等待确认：reqboard_ask_confirm(kind=requirement)
             
      阶段2 完成标志：
         • rtm-brainstorming.yml 已生成
         • FR 列表已提取（FR-1, FR-2, ...）
         • fr_to_design 空映射已初始化
         • 产物已登记到 artifacts[]
             ↓
   [阶段3] Dive 模式检查（确认后）
      │
      ├─→ 读取 rtm-brainstorming.yml (~1ms)
      │
      ├─→ 检查：artifacts[0].confirmed ?
      │      ├─ YES → ✅ 需求已确认，可以推进到 design
      │      └─ NO (用户提出异议) → 🔄 进入反馈循环
      │
      └─→ Dive 决策输出：
             IF confirmed:
                "需求已确认，识别到 5 个功能点（FR-1 到 FR-5），
                 设计覆盖度目标 100%，准备进入 design 阶段"
             ELSE (用户提出异议，反馈循环):
                ┌─ 读取用户异议（user_feedback）
                ├─ 针对异议进行讨论："我理解您的疑虑，关于XXX..."
                ├─ 返回到讨论阶段（draft 阶段3）
                ├─ 与用户重新讨论需求
                ├─ 修改 requirement.md
                ├─ 重新提交：reqboard_submit(kind=requirement)
                ├─ 再次校验：G2 门禁检查（FR 格式、必填节）
                ├─ 更新 rtm-brainstorming.yml：
                │      • 重新提取 FR 列表（可能新增/删除/修改 FR）
                │      • 更新 outputs.requirements
                │      • 增加 metadata.version（版本 +1）
                └─ 再次等待确认（形成反馈循环）
             ↓
   [阶段4] Dive 自动化准备（确认后推进到 design）
      │
      ├─→ 压缩上下文：
      │      • 压缩 brainstorming 阶段的对话历史
      │      • 保留需求文档内容（FR 列表、边界）
      │
      ├─→ 注入阶段提示词：
      │      • design 阶段提示词（设计纪律）
      │      • design/*.md 模板链接（architecture/data-model/interfaces）
      │      • serves: FR-1, FR-2 标注规则
      │
      ├─→ 注入 RTM 数据（节点输入包）：
      │      • requirements: [FR-1, FR-2, ...] ← 从 rtm-brainstorming.yml
      │      • 需求摘要、边界
      │
      └─→ Dive 自动开始设计：
             "基于以下需求，我们来设计技术方案..."
             下一步：编写设计文档


节点二：design（设计）
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 编写设计文档
      │
      ├─→ 编写 design/*.md：
      │      architecture.md, data-model.md, interfaces.md, ...
      │      每个章节标注 serves: FR-1, FR-2
      │
      └─→ 提交：reqboard_submit(kind=design)
             
      阶段1 完成标志：
         • design/*.md 已编写并提交
         • 每个章节已标注 serves: FR-N
         • reqboard_submit 调用成功
             ↓
   [阶段2] 校验与生成 RTM（门禁检查）
      │
      ├─→ 校验设计文档：
      │      • 扫描 design/*.md 提取章节
      │      • 解析 serves: FR-1, FR-2 标注
      │      • 构建 fr_to_design 映射
      │      • 计算设计覆盖度
      │
      ├─→ 门禁检查（coverage.design.rate）：
      │      IF coverage.design.rate = 100%:
      │         ✅ 通过门禁，继续生成 RTM
      │      ELSE:
      │         🚫 拒绝提交，返回错误：
      │            "设计覆盖度不足 (X/Y)，缺少以下 FR 的设计：
      │             - FR-3: xxx
      │             - FR-5: xxx
      │            请补充这些 FR 的设计后重新提交"
      │         → 返回阶段1（补充设计）
      │
      ├─→ 生成 rtm-design.yml（仅在门禁通过后）：
      │      outputs:
      │         design_sections:
      │            - { ref: "design/arch#1.1", title: "...", serves: [FR-1] }
      │      traceability:
      │         fr_to_design:
      │            FR-1: ["design/arch#1.1", "design/arch#1.2"]
      │            FR-2: ["design/data#2.1"]
      │      coverage:
      │         design:
      │            total_frs: 5
      │            covered_frs: 5
      │            uncovered: []
      │            rate: 100%
      │
      └─→ 等待确认：reqboard_ask_confirm(kind=design)
             
      阶段2 完成标志：
         • 设计覆盖度门禁通过（100%）
         • rtm-design.yml 已生成
         • design_sections 已提取
         • fr_to_design 映射已构建
             ↓
   [阶段3] Dive 模式检查（确认后）
      │
      ├─→ 读取 rtm-design.yml (~1ms)
      │      • coverage.design.rate 必然是 100%（阶段2门禁保证）
      │
      ├─→ 检查：设计是否已确认？
      │      ├─ YES (用户确认) → ✅ 可以进入拆分
      │      └─ NO (用户提出异议) → 🔄 进入反馈循环
      │             ┌─ 读取用户异议（user_feedback）
      │             ├─ 针对异议讨论："关于架构设计，您提到..."
      │             ├─ 修改 design/*.md
      │             ├─ 重新提交：reqboard_submit(kind=design)
      │             ├─ 再次校验 + 门禁检查（阶段2）
      │             ├─ 更新 rtm-design.yml（version +1）
      │             └─ 再次等待确认（形成反馈循环）
      │
      └─→ Dive 决策输出：
              IF confirmed:
                 "设计覆盖度 100% (5/5)，所有 FR 都有设计，准备进入拆分"
              ELSE (用户提出异议，反馈循环):
                 ┌─ 读取用户异议（user_feedback）
                 ├─ 针对异议讨论："关于设计方案，您提到..."
                 ├─ 修改 design/*.md
                 ├─ 重新提交：reqboard_submit(kind=design)
                 ├─ 再次校验 + 门禁检查（阶段2）
                 ├─ 更新 rtm-design.yml：
                 │      • 重新提取 design_sections（可能新增/删除章节）
                 │      • 重新构建 fr_to_design 映射
                 │      • 重新计算设计覆盖度
                 │      • 增加 metadata.version（版本 +1）
                 └─ 再次等待确认（形成反馈循环）
             ↓
   [阶段4] Dive 自动化准备（确认后推进到 decomposing）
      │
      ├─→ 压缩上下文：
      │      • 压缩 design 阶段的对话历史
      │      • 保留设计文档内容（架构、接口、数据模型）
      │
      ├─→ 注入阶段提示词：
      │      • decomposing 阶段提示词（拆分纪律）
      │      • decomposition.md 模板链接
      │      • 任务粒度规则、depends_on 规则
      │
      ├─→ 注入 RTM 数据（节点输入包，压缩模式）：
      │      • requirements: [FR-1, FR-2, ...] 
      │      • design_sections: [design/arch#1.1, ...]
      │      • fr_to_design 映射
      │      • 设计覆盖度：100%
      │
      └─→ Dive 自动开始拆分：
             "基于设计方案，我们来拆分任务..."
             下一步：编写拆分计划


节点三：decomposing（拆分）
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 编写拆分计划
      │
      ├─→ 编写 decomposition.md：
      │      定义任务列表（key / title / phase / side / depends_on）
      │      每个任务标注 implements: design/arch#1.1
      │      每个任务标注 serves: FR-1
      │
      └─→ 提交：reqboard_submit(kind=plan)
             
      阶段1 完成标志：
         • decomposition.md 已编写并提交
         • 任务列表已定义（key/title/phase/side/depends_on）
         • 每个任务已标注 implements 和 serves
         • reqboard_submit 调用成功
             ↓
   [阶段2] 校验与生成 RTM（批准计划 + 门禁检查）
      │
      ├─→ 校验拆分计划：
      │      • 从任务台账提取 design_serves 字段
      │      • 构建 design_to_tasks 映射
      │      • 计算实施覆盖度
      │
      ├─→ 门禁检查（coverage.implementation.rate）：
      │      IF coverage.implementation.rate = 100%:
      │         ✅ 通过门禁，可以批准计划
      │      ELSE:
      │         🚫 拒绝批准，返回错误：
      │            "实施覆盖度不足 (X/Y)，以下设计章节缺少任务：
      │             - design/arch#2.3
      │            请补充任务覆盖这些设计后重新提交"
      │         → 返回阶段1（补充任务）
      │
      ├─→ 批准计划：reqboard_ask_confirm(target=plan)
      │      （仅在门禁通过后才能批准）
      │
      ├─→ 生成 rtm-decomposing.yml（仅在批准后）：
      │      outputs:
      │         tasks:
      │            - id: t-354ea0
      │              title: "实现 RTM 文件结构"
      │              implements: "design/arch#1.1"
      │              serves: [FR-1, FR-2]           ← 覆盖的需求点
      │              depends_on: []                 ← 任务依赖（DAG）
      │              phase: fullstack               ← 任务类型
      │              side: backend                  ← 前端/后端
      │            - id: t-abc123
      │              title: "实现 RTM 生成逻辑"
      │              implements: "design/arch#1.2"
      │              serves: [FR-2, FR-3]
      │              depends_on: [t-354ea0]         ← 依赖 t-354ea0
      │              phase: implement
      │              side: backend
      │      traceability:
      │         design_to_tasks:
      │            "design/arch#1.1": [t-354ea0]
      │            "design/arch#1.2": [t-abc123]
      │         fr_to_tasks:                       ← 需求点到任务的映射
      │            FR-1: [t-354ea0]
      │            FR-2: [t-354ea0, t-abc123]
      │            FR-3: [t-abc123]
      │      coverage:
      │         implementation:
      │            total_designs: 4
      │            covered_designs: 4
      │            uncovered: []
      │            rate: 100%
      │
      └─→ 同时生成 rtm-implementing 完整文件结构：
             • rtm-implementing.yml（汇总文件，初始统计）
             • rtm-implementing/ 目录
             • 为每个任务创建骨架文件：rtm-implementing/t-xxx.yml
               - 初始状态：todo
               - 初始 workflow：根据任务的 phase 字段决定需要哪些子阶段
                 * phase=implement → 只有 implement 阶段
                 * phase=doc → doc + implement + test + commit
                 * phase=ui → ui + implement + test + commit
                 * phase=test → test 阶段
                 * 完整任务：doc → ui → analysis → implement → test → review → commit
               - workflow_params：从任务定义中提取
                 * REQ_ID / TASK_ID / TASK_TITLE
                 * DESIGN_FILES (从 implements 推断)
                 * TEST_PATTERN (从任务标题推断)
                 * SIDE (从 side 字段获取：frontend/backend/fullstack/doc)
                 * PHASE (从 phase 字段获取：决定子阶段范围)
             
      阶段2 完成标志：
         • 实施覆盖度门禁通过（100%）
         • 计划已批准
         • rtm-decomposing.yml 已生成
         • design_to_tasks 映射已构建
         • rtm-implementing.yml 骨架已生成
         • 任务已落库（reqboard_decompose）
             ↓
   [阶段3] Dive 模式检查（批准后）
      │
      ├─→ 读取 rtm-decomposing.yml (~1ms)
      │      • coverage.implementation.rate 必然是 100%（阶段2门禁保证）
      │
      ├─→ 检查：拆分计划是否已批准？
      │      ├─ YES (用户批准) → ✅ 可以开工
      │      └─ NO (用户提出异议) → 🔄 进入反馈循环
      │             ┌─ 读取用户异议（user_feedback）
      │             ├─ 针对异议讨论："关于任务拆分，您提到..."
      │             ├─ 修改 decomposition.md
      │             ├─ 重新提交：reqboard_submit(kind=plan)
      │             ├─ 再次校验 + 门禁检查（阶段2）
      │             ├─ 更新 rtm-decomposing.yml（version +1）
      │             └─ 再次等待批准（形成反馈循环）
      │
      └─→ Dive 决策输出：
              IF approved:
                 "实施覆盖度 100% (4/4)，所有设计都有任务，准备开工"
              ELSE (用户提出异议，反馈循环):
                 ┌─ 读取用户异议（user_feedback）
                 ├─ 针对异议讨论："关于任务拆分，您提到..."
                 ├─ 修改 decomposition.md
                 ├─ 重新提交：reqboard_submit(kind=plan)
                 ├─ 再次校验 + 门禁检查（阶段2）
                 ├─ 更新 rtm-decomposing.yml：
                 │      • 重新提取 tasks（可能新增/删除任务）
                 │      • 重新构建 design_to_tasks 映射
                 │      • 重新计算实施覆盖度
                 │      • 增加 metadata.version（版本 +1）
                 └─ 再次等待批准（形成反馈循环）
             ↓
   [阶段4] Dive 自动化准备（批准后推进到 implementing）
      │
      ├─→ 准备子阶段调度数据：
      │      • rtm-implementing.yml 已生成（汇总文件）
      │      • rtm-implementing/*.yml 已生成（任务文件，含 workflow_params）
      │      • 每个任务的 workflow 定义已在任务文件中（根据 phase 字段）
      │      • Dive 将在 implementing 阶段构建子阶段图：
      │        - 每个任务的每个子阶段都是一个节点
      │        - 计算双层依赖（任务依赖 + 子阶段依赖）
      │        - 波次调度：每波启动所有入度为0的子阶段
      │
      ├─→ 压缩上下文：
      │      • 压缩 decomposing 阶段的对话历史
      │      • 保留拆分计划（任务列表、依赖关系）
      │
      ├─→ 注入阶段提示词：
      │      • implementing 阶段提示词（实施纪律）
      │      • Subagent 并行执行规范
      │      • 子任务执行规范（doc → ui → analysis → implement → test → review → commit）
      │      • 汇报格式（reqboard_task_report）
      │
      ├─→ 注入 RTM 数据（节点输入包，压缩模式）：
      │      • tasks: [t-354ea0, t-abc123, ...] ← 从 rtm-decomposing.yml
      │      • design_to_tasks 映射
      │      • 实施覆盖度：100%
      │      • 任务状态：tasks_todo: 5
      │
      └─→ Dive 自动开始执行：
节点四：implementing（实施）★ 核心节点
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 基于 DSH Agent Teams 的任务执行（零实现成本）
      │
      ├─→ Dive (Team Lead) 初始化：
      │      1. 创建 Worker Agents（持久化）：
      │         spawn_teammate({
      │           name: "worker-1",
      │           description: "任务执行者1",
      │           prompt: "你是任务执行 Worker，负责执行子阶段任务...",
      │           context: "fresh"
      │         })
      │         spawn_teammate({ name: "worker-2", ... })
      │         spawn_teammate({ name: "worker-3", ... })
      │      
      │      2. 读取所有任务及其 workflow：
      │         const summary = readYAML('rtm-implementing.yml');
      │         const allTasks = summary.tasks;
      │      
      │      3. 为每个子阶段创建共享任务（team_task_create）：
      │         FOR EACH task in allTasks:
      │           FOR EACH phase in task.workflow:
      │             team_task_create({
      │               subject: "${task.id}-${phase}",
      │               description: "执行任务 ${task.title} 的 ${phase} 阶段",
      │               blocked_by: calculateDependencies(task, phase),
      │               write_scopes: ["${task.files}"]
      │             })
      │      
      │         依赖计算（DSH 原生支持 DAG）：
      │         - T1-doc: blocked_by = []（立即 ready）
      │         - T1-implement: blocked_by = ["T1-doc"]（等 T1-doc）
      │         - T2-doc: blocked_by = []（立即 ready）
      │         - T3-doc: blocked_by = ["T1-commit"]（等 T1 完成）
      │      
      │      4. 启动 Worker 循环（每个 Worker 独立运行）：
      │         send_message("worker-1", "开始执行任务循环")
      │         send_message("worker-2", "开始执行任务循环")
      │         send_message("worker-3", "开始执行任务循环")
      │
      ├─→ Worker Agent 的工作循环（自动负载均衡）：
      │      LOOP:
      │         1. 列出所有 ready 任务（DSH 自动计算）：
      │            tasks = team_task_list({ 
      │              status: "pending",
      │              ready: true  ← DSH 自动过滤依赖已满足的任务
      │            })
      │         
      │         2. Claim 第一个 ready 任务（先到先得）：
      │            task = tasks[0]
      │            team_task_update({
      │              task_id: task.id,
      │              expected_revision: task.revision,
      │              action: "claim"  ← CAS 操作，防冲突
      │            })
      │         
      │         3. 执行任务：
      │            executeSubphase(task)
      │            // 例如：T1-doc
      │            // - 读取 rtm-implementing/t-001.yml
      │            // - 编写任务文档
      │            // - 调用 reqboard_task_report
      │         
      │         4. 完成任务：
      │            team_task_update({
      │              task_id: task.id,
      │              expected_revision: task.revision,
      │              action: "complete"
      │            })
      │            // DSH 自动解锁依赖它的任务（blocked_by）
      │         
      │         5. 继续循环，直到没有 ready 任务
      │
      ├─→ Dive (Team Lead) 的监控（事件驱动，零轮询）：
      │      LOOP:
      │         1. 等待任务变化（阻塞，零成本）：
      │            result = wait_agent({ timeout: 300000 }) // 5分钟
      │         
      │         2. 有变化时，检查状态：
      │            agents = list_agents()
      │            tasks = team_task_list()
      │            
      │            // 统计进度
      │            total = tasks.length
      │            completed = tasks.filter(t => t.status === 'completed').length
      │            console.log(`进度：${completed}/${total}`)
      │         
      │         3. 假死检测（5分钟心跳）：
      │            FOR EACH agent in agents:
      │              IF agent.status === 'running' && agent.idle_time > 30min:
      │                interrupt_agent(agent.name)
      │                send_message(agent.name, "重新开始任务循环")
      │         
      │         4. 所有任务完成 → 退出循环
      │
      ├─→ 架构示意：
      │      
      │      ┌────────────────────────────────────────────────────┐
      │      │  Dive (Team Lead)                                  │
      │      │  • 创建 Worker Agents                              │
      │      │  • 创建共享任务（team_task）                       │
      │      │  • 监控进度（wait_agent）                          │
      │      │  • 假死检测（5分钟心跳）                           │
      │      └────────────────────────────────────────────────────┘
      │               ↓ spawn_teammate
      │      ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
      │      │ Worker-1    │  │ Worker-2    │  │ Worker-3    │
      │      │ (持久)      │  │ (持久)      │  │ (持久)      │
      │      │             │  │             │  │             │
      │      │ 循环：      │  │ 循环：      │  │ 循环：      │
      │      │ 1.list ready│  │ 1.list ready│  │ 1.list ready│
      │      │ 2.claim任务 │  │ 2.claim任务 │  │ 2.claim任务 │
      │      │ 3.执行      │  │ 3.执行      │  │ 3.执行      │
      │      │ 4.complete  │  │ 4.complete  │  │ 4.complete  │
      │      │             │  │             │  │             │
      │      │ T1-doc ✓    │  │ T2-doc ✓    │  │ T4-doc ✓    │
      │      │ T1-impl ✓   │  │ T2-impl ✓   │  │ T4-impl ✓   │
      │      │ T1-test ... │  │ T2-test ... │  │ T7-doc ...  │
      │      └─────────────┘  └─────────────┘  └─────────────┘
      │               ↓ complete task
      │      ┌────────────────────────────────────────────────────┐
      │      │  Shared Task Board (DSH 管理)                      │
      │      │  • T1-doc (completed)                              │
      │      │  • T1-implement (in_progress) ← Worker-1           │
      │      │  • T2-doc (completed)                              │
      │      │  • T2-implement (in_progress) ← Worker-2           │
      │      │  • T3-doc (pending, blocked_by: [T1-commit])       │
      │      │  • ...                                             │
      │      │                                                    │
      │      │  DSH 自动：                                        │
      │      │  • 计算 ready 状态（依赖已满足）                  │
      │      │  • CAS 更新（防并发冲突）                          │
      │      │  • 依赖解锁（complete → 解锁 blocked_by）         │
      │      └────────────────────────────────────────────────────┘
      │
      └─→ 关键优势：
             • **零 DAG 实现成本**：DSH 原生支持 blocked_by
             • **自动负载均衡**：Worker 先到先得
             • **零轮询成本**：wait_agent 事件驱动
             • **CAS 防冲突**：team_task_update 原子操作
             • **持久化 Worker**：可以连续执行多个任务
             • **共享文件系统**：所有 agent 共享工作目录
   [阶段2] 更新 RTM（每次任务状态变更）
      │
      ├─→ 文件结构（已在 decomposing 阶段2 生成）：
      │      rtm-implementing.yml           ← 汇总文件（轻量，只有统计）
      │      rtm-implementing/             ← 任务详情目录
      │         ├─ t-354ea0.yml            ← 单个任务的详情 + workflow
      │         ├─ t-abc123.yml
      │         └─ t-def456.yml
      │
      ├─→ 更新汇总文件（rtm-implementing.yml）：
      │      • 重新统计 tasks_done / tasks_in_progress / tasks_todo
      │      • 只保留任务 id 列表和统计信息（不含详情）
      │      status:
      │         tasks_total: 5
      │         tasks_done: 2
      │         tasks_in_progress: 2
      │         tasks_todo: 1
      │      tasks:
      │         - { id: t-354ea0, status: in_progress }
      │         - { id: t-abc123, status: in_progress }
      │         - { id: t-def456, status: done }
      │         - { id: t-789012, status: todo }
      │         - { id: t-345678, status: todo }
      │
      ├─→ 更新单个任务文件（rtm-implementing/t-354ea0.yml）：
      │      • 只更新变化的那个任务文件（不影响其他任务）
      │      task:
      │         id: t-354ea0
      │         title: "实现 RTM 文件结构"
      │         status: in_progress
      │         implements: "design/arch#1.1"
      │         serves: [FR-1]
      │         workflow_total: 7  ← 固定7个子任务阶段
      │         workflow_done: 3   ← 已完成3个
      │         workflow:
      │            - { phase: doc, status: done, completed_at: "2024-01-01T10:00:00Z" }
      │            - { phase: ui, status: done, completed_at: "2024-01-01T11:00:00Z" }
      │            - { phase: analysis, status: done, completed_at: "2024-01-01T12:00:00Z" }
      │            - { phase: implement, status: in_progress, started_at: "2024-01-01T13:00:00Z" }
      │            - { phase: test, status: pending }
      │            - { phase: review, status: pending }
      │            - { phase: commit, status: pending }
      │
      └─→ 优势：
             • 更新快：只写单个任务文件（~1KB）而不是整个汇总（~50KB）
             • 读取快：Dive 模式只需读取汇总文件（~5KB）获取统计
             • 按需读取：需要任务详情时再读取单个任务文件
             • 并发安全：多个任务可以并发更新（不同文件）
             
      阶段2 完成标志：
         • rtm-implementing.yml 汇总文件已更新（统计信息）
         • rtm-implementing/t-xxx.yml 任务文件已更新（详情 + workflow）
         • tasks_done / tasks_in_progress / tasks_todo 统计已更新
             ↓
   [阶段3] Dive 监控（基于 Agent Teams，零成本）
      │
      ├─→ 主循环：wait_agent 事件驱动（DSH 原生支持）
      │      LOOP:
      │         1. 等待 Agent 或任务变化（阻塞，零成本）：
      │            result = wait_agent({ timeout: 300000 }) // 5分钟
      │            
      │            返回值：
      │            • timedOut: false → 有变化（任务完成/agent状态变化）
      │            • timedOut: true → 5分钟超时（心跳检测）
      │         
      │         2. 有变化时，检查进度：
      │            agents = list_agents()
      │            tasks = team_task_list()
      │            
      │            进度统计：
      │            • total = tasks.length
      │            • completed = tasks.filter(t => t.status === 'completed').length
      │            • in_progress = tasks.filter(t => t.status === 'in_progress').length
      │            • ready = tasks.filter(t => t.status === 'pending' && t.ready).length
      │            
      │            console.log(`进度：${completed}/${total} 完成，${in_progress} 进行中，${ready} 就绪`)
      │         
      │         3. 超时时（5分钟心跳检测）：
      │            假死检测：
      │            FOR EACH agent in agents:
      │              // 检查 agent 是否卡住
      │              IF agent.status === 'running':
      │                // 检查该 agent 的任务
      │                myTasks = team_task_list({ owner: agent.name })
      │                runningTask = myTasks.find(t => t.status === 'in_progress')
      │                
      │                IF runningTask && 任务运行时间 > 30分钟:
      │                  console.warn(`假死：${agent.name} 的任务 ${runningTask.subject}`)
      │                  
      │                  // 中断并重启
      │                  interrupt_agent(agent.name)
      │                  
      │                  // 释放任务
      │                  team_task_update({
      │                    task_id: runningTask.id,
      │                    action: "release"  ← 释放回 pending
      │                  })
      │                  
      │                  // 重新启动 agent
      │                  send_message(agent.name, "重新开始任务循环")
      │         
      │         4. 所有任务完成 → 退出循环：
      │            IF completed === total:
      │              console.log('🎉 所有子阶段完成')
      │              BREAK
      │
      ├─→ DSH Agent Teams 的优势（零实现成本）：
      │      • **wait_agent**：原生事件驱动，零轮询
      │      • **blocked_by**：原生 DAG 支持，自动计算 ready
      │      • **CAS 更新**：防并发冲突（expected_revision）
      │      • **任务释放**：release 操作，假死恢复简单
      │      • **共享任务板**：所有 agent 看到同一个任务列表
      │
      ├─→ Dive 的介入能力（完全掌控）：
      │      • 每个任务完成后，Dive 可以：
      │        - 检查结果质量（通过 RTM）
      │        - 决定是否继续或暂停流程
      │        - 向 Worker 发送调整指令（send_message）
      │      • 发现问题时：
      │        - 暂停所有 Worker：interrupt_agent(...)
      │        - 修改任务：team_task_update(action: "edit")
      │        - 重新启动：send_message(...)
      │
      └─→ 性能与成本：
             • **事件驱动**：wait_agent 阻塞等待，零轮询成本
             • **心跳检测**：12次/小时（5分钟超时）
             • **读取成本**：
               - 每次心跳：list_agents + team_task_list ≈ 2000 tokens
               - 12次/小时 × 2000 = 24,000 tokens/小时
             • **对比持续轮询**：降低 98%（1,440,000 → 24,000）
             • **Dive 可用性**：95%+（只在处理事件时占用）
             
      阶段3 完成标志：
         • 所有共享任务都已 completed
         • Dive 收到最后一个任务完成事件
         • team_task_list 显示 100% 完成
   [阶段4] Dive 自动化准备（所有任务完成后推进到 accepting）
      │
      ├─→ 压缩上下文：
      │      • 压缩 implementing 阶段的对话历史
      │      • 保留任务汇报、关键决策
      │
      ├─→ 注入阶段提示词：
      │      • accepting 阶段提示词（验收纪律）
      │      • 测试文档模板链接
      │      • covers: t-xxx 标注规则
      │
      ├─→ 注入 RTM 数据（节点输入包）：
      │      • tasks: [t-354ea0, ...] ← 所有已完成任务
      │      • task_details: 每个任务的 workflow 执行记录
      │
      └─→ Dive 自动开始验收：
             "所有任务已完成，开始编写验收材料..."
             下一步：编写测试用例


节点五：accepting（验收）
═══════════════════════════════════════════════════════════════════════════
   [阶段1] 编写测试文档
      │
      ├─→ 编写测试用例：
      │      test-cases.md 或 tasks/*/test.md
      │      每个测试用例标注 covers: t-354ea0
      │      每个测试用例标注 validates: FR-1
      │
      └─→ 提交：reqboard_submit(kind=verification)
             
      阶段1 完成标志：
         • 测试用例已编写
         • 每个测试用例已标注 covers: t-xxx
         • reqboard_submit 调用成功
             ↓
   [阶段2] 校验与生成 RTM（门禁检查）
      │
      ├─→ 校验测试文档：
      │      • 扫描测试文档提取 covers 标注
      │      • 构建 task_to_tests 映射
      │      • 计算测试覆盖度
      │
      ├─→ 门禁检查（coverage.testing.rate）：
      │      IF coverage.testing.rate >= 80%:
      │         ✅ 通过门禁，可以提交验收
      │      ELSE:
      │         🚫 拒绝提交，返回错误：
      │            "测试覆盖度不足 (X%)，以下任务缺少测试用例：
      │             - t-f0e25a
      │             - t-d29db5
      │             - t-88a3c1
      │            请补充测试用例使覆盖度达到 ≥80% 后重新提交"
      │         → 返回阶段1（补充测试用例）
      │
      ├─→ 生成 rtm-accepting.yml（仅在门禁通过后）：
      │      outputs:
      │         test_cases:
      │            - { id: TC-1, title: "...", covers: [t-354ea0], validates: [FR-1] }
      │      traceability:
      │         task_to_tests:
      │            t-354ea0: [TC-1, TC-2]
      │            t-abc123: [TC-3]
      │            t-f0e25a: [TC-4, TC-5]
      │      coverage:
      │         testing:
      │            total_tasks: 5
      │            tested_tasks: 5
      │            untested: []
      │            rate: 100%
      │
      └─→ 等待人工审核
             
      阶段2 完成标志：
         • 测试覆盖度门禁通过（≥80%）
         • rtm-accepting.yml 已生成
         • test_cases 已提取
         • task_to_tests 映射已构建
         • 验收材料已提交，等待人工审核
             ↓
   [阶段3] Dive 模式检查（提交验收材料时）
      │
      ├─→ 读取 rtm-accepting.yml (~1ms)
      │      • coverage.testing.rate 必然 >= 80%（阶段2门禁保证）
      │
      ├─→ 检查：验收是否通过？
      │      ├─ YES (人工审核通过) → ✅ 可以归档
      │      └─ NO (人工审核未通过，返工) → 🔄 进入反馈循环
      │             ┌─ 读取验收返工意见（user_feedback）
      │             ├─ 针对意见修改代码/文档
      │             ├─ 补充测试用例
      │             ├─ 重新提交：reqboard_submit(kind=verification)
      │             ├─ 再次校验 + 门禁检查（阶段2）
      │             ├─ 更新 rtm-accepting.yml（version +1）
      │             └─ 再次等待验收（形成反馈循环）
      │
      └─→ Dive 决策输出：
              IF 人工审核通过:
                 "验收通过，测试覆盖度 100% (5/5)，所有任务已完成且测试充分，准备归档"
              ELSE (返工，反馈循环):
                 ┌─ 读取验收返工意见（user_feedback）
                 ├─ 针对意见修改代码/文档
                 ├─ 补充测试用例
                 ├─ 重新提交：reqboard_submit(kind=verification)
                 ├─ 再次校验 + 门禁检查（阶段2）
                 ├─ 更新 rtm-accepting.yml：
                 │      • 重新提取 test_cases（可能新增测试）
                 │      • 重新构建 task_to_tests 映射
                 │      • 重新计算测试覆盖度
                 │      • 增加 metadata.version（版本 +1）
                 └─ 再次等待验收（形成反馈循环）
             ↓
   [阶段4] Dive 自动化准备（验收通过后推进到 done）
      │
      ├─→ 压缩上下文：
      │      • 压缩 accepting 阶段的对话历史
      │      • 保留验收材料、测试结果
      │
      ├─→ 注入阶段提示词：
      │      • done 阶段提示词（归档纪律）
      │      • 归档材料清单规则
      │      • 合并去向规则（按需求类型）
      │
      ├─→ 注入 RTM 数据（节点输入包）：
      │      • 完整追溯链：FR → 设计 → 任务 → 测试
      │      • 覆盖度统计：设计 100%、实施 100%、测试 80%
      │      • 所有文档路径
      │
      └─→ Dive 自动开始归档：
             "验收通过，开始准备归档材料..."
             下一步：编写归档材料


═══════════════════════════════════════════════════════════════════════════
性能对比：

传统方式（实时解析）：
   [启动] → 读取 requirement.md (50ms)
         → 读取 design/*.md (100ms)
         → 读取 tasks.json (50ms)
         → 解析 FR 列表 (100ms)
         → 构建追溯映射 (200ms)
         → 计算覆盖度 (50ms)
         → 总耗时：~550ms

RTM 方式（预构建索引）：
   [启动] → 读取 rtm-lifecycle.yml (1ms)
         → 读取 rtm-implementing.yml (1ms)
         → 总耗时：~2ms

性能提升：275x (550ms → 2ms)

═══════════════════════════════════════════════════════════════════════════
Dive 模式的核心价值：

1. 快速感知：2ms 内获取当前节点完整状态
2. 精准决策：基于覆盖度统计和追溯映射做判断
3. 细粒度追踪：implementing 节点可以看到子任务 workflow 卡在哪里
4. 自动化闭环：无需人工介入，Dive 模式自动推进流程

```

#### 场景1：Dive 模式自动推进

```
Dive 模式循环检查
  ↓
读取 rtm-lifecycle.yml（~1ms）
  current_stage: design
  ↓
读取 rtm-design.yml（~1ms）
  coverage.design.rate: 67%
  uncovered: [FR-3]
  ↓
决策：还有 1 个 FR 缺少设计，继续设计
```

#### 场景2：会话节点追溯展示

```
用户点击 implementing 节点
  ↓
StageOverview 读取 rtm-implementing.yml
  ↓
追溯 Tab 显示：
  - FR-1 → design/arch#1.1 → t-354ea0 → TC-1
  - FR-2 → design/arch#2 → t-f0e25a → (无测试)
  - 覆盖度：设计 100%，实施 100%，测试 50%
```

#### 场景3：验收门禁检查

```
reqboard_submit(kind=verification)
  ↓
读取 rtm-implementing.yml
  coverage.testing.rate: 50%
  ↓
门禁拒绝：测试覆盖度不足 80%
返回：uncovered: [t-f0e25a, t-d29db5, ...]
```

---

## 跨节点反馈循环流程图

当用户在某个节点提出异议时，可能涉及**跨节点的反馈循环**（需要回到上游节点修改）：

```
┌───────────────────────────────────────────────────────────────────────────┐
│              跨节点反馈循环 - 每个节点的更新影响范围                          │
└───────────────────────────────────────────────────────────────────────────┘


场景1：design 阶段发现需求有问题
═══════════════════════════════════════════════════════════════════════════
   [当前] design 阶段
      │
      ├─→ 用户反馈："这个 FR-3 的需求定义不清楚，需要重新讨论"
      │
      └─→ Dive 判断：这是需求问题，不是设计问题
             ↓
   [回退] brainstorming 阶段
      │
      ├─→ 返回讨论阶段（draft 阶段3）
      ├─→ 与用户重新讨论 FR-3
      ├─→ 修改 requirement.md（修改 FR-3 的定义）
      ├─→ 重新提交：reqboard_submit(kind=requirement)
      ├─→ 更新 rtm-brainstorming.yml：
      │      • 重新提取 FR 列表
      │      • FR-3 的定义已更新
      │      • metadata.version: 2
      ├─→ 再次确认需求
      │
      └─→ 确认通过后，回到 design 阶段
             ↓
   [恢复] design 阶段
      │
      ├─→ 重新读取 rtm-brainstorming.yml（version: 2）
      ├─→ 基于新的 FR-3 定义重新设计
      ├─→ 修改 design/*.md
      ├─→ 重新提交：reqboard_submit(kind=design)
      ├─→ 更新 rtm-design.yml：
      │      • 重新提取 design_sections
      │      • 重新构建 fr_to_design 映射（FR-3 的映射已更新）
      │      • 重新计算覆盖度
      │      • metadata.version: 2
      │
      └─→ 再次确认设计


场景2：decomposing 阶段发现设计有问题
═══════════════════════════════════════════════════════════════════════════
   [当前] decomposing 阶段
      │
      ├─→ 用户反馈："架构设计不合理，需要重新设计数据模型"
      │
      └─→ Dive 判断：这是设计问题，不是拆分问题
             ↓
   [回退] design 阶段
      │
      ├─→ 与用户重新讨论架构设计
      ├─→ 修改 design/data-model.md
      ├─→ 重新提交：reqboard_submit(kind=design)
      ├─→ 更新 rtm-design.yml：
      │      • 重新提取 design_sections（数据模型章节已更新）
      │      • 重新构建 fr_to_design 映射
      │      • metadata.version: 2
      ├─→ 再次确认设计
      │
      └─→ 确认通过后，回到 decomposing 阶段
             ↓
   [恢复] decomposing 阶段
      │
      ├─→ 重新读取 rtm-design.yml（version: 2）
      ├─→ 基于新的数据模型重新拆分任务
      ├─→ 修改 decomposition.md
      ├─→ 重新提交：reqboard_submit(kind=plan)
      ├─→ 更新 rtm-decomposing.yml：
      │      • 重新提取 tasks
      │      • 重新构建 design_to_tasks 映射（基于新的数据模型）
      │      • metadata.version: 2
      │
      └─→ 再次批准计划


场景3：implementing 阶段发现需求/设计/拆分有问题
═══════════════════════════════════════════════════════════════════════════
   [当前] implementing 阶段
      │
      ├─→ 执行任务时发现："这个功能需求不合理"
      │
      └─→ Dive 判断问题类型：
             ├─ 需求问题 → 回退到 brainstorming
             ├─ 设计问题 → 回退到 design
             └─ 拆分问题 → 回退到 decomposing
             ↓
   [示例：需求问题]
      │
      ├─→ 回退到 brainstorming → 修改需求 → 更新 rtm-brainstorming.yml
      ├─→ 连锁更新 design → 修改设计 → 更新 rtm-design.yml
      ├─→ 连锁更新 decomposing → 修改拆分 → 更新 rtm-decomposing.yml
      │
      └─→ 恢复 implementing，基于新的拆分计划继续执行


场景4：accepting 阶段发现任务执行有问题
═══════════════════════════════════════════════════════════════════════════
   [当前] accepting 阶段
      │
      ├─→ 验收发现："任务 t-354ea0 的实现不符合需求"
      │
      └─→ Dive 判断问题类型：
             ├─ 实现问题 → 回退到 implementing（修改代码）
             ├─ 任务定义问题 → 回退到 decomposing（修改拆分）
             ├─ 设计问题 → 回退到 design
             └─ 需求问题 → 回退到 brainstorming
             ↓
   [示例：实现问题]
      │
      ├─→ 回退到 implementing
      ├─→ 修改任务 t-354ea0 的代码
      ├─→ 更新 rtm-implementing.yml：
      │      • task_details[t-354ea0].workflow 更新
      │      • metadata.version: 3
      ├─→ 任务完成后回到 accepting
      ├─→ 重新提交验收材料
      │
      └─→ 更新 rtm-accepting.yml（version: 2）


═══════════════════════════════════════════════════════════════════════════
关键规则：跨节点反馈循环的更新流程

1. **判断问题归属**：
   - Dive 模式根据用户反馈判断问题属于哪个节点
   - 回退到对应的上游节点

2. **连锁更新**：
   - 修改上游节点后，必须更新该节点的 RTM
   - 所有下游节点都需要重新检查和更新（因为依赖已变化）

3. **版本追踪**：
   - 每次更新 RTM 时，metadata.version +1
   - 下游节点读取时检查 version，决定是否需要重新处理

4. **更新顺序**（从上游到下游）：
   brainstorming → design → decomposing → implementing → accepting
   
   修改任何一个节点，都会触发下游节点的连锁更新：
   - 修改需求 → 设计/拆分/实施/验收 都需要重新检查
   - 修改设计 → 拆分/实施/验收 都需要重新检查
   - 修改拆分 → 实施/验收 都需要重新检查
   - 修改实施 → 验收 需要重新检查

5. **RTM 更新防遗漏清单**：
   □ 重新提取数据（requirements/design_sections/tasks/test_cases）
   □ 重新构建追溯映射（fr_to_design/design_to_tasks/task_to_tests）
   □ 重新计算覆盖度（design/implementation/testing）
   □ 增加版本号（metadata.version +1）
   □ 更新时间戳（metadata.generated_at）

═══════════════════════════════════════════════════════════════════════════
```

---

## 功能点

### FR-1: RTM 文件结构设计

实现每个节点一个 RTM 的文件结构，包含：

**rtm-lifecycle.yml**（全局节点状态）：
- 当前节点（current_stage）
- 各节点状态（stages[].status: pending/in_progress/completed）
- 各节点时间戳（started_at / completed_at）

**rtm-brainstorming.yml**（需求分析节点）：
- 本节点产出：FR 列表（id / title / source / line）
- 本节点状态：产物确认状态

**rtm-design.yml**（设计节点）：
- 本节点输入：requirements（来自 brainstorming）
- 本节点产出：design_sections（ref / title / serves）
- 本节点追溯：fr_to_design 映射
- 本节点覆盖度：total_frs / covered_frs / uncovered / rate

**rtm-decomposing.yml**（拆分节点）：
- 本节点输入：requirements / design_sections
- 本节点产出：tasks（id / title / implements / serves）
- 本节点追溯：design_to_tasks 映射
- 本节点覆盖度：total_designs / covered_designs / uncovered / rate

**rtm-implementing.yml**（实施节点，拆分文件结构）：

**汇总文件**（rtm-implementing.yml，轻量级）：
- 本节点输入：tasks
- 本节点状态：tasks_total / tasks_done / tasks_in_progress / tasks_todo
- 任务列表：tasks[]（只含 id / status，不含详情）
- 用途：快速读取统计信息和任务状态概览

**任务详情目录**（rtm-implementing/，按需读取）：
- 目录结构：rtm-implementing/t-{task_id}.yml
- 单个任务文件内容：
  - 任务基本信息：id / title / status / implements / serves
  - workflow（子任务执行链）：记录每个子任务节点的状态
    - 子任务阶段：doc / ui / analysis / implement / test / review / commit
    - 每个子任务：phase / status / started_at / completed_at
    - 用途：跟踪每个父任务内部的 workflow 执行进度
- 优势：
  - 更新快：只写单个任务文件（~1KB）而不是整个汇总（~50KB）
  - 读取快：Dive 模式只需读取汇总文件获取统计
  - 按需读取：需要任务详情时再读取单个任务文件
  - 并发安全：多个任务可以并发更新（不同文件）

**rtm-accepting.yml**（验收节点）：
- 本节点输入：tasks
- 本节点产出：test_cases（id / title / covers / validates）
- 本节点追溯：task_to_tests 映射
- 本节点覆盖度：total_tasks / tested_tasks / untested / rate

**验收标准**：
- 创建一个测试需求，生成所有 7 个 RTM 文件
- 文件大小：lifecycle ~50 行，各节点 30-60 行
- 必须包含 metadata / inputs / outputs / traceability / coverage 结构

---

### FR-2: RTM 生成逻辑（7 个触发点）

在需求流程的 7 个关键时刻自动生成/更新 RTM：

1. **立项时**（reqboard_create）：
   - 创建 rtm-lifecycle.yml 骨架
   - 所有节点 status: pending

2. **提交需求文档后**（reqboard_submit kind=requirement，门禁通过）：
   - 生成 rtm-brainstorming.yml
   - 解析 requirement.md 提取 FR 列表
   - 初始化 fr_to_design 空映射

3. **确认需求后**（reqboard_ask_confirm target=artifact kind=requirement）：
   - 更新 rtm-brainstorming.yml：artifacts[0].confirmed = true
   - 更新 rtm-lifecycle.yml：brainstorming.status = completed

4. **提交设计文档后**（reqboard_submit kind=design，门禁通过）：
   - 生成 rtm-design.yml
   - 扫描 design/*.md 提取章节和 serves 标注
   - 构建 fr_to_design 映射
   - 计算设计覆盖度

5. **批准拆分计划后**（reqboard_ask_confirm target=plan）：
   - 生成 rtm-decomposing.yml
   - 从任务台账提取 design_serves 字段
   - 构建 design_to_tasks 映射
   - 计算实施覆盖度
   - 生成 rtm-implementing.yml 骨架

6. **任务状态变更时**（reqboard_task_move）：
   - 更新 rtm-implementing.yml
   - 重新统计 tasks_done / tasks_in_progress / tasks_todo
   - 更新 task_details[].status
   - 更新 task_details[].workflow（子任务执行链）：
     - 记录当前子任务的 phase / status / started_at / completed_at
     - 子任务阶段：doc → ui → analysis → implement → test → review → merge
     - 用途：追踪父任务内部的细粒度执行进度

7. **提交验收材料后**（reqboard_submit kind=verification，门禁通过）：
   - 生成 rtm-accepting.yml
   - 扫描测试文档提取 covers 标注
   - 构建 task_to_tests 映射
   - 计算测试覆盖度

**验收标准**：
- 创建测试需求，模拟完整流程，验证 7 个触发点都能正确生成/更新 RTM
- 检查 RTM 文件内容与台账和文档一致
- 验证版本号每次更新 +1

---

### FR-3: 数据同步机制

保证 RTM 的基础数据与台账一致，追溯关系从文档解析：

**台账数据同步**：
- 任务状态：从 tasks.json 读取最新状态
- 子任务状态：从 tasks[].workflow 读取子任务执行链进度
  - 子任务阶段：doc / ui / analysis / implement / test / review / commit
  - 每个子任务：subtask_id / phase / status / started_at / completed_at
- 节点状态：从 requirements[].status 读取
- 产物列表：从 requirements[].artifacts 读取

**文档数据解析**：
- FR 列表：解析 requirement.md，提取 `**FR-N:` 标记
- 设计章节：解析 design/*.md，提取 `## N.M` 标题和 `serves:` 标注
- 任务追溯：从 tasks[].design_serves 字段提取
- 测试用例：解析测试文档，提取 `covers:` 标注

**一致性保证**：
- 更新 RTM 时先读取台账最新数据
- 使用与 StageOverview 相同的统计逻辑
- 版本号标记，避免旧数据覆盖新数据

**验收标准**：
- 修改任务状态 → RTM 同步更新 → 与台账一致
- 修改设计文档 → RTM 重新解析 → 追溯关系正确
- StageOverview 的任务状态 === RTM 的任务状态

---

### FR-4: 追溯关系索引

构建四级追溯链（FR → 设计 → 任务 → 测试）：

**Level 1: FR → 设计**：
- 解析 design/*.md 的 `serves: FR-1, FR-2` 标注
- 构建 fr_to_design 映射：`{ "FR-1": ["design/arch#1.1", ...] }`
- 检测未覆盖的 FR

**Level 2: 设计 → 任务**：
- 从 tasks[].design_serves 提取引用
- 构建 design_to_tasks 映射：`{ "design/arch#1.1": ["t-354ea0", ...] }`
- 检测未实现的设计章节

**Level 3: 任务 → 测试**：
- 解析测试文档的 `covers: t-354ea0` 标注
- 构建 task_to_tests 映射：`{ "t-354ea0": ["TC-1", ...] }`
- 检测无测试的任务

**验收标准**：
- 创建测试需求，手工标注 serves/implements/covers
- 生成 RTM，验证三级映射正确
- 检查完整追溯链：FR-1 → design#1.1 → t-354ea0 → TC-1

---

### FR-5: 覆盖度统计

自动计算三层覆盖度：

**设计覆盖度**：
- total_frs：总 FR 数
- covered_frs：有设计章节的 FR 数
- uncovered：未覆盖的 FR 列表
- rate：覆盖率（%）

**实施覆盖度**：
- total_designs：总设计章节数
- covered_designs：有任务实现的章节数
- uncovered：未实现的章节列表
- rate：覆盖率（%）

**测试覆盖度**：
- total_tasks：总任务数
- tested_tasks：有测试用例的任务数
- untested：无测试的任务列表
- rate：覆盖率（%）

**验收标准**：
- 创建测试需求：3 个 FR，2 个有设计 → 设计覆盖度 67%
- 4 个设计章节，3 个有任务 → 实施覆盖度 75%
- 5 个任务，2 个有测试 → 测试覆盖度 40%
- 验证 RTM 中的统计数字正确

---

### FR-6: 修改需求时 RTM 更新策略

需求修改后，RTM 采用智能更新策略：

**增量更新**（新增内容）：
- 新增 FR → 追加到 fr_to_design，初始为空映射
- 新增设计章节 → 追加到 design_to_tasks
- 保留旧数据，版本号 +1

**完全重建**（删除内容）：
- change_note 包含"删除/移除"关键词 → 重新扫描文档
- 构建新的追溯映射
- 检测孤儿任务（引用了已删除的设计）

**冲突标记**（下游已创建）：
- 设计章节被删除，但任务已创建 → 标记 orphan_tasks
- 不自动删除任务，提示人工处理

**验收标准**：
- 新增 FR-3 → RTM 增量更新，保留 FR-1/FR-2
- 删除设计章节 → RTM 重建，标记孤儿任务
- 验证 change_note 触发正确的更新策略

---

### FR-7: StageOverview 集成

使会话节点可以读取和展示 RTM 追溯数据：

**assembleStageOverview 增强**：
- 从台账组装基础数据（保持不变）
- 读取当前节点的 RTM 文件
- 合并追溯数据到 StageOverview.stages[stage].body

**追溯 Tab 展示**：
- 需求层：FR 列表
- 设计层：设计章节 + fr_to_design 映射
- 任务层：任务列表 + design_to_tasks 映射
- 测试层：测试用例 + task_to_tests 映射
- 覆盖度：三层覆盖率统计

**验收标准**：
- GET /api/stage-overview/:id 返回包含 traceability 的数据
- 会话节点右上角点击 implementing → 追溯 Tab 显示完整追溯链
- 覆盖度统计正确显示

---

### FR-8: Dive 模式集成

Dive 模式可以快速读取 RTM 进行决策：

**读取接口**：
```typescript
// 读取全局状态
const lifecycle = readYAML('rtm-lifecycle.yml')
const currentStage = lifecycle.lifecycle.current_stage

// 读取当前节点 RTM
const stageRTM = readYAML(`rtm-${currentStage}.yml`)
const coverage = stageRTM.coverage
```

**决策逻辑**：
```typescript
// 检查是否可以推进
if (currentStage === 'design') {
  if (coverage.design.rate === 100) {
    return '所有 FR 都有设计，可以准备拆分'
  }
  return `还有 ${coverage.design.uncovered.length} 个 FR 缺少设计`
}

if (currentStage === 'implementing') {
  const impl = lifecycle.stages.implementing
  if (impl.tasks_done === impl.tasks_total) {
    if (stageRTM.coverage?.testing?.rate >= 80) {
      return '所有任务已完成且测试充分，可以进入验收'
    }
    return '任务已完成，但测试覆盖度不足，需补充测试'
  }
}
```

**节点输入包注入**：

Dive 模式在每个节点启动时，自动从 RTM 读取数据并注入到节点输入包：

```typescript
// assembleNodeInput(stage: string, requirementId: string)
function assembleNodeInput(stage: string, reqId: string) {
  const lifecycle = readRTM('rtm-lifecycle.yml', reqId);
  const stageRTM = readRTM(`rtm-${stage}.yml`, reqId);
  
  return {
    // 节点基础信息
    stage: stage,
    requirement_id: reqId,
    previous_stage: lifecycle.previous_stage,
    
    // 当前节点状态快照（来自 RTM，不需要实时解析文档）
    status: stageRTM.status,
    inputs: stageRTM.inputs,
    outputs: stageRTM.outputs,
    traceability: stageRTM.traceability,
    coverage: stageRTM.coverage,
    
    // 下一步行动建议
    next_action: generateNextAction(stageRTM),
  };
}
```

**注入时机**：
- brainstorming 节点：注入 FR 列表
- design 节点：注入 FR 列表 + 设计覆盖度
- decomposing 节点：注入设计章节 + 实施覆盖度
- implementing 节点：注入任务列表 + 任务完成度 + 子任务 workflow
- accepting 节点：注入任务列表 + 测试覆盖度

**压缩能力**：

RTM 数据在注入节点输入包时支持压缩模式，减少 token 消耗：

```typescript
// 完整模式（用于首次注入，~500 tokens）
{
  stage: "implementing",
  status: {
    tasks_total: 5,
    tasks_done: 2,
    tasks_in_progress: 2,
    tasks_todo: 1
  },
  task_details: [
    { id: "t-354ea0", status: "in_progress", workflow: [...] },
    { id: "t-abc123", status: "in_progress", workflow: [...] },
    ...
  ]
}

// 压缩模式（用于循环检查，~50 tokens）
{
  stage: "implementing",
  progress: "2/5 done, 2 in_progress",
  current_tasks: ["t-354ea0@implement", "t-abc123@implement"],
  next_action: "继续执行 t-354ea0 的 implement 阶段"
}
```

**压缩规则**：
- 状态统计：tasks_total/done/in_progress → "2/5 done, 2 in_progress"
- 任务详情：只保留 in_progress 任务的 id 和当前 workflow 阶段
- 追溯映射：只保留 uncovered 列表，不保留完整映射
- 覆盖度：只保留 rate 和 uncovered，不保留 total/covered

**压缩比**：
- 完整模式：~500 tokens（首次注入，包含所有细节）
- 压缩模式：~50 tokens（循环检查，只包含关键信息）
- 压缩比：10:1

**验收标准**：
- Dive 模式读取 RTM 耗时 < 5ms（2 个文件）
- 基于覆盖度统计做出正确决策
- 性能提升：从 ~500ms 降到 ~2ms
- 节点输入包自动注入 RTM 数据（无需手动读取）
- 压缩模式减少 90% token 消耗（500 tokens → 50 tokens）

---

### FR-9: 错误处理和兜底

处理异常情况，保证系统鲁棒性：

**文件缺失**：
- RTM 文件不存在 → 实时从台账和文档生成（降级模式）
- 台账数据缺失 → 返回空数据，不崩溃

**解析失败**：
- YAML 格式错误 → 记录错误，返回空 RTM
- 文档标注缺失 → 标记为未覆盖，继续执行

**并发冲突**：
- 多 Agent 同时更新 RTM → 后写覆盖前写（文件级锁）
- 版本号冲突 → 记录警告，使用最新版本

**数据不一致**：
- RTM 与台账不一致 → 优先信任台账，重新生成 RTM
- 定期校验机制（可选）

**验收标准**：
- 删除 RTM 文件 → 系统自动重新生成
- 人工修改 YAML 导致格式错误 → 记录错误，不崩溃
- 两个 Agent 同时更新 → 不出现数据损坏

---

### FR-10: 性能优化

保证 RTM 读写性能满足 Dive 模式需求：

**读取优化**：
- 使用 Node.js fs 直接读取 YAML（~1ms/文件）
- 按需读取（只读当前节点 RTM）
- 缓存解析结果（可选）

**写入优化**：
- 增量更新（不重建整个文件）
- 批量写入（同一事件多个更新合并）
- 异步写入（不阻塞主流程）

**文件大小控制**：
- lifecycle ~50 行
- 各节点 RTM 30-60 行
- 总计 ~300 行（vs 单文件 ~500 行）

**验收标准**：
- 读取 2 个 RTM 文件 < 5ms
- 写入 RTM 文件 < 10ms
- 完整流程（7 次更新）< 100ms

---

### FR-11: 基于 DSH Agent Teams 的并行任务执行（零实现成本）

实现多个父任务通过 DSH Agent Teams 并行执行的机制：

**完全基于 DSH 原生能力，零实现成本！**

DSH Agent Teams 已经提供了我们需要的所有能力：
- ✅ **共享任务板**（team_task）
- ✅ **原生 DAG 支持**（blocked_by）
- ✅ **事件驱动**（wait_agent）
- ✅ **持久化 Worker**（spawn_teammate）
- ✅ **CAS 防冲突**（expected_revision）
- ✅ **自动负载均衡**（Worker 自己 claim 任务）

**核心原理**：
- **1个子阶段 = 1个共享任务**（team_task）
  - 不需要自己创建 Subagent，使用持久化的 Worker Agent
  - 例如：T1-doc、T1-implement、T2-doc 各自是一个 team_task
  - Worker 自动 claim ready 的任务

- **DSH 原生 DAG 调度**（零实现成本）：
  - **任务级 DAG**：T3-doc 的 blocked_by: ["T1-commit"]
  - **子阶段级 DAG**：T1-implement 的 blocked_by: ["T1-doc"]
  - **DSH 自动计算 ready 状态**：依赖已满足的任务自动 ready
  - **DSH 自动解锁**：任务 complete 时自动解锁依赖它的任务

- **Dive (Team Lead) 完全掌控**：
  - 创建 Worker Agents 和共享任务
  - 通过 wait_agent 监控进度（事件驱动，零轮询）
  - 每个任务完成后可以检查结果、调整策略
  - 发现问题时可以 interrupt_agent / send_message 介入

**架构示意**（DSH Agent Teams 原生能力）：

```
┌─────────────────────────────────────────────────────────────────────┐
│  Dive (Team Lead)                                                    │
│  • spawn_teammate: 创建 Worker Agents                                │
│  • team_task_create: 创建所有子阶段任务（含 blocked_by）             │
│  • wait_agent: 等待任务完成（事件驱动，零轮询）                      │
│  • list_agents / team_task_list: 监控进度                            │
│  • interrupt_agent: 假死检测与恢复                                   │
└─────────────────────────────────────────────────────────────────────┘
         ↓ spawn_teammate (持久化)
         
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Worker-1     │  │ Worker-2     │  │ Worker-3     │
│ (持久)       │  │ (持久)       │  │ (持久)       │
│              │  │              │  │              │
│ 工作循环：   │  │ 工作循环：   │  │ 工作循环：   │
│ 1. list      │  │ 1. list      │  │ 1. list      │
│    ready任务 │  │    ready任务 │  │    ready任务 │
│ 2. claim     │  │ 2. claim     │  │ 2. claim     │
│ 3. 执行      │  │ 3. 执行      │  │ 3. 执行      │
│ 4. complete  │  │ 4. complete  │  │ 4. complete  │
│              │  │              │  │              │
│ T1-doc ✓     │  │ T2-doc ✓     │  │ T4-doc ✓     │
│ T1-impl ✓    │  │ T2-impl ✓    │  │ T7-doc ✓     │
│ T3-doc ...   │  │ T1-test ...  │  │ T4-impl ...  │
└──────────────┘  └──────────────┘  └──────────────┘
         ↓ claim & complete
┌─────────────────────────────────────────────────────────────────────┐
│  Shared Task Board (DSH 原生管理)                                    │
│                                                                      │
│  Wave 1（ready，无依赖）：                                           │
│  • T1-doc (completed) ✓                                              │
│  • T2-doc (completed) ✓                                              │
│  • T4-doc (in_progress) ← Worker-3                                   │
│  • T7-doc (completed) ✓                                              │
│                                                                      │
│  Wave 2（ready，依赖已满足）：                                       │
│  • T1-implement (completed) ✓                                        │
│  • T2-implement (completed) ✓                                        │
│  • T3-doc (in_progress) ← Worker-1  (T1完成后解锁)                  │
│  • T4-implement (pending, ready) ← 等待 Worker claim                │
│  • T7-implement (in_progress) ← Worker-2                             │
│                                                                      │
│  Wave 3（pending，依赖未满足）：                                     │
│  • T1-test (pending, blocked_by: [T1-implement]) ← 已满足，ready    │
│  • T2-test (pending, blocked_by: [T2-implement]) ← 已满足，ready    │
│  • T3-implement (pending, blocked_by: [T3-doc]) ← 未满足，not ready │
│  • T5-implement (pending, blocked_by: [T1-..., T2-..., T3-..., T4-...]) ← 未满足 │
│                                                                      │
│  DSH 自动管理：                                                      │
│  ✅ 计算 ready 状态（依赖已满足 → ready: true）                     │
│  ✅ CAS 更新（expected_revision 防并发冲突）                         │
│  ✅ 依赖解锁（complete 自动解锁 blocked_by）                         │
│  ✅ 任务释放（release 操作，假死恢复）                               │
└─────────────────────────────────────────────────────────────────────┘

关键优势（DSH 原生能力）：
• **零 DAG 实现**：blocked_by 原生支持，DSH 自动计算 ready
• **零轮询成本**：wait_agent 事件驱动
• **自动负载均衡**：Worker 先到先得 claim
• **CAS 防冲突**：expected_revision 原子操作
• **持久化 Worker**：可以连续执行多个任务，不需要为每个子阶段创建新 agent
• **共享文件系统**：所有 agent 共享工作目录，RTM 自动可见
```
**任务类型与子阶段映射**：

不是所有任务都需要 7 个子阶段。根据任务的 **phase** 字段决定：

| 任务类型（phase） | 需要的子阶段 | 说明 |
|------------------|-------------|------|
| **implement** | implement | 简单的代码改动（如删除文件） |
| **doc** | doc → implement → test → commit | 文档类任务 |
| **ui** | ui → implement → test → commit | UI 设计类任务 |
| **analysis** | analysis → implement → test → commit | 分析类任务 |
| **test** | test | 纯测试任务 |
| **review** | review | 代码审查任务 |
| **完整任务** | doc → ui → analysis → implement → test → review → commit | 大型功能开发 |

**示例**：
- T1: 删除工具目录 → phase=implement → 只需 implement 阶段
- T2: 重写文档 → phase=doc → doc + implement + test + commit
- T3: 完整功能开发 → 无 phase 或 phase=fullstack → 全部 7 个阶段

**Subagent Prompt 模板**：

每个 subagent 启动时注入的 prompt（根据任务的 phase 动态调整）：

```
你需要执行任务 {TASK_ID}（{TASK_TITLE}）的实施流程。

任务信息：
- 任务 ID：{TASK_ID}
- 任务标题：{TASK_TITLE}
- 实现设计：{DESIGN_FILES}
- 服务功能点：{SERVES}

执行流程（7个子阶段，必须按顺序执行）：

1. **doc 阶段**：编写任务文档
   - 读取任务定义：rtm-implementing/{TASK_ID}.yml
   - 编写任务文档：docs/requirements/{REQ_ID}/tasks/{TASK_ID}.md
   - 内容包括：任务定义、实施方案、验收标准
   - 完成后调用：reqboard_task_report(task_id, summary, completed)

2. **ui 阶段**：UI 设计（frontend 任务需要，backend 任务跳过）
   - 读取设计文档：design/{DESIGN_FILES}
   - 生成 UI 原型/组件
   - 完成后调用：reqboard_task_report(...)

3. **analysis 阶段**：分析实现方案
   - 读取设计和需求
   - 分析技术方案、依赖关系
   - 完成后调用：reqboard_task_report(...)

4. **implement 阶段**：编码实现（核心阶段）
   - 读取设计和任务文档
   - 实现功能代码
   - 完成后调用：reqboard_task_report(...)

5. **test 阶段**：编写和运行测试
   - 编写测试用例
   - 运行测试：bash("npm test {TEST_PATTERN}")
   - 检查覆盖度（要求 ≥80%）
   - 完成后调用：reqboard_task_report(...)

6. **review 阶段**：代码审查
   - 自动审查代码规范
   - 自动修复可修复的问题
   - 完成后调用：reqboard_task_report(...)

7. **commit 阶段**：提交代码
   - 提交代码：bash("git add . && git commit -m 'feat: {TASK_TITLE}'")
   - 完成后调用：reqboard_task_report(...)

重要提醒：
- 每个阶段完成后必须调用 reqboard_task_report 汇报
- reqboard_task_report 会自动更新 rtm-implementing/{TASK_ID}.yml
- 如果某个阶段失败，停止执行并报告错误
- backend 任务可以跳过 ui 阶段
```

**RTM 数据结构**：

```yaml
# rtm-implementing/t-354ea0.yml（单个任务文件）
task:
  id: t-354ea0
  title: "实现 RTM 文件结构"
  status: in_progress
  implements: "design/arch#1.1"
  serves: [FR-1, FR-2]
  depends_on: []                    # 任务依赖（DAG 调度用）
  phase: fullstack                  # 任务类型
  side: backend                     # frontend / backend / fullstack / doc
  
  # Subagent 信息
  subagent_id: "sa-abc123"          # Subagent 的 ID
  subagent_status: "running"         # running / completed / failed
  
  # Workflow 参数（用于生成 subagent prompt）
  workflow_params:
    REQ_ID: "REQ-260926140539-457b"
    TASK_ID: "t-354ea0"
    TASK_TITLE: "实现 RTM 文件结构"
    DESIGN_FILES: "design/arch.md"
    IMPL_FILES: "src/rtm/generator.ts"
    TEST_PATTERN: "rtm.test.ts"
    SIDE: "backend"                  # frontend / backend / fullstack / doc
    PHASE: "fullstack"               # 决定需要哪些子阶段
  
  # 子任务执行记录（根据 PHASE 决定数量，此例为完整任务）
  workflow_total: 7
  workflow_done: 3
  workflow:
    - phase: doc
      status: done
      started_at: "2024-01-01T09:00:00Z"
      completed_at: "2024-01-01T10:00:00Z"
      steps_completed:
        - action: "编写任务文档"
          files_changed: ["docs/requirements/REQ-xxx/tasks/t-354ea0.md"]
          output: "任务文档已完成"
    
    - phase: ui
      status: skipped                 # backend 任务跳过 ui 阶段
      skip_reason: "backend task, no UI needed"
    
    - phase: analysis
      status: done
      started_at: "2024-01-01T10:00:00Z"
      completed_at: "2024-01-01T12:00:00Z"
      steps_completed:
        - action: "分析实现方案"
          output: "确定实施步骤"
    
    - phase: implement
      status: in_progress             # 当前正在执行
      started_at: "2024-01-01T13:00:00Z"
      steps_completed:
        - action: "创建 rtm-lifecycle.yml 结构"
          files_changed: ["src/rtm/lifecycle.ts"]
          commit: "feat: add rtm-lifecycle structure"
      current_step:
        action: "实现生成逻辑"
        started_at: "2024-01-01T14:00:00Z"
      steps_todo:
        - "编写单元测试"
        - "集成到 reqboard_create"
    
    - phase: test
      status: pending
    
    - phase: review
      status: pending
    
    - phase: commit
      status: pending
```

**DAG 调度逻辑**：

任务并行执行基于 **DAG（有向无环图）调度**：

```
任务依赖关系示例：
T1: depends_on: []           ← 入度0，可立即启动
T2: depends_on: []           ← 入度0，可立即启动
T3: depends_on: [t1]         ← 入度1，等待 t1
T4: depends_on: []           ← 入度0，可立即启动
T5: depends_on: [t1,t2,t3,t4] ← 入度4，等待全部依赖
T6: depends_on: [t5]         ← 入度1，等待 t5
T7: depends_on: []           ← 入度0，可立即启动
T8: depends_on: [t6,t7]      ← 入度2，等待 t6 和 t7

执行时序（基于 DAG）：
Wave 1: T1, T2, T4, T7（并行启动，入度为0）
  ↓
Wave 2: T3（T1 完成后启动）
  ↓
Wave 3: T5（T1, T2, T3, T4 全部完成后启动）
  ↓
Wave 4: T6（T5 完成后启动）
  ↓
Wave 5: T8（T6 和 T7 全部完成后启动）
```

**调度算法**：
1. **初始化**：计算每个任务的入度（depends_on 长度）
2. **启动 Wave 1**：所有入度为0的任务并行启动 subagent
3. **监听完成事件**：当某个任务完成时
   - 减少所有依赖它的任务的入度
   - 如果某任务入度变为0，立即启动该任务的 subagent
4. **循环直到所有任务完成**

**执行流程**（DSH Agent Teams，零实现成本）：

```typescript
// ============ Dive (Team Lead) 的初始化 ============

// 1. 创建持久化 Worker Agents
for (let i = 1; i <= 3; i++) {
  await spawn_teammate({
    name: `worker-${i}`,
    description: `任务执行 Worker ${i}`,
    prompt: `你是任务执行 Worker。循环执行：
1. team_task_list({ status: "pending", ready: true })
2. claim 第一个任务
3. 执行任务（读取 RTM → 执行子阶段 → reqboard_task_report）
4. complete 任务
持续等待新任务。`,
    context: "fresh"
  });
}

// 2. 为每个子阶段创建共享任务
const summary = readYAML('rtm-implementing.yml');
for (const task of summary.tasks) {
  const taskDetail = readYAML(`rtm-implementing/${task.id}.yml`);
  const phases = taskDetail.workflow.map(w => w.phase);
  
  for (let i = 0; i < phases.length; i++) {
    const phase = phases[i];
    const blockedBy = [];
    
    // 同任务内的前序
    if (i > 0) blockedBy.push(`${task.id}-${phases[i-1]}`);
    
    // 任务级依赖
    if (i === 0 && taskDetail.depends_on) {
      for (const depId of taskDetail.depends_on) {
        const depTask = readYAML(`rtm-implementing/${depId}.yml`);
        const lastPhase = depTask.workflow[depTask.workflow.length - 1].phase;
        blockedBy.push(`${depId}-${lastPhase}`);
      }
    }
    
    await team_task_create({
      subject: `${task.id}-${phase}`,
      description: `执行 ${task.id} 的 ${phase} 阶段`,
      blocked_by: blockedBy  // DSH 自动管理依赖
    });
  }
}

// 3. 启动 Worker
for (let i = 1; i <= 3; i++) {
  await send_message(`worker-${i}`, "开始执行");
}

// ============ Dive 监控（事件驱动，零轮询） ============

while (true) {
  // 等待变化（阻塞，零成本）
  const result = await wait_agent({ timeout: 300000 });
  
  // 检查进度
  const tasks = await team_task_list();
  const completed = tasks.filter(t => t.status === 'completed').length;
  console.log(`📊 ${completed}/${tasks.length}`);
  
  if (completed === tasks.length) break;  // 全部完成
  
  // 假死检测（5分钟心跳）
  if (result.timedOut) {
    const agents = await list_agents();
    for (const agent of agents) {
      const myTasks = await team_task_list({ owner: agent.name });
      const stuck = myTasks.find(t => 
        t.status === 'in_progress' && 
        Date.now() - new Date(t.updated_at).getTime() > 30*60*1000
      );
      
      if (stuck) {
        await interrupt_agent(agent.name);
        await team_task_update({
          task_id: stuck.id,
          action: "release"  // 重新变为 pending
        });
        await send_message(agent.name, "重启");
      }
    }
  }
}

await reqboard_move('implementing', 'accepting', '完成');
```
**与 RTM 的集成**：
- decomposing 阶段2：生成任务文件时包含 workflow_params
- decomposing 阶段4：不创建任何 Workflow（没有这个概念），只准备数据
- implementing 阶段1：Dive 模式为每个 todo 任务启动 subagent
- implementing 阶段2：每个 subagent 内部通过 reqboard_task_report 更新 RTM

**验收标准**：
- 调用 reqboard_task_run() 自动为所有 todo 任务启动 subagent
- 多个 subagent 并行执行（通过 job_list 可以看到多个后台任务）
- 每个 subagent 内部按 7 个子阶段串行执行
- 每个子阶段完成时自动更新 rtm-implementing/t-xxx.yml
- backend 任务自动跳过 ui 阶段
- 测试覆盖度不足时自动拒绝推进（< 80%）
- 所有任务完成后自动推进到 accepting 阶段

---
## 数据契约

### RTM 文件格式

**rtm-lifecycle.yml**：
```yaml
metadata:
  requirement_id: string  # REQ-xxx
  created_at: string      # ISO 8601
  version: number         # 每次更新 +1

lifecycle:
  current_stage: string   # draft / brainstorming / design / ...
  stages:
    [stage_key]:
      status: string      # pending / in_progress / completed
      started_at: string  # ISO 8601（可选）
      completed_at: string # ISO 8601（可选）
```

**rtm-[stage].yml**（各节点）：
```yaml
metadata:
  stage: string           # 节点名称
  requirement_id: string
  generated_at: string    # ISO 8601
  version: number

inputs:                   # 本节点输入（可选）
  [key]: [value]

outputs:                  # 本节点产出（可选）
  [key]: [value]

traceability:             # 本节点追溯关系（可选）
  [mapping_key]:
    [from]: [to_list]

coverage:                 # 本节点覆盖度（可选）
  total: number
  covered: number
  uncovered: [list]
  rate: number

status:                   # 本节点状态（可选）
  [state_key]: [value]
```

**rtm-implementing.yml 详细结构示例**：
```yaml
metadata:
  stage: implementing
  requirement_id: REQ-xxx
  generated_at: "2026-09-26T10:00:00Z"
  version: 5

inputs:
  tasks:
    - id: t-354ea0
      title: "实现 RTM 生成逻辑"
      status: in_progress

status:
  tasks_total: 5
  tasks_done: 2
  tasks_in_progress: 2
  tasks_todo: 1

task_details:
  - id: t-354ea0
    status: in_progress
    started_at: "2026-09-26T09:00:00Z"
    claimed_by: agent-001
    workflow:                    # 子任务执行链（新增）
      - subtask_id: st-doc-001
        phase: doc               # 阶段：doc / ui / analysis / implement / test / review / commit
        status: done             # 子任务状态：pending / in_progress / done
        started_at: "2026-09-26T09:00:00Z"
        completed_at: "2026-09-26T09:15:00Z"
      - subtask_id: st-implement-001
        phase: implement
        status: in_progress
        started_at: "2026-09-26T09:30:00Z"
      - subtask_id: st-test-001
        phase: test
        status: pending
```

**workflow 字段说明**：
- **subtask_id**: 子任务唯一 ID（格式：st-{phase}-{序号}）
- **phase**: 子任务阶段（doc / ui / analysis / implement / test / review / commit）
- **status**: 子任务状态（pending / in_progress / done）
- **started_at**: 子任务开始时间（ISO 8601）
- **completed_at**: 子任务完成时间（ISO 8601，可选）

**用途**：
- 追踪每个父任务内部的细粒度执行进度
- Dive 模式可以快速判断当前卡在哪个子任务阶段
- StageOverview 追溯 Tab 可以展示完整的 workflow 执行链

### 版本兼容

- **向后兼容**：新增字段不影响旧版本读取
- **版本号**：metadata.version 用于追踪变更历史
- **降级模式**：RTM 缺失时从台账实时生成

### 迁移路径

- **Phase 1**：新需求自动生成 RTM（新功能）
- **Phase 2**：存量需求按需生成 RTM（手动触发）
- **Phase 3**：StageOverview 优先使用 RTM（性能优化）

---

## 验收标准

### 端到端测试

创建一个完整的测试需求，验证：

1. **立项** → 生成 rtm-lifecycle.yml
2. **提交需求文档** → 生成 rtm-brainstorming.yml，提取 3 个 FR
3. **提交设计文档** → 生成 rtm-design.yml，构建 fr_to_design 映射，覆盖度 67%
4. **批准拆分计划** → 生成 rtm-decomposing.yml 和 rtm-implementing.yml，构建 design_to_tasks 映射
5. **任务状态变更** → 更新 rtm-implementing.yml，tasks_done 正确统计，workflow 子任务状态正确记录（doc → implement → test 各阶段的 status / started_at / completed_at）
6. **提交验收材料** → 生成 rtm-accepting.yml，构建 task_to_tests 映射，测试覆盖度 40%

### 性能测试

- Dive 模式读取 RTM 决策 < 5ms（vs 现在 ~500ms）
- 任务状态变更触发 RTM 更新 < 10ms
- 完整流程生成所有 RTM < 100ms

### 数据一致性测试

- RTM 的任务状态 === 台账的任务状态
- RTM 的子任务 workflow 状态 === 台账的 tasks[].workflow 状态
- RTM 的 FR 列表 === requirement.md 的 FR 列表
- RTM 的追溯关系 === 文档标注的追溯关系

### 异常测试

- 删除 RTM 文件 → 自动重新生成
- YAML 格式错误 → 记录错误，不崩溃
- 并发更新 → 不出现数据损坏

---

## 实施约束

### 技术约束

- **语言**：TypeScript（与 dsh-pmboard 一致）
- **YAML 库**：使用 js-yaml（已在项目中使用）
- **文件路径**：`docs/requirements/REQ-xxx/rtm-*.yml`

### 性能约束

- RTM 读取 < 5ms（2 个文件）
- RTM 写入 < 10ms
- 文件大小 < 100 行/文件

### 兼容性约束

- 不改变台账结构
- 不改变文档格式
- 不改变 reqboard 工具的对外接口

### 回滚方案

- RTM 是增强功能，可以关闭
- 关闭后系统回退到现有行为（实时解析文档）
- RTM 文件可以删除，不影响台账

---

## 依赖

### 上游依赖

- **dsh-reqboard.json**（台账）：需求和任务的基础数据
- **requirement.md**：FR 列表
- **design/*.md**：设计章节和 serves 标注
- **tasks.json**：任务的 design_serves 字段

### 下游影响

- **StageOverview**：新增 traceability 字段
- **会话节点前端**：新增追溯 Tab
- **Dive 模式**：新增 RTM 读取逻辑

### 外部依赖

- **js-yaml**：YAML 解析和序列化
- **Node.js fs**：文件读写

---

## 风险与缓解

### 风险1：数据不一致

**风险**：RTM 与台账数据不同步

**缓解**：
- RTM 更新时从台账读取最新数据
- 使用与 StageOverview 相同的统计逻辑
- 定期校验机制（可选）

### 风险2：性能不达预期

**风险**：RTM 读取仍然慢

**缓解**：
- 按需读取（只读当前节点）
- 文件大小控制（< 100 行）
- 缓存机制（可选）

### 风险3：并发冲突

**风险**：多 Agent 同时更新 RTM

**缓解**：
- 文件级锁（后写覆盖前写）
- 版本号检测
- 降级模式（RTM 损坏时从台账重新生成）

### 风险4：迁移成本

**风险**：存量需求迁移困难

**缓解**：
- 新需求自动生成 RTM
- 存量需求按需生成（手动触发）
- StageOverview 兼容无 RTM 场景

---

## 后续演进

### Phase 1（本次实施）

- 实现 RTM 生成和更新逻辑
- StageOverview 集成
- Dive 模式集成

### Phase 2（未来优化）

- 追溯链可视化（图形展示）
- 实时校验机制
- 批量迁移存量需求

### Phase 3（未来扩展）

- 跨需求追溯（依赖关系）
- 影响分析（修改波及面）
- 智能建议（覆盖度优化建议）
