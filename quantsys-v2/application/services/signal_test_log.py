"""
信号测试表 & 回扫验证工具

用途:
1. 将策略产生的信号写入 quant.signal_test_log 表
2. 定时回扫已记录信号，对比信号价格 vs 当前价格，计算"如果执行了会怎样"
3. 按策略/交易日/标的维度统计胜率和盈亏

流程:
  T日收盘 → 策略生产信号 → 写入 signal_test_log (status='pending')
  T+N日   → 回扫任务抓取最新价格 → 计算模拟盈亏 → 更新 status='verified'

表结构:
  CREATE TABLE IF NOT EXISTS quant.signal_test_log (
      id              SERIAL PRIMARY KEY,
      symbol          VARCHAR(20)    NOT NULL,
      name            VARCHAR(100),
      strategy_name   VARCHAR(100)   NOT NULL,
      signal_date     DATE           NOT NULL,   -- 信号产生日期
      action          VARCHAR(10)    NOT NULL,   -- buy / sell
      confidence      FLOAT,
      signal_price    FLOAT,                      -- 信号产生时的收盘价
      entry_price     FLOAT,                      -- 建议入场价
      stop_loss       FLOAT,                      -- 止损价
      reason          TEXT,
      details         JSONB,
      -- 验证字段 --
      status          VARCHAR(20)    DEFAULT 'pending',  -- pending / verified / expired
      verify_date     DATE,                          -- 验证日期
      current_price   FLOAT,                         -- 当前价
      pnl_pct         FLOAT,                         -- 涨跌幅 %
      hit_stop_loss   BOOLEAN       DEFAULT FALSE,   -- 是否触及止损
      hit_target_1    BOOLEAN       DEFAULT FALSE,   -- 是否触及+10%
      hit_target_2    BOOLEAN       DEFAULT FALSE,   -- 是否触及+20%
      hit_target_3    BOOLEAN       DEFAULT FALSE,   -- 是否触及+30%
      max_pnl_pct     FLOAT,                         -- 期间最大涨幅
      max_loss_pct    FLOAT,                         -- 期间最大跌幅
      holding_days    INT,                           -- 持仓天数
      created_at      TIMESTAMPTZ   DEFAULT NOW(),
      updated_at      TIMESTAMPTZ   DEFAULT NOW()
  );

Author: QuantSys V2
Date: 2026-05-25
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
import json
import structlog

import psycopg2
from psycopg2.extras import RealDictCursor

from infrastructure.persistence.database.base_repository import _resolve_db_dsn

logger = structlog.get_logger(__name__)


class SignalTestLog:
    """信号测试日志管理器"""

    TABLE_NAME = 'quant.signal_test_log'

    def __init__(self):
        self._ensure_table()

    @staticmethod
    def _get_conn():
        """获取数据库连接"""
        dsn = _resolve_db_dsn()
        if not dsn:
            raise RuntimeError("No database DSN configured (set PGDATABASE or DATABASE_URL)")
        return psycopg2.connect(dsn)

    # ═══════════════════════════════════════════════════════
    # 表管理
    # ═══════════════════════════════════════════════════════

    def _ensure_table(self):
        """确保测试表存在"""
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
            id              SERIAL PRIMARY KEY,
            symbol          VARCHAR(20)    NOT NULL,
            name            VARCHAR(100),
            strategy_name   VARCHAR(100)   NOT NULL,
            signal_date     DATE           NOT NULL,
            action          VARCHAR(10)    NOT NULL,
            confidence      DOUBLE PRECISION,
            signal_price    DOUBLE PRECISION,
            entry_price     DOUBLE PRECISION,
            stop_loss       DOUBLE PRECISION,
            reason          TEXT,
            details         JSONB,
            status          VARCHAR(20)    DEFAULT 'pending',
            verify_date     DATE,
            current_price   DOUBLE PRECISION,
            pnl_pct         DOUBLE PRECISION,
            hit_stop_loss   BOOLEAN        DEFAULT FALSE,
            hit_target_1    BOOLEAN        DEFAULT FALSE,
            hit_target_2    BOOLEAN        DEFAULT FALSE,
            hit_target_3    BOOLEAN        DEFAULT FALSE,
            max_pnl_pct     DOUBLE PRECISION,
            max_loss_pct    DOUBLE PRECISION,
            holding_days    INT,
            created_at      TIMESTAMPTZ    DEFAULT NOW(),
            updated_at      TIMESTAMPTZ    DEFAULT NOW()
        );
        """
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(ddl)
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            conn.close()

    # ═══════════════════════════════════════════════════════
    # 写入
    # ═══════════════════════════════════════════════════════

    def record_signal(self, signal: Dict[str, Any]) -> int:
        """
        记录一条信号到测试表。

        Args:
            signal: StrategyRunner 返回的信号字典 + 额外字段:
                {
                    'symbol': str,
                    'name': str (optional),
                    'strategy_name': str,
                    'signal_date': str or date,
                    'action': 'buy'|'sell'|'hold',
                    'confidence': float,
                    'signal_price': float,       # 收盘价
                    'entry_price': float | None,
                    'stop_loss': float | None,
                    'reason': str,
                    'details': dict (optional),
                }

        Returns:
            插入的记录ID
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        sql = f"""
        INSERT INTO {self.TABLE_NAME}
            (symbol, name, strategy_name, signal_date, action,
             confidence, signal_price, entry_price, stop_loss,
             reason, details)
        VALUES
            (%s, %s, %s, %s, %s,
             %s, %s, %s, %s,
             %s, %s)
        RETURNING id
        """

        cursor.execute(sql, (
            signal['symbol'],
            signal.get('name', ''),
            signal['strategy_name'],
            self._to_date(signal.get('signal_date', datetime.now().date())),
            signal['action'],
            signal.get('confidence', 0.0),
            signal.get('signal_price'),
            signal.get('entry_price'),
            signal.get('stop_loss'),
            signal.get('reason', ''),
            json.dumps(signal.get('details', {})),
        ))

        record_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        logger.info(
            "Signal recorded: id=%s symbol=%s strategy=%s action=%s",
            record_id, signal['symbol'], signal['strategy_name'], signal['action']
        )
        return record_id

    def record_batch(self, signals: List[Dict[str, Any]]) -> int:
        """批量记录信号，返回记录数"""
        count = 0
        for sig in signals:
            if sig.get('action') in ('buy', 'sell') and sig.get('confidence', 0) > 0.5:
                self.record_signal(sig)
                count += 1
        return count

    # ═══════════════════════════════════════════════════════
    # 回扫验证
    # ═══════════════════════════════════════════════════════

    def verify_pending(self, days_after: int = 5) -> Dict[str, Any]:
        """
        回扫所有 pending 状态的信号，用最新价格计算模拟盈亏。

        此方法需要能获取到标的的当前价格。
        在实际部署中，可以从K线数据或实时报价获取。

        Args:
            days_after: 信号产生后多少天验证

        Returns:
            {
                'total_pending': int,
                'verified': int,
                'win_rate': float,
                'avg_pnl': float,
                'by_strategy': {strategy_name: {win_rate, avg_pnl}},
            }
        """
        conn = self._get_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # 获取待验证信号
        cutoff_date = date.today() - timedelta(days=days_after)
        cursor.execute(f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE status = 'pending'
              AND signal_date <= %s
              AND action = 'buy'
            ORDER BY signal_date DESC
        """, (cutoff_date,))

        pending = cursor.fetchall()
        verified_count = 0
        results = []

        for record in pending:
            # 获取当前价格（这里用占位逻辑，实际需对接行情API）
            current_price = self._get_current_price(record['symbol'])

            if current_price is None:
                logger.warning(
                    "Cannot get current price for %s, skip signal #%s",
                    record['symbol'], record['id']
                )
                continue

            entry = record['entry_price'] or record['signal_price']
            if not entry:
                continue

            pnl_pct = (current_price - entry) / entry * 100
            days_held = (date.today() - record['signal_date']).days
            hit_stop = False

            if record['stop_loss'] and entry:
                hit_stop = current_price <= record['stop_loss']

            # 更新记录
            cursor.execute(f"""
                UPDATE {self.TABLE_NAME}
                SET status = 'verified',
                    verify_date = %s,
                    current_price = %s,
                    pnl_pct = %s,
                    hit_stop_loss = %s,
                    holding_days = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (
                date.today(),
                current_price,
                round(pnl_pct, 4),
                hit_stop,
                days_held,
                record['id'],
            ))

            results.append({
                'symbol': record['symbol'],
                'strategy_name': record['strategy_name'],
                'pnl_pct': round(pnl_pct, 4),
                'win': pnl_pct > 0,
                'hit_stop_loss': hit_stop,
                'holding_days': days_held,
            })
            verified_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        # ── 汇总统计 ──
        wins = [r for r in results if r['win']]
        win_rate = len(wins) / len(results) if results else 0.0
        avg_pnl = sum(r['pnl_pct'] for r in results) / len(results) if results else 0.0

        # 按策略统计
        by_strategy = {}
        for r in results:
            s = r['strategy_name']
            if s not in by_strategy:
                by_strategy[s] = {'wins': 0, 'total': 0, 'pnls': []}
            by_strategy[s]['total'] += 1
            if r['win']:
                by_strategy[s]['wins'] += 1
            by_strategy[s]['pnls'].append(r['pnl_pct'])

        for s_name, s_data in by_strategy.items():
            s_data['win_rate'] = round(s_data['wins'] / s_data['total'], 4) if s_data['total'] else 0
            s_data['avg_pnl'] = round(sum(s_data['pnls']) / len(s_data['pnls']), 4)
            del s_data['wins']
            del s_data['pnls']

        return {
            'total_pending': len(pending),
            'verified': verified_count,
            'win_rate': round(win_rate, 4),
            'avg_pnl_pct': round(avg_pnl, 4),
            'by_strategy': by_strategy,
        }

    def get_records(
        self,
        page: int = 1,
        page_size: int = 20,
        strategy_name: str = None,
        action: str = None,
        symbol: str = None,
        status: str = None,
    ) -> Dict[str, Any]:
        """
        获取信号记录列表（分页）。

        Returns:
            {
                'records': [...],
                'pagination': { 'page': 1, 'page_size': 20, 'total': int }
            }
        """
        conn = self._get_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        conditions = []
        params = []

        if strategy_name:
            conditions.append("strategy_name = %s")
            params.append(strategy_name)
        if action:
            conditions.append("action = %s")
            params.append(action)
        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)
        if status:
            conditions.append("status = %s")
            params.append(status)

        where = ' AND '.join(conditions) if conditions else '1=1'
        offset = (page - 1) * page_size

        # 总数
        cursor.execute(f"""
            SELECT COUNT(*) as cnt FROM {self.TABLE_NAME} WHERE {where}
        """, params)
        total = cursor.fetchone()['cnt']

        # 分页查询
        cursor.execute(f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, params + [page_size, offset])

        records = []
        for row in cursor.fetchall():
            r = dict(row)
            # 日期转为字符串
            for f in ('signal_date', 'verify_date', 'created_at', 'updated_at'):
                if r.get(f):
                    r[f] = str(r[f])
            if r.get('details') and isinstance(r['details'], str):
                try:
                    import json
                    r['details'] = json.loads(r['details'])
                except Exception:
                    pass
            records.append(r)

        cursor.close()
        conn.close()

        return {
            'records': records,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
            }
        }

    def get_stats(
        self,
        strategy_name: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """
        获取信号测试统计。

        Returns:
            {
                'total_signals': int,
                'verified': int,
                'win_rate': float,
                'avg_pnl_pct': float,
                'max_pnl_pct': float,
                'max_loss_pct': float,
                'avg_holding_days': float,
                'hit_stop_loss_rate': float,
                'monthly_breakdown': [...],
            }
        """
        conn = self._get_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        conditions = ["status = 'verified'"]
        params = []

        if strategy_name:
            conditions.append("strategy_name = %s")
            params.append(strategy_name)
        if start_date:
            conditions.append("signal_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("signal_date <= %s")
            params.append(end_date)

        where = ' AND '.join(conditions)

        cursor.execute(f"""
            SELECT
                COUNT(*) as total,
                AVG(pnl_pct) as avg_pnl,
                MAX(pnl_pct) as max_pnl,
                MIN(pnl_pct) as max_loss,
                AVG(holding_days) as avg_days,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate,
                SUM(CASE WHEN hit_stop_loss THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as stop_loss_rate
            FROM {self.TABLE_NAME}
            WHERE {where}
        """, params)

        overall = cursor.fetchone()

        # 月度分布
        cursor.execute(f"""
            SELECT
                TO_CHAR(signal_date, 'YYYY-MM') as month,
                COUNT(*) as count,
                AVG(pnl_pct) as avg_pnl,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate
            FROM {self.TABLE_NAME}
            WHERE {where}
            GROUP BY 1
            ORDER BY 1 DESC
            LIMIT 12
        """, params)

        monthly = [dict(r) for r in cursor.fetchall()]

        # ── 按策略统计 ──
        cursor.execute(f"""
            SELECT
                strategy_name,
                COUNT(*) as total,
                AVG(pnl_pct) as avg_pnl,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate
            FROM {self.TABLE_NAME}
            WHERE {where}
            GROUP BY strategy_name
            ORDER BY strategy_name
        """, params)
        by_strategy = [dict(r) for r in cursor.fetchall()]

        cursor.close()
        conn.close()

        return {
            'total_signals': overall['total'] or 0,
            'win_rate': round(overall['win_rate'] or 0, 4),
            'avg_pnl_pct': round(overall['avg_pnl'] or 0, 4),
            'max_pnl_pct': round(overall['max_pnl'] or 0, 4),
            'max_loss_pct': round(overall['max_loss'] or 0, 4),
            'avg_holding_days': round(overall['avg_days'] or 0, 1),
            'hit_stop_loss_rate': round(overall['stop_loss_rate'] or 0, 4),
            'monthly_breakdown': monthly,
            'by_strategy': by_strategy,
        }

    # ═══════════════════════════════════════════════════════
    # 辅助
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _to_date(val) -> date:
        if isinstance(val, str):
            return datetime.strptime(val[:10], '%Y-%m-%d').date()
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        return date.today()

    @staticmethod
    def _get_current_price(symbol: str) -> Optional[float]:
        """
        获取标的当前价格。
        实际部署时对接 quant_cli stock.quote 或 data_fetch_stock。
        """
        try:
            # 尝试从 quantlib 获取
            from domain.quantlib.data_sources.akshare_adapter import get_realtime_price
            return get_realtime_price(symbol)
        except Exception:
            logger.debug("Cannot get realtime price for %s via akshare", symbol)
        return None
