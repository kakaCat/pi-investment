"""热力图聚合服务 — agent 判断 × 市场实际走势的可视化校验数据源（纯本地 DB，无外部行情调用）"""
from datetime import date, datetime, time, timedelta
from typing import Optional

import structlog

VALID_WINDOWS = (1, 5, 20)
LOOKBACK_DAYS = 30  # spec §4.3：信号/池事件回看窗口（日历日）


class HeatmapService:
    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self._repo = None

    @property
    def repo(self):
        """延迟初始化避免循环 import（与 MarketDataService 同模式）"""
        if self._repo is None:
            from adapters.outbound.repositories.heatmap_repository import HeatmapRepository
            self._repo = HeatmapRepository()
        return self._repo

    def get_heatmap(self, date: Optional[str] = None, window: int = 5) -> dict:
        try:
            if window not in VALID_WINDOWS:
                return {'success': False, 'error': f'window 必须是 {VALID_WINDOWS} 之一'}
            anchor = self._resolve_anchor(date, window)
            if anchor is None:
                return {'success': True, 'data': self._empty_data(date, window)}

            dates = self.repo.get_trade_dates_from(anchor, window + 1)
            d0 = dates[0]
            dn = dates[min(window, len(dates) - 1)]
            partial = len(dates) < window + 1

            lookback_start = d0 - timedelta(days=LOOKBACK_DAYS)
            signals = self.repo.get_signals_between(lookback_start, d0)
            pool_events = self.repo.get_pool_events_between(
                datetime.combine(lookback_start, time.min),
                datetime.combine(d0, time.max),
            )
            pool_names = self.repo.get_pool_names()
            holdings = self.repo.get_current_holding_symbols()
            members_at_d, scope_degraded = self._replay_pool_members(d0)

            in_scope = {s['symbol'] for s in signals} | holdings | members_at_d

            scope_meta = self.repo.get_stocks_meta(sorted(in_scope))
            industries = sorted({m['industry'] for m in scope_meta.values() if m['industry']})
            if not industries:
                return {'success': True, 'data': self._empty_data(d0.isoformat(), window, scope_degraded)}
            universe_meta = self.repo.get_stocks_meta_by_industries(industries)
            closes = self.repo.get_range_closes(sorted(universe_meta), d0, dn)

            signals_by_symbol = self._group_signals(signals)
            events_by_symbol = self._group_pool_events(pool_events, pool_names)

            data = self._build_data(
                d0=d0, dn=dn, window=window, partial=partial,
                scope_degraded=scope_degraded,
                universe_meta=universe_meta, in_scope=in_scope,
                closes=closes,
                signals_by_symbol=signals_by_symbol,
                events_by_symbol=events_by_symbol,
                pool_events=pool_events,
                signals=signals,
            )
            return {'success': True, 'data': data}
        except Exception as e:
            self.logger.error("heatmap_aggregation_failed", error=str(e))
            return {'success': False, 'error': f'热力图聚合失败: {e}'}

    # ---- 内部方法 ----

    def _resolve_anchor(self, date_arg: Optional[str], window: int) -> Optional[date]:
        if date_arg:
            return self.repo.get_last_trade_date_on_or_before(date.fromisoformat(date_arg))
        # 默认：锚到"最近一个已走完的验证窗"起点（最新交易日前推 window 个交易日）。
        # 否则首屏必然 partial 且 d0==dn，全量股票被剔除、页面空图（2026-08-02 bug）
        dates = self.repo.get_trade_dates_up_to(date.today(), window + 1)
        return dates[0] if dates else None

    def _replay_pool_members(self, d0: date) -> tuple[set[str], bool]:
        """回放 d0 时点池成员：从当前成员倒序撤销 d0 之后的事件（add→剔除，remove→加回）。
        spec §4.3：d0 之前无任何池日志 → 池历史不可知 → 返回空集合并标记 degraded
        （in_scope 退化为「信号+持仓」口径）。"""
        cutoff = datetime.combine(d0, time.max)
        if not self.repo.has_pool_log_before(cutoff):
            return set(), True
        members = self.repo.get_pool_members_now()
        for evt in self.repo.get_pool_events_after(cutoff):
            if evt['action'] == 'add':
                members.discard(evt['symbol'])
            elif evt['action'] == 'remove':
                members.add(evt['symbol'])
        return members, False

    @staticmethod
    def _group_signals(signals: list[dict]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for s in signals:
            grouped.setdefault(s['symbol'], []).append({
                'type': s['action'],
                'date': s['signal_date'].isoformat(),
                'strategy': s['strategy_id'],
            })
        return grouped

    @staticmethod
    def _group_pool_events(events: list[dict], pool_names: dict[int, str]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for e in events:
            grouped.setdefault(e['symbol'], []).append({
                'action': e['action'],
                'pool': pool_names.get(e['pool_id'], str(e['pool_id'])),
                'date': e['changed_at'].date().isoformat(),
            })
        return grouped

    def _build_data(self, *, d0, dn, window, partial, scope_degraded,
                    universe_meta, in_scope, closes,
                    signals_by_symbol, events_by_symbol, pool_events, signals) -> dict:
        excluded = 0
        industries_map: dict[str, list[dict]] = {}
        for symbol, meta in universe_meta.items():
            c = closes.get(symbol, {})
            c0, cn = c.get('first_close'), c.get('last_close')
            # 区间内不足 2 个交易日（含完全无数据/停牌）→ 剔除
            if not c0 or cn is None or c.get('first_date') == c.get('last_date'):
                excluded += 1
                continue
            stock = {
                'symbol': symbol,
                'name': meta['name'],
                'change_pct': round((cn - c0) / c0 * 100, 2),
                'market_cap': meta['market_cap'] or 0,
                'in_scope': symbol in in_scope,
                # 实际用于计算的区间（容忍配对下可能窄于 d0→dn）
                'start_date': c['first_date'].isoformat(),
                'end_date': c['last_date'].isoformat(),
            }
            if symbol in signals_by_symbol:
                stock['signals'] = signals_by_symbol[symbol]
            if symbol in events_by_symbol:
                stock['pool_events'] = events_by_symbol[symbol]
            industries_map.setdefault(meta['industry'], []).append(stock)

        industries = []
        for name, stocks in industries_map.items():
            total_w = sum(max(s['market_cap'], 0) or 1 for s in stocks)
            weighted = sum(
                s['change_pct'] * (max(s['market_cap'], 0) or 1) for s in stocks
            ) / total_w if total_w else 0.0
            industries.append({
                'name': name,
                'change_pct': round(weighted, 2),
                'agent_stance': self._derive_stance(name, universe_meta, in_scope, signals, pool_events),
                'stocks': sorted(stocks, key=lambda s: s['market_cap'], reverse=True),
            })
        industries.sort(key=lambda i: sum(s['market_cap'] for s in i['stocks']), reverse=True)

        return {
            'date': d0.isoformat(),
            'window': window,
            'actual_end_date': dn.isoformat(),
            'partial': partial,
            'scope_degraded': scope_degraded,
            'excluded_count': excluded,
            'industries': industries,
        }

    @staticmethod
    def _derive_stance(industry: str, universe_meta, in_scope, signals, pool_events) -> str:
        """spec §4.4：行业内 in_scope 股票的 (buy + add) vs (sell + remove) 净方向"""
        industry_symbols = {
            sym for sym, m in universe_meta.items()
            if m['industry'] == industry and sym in in_scope
        }
        pos = sum(1 for s in signals if s['symbol'] in industry_symbols and s['action'] == 'buy')
        pos += sum(1 for e in pool_events if e['symbol'] in industry_symbols and e['action'] == 'add')
        neg = sum(1 for s in signals if s['symbol'] in industry_symbols and s['action'] == 'sell')
        neg += sum(1 for e in pool_events if e['symbol'] in industry_symbols and e['action'] == 'remove')
        if pos > neg:
            return 'bullish'
        if neg > pos:
            return 'bearish'
        return 'neutral'

    @staticmethod
    def _empty_data(date_str: Optional[str], window: int, scope_degraded: bool = False) -> dict:
        return {
            'date': date_str,
            'window': window,
            'actual_end_date': None,
            'partial': False,
            'scope_degraded': scope_degraded,
            'excluded_count': 0,
            'industries': [],
            'message': '该日期无可用 K 线数据或 agent 相关行业为空',
        }


heatmap_service = HeatmapService()
