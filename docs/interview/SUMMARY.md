# AI Agent 面试题库 - 快速总结

## 🎯 核心知识点速查

### 1. Agent架构（必考）

```
用户交互层
    ↓
Agent核心层（对话管理、任务规划、执行引擎、记忆系统、工具注册、反思模块）
    ↓
工具层（文件、搜索、API、计算、代码执行等）
    ↓
基础设施层（LLM、向量DB、缓存、监控）
```

**核心模块：**
- SessionManager: 会话管理
- Planner: 任务规划
- Executor: 执行引擎  
- Memory: 记忆系统
- ToolRegistry: 工具注册
- Reflection: 反思模块

### 2. 记忆系统（高频）

**三层架构：**
```
工作记忆 (Working Memory)
  ↓ 重要信息沉淀
短期记忆 (Short-term Memory, 24h-7天, Redis)
  ↓ 高价值信息固化
长期记忆 (Long-term Memory, 永久, VectorDB)
```

**静态 vs 动态：**
- **静态**：用户画像、项目文档、领域知识（低频更新）
- **动态**：对话历史、任务结果、用户反馈（高频更新）

**召回策略：**
- 语义相似度 + 时间衰减 + 重要性评分

### 3. 上下文管理（必考）

**优先级（P0-P4）：**
```
P0 (100%): 系统Prompt、用户输入、工具调用历史
P1 (90%):  最近对话、当前文件
P2 (70%):  相关代码、项目配置
P3 (40%):  历史记忆
P4 (20%):  示例代码
```

**压缩策略：**
- 滚动窗口: 保留最近N条
- 智能摘要: LLM压缩中间对话
- 分层缓存: 热温冷数据分离

### 4. 单Agent vs 多Agent

**选单Agent：**
- ✅ 任务规模小-中等
- ✅ 预算有限
- ✅ 需要连贯上下文

**选多Agent：**
- ✅ 高度复杂任务
- ✅ 需要专业领域知识
- ✅ 可并行提升效率

**协作模式：**
- 串行: Pipeline
- 并行: Fan-out/Fan-in
- 层级: Manager-Worker
- 辩论: Debate

### 5. 任务拆分

**SMART原则：**
- Specific（具体的）
- Measurable（可衡量的）
- Achievable（可实现的）
- Relevant（相关的）
- Time-bound（有时限的）

**粒度决策：**
- 粗粒度: 2-4小时/任务（紧急简单）
- 中粒度: 30-60分钟/任务 ✅ 推荐
- 细粒度: 5-15分钟/任务（复杂关键）

### 6. 提示词评估

**评估指标：**
| 指标 | 目标 | 权重 |
|------|------|------|
| 准确率 | >90% | 40% |
| 鲁棒性 | >0.85 | 20% |
| Token效率 | 越低越好 | 20% |
| 响应时间 | <2s | 10% |
| 用户满意度 | >80% | 10% |

**评估方法：**
- 离线评估: 测试集 + 指标计算
- A/B测试: 生产环境对比
- 用户反馈: 点赞率、修改次数

### 7. 成本优化

**模型选择：**
```
简单任务 → GPT-3.5 Turbo ($0.5/1M)
中等任务 → GPT-4o ($5/1M)
复杂任务 → Claude 3.5 Sonnet ($3/1M)
性价比 → DeepSeek ($0.14/1M) ⭐
```

**优化策略：**
1. 分层模型（60%简单+30%中等+10%复杂）
2. 提示词缓存（节省90% tokens）
3. 输出长度控制
4. 批处理

**1000行代码成本：**
- Claude 3.5 Sonnet: $0.31
- DeepSeek: $0.006（节省98%）

### 8. 框架选型

| 框架 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **自研** | 复杂定制 | 完全可控 | 开发成本高 |
| **LangChain** | 标准RAG | 生态丰富 | 抽象过度 |
| **LangGraph** | 复杂工作流 | 可视化 | 学习曲线陡 |
| **Coze** | 快速验证 | 零代码 | 灵活性差 |

**决策树：**
```
POC验证? → Yes → Coze/Dify
标准RAG? → Yes → LangChain
复杂流程? → Yes → LangGraph
深度定制? → Yes → 自研
```

## 🔥 面试必背

### Top 10 核心概念

1. **ReAct范式**: Reasoning + Acting（思考→行动→观察循环）
2. **Function Calling**: LLM输出结构化工具调用请求
3. **RAG**: Retrieval-Augmented Generation（检索增强生成）
4. **Few-shot Learning**: 通过示例引导输出
5. **CoT**: Chain-of-Thought（思维链提示）
6. **Embedding**: 文本向量化（用于语义检索）
7. **Token**: LLM的最小处理单元（约等于0.75个英文单词）
8. **Temperature**: 控制输出随机性（0=确定，1=随机）
9. **Context Window**: 模型能处理的最大token数
10. **Hallucination**: 模型生成不准确或虚构的内容

### 加分回答模板

**架构设计类：**
```
1. 总体架构（画图）
2. 核心模块职责
3. 数据流向
4. 技术选型理由
5. 遇到的问题和解决方案
```

**技术深度类：**
```
1. 原理解释（概念定义）
2. 代码示例（可运行）
3. 优缺点分析
4. 适用场景
5. 最佳实践
```

**项目经验类：**
```
1. 背景和目标
2. 技术架构
3. 关键难点
4. 解决方案（带数据）
5. 成果和反思
```

### 常见追问及应对

**Q: "为什么这么设计？"**
→ 讲清楚权衡（performance vs complexity, cost vs quality）

**Q: "有没有考虑过其他方案？"**
→ 至少说出2-3个替代方案，对比优劣

**Q: "实际效果怎么样？"**
→ 用数据说话（准确率、响应时间、成本、用户满意度）

**Q: "遇到过什么问题？"**
→ 诚实说出问题 + 如何解决 + 学到什么

**Q: "如果重新做会怎么设计？"**
→ 反思不足 + 改进方向（体现成长性）

## 📊 关键数据记忆

### Token消耗
- 1行代码 ≈ 15-25 tokens
- 1000字中文 ≈ 1500-2000 tokens
- 系统Prompt ≈ 2000-5000 tokens

### 成本参考（每百万tokens）
- GPT-4 Turbo: $10 (输入) / $30 (输出)
- GPT-4o: $5 / $15
- Claude 3.5 Sonnet: $3 / $15
- GPT-3.5 Turbo: $0.5 / $1.5
- DeepSeek: $0.14 / $0.28

### 上下文窗口
- GPT-4 Turbo: 128K
- Claude 3.5 Sonnet: 200K
- GPT-3.5 Turbo: 16K
- Gemini 1.5 Pro: 1M

### 性能指标
- 响应时间: <2s（用户可接受）
- 准确率: >90%（生产可用）
- Token效率: <10K/请求（经济）

## 💡 面试技巧

### Do ✅
- 用具体数据（不是"很快"，而是"200ms"）
- 画图说明（架构图、流程图）
- 承认不足（没有完美方案）
- 主动关联（"这个和您刚才问的XX类似"）
- 反问面试官（显示思考深度）

### Don't ❌
- 只讲概念不讲实战
- 说不清为什么这么设计
- 把所有功劳归自己
- 对不懂的问题瞎编
- 批评前公司/团队

### 准备清单

**简历上的项目必须准备：**
- [ ] 5分钟讲清楚架构
- [ ] 说出3个关键技术难点
- [ ] 每个难点的解决方案
- [ ] 量化的成果数据
- [ ] 至少1个踩坑经验

**通用问题准备：**
- [ ] 自我介绍（2分钟版本）
- [ ] 为什么做Agent方向
- [ ] 最近在学什么
- [ ] 对Agent未来的看法
- [ ] 为什么选择我们公司

## 🎓 推荐学习资源

### 必读论文
- ReAct: Synergizing Reasoning and Acting in Language Models
- Reflexion: Language Agents with Verbal Reinforcement Learning
- Chain-of-Thought Prompting Elicits Reasoning in LLMs

### 框架文档
- LangChain: https://python.langchain.com/
- LangGraph: https://langchain-ai.github.io/langgraph/
- LlamaIndex: https://docs.llamaindex.ai/

### 实战项目
- AutoGPT: https://github.com/Significant-Gravitas/AutoGPT
- GPT Engineer: https://github.com/gpt-engineer-org/gpt-engineer
- Cursor: https://cursor.sh/

### 技术博客
- Anthropic: https://www.anthropic.com/research
- OpenAI: https://openai.com/research
- LangChain Blog: https://blog.langchain.dev/

---

**使用建议**：
1. 打印本文档随身携带
2. 面试前1小时快速过一遍
3. 重点记忆"必背"和"数据"部分
4. 结合自己项目准备具体案例

**祝面试顺利！🚀**

