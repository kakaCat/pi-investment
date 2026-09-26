# RTM YAML 实施完整流程图

> 创建日期：2026-09-26  
> 目标：从立项到归档的完整 RTM 生命周期

---

## 🎯 总览流程图

```mermaid
graph TB
    Start[立项 reqboard_create] --> InitRTM[创建 RTM 骨架]
    
    InitRTM --> |创建两个文件|RTMFiles
    
    subgraph RTMFiles[RTM 文件结构]
        LC[rtm-lifecycle.yml<br/>流程状态]
        TR[rtm-traceability.yml<br/>追溯关系]
    end
    
    RTMFiles --> Draft[draft 节点]
    Draft --> |提交需求文档|Brainstorm[brainstorming 节点]
    Brainstorm --> |更新 lifecycle|UpdateLC1[lifecycle.current_stage = brainstorming]
    Brainstorm --> |提取 FR|UpdateTR1[traceability.fr_to_design 初始化]
    
    UpdateLC1 --> Design[design 节点]
    UpdateTR1 --> Design
    
    Design --> |提交设计文档|DesignSubmit[扫描 design/*.md]
    DesignSubmit --> |提取 serves 标注|UpdateTR2[更新 traceability.fr_to_design]
    DesignSubmit --> |更新节点状态|UpdateLC2[lifecycle.stages.design.status = completed]
    
    UpdateTR2 --> Decompose[decomposing 节点]
    UpdateLC2 --> Decompose
    
    Decompose --> |批准计划|ApprovePlan[创建任务到台账]
    ApprovePlan --> |提取任务追溯|UpdateTR3[更新 traceability.design_to_tasks]
    ApprovePlan --> |更新节点状态|UpdateLC3[lifecycle.current_stage = implementing]
    
    UpdateTR3 --> Implement[implementing 节点]
    UpdateLC3 --> Implement
    
    Implement --> |任务状态变更|TaskMove[reqboard_task_move]
    TaskMove --> |频繁更新|UpdateLC4[lifecycle.stages.implementing.tasks_done++]
    
    UpdateLC4 --> |所有任务完成|Accept[accepting 节点]
    
    Accept --> |提交验收材料|VerifySubmit[扫描测试文档]
    VerifySubmit --> |提取 covers 标注|UpdateTR4[更新 traceability.task_to_tests]
    VerifySubmit --> |更新节点状态|UpdateLC5[lifecycle.current_stage = accepting]
    
    UpdateTR4 --> Archive[archived 节点]
    UpdateLC5 --> Archive
    
    Archive --> |归档|FinalSnapshot[RTM 最终快照]
    
    FinalSnapshot --> End[完成]
```

---

## 📊 详细流程：7 个阶段

### 阶段 1：立项（draft）

```mermaid
sequenceDiagram
    participant User as 用户/PM
    participant Agent as Agent
    participant Create as reqboard_create
    participant RTM as RTM Generator
    participant FS as 文件系统
    
    User->>Agent: 立项需求
    Agent->>Create: 调用 reqboard_create
    Create->>RTM: 初始化 RTM
    
    RTM->>FS: 写入 rtm-lifecycle.yml
    Note over FS: current_stage: draft<br/>所有节点 status: pending
    
    RTM->>FS: 写入 rtm-traceability.yml
    Note over FS: 空的追溯映射<br/>fr_to_design: {}<br/>design_to_tasks: {}<br/>task_to_tests: {}
    
    FS-->>RTM: 创建成功
    RTM-->>Create: 初始化完成
    Create-->>Agent: 需求已创建
    Agent-->>User: REQ-xxx 已立项
```

**生成文件**：
- ✅ `rtm-lifecycle.yml`（骨架）
- ✅ `rtm-traceability.yml`（空映射）

---

### 阶段 2：需求分析（brainstorming）

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Submit as reqboard_submit
    participant Parser as 文档解析器
    participant RTM as RTM Updater
    participant FS as 文件系统
    
    Agent->>Submit: 提交需求文档
    Submit->>Parser: 解析 requirement.md
    Parser->>Parser: 提取 FR 列表
    Note over Parser: FR-1, FR-2, FR-3...
    
    Parser-->>Submit: FR 列表
    Submit->>RTM: 更新 lifecycle
    RTM->>FS: 更新 rtm-lifecycle.yml
    Note over FS: current_stage: design<br/>brainstorming.status: completed
    
    Submit->>RTM: 初始化 traceability
    RTM->>FS: 更新 rtm-traceability.yml
    Note over FS: fr_to_design:<br/>  FR-1: []<br/>  FR-2: []<br/>  FR-3: []
    
    FS-->>RTM: 更新成功
    RTM-->>Submit: 完成
    Submit-->>Agent: 需求文档已确认
```

**更新内容**：
- ✅ lifecycle: brainstorming → completed
- ✅ traceability: 初始化 FR 列表（空映射）

---

### 阶段 3：设计（design）

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Submit as reqboard_submit
    participant Scanner as 设计扫描器
    participant RTM as RTM Updater
    participant FS as 文件系统
    
    Agent->>Submit: 提交设计文档
    Submit->>Scanner: 扫描 design/*.md
    
    Scanner->>Scanner: 提取章节 + serves 标注
    Note over Scanner: design/arch#1.1 `serves: FR-1`<br/>design/arch#2 `serves: FR-2, FR-6`
    
    Scanner-->>Submit: 设计章节列表
    Submit->>RTM: 构建 FR → 设计映射
    
    RTM->>FS: 更新 rtm-traceability.yml
    Note over FS: fr_to_design:<br/>  FR-1: [design/arch#1.1, design/arch#1.2]<br/>  FR-2: [design/arch#2]
    
    RTM->>FS: 更新 rtm-lifecycle.yml
    Note over FS: current_stage: decomposing<br/>design.status: completed
    
    FS-->>RTM: 更新成功
    RTM-->>Submit: 完成
    Submit-->>Agent: 设计已确认
```

**更新内容**：
- ✅ lifecycle: design → completed
- ✅ traceability: fr_to_design 映射填充

---

### 阶段 4：拆分（decomposing）

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Confirm as reqboard_ask_confirm
    participant Decompose as 拆分执行器
    participant Ledger as 台账
    participant RTM as RTM Updater
    participant FS as 文件系统
    
    Agent->>Confirm: 批准拆分计划
    Confirm->>Decompose: 执行拆分
    Decompose->>Ledger: 创建任务到台账
    Note over Ledger: t-354ea0: {<br/>  requirement_refs: [FR-1]<br/>  design_serves: design/arch#1.1<br/>}
    
    Decompose->>RTM: 提取任务追溯信息
    RTM->>Ledger: 读取任务列表
    RTM->>RTM: 构建 设计 → 任务映射
    
    RTM->>FS: 更新 rtm-traceability.yml
    Note over FS: design_to_tasks:<br/>  design/arch#1.1: [t-354ea0, t-abc123]<br/>  design/arch#2: [t-f0e25a]
    
    RTM->>FS: 更新 rtm-lifecycle.yml
    Note over FS: current_stage: implementing<br/>decomposing.status: completed<br/>implementing.tasks_total: 8
    
    FS-->>RTM: 更新成功
    RTM-->>Confirm: 完成
    Confirm-->>Agent: 拆分已完成
```

**更新内容**：
- ✅ lifecycle: decomposing → completed, implementing → in_progress
- ✅ traceability: design_to_tasks 映射填充

---

### 阶段 5：实施（implementing）- 频繁更新

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant TaskMove as reqboard_task_move
    participant Ledger as 台账
    participant RTM as RTM Updater
    participant FS as 文件系统
    
    loop 每次任务状态变更
        Agent->>TaskMove: 任务状态变更
        TaskMove->>Ledger: 更新任务状态
        Note over Ledger: t-354ea0.status: done
        
        TaskMove->>RTM: 重新统计
        RTM->>Ledger: 统计任务状态
        RTM->>RTM: 计算 tasks_done/in_progress/todo
        
        RTM->>FS: 更新 rtm-lifecycle.yml
        Note over FS: implementing.tasks_done: 5<br/>implementing.tasks_in_progress: 2<br/>implementing.tasks_todo: 1
        
        FS-->>RTM: 更新成功
    end
    
    RTM->>RTM: 检测所有任务完成
    RTM->>FS: 更新 rtm-lifecycle.yml
    Note over FS: current_stage: accepting<br/>implementing.status: completed
    
    RTM-->>Agent: 可以进入验收
```

**更新内容**：
- ✅ lifecycle: 频繁更新任务统计（tasks_done/in_progress/todo）
- ⚠️ traceability: 不变

---

### 阶段 6：验收（accepting）

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Submit as reqboard_submit
    participant Scanner as 测试扫描器
    participant RTM as RTM Updater
    participant FS as 文件系统
    
    Agent->>Submit: 提交验收材料
    Submit->>Scanner: 扫描测试文档
    
    Scanner->>Scanner: 提取 covers 标注
    Note over Scanner: TC-1 `covers: t-354ea0`<br/>TC-2 `covers: t-0c18e3`
    
    Scanner-->>Submit: 测试用例列表
    Submit->>RTM: 构建 任务 → 测试映射
    
    RTM->>FS: 更新 rtm-traceability.yml
    Note over FS: task_to_tests:<br/>  t-354ea0: [TC-1]<br/>  t-0c18e3: [TC-2]<br/>  t-abc123: []
    
    RTM->>RTM: 计算覆盖度统计
    RTM->>FS: 更新 coverage
    Note over FS: testing:<br/>  total: 8<br/>  covered: 2<br/>  rate: 25
    
    RTM->>FS: 更新 rtm-lifecycle.yml
    Note over FS: accepting.status: in_progress
    
    FS-->>RTM: 更新成功
    RTM-->>Submit: 完成
    Submit-->>Agent: 验收材料已提交
```

**更新内容**：
- ✅ lifecycle: accepting → in_progress
- ✅ traceability: task_to_tests 映射填充
- ✅ traceability: coverage.testing 统计

---

### 阶段 7：归档（archived）

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Submit as reqboard_submit
    participant RTM as RTM Updater
    participant FS as 文件系统
    participant Git as Git
    
    Agent->>Submit: 验收通过，归档
    Submit->>RTM: 最终快照
    
    RTM->>FS: 更新 rtm-lifecycle.yml
    Note over FS: current_stage: archived<br/>accepting.status: completed<br/>archived.status: completed<br/>archived_at: 2026-09-26T21:00:00Z
    
    RTM->>FS: 确认 rtm-traceability.yml
    Note over FS: 完整的追溯链<br/>所有覆盖度统计
    
    FS-->>RTM: 最终快照完成
    RTM-->>Submit: 完成
    Submit-->>Git: 提交最终版本
    Git-->>Submit: 已归档
    Submit-->>Agent: 需求已归档
```

**最终状态**：
- ✅ lifecycle: 所有节点完成
- ✅ traceability: 完整的四级追溯链
- ✅ coverage: 最终覆盖度统计

---

## 🔄 会话节点读取流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Session as 会话页面
    participant API as GET /api/stage-overview/:id
    participant Query as QueryStageOverview
    participant RTM as RTM Reader
    participant FS as 文件系统
    participant Render as renderNodePanel
    
    User->>Session: 打开会话（处理 REQ-xxx）
    Session->>API: 获取需求详情
    API->>Query: queryStageOverview(reqId)
    
    Query->>RTM: 读取 RTM 数据
    RTM->>FS: 读取 rtm-lifecycle.yml
    FS-->>RTM: 流程状态
    
    RTM->>FS: 读取 rtm-traceability.yml
    FS-->>RTM: 追溯关系
    
    RTM->>RTM: 合并数据
    RTM-->>Query: { lifecycle, traceability }
    
    Query->>Query: 装配 StageOverview
    Query-->>API: StageOverview + RTM
    API-->>Session: JSON 响应
    
    Session->>Render: renderNodePanel(overview)
    
    alt 用户点击 implementing 节点
        Render->>Render: renderImplViews()
        Note over Render: 显示三个 Tab:<br/>[DAG] [泳道] [追溯]
        
        alt 用户点击「追溯」Tab
            Render->>Render: renderTraceView(traceability)
            Note over Render: 📋 需求层<br/>🎨 设计层<br/>⚙️ 任务层<br/>📊 覆盖度统计
            Render-->>User: 显示完整追溯链
        end
    end
```

---

## 📊 数据流总览

```mermaid
graph LR
    subgraph 数据源
        Req[requirement.md]
        Des[design/*.md]
        Ledger[台账 tasks.json]
        Test[test-cases.md]
    end
    
    subgraph RTM 生成
        Extract[提取器]
        Req --> Extract
        Des --> Extract
        Ledger --> Extract
        Test --> Extract
        
        Extract --> LC[rtm-lifecycle.yml]
        Extract --> TR[rtm-traceability.yml]
    end
    
    subgraph 使用方
        LC --> Session[会话节点]
        TR --> Session
        
        Session --> Display[追溯 Tab 显示]
    end
```

---

## ⏱️ 更新频率对比

```mermaid
gantt
    title RTM 文件更新频率
    dateFormat YYYY-MM-DD HH:mm
    
    section rtm-lifecycle.yml
    立项创建        :2026-09-26 10:00, 1m
    需求确认        :2026-09-26 11:30, 1m
    设计确认        :2026-09-26 14:00, 1m
    拆分完成        :2026-09-26 15:30, 1m
    任务1完成       :2026-09-26 16:15, 1m
    任务2完成       :2026-09-26 16:45, 1m
    任务3完成       :2026-09-26 17:10, 1m
    任务4完成       :2026-09-26 17:35, 1m
    任务5完成       :2026-09-26 18:00, 1m
    验收提交        :2026-09-26 20:00, 1m
    归档            :2026-09-26 21:00, 1m
    
    section rtm-traceability.yml
    立项创建        :2026-09-26 10:00, 1m
    设计映射生成     :2026-09-26 14:00, 1m
    任务映射生成     :2026-09-26 15:30, 1m
    测试映射生成     :2026-09-26 20:00, 1m
```

**结论**：
- lifecycle: 11 次更新（频繁）
- traceability: 4 次更新（稳定）

---

## ✅ 实施计划

```mermaid
gantt
    title RTM YAML 实施计划（2个工作日）
    dateFormat YYYY-MM-DD
    
    section 阶段1：后端生成
    RTM 初始化逻辑     :a1, 2026-09-27, 2h
    RTM 更新逻辑（7个触发点）  :a2, after a1, 4h
    测试生成流程       :a3, after a2, 2h
    
    section 阶段2：前端集成
    StageOverview 集成  :b1, after a3, 2h
    会话节点追溯 Tab    :b2, after b1, 3h
    样式调整          :b3, after b2, 2h
    
    section 阶段3：测试验证
    E2E 测试          :c1, after b3, 2h
    修复问题          :c2, after c1, 1h
```

**总工作量**：14-16 小时（2 个工作日）
