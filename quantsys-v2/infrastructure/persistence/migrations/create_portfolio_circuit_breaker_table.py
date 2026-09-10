import logging

logger = logging.getLogger(__name__)

"""创建组合级回撤熔断状态表（M4 硬拦截，2026-09-10，w-f4aa1f6a）

区分：quant.strategy_circuit_breaker = 策略级熔断（连续亏损/低胜率暂停策略）
     quant.portfolio_circuit_breaker = 组合级回撤熔断（60日回撤>8% 禁止新开仓）

本表是 trade_guard 买入硬拦截的数据源；M4 工具触发/解除时双写。
2026-09-10 已直接 psql 建表上线，本文件供幂等复现。
"""

from infrastructure.persistence.database.engine import db_cursor

DDL = """
CREATE TABLE IF NOT EXISTS quant.portfolio_circuit_breaker (
    account_name VARCHAR(64) PRIMARY KEY,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    triggered_at TIMESTAMPTZ,
    triggered_drawdown NUMERIC(8,2),
    actions_taken JSONB,
    unblock_condition TEXT,
    note TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE quant.portfolio_circuit_breaker IS 'M4 组合级回撤熔断状态（交易网关硬拦截数据源；区分策略级 strategy_circuit_breaker）';
"""


def run_migration():
    with db_cursor(commit=True) as cur:
        cur.execute(DDL)
    logger.info("✅ quant.portfolio_circuit_breaker 表已就绪")


if __name__ == '__main__':
    run_migration()
