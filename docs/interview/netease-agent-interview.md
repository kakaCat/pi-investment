# 网易 Agent 开发岗一面（2026年6月）

## 1. 自我介绍，重点介绍Agent相关项目经历

**答案：**

面试自我介绍的黄金结构（2-3分钟）：

```
"您好，我是XXX，主要从事AI Agent方向的研发工作。

【教育背景】简短一句话
本科/研究生毕业于XX大学计算机专业。

【核心项目经历】重点讲1-2个Agent项目

项目1：智能投资Agent系统（最近/最重要的）
- 背景：开发了一个自主运行的股票投资决策系统
- 技术栈：TypeScript + DeepSeek + LangChain，集成60+投资工具
- 架构：三层架构（Agent大脑 + 后端服务 + Web监控）
- 难点与解决：
  * 自主调度：实现cron-based任务调度，Agent每天自动执行投资分析
  * 记忆系统：设计分层记忆（工作记忆/短期/长期），支持上下文压缩
  * 工具编排：通过Skill体系实现工具分层和组合复用
- 成果：系统已稳定运行X个月，完成XX次自主决策

项目2：Coding Agent助手（如果有的话）
- 背景：辅助日常编程工作的AI助手
- 功能：代码生成、测试编写、代码审查、Bug修复
- 技术亮点：
  * RAG增强：使用GraphRAG建模代码调用关系
  * 上下文管理：实现智能压缩，支持128K上下文
  * 工具生态：集成文件操作、命令执行、LSP等20+工具
- 自用体验：每天使用，月均节省XX小时开发时间

【技术能力】
- Agent框架：熟练使用LangChain/LangGraph，深入理解ReAct/Plan-Execute范式
- 大模型：有GPT-4、Claude、DeepSeek等模型的实际应用经验
- 工程能力：TypeScript/Python全栈，熟悉微服务架构

【对Agent的理解】
我认为Agent的核心是：感知-规划-执行-反思的闭环。
不仅是简单的工具调用，而是具备自主决策、学习改进的能力。

期待能在贵司继续深耕Agent方向，很高兴有机会交流。"
```

**关键要点：**
- ✅ 突出Agent相关项目（不是泛泛的AI项目）
- ✅ 用数据说话（多少工具、运行多久、节省多少时间）
- ✅ 展示技术深度（不只是调用API，而是解决了实际问题）
- ✅ 体现理解深度（知道Agent的核心是什么）

## 2. Agent项目整体架构是什么？核心模块有哪些？

**答案：**

典型Agent系统的分层架构：

```
┌─────────────────────────────────────────────────────────┐
│                    用户交互层                            │
│  CLI / Web UI / API / 飞书Bot                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    Agent核心层                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 对话管理器   │  │  任务规划器  │  │  执行引擎    │ │
│  │ Session Mgr  │  │  Planner     │  │  Executor    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 记忆系统     │  │  工具注册表  │  │  反思模块    │ │
│  │ Memory       │  │  Tool Registry│  │  Reflection  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    工具层                                │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐        │
│  │文件  │ │搜索  │ │API   │ │计算  │ │代码  │ ...    │
│  │操作  │ │工具  │ │调用  │ │工具  │ │执行  │        │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  基础设施层                              │
│  LLM服务 | 向量数据库 | 缓存 | 监控 | 日志              │
└─────────────────────────────────────────────────────────┘
```

**核心模块详解：**

### 1. 对话管理器（Session Manager）
```typescript
class SessionManager {
  // 职责：
  // - 管理多轮对话状态
  // - 维护上下文窗口
  // - 触发上下文压缩
  
  sessions: Map<string, Session>
  
  async handleMessage(sessionId: string, message: string) {
    const session = this.getOrCreateSession(sessionId)
    session.addMessage(message)
    
    // 检查是否需要压缩
    if (session.tokenCount > threshold) {
      await session.compress()
    }
    
    return await this.agentLoop(session)
  }
}
```

### 2. 任务规划器（Planner）
```typescript
class TaskPlanner {
  // 职责：
  // - 理解用户意图
  // - 分解复杂任务
  // - 生成执行计划
  
  async plan(userInput: string, context: Context): Promise<Plan> {
    const intent = await this.understandIntent(userInput)
    
    if (intent.isSimple) {
      // 简单任务直接执行
      return { steps: [{ action: "execute", tool: intent.tool }] }
    } else {
      // 复杂任务分解
      return await this.decompose(intent)
    }
  }
  
  async decompose(intent: Intent): Promise<Plan> {
    const prompt = `
    任务: ${intent.description}
    可用工具: ${this.availableTools}
    
    请分解为可执行的步骤序列。
    `
    const plan = await llm.generate(prompt)
    return parsePlan(plan)
  }
}
```

### 3. 执行引擎（Executor）
```typescript
class Executor {
  // 职责：
  // - 执行计划中的每个步骤
  // - 调用相应的工具
  // - 处理工具执行结果
  
  async execute(plan: Plan): Promise<ExecutionResult> {
    const results = []
    
    for (const step of plan.steps) {
      try {
        const tool = this.toolRegistry.get(step.toolName)
        const result = await tool.execute(step.params)
        results.push(result)
        
        // 根据结果决定是否继续
        if (this.shouldStop(result)) break
      } catch (error) {
        // 错误处理和重试
        await this.handleError(error, step)
      }
    }
    
    return { results, success: true }
  }
}
```

### 4. 记忆系统（Memory System）
```typescript
class MemorySystem {
  workingMemory: Message[]      // 当前对话
  shortTermMemory: Redis         // 最近会话
  longTermMemory: VectorDB       // 知识库
  
  async recall(query: string): Promise<Memory[]> {
    // 多路召回
    const semantic = await this.longTermMemory.search(query)
    const recent = await this.shortTermMemory.get(sessionId)
    
    return this.merge(semantic, recent)
  }
  
  async consolidate() {
    // 定期将短期记忆固化到长期记忆
    const important = this.filterImportant(this.workingMemory)
    await this.longTermMemory.insert(important)
  }
}
```

### 5. 工具注册表（Tool Registry）
```typescript
class ToolRegistry {
  tools: Map<string, Tool>
  
  register(tool: Tool) {
    this.tools.set(tool.name, tool)
  }
  
  getSchema(): ToolSchema[] {
    // 返回所有工具的schema，用于Function Calling
    return Array.from(this.tools.values()).map(t => t.schema)
  }
  
  selectTools(context: Context): Tool[] {
    // 根据上下文智能选择相关工具（避免注入所有工具）
    return this.tools.filter(t => t.isRelevant(context))
  }
}
```

### 6. 反思模块（Reflection）
```typescript
class ReflectionModule {
  // 职责：
  // - 评估执行结果
  // - 发现错误并修正
  // - 从失败中学习
  
  async reflect(execution: ExecutionResult): Promise<Reflection> {
    const prompt = `
    执行结果: ${execution.output}
    是否达成目标: ${execution.goalAchieved}
    
    请评估：
    1. 结果是否正确？
    2. 如果有问题，原因是什么？
    3. 应该如何改进？
    `
    
    const reflection = await llm.generate(prompt)
    
    if (reflection.needsRetry) {
      return { action: "retry", improvedPlan: reflection.newPlan }
    }
    
    return { action: "accept", lessons: reflection.lessons }
  }
}
```

**数据流图：**

```
用户输入 
  ↓
SessionManager (管理会话)
  ↓
Memory.recall() (召回相关记忆)
  ↓
Planner.plan() (生成执行计划)
  ↓
Executor.execute() (执行工具调用)
  ↓
Reflection.reflect() (评估结果)
  ↓
  需要重试？
  Yes → 返回 Planner (重新规划)
  No → Memory.consolidate() (更新记忆)
  ↓
返回结果给用户
```

**实际项目示例（我的投资Agent系统）：**

```typescript
// 核心模块
src/
├── core/
│   ├── agent-loop.ts          // Agent主循环（ReAct实现）
│   ├── session-manager.ts     // 会话管理
│   └── context-manager.ts     // 上下文管理
│
├── planning/
│   ├── intent-recognizer.ts   // 意图识别
│   └── task-decomposer.ts     // 任务分解
│
├── memory/
│   ├── working-memory.ts      // 工作记忆
│   ├── conversation-store.ts  // 对话存储
│   └── knowledge-base.ts      // 知识库
│
├── tools/
│   ├── registry.ts            // 工具注册
│   ├── portfolio/             // 投资组合工具
│   ├── market/                // 市场数据工具
│   └── analysis/              // 分析工具
│
└── services/
    ├── scheduler.ts           // 定时任务
    ├── notification.ts        // 通知服务
    └── audit-logger.ts        // 审计日志
```

## 3. 项目中用了哪些框架（LangChain、Coze）？为什么选、优缺点？

**答案：**

### 主流Agent框架对比

| 框架 | 类型 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| **LangChain** | 代码框架 | 生态丰富、灵活度高 | 抽象过度、文档混乱 | 复杂定制需求 |
| **LangGraph** | 状态机框架 | 流程可视化、易调试 | 学习曲线陡 | 多步骤工作流 |
| **Coze** | 低代码平台 | 零代码、快速上线 | 灵活性受限 | 标准业务场景 |
| **Dify** | 开源平台 | 开箱即用、UI友好 | 定制困难 | MVP快速验证 |
| **AutoGPT** | 自主Agent | 高度自主 | 不稳定、成本高 | 研究探索 |

### 我的选择和原因

**项目1：投资Agent系统 - 自研框架**

```typescript
// 为什么不用现成框架？

// 原因1：特殊需求
// - 需要定时自主运行（不是纯对话式）
// - 需要复杂的投资工具编排
// - 需要深度定制记忆系统

// 原因2：LangChain的问题
// ❌ 过度抽象：Chain、Agent、Memory、Tool等概念层层嵌套
// ❌ 版本不稳定：API频繁breaking change
// ❌ 调试困难：错误堆栈很深，难以定位问题
// ❌ 性能开销：很多不需要的中间层

// 解决方案：轻量级自研
class SimpleAgentLoop {
  async run(input: string): Promise<string> {
    let thought = input
    let iterations = 0
    const maxIterations = 10
    
    while (iterations < maxIterations) {
      // 1. 思考下一步
      const action = await this.think(thought)
      
      // 2. 执行工具
      if (action.type === 'tool_call') {
        const result = await this.executeTool(action)
        thought = `Tool result: ${result}`
      } else if (action.type === 'final_answer') {
        return action.answer
      }
      
      iterations++
    }
    
    throw new Error('Max iterations reached')
  }
}

// 优点：
// ✅ 代码简洁（核心逻辑50行）
// ✅ 易于调试（清晰的执行流程）
// ✅ 性能好（无额外抽象）
// ✅ 可控性强（完全掌握每个细节）
```

**项目2：如果是标准RAG应用 - LangChain**

```python
# 对于标准的RAG应用，LangChain还是不错的选择

from langchain.vectorstores import Pinecone
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA

# 优点：快速搭建
vectorstore = Pinecone.from_documents(docs, OpenAIEmbeddings())
qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(),
    retriever=vectorstore.as_retriever()
)

answer = qa_chain.run("问题")

# 适用场景：
# ✅ 标准RAG应用（文档问答）
# ✅ 简单的工具调用
# ✅ 快速POC验证
# ❌ 复杂的多步骤工作流
# ❌ 需要深度定制
```

**项目3：复杂工作流 - LangGraph**

```python
# LangGraph适合有明确状态转换的场景

from langgraph.graph import StateGraph

# 定义状态
class AgentState(TypedDict):
    messages: List[Message]
    next_action: str

# 构建图
workflow = StateGraph(AgentState)

workflow.add_node("analyze", analyze_node)
workflow.add_node("execute", execute_node)
workflow.add_node("verify", verify_node)

workflow.add_edge("analyze", "execute")
workflow.add_conditional_edges(
    "execute",
    should_verify,
    {
        "verify": "verify",
        "end": END
    }
)

app = workflow.compile()

# 优点：
# ✅ 流程可视化（可以画出状态机图）
# ✅ 易于调试（可以看到每个状态转换）
# ✅ 支持循环和条件分支
# ✅ 可以持久化状态（中断恢复）

# 缺点：
# ❌ 概念较复杂（State、Node、Edge）
# ❌ 简单任务会显得过度设计
```

**项目4：快速验证 - Coze**

```
Coze低代码平台：

优点：
✅ 零代码：拖拽式搭建
✅ 快速上线：1小时搭建MVP
✅ 内置工具：天气、搜索、知识库等
✅ 多渠道发布：微信、飞书、网页

缺点：
❌ 黑盒：无法查看底层实现
❌ 受限：只能用平台提供的能力
❌ 数据：数据存在平台上
❌ 成本：按调用次数收费

适用场景：
✅ 业务人员快速验证想法
✅ 标准化客服、助手场景
❌ 需要深度定制的场景
❌ 对数据安全有要求的场景
```

### 选择框架的决策树

```
开始
  ↓
是POC快速验证？
  Yes → Coze/Dify (低代码平台)
  No ↓
  
是标准RAG应用？
  Yes → LangChain (生态成熟)
  No ↓
  
有复杂的状态流转？
  Yes → LangGraph (状态机)
  No ↓
  
需要深度定制？
  Yes → 自研框架 (完全控制)
  No → LangChain (快速开发)
```

### 我的最终选择理由

```
投资Agent系统选择自研，因为：

1. **定时自主运行需求**
   - 不是传统的"用户问-Agent答"模式
   - 需要cron调度，每天自动执行任务
   - 现成框架都是被动响应式的

2. **复杂的工具编排**
   - 60+投资工具，需要分层管理
   - 工具之间有依赖关系
   - 需要动态选择工具子集

3. **特殊的记忆需求**
   - 需要记住投资组合状态
   - 需要学习历史决策的效果
   - 需要跨会话的长期记忆

4. **性能和成本考虑**
   - LangChain的抽象层带来额外开销
   - 自研可以精确控制token消耗
   - 每次运行都要优化成本

5. **可维护性**
   - 框架升级可能break现有代码
   - 自研代码完全掌控，易于调试
   - 团队可以快速理解核心逻辑

结论：
- 简单应用 → 用框架（快速）
- 复杂应用 → 自研（可控）
- 我的项目属于后者
```

