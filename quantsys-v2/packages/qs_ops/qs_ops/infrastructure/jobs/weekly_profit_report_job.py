#!/usr/bin/env python
"""每周盈利报告（2026-10-19 · 盈利链路修复收尾）

回答用户一个问题：「这周赚没赚钱、信号准不准、机会抓住还是错过」。

三段式：
  ① 各账户本周已实现盈亏（SELL 成交 realized_pnl 汇总）+ 净值周变动
    （simulation_equity_snapshot 周末最新 − 周前最后快照，缺数据如实 N/A）；
  ② 信号命中率（signal_tracking 本周完成 T+5/T+10 评估的行）；
  ③ 机会捕捉/错过（本周 BUY 信号标的 vs 本周实际 BUY 成交标的对照）。

推送：NotificationFacade.send_card（股票类内容 → 原群，分群规则 2026-10-14）。
调度：周日 20:30（避开 strategy_loop_weekly 20:15 撞点）。

诚实口径：
  - 没有任何账户有成交 → 明说"本周无成交"，不编造 0 收益的绿色假象；
  - 命中率样本不足 5 条 → 标注"样本不足，仅供参考"；
  - 净值快照缺失 → N/A，不按 0 记。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)

#: 命中率评估的最小样本量（低于此数只展示不评价）
MIN_HIT_SAMPLE = 5


def week_range(now: Optional[datetime] = None) -> Tuple[date, date]:
    """报告覆盖周：上周一 ~ 上周日（周日晚上跑，报的是刚结束的交易周）。"""
    now = now or datetime.now()
    this_monday = now.date() - timedelta(days=now.weekday())
    return this_monday - timedelta(days=7), this_monday - timedelta(days=1)


def gather_weekly_report(conn, week_start: date, week_end: date) -> Dict[str, Any]:
    """聚合三段数据。conn 为 SQLAlchemy connection（可注入，测试可换库/打桩）。"""
    return {
        'week': {'start': week_start.isoformat(), 'end': week_end.isoformat()},
        'accounts': _account_weekly(conn, week_start, week_end),
        'hit_rate': _signal_hit_rate(conn, week_start, week_end),
        'opportunities': _opportunities(conn, week_start, week_end),
    }


def _account_weekly(conn, ws: date, we: date) -> List[Dict[str, Any]]:
    sells = conn.execute(text("""
        SELECT account_name, count(*) AS sells,
               COALESCE(sum(realized_pnl), 0) AS realized_pnl
          FROM quant.simulation_trades
         WHERE action = 'SELL'
           AND trade_time >= :ws AND trade_time < :we_exclusive
         GROUP BY account_name
    """), {'ws': ws, 'we_exclusive': we + timedelta(days=1)}).fetchall()

    accounts = []
    active = conn.execute(text(
        "SELECT account_name, display_name, total_value, cumulative_return "
        "FROM quant.simulation_account WHERE status = 'active' ORDER BY 1")).fetchall()
    pnl_by_acct = {r[0]: r for r in sells}
    for name, display, total_value, cum_ret in active:
        s = pnl_by_acct.get(name)
        accounts.append({
            'account_name': name,
            'display_name': display or name,
            'sells': int(s[1]) if s else 0,
            'realized_pnl': float(s[2]) if s else 0.0,
            'week_return_pct': _week_return(conn, name, ws, we),
            'total_value': float(total_value or 0),
            'cumulative_return_pct': round(float(cum_ret or 0) * 100, 2),
        })
    return accounts


def _week_return(conn, account_name: str, ws: date, we: date) -> Optional[float]:
    """净值周变动 %：周末最新快照 vs 周前最后快照；缺任一侧返回 None（N/A）。"""
    end_row = conn.execute(text("""
        SELECT total_value FROM quant.simulation_equity_snapshot
         WHERE account_name = :a AND snapshot_date <= :we
         ORDER BY snapshot_date DESC LIMIT 1
    """), {'a': account_name, 'we': we}).fetchone()
    start_row = conn.execute(text("""
        SELECT total_value FROM quant.simulation_equity_snapshot
         WHERE account_name = :a AND snapshot_date < :ws
         ORDER BY snapshot_date DESC LIMIT 1
    """), {'a': account_name, 'ws': ws}).fetchone()
    if not end_row or not start_row or not float(start_row[0]):
        return None
    return round((float(end_row[0]) / float(start_row[0]) - 1) * 100, 2)


def _signal_hit_rate(conn, ws: date, we: date) -> Dict[str, Any]:
    """本周完成评估的信号命中率（hit_5d/10d 非空且本周更新过）。"""
    row = conn.execute(text("""
        SELECT count(*) AS evaluated,
               count(*) FILTER (WHERE hit_5d)  AS hit5,
               count(*) FILTER (WHERE hit_10d) AS hit10,
               count(*) FILTER (WHERE hit_5d IS NOT NULL)  AS eval5,
               count(*) FILTER (WHERE hit_10d IS NOT NULL) AS eval10
          FROM quant.signal_tracking
         WHERE updated_at >= :ws AND updated_at < :we_exclusive
    """), {'ws': ws, 'we_exclusive': we + timedelta(days=1)}).fetchone()
    evaluated, hit5, hit10, eval5, eval10 = (int(x or 0) for x in row)
    return {
        'evaluated': evaluated,
        'hit5_rate': round(hit5 / eval5 * 100, 1) if eval5 else None,
        'hit10_rate': round(hit10 / eval10 * 100, 1) if eval10 else None,
        'enough': evaluated >= MIN_HIT_SAMPLE,
    }


def _opportunities(conn, ws: date, we: date) -> Dict[str, Any]:
    """本周 BUY 信号 vs 实际买入成交对照（按标的去重）。"""
    signals = conn.execute(text("""
        SELECT DISTINCT s.symbol, max(s.name) AS name,
               min(s.price) AS price, count(*) AS cnt
          FROM quant.signals s
         WHERE s.signal_date >= :ws AND s.signal_date <= :we
           AND s.action = 'BUY'
         GROUP BY s.symbol
    """), {'ws': ws, 'we': we}).fetchall()
    traded = {r[0] for r in conn.execute(text("""
        SELECT DISTINCT symbol FROM quant.simulation_trades
         WHERE action = 'BUY' AND trade_time >= :ws AND trade_time < :we_exclusive
    """), {'ws': ws, 'we_exclusive': we + timedelta(days=1)}).fetchall()}

    captured, missed = [], []
    for sym, name, price, cnt in signals:
        item = {'symbol': sym, 'name': name,
                'price': float(price) if price is not None else None,
                'signal_count': int(cnt)}
        (captured if sym in traded else missed).append(item)
    return {'captured': captured, 'missed': missed,
            'signal_symbols': len(signals), 'traded_symbols': len(traded)}


def render_markdown(report: Dict[str, Any]) -> str:
    """三段式卡片正文（纯函数）。"""
    wk = report['week']
    lines = [f"**周期**：{wk['start']} ~ {wk['end']}", '']

    # ① 账户盈亏
    lines.append('**一、本周已实现盈亏**')
    active_with_trades = [a for a in report['accounts'] if a['sells'] > 0]
    if not report['accounts']:
        lines.append('- 无活跃模拟账户')
    else:
        for a in report['accounts']:
            wr = a['week_return_pct']
            wr_text = f"{wr:+.2f}%" if wr is not None else 'N/A（缺净值快照）'
            lines.append(
                f"- {a['display_name']}：卖出 {a['sells']} 笔，"
                f"已实现盈亏 **{a['realized_pnl']:+.0f} 元**，"
                f"周净值变动 {wr_text}，累计 {a['cumulative_return_pct']:+.2f}%")
        if not active_with_trades:
            lines.append('- ⚠️ 本周所有账户零卖出——没有利润落袋，只有浮动')
    lines.append('')

    # ② 信号命中率
    h = report['hit_rate']
    lines.append('**二、信号命中率**')
    if h['evaluated'] == 0:
        lines.append('- 本周无完成 T+5/T+10 评估的信号（信号恢复于 10-19，下周起有数据）')
    else:
        r5 = f"{h['hit5_rate']}%" if h['hit5_rate'] is not None else 'N/A'
        r10 = f"{h['hit10_rate']}%" if h['hit10_rate'] is not None else 'N/A'
        suffix = '' if h['enough'] else f'（样本 {h["evaluated"]} 条 < {MIN_HIT_SAMPLE}，仅供参考）'
        lines.append(f"- 本周评估 {h['evaluated']} 条：T+5 命中 {r5}，T+10 命中 {r10}{suffix}")
    lines.append('')

    # ③ 机会捕捉/错过
    o = report['opportunities']
    lines.append('**三、机会捕捉与错过**')
    if o['signal_symbols'] == 0:
        lines.append('- 本周无 BUY 信号')
    else:
        lines.append(f"- BUY 信号覆盖 {o['signal_symbols']} 只标的，"
                     f"实际买入 {len(o['captured'])} 只，错过 {len(o['missed'])} 只")
        for it in o['captured'][:5]:
            lines.append(f"  - ✅ {it['name']}（{it['symbol']}）信号价 ¥{it['price']}")
        for it in o['missed'][:5]:
            lines.append(f"  - ❌ 错过 {it['name']}（{it['symbol']}）信号价 ¥{it['price']}")
        if len(o['missed']) > 5:
            lines.append(f"  - … 另有 {len(o['missed']) - 5} 只错过（signals 表可溯）")
    return '\n'.join(lines)


class WeeklyProfitReportJob:
    """每周盈利报告作业（生产路径：execute → gather → render → send_card）。"""

    def __init__(self, facade=None):
        if facade is None:
            from qs_notification.application.notification_factory import (
                get_notification_facade,
            )
            facade = get_notification_facade()
        self.facade = facade

    def execute(self, dry_run: bool = False, now: Optional[datetime] = None) -> Dict[str, Any]:
        from infrastructure.persistence.database.engine import get_engine

        ws, we = week_range(now)
        engine = get_engine()
        with engine.connect() as conn:
            report = gather_weekly_report(conn, ws, we)
        content = render_markdown(report)
        title = f"📊 每周盈利报告 {report['week']['start']}~{report['week']['end']}"

        send_ok = False
        if not dry_run:
            try:
                send_ok = bool(self.facade.send_card(title, content))
            except Exception as e:  # noqa: BLE001
                logger.error('每周盈利报告发送失败: %s', e)
        logger.info('每周盈利报告生成完成', week=report['week'], dry_run=dry_run,
                    send_ok=send_ok)
        return {'status': 'completed' if (dry_run or send_ok) else 'failed',
                'action': 'weekly_profit_report',
                'week': report['week'], 'send_ok': send_ok,
                'accounts': len(report['accounts']),
                'signals': report['opportunities']['signal_symbols'],
                'content_preview': content[:500]}


def execute(task_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """调度入口（qs_ops Job / scheduler_tasks handler 共用）。"""
    params = task_context or {}
    return WeeklyProfitReportJob().execute(
        dry_run=bool(params.get('dry_run', False)))
