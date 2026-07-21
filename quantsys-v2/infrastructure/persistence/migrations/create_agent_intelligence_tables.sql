-- ============================================
-- Agent 智能系统核心表
-- 创建日期: 2026-06-25
-- 用途: 支持 Agent 博弈智能和自主学习
-- ============================================

-- 1. Agent 决策日志表
CREATE TABLE IF NOT EXISTS quant.agent_decisions (
  id SERIAL PRIMARY KEY,
  decision_id VARCHAR(50) UNIQUE NOT NULL,  -- 唯一决策ID
  decision_type VARCHAR(50) NOT NULL,       -- create_pool, refresh_pool, buy_stock, sell_stock
  context JSONB NOT NULL,                   -- 决策时的上下文
  parameters JSONB NOT NULL,                -- 决策参数
  reasoning TEXT,                           -- Agent 的推理过程
  created_at TIMESTAMP DEFAULT NOW(),
  created_by VARCHAR(50) DEFAULT 'agent',   -- agent | user

  -- 评估字段
  evaluation_status VARCHAR(20) DEFAULT 'pending',  -- pending, evaluating, evaluated
  evaluation_result JSONB,                  -- 评估结果
  evaluation_date TIMESTAMP,

  -- 学习字段
  learned_lesson TEXT,                      -- 学到的教训
  confidence_score FLOAT,                   -- 置信度 0-1
  success BOOLEAN,                          -- 决策是否成功

  -- 关联字段
  related_entity_type VARCHAR(50),          -- pool, stock, strategy
  related_entity_id VARCHAR(50)             -- 关联的实体ID
);

CREATE INDEX idx_agent_decisions_type ON quant.agent_decisions(decision_type);
CREATE INDEX idx_agent_decisions_status ON quant.agent_decisions(evaluation_status);
CREATE INDEX idx_agent_decisions_created_at ON quant.agent_decisions(created_at DESC);
CREATE INDEX idx_agent_decisions_entity ON quant.agent_decisions(related_entity_type, related_entity_id);

COMMENT ON TABLE quant.agent_decisions IS 'Agent决策日志：记录每个决策的上下文、参数、推理、结果';
COMMENT ON COLUMN quant.agent_decisions.decision_id IS '唯一决策ID，格式：dec_<timestamp>_<random>';
COMMENT ON COLUMN quant.agent_decisions.context IS '决策时的市场环境、池子状态等上下文信息';
COMMENT ON COLUMN quant.agent_decisions.reasoning IS 'Agent 的推理过程（自然语言）';


-- 2. Agent 知识库表
CREATE TABLE IF NOT EXISTS quant.agent_knowledge (
  id SERIAL PRIMARY KEY,
  knowledge_id VARCHAR(50) UNIQUE NOT NULL,
  domain VARCHAR(100) NOT NULL,            -- sector:白酒, sector:医药, strategy:macd
  knowledge_type VARCHAR(50) NOT NULL,     -- filter_rule, strategy_param, risk_threshold
  content JSONB NOT NULL,                  -- 知识内容
  confidence FLOAT DEFAULT 0.5,            -- 置信度 0-1
  evidence JSONB,                          -- 支撑证据（决策ID列表）
  learned_at TIMESTAMP DEFAULT NOW(),
  last_validated TIMESTAMP,
  validation_count INT DEFAULT 0,          -- 验证次数
  success_count INT DEFAULT 0,             -- 成功次数
  status VARCHAR(20) DEFAULT 'active',     -- active, testing, deprecated
  created_by VARCHAR(50) DEFAULT 'system'
);

CREATE INDEX idx_agent_knowledge_domain ON quant.agent_knowledge(domain);
CREATE INDEX idx_agent_knowledge_type ON quant.agent_knowledge(knowledge_type);
CREATE INDEX idx_agent_knowledge_status ON quant.agent_knowledge(status);
CREATE INDEX idx_agent_knowledge_confidence ON quant.agent_knowledge(confidence DESC);

COMMENT ON TABLE quant.agent_knowledge IS 'Agent知识库：存储从经验中学到的规则和模式';
COMMENT ON COLUMN quant.agent_knowledge.domain IS '知识适用的领域，如：sector:白酒、strategy:macd';
COMMENT ON COLUMN quant.agent_knowledge.confidence IS '知识置信度，基于成功率自动更新';


-- 3. 池子变更日志表
CREATE TABLE IF NOT EXISTS quant.pool_change_log (
  id SERIAL PRIMARY KEY,
  pool_id INT REFERENCES quant.stock_pools(id),
  changed_at TIMESTAMP DEFAULT NOW(),
  action VARCHAR(20) NOT NULL,             -- add, remove, refresh, update
  symbol VARCHAR(20),                      -- 股票代码（add/remove时有）
  reason TEXT,                             -- 变更原因
  triggered_by VARCHAR(50),                -- agent_auto, user_manual, scheduled
  agent_decision_id VARCHAR(50),           -- 关联的决策ID
  context JSONB,                           -- 变更时的上下文

  -- 变更前后状态
  before_state JSONB,
  after_state JSONB
);

CREATE INDEX idx_pool_change_log_pool_id ON quant.pool_change_log(pool_id);
CREATE INDEX idx_pool_change_log_changed_at ON quant.pool_change_log(changed_at DESC);
CREATE INDEX idx_pool_change_log_action ON quant.pool_change_log(action);
CREATE INDEX idx_pool_change_log_triggered_by ON quant.pool_change_log(triggered_by);
CREATE INDEX idx_pool_change_log_symbol ON quant.pool_change_log(symbol);

COMMENT ON TABLE quant.pool_change_log IS '池子变更日志：追踪所有池子成员变化及原因';
COMMENT ON COLUMN quant.pool_change_log.reason IS '变更原因（自然语言），如：ROE下降至12%，低于15%阈值';


-- 4. 对手行为快照表
CREATE TABLE IF NOT EXISTS quant.opponent_behavior_snapshot (
  id SERIAL PRIMARY KEY,
  snapshot_time TIMESTAMP DEFAULT NOW(),

  -- 散户行为
  retail_behavior VARCHAR(50),             -- panic_selling, fomo_buying, neutral
  retail_net_flow BIGINT,                  -- 净流入（单位：元）
  retail_emotion_index FLOAT,              -- 情绪指数 0-100

  -- 机构行为
  institution_behavior VARCHAR(50),        -- accumulating, distributing, neutral
  institution_net_flow BIGINT,
  institution_target_sectors JSONB,        -- 目标板块

  -- 游资行为
  hot_money_behavior VARCHAR(50),          -- pump_and_dump, inactive
  hot_money_target_stocks JSONB,           -- 目标股票
  hot_money_stage VARCHAR(50),             -- accumulation, markup, distribution

  -- 市场整体
  market_phase VARCHAR(50),                -- bull, bear, consolidation, accumulation, distribution
  risk_appetite VARCHAR(20),               -- high, medium, low

  -- 机会映射
  opportunities JSONB                      -- 当前的博弈机会
);

CREATE INDEX idx_opponent_snapshot_time ON quant.opponent_behavior_snapshot(snapshot_time DESC);
CREATE INDEX idx_opponent_snapshot_market_phase ON quant.opponent_behavior_snapshot(market_phase);

COMMENT ON TABLE quant.opponent_behavior_snapshot IS '对手行为快照：定时记录市场参与者行为';
COMMENT ON COLUMN quant.opponent_behavior_snapshot.retail_emotion_index IS '0-20:极度恐慌 20-40:恐慌 40-60:中性 60-80:贪婪 80-100:极度贪婪';


-- 5. 池子博弈指标表
CREATE TABLE IF NOT EXISTS quant.pool_game_metrics (
  id SERIAL PRIMARY KEY,
  pool_id INT REFERENCES quant.stock_pools(id),
  measured_at TIMESTAMP DEFAULT NOW(),

  -- 战场评分
  battlefield_score FLOAT,                 -- 0-100，战场优势评分

  -- 对手分析
  opponent_strength JSONB,                 -- {institution: 'strong', retail: 'weak'}
  game_phase VARCHAR(50),                  -- accumulation, markup, distribution, markdown

  -- 优劣势
  advantages JSONB,                        -- 我方优势列表
  disadvantages JSONB,                     -- 我方劣势列表

  -- 推荐
  recommendation VARCHAR(50),              -- enter, hold, exit, avoid
  urgency VARCHAR(20),                     -- low, medium, high, critical
  confidence FLOAT                         -- 推荐置信度
);

CREATE INDEX idx_pool_game_metrics_pool_id ON quant.pool_game_metrics(pool_id);
CREATE INDEX idx_pool_game_metrics_time ON quant.pool_game_metrics(measured_at DESC);
CREATE INDEX idx_pool_game_metrics_score ON quant.pool_game_metrics(battlefield_score DESC);
CREATE INDEX idx_pool_game_metrics_recommendation ON quant.pool_game_metrics(recommendation);

COMMENT ON TABLE quant.pool_game_metrics IS '池子博弈指标：评估池子的竞争优势和博弈位置';
COMMENT ON COLUMN quant.pool_game_metrics.battlefield_score IS '战场优势综合评分：估值20% 对手30% 趋势25% 流动性15% 时机10%';


-- 6. 操纵事件表
CREATE TABLE IF NOT EXISTS quant.manipulation_events (
  id SERIAL PRIMARY KEY,
  symbol VARCHAR(20) NOT NULL,
  detected_at TIMESTAMP DEFAULT NOW(),

  -- 操纵类型
  manipulation_type VARCHAR(50) NOT NULL,  -- pump_and_dump, wash_trading, spoofing
  stage VARCHAR(50),                       -- accumulation, markup, distribution, collapse

  -- 检测指标
  detection_signals JSONB,                 -- 检测到的异常信号
  confidence FLOAT,                        -- 检测置信度

  -- 操纵者
  suspected_manipulator VARCHAR(50),       -- hot_money, institution, unknown

  -- 价格信息
  price_at_detection FLOAT,
  fair_value_estimate FLOAT,
  deviation_pct FLOAT,                     -- 偏离度

  -- 状态
  status VARCHAR(20) DEFAULT 'active',     -- active, completed, false_alarm
  resolved_at TIMESTAMP
);

CREATE INDEX idx_manipulation_symbol ON quant.manipulation_events(symbol);
CREATE INDEX idx_manipulation_detected_at ON quant.manipulation_events(detected_at DESC);
CREATE INDEX idx_manipulation_type ON quant.manipulation_events(manipulation_type);
CREATE INDEX idx_manipulation_status ON quant.manipulation_events(status);

COMMENT ON TABLE quant.manipulation_events IS '操纵事件记录：追踪检测到的市场操纵行为';
COMMENT ON COLUMN quant.manipulation_events.manipulation_type IS 'pump_and_dump:拉高出货 wash_trading:对倒 spoofing:虚假报价';


-- 7. 池子健康度历史表
CREATE TABLE IF NOT EXISTS quant.pool_health_history (
  id SERIAL PRIMARY KEY,
  pool_id INT REFERENCES quant.stock_pools(id),
  measured_date DATE NOT NULL,

  -- 质量指标
  avg_score FLOAT,                         -- 平均质量评分
  avg_roe FLOAT,                           -- 平均 ROE
  avg_pe FLOAT,                            -- 平均 PE
  avg_pb FLOAT,                            -- 平均 PB

  -- 收益指标
  return_1d FLOAT,                         -- 日收益率
  return_1w FLOAT,                         -- 周收益率
  return_1m FLOAT,                         -- 月收益率
  vs_market FLOAT,                         -- 相对市场收益

  -- 风险指标
  volatility FLOAT,                        -- 波动率
  max_drawdown FLOAT,                      -- 最大回撤

  -- 成员统计
  member_count INT,                        -- 成员数量
  turnover_rate FLOAT,                     -- 换手率（成员变化比例）

  UNIQUE(pool_id, measured_date)
);

CREATE INDEX idx_pool_health_pool_id ON quant.pool_health_history(pool_id);
CREATE INDEX idx_pool_health_date ON quant.pool_health_history(measured_date DESC);

COMMENT ON TABLE quant.pool_health_history IS '池子健康度历史：追踪池子质量和表现的时间序列';


-- ============================================
-- 初始化数据
-- ============================================

-- 插入示例知识（可选）
INSERT INTO quant.agent_knowledge (knowledge_id, domain, knowledge_type, content, confidence, status)
VALUES
  ('know_001', 'sector:白酒', 'filter_rule',
   '{"rule": "min_roe >= 15", "reason": "白酒行业优质股标准"}',
   0.5, 'active'),
  ('know_002', 'general', 'risk_threshold',
   '{"rule": "max_drawdown <= -10%", "reason": "风险控制标准"}',
   0.8, 'active')
ON CONFLICT (knowledge_id) DO NOTHING;
