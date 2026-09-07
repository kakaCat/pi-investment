"""
P2.2 E2E 测试夹具和辅助工具

提供进化引擎、调度器、Agent 决策闭环测试所需的辅助函数。

实际 DB 表结构（quant schema）:
- quant.agent_decisions: decision_id, decision_type, context(jsonb),
  parameters(jsonb), evaluation_status, score, score_band,
  confidence_score, created_at ...
- quant.evolution_fitness: account_name, window_end, window_days,
  up_capture, down_capture, fitness, up_days, down_days, status, computed_at
- quant.inprocess_job_runs: job_id, run_date, status, started_at,
  finished_at, result(jsonb), error
- quant.daily_klines: symbol, trade_date, open, high, low, close,
  volume, amount, turnover_rate, remark, source
"""
import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional


# ═══════════════════════════════════════════════════════════════
# 数据库辅助
# ═══════════════════════════════════════════════════════════════

def get_test_db_conn():
    """获取测试数据库连接"""
    import os
    import psycopg2
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=int(os.environ.get('PGPORT', '5432')),
        database=os.environ.get('PGDATABASE', 'quant_test'),
    )


def cleanup_test_decisions(conn, test_prefix: str = "E2E_TEST"):
    """清理测试决策数据"""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM quant.agent_decisions WHERE decision_id LIKE %s",
            (f"{test_prefix}%",)
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cursor.close()


def cleanup_test_fitness(conn, test_account: str = "test_agent_virtual"):
    """清理测试适应度数据"""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM quant.evolution_fitness WHERE account_name = %s",
            (test_account,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cursor.close()


def cleanup_test_job_runs(conn, test_prefix: str = "E2E_TEST"):
    """清理测试调度器运行记录"""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM quant.inprocess_job_runs WHERE job_id LIKE %s",
            (f"{test_prefix}%",)
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cursor.close()


# ═══════════════════════════════════════════════════════════════
# 决策创建辅助
# ═══════════════════════════════════════════════════════════════

def create_test_decision(
    conn,
    decision_id: str,
    symbol: str = "600519.SH",
    action: str = "trade_buy",
    price: float = 1650.00,
    quantity: int = 100,
    created_at: Optional[date] = None,
    test_prefix: str = "E2E_TEST"
) -> str:
    """创建测试决策（使用实际 quant.agent_decisions 表结构）"""
    if created_at is None:
        created_at = date.today() - timedelta(days=25)

    full_decision_id = f"{test_prefix}_{decision_id}"
    created_dt = (datetime.combine(created_at, datetime.min.time())
                  if isinstance(created_at, date) and not isinstance(created_at, datetime)
                  else created_at)

    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO quant.agent_decisions
            (decision_id, decision_type, context, parameters,
             evaluation_status, confidence_score, created_at)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)
            ON CONFLICT (decision_id) DO NOTHING
        """, (
            full_decision_id,
            action,
            json.dumps({"source": "e2e_test"}),
            json.dumps({"symbol": symbol, "price": price, "quantity": quantity}),
            "pending",
            0.85,
            created_dt,
        ))
        conn.commit()
        return full_decision_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()


def get_decision(conn, decision_id: str) -> Optional[Dict[str, Any]]:
    """获取决策详情"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT decision_id, decision_type, parameters,
                   evaluation_status, score, score_band, confidence_score
            FROM quant.agent_decisions WHERE decision_id = %s
        """, (decision_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            'decision_id': row[0],
            'decision_type': row[1],
            'parameters': json.loads(row[2]) if isinstance(row[2], str) else row[2],
            'evaluation_status': row[3],
            'score': row[4],
            'score_band': row[5],
            'confidence_score': row[6],
        }
    finally:
        cursor.close()


def cleanup_test_klines(conn, symbol: str = "600519.SH"):
    """清理测试 K 线数据"""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM quant.daily_klines WHERE symbol = %s",
            (symbol,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cursor.close()


def ensure_test_stock(conn, symbol: str):
    """确保 stocks 表中存在该股票（满足 daily_klines FK 约束）

    stocks 使用带交易所后缀的格式（如 600519.SH），market 字段必须为 'A' 或 'HK'。
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO quant.stocks (symbol, name, market)
            VALUES (%s, %s, %s)
            ON CONFLICT (symbol) DO NOTHING
        """, (symbol, f"TEST_{symbol}", "A"))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cursor.close()


def insert_test_klines(
    conn,
    symbol: str,
    start_date: date,
    end_date: date,
    base_price: float = 1650.00,
    price_change: float = 0.15
):
    """插入测试 K 线数据（自动确保 stocks 表有对应记录）"""
    ensure_test_stock(conn, symbol)
    cursor = conn.cursor()
    try:
        current_date = start_date
        price = base_price
        while current_date <= end_date:
            if current_date.weekday() < 5:  # 跳过周末
                change = price_change / 20  # 均匀分布到 20 个交易日
                price = price * (1 + change)

                cursor.execute("""
                    INSERT INTO quant.daily_klines
                    (symbol, trade_date, open, high, low, close, volume, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, trade_date) DO UPDATE
                    SET close = EXCLUDED.close, volume = EXCLUDED.volume
                """, (
                    symbol,
                    current_date,
                    price * 0.99,
                    price * 1.02,
                    price * 0.98,
                    price,
                    1000000,
                    price * 1000000
                ))
            current_date += timedelta(days=1)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()


# ═══════════════════════════════════════════════════════════════
# 模拟对象（用于 DecisionScoreService 等依赖注入测试）
# ═══════════════════════════════════════════════════════════════

class MockKlineRepository:
    """模拟 K 线仓库，满足 IKlineRepository.get_daily_klines 签名"""

    def __init__(self, klines_data: Dict[str, Any]):
        self.klines_data = klines_data

    def get_daily_klines(self, symbol: str, start_date: str, end_date: str):
        import polars as pl
        if symbol in self.klines_data:
            return pl.DataFrame(self.klines_data[symbol])
        return pl.DataFrame()


class MockDecisionRepository:
    """模拟决策仓库，满足 IAgentIntelligenceRepository 接口"""

    def __init__(self, decisions: list = None):
        self.decisions = decisions or []
        self.scored_decisions = []

    def list_pending_evaluations(self, days: int = 1):
        return self.decisions

    def update_score(self, decision_id: str, score: float, band: str, detail: dict):
        self.scored_decisions.append({
            'decision_id': decision_id,
            'score': score,
            'band': band,
            'detail': detail
        })
        return decision_id
