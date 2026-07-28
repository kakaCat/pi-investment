"""
股票池服务

职责：
1. 管理热门股票池（沪深300 + 创业板50 + 科创50）
2. 提供扫描范围（自选股 + 热门股票池）
3. 缓存热门股票池（1小时TTL）
4. 自定义股票池 CRUD（静态池 + 动态池）
5. 动态池刷新（基于 filter_template 重新筛选）
6. 筛选建池（scan → create pool 一步完成）
"""
from typing import Dict, List, Optional
from adapters.outbound.repositories import StockORMRepository
import time
import structlog

logger = structlog.get_logger(__name__)


class StockPoolService:
    """股票池服务：热门池 + 自定义池管理"""

    # 热门指数代码
    HOT_INDEX_CODES = [
        '000300.SH',  # 沪深300
        '399006.SZ',  # 创业板指
        '000688.SH'   # 科创50
    ]

    def __init__(self, stock_repo: StockORMRepository, pool_repo=None, scoring_service=None):
        """
        初始化股票池服务

        Args:
            stock_repo: 股票仓储实例
            pool_repo: StockPoolRepository 实例（可选，用于自定义池 CRUD）
            scoring_service: OpportunityScoringService 实例（可选，用于 scan_create）
        """
        self.stock_repo = stock_repo
        self._pool_repo = pool_repo
        self._scoring_service = scoring_service
        self._cache = None
        self._cache_time = 0
        self._cache_ttl = 3600  # 1 hour
        # 热门池数据来源：'index_constituents' | 'fallback_active_stocks'
        self._hot_pool_source = None

    def get_hot_stocks(self) -> List[str]:
        """
        获取热门股票池（带缓存）

        从3个热门指数获取成分股：
        - 000300.SH: 沪深300
        - 399006.SZ: 创业板指
        - 000688.SH: 科创50

        Returns:
            股票代码列表（去重）
            ['600000.SH', '600036.SH', '000001.SZ', ...]
        """
        # 检查缓存
        current_time = time.time()
        if self._cache is not None and (current_time - self._cache_time) < self._cache_ttl:
            logger.debug("Using cached hot stocks")
            return self._cache

        # 缓存过期或不存在，重新查询
        logger.info(f"Fetching hot stocks from indices: {self.HOT_INDEX_CODES}")

        try:
            # 查询指数成分股
            constituents = self.stock_repo.get_index_constituents(self.HOT_INDEX_CODES)

            if not constituents:
                # index_constituents 表为空（采集任务未跑过）时，不能让扫描池
                # 静默变空——降级为「近期活跃股票」并显式标记来源
                from adapters.outbound.repositories import KlineORMRepository
                fallback = KlineORMRepository().get_active_symbols(days=15, min_days=3, limit=500)
                logger.warning(
                    f"index_constituents 为空，热门池降级为活跃股票 fallback: {len(fallback)} 只")
                self._hot_pool_source = 'fallback_active_stocks'
                unique_stocks = fallback
            else:
                self._hot_pool_source = 'index_constituents'
                # 去重（保持顺序）
                unique_stocks = list(dict.fromkeys(constituents))

            # 更新缓存
            self._cache = unique_stocks
            self._cache_time = current_time

            logger.info(f"Hot stocks fetched: {len(unique_stocks)} stocks (source={self._hot_pool_source})")
            return unique_stocks

        except Exception as e:
            logger.error(f"Failed to fetch hot stocks: {e}")
            # 如果有旧缓存，返回旧缓存
            if self._cache is not None:
                logger.warning("Returning stale cache due to error")
                return self._cache
            raise

    def get_scan_universe(self, user_watchlist: List[str]) -> List[str]:
        """
        获取扫描范围（自选股 + 热门股票池）

        Args:
            user_watchlist: 用户自选股列表

        Returns:
            股票代码列表（去重）
            ['600000.SH', '600036.SH', '000858.SZ', ...]
        """
        # 获取热门股票池
        hot_stocks = self.get_hot_stocks()

        # 合并自选股和热门股票池
        combined = user_watchlist + hot_stocks

        # 去重（保持顺序）
        unique_stocks = list(dict.fromkeys(combined))

        logger.info(
            f"Scan universe: {len(unique_stocks)} stocks "
            f"(watchlist: {len(user_watchlist)}, hot: {len(hot_stocks)})"
        )

        return unique_stocks

    # ── 自定义池 CRUD ──

    def create_pool(self, name: str, pool_type: str, symbols: list = None,
                    filter_template: dict = None, refresh_interval: str = None,
                    description: str = None) -> dict:
        """创建股票池（静态或动态）。"""
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        if pool_type == 'static' and not symbols:
            raise ValueError("Static pool requires symbols list")
        if pool_type == 'dynamic' and not filter_template:
            raise ValueError("Dynamic pool requires filter_template")

        return self._pool_repo.create({
            'name': name,
            'pool_type': pool_type,
            'symbols': symbols or [],
            'description': description,
            'filter_template': filter_template,
            'refresh_interval': refresh_interval,
        })

    def get_pool(self, pool_id: int) -> dict:
        """获取池子详情。不存在时抛 ValueError。"""
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        pool = self._pool_repo.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        # 优先使用 members 字段（新格式），如果不存在则从 symbols 构建
        if pool.get('members') and len(pool.get('members', [])) > 0:
            # 已有 members 数据，补充缺失的股票名称
            members = pool['members']
            symbols_need_names = [m['symbol'] for m in members if not m.get('name')]
            if symbols_need_names:
                names_by_symbol = self.stock_repo.batch_get_names(symbols_need_names)
                for member in members:
                    if not member.get('name') and member['symbol'] in names_by_symbol:
                        member['name'] = names_by_symbol[member['symbol']]
            pool['members'] = members
        else:
            # 兼容旧格式：从 symbols 构建 members
            symbols = pool.get('symbols') or []
            names_by_symbol = {}
            if symbols:
                names_by_symbol = self.stock_repo.batch_get_names(symbols)
            pool['members'] = [
                {
                    'symbol': symbol,
                    'name': names_by_symbol.get(symbol),
                    'description': None,
                    'buy_point': None,
                    'sell_point': None,
                    'tags': []
                }
                for symbol in symbols
            ]
        return pool

    def list_pools(self) -> list:
        """列出所有池子（摘要信息，不含完整 symbols）。"""
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        pools = self._pool_repo.get_all()
        result = []
        for p in pools:
            summary = {
                'id': p['id'],
                'name': p['name'],
                'pool_type': p['pool_type'],
                'description': p['description'],
                'symbol_count': len(p.get('symbols', [])),
                'refresh_interval': p.get('refresh_interval'),
                'last_refreshed_at': str(p['last_refreshed_at']) if p.get('last_refreshed_at') else None,
                'has_validation': p.get('last_validation') is not None,
                'created_at': str(p['created_at']),
            }
            result.append(summary)
        return result

    def update_pool(self, pool_id: int, **kwargs) -> dict:
        """更新池子字段。返回更新后的池子。"""
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        updated = self._pool_repo.update(pool_id, kwargs)
        if not updated:
            raise ValueError(f"Pool {pool_id} not found")
        return updated

    def delete_pool(self, pool_id: int) -> bool:
        """删除池子。不存在时抛 ValueError。"""
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        if not self._pool_repo.delete(pool_id):
            raise ValueError(f"Pool {pool_id} not found")
        return True

    def update_member(self, pool_id: int, symbol: str, member_data: dict) -> dict:
        """
        更新池子中单个成员的详细信息

        Args:
            pool_id: 池子ID
            symbol: 股票代码
            member_data: 成员数据（description, buy_point, sell_point, tags）

        Returns:
            更新后的池子
        """
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")

        pool = self._pool_repo.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        # 获取现有 members
        members = pool.get('members')
        logger.info(f"Current members type: {type(members)}, value: {members}")

        if not members or len(members) == 0:
            # 如果没有 members，从 symbols 构建
            symbols = pool.get('symbols') or []
            names_by_symbol = self.stock_repo.batch_get_names(symbols) if symbols else {}
            members = [
                {
                    'symbol': s,
                    'name': names_by_symbol.get(s),
                    'description': None,
                    'buy_point': None,
                    'sell_point': None,
                    'tags': []
                }
                for s in symbols
            ]
            logger.info(f"Built members from symbols: {len(members)} members")

        # 查找并更新指定成员
        found = False
        for i, member in enumerate(members):
            logger.debug(f"Checking member {i}: {member.get('symbol')} vs {symbol}")
            if member.get('symbol') == symbol:
                # 更新字段，只更新提供的值
                logger.info(f"Found member at index {i}, updating with data: {member_data}")
                if 'description' in member_data:
                    members[i]['description'] = member_data['description']
                if 'buy_point' in member_data:
                    members[i]['buy_point'] = member_data['buy_point']
                if 'sell_point' in member_data:
                    members[i]['sell_point'] = member_data['sell_point']
                if 'tags' in member_data:
                    members[i]['tags'] = member_data['tags']
                found = True
                logger.info(f"Updated member {symbol} in pool {pool_id}: {members[i]}")
                break

        if not found:
            logger.error(f"Symbol {symbol} not found in pool {pool_id}")
            raise ValueError(f"Symbol {symbol} not found in pool {pool_id}")

        # 更新数据库
        logger.info(f"Updating database with members: {members}")
        updated = self._pool_repo.update(pool_id, {'members': members})
        if not updated:
            logger.error(f"Failed to update pool {pool_id}")
            raise ValueError(f"Failed to update pool {pool_id}")

        logger.info(f"Successfully updated pool {pool_id}")
        return self.get_pool(pool_id)

    # 动态池手动增删成员的覆盖警告
    DYNAMIC_POOL_WARNING = (
        '动态池 refresh 将按筛选条件重建成员，手动增删的成员可能被覆盖'
    )

    def _ensure_members(self, pool: dict) -> list:
        """返回池的 members 列表；为空时从 symbols 重建（不持久化）。"""
        members = pool.get('members') or []
        if members:
            return list(members)
        symbols = pool.get('symbols') or []
        names_by_symbol = self.stock_repo.batch_get_names(symbols) if symbols else {}
        return [
            {'symbol': s, 'name': names_by_symbol.get(s), 'description': None,
             'buy_point': None, 'sell_point': None, 'tags': []}
            for s in symbols
        ]

    def add_members(self, pool_id: int, symbols: List[str],
                    member_data: dict = None) -> dict:
        """
        批量添加池子成员（幂等：已在池中的跳过）。

        Returns:
            {pool, added, skipped, warning?}
        """
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        pool = self._pool_repo.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        member_data = member_data or {}
        current_symbols = list(pool.get('symbols') or [])
        members = self._ensure_members(pool)

        existing = set(current_symbols)
        to_add = [s for s in symbols if s not in existing]
        skipped = [s for s in symbols if s in existing]

        if to_add:
            names_by_symbol = self.stock_repo.batch_get_names(to_add)
            for s in to_add:
                members.append({
                    'symbol': s,
                    'name': names_by_symbol.get(s),
                    'description': member_data.get('description'),
                    'buy_point': member_data.get('buy_point'),
                    'sell_point': member_data.get('sell_point'),
                    'tags': member_data.get('tags') or [],
                })
                current_symbols.append(s)
            updated = self._pool_repo.update(
                pool_id, {'symbols': current_symbols, 'members': members})
            if not updated:
                raise ValueError(f"Failed to update pool {pool_id}")

        result = {
            'pool': self.get_pool(pool_id),
            'added': to_add,
            'skipped': skipped,
        }
        if pool.get('pool_type') == 'dynamic':
            result['warning'] = self.DYNAMIC_POOL_WARNING
        return result

    def remove_members(self, pool_id: int, symbols: List[str]) -> dict:
        """
        批量移除池子成员（幂等：不在池中的跳过）。

        Returns:
            {pool, removed, skipped, warning?}
        """
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        pool = self._pool_repo.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        current_symbols = list(pool.get('symbols') or [])
        members = self._ensure_members(pool)

        existing = set(current_symbols)
        to_remove = [s for s in symbols if s in existing]
        skipped = [s for s in symbols if s not in existing]

        if to_remove:
            remove_set = set(to_remove)
            current_symbols = [s for s in current_symbols if s not in remove_set]
            members = [m for m in members if m.get('symbol') not in remove_set]
            updated = self._pool_repo.update(
                pool_id, {'symbols': current_symbols, 'members': members})
            if not updated:
                raise ValueError(f"Failed to update pool {pool_id}")

        result = {
            'pool': self.get_pool(pool_id),
            'removed': to_remove,
            'skipped': skipped,
        }
        if pool.get('pool_type') == 'dynamic':
            result['warning'] = self.DYNAMIC_POOL_WARNING
        return result

    def sync_stock_names(self, pool_id: int) -> dict:
        """同步股票池成员名称并持久化到 members 字段。"""
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")

        pool = self._pool_repo.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        symbols = pool.get('symbols') or []
        members = pool.get('members') or []

        if members:
            member_symbols = [
                member.get('symbol') if isinstance(member, dict) else member
                for member in members
            ]
            symbols = list(dict.fromkeys([*member_symbols, *symbols]))

        if not symbols:
            raise ValueError(f"Pool {pool_id} is empty")

        logger.info(f"Syncing names for {len(symbols)} symbols: {symbols[:5]}...")
        names_by_symbol = self.stock_repo.batch_get_names(symbols)
        logger.info(f"Got {len(names_by_symbol)} names: {list(names_by_symbol.items())[:3]}")

        existing_by_symbol = {}
        for member in members:
            if isinstance(member, dict) and member.get('symbol'):
                existing_by_symbol[member['symbol']] = member

        synced_members = []
        for symbol in symbols:
            existing = existing_by_symbol.get(symbol, {})
            name = names_by_symbol.get(symbol) or existing.get('name')
            synced_members.append({
                'symbol': symbol,
                'name': name,
                'description': existing.get('description'),
                'buy_point': existing.get('buy_point'),
                'sell_point': existing.get('sell_point'),
                'tags': existing.get('tags') or [],
            })

        logger.info(f"Updating pool {pool_id} with {len(synced_members)} members")
        updated = self._pool_repo.update(pool_id, {'members': synced_members})
        if not updated:
            raise ValueError(f"Failed to update pool {pool_id}")
        return updated

    def refresh_pool(self, pool_id: int) -> dict:
        """刷新动态池：用 filter_template 重新筛选，更新 symbols。"""
        if not self._pool_repo:
            raise RuntimeError("StockPoolRepository not configured")
        if not self._scoring_service:
            raise RuntimeError("OpportunityScoringService not configured")

        pool = self._pool_repo.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")
        if pool['pool_type'] != 'dynamic':
            raise ValueError(f"Pool {pool_id} is static, cannot refresh")
        if not pool.get('filter_template'):
            raise ValueError(f"Pool {pool_id} has no filter_template")

        template = pool['filter_template']
        universe = self.get_hot_stocks()

        filters = {
            'technical': template.get('technical', []),
            'fundamental': template.get('fundamental', []),
        }
        scored = self._scoring_service.score_stocks(universe, filters)

        # Apply min_score filter
        min_score = template.get('min_score', 0)
        filtered = [s for s in scored if s.get('score', 0) >= min_score]

        # Apply max_risk_level filter
        max_risk = template.get('max_risk_level')
        if max_risk:
            risk_order = {'low': 0, 'medium': 1, 'high': 2}
            max_level = risk_order.get(max_risk, 2)
            filtered = [s for s in filtered if risk_order.get(s.get('risk_level', 'high'), 2) <= max_level]

        # Sort by score descending, take top_n
        filtered.sort(key=lambda s: s.get('score', 0), reverse=True)
        top_n = template.get('top_n', 50)
        symbols = [s['symbol'] for s in filtered[:top_n]]

        updated = self._pool_repo.update_symbols(pool_id, symbols)
        logger.info(f"Refreshed pool {pool_id}: {len(symbols)} symbols")
        return updated

    def create_from_scan(self, name: str, pool_type: str, scan_params: dict,
                         refresh_interval: str = None, description: str = None) -> dict:
        """筛选建池：执行多因子扫描后自动创建池子。"""
        if not self._scoring_service:
            raise RuntimeError("OpportunityScoringService not configured")

        universe = self.get_hot_stocks()
        filters = {
            'technical': scan_params.get('technical', []),
            'fundamental': scan_params.get('fundamental', []),
            'conditions': scan_params.get('conditions', []),
            'logic': scan_params.get('logic', 'AND'),
        }
        scored = self._scoring_service.score_stocks(universe, filters)

        min_score = scan_params.get('min_score', 0)
        filtered = [s for s in scored if s.get('score', 0) >= min_score]

        max_risk = scan_params.get('max_risk_level')
        if max_risk:
            risk_order = {'low': 0, 'medium': 1, 'high': 2}
            max_level = risk_order.get(max_risk, 2)
            filtered = [s for s in filtered if risk_order.get(s.get('risk_level', 'high'), 2) <= max_level]

        filtered.sort(key=lambda s: s.get('score', 0), reverse=True)
        top_n = scan_params.get('top_n', 50)
        symbols = [s['symbol'] for s in filtered[:top_n]]

        filter_template = scan_params if pool_type == 'dynamic' else None

        return self.create_pool(
            name=name,
            pool_type=pool_type,
            symbols=symbols,
            filter_template=filter_template,
            refresh_interval=refresh_interval if pool_type == 'dynamic' else None,
            description=description,
        )
