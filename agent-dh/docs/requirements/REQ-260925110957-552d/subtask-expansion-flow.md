# 方案C（混合模式）：子卡拆分流程图

```mermaid
flowchart TD
    Start([开始：需求进入 decomposing]) --> Planning[Agent 规划任务]
    
    Planning --> DeclareStages{为每个任务<br/>声明 stages}
    
    DeclareStages -->|纯代码| S1["stages: ['implement', 'test']"]
    DeclareStages -->|需联调| S2["stages: ['implement', 'integrate', 'test']"]
    DeclareStages -->|复杂任务| S3["stages: ['analysis', 'implement', 'test', 'review']"]
    DeclareStages -->|纯文档| S4["stages: ['doc']"]
    
    S1 --> DocTable[生成 decomposition.md<br/>任务表含 stages 字段]
    S2 --> DocTable
    S3 --> DocTable
    S4 --> DocTable
    
    DocTable --> HumanReview{人工审批}
    
    HumanReview -->|拒绝| Planning
    HumanReview -->|批准| Decompose[reqboard_decompose 落库]
    
    Decompose --> CreateParents[创建 23 个父卡<br/>✅ 带 stages 字段<br/>❌ 不创建子卡]
    
    CreateParents --> ToImpl[需求 → implementing]
    
    ToImpl --> AdvanceLoop([advanceRequirement 循环开始])
    
    AdvanceLoop --> SelectEvent[selectAdvanceEvent<br/>选择下一个事件]
    
    SelectEvent -->|优先1| CheckFinalize{某父卡子卡<br/>全部 done?}
    CheckFinalize -->|是| FinalizeParent[FINALIZE_PARENT<br/>收尾父卡]
    FinalizeParent --> AdvanceLoop
    CheckFinalize -->|否| CheckSubtask
    
    SelectEvent -->|优先2| CheckSubtask{某父卡有<br/>ready 子卡?}
    CheckSubtask -->|是| RunSubtask[RUN_SUBTASK<br/>执行子卡]
    RunSubtask --> AdvanceLoop
    CheckSubtask -->|否| CheckOpenParent
    
    SelectEvent -->|优先3| CheckOpenParent{有 ready 父卡<br/>且未超并发?}
    CheckOpenParent -->|是| OpenParent[OPEN_PARENT<br/>父卡开工]
    CheckOpenParent -->|否| CheckRollup
    
    OpenParent --> ExpandSubtasks[expandSubtasks<br/>读取 stages 字段]
    
    ExpandSubtasks --> CreateChildren[创建 5-7 个子卡<br/>同一事务原子操作]
    
    CreateChildren -->|子卡链| Child1[子卡1: 领域类型定义·implement]
    CreateChildren --> Child2[子卡2: 领域类型定义·test]
    
    Child1 --> InProgress[父卡 → in_progress]
    Child2 --> InProgress
    
    InProgress --> AdvanceLoop
    
    SelectEvent -->|优先4| CheckRollup{全部父卡 done?}
    CheckRollup -->|是| Rollup[ROLLUP<br/>需求 → accepting]
    CheckRollup -->|否| Noop
    
    Rollup --> End([结束：进入验收])
    
    SelectEvent -->|无事件| Noop[返回 undefined<br/>noop 计数+1]
    Noop --> CheckStagnation{连续 5 次 noop?}
    CheckStagnation -->|是| Pause[PAUSE 停滞熔断<br/>autoRun = false]
    CheckStagnation -->|否| LoopEnd
    Pause --> End2([结束：链暂停])
    
    LoopEnd[循环结束] --> End3([返回结果])
    
    style Start fill:#e1f5e1
    style End fill:#ffe1e1
    style End2 fill:#ffe1e1
    style End3 fill:#e1e1ff
    style OpenParent fill:#fff4e1
    style ExpandSubtasks fill:#fff4e1
    style CreateChildren fill:#fff4e1
    style CreateParents fill:#e1f0ff
    style DeclareStages fill:#e1f0ff
    style DocTable fill:#e1f0ff
```

## 关键时间点对比

### 拆分阶段（decomposing）
- ✅ **声明 stages**：Agent 在规划时确定每个任务的阶段
- ✅ **人工审批**：能看到每个任务的 stages 划分
- ✅ **落库父卡**：reqboard_decompose 创建 23 个父卡（带 stages 字段）
- ❌ **不创建子卡**：此时子卡还不存在

### 实施阶段（implementing）
- ✅ **懒展开**：父卡开工时才创建子卡
- ✅ **原子操作**：父卡状态变更 + 子卡创建在同一事务
- ✅ **按需创建**：只为需要执行的父卡创建子卡
- ✅ **依赖执行**：子卡按依赖链串行执行

## 数据流示例

```typescript
// 1. 拆分阶段：decomposition.md
const plan = {
  tasks: [
    {
      key: 't1',
      title: '领域类型定义',
      stages: ['implement', 'test'],  // ← 此时声明
      dependsOn: [],
      acceptance: '...',
      implementation: '...'
    }
  ]
}

// 2. reqboard_decompose 落库
const parentTask = {
  id: 't-cda91b',
  title: '领域类型定义',
  stages: ['implement', 'test'],  // ← 写入父卡
  status: 'todo',
  parentId: undefined,  // ← 是父卡
  // ... 其他字段
}

// 3. 实施阶段：OPEN_PARENT
advanceRequirement()
  → selectAdvanceEvent() 
  → OPEN_PARENT(t-cda91b)
  → expandSubtasks(parentTask)  // ← 读取 stages
  → 创建子卡：
    [
      { id: 'sub-1', title: '领域类型定义·implement', parentId: 't-cda91b' },
      { id: 'sub-2', title: '领域类型定义·test', parentId: 't-cda91b' }
    ]

// 4. 执行子卡
RUN_SUBTASK(sub-1) → done
RUN_SUBTASK(sub-2) → done
FINALIZE_PARENT(t-cda91b) → done

// 5. 继续下一个父卡...
```

## 对比当前问题

### 当前问题（REQ-260925110957-552d）
```
拆分时：创建 23 个父卡，❌ 没有 stages 字段
实施时：expandSubtasks 读不到 stages → 返回空数组
结果：父卡开工但没有子卡 → 选择器找不到 RUN_SUBTASK 事件
状态：前 10 个任务莫名其妙完成了，第 11 个开始永久 todo
```

### 方案C 修复后
```
拆分时：创建 23 个父卡，✅ 带 stages: ['implement', 'test']
实施时：expandSubtasks 读取 stages → 创建 2 个子卡
结果：父卡 in_progress + 子卡链 todo → 选择器找到 RUN_SUBTASK
状态：子卡执行 → done → FINALIZE_PARENT → 下一个父卡
```
