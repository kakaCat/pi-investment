-- 记忆表
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('knowledge', 'experience', 'decision', 'data')),
    tags TEXT[],
    agent_id VARCHAR(100),
    search_vector tsvector,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 标签表
CREATE TABLE IF NOT EXISTS tags (
    name VARCHAR(100) PRIMARY KEY,
    count INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_search ON memories USING gin(search_vector);
CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories USING gin(tags);

-- 全文搜索触发器
CREATE OR REPLACE FUNCTION memories_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS memories_search_vector_trigger ON memories;
CREATE TRIGGER memories_search_vector_trigger
BEFORE INSERT OR UPDATE ON memories
FOR EACH ROW EXECUTE FUNCTION memories_search_vector_update();

-- 插入测试数据
INSERT INTO memories (title, content, category, tags, agent_id) VALUES
('缠论核心理论：笔、线段、中枢', '缠论的三大核心概念：笔（5根K线构成）、线段（至少3笔构成）、中枢（至少3段重叠区间）。理解这三个概念是掌握缠论的基础。', 'knowledge', ARRAY['缠论', '技术分析', '理论基础'], 'web-test'),
('成功案例：贵州茅台趋势判断', '2024年7月初，通过缠论分析判断贵州茅台形成30分钟级别中枢，预判将突破上行。实际在7月15日成功突破，获利12.5%。', 'experience', ARRAY['成功案例', '贵州茅台', '缠论', '中枢'], 'web-test'),
('市场规律：筹码分布与股价关系', '通过长期观察发现，当筹码高度集中在某一价格区间（单峰密集），且主力持仓比例超过50%时，突破该区间后往往有较大涨幅。', 'knowledge', ARRAY['筹码分布', '主力', '市场规律'], 'web-test'),
('决策记录：新能源板块轮动策略', '8月初采用板块轮动策略，从锂电池龙头（宁德时代）切换到整车龙头（比亚迪）。理由是锂电池板块涨幅过大，资金开始向下游转移。', 'decision', ARRAY['板块轮动', '新能源', '策略'], 'web-test'),
('数据洞察：成交量与趋势反转', '统计2024年上半年数据发现：在趋势末期，当成交量连续3日放大超过前5日均量的150%，且股价涨幅不足3%时，有78%的概率在5日内出现反转。', 'data', ARRAY['数据分析', '成交量', '趋势反转'], 'web-test'),
('失败教训：追高买入的风险', '6月底在新能源板块情绪高涨时追高买入多只个股，结果遭遇回调，损失8%。教训：不要在市场情绪极度乐观时追高，等待回调后再介入。', 'experience', ARRAY['失败教训', '风险控制', '追高'], 'web-test')
ON CONFLICT DO NOTHING;

-- 更新标签统计
INSERT INTO tags (name, count)
SELECT DISTINCT unnest(tags) as name, COUNT(*) OVER (PARTITION BY unnest(tags))
FROM memories
ON CONFLICT (name) DO UPDATE SET count = EXCLUDED.count;
