#!/usr/bin/env python3
"""
持仓风险检查脚本

功能：
1. 读取当前持仓
2. 检查持仓风险（集中度、止损价位）
3. 生成风险预警报告
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict
import sqlite3

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database
from quantsys.risk import StopLossManager, PositionManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class RiskChecker:
    """风险检查器"""

    def __init__(self, quant_db: Database, main_db_path: str):
        self.quant_db = quant_db
        self.main_db_path = main_db_path
        self.stop_loss_mgr = StopLossManager()
        self.position_mgr = PositionManager()

    def get_holdings(self) -> List[Dict]:
        """从主项目数据库读取持仓"""
        if not os.path.exists(self.main_db_path):
            logger.warning(f"⚠️  主项目数据库不存在: {self.main_db_path}")
            return []

        try:
            conn = sqlite3.connect(self.main_db_path)
            cursor = conn.execute("""
                SELECT symbol, shares, cost_basis, market_value, unrealized_pnl
                FROM holdings
                WHERE shares > 0
            """)

            holdings = []
            for row in cursor.fetchall():
                holdings.append({
                    'symbol': row[0],
                    'shares': row[1],
                    'cost_basis': row[2],
                    'market_value': row[3],
                    'unrealized_pnl': row[4]
                })

            conn.close()
            return holdings

        except Exception as e:
            logger.error(f"❌ 读取持仓失败: {e}")
            return []

    def get_current_price(self, symbol: str) -> float:
        """获取最新价格"""
        conn = self.quant_db._get_connection()
        cursor = conn.execute("""
            SELECT close
            FROM daily_klines
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT 1
        """, (symbol,))

        row = cursor.fetchone()
        return row[0] if row else None

    def get_price_history(self, symbol: str, days: int = 30) -> List[Dict]:
        """获取历史价格"""
        conn = self.quant_db._get_connection()
        cursor = conn.execute("""
            SELECT date, high, low, close
            FROM daily_klines
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT ?
        """, (symbol, days))

        history = []
        for row in cursor.fetchall():
            history.append({
                'date': row[0],
                'high': row[1],
                'low': row[2],
                'close': row[3]
            })

        return history

    def check_stop_loss(self, holding: Dict) -> Dict:
        """检查止损"""
        symbol = holding['symbol']
        entry_price = holding['cost_basis']
        current_price = self.get_current_price(symbol)

        if current_price is None:
            return {
                'symbol': symbol,
                'status': 'ERROR',
                'message': '无法获取当前价格'
            }

        # 获取历史最高价
        history = self.get_price_history(symbol, days=30)
        if not history:
            highest_price = current_price
        else:
            highest_price = max([h['high'] for h in history])

        # 计算盈亏比例
        pnl_pct = (current_price - entry_price) / entry_price

        # 检查止损条件
        should_stop, reason = self.stop_loss_mgr.should_stop_loss(
            symbol=symbol,
            entry_price=entry_price,
            current_price=current_price,
            highest_price=highest_price,
            entry_date=history[-1]['date'] if history else None,
            current_date=history[0]['date'] if history else None
        )

        # 计算止损价位
        stop_loss_price = entry_price * 0.92  # 固定止损 -8%
        trailing_stop_price = highest_price * 0.90  # 移动止损 -10%

        return {
            'symbol': symbol,
            'entry_price': entry_price,
            'current_price': current_price,
            'highest_price': highest_price,
            'pnl_pct': pnl_pct,
            'should_stop': should_stop,
            'stop_reason': reason,
            'stop_loss_price': stop_loss_price,
            'trailing_stop_price': trailing_stop_price,
            'status': 'ALERT' if should_stop else 'OK'
        }

    def check_concentration(self, holdings: List[Dict]) -> Dict:
        """检查持仓集中度"""
        if not holdings:
            return {'status': 'OK', 'message': '无持仓'}

        total_value = sum(h['market_value'] for h in holdings)

        # 计算单只股票占比
        concentrations = []
        for h in holdings:
            pct = h['market_value'] / total_value
            concentrations.append({
                'symbol': h['symbol'],
                'value': h['market_value'],
                'percentage': pct
            })

        # 按占比排序
        concentrations.sort(key=lambda x: x['percentage'], reverse=True)

        # 检查是否过度集中
        alerts = []
        for c in concentrations:
            if c['percentage'] > 0.30:  # 单只股票超过30%
                alerts.append({
                    'symbol': c['symbol'],
                    'percentage': c['percentage'],
                    'level': 'HIGH',
                    'message': f"持仓占比过高 ({c['percentage']:.1%})"
                })
            elif c['percentage'] > 0.20:  # 单只股票超过20%
                alerts.append({
                    'symbol': c['symbol'],
                    'percentage': c['percentage'],
                    'level': 'MEDIUM',
                    'message': f"持仓占比较高 ({c['percentage']:.1%})"
                })

        return {
            'total_value': total_value,
            'holdings_count': len(holdings),
            'concentrations': concentrations,
            'alerts': alerts,
            'status': 'ALERT' if alerts else 'OK'
        }

    def check_portfolio_risk(self, holdings: List[Dict]) -> Dict:
        """检查组合风险"""
        if not holdings:
            return {'status': 'OK', 'message': '无持仓'}

        total_value = sum(h['market_value'] for h in holdings)
        total_pnl = sum(h['unrealized_pnl'] for h in holdings)
        total_pnl_pct = total_pnl / (total_value - total_pnl) if total_value > total_pnl else 0

        # 统计盈亏分布
        profit_count = len([h for h in holdings if h['unrealized_pnl'] > 0])
        loss_count = len([h for h in holdings if h['unrealized_pnl'] < 0])

        # 最大亏损持仓
        max_loss_holding = min(holdings, key=lambda x: x['unrealized_pnl'])
        max_loss_pct = max_loss_holding['unrealized_pnl'] / (
            max_loss_holding['market_value'] - max_loss_holding['unrealized_pnl']
        )

        return {
            'total_value': total_value,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'profit_count': profit_count,
            'loss_count': loss_count,
            'max_loss_symbol': max_loss_holding['symbol'],
            'max_loss_pct': max_loss_pct,
            'status': 'ALERT' if total_pnl_pct < -0.10 else 'OK'  # 总亏损超过10%预警
        }


def save_risk_report(report: Dict, output_path: str):
    """保存风险报告"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 风险报告已保存到: {output_path}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("持仓风险检查任务开始")
    logger.info(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 数据库路径
    quant_db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest', 'stock-db', 'stocks.db'
    )

    main_db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        '.pi-invest', 'portfolio.db'
    )

    quant_db = Database(quant_db_path)
    checker = RiskChecker(quant_db, main_db_path)

    # 读取持仓
    holdings = checker.get_holdings()
    logger.info(f"当前持仓: {len(holdings)} 只股票")

    if not holdings:
        logger.info("⚠️  无持仓，跳过风险检查")
        return

    logger.info("")

    # 1. 检查止损
    logger.info("1️⃣  检查止损条件...")
    stop_loss_results = []
    for holding in holdings:
        result = checker.check_stop_loss(holding)
        stop_loss_results.append(result)

        if result['status'] == 'ALERT':
            logger.warning(f"  ⚠️  {result['symbol']}: {result['stop_reason']}")
        else:
            logger.info(f"  ✅ {result['symbol']}: 正常 (盈亏: {result['pnl_pct']:.2%})")

    logger.info("")

    # 2. 检查集中度
    logger.info("2️⃣  检查持仓集中度...")
    concentration = checker.check_concentration(holdings)

    if concentration['alerts']:
        for alert in concentration['alerts']:
            logger.warning(f"  ⚠️  {alert['symbol']}: {alert['message']}")
    else:
        logger.info("  ✅ 持仓分散度良好")

    logger.info("")

    # 3. 检查组合风险
    logger.info("3️⃣  检查组合风险...")
    portfolio_risk = checker.check_portfolio_risk(holdings)

    logger.info(f"  总市值: ¥{portfolio_risk['total_value']:,.2f}")
    logger.info(f"  总盈亏: ¥{portfolio_risk['total_pnl']:,.2f} ({portfolio_risk['total_pnl_pct']:.2%})")
    logger.info(f"  盈利/亏损: {portfolio_risk['profit_count']}/{portfolio_risk['loss_count']}")

    if portfolio_risk['status'] == 'ALERT':
        logger.warning(f"  ⚠️  组合亏损较大: {portfolio_risk['total_pnl_pct']:.2%}")

    logger.info("")
    logger.info("=" * 60)
    logger.info("风险检查完成")
    logger.info("=" * 60)

    # 生成报告
    report = {
        'generated_at': datetime.now().isoformat(),
        'holdings_count': len(holdings),
        'stop_loss_checks': stop_loss_results,
        'concentration': concentration,
        'portfolio_risk': portfolio_risk,
        'alerts': {
            'stop_loss': [r for r in stop_loss_results if r['status'] == 'ALERT'],
            'concentration': concentration['alerts'],
            'portfolio': portfolio_risk['status'] == 'ALERT'
        }
    }

    # 保存报告
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest'
    )
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, 'risk_report.json')
    save_risk_report(report, output_path)

    # 统计预警
    total_alerts = (
        len(report['alerts']['stop_loss']) +
        len(report['alerts']['concentration']) +
        (1 if report['alerts']['portfolio'] else 0)
    )

    if total_alerts > 0:
        logger.warning(f"\n⚠️  共发现 {total_alerts} 个风险预警")
    else:
        logger.info("\n✅ 未发现风险预警")


if __name__ == '__main__':
    main()
