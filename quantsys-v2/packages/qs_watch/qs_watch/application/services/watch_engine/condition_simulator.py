"""条件历史回测器（2026-10-20 框架适配 P0）：建规则前先看「过去 N 天会触发几次」

动机：#248 买入区规则上线即 61 次/日——建规则前没有任何「这条条件历史表现如何」的
验证手段。本模拟器把条件 DSL 在日线历史上逐日重放：每日收盘视为「现价」，按当时
可见的数据构造 EvalContext（前 i 日收盘算 MA/RSI、前 20 日均量算量比），答案就是
「这条规则过去会怎么响」。

口径与限制（诚实标注）：
  · 日频重放：price_break/pct_change/pnl_pct/ma_break/rsi/volume_surge/combined 可用；
  · velocity 依赖盘中价格历史——日频重放下恒 degraded（永不触发，不算漏报）；
  · staged_break 是有状态状态机（触及→观察→确认），点态重放不适用——跳过并标注；
  · fund_flow 依赖资金流向数据源（无历史序列）——跳过并标注；
  · 闩锁/冷却/去重/日上限不参与重放——答案是「裸条件的触发密度」，
    真实线上会比这更安静（迟滞带+冷却压着）。
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

from qs_watch.application.services.watch_engine.conditions import (
    EvalContext, evaluate, validate_condition,
)

logger = structlog.get_logger(__name__)

DEFAULT_DAYS = 30

#: 日频重放不适用的条件类型（跳过并在 notes 说明）
_SKIP_TYPES = {'staged_break': '两段式伏击是有状态状态机，点态日频重放不适用',
               'fund_flow': '资金流向无历史序列可重放'}


@dataclass
class _Bar:
    date: str
    close: float
    volume: float
    prev_close: Optional[float]


def _collect_types(conds: List[dict]) -> set:
    out = set()
    for c in conds or []:
        out.add((c or {}).get('type'))
        if (c or {}).get('type') == 'combined':
            out |= _collect_types(((c.get('params') or {}).get('conditions')) or [])
    return {t for t in out if t}


def simulate_conditions(symbol: str, conditions: List[dict], *,
                        days: int = DEFAULT_DAYS,
                        cost_price: Optional[float] = None,
                        klines_provider: Callable[..., Optional[list]] = None,
                        now: Optional[datetime] = None) -> Dict[str, Any]:
    """把 conditions 在最近 days 天的日线上逐日重放。

    klines_provider(symbol, start, end) -> [{date, close, volume}]（升序）或 None。
    返回 {window, days_evaluated, per_condition, notes}。
    """
    now = now or datetime.now()
    days = max(5, min(int(days or DEFAULT_DAYS), 250))
    notes: List[str] = []

    for c in conditions or []:
        validate_condition(c)   # 非法条件响亮拒绝（400 语义由路由转）

    skipped = _collect_types(conditions) & set(_SKIP_TYPES)
    for t in sorted(skipped):
        notes.append('跳过 %s：%s' % (t, _SKIP_TYPES[t]))

    if klines_provider is None:
        from qs_market_data.adapters.outbound.datasources.manager import (
            get_data_provider_manager,
        )

        def klines_provider(sym, start, end):  # noqa: F811
            r = get_data_provider_manager().get_klines(sym, 'daily', start, end)
            if not r.get('success') or not r.get('data'):
                return None
            out = []
            for k in r['data']:
                if isinstance(k, dict):
                    d, c, v = k.get('date'), k.get('close'), k.get('volume')
                else:
                    d, c, v = (getattr(k, 'date', None), getattr(k, 'close', None),
                               getattr(k, 'volume', None))
                if d and c is not None:
                    out.append({'date': str(d)[:10], 'close': float(c),
                                'volume': float(v) if v is not None else 0.0})
            return out

    start = (now - timedelta(days=int(days * 1.9))).strftime('%Y-%m-%d')
    end = now.strftime('%Y-%m-%d')
    bare = str(symbol).split('.')[0]
    rows = klines_provider(bare, start, end)
    if not rows:
        raise RuntimeError('K 线数据不可用（%s %s~%s），无法回测' % (bare, start, end))

    # 只回放大窗口的尾部 days 个交易日（头部留作指标预热：MA/RSI 需要历史根数）
    bars: List[_Bar] = []
    for i, r in enumerate(rows):
        prev = rows[i - 1]['close'] if i > 0 else None
        bars.append(_Bar(date=r['date'], close=float(r['close']),
                         volume=float(r['volume'] or 0), prev_close=prev))
    eval_bars = bars[-days:] if len(bars) > days else bars
    if len(bars) < 30:
        notes.append('K 线仅 %d 根（<30），MA20/RSI14 等指标前期会降级' % len(bars))

    per_condition: List[Dict[str, Any]] = [
        {'idx': idx, 'type': (c or {}).get('type'), 'triggers': []}
        for idx, c in enumerate(conditions or [])
    ]

    offset = len(bars) - len(eval_bars)
    for i, bar in enumerate(eval_bars):
        # 当日可见上下文：截至当日的收盘序列 + 前 20 日均量（不含当日，与线上同口径）
        hist_closes = [b.close for b in bars[:offset + i + 1]]
        prior_vols = [b.volume for b in bars[max(0, offset + i - 20):offset + i]]
        avg_vol = (sum(prior_vols) / len(prior_vols)) if len(prior_vols) >= 10 else None

        change_pct = None
        if bar.prev_close:
            change_pct = round((bar.close - bar.prev_close) / bar.prev_close * 100, 2)
        quote = SimpleNamespace(symbol=bare, price=bar.close, prev_close=bar.prev_close,
                                volume=bar.volume or None, change_pct=change_pct,
                                name=None)
        ctx = EvalContext(
            cost_price=float(cost_price) if cost_price else None,
            daily_closes=tuple(hist_closes),
            avg_volume_20d=avg_vol,
            elapsed_fraction=1.0,   # 日频重放按全日口径折算量比
        )
        for idx, cond in enumerate(conditions or []):
            if (cond or {}).get('type') in _SKIP_TYPES:
                continue
            try:
                result = evaluate(cond, quote, ctx, now=datetime.strptime(bar.date, '%Y-%m-%d'))
            except Exception as e:  # noqa: BLE001 - 单日评估失败不炸整轮回放
                logger.debug('回测单日评估失败', date=bar.date, idx=idx, error=str(e))
                continue
            if result.triggered:
                per_condition[idx]['triggers'].append({
                    'date': bar.date, 'price': bar.close, 'message': result.message})

    for pc in per_condition:
        trs = pc['triggers']
        pc['trigger_count'] = len(trs)
        pc['verdict'] = ('⚠️ 触发过密（>%d 天1次），建规则前建议加冷却/改两段式' % (days // 10)
                         if len(trs) > max(3, days // 10) else
                         '密度可接受' if trs else '窗口内未触发（检查阈值是否过严）')
        if len(trs) > 20:
            pc['triggers_sample'] = trs[:20]
            del pc['triggers']      # 太多只给样本，防响应体膨胀

    return {'symbol': bare,
            'window': {'from': eval_bars[0].date, 'to': eval_bars[-1].date,
                       'days': len(eval_bars)},
            'per_condition': per_condition, 'notes': notes}
