-- ============================================
-- Agent 智能系统表迁移
-- 日期: 2026-06-25
-- 说明: 删除旧表并创建新的智能系统表
-- ============================================

-- 备份旧表（如果需要）
-- CREATE TABLE quant.agent_decisions_backup AS SELECT * FROM quant.agent_decisions;

-- 删除旧表
DROP TABLE IF EXISTS quant.agent_decisions CASCADE;
DROP TABLE IF EXISTS quant.agent_knowledge CASCADE;
DROP TABLE IF EXISTS quant.pool_change_log CASCADE;
DROP TABLE IF EXISTS quant.opponent_behavior_snapshot CASCADE;
DROP TABLE IF EXISTS quant.pool_game_metrics CASCADE;
DROP TABLE IF EXISTS quant.manipulation_events CASCADE;
DROP TABLE IF EXISTS quant.pool_health_history CASCADE;

-- ============================================
-- 重新创建表
-- ============================================

-- 1. Agent 决策日志表
CREATE TABLE quant.agent_decisions (
  id SERIAL PRIMARY KEY,
  decision_id VARCHAR(50) UNIQUE NOT NULL,
  decision_type VARCHAR(50) NOT NULL,
  context JSONB NOT NULL,
  parameters JSONB NOT NULL,
  reasoning TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  created_by VARCHAR(50) DEFAULT 'agent',

  evaluation_status VARCHAR(20) DEFAULT 'pending',
  evaluation_result JSONB,
  evaluation_date TIMESTAMP,

  learned_lesson TEXT,
  confidence_score FLOAT,
  success BOOLEAN,

  related_entity_type VARCHAR(50),
  related_entity_id VARCHAR(50)
);

CREATE INDEX idx_agent_decisions_type ON quant.agent_decisions(decision_type);
CREATE INDEX idx_agent_decisions_status ON quant.agent_decisions(evaluation_status);
CREATE INDEX idx_agent_decisions_created_at ON quant.agent_decisions(created_at DESC);
CREATE INDEX idx_agent_decisions_entity ON quant.agent_decisions(related_entity_type, related_entity_id);

COMMENT ON TABLE quant.agent_decisions IS 'Agent决策日志：记录每个决策的上下文、参数、推理、结果';


-- 2. Agent 知识库表
CREATE TABLE quant.agent_knowledge (
  id SERIAL PRIMARY KEY,
  knowledge_id VARCHAR(50) UNIQUE NOT NULL,
  domain VARCHAR(100) NOT NULL,
  knowledge_type VARCHAR(50) NOT NULL,
  content JSONB NOT NULL,
  confidence FLOAT DEFAULT 0.5,
  evidence JSONB,
  learned_at TIMESTAMP DEFAULT NOW(),
  last_validated TIMESTAMP,
  validation_count INT DEFAULT 0,
  success_count INT DEFAULT 0,
  status VARCHAR(20) DEFAULT 'active',
  created_by VARCHAR(50) DEFAULT 'system'
);

CREATE INDEX idx_agent_knowledge_domain ON quant.agent_knowledge(domain);
CREATE INDEX idx_agent_knowledge_type ON quant.agent_knowledge(knowledge_type);
CREATE INDEX idx_agent_knowledge_status ON quant.agent_knowledge(status);
CREATE INDEX idx_agent_knowledge_confidence ON quant.agent_knowledge(confidence DESC);

COMMENT ON TABLE quant.agent_knowledge IS 'Agent知识库：存储从经验中学到的规则和模式';


-- 3. 池子变更日志表
CREATE TABLE quant.pool_change_log (
  id SERIAL PRIMARY KEY,
  pool_id INT REFERENCES quant.stock_pools(id),
  changed_at TIMESTAMP DEFAULT NOW(),
  action VARCHAR(20) NOT NULL,
  symbol VARCHAR(20),
  reason TEXT,
  triggered_by VARCHAR(50),
  agent_decision_id VARCHAR(50),
  context JSONB,
  before_state JSONB,
  after_state JSONB
);

CREATE INDEX idx_pool_change_log_pool_id ON quant.pool_change_log(pool_id);
CREATE INDEX idx_pool_change_log_changed_at ON quant.pool_change_log(changed_at DESC);
CREATE INDEX idx_pool_change_log_action ON quant.pool_change_log(action);
CREATE INDEX idx_pool_change_log_triggered_by ON quant.pool_change_log(triggered_by);
CREATE INDEX idx_pool_change_log_symbol ON quant.pool_change_log(symbol);

COMMENT ON TABLE quant.pool_change_log IS '池子变更日志：追踪所有池子成员变化及原因';


-- 4. 对手行为快照表
CREATE TABLE quant.opponent_behavior_snapshot (
  id SERIAL PRIMARY KEY,
  snapshot_time TIMESTAMP DEFAULT NOW(),

  retail_behavior VARCHAR(50),
  retail_net_flow BIGINT,
  retail_emotion_index FLOAT,

  institution_behavior VARCHAR(50),
  institution_net_flow BIGINT,
  institution_target_sectors JSONB,

  hot_money_behavior VARCHAR(50),
  hot_money_target_stocks JSONB,
  hot_money_stage VARCHAR(50),

  market_phase VARCHAR(50),
  risk_appetite VARCHAR(20),
  opportunities JSONB
);

CREATE INDEX idx_opponent_snapshot_time ON quant.opponent_behavior_snapshot(snapshot_time DESC);
CREATE INDEX idx_opponent_snapshot_market_phase ON quant.opponent_behavior_snapshot(market_phase);

COMMENT ON TABLE quant.opponent_behavior_snapshot IS '对手行为快照：定时记录市场参与者行为';


-- 5. 池子博弈指标表
CREATE TABLE quant.pool_game_metrics (
  id SERIAL PRIMARY KEY,
  pool_id INT REFERENCES quant.stock_pools(id),
  measured_at TIMESTAMP DEFAULT NOW(),

  battlefield_score FLOAT,
  opponent_strength JSONB,
  game_phase VARCHAR(50),
  advantages JSONB,
  disadvantages JSONB,
  recommendation VARCHAR(50),
  urgency VARCHAR(20),
  confidence FLOAT
);

CREATE INDEX idx_pool_game_metrics_pool_id ON quant.pool_game_metrics(pool_id);
CREATE INDEX idx_pool_game_metrics_time ON quant.pool_game_metrics(measured_at DESC);
CREATE INDEX idx_pool_game_metrics_score ON quant.pool_game_metrics(battlefield_score DESC);
CREATE INDEX idx_pool_game_metrics_recommendation ON quant.pool_game_metrics(recommendation);

COMMENT ON TABLE quant.pool_game_metrics IS '池子博弈指标：评估池子的竞争优势和博弈位置';


-- 6. 操纵事件表
CREATE TABLE quant.manipulation_events (
  id SERIAL PRIMARY KEY,
  symbol VARCHAR(20) NOT NULL,
  detected_at TIMESTAMP DEFAULT NOW(),

  manipulation_type VARCHAR(50) NOT NULL,
  stage VARCHAR(50),
  detection_signals JSONB,
  confidence FLOAT,
  suspected_manipulator VARCHAR(50),

  price_at_detection FLOAT,
  fair_value_estimate FLOAT,
  deviation_pct FLOAT,

  status VARCHAR(20) DEFAULT 'active',
  resolved_at TIMESTAMP
);

CREATE INDEX idx_manipulation_symbol ON quant.manipulation_events(symbol);
CREATE INDEX idx_manipulation_detected_at ON quant.manipulation_events(detected_at DESC);
CREATE INDEX idx_manipulation_type ON quant.manipulation_events(manipulation_type);
CREATE INDEX idx_manipulation_status ON quant.manipulation_events(status);

COMMENT ON TABLE quant.manipulation_events IS '操纵事件记录：追踪检测到的市场操纵行为';


-- 7. 池子健康度历史表
CREATE TABLE quant.pool_health_history (
  id SERIAL PRIMARY KEY,
  pool_id INT REFERENCES quant.stock_pools(id),
  measured_date DATE NOT NULL,

  avg_score FLOAT,
  avg_roe FLOAT,
  avg_pe FLOAT,
  avg_pb FLOAT,

  return_1d FLOAT,
  return_1w FLOAT,
  return_1m FLOAT,
  vs_market FLOAT,

  volatility FLOAT,
  max_drawdown FLOAT,

  member_count INT,
  turnover_rate FLOAT,

  UNIQUE(pool_id, measured_date)
);

CREATE INDEX idx_pool_health_pool_id ON quant.pool_health_history(pool_id);
CREATE INDEX idx_pool_health_date ON quant.pool_health_history(measured_date DESC);

COMMENT ON TABLE quant.pool_health_history IS '池子健康度历史：追踪池子质量和表现的时间序列';


-- ============================================
-- 初始化示例数据
-- ============================================

INSERT INTO quant.agent_knowledge (knowledge_id, domain, knowledge_type, content, confidence, status)
VALUES
  ('know_001', 'sector:白酒', 'filter_rule',
   '{"rule": "min_roe >= 15", "reason": "白酒行业优质股标准"}'::jsonb,
   0.5, 'active'),
  ('know_002', 'general', 'risk_threshold',
   '{"rule": "max_drawdown <= -10%", "reason": "风险控制标准"}'::jsonb,
   0.8, 'active')
ON CONFLICT (knowledge_id) DO NOTHING;

-- 验证表创建
SELECT
  'agent_decisions' as table_name,
  COUNT(*) as row_count
FROM quant.agent_decisions
UNION ALL
SELECT 'agent_knowledge', COUNT(*) FROM quant.agent_knowledge
UNION ALL
SELECT 'pool_change_log', COUNT(*) FROM quant.pool_change_log
UNION ALL
SELECT 'opponent_behavior_snapshot', COUNT(*) FROM quant.opponent_behavior_snapshot
UNION ALL
SELECT 'pool_game_metrics', COUNT(*) FROM quant.pool_game_metrics
UNION ALL
SELECT 'manipulation_events', COUNT(*) FROM quant.manipulation_events
UNION ALL
SELECT 'pool_health_history', COUNT(*) FROM quant.pool_health_history;
