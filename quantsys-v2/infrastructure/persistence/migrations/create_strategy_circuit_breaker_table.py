"""
创建策略熔断器表

用于存储策略的熔断状态
"""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS quant.strategy_circuit_breaker (
    strategy_name VARCHAR(255) PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    consecutive_losses INTEGER NOT NULL DEFAULT 0,
    consecutive_wins INTEGER NOT NULL DEFAULT 0,
    rolling_win_rate DECIMAL(5, 4),
    recent_trades JSONB,
    reason TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_circuit_breaker_status
ON quant.strategy_circuit_breaker(status);

CREATE INDEX IF NOT EXISTS idx_circuit_breaker_updated
ON quant.strategy_circuit_breaker(updated_at DESC);

COMMENT ON TABLE quant.strategy_circuit_breaker IS '策略熔断器状态表';
COMMENT ON COLUMN quant.strategy_circuit_breaker.strategy_name IS '策略名称';
COMMENT ON COLUMN quant.strategy_circuit_breaker.status IS '熔断状态: active/warning/suspended';
COMMENT ON COLUMN quant.strategy_circuit_breaker.consecutive_losses IS '连续亏损次数';
COMMENT ON COLUMN quant.strategy_circuit_breaker.consecutive_wins IS '连续盈利次数';
COMMENT ON COLUMN quant.strategy_circuit_breaker.rolling_win_rate IS '滚动胜率（20笔）';
COMMENT ON COLUMN quant.strategy_circuit_breaker.recent_trades IS '最近交易记录（JSON数组）';
COMMENT ON COLUMN quant.strategy_circuit_breaker.reason IS '状态变更原因';
"""


def upgrade(cursor):
    """执行升级"""
    cursor.execute(CREATE_TABLE_SQL)


def downgrade(cursor):
    """执行降级"""
    cursor.execute("DROP TABLE IF EXISTS quant.strategy_circuit_breaker;")


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine

    load_dotenv()

    engine = get_engine()
    conn = engine.raw_connection()

    try:
        cursor = conn.cursor()
        print("创建策略熔断器表...")
        upgrade(cursor)
        conn.commit()
        print("✓ 表创建成功")
    except Exception as e:
        print(f"✗ 创建失败: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()  # 归还给 Engine 池
