"""持仓板块映射服务（2026-10-19 P2 市场环境联动）

用户的场景：「看好的个股，但整个板块集体跳水，就需要评估是否调整持仓」。
板块强度数据（MarketState.sectors）用的是行情源行业板块名（东财/akshare 口径），
而 quant.stocks.industry 是证监会分类（「制造业-医药制造业」）——两套命名对不上，
可靠映射只能**反查**：逐个板块取成分股，与持仓标的求交。

纪律：
- 取数走 qs_market_data 的 DataProviderManager（仓内 Data Access Rules：不直连 akshare）；
- 构建是重活（每板块一次外呼），只在 **sidecar 每日刷新**，tick 热路径只读缓存快照；
- 失败保留旧映射（stale 比空好），首次构建失败返回空映射——held_sector_pct
  评估器对空映射 skipped（诚实标注），绝不拿残缺数据当「无越线」。
"""
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 映射缓存 TTL（秒）：板块成分日间基本不变，6h 够
DEFAULT_TTL_SEC = 6 * 3600
#: 单日刷新最多遍历的行业板块数（防爆量外呼；东财行业板块约 86 个）
MAX_BOARDS_PER_REFRESH = 120


class HeldSectorMapService:
    """持仓 → 行情板块 的映射（内存快照 + TTL 惰性过期，refresh 由调用方驱动）"""

    def __init__(self, position_repo, accounts,
                 data_manager=None,
                 ttl_sec: int = DEFAULT_TTL_SEC,
                 now_fn: Callable[[], datetime] = datetime.now):
        self._position_repo = position_repo
        self._accounts = tuple(accounts)
        self._manager = data_manager  # None 时首次 refresh 惰性取单例（测试注入友好）
        self._ttl = ttl_sec
        self._now = now_fn
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._built_at: Optional[datetime] = None
        self.degraded: bool = False

    # ── 读（tick 安全：只读缓存，零 I/O）─────────────────────

    def held_boards(self) -> Dict[str, List[Dict[str, Any]]]:
        """板块名 → [{symbol, account, shares}]；未构建/已过期返回 {}（调用方 skipped）。"""
        if self._built_at is None:
            return {}
        if (self._now() - self._built_at).total_seconds() >= self._ttl:
            return {}
        return self._cache

    # ── 写（sidecar 每日调用；绝不在 tick 热路径跑）──────────

    def refresh(self, force: bool = False) -> Dict[str, Any]:
        """重建映射。失败保留旧缓存并置 degraded；首次失败则缓存为空。

        返回 {'boards': n, 'holdings': m, 'degraded': bool} 供调用方记日志。
        """
        if not force and self._built_at is not None and \
                (self._now() - self._built_at).total_seconds() <= self._ttl:
            return {'boards': len(self._cache), 'skipped': 'TTL 未到期',
                    'degraded': self.degraded}
        try:
            holdings = self._load_holdings()
        except Exception as e:  # noqa: BLE001
            self.degraded = True
            logger.error('持仓读取失败，保留旧板块映射', error=str(e))
            return {'boards': len(self._cache), 'degraded': True}
        if not holdings:
            self._cache, self._built_at, self.degraded = {}, self._now(), False
            return {'boards': 0, 'holdings': 0, 'degraded': False}

        try:
            manager = self._manager or self._default_manager()
            new_map = self._build(manager, holdings)
        except Exception as e:  # noqa: BLE001
            self.degraded = True
            logger.error('板块映射重建失败，保留旧映射', error=str(e))
            return {'boards': len(self._cache), 'degraded': True}

        self._cache, self._built_at, self.degraded = new_map, self._now(), False
        logger.info('持仓板块映射已重建', boards=len(new_map),
                    holdings=sum(len(v) for v in new_map.values()))
        return {'boards': len(new_map),
                'holdings': sum(len(v) for v in new_map.values()),
                'degraded': False}

    # ── 内部 ────────────────────────────────────────────────

    def _load_holdings(self) -> Dict[str, List[Dict[str, Any]]]:
        """symbol → [{symbol, account, shares}]（同标的多账户合并列出）。

        行是 ORM 对象（与 PositionLifecycleService 同一仓储同一形状）。
        单账户读取失败抛给上层（fail-closed：宁可不重建也不拿残缺持仓误判"无持仓"）。
        """
        out: Dict[str, List[Dict[str, Any]]] = {}
        for acct in self._accounts:
            rows = self._position_repo.get_all_positions(acct) or []
            for p in rows:
                sym = str(getattr(p, 'symbol', '') or '').split('.')[0]
                shares = int(getattr(p, 'shares_total', 0) or 0)
                if not sym or shares <= 0:
                    continue
                out.setdefault(sym, []).append(
                    {'symbol': sym, 'account': acct, 'shares': shares})
        return out

    def _build(self, manager, holdings: Dict[str, List[Dict[str, Any]]]
               ) -> Dict[str, List[Dict[str, Any]]]:
        lst = manager.get_sector_list()
        # 形状兼容（2026-10-20 两次实测修正）：manager 返回 {'success':True,
        # 'data': MarketData(...)}——dict 里再包一层对象，要剥两次才到 industries。
        data = lst.get('data') if isinstance(lst, dict) else getattr(lst, 'data', None)
        if data is not None and not isinstance(data, dict):
            data = getattr(data, 'data', None)   # MarketData → 内层 dict
        if not isinstance(data, dict):
            raise RuntimeError('板块列表获取失败: %r' % (lst,))
        industries = data.get('industries') or []
        names = [str(i.get('name')) for i in industries if isinstance(i, dict) and i.get('name')]
        if not names:
            raise RuntimeError('板块列表为空（数据源异常）')

        held_symbols = set(holdings)
        result: Dict[str, List[Dict[str, Any]]] = {}
        for name in names[:MAX_BOARDS_PER_REFRESH]:
            try:
                res = manager.get_sector_stocks(name)
            except Exception as e:  # noqa: BLE001 - 单板块失败不拖垮整批
                logger.warning('板块成分获取失败（跳过该板块）', board=name, error=str(e))
                continue
            data = res.get('data') if isinstance(res, dict) else getattr(res, 'data', None)
            if data is not None and not isinstance(data, dict):
                data = getattr(data, 'data', None)   # 同款双层包裹剥壳
            if not isinstance(data, dict) or not data.get('found'):
                continue
            members = [h for s in
                       (str(x.get('symbol') or '') for x in (data.get('stocks') or []))
                       for h in holdings.get(s, [])]
            if members:
                result[name] = members
        return result

    @staticmethod
    def _default_manager():
        from qs_market_data.adapters.outbound.datasources.manager import (
            get_data_provider_manager,
        )
        return get_data_provider_manager()
