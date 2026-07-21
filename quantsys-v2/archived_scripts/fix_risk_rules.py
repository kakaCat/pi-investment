#!/usr/bin/env python3
"""
缺陷4修复：初始化风控规则
创建默认的风险控制规则
"""

import sys
import os

# 确保在正确的目录
os.chdir('/Users/mac/Documents/ai/pi-investment/quantsys-v2')
sys.path.insert(0, '/Users/mac/Documents/ai/pi-investment/quantsys-v2')

from infrastructure.database import get_session
from sqlalchemy import text

def init_risk_rules():
    """初始化默认风控规则"""
    print("=" * 60)
    print("  初始化风控规则")
    print("=" * 60)

    session = get_session()

    try:
        # 检查表是否存在
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'risk_rules'
            );
        """))
        table_exists = result.scalar()

        if not table_exists:
            print("❌ risk_rules 表不存在，需要创建")
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS risk_rules (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    rule_type VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20),
                    enabled BOOLEAN DEFAULT true,
                    stop_loss_percent DECIMAL(5,4),
                    take_profit_percent DECIMAL(5,4),
                    max_position_percent DECIMAL(5,4),
                    max_sector_percent DECIMAL(5,4),
                    max_single_loss_percent DECIMAL(5,4),
                    trailing_stop BOOLEAN DEFAULT false,
                    atr_multiple DECIMAL(5,2),
                    max_hold_days INTEGER,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """))
            session.commit()
            print("✅ risk_rules 表已创建")

        # 检查现有规则数量
        result = session.execute(text("SELECT COUNT(*) FROM risk_rules"))
        count = result.scalar()
        print(f"\n当前风控规则数量: {count}")

        if count > 0:
            print("✅ 风控规则已存在，跳过初始化")
            # 显示现有规则
            result = session.execute(text("""
                SELECT name, rule_type, enabled
                FROM risk_rules
                ORDER BY id
            """))
            print("\n现有规则列表:")
            for row in result:
                status = "启用" if row[2] else "禁用"
                print(f"  • {row[0]} ({row[1]}) - {status}")
            return

        # 插入默认规则
        default_rules = [
            {
                'name': '全局止损规则',
                'rule_type': 'stop_loss',
                'symbol': None,
                'enabled': True,
                'stop_loss_percent': 0.08,
                'take_profit_percent': None,
                'max_position_percent': None,
                'max_sector_percent': None,
                'max_single_loss_percent': None,
                'trailing_stop': False,
                'atr_multiple': None,
                'max_hold_days': None,
                'description': '全局止损：单个持仓下跌8%自动止损'
            },
            {
                'name': '全局止盈规则',
                'rule_type': 'take_profit',
                'symbol': None,
                'enabled': True,
                'stop_loss_percent': None,
                'take_profit_percent': 0.20,
                'max_position_percent': None,
                'max_sector_percent': None,
                'max_single_loss_percent': None,
                'trailing_stop': False,
                'atr_multiple': None,
                'max_hold_days': None,
                'description': '全局止盈：单个持仓上涨20%自动止盈'
            },
            {
                'name': '单股仓位限制',
                'rule_type': 'position_limit',
                'symbol': None,
                'enabled': True,
                'stop_loss_percent': None,
                'take_profit_percent': None,
                'max_position_percent': 0.20,
                'max_sector_percent': None,
                'max_single_loss_percent': None,
                'trailing_stop': False,
                'atr_multiple': None,
                'max_hold_days': None,
                'description': '单只股票最大仓位不超过总资金的20%'
            },
            {
                'name': '单行业仓位限制',
                'rule_type': 'sector_limit',
                'symbol': None,
                'enabled': True,
                'stop_loss_percent': None,
                'take_profit_percent': None,
                'max_position_percent': None,
                'max_sector_percent': 0.40,
                'max_single_loss_percent': None,
                'trailing_stop': False,
                'atr_multiple': None,
                'max_hold_days': None,
                'description': '单个行业最大仓位不超过总资金的40%'
            },
            {
                'name': '单日最大亏损限制',
                'rule_type': 'daily_loss_limit',
                'symbol': None,
                'enabled': True,
                'stop_loss_percent': None,
                'take_profit_percent': None,
                'max_position_percent': None,
                'max_sector_percent': None,
                'max_single_loss_percent': 0.05,
                'trailing_stop': False,
                'atr_multiple': None,
                'max_hold_days': None,
                'description': '单日总亏损不超过总资金的5%，触发后停止交易'
            }
        ]

        print(f"\n插入 {len(default_rules)} 条默认规则...")

        for rule_data in default_rules:
            session.execute(text("""
                INSERT INTO risk_rules (
                    name, rule_type, symbol, enabled,
                    stop_loss_percent, take_profit_percent,
                    max_position_percent, max_sector_percent,
                    max_single_loss_percent, trailing_stop,
                    atr_multiple, max_hold_days, description
                ) VALUES (
                    :name, :rule_type, :symbol, :enabled,
                    :stop_loss_percent, :take_profit_percent,
                    :max_position_percent, :max_sector_percent,
                    :max_single_loss_percent, :trailing_stop,
                    :atr_multiple, :max_hold_days, :description
                )
            """), rule_data)
            print(f"  ✅ {rule_data['name']}")

        session.commit()
        print(f"\n✅ 成功初始化 {len(default_rules)} 条风控规则")

        # 验证
        result = session.execute(text("""
            SELECT name, rule_type, enabled
            FROM risk_rules
            ORDER BY id
        """))

        print("\n最终规则列表:")
        for row in result:
            status = "启用" if row[2] else "禁用"
            print(f"  • {row[0]} ({row[1]}) - {status}")

    except Exception as e:
        session.rollback()
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    init_risk_rules()
