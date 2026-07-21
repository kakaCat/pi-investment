"""
天山铝业(002532) 分批买入计划 — 写入数据库

创建日期: 2026-05-26
策略类型: stock_buy_plan（个股买入计划）
用途: 可查询、可复用、可自动执行的买入策略模板
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infrastructure.persistence.database.engine import init_engine
from infrastructure.persistence.database.base_repository import BaseRepository

# Initialize database engine
init_engine(pool_size=2, max_overflow=8)


def create_buy_plan():
    """将天山铝业买入计划写入 quant.strategy_configs 表"""
    repo = BaseRepository()
    cursor = repo.db.cursor()

    # 计划参数（完整的买卖规则）
    parameters = {
        "symbol": "002532",
        "name": "天山铝业",
        "market": "A",
        "sector": "有色金属-基本金属-铝",
        "created_at": "2026-05-26",

        # ===== 买入条件 =====
        "entry": {
            "tranches": [
                {"level": 1, "price": 14.62, "pct": 0.005, "trigger": "布林下轨 + 安全买点"},
                {"level": 2, "price": 13.45, "pct": 0.005, "trigger": "跌8%加仓（原买点-8%）"},
                {"level": 3, "price": 12.64, "pct": 0.005, "trigger": "理想买点（深度回调）"},
            ],
            "total_position_pct": 0.015,
            "entry_signals": [
                "价格 ≤ 14.62",
                "MACD柱转正或连续2日收窄",
                "主力资金连续2日净流入",
                "RSI回到40以上"
            ],
            "min_signals_required": 2,
        },

        # ===== 止损规则 =====
        "stop_loss": {
            "method": "fixed_8pct",
            "levels": [
                {"entry_price": 14.62, "stop": 13.45},
                {"entry_price": 13.45, "stop": 12.37},
                {"entry_price": 12.64, "stop": 11.63},
            ],
            "hard_stop_pct": -0.08,
        },

        # ===== 止盈规则 =====
        "take_profit": {
            "tranches": [
                {"label": "保守", "price": 18.92, "pct_gain": 0.294, "sell_ratio": 0.50},
                {"label": "中等", "price": 23.65, "pct_gain": 0.618, "sell_ratio": 0.30},
                {"label": "激进", "price": 31.54, "pct_gain": 1.157, "sell_ratio": 0.20},
            ],
        },

        # ===== 基本面快照 =====
        "fundamentals": {
            "roe": 29.08,
            "roe_trend": "上升",
            "debt_ratio": 39.94,
            "gross_margin": 35.61,
            "net_margin": 26.19,
            "quality_score": 93,
            "quality_grade": "A（优质）",
        },

        # ===== 估值快照 =====
        "valuation": {
            "pe": 11.92,
            "pe_percentile": 88.8,
            "pb": 2.27,
            "fair_value": 24.48,
            "valuation_status": "cheap_absolute_but_cyclical_trap",
        },

        # ===== 技术面快照 =====
        "technicals": {
            "current_price": 14.82,
            "ma5": 15.90,
            "ma10": 16.21,
            "ma20": 17.07,
            "ma60": 17.39,
            "macd": -0.551,
            "rsi14": 33.3,
            "trend": "全面空头排列",
            "candlestick": "看跌吞没(2026-05-25)",
            "key_support": [14.68, 14.66, 13.45],
            "key_resistance": [16.44, 17.39, 19.13],
        },

        # ===== 风险矩阵 =====
        "risks": [
            {"factor": "铝价下跌", "level": "high", "detail": "核心风险，铝价每跌10%利润降20-30%"},
            {"factor": "PE分位过高", "level": "medium", "detail": "PE 88.8%分位，周期股低PE陷阱"},
            {"factor": "技术空头", "level": "medium", "detail": "全面空头排列，短期无反转信号"},
            {"factor": "主力流出", "level": "medium", "detail": "近10日主力净卖出为主"},
        ],

        # ===== 自动执行配置 =====
        "auto_execution": {
            "enabled": False,
            "check_interval_minutes": 60,
            "action": "create_limit_order",
            "limit_order_price": 14.62,
            "message": "天山铝业触及安全买点14.62，是否执行第1批买入？",
        },
    }

    # 检查是否已有该计划
    cursor.execute(
        "SELECT id, strategy_name FROM quant.strategy_configs WHERE strategy_name = %s",
        ("天山铝业(002532) 分批买入计划",)
    )
    existing = cursor.fetchone()

    if existing:
        # 更新已有计划
        cursor.execute("""
            UPDATE quant.strategy_configs
            SET parameters = %s,
                description = %s,
                metadata = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id
        """, (
            json.dumps(parameters),
            "2026-05-26 深度分析：工业金属行业精选，天山铝业三档分批买入策略。基本面A级(93分)，ROE 29%，PE 11.92。等待价格回调至14.62以下建仓。",
            json.dumps({
                "source": "pi-invest agent deep analysis",
                "analysis_file": ".pi-invest/reviews/002532-天山铝业-深研-2026-05-26.md",
                "strategy_pipeline": ["行业轮动→工业金属top3", "因子精选→5选1", "ML置信过滤→0.661通过"],
                "tags": ["工业金属", "铝业", "周期股", "价值型", "分批建仓"],
            }),
            existing["id"],
        ))
        plan_id = existing["id"]
        action = "updated"
    else:
        # 创建新计划
        cursor.execute("""
            INSERT INTO quant.strategy_configs (
                strategy_name, strategy_type, description, parameters,
                metadata, is_active, version, author
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id
        """, (
            "天山铝业(002532) 分批买入计划",
            "stock_buy_plan",
            "2026-05-26 深度分析：工业金属行业精选，天山铝业三档分批买入策略。基本面A级(93分)，ROE 29%，PE 11.92。等待价格回调至14.62以下建仓。",
            json.dumps(parameters),
            json.dumps({
                "source": "pi-invest agent deep analysis",
                "analysis_file": ".pi-invest/reviews/002532-天山铝业-深研-2026-05-26.md",
                "strategy_pipeline": ["行业轮动→工业金属top3", "因子精选→5选1", "ML置信过滤→0.661通过"],
                "tags": ["工业金属", "铝业", "周期股", "价值型", "分批建仓"],
            }),
            True,
            "v1.0",
            "pi-agent",
        ))
        result = cursor.fetchone()
        plan_id = result["id"]
        action = "created"

    repo.db.commit()
    cursor.close()

    print(f"✅ 买入计划 {action} (ID: {plan_id})")
    print(f"   表: quant.strategy_configs")
    print(f"   类型: stock_buy_plan")
    print(f"   查询: SELECT * FROM quant.strategy_configs WHERE id = {plan_id};")
    return plan_id


if __name__ == "__main__":
    create_buy_plan()
