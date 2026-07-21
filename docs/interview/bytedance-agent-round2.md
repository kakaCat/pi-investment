# 字节跳动 Agent 二面高频题整理

## 1. 自我介绍

**答案：**
在自我介绍中应该重点突出：
- Agent相关项目经验（开发过哪些Agent系统）
- 技术栈：使用的框架（LangChain、LangGraph等）、模型（GPT-4、Claude等）
- 解决的实际问题和取得的成果
- 对Agent架构的理解深度

示例框架：
"我是XXX，主要做AI Agent方向的开发。最近在做一个自动化编程助手项目，基于LangChain框架，集成了代码生成、测试、调试等多个工具。项目中实现了RAG增强的代码理解能力，通过Graph数据库建模代码调用关系。目前系统能够自动完成中等复杂度的编程任务，准确率达到XX%。"

## 2. 编点？有论文么？有实习么？

**答案：**
这是了解候选人学术背景和实践经验的问题。应该：

- **编程经验**：说明有多少年编程经验，熟练掌握哪些语言
- **论文发表**：如果有相关论文（AI、NLP、Agent方向），简要介绍研究内容
- **实习经历**：重点讲与AI/Agent相关的实习，突出技术深度和项目成果

## 3. 整个链路运转的流程？

**答案：**
一个完整的Agent运转流程通常包括：

```
用户输入 → Prompt工程 → 意图理解 → 任务规划(Planning) 
→ 工具选择 → 工具调用 → 结果解析 → 反思(Reflection) 
→ 记忆更新 → 响应生成 → 用户输出
```

**详细说明：**
1. **输入处理**：接收用户请求，进行预处理和安全检查
2. **意图理解**：通过LLM理解用户真实意图
3. **任务分解**：将复杂任务分解为可执行的子任务
4. **工具调用**：根据任务选择合适的工具（Function Calling）
5. **执行与监控**：执行工具调用，监控执行状态
6. **结果聚合**：整合多个工具的输出
7. **反思机制**：评估结果质量，必要时重新规划
8. **记忆管理**：更新短期和长期记忆
9. **响应生成**：生成最终答案返回用户

## 4. skill分层体系是怎么做，为什么这么设计？

**答案：**

Skill分层体系采用**信息分层架构**（按访问阶段分层），而非功能分层。这是为了优化Agent的工具发现和推理成本：

### 三层信息架构

```
┌─────────────────────────────────────────────────────────┐
│ 索引层 (Index Layer) - YAML Frontmatter                 │
│ • 位置：SKILL.md 文件的 YAML 前置元数据                  │
│ • 内容：name + description (仅摘要)                     │
│ • 成本：~100 tokens per skill                          │
│ • 加载时机：Agent启动时一次性加载所有技能索引            │
│                                                         │
│ 作用：工具发现 (Tool Discovery)                          │
│ Agent扫描所有技能摘要，决定调用哪个                       │
└─────────────────────────────────────────────────────────┘
                        ↓ Agent选择某个技能后
┌─────────────────────────────────────────────────────────┐
│ 指令层 (Instruction Layer) - Markdown 正文               │
│ • 位置：SKILL.md 的 Markdown 正文部分                    │
│ • 内容：详细使用指南、参数说明、Few-Shot 示例             │
│ • 成本：~2K-5K tokens per skill                        │
│ • 加载时机：Agent决定使用该技能时动态加载                 │
│                                                         │
│ 作用：用户手册 (相当于 --help)                           │
│ 告诉Agent如何正确使用这个技能，处理边缘情况               │
└─────────────────────────────────────────────────────────┘
                        ↓ Agent构造参数并调用
┌─────────────────────────────────────────────────────────┐
│ 执行层 (Execution Layer) - 实际代码                      │
│ • 位置：Python脚本/TypeScript函数/CLI命令/Docker容器     │
│ • 内容：真正的可执行逻辑                                 │
│ • 成本：执行时间和计算资源                               │
│                                                         │
│ 作用：执行任务 (Task Execution)                          │
│ 接收参数，执行计算，返回结果                              │
└─────────────────────────────────────────────────────────┘
```

### 实际案例

**索引层示例** (agent-ts/skills/portfolio-analyze.md)
```yaml
---
name: portfolio-analyze
description: 分析持仓组合的风险收益特征，生成投资建议
---
```

**指令层示例** (同一文件的Markdown正文)
```markdown
## 功能说明
分析持仓组合的风险收益特征，包括夏普比率、最大回撤、持仓集中度等...

## 参数
- `portfolio_id` (必填): 组合ID
- `analysis_type` (可选): 分析类型，默认为 "full"
  - "full": 完整分析
  - "risk": 仅风险分析
  - "performance": 仅收益分析

## 使用示例
```
分析我的持仓组合
分析组合 PORTFOLIO_001 的风险
```

## 注意事项
- 需要至少3个月的历史数据
- 空仓时返回默认风险评级
```

**执行层示例**
```typescript
// src/infrastructure/tools/portfolio/portfolio-analyze-tool.ts
export const portfolioAnalyzeTool = {
  name: 'portfolio-analyze',
  execute: async (id: string, params: AnalyzeParams) => {
    const data = await quantV2Client.get(`/api/portfolio/${id}`);
    const analysis = calculateMetrics(data);
    return formatAnalysisResult(analysis);
  }
}
```

### 设计原因

**1. 推理成本优化**
- ❌ **传统做法**：一次性加载所有技能的详细文档
  - 60个技能 × 3K tokens = 180K tokens（每次对话都消耗）
- ✅ **分层做法**：启动时只加载索引
  - 索引层：60个技能 × 100 tokens = 6K tokens
  - 指令层：按需加载 1-3 个技能 × 3K = 9K tokens
  - **节省 >90% 推理成本**

**2. 符合LLM认知模式**
- Markdown是LLM最"原生"的理解格式（训练语料中大量存在）
- 比JSON Schema传递更丰富的语义细微差别
- Few-Shot示例帮助LLM理解边缘情况和用户意图

**3. 模拟人类使用工具的过程**
```bash
# 第一步：浏览工具列表（索引层）
$ ls /usr/bin | grep git
git, gitk, git-flow...

# 第二步：查看某个工具的帮助（指令层）
$ git --help
GIT(1)                    Git Manual                    GIT(1)
NAME
       git - the stupid content tracker
SYNOPSIS
       git [--version] [--help] [-C <path>]...

# 第三步：执行命令（执行层）
$ git commit -m "fix: correct skill layering"
```

**4. 支持动态扩展**
- 新增技能只需添加一个SKILL.md文件
- Agent自动发现并集成
- 无需修改核心代码

### 与功能分层的区别

**⚠️ 常见误区：混淆信息架构与功能架构**

| 维度 | 信息架构（正确） | 功能架构（混淆概念） |
|------|-----------------|-------------------|
| 目的 | 优化Agent工具发现流程 | 组织工具的复杂度层次 |
| 分层依据 | 访问阶段（发现→学习→执行） | 功能复杂度（原子→基础→复合） |
| 层次 | Index → Instruction → Execution | Tool → Skill → Composite Skill |
| 解决问题 | 如何高效发现和使用工具 | 如何组合简单工具构建复杂能力 |
| 典型实现 | Claude Code, Cursor, Continue | LangChain (ToolKit) |

两种架构**可以共存**：
- 信息架构：定义Agent如何访问工具（访问协议）
- 功能架构：定义工具如何组织（能力组织）

例如：一个"代码重构"的复合Skill（功能架构L3），仍然需要通过索引层→指令层→执行层（信息架构）被Agent调用。

## 5. 用户输入怎么和相关skill匹配？

**答案：**

Skill匹配通常采用以下策略：

**方法1：语义匹配（推荐）**
```python
# 1. 为每个Skill准备描述和示例
skills = {
    "code_gen": {
        "description": "生成代码，实现特定功能",
        "examples": ["写一个排序函数", "实现用户登录接口"]
    },
    "code_review": {
        "description": "审查代码质量，发现潜在问题",
        "examples": ["检查这段代码", "帮我review"]
    }
}

# 2. 用户输入编码
user_input_embedding = embed(user_input)

# 3. 计算相似度
for skill_name, skill_info in skills.items():
    skill_embedding = embed(skill_info["description"] + skill_info["examples"])
    similarity = cosine_similarity(user_input_embedding, skill_embedding)
    
# 4. 选择Top-K最相关的Skill
```

**方法2：LLM路由**
```python
prompt = f"""
用户输入: {user_input}

可用Skill列表:
1. code_gen - 代码生成
2. code_review - 代码审查  
3. debug - 调试代码

请选择最合适的Skill（输出Skill名称）
"""
selected_skill = llm.generate(prompt)
```

**方法3：规则+语义混合**
- 先用规则（关键词）快速过滤
- 再用语义相似度精确匹配
- 最后用LLM做final决策

## 6. 有skill沉淀机制么？还是只能用户自己构造？

**答案：**

好的Agent系统应该有**自动Skill沉淀机制**：

**1. 使用模式学习**
```python
# 记录用户高频使用的Skill组合
skill_usage_log = {
    "user_id": "user123",
    "pattern": ["code_gen", "test_gen", "code_review"],
    "frequency": 50,
    "success_rate": 0.85
}

# 自动创建复合Skill
if pattern.frequency > threshold:
    create_composite_skill(pattern)
```

**2. 成功案例固化**
```python
# 当某个任务执行成功时，保存为Skill模板
if task.success:
    new_skill = {
        "name": f"auto_skill_{timestamp}",
        "description": task.description,
        "steps": task.execution_steps,
        "tools": task.used_tools,
        "prompt_template": task.prompt
    }
    skill_library.add(new_skill)
```

**3. 用户反馈驱动**
```python
# 用户可以保存当前会话为Skill
@command("/save-as-skill")
def save_conversation_as_skill(conversation):
    skill = extract_skill_from_conversation(conversation)
    skill_library.add(skill)
    return f"Skill '{skill.name}' 已保存"
```

**4. 跨用户共享（可选）**
- 将高质量Skill上传到中央库
- 其他用户可以搜索和下载
- 类似GitHub的Skill市场

## 7. 长短期记忆怎么设计的？

**答案：**

记忆系统的分层设计：

```
┌─────────────────────────────────────────┐
│  工作记忆 (Working Memory)               │
│  当前对话上下文，容量：4K-8K tokens       │
│  生命周期：当前会话                       │
└─────────────────────────────────────────┘
            ↓ 重要信息沉淀
┌─────────────────────────────────────────┐
│  短期记忆 (Short-term Memory)            │
│  最近N次对话的摘要                        │
│  生命周期：24小时-7天                     │
│  存储：内存/Redis                         │
└─────────────────────────────────────────┘
            ↓ 高价值信息固化
┌─────────────────────────────────────────┐
│  长期记忆 (Long-term Memory)             │
│  用户偏好、项目上下文、知识库             │
│  生命周期：永久                           │
│  存储：向量数据库（Pinecone/Weaviate）   │
└─────────────────────────────────────────┘
```

**实现细节：**

```python
class MemorySystem:
    def __init__(self):
        self.working_memory = []  # 当前上下文
        self.short_term_db = Redis()  # 短期记忆
        self.long_term_db = VectorDB()  # 长期记忆
        
    def add_message(self, message):
        # 添加到工作记忆
        self.working_memory.append(message)
        
        # 检查是否需要压缩
        if self.get_token_count() > MAX_TOKENS:
            self.compress_working_memory()
            
    def compress_working_memory(self):
        # 提取关键信息
        summary = llm.summarize(self.working_memory)
        
        # 移到短期记忆
        self.short_term_db.set(
            key=f"session_{session_id}",
            value=summary,
            ex=86400  # 24小时过期
        )
        
        # 清理工作记忆
        self.working_memory = self.working_memory[-5:]  # 保留最近5条
        
    def save_to_long_term(self, content, importance_score):
        if importance_score > 0.7:  # 重要信息才保存
            embedding = embed(content)
            self.long_term_db.insert({
                "content": content,
                "embedding": embedding,
                "timestamp": now(),
                "importance": importance_score
            })
            
    def recall(self, query):
        # 从长期记忆中检索相关信息
        results = self.long_term_db.search(
            query_embedding=embed(query),
            top_k=5
        )
        return results
```

## 8. 为什么要静态长期记忆和动态长期记忆？

**答案：**

**静态长期记忆（Static Long-term Memory）**
- **定义**：不随对话变化的固定知识
- **内容**：
  - 用户画像（职业、技术栈、偏好）
  - 项目文档（README、API文档）
  - 领域知识库（编程最佳实践）
- **更新频率**：低（手动更新或定期批量更新）
- **存储**：向量数据库 + 结构化数据库

**动态长期记忆（Dynamic Long-term Memory）**
- **定义**：随对话不断积累的经验
- **内容**：
  - 历史对话摘要
  - 用户反馈记录
  - 任务执行结果
- **更新频率**：高（每次对话后更新）
- **存储**：向量数据库（支持增量更新）

**为什么要分开？**

1. **检索效率**
   - 静态记忆：可以预先索引，检索快
   - 动态记忆：需要支持实时写入

2. **更新策略**
   - 静态记忆：批量更新，保证一致性
   - 动态记忆：增量更新，保证实时性

3. **存储成本**
   - 静态记忆：可以用更便宜的存储
   - 动态记忆：需要更快的读写性能

4. **召回策略**
   - 静态记忆：根据语义相似度召回
   - 动态记忆：根据时间近度+语义相似度

**示例实现：**
```python
class HybridMemory:
    def __init__(self):
        self.static_memory = StaticVectorDB()  # 项目文档等
        self.dynamic_memory = DynamicVectorDB()  # 对话历史
        
    def recall(self, query):
        # 从两个库中分别检索
        static_results = self.static_memory.search(query, top_k=3)
        dynamic_results = self.dynamic_memory.search(
            query, 
            top_k=2,
            time_decay=True  # 动态记忆加入时间衰减
        )
        
        # 合并结果
        return self.merge_results(static_results, dynamic_results)
```

## 9. 每一轮对话触发一次长期记忆存储，有没有出现用户长期记忆快速积累，存的过多？

**答案：**

这确实是一个实际问题。解决方案：

**问题表现：**
- 长期记忆膨胀，检索变慢
- 存储成本上升
- 检索噪音增加（召回不相关的旧记忆）

**解决方案：**

**1. 重要性过滤**
```python
def should_save_to_long_term(message):
    # 只保存重要信息
    importance_score = calculate_importance(message)
    
    # 过滤条件
    if importance_score < 0.7:
        return False
    if is_chitchat(message):
        return False
    if is_duplicate(message):
        return False
        
    return True
```

**2. 记忆合并（Memory Consolidation）**
```python
# 定期合并相似记忆
def consolidate_memories():
    memories = fetch_recent_memories(days=7)
    clusters = cluster_similar_memories(memories)
    
    for cluster in clusters:
        # 将相似记忆合并为一条
        merged = llm.summarize(cluster)
        save_merged_memory(merged)
        delete_memories(cluster)
```

**3. 时间衰减（Temporal Decay）**
```python
def calculate_memory_score(memory):
    semantic_score = cosine_similarity(query, memory.embedding)
    time_decay = math.exp(-lambda * days_ago(memory.timestamp))
    importance = memory.importance_score
    
    # 综合得分
    return semantic_score * time_decay * importance
```

**4. 主动遗忘（Forgetting Mechanism）**
```python
# 定期清理低价值记忆
@scheduled(cron="0 2 * * *")  # 每天凌晨2点
def forget_low_value_memories():
    memories = fetch_all_memories()
    
    for memory in memories:
        # 计算记忆价值
        value = (
            memory.access_count * 0.3 +  # 被访问次数
            memory.importance * 0.5 +     # 重要性
            memory.recency * 0.2          # 新鲜度
        )
        
        if value < threshold:
            delete_memory(memory.id)
```

**5. 分级存储**
```python
# 热数据：最近7天，存Redis
# 温数据：7-30天，存向量数据库
# 冷数据：30天以上，归档到对象存储
def tiered_storage(memory):
    age = days_ago(memory.timestamp)
    
    if age < 7:
        redis.set(memory.id, memory)
    elif age < 30:
        vector_db.insert(memory)
    else:
        s3.archive(memory)
```


## 10. 大模型怎么决定长期记忆是否需要召回？

**答案：**

长期记忆召回决策通常采用**混合策略**：

**方法1：语义相似度召回**
```python
def semantic_recall(query):
    # 1. 查询编码
    query_embedding = embed(query)
    
    # 2. 向量检索
    candidates = vector_db.search(
        query_embedding,
        top_k=20,  # 先召回较多候选
        threshold=0.7  # 相似度阈值
    )
    
    # 3. 重排序
    reranked = rerank_model.score(query, candidates)
    return reranked[:5]  # 返回Top-5
```

**方法2：LLM主动决策**
```python
def llm_driven_recall(query, context):
    decision_prompt = f"""
    用户查询: {query}
    当前上下文: {context}
    
    是否需要检索历史记忆？
    如果需要，应该检索什么类型的信息？
    
    回答格式:
    {{
        "need_recall": true/false,
        "recall_query": "具体检索查询",
        "reason": "原因"
    }}
    """
    
    decision = llm.generate(decision_prompt, response_format="json")
    
    if decision["need_recall"]:
        return vector_db.search(decision["recall_query"])
    return []
```

**方法3：规则+语义混合**
```python
def hybrid_recall(query, conversation_history):
    # 规则1：检测明确的引用
    if has_reference(query, ["之前", "上次", "刚才"]):
        return recall_recent_context()
    
    # 规则2：检测特定实体
    entities = extract_entities(query)
    if entities:
        memories = []
        for entity in entities:
            memories.extend(vector_db.search_by_metadata(entity=entity))
        return memories
    
    # 规则3：语义检索
    return semantic_search(query)
```

**方法4：多路召回+融合**
```python
def multi_path_recall(query):
    results = []
    
    # 路径1：语义召回
    semantic_results = vector_db.search(query)
    results.extend(semantic_results)
    
    # 路径2：关键词召回
    keywords = extract_keywords(query)
    keyword_results = bm25_search(keywords)
    results.extend(keyword_results)
    
    # 路径3：时间召回（最近的对话）
    recent_results = fetch_recent_memories(hours=24)
    results.extend(recent_results)
    
    # 去重+重排序
    unique_results = deduplicate(results)
    final_results = rerank(query, unique_results)
    
    return final_results[:5]
```

**决策流程：**
```
用户查询 → 意图分析 → 判断是否需要召回
    ↓
需要召回 → 生成召回查询 → 多路召回
    ↓
召回结果 → 相关性过滤 → 重排序 → Top-K
    ↓
注入到上下文 → LLM生成回答
```

## 11. 压缩机制是做的？上下文窗口口总token多大？触发上限为什么选这个值？

**答案：**

**上下文窗口设计：**

典型配置（以GPT-4为例）：
- **模型上限**：128K tokens
- **实际配置**：32K tokens（留出余量）
- **触发压缩**：28K tokens（90%阈值）
- **压缩目标**：16K tokens（50%容量）

**为什么这样设置？**

1. **不用满上限的原因**：
   - 成本考虑（token越多越贵）
   - 响应速度（上下文越长，推理越慢）
   - 质量考虑（超长上下文可能导致"中间丢失"现象）
   - 预留输出空间（需要为输出保留tokens）

2. **90%触发压缩**：
   - 避免突然超限
   - 给压缩操作留出时间
   - 防止压缩过于频繁

3. **压缩到50%**：
   - 避免频繁压缩（压缩成本高）
   - 保留足够上下文
   - 为后续对话留出空间

**压缩策略：**

**策略1：滚动窗口（简单但有损）**
```python
def rolling_window_compress(messages):
    # 保留系统提示 + 最近N条消息
    system_messages = [m for m in messages if m.role == "system"]
    recent_messages = messages[-10:]  # 最近10条
    
    return system_messages + recent_messages
```

**策略2：摘要压缩（常用）**
```python
def summary_compress(messages):
    # 1. 保留必须保留的消息
    system_msg = messages[0]  # 系统提示
    recent_msgs = messages[-5:]  # 最近5条
    
    # 2. 压缩中间消息
    middle_msgs = messages[1:-5]
    summary = llm.summarize(f"""
    请总结以下对话的关键信息：
    {format_messages(middle_msgs)}
    
    要求：
    - 保留所有重要决策和结论
    - 保留用户偏好和设置
    - 保留未完成的任务
    - 忽略闲聊内容
    """)
    
    # 3. 构造压缩后的上下文
    return [
        system_msg,
        {"role": "system", "content": f"[对话摘要]\n{summary}"},
        *recent_msgs
    ]
```

**策略3：分层压缩（推荐）**
```python
class HierarchicalCompressor:
    def compress(self, messages):
        compressed = []
        
        # Layer 1: 系统消息（不压缩）
        compressed.append(messages[0])
        
        # Layer 2: 重要消息（保留）
        important = self.filter_important(messages)
        compressed.extend(important)
        
        # Layer 3: 普通消息（摘要）
        normal = self.filter_normal(messages)
        if normal:
            summary = self.summarize(normal)
            compressed.append(summary)
        
        # Layer 4: 最近消息（完整保留）
        compressed.extend(messages[-5:])
        
        return compressed
    
    def filter_important(self, messages):
        important = []
        for msg in messages:
            # 包含工具调用的消息
            if msg.get("tool_calls"):
                important.append(msg)
            # 用户明确标记为重要
            if msg.get("metadata", {}).get("important"):
                important.append(msg)
            # 包含代码或配置
            if contains_code(msg["content"]):
                important.append(msg)
        return important
```

**策略4：智能选择性保留**
```python
def selective_compress(messages):
    # 计算每条消息的重要性分数
    scores = []
    for msg in messages:
        score = calculate_importance(msg)
        scores.append((msg, score))
    
    # 按重要性排序
    sorted_msgs = sorted(scores, key=lambda x: x[1], reverse=True)
    
    # 保留高分消息直到达到token预算
    selected = []
    total_tokens = 0
    target_tokens = 16000
    
    for msg, score in sorted_msgs:
        msg_tokens = count_tokens(msg)
        if total_tokens + msg_tokens <= target_tokens:
            selected.append(msg)
            total_tokens += msg_tokens
    
    # 按时间顺序重新排列
    selected.sort(key=lambda m: m["timestamp"])
    return selected

def calculate_importance(message):
    score = 0.0
    
    # 因子1：角色（系统消息最重要）
    if message["role"] == "system":
        score += 10.0
    elif message["role"] == "user":
        score += 5.0
    
    # 因子2：包含工具调用
    if message.get("tool_calls"):
        score += 8.0
    
    # 因子3：包含代码
    if contains_code(message["content"]):
        score += 6.0
    
    # 因子4：时间新鲜度
    recency = calculate_recency(message["timestamp"])
    score += recency * 3.0
    
    # 因子5：内容长度（适中的长度更重要）
    length_score = min(len(message["content"]) / 1000, 1.0)
    score += length_score * 2.0
    
    return score
```

**实际应用：**
```python
class ContextManager:
    def __init__(self, max_tokens=32000, compress_at=28000):
        self.max_tokens = max_tokens
        self.compress_at = compress_at
        self.messages = []
        
    def add_message(self, message):
        self.messages.append(message)
        
        # 检查是否需要压缩
        current_tokens = self.count_total_tokens()
        if current_tokens > self.compress_at:
            self.compress()
    
    def compress(self):
        print(f"压缩前: {self.count_total_tokens()} tokens")
        
        # 使用分层压缩策略
        self.messages = hierarchical_compress(self.messages)
        
        print(f"压缩后: {self.count_total_tokens()} tokens")
```

## 12. 讲一下动态prompt和静态prompt？

**答案：**

**静态Prompt（Static Prompt）**

**定义**：不随对话变化的固定提示词

**组成部分**：
```python
static_prompt = """
# 角色定义
你是一个专业的Python编程助手。

# 能力边界
- 你可以：编写代码、解释代码、debug、优化
- 你不可以：执行系统命令、访问网络

# 行为准则
1. 代码必须包含注释
2. 优先考虑代码可读性
3. 遵循PEP 8规范
4. 提供单元测试

# 输出格式
回答时请按以下格式：
1. 问题分析
2. 解决方案
3. 代码实现
4. 测试用例
"""
```

**特点**：
- 每次对话开始时注入
- 内容不变（或很少变）
- 定义Agent的"人格"和基础能力

**动态Prompt（Dynamic Prompt）**

**定义**：根据上下文动态生成的提示词

**示例：**
```python
def generate_dynamic_prompt(context):
    prompt_parts = []
    
    # 1. 召回的长期记忆
    if context.relevant_memories:
        prompt_parts.append(f"""
        # 相关历史信息
        {format_memories(context.relevant_memories)}
        """)
    
    # 2. 当前项目上下文
    if context.current_project:
        prompt_parts.append(f"""
        # 当前项目
        项目名称: {context.current_project.name}
        技术栈: {context.current_project.stack}
        代码规范: {context.current_project.style_guide}
        """)
    
    # 3. 可用工具列表
    available_tools = get_available_tools(context)
    prompt_parts.append(f"""
    # 可用工具
    {format_tools(available_tools)}
    """)
    
    # 4. Few-shot示例（根据任务类型选择）
    if context.task_type == "code_generation":
        prompt_parts.append(CODE_GEN_EXAMPLES)
    elif context.task_type == "debugging":
        prompt_parts.append(DEBUG_EXAMPLES)
    
    return "\n\n".join(prompt_parts)
```

**对比表格：**

| 维度 | 静态Prompt | 动态Prompt |
|------|-----------|-----------|
| **内容** | 固定不变 | 动态生成 |
| **作用** | 定义角色和基础规则 | 提供上下文相关信息 |
| **更新频率** | 很少（版本更新时） | 每次对话 |
| **Token消耗** | 固定成本 | 变化成本 |
| **示例** | 系统角色、行为准则 | 项目上下文、工具列表 |

**实际应用架构：**

```python
class PromptBuilder:
    def __init__(self):
        # 静态部分（加载一次）
        self.static_prompt = load_static_prompt()
        
    def build_prompt(self, user_input, context):
        prompt_sections = []
        
        # 1. 静态Prompt（始终包含）
        prompt_sections.append(self.static_prompt)
        
        # 2. 动态上下文
        dynamic_context = self.build_dynamic_context(context)
        prompt_sections.append(dynamic_context)
        
        # 3. Few-shot示例（按需包含）
        if self.should_include_examples(user_input):
            examples = self.select_examples(user_input)
            prompt_sections.append(examples)
        
        # 4. 用户输入
        prompt_sections.append(f"# 用户请求\n{user_input}")
        
        return "\n\n".join(prompt_sections)
    
    def build_dynamic_context(self, context):
        parts = []
        
        # 项目信息
        if context.project:
            parts.append(self.format_project_context(context.project))
        
        # 对话历史摘要
        if context.conversation_summary:
            parts.append(f"# 对话摘要\n{context.conversation_summary}")
        
        # 相关代码文件
        if context.relevant_files:
            parts.append(self.format_code_context(context.relevant_files))
        
        # 可用工具
        parts.append(self.format_tools(context.available_tools))
        
        return "\n\n".join(parts)
```

**优化技巧：**

1. **静态部分缓存**
```python
# 静态Prompt可以利用提示词缓存
# OpenAI/Anthropic支持前缀缓存
cached_static_prompt = cache_prompt(static_prompt, ttl=3600)
```

2. **动态部分按需加载**
```python
# 不是所有动态信息都需要每次都加载
def build_dynamic_prompt(context):
    prompt = ""
    
    # 只在需要时加载项目上下文
    if mentions_project(context.user_input):
        prompt += load_project_context()
    
    # 只在需要时召回记忆
    if needs_memory_recall(context.user_input):
        prompt += recall_relevant_memories()
    
    return prompt
```

3. **分级加载策略**
```python
# P0: 必须加载（静态prompt）
# P1: 高概率需要（当前文件上下文）
# P2: 可能需要（相关文件）
# P3: 很少需要（全局项目信息）

def build_tiered_prompt(context, token_budget):
    prompt = static_prompt  # P0
    remaining_budget = token_budget - count_tokens(prompt)
    
    # P1
    if remaining_budget > 1000:
        current_file = load_current_file_context()
        prompt += current_file
        remaining_budget -= count_tokens(current_file)
    
    # P2
    if remaining_budget > 2000:
        related_files = load_related_files()
        prompt += related_files
        remaining_budget -= count_tokens(related_files)
    
    # P3
    if remaining_budget > 5000:
        project_context = load_full_project_context()
        prompt += project_context
    
    return prompt
```

## 13. 模型底座是哪个？例如写一千行代码，需要消耗多少token？成本高么？你用的百万token计费是多少？

**答案：**

**常用模型底座对比：**

| 模型 | 输入价格 | 输出价格 | 上下文长度 | 适用场景 |
|------|---------|---------|-----------|---------|
| **GPT-4 Turbo** | $10/1M tokens | $30/1M tokens | 128K | 复杂推理任务 |
| **GPT-4o** | $5/1M tokens | $15/1M tokens | 128K | 平衡性能成本 |
| **Claude 3.5 Sonnet** | $3/1M tokens | $15/1M tokens | 200K | 代码生成 |
| **Claude 3 Opus** | $15/1M tokens | $75/1M tokens | 200K | 最高质量 |
| **GPT-3.5 Turbo** | $0.5/1M tokens | $1.5/1M tokens | 16K | 简单任务 |
| **DeepSeek-V2.5** | $0.14/1M tokens | $0.28/1M tokens | 128K | 性价比之王 |

**1000行代码的Token消耗估算：**

```python
# 经验公式：1行代码 ≈ 15-25 tokens（含注释和空行）
# 1000行代码 ≈ 15,000 - 25,000 tokens

# 示例计算（使用Claude 3.5 Sonnet）
code_tokens = 20000  # 1000行代码

# 场景1：一次性生成1000行代码
input_tokens = 2000  # 用户需求描述 + 上下文
output_tokens = 20000  # 生成的代码

cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000
print(f"成本: ${cost:.4f}")  # 约 $0.31

# 场景2：迭代式开发（更现实）
# 10次迭代，每次100行
iterations = 10
cost_per_iteration = (
    (2000 + 5000) * 3 +  # 输入：需求+已有代码上下文
    2000 * 15            # 输出：新增代码
) / 1_000_000

total_cost = cost_per_iteration * iterations
print(f"迭代式开发成本: ${total_cost:.4f}")  # 约 $0.51
```

**实际项目成本分析：**

```python
# 以一个中型Agent项目为例
class CostAnalysis:
    def __init__(self, model="claude-3.5-sonnet"):
        if model == "claude-3.5-sonnet":
            self.input_price = 3 / 1_000_000
            self.output_price = 15 / 1_000_000
        elif model == "gpt-4o":
            self.input_price = 5 / 1_000_000
            self.output_price = 15 / 1_000_000
    
    def calculate_daily_cost(self):
        # 开发阶段（每天）
        daily_usage = {
            "code_generation": {
                "sessions": 20,
                "input_per_session": 8000,
                "output_per_session": 3000
            },
            "code_review": {
                "sessions": 10,
                "input_per_session": 5000,
                "output_per_session": 1000
            },
            "debugging": {
                "sessions": 15,
                "input_per_session": 6000,
                "output_per_session": 2000
            }
        }
        
        total_cost = 0
        for task, usage in daily_usage.items():
            input_tokens = usage["sessions"] * usage["input_per_session"]
            output_tokens = usage["sessions"] * usage["output_per_session"]
            
            cost = (
                input_tokens * self.input_price +
                output_tokens * self.output_price
            )
            total_cost += cost
            print(f"{task}: ${cost:.2f}")
        
        print(f"\n每日总成本: ${total_cost:.2f}")
        print(f"每月成本（22工作日）: ${total_cost * 22:.2f}")
        
        return total_cost

# 运行分析
analyzer = CostAnalysis("claude-3.5-sonnet")
analyzer.calculate_daily_cost()

# 输出示例：
# code_generation: $1.38
# code_review: $0.30
# debugging: $0.72
# 
# 每日总成本: $2.40
# 每月成本（22工作日）: $52.80
```

**成本优化策略：**

1. **分层模型策略**
```python
class TieredModelStrategy:
    def select_model(self, task_complexity):
        if task_complexity == "simple":
            return "gpt-3.5-turbo"  # $0.002/千tokens
        elif task_complexity == "medium":
            return "gpt-4o"  # $0.010/千tokens
        else:
            return "claude-3-opus"  # $0.075/千tokens
    
    # 示例：60%简单任务 + 30%中等 + 10%复杂
    # 加权平均成本 ≈ $0.016/千tokens
    # 相比全用GPT-4 Opus节省约80%
```

2. **提示词缓存**
```python
# Anthropic Prompt Caching
# 缓存的tokens价格 = 正常价格的10%
# 静态prompt（5000 tokens）缓存后每次只需 $0.015

# 100次对话的成本对比：
# 不缓存：100 * 5000 * $3/1M = $1.50
# 缓存：1 * 5000 * $3/1M + 99 * 5000 * $0.3/1M = $0.16
# 节省：90%
```

3. **输出长度控制**
```python
# 输出token通常是输入的5倍价格
# 严格控制输出长度可以显著降低成本

prompt = """
生成代码时：
- 最多100行
- 省略重复的样板代码
- 使用注释说明省略的部分
"""
```

4. **增量生成**
```python
# 不要一次生成大量代码
# 而是分步骤生成，每步验证

# 错误做法：
"生成完整的用户认证系统（1000行）"  # 可能浪费tokens

# 正确做法：
"第一步：生成用户模型（50行）"
"第二步：生成认证中间件（30行）"
...
```

**DeepSeek的优势（我的选择）：**

```python
# DeepSeek-V2.5 定价
input_price = $0.14/1M tokens
output_price = $0.28/1M tokens

# 相比Claude 3.5 Sonnet：
# 输入便宜 21倍（$3 vs $0.14）
# 输出便宜 54倍（$15 vs $0.28）

# 1000行代码成本：
cost = (2000 * 0.14 + 20000 * 0.28) / 1_000_000
# = $0.0059  （不到1美分！）

# 对比Claude：$0.31
# 节省：98%
```

**结论：**
- **开发阶段**：优先使用DeepSeek（成本极低）
- **生产环境**：根据任务复杂度选择模型
- **关键任务**：使用GPT-4o或Claude 3.5 Sonnet
- **每月成本**：个人开发者 $10-50，团队 $200-1000


## 14. 追问为什么需要这么高的成本？

**答案：**

这个问题考察对成本的理解和优化思路。正确的回答应该包含：

**1. 成本构成分析**

```python
# Agent系统的token消耗来源
class TokenCostBreakdown:
    def analyze(self, session):
        breakdown = {
            "静态prompt": 5000,      # 系统提示、规则
            "动态上下文": 8000,       # 项目信息、工具列表
            "对话历史": 3000,        # 最近对话
            "召回记忆": 2000,        # 长期记忆检索
            "工具调用结果": 4000,    # API响应、文件内容
            "用户输入": 500,         # 用户问题
            "Few-shot示例": 3000,   # 示例代码
            "输出生成": 2000         # 生成的回答
        }
        
        total = sum(breakdown.values())
        print(f"单次对话总token: {total}")
        
        for item, tokens in breakdown.items():
            percentage = tokens / total * 100
            print(f"{item}: {tokens} ({percentage:.1f}%)")
        
        return breakdown

# 输出：
# 单次对话总token: 27500
# 静态prompt: 5000 (18.2%)
# 动态上下文: 8000 (29.1%)  # ← 最大消耗
# 工具调用结果: 4000 (14.5%)  # ← 第二大
```

**2. 为什么成本看起来高？**

**原因1：上下文膨胀**
```
普通对话: 用户问题(100 tokens) → 模型回答(200 tokens)
Agent对话: 
  用户问题(100) 
  + 系统prompt(5000)
  + 项目上下文(8000)
  + 工具定义(3000)
  + 历史记忆(2000)
  + Few-shot示例(3000)
  = 21,100 tokens输入

输入膨胀了 211倍！
```

**原因2：多轮交互**
```python
# 一个复杂任务可能需要多轮对话
task = "实现用户认证系统"

rounds = [
    "理解需求",           # 3K tokens
    "设计数据库schema",   # 5K tokens  
    "生成模型代码",       # 8K tokens
    "生成API接口",        # 8K tokens
    "生成单元测试",       # 6K tokens
    "调试错误",           # 4K tokens
]

total_tokens = sum([count_tokens(r) for r in rounds])
# 总消耗：34K tokens
```

**原因3：工具调用开销**
```python
# 每次工具调用都会产生额外开销
def tool_call_cost(tool_name, tool_output):
    cost_breakdown = {
        "工具定义注入": 500,        # 工具的schema
        "工具调用决策": 2000,       # LLM决定调用哪个工具
        "工具参数生成": 500,        # 生成调用参数
        "工具输出": len(tool_output),  # 工具返回结果
        "结果解读": 1000,           # LLM理解工具输出
    }
    return sum(cost_breakdown.values())

# 一个任务调用5个工具 = 5 * 4000 = 20K tokens
```

**3. 但是，这个成本值得吗？**

**ROI分析：**
```python
# 场景：开发一个中等复杂度的功能

# 方案A：人工开发
human_cost = {
    "开发时间": 4小时,
    "时薪": 50美元,
    "总成本": 200美元
}

# 方案B：Agent辅助
agent_cost = {
    "token消耗": 100K tokens,
    "模型成本": 2美元,  # 使用DeepSeek
    "人工审查": 0.5小时,
    "时薪": 50美元,
    "总成本": 27美元
}

savings = 200 - 27 = 173美元
efficiency_gain = 200 / 27 = 7.4倍

print(f"节省: ${savings}")
print(f"效率提升: {efficiency_gain:.1f}x")
```

**4. 如何优化成本？**

**优化1：激进的上下文裁剪**
```python
# 只在必要时注入完整上下文
def build_minimal_context(user_input):
    # 基础prompt（必须）
    context = [base_prompt]  # 2K tokens
    
    # 按需加载其他部分
    if needs_project_context(user_input):
        context.append(project_info)  # +3K
    
    if needs_tool_access(user_input):
        relevant_tools = select_tools(user_input)  # 只注入相关工具
        context.append(relevant_tools)  # +1K 而不是 +5K
    
    if needs_memory(user_input):
        context.append(recall_memory(user_input))  # +2K
    
    return context  # 总共 5-10K，而不是 20K
```

**优化2：结果缓存**
```python
# 相同的输入不重复调用LLM
@cache(ttl=3600)
def call_llm(prompt, **kwargs):
    return llm.generate(prompt, **kwargs)

# 示例：用户多次问同样的问题
# 第一次：消耗3K tokens
# 后续：从缓存读取，0 tokens
```

**优化3：本地工具替代LLM**
```python
# 不是所有任务都需要LLM
class HybridAgent:
    def handle_request(self, request):
        # 简单任务：用规则处理（0成本）
        if is_simple_query(request):
            return rule_based_handler(request)
        
        # 中等任务：用小模型（低成本）
        if is_medium_query(request):
            return small_model_handler(request)  # GPT-3.5
        
        # 复杂任务：用大模型（高成本）
        return large_model_handler(request)  # GPT-4

# 成本分布：50%规则 + 30%小模型 + 20%大模型
# 平均成本下降60-70%
```

**优化4：批处理**
```python
# 批量处理相似任务
def batch_process(tasks):
    # 不好的做法：每个任务单独调用
    # for task in tasks:
    #     result = llm.generate(task)  # 100次调用
    
    # 好的做法：批量处理
    batch_prompt = f"""
    处理以下{len(tasks)}个相似任务：
    {format_tasks(tasks)}
    """
    results = llm.generate(batch_prompt)  # 1次调用
    
    # 成本节省：～80%（共享上下文）
```

**5. 对比其他选择**

```python
# 选择1：不用Agent（纯人工）
# 成本：高人力成本，低API成本
# 效率：慢
# 质量：依赖个人能力

# 选择2：简单脚本自动化
# 成本：0 API成本
# 效率：快，但功能受限
# 质量：只能处理预定义场景

# 选择3：Agent系统
# 成本：中等API成本（每月$20-100）
# 效率：非常快
# 质量：高且一致

# 结论：对于需要智能决策的任务，Agent的ROI最高
```

**最佳实践总结：**

1. **成本是可控的**：通过优化可以降低50-80%
2. **成本是值得的**：效率提升通常是10-100倍
3. **选择合适的模型**：不要为所有任务都用最贵的模型
4. **监控和优化**：持续追踪token使用，优化高消耗环节

**面试加分回答：**
```
"从绝对值看成本确实不低，但需要考虑ROI。我们的系统通过：
1. 选择DeepSeek等性价比模型（成本降90%）
2. 激进的上下文管理（减少50%无效tokens）
3. 分层模型策略（简单任务用轻量模型）
4. 结果缓存和批处理

实际每月成本控制在$50以内，但提升开发效率5-10倍。
相当于每月花$50，获得价值$500的生产力提升。"
```

## 15. 你平时自己还用你的coding agent么？

**答案：**

这个问题考察：
1. 是否真正使用自己开发的工具（吃自己的狗粮）
2. 对工具实际效果的诚实评价
3. 发现的问题和改进空间

**好的回答框架：**

**1. 使用频率和场景**
```
"是的，我每天都在用。主要场景包括：

高频场景（每天）：
- 生成样板代码（API接口、数据模型）
- 编写单元测试
- 代码重构建议
- 快速原型开发

中频场景（每周）：
- 理解陌生代码库
- 调试复杂bug
- 性能优化建议
- 文档生成

低频场景（偶尔）：
- 架构设计讨论
- 技术选型分析
"
```

**2. 实际效果评估**

```python
class SelfUsageAnalysis:
    """我自己使用的真实数据"""
    
    def __init__(self):
        self.usage_stats = {
            "总使用次数": 1000,
            "成功率": 0.75,  # 75%的任务能很好完成
            "部分成功率": 0.20,  # 20%需要人工调整
            "失败率": 0.05,  # 5%完全不可用
        }
    
    def task_performance(self):
        return {
            "简单任务": {
                "示例": "生成CRUD接口",
                "成功率": 0.95,
                "平均耗时": "30秒",
                "vs人工": "快10倍"
            },
            "中等任务": {
                "示例": "实现复杂业务逻辑",
                "成功率": 0.70,
                "需要调整": "通常需要10-20%修改",
                "vs人工": "快3-5倍"
            },
            "复杂任务": {
                "示例": "系统架构设计",
                "成功率": 0.40,
                "使用方式": "作为brainstorming工具",
                "vs人工": "提供思路，不能完全依赖"
            }
        }
```

**3. 发现的问题（诚实很重要）**

```
"通过自己使用，我发现了几个主要问题：

问题1：上下文理解不准确
- 表现：有时候会误解项目现有的设计模式
- 原因：RAG召回不够精准
- 改进：增加了代码调用关系的Graph索引

问题2：生成代码风格不一致
- 表现：每次生成的代码风格略有差异
- 原因：prompt不够明确
- 改进：自动从项目中提取style guide

问题3：错误处理不完善
- 表现：生成的代码缺少边界情况处理
- 原因：训练数据偏向happy path
- 改进：在prompt中明确要求error handling

问题4：测试覆盖率不足
- 表现：生成的测试只覆盖基本场景
- 原因：模型倾向于生成简单测试
- 改进：加入测试覆盖率检查和补充机制
"
```

**4. 持续改进的例子**

```python
# 真实改进案例
class ImprovementFromDogfooding:
    """基于自己使用反馈的改进"""
    
    def example_1_code_style_consistency(self):
        """改进1：代码风格一致性"""
        
        # 问题：之前的实现
        prompt_before = "生成一个用户注册接口"
        
        # 改进后：自动注入项目风格
        prompt_after = f"""
        生成一个用户注册接口
        
        项目风格要求：
        {self.extract_style_from_existing_code()}
        - 使用TypeScript strict mode
        - 函数命名：camelCase
        - 接口命名：IXxxxx
        - 错误处理：统一使用Result<T, Error>
        """
        
        # 结果：代码风格一致性从60%提升到95%
    
    def example_2_context_awareness(self):
        """改进2：上下文感知"""
        
        # 问题：多次询问相同问题
        # 之前：每次都要重新说明项目背景
        
        # 改进：增加会话级别的项目上下文缓存
        class SessionContext:
            def __init__(self):
                self.project_type = None  # 自动检测
                self.tech_stack = None    # 自动识别
                self.coding_patterns = [] # 学习到的模式
            
            def learn_from_interaction(self, code_changes):
                # 从我的修改中学习偏好
                patterns = extract_patterns(code_changes)
                self.coding_patterns.extend(patterns)
        
        # 结果：第二次使用时，自动遵循我的偏好
    
    def example_3_iteration_support(self):
        """改进3：迭代式开发支持"""
        
        # 问题：修改代码时，Agent会重新生成整个文件
        # 改进：支持增量修改
        
        @command("/refine")
        def refine_last_generation(feedback):
            """根据反馈精修上次生成的代码"""
            last_code = get_last_generated_code()
            
            prompt = f"""
            上次生成的代码：
            {last_code}
            
            用户反馈：
            {feedback}
            
            请只修改需要改的部分，保持其他代码不变。
            """
            
            return llm.generate(prompt)
        
        # 结果：迭代效率提升3倍
```

**5. 使用体验总结（诚实且有洞察）**

```
"总体来说，Coding Agent已经是我日常开发不可或缺的工具：

什么时候用：
✅ 重复性工作（CRUD、测试、文档）
✅ 快速原型（验证想法）
✅ 代码探索（理解新项目）
✅ 样板代码生成

什么时候不用：
❌ 核心算法实现（需要精确控制）
❌ 性能关键路径（需要深度优化）
❌ 复杂状态管理（容易出错）
❌ 安全敏感代码（需要人工审查）

最大价值：
不是"完全替代编程"，而是：
1. 加速重复性工作（10倍）
2. 提供代码探索能力（理解陌生项目）
3. 作为结对编程伙伴（brainstorming）

如果重新设计：
我会更关注：
1. 代码理解能力（而不只是生成）
2. 迭代式开发支持（而不是一次性生成）
3. 与IDE深度集成（而不是独立工具）
"
```

**加分点：展示具体数据**

```python
# 如果有tracking系统，展示真实数据
my_usage_stats = {
    "本月使用次数": 156,
    "平均每天": 7.1,
    "最常用功能": "代码生成(45%), 测试生成(30%), 代码解释(25%)",
    "平均节省时间": "每次15分钟",
    "月累计节省": "39小时",
    "Token消耗": "2.3M tokens",
    "月成本": "$12 (DeepSeek)",
    "ROI": "39小时 * $50/小时 / $12 = 162x"
}
```

**面试官想听到的关键点：**
1. ✅ 真的在用（有具体数据和例子）
2. ✅ 客观评价（不是完美的，有局限性）
3. ✅ 持续改进（基于使用反馈优化）
4. ✅ 清楚定位（知道什么时候用、什么时候不用）

## 16-24题继续...

（由于内容较长，我将分多个文件创建。现在创建其他公司的面试题文件）

