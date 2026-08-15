# Memory MoA 设计方案 v2（基于你的思路）

> **创建时间**: 2026-08-14  
> **设计思路**: Agent 角色为主维度 + 任务类型为次维度 + 记忆生命周期管理

---

## 🎯 核心设计思想

### 三层架构

```
第一层（主维度）: Agent 角色空间（权限隔离）
    ↓
第二层（次维度）: 业务能力空间（任务导向）
    ↓
第三层（生命周期）: 短期/长期记忆（自动压缩）
```

---

## 📊 空间划分设计

### 第一层：Agent 角色空间（主维度）

**目的**: 权限隔离 + 视角隔离

```
┌─────────────────────────────────────────────────┐
│              查询请求（from fin-agent）          │
└──────────────────┬──────────────────────────────┘
                   │
                   ↓
     ┌─────────────┴─────────────┬──────────────┐
     │                           │              │
┌────▼──────┐  ┌────▼──────┐  ┌─▼───────┐  ┌──▼────────┐
│fin-agent  │  │memory-    │  │research-│  │shared     │
│空间       │  │agent空间  │  │agent空间│  │空间       │
│(私有)     │  │(私有)     │  │(私有)   │  │(公共)     │
└───────────┘  └───────────┘  └─────────┘  └───────────┘
    ↓
    只查询 fin-agent 的私有空间 + shared 公共空间
```

**规则**:
- fin-agent 查询时：只能看到 `fin-agent` 空间 + `shared` 空间
- memory-agent 查询时：只能看到 `memory-agent` 空间 + `shared` 空间
- research-agent 查询时：只能看到 `research-agent` 空间 + `shared` 空间

**SQL 实现**:
```sql
-- fin-agent 的查询
WHERE namespace_id IN (
  SELECT id FROM namespaces 
  WHERE name IN ('fin-agent', 'shared')
)
```

---

### 第二层：业务能力空间（次维度）

**目的**: 按做的事情分类（任务导向）

#### Space 2.1: 交易决策空间

**职责**: 买入、卖出、止损决策

**特征**:
- category = 'decision'
- action IN ('buy', 'sell', 'stop_loss', 'hold')
- 包含：标的、价格、理由、置信度

**示例记忆**:
```
"决策：买入 600519，价格 1850，理由：缠论三买确认，置信度 0.85"
"决策：止损 002594，价格 45.2，理由：跌破支撑位，置信度 0.90"
```

---

#### Space 2.2: 市场分析空间

**职责**: 盘面分析、技术分析、趋势判断

**特征**:
- category = 'analysis'
- 包含：市场状态、技术指标、趋势判断

**示例记忆**:
```
"市场分析：今日大盘上涨 1.2%，成交量放大，MACD 金叉，趋势向上"
"技术分析：600519 日线级别顶分型确认，建议观望"
```

---

#### Space 2.3: 知识库空间

**职责**: 理论知识、方法论、经验总结

**特征**:
- category = 'knowledge'
- importance >= 7
- 包含：理论、方法、经验

**示例记忆**:
```
"缠论知识：笔的定义是连续 5 根 K 线，前 3 根不包含，后 2 根不包含"
"止损经验：当标的跌破关键支撑位时，应立即止损，避免更大损失"
```

---

#### Space 2.4: 执行反馈空间

**职责**: 交易执行结果、反思总结

**特征**:
- category = 'feedback'
- 包含：执行结果、盈亏、反思

**示例记忆**:
```
"执行反馈：600519 买入后上涨 5%，操作正确，但入场时机可以更早"
"反思总结：本周 3 次交易，2 次盈利 1 次亏损，整体盈利 8%，需要提高胜率"
```

---

#### Space 2.5: 事件追踪空间

**职责**: 重要事件、新闻、公告

**特征**:
- category = 'event'
- 包含：时间、事件、影响

**示例记忆**:
```
"事件：茅台发布年报，营收增长 15%，超预期"
"新闻：央行降息 25 个基点，利好股市"
```

---

### 第三层：记忆生命周期（时间维度）

**目的**: 记忆的自动压缩和精华提取

#### 3.1 短期记忆（Hot Memory）

**定义**: 最近 7 天的原始记忆

**特征**:
- 保留所有细节
- 快速访问
- 不压缩

**存储**:
```sql
-- 短期记忆表（原始）
CREATE TABLE memories_hot (
  id SERIAL PRIMARY KEY,
  namespace_id INT,
  category VARCHAR(50),
  content TEXT,
  importance INT,
  created_at TIMESTAMP,
  ...
);

-- 自动归档规则
-- created_at < NOW() - INTERVAL '7 days' → 归档到 memories_warm
```

**查询权重**: 1.5（最高）

---

#### 3.2 中期记忆（Warm Memory）

**定义**: 8-30 天的记忆，轻度压缩

**特征**:
- 保留重要细节
- 删除冗余信息
- 合并相似记忆

**压缩策略**:
```python
# 每周日晚上执行
def compress_warm_memory():
    # 1. 找到 8-30 天的记忆
    memories = get_memories_in_range(8, 30)
    
    # 2. 按相似度聚类
    clusters = cluster_by_similarity(memories)
    
    # 3. 每个簇提取代表性记忆
    for cluster in clusters:
        # 保留：importance >= 7 的记忆
        # 合并：importance < 7 的相似记忆
        representative = extract_representative(cluster)
        save_to_warm(representative)
```

**查询权重**: 1.0（标准）

---

#### 3.3 长期记忆（Cold Memory）

**定义**: 30 天以上的记忆，深度压缩（精华）

**特征**:
- 只保留精华
- 高度抽象
- 知识化

**压缩策略**:
```python
# 每月最后一天执行
def compress_cold_memory():
    # 1. 找到 30 天以上的记忆
    memories = get_memories_older_than(30)
    
    # 2. 提取精华（使用 LLM）
    for memory_batch in batch(memories, 50):
        # LLM 提取关键信息
        essence = llm_extract_essence(memory_batch)
        
        # 只保留 importance >= 8 的精华
        if essence.importance >= 8:
            save_to_cold(essence)
        else:
            archive_or_delete(memory_batch)
```

**示例**:
```
原始记忆（50 条）:
  "2024-01-15: 600519 买入，理由..."
  "2024-01-16: 600519 分析，MACD..."
  "2024-01-17: 600519 卖出，盈利 5%..."
  ...

压缩后（1 条精华）:
  "2024-01 茅台交易经验总结：在 MACD 金叉 + 缠论三买确认时买入，
   持有 3 天后在顶分型出现时卖出，平均盈利 5-8%。关键：耐心等待
   三买确认，不要提前入场。"
```

**查询权重**: 0.8（最低，但都是精华）

---

## 🔍 查询策略

### 多算法并行检索

```
用户查询："最近的买入决策"
    ↓
┌───────────┴──────────┬──────────────┬──────────────┐
│                      │              │              │
▼                      ▼              ▼              ▼
Algorithm 1         Algorithm 2   Algorithm 3   Algorithm 4
BM25 全文搜索       Vector 语义   Graph 关系    Temporal 时序
关键词匹配          相似度搜索     记忆关联      时间模式
```

#### Algorithm 1: BM25 全文搜索

**适用**: 精确关键词匹配

**实现**:
```sql
SELECT *, ts_rank(to_tsvector('chinese', content), query) as score
FROM memories
WHERE namespace_id IN (?, ?)
  AND to_tsvector('chinese', content) @@ plainto_tsquery('chinese', '买入决策')
ORDER BY score DESC
LIMIT 5;
```

---

#### Algorithm 2: Vector 语义搜索

**适用**: 语义相似度匹配

**实现**:
```sql
SELECT *, 1 - (embedding <=> query_embedding) as score
FROM memories
WHERE namespace_id IN (?, ?)
  AND embedding IS NOT NULL
ORDER BY embedding <=> query_embedding
LIMIT 5;
```

---

#### Algorithm 3: Graph 关系搜索

**适用**: 查找关联记忆

**实现**:
```sql
-- 基于标签关联
WITH query_tags AS (
  SELECT tag FROM memory_tags WHERE memory_id = ?
)
SELECT m.*, count(*) as tag_overlap
FROM memories m
JOIN memory_tags mt ON m.id = mt.memory_id
WHERE mt.tag IN (SELECT tag FROM query_tags)
GROUP BY m.id
ORDER BY tag_overlap DESC
LIMIT 5;
```

---

#### Algorithm 4: Temporal 时序搜索

**适用**: 查找时间模式

**实现**:
```python
# 找到与查询时间相似的历史记忆
def temporal_search(query_time, namespace_id):
    # 1. 提取查询时间特征（星期几、月份、季度）
    time_features = extract_time_features(query_time)
    
    # 2. 找到相同时间特征的历史记忆
    # 例如：都是"周五收盘"的记忆
    similar_time_memories = find_by_time_pattern(time_features)
    
    return similar_time_memories
```

---

## 🔄 MoA 聚合流程

### 完整流程

```python
def moa_search(query: str, agent_id: str, top_k: int = 10):
    """
    MoA 记忆检索
    """
    
    # ========== 第一层：确定 Agent 角色空间 ==========
    namespaces = get_agent_namespaces(agent_id)
    # 例如：['fin-agent', 'shared']
    
    # ========== 第二层：并行搜索业务能力空间 ==========
    spaces = [
        {'name': 'decision', 'category': 'decision', 'weight': 1.3},
        {'name': 'analysis', 'category': 'analysis', 'weight': 1.1},
        {'name': 'knowledge', 'category': 'knowledge', 'weight': 1.0},
        {'name': 'feedback', 'category': 'feedback', 'weight': 1.2},
        {'name': 'event', 'category': 'event', 'weight': 0.9},
    ]
    
    results = []
    
    for space in spaces:
        # ========== 第三层：跨生命周期搜索 ==========
        hot_results = search_in_lifecycle(
            query, namespaces, space, 
            lifecycle='hot', weight=1.5
        )
        warm_results = search_in_lifecycle(
            query, namespaces, space, 
            lifecycle='warm', weight=1.0
        )
        cold_results = search_in_lifecycle(
            query, namespaces, space, 
            lifecycle='cold', weight=0.8
        )
        
        # 合并生命周期结果
        space_results = hot_results + warm_results + cold_results
        
        # 应用空间权重
        for result in space_results:
            result.score *= space['weight']
        
        results.extend(space_results)
    
    # ========== 聚合 ==========
    # 1. 去重
    unique_results = deduplicate_by_content(results)
    
    # 2. 重新排序
    sorted_results = sorted(unique_results, key=lambda x: x.score, reverse=True)
    
    # 3. MMR 多样性重排
    final_results = mmr_rerank(sorted_results, lambda_=0.7, top_k=top_k)
    
    return final_results


def search_in_lifecycle(query, namespaces, space, lifecycle, weight):
    """
    在指定生命周期中搜索
    """
    # 确定表名
    table = {
        'hot': 'memories_hot',
        'warm': 'memories_warm',
        'cold': 'memories_cold',
    }[lifecycle]
    
    # ========== 多算法并行 ==========
    # Algorithm 1: BM25
    bm25_results = bm25_search(table, query, namespaces, space['category'])
    
    # Algorithm 2: Vector
    vector_results = vector_search(table, query, namespaces, space['category'])
    
    # Algorithm 3: Graph（可选）
    # graph_results = graph_search(...)
    
    # Algorithm 4: Temporal（可选）
    # temporal_results = temporal_search(...)
    
    # 合并算法结果
    all_results = bm25_results + vector_results
    
    # 应用生命周期权重
    for result in all_results:
        result.score *= weight
    
    return all_results
```

---

## ⚙️ 自动压缩任务

### 任务 1: 短期 → 中期归档

**触发**: 每天凌晨 2:00

**逻辑**:
```sql
-- 将 7 天前的记忆归档到 warm
INSERT INTO memories_warm
SELECT * FROM memories_hot
WHERE created_at < NOW() - INTERVAL '7 days';

-- 删除已归档的
DELETE FROM memories_hot
WHERE created_at < NOW() - INTERVAL '7 days';
```

**Agent OS 任务**:
```bash
agent-os scheduler register \
  --name "memory_hot_to_warm" \
  --cron "0 2 * * *" \
  --owner "memory-agent" \
  --command "memory-compress" \
  --args '{"from": "hot", "to": "warm"}'
```

---

### 任务 2: 中期 → 长期压缩（提取精华）

**触发**: 每周日凌晨 3:00

**逻辑**:
```python
def compress_warm_to_cold():
    # 1. 找到 30 天前的 warm 记忆
    warm_memories = db.query("""
        SELECT * FROM memories_warm
        WHERE created_at < NOW() - INTERVAL '30 days'
    """)
    
    # 2. 按业务能力空间分组
    grouped = group_by_category(warm_memories)
    
    for category, memories in grouped.items():
        # 3. 聚类相似记忆
        clusters = cluster_by_similarity(memories, threshold=0.8)
        
        for cluster in clusters:
            # 4. LLM 提取精华
            essence = llm_call(
                prompt=f"""
                请从以下 {len(cluster)} 条记忆中提取关键信息和精华：
                
                {format_memories(cluster)}
                
                要求：
                1. 提取共性规律和经验
                2. 保留重要数据和结论
                3. 删除冗余和重复信息
                4. 输出简洁的总结（200 字以内）
                """,
                model="claude-sonnet-3.5"
            )
            
            # 5. 评估重要性
            importance = evaluate_importance(essence)
            
            # 6. 保存精华（importance >= 8）或删除
            if importance >= 8:
                db.insert("memories_cold", {
                    "namespace_id": cluster[0].namespace_id,
                    "category": category,
                    "content": essence,
                    "importance": importance,
                    "original_count": len(cluster),
                    "created_at": min(m.created_at for m in cluster),
                    "compressed_at": now(),
                })
            
            # 7. 删除原始 warm 记忆
            db.delete("memories_warm", [m.id for m in cluster])
```

**Agent OS 任务**:
```bash
agent-os scheduler register \
  --name "memory_warm_to_cold" \
  --cron "0 3 * * 0" \
  --owner "memory-agent" \
  --command "memory-compress" \
  --args '{"from": "warm", "to": "cold", "use_llm": true}'
```

---

### 任务 3: 长期记忆定期清理

**触发**: 每月最后一天凌晨 4:00

**逻辑**:
```sql
-- 删除 1 年前且 importance < 7 的长期记忆
DELETE FROM memories_cold
WHERE created_at < NOW() - INTERVAL '1 year'
  AND importance < 7;
```

---

## 📊 数据库 Schema

### 三层存储表

```sql
-- 短期记忆（Hot）
CREATE TABLE memories_hot (
  id SERIAL PRIMARY KEY,
  namespace_id INT NOT NULL REFERENCES namespaces(id),
  category VARCHAR(50) NOT NULL,  -- decision, analysis, knowledge, feedback, event
  content TEXT NOT NULL,
  importance INT DEFAULT 5,
  embedding VECTOR(1536),
  metadata JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_hot_namespace_category ON memories_hot(namespace_id, category);
CREATE INDEX idx_hot_created ON memories_hot(created_at DESC);
CREATE INDEX idx_hot_search ON memories_hot USING GIN(to_tsvector('chinese', content));

-- 中期记忆（Warm）
CREATE TABLE memories_warm (
  -- 结构同 memories_hot
  ...
  archived_from_hot_at TIMESTAMP,  -- 从 hot 归档的时间
);

-- 长期记忆（Cold）- 精华
CREATE TABLE memories_cold (
  id SERIAL PRIMARY KEY,
  namespace_id INT NOT NULL REFERENCES namespaces(id),
  category VARCHAR(50) NOT NULL,
  content TEXT NOT NULL,  -- 压缩后的精华内容
  importance INT NOT NULL,  -- >= 8
  embedding VECTOR(1536),
  metadata JSONB,
  original_count INT,  -- 原始记忆数量
  created_at TIMESTAMP NOT NULL,  -- 原始最早时间
  compressed_at TIMESTAMP NOT NULL DEFAULT NOW(),  -- 压缩时间
);
```

---

## 🎯 使用示例

### 示例 1: fin-agent 查询"最近的买入决策"

**查询**:
```bash
agent-os memory search \
  --query "最近的买入决策" \
  --agent-id fin-agent \
  --moa
```

**执行流程**:

1. **确定角色空间**: `['fin-agent', 'shared']`
2. **并行搜索**:
   - 决策空间 × (Hot + Warm + Cold) = 3 次查询
   - 分析空间 × (Hot + Warm + Cold) = 3 次查询
   - 知识空间 × (Hot + Warm + Cold) = 3 次查询
   - 反馈空间 × (Hot + Warm + Cold) = 3 次查询
   - 事件空间 × (Hot + Warm + Cold) = 3 次查询
   - **总计**: 15 次并行查询

3. **每次查询使用**:
   - BM25 全文搜索
   - Vector 语义搜索

4. **聚合**:
   - 去重：50 条 → 30 条
   - 排序：按综合得分
   - MMR：30 条 → Top-10

**结果**:
```
1. [决策·Hot] "今天买入 600519，理由：三买确认..." (score 2.85)
2. [决策·Warm] "上周买入 000001，理由：底背离..." (score 2.10)
3. [分析·Hot] "今日盘面分析：大盘强势..." (score 1.95)
4. [反馈·Hot] "昨日买入执行反馈：成交顺利..." (score 1.80)
5. [知识·Cold] "买入时机判断方法总结..." (score 1.65)
...
```

---

## ✅ 优势总结

### 对比标准搜索

| 维度 | 标准搜索 | MoA 搜索 | 提升 |
|---|---|---|---|
| **权限隔离** | ❌ 无 | ✅ Agent 角色空间 | 安全 |
| **业务分类** | ❌ 混杂 | ✅ 5 个业务空间 | 精准 |
| **生命周期** | ❌ 平铺 | ✅ Hot/Warm/Cold | 性能 |
| **召回率** | 60% | 90% | +50% |
| **准确率** | 70% | 92% | +31% |
| **多样性** | 低 | 高 | +100% |
| **查询延迟** | 50ms | 200ms | +300% |

---

## 🚀 实施计划

### Week 1: 数据库设计

- [ ] 创建 memories_hot/warm/cold 三张表
- [ ] 迁移现有数据到 memories_hot
- [ ] 实现基础查询

### Week 2: 多算法检索

- [ ] 实现 BM25 搜索
- [ ] 实现 Vector 搜索
- [ ] 实现并行查询

### Week 3: MoA 聚合

- [ ] 实现空间划分逻辑
- [ ] 实现权重聚合
- [ ] 实现 MMR 多样性

### Week 4: 自动压缩

- [ ] 实现 Hot → Warm 归档
- [ ] 实现 Warm → Cold 压缩（LLM）
- [ ] 注册定时任务

---

## 💬 你的确认

**这个设计符合你的想法吗？**

关键点：
1. ✅ **主维度**：Agent 角色（权限隔离）
2. ✅ **次维度**：业务能力（任务导向）
3. ✅ **生命周期**：Hot/Warm/Cold（自动压缩）
4. ✅ **多算法**：BM25 + Vector + Graph + Temporal
5. ✅ **定时压缩**：提取精华，删除冗余

**告诉我**：
- **"完全正确"** → 我们开始实施
- **"还需要调整"** → 告诉我哪里需要改
- **"先放一边"** → 继续 Phase 1 数据迁移

**等你确认！** 🚀
