"""
测试 StockPoolService
"""
import pytest
from unittest.mock import Mock, patch
import time
from application.services.stock_pool_service import StockPoolService
from adapters.outbound.repositories import StockORMRepository


class TestStockPoolService:
    """测试股票池服务"""

    @pytest.fixture
    def mock_stock_repo(self):
        """创建mock的StockRepository"""
        return Mock(spec=StockORMRepository)

    @pytest.fixture
    def service(self, mock_stock_repo):
        """创建StockPoolService实例"""
        return StockPoolService(mock_stock_repo)

    def test_get_hot_stocks_basic(self, service, mock_stock_repo):
        """测试获取热门股票池 - 基本功能"""
        # Mock返回数据
        mock_stock_repo.get_index_constituents.return_value = [
            '000001.SH', '600036.SH', '000001.SZ', '000002.SZ'
        ]

        # 调用方法
        result = service.get_hot_stocks()

        # 验证调用参数
        mock_stock_repo.get_index_constituents.assert_called_once_with(
            ['000300.SH', '399006.SZ', '000688.SH']
        )

        # 验证返回结果
        assert isinstance(result, list)
        assert len(result) == 4
        assert '000001.SH' in result
        assert '000001.SZ' in result

    def test_get_hot_stocks_deduplication(self, service, mock_stock_repo):
        """测试获取热门股票池 - 去重功能"""
        # Mock返回包含重复股票的数据
        mock_stock_repo.get_index_constituents.return_value = [
            '000001.SH', '600036.SH', '000001.SH', '000001.SZ', '600036.SH'
        ]

        result = service.get_hot_stocks()

        # 验证去重
        assert len(result) == 3
        assert result.count('000001.SH') == 1
        assert result.count('600036.SH') == 1
        assert result.count('000001.SZ') == 1

    def test_get_hot_stocks_caching(self, service, mock_stock_repo):
        """测试获取热门股票池 - 缓存功能"""
        # Mock返回数据
        mock_stock_repo.get_index_constituents.return_value = [
            '000001.SH', '600036.SH'
        ]

        # 第一次调用
        result1 = service.get_hot_stocks()
        assert mock_stock_repo.get_index_constituents.call_count == 1

        # 第二次调用（应该使用缓存）
        result2 = service.get_hot_stocks()
        assert mock_stock_repo.get_index_constituents.call_count == 1  # 没有增加
        assert result1 == result2

    def test_get_hot_stocks_cache_expiration(self, service, mock_stock_repo):
        """测试获取热门股票池 - 缓存过期"""
        # Mock返回数据
        mock_stock_repo.get_index_constituents.return_value = [
            '000001.SH', '600036.SH'
        ]

        # 第一次调用
        service.get_hot_stocks()
        assert mock_stock_repo.get_index_constituents.call_count == 1

        # 模拟缓存过期（修改缓存时间）
        service._cache_time = time.time() - 3601  # 超过1小时

        # 第二次调用（应该重新查询）
        service.get_hot_stocks()
        assert mock_stock_repo.get_index_constituents.call_count == 2

    def test_get_hot_stocks_empty_result(self, service, mock_stock_repo):
        """测试获取热门股票池 - 空结果"""
        # Mock返回空列表
        mock_stock_repo.get_index_constituents.return_value = []

        result = service.get_hot_stocks()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_scan_universe_empty_watchlist(self, service, mock_stock_repo):
        """测试获取扫描范围 - 空自选股"""
        # Mock热门股票池
        mock_stock_repo.get_index_constituents.return_value = [
            '000001.SH', '600036.SH', '000001.SZ'
        ]

        result = service.get_scan_universe([])

        # 应该只返回热门股票池
        assert len(result) == 3
        assert '000001.SH' in result
        assert '600036.SH' in result
        assert '000001.SZ' in result

    def test_get_scan_universe_with_watchlist(self, service, mock_stock_repo):
        """测试获取扫描范围 - 有自选股"""
        # Mock热门股票池
        mock_stock_repo.get_index_constituents.return_value = [
            '000001.SH', '600036.SH'
        ]

        # 自选股
        watchlist = ['000858.SZ', '002594.SZ']

        result = service.get_scan_universe(watchlist)

        # 应该返回自选股 + 热门股票池
        assert len(result) == 4
        assert '000001.SH' in result
        assert '600036.SH' in result
        assert '000858.SZ' in result
        assert '002594.SZ' in result

    def test_get_scan_universe_deduplication(self, service, mock_stock_repo):
        """测试获取扫描范围 - 去重功能"""
        # Mock热门股票池
        mock_stock_repo.get_index_constituents.return_value = [
            '000001.SH', '600036.SH', '000001.SZ'
        ]

        # 自选股包含热门股票池中的股票
        watchlist = ['000001.SH', '000858.SZ', '600036.SH']

        result = service.get_scan_universe(watchlist)

        # 应该去重
        assert len(result) == 4  # 000001, 600036, 000001, 000858
        assert result.count('000001.SH') == 1
        assert result.count('600036.SH') == 1
        assert result.count('000001.SZ') == 1
        assert result.count('000858.SZ') == 1

    def test_get_scan_universe_all_duplicates(self, service, mock_stock_repo):
        """测试获取扫描范围 - 自选股全部在热门池中"""
        # Mock热门股票池
        mock_stock_repo.get_index_constituents.return_value = [
            '000001.SH', '600036.SH', '000001.SZ'
        ]

        # 自选股全部在热门池中
        watchlist = ['000001.SH', '600036.SH']

        result = service.get_scan_universe(watchlist)

        # 应该只返回3个（去重后）
        assert len(result) == 3
        assert '000001.SH' in result
        assert '600036.SH' in result
        assert '000001.SZ' in result

    def test_hot_index_codes_constant(self):
        """测试热门指数代码常量"""
        assert StockPoolService.HOT_INDEX_CODES == [
            '000300.SH',  # 沪深300
            '399006.SZ',  # 创业板指
            '000688.SH'   # 科创50
        ]

    def test_get_pool_includes_member_names(self, mock_stock_repo):
        """股票池详情返回成员列表和股票名称。"""
        pool_repo = Mock()
        pool_repo.get_pool.return_value = {
            'id': 4,
            'name': '高波动池',
            'pool_type': 'static',
            'symbols': ['300750', '688981', '999999'],
        }
        mock_stock_repo.batch_get_names.return_value = {
            '300750': '宁德时代',
            '688981': '中芯国际',
        }
        service = StockPoolService(mock_stock_repo, pool_repo=pool_repo)

        result = service.get_pool(4)

        mock_stock_repo.batch_get_names.assert_called_once_with(['300750', '688981', '999999'])
        assert result['members'] == [
            {'symbol': '300750', 'name': '宁德时代', 'description': None, 'buy_point': None, 'sell_point': None, 'tags': []},
            {'symbol': '688981', 'name': '中芯国际', 'description': None, 'buy_point': None, 'sell_point': None, 'tags': []},
            {'symbol': '999999', 'name': None, 'description': None, 'buy_point': None, 'sell_point': None, 'tags': []},
        ]

    def test_sync_stock_names_persists_member_names(self, mock_stock_repo):
        """同步股票名称会保留成员元数据并回写 members。"""
        pool_repo = Mock()
        pool_repo.get_pool.return_value = {
            'id': 4,
            'name': '高波动池',
            'pool_type': 'static',
            'symbols': ['300750', '688981'],
            'members': [
                {
                    'symbol': '300750',
                    'description': '电池龙头',
                    'buy_point': '突破均线',
                    'sell_point': '跌破支撑',
                    'tags': ['成长股'],
                },
                {'symbol': '688981', 'name': ''},
            ],
        }
        pool_repo.update.return_value = {
            'id': 4,
            'members': [
                {
                    'symbol': '300750',
                    'name': '宁德时代',
                    'description': '电池龙头',
                    'buy_point': '突破均线',
                    'sell_point': '跌破支撑',
                    'tags': ['成长股'],
                },
                {
                    'symbol': '688981',
                    'name': '中芯国际',
                    'description': None,
                    'buy_point': None,
                    'sell_point': None,
                    'tags': [],
                },
            ],
        }
        mock_stock_repo.batch_get_names.return_value = {
            '300750': '宁德时代',
            '688981': '中芯国际',
        }
        service = StockPoolService(mock_stock_repo, pool_repo=pool_repo)

        result = service.sync_stock_names(4)

        mock_stock_repo.batch_get_names.assert_called_once_with(['300750', '688981'])
        pool_repo.update.assert_called_once_with(4, {'members': [
            {
                'symbol': '300750',
                'name': '宁德时代',
                'description': '电池龙头',
                'buy_point': '突破均线',
                'sell_point': '跌破支撑',
                'tags': ['成长股'],
            },
            {
                'symbol': '688981',
                'name': '中芯国际',
                'description': None,
                'buy_point': None,
                'sell_point': None,
                'tags': [],
            },
        ]})
        assert result['members'][0]['name'] == '宁德时代'


class TestPoolMemberOps:
    """add_members / remove_members 单元测试"""

    @pytest.fixture
    def mock_stock_repo(self):
        repo = Mock()
        repo.batch_get_names.return_value = {
            '600519.SH': '贵州茅台', '000858.SZ': '五粮液', '000001.SZ': '平安银行',
        }
        return repo

    def _make_service(self, mock_stock_repo, pool):
        pool_repo = Mock()
        pool_repo.get_pool.return_value = pool
        pool_repo.update.return_value = dict(pool) if pool else None
        return StockPoolService(mock_stock_repo, pool_repo=pool_repo), pool_repo

    def _static_pool(self):
        return {
            'id': 1, 'name': '测试池', 'pool_type': 'static',
            'symbols': ['600519.SH'],
            'members': [
                {'symbol': '600519.SH', 'name': '贵州茅台', 'description': None,
                 'buy_point': None, 'sell_point': None, 'tags': []},
            ],
        }

    def test_add_members_adds_new_with_names_and_metadata(self, mock_stock_repo):
        svc, pool_repo = self._make_service(mock_stock_repo, self._static_pool())
        result = svc.add_members(1, ['000858.SZ', '000001.SZ'],
                                 member_data={'description': '关注', 'tags': ['白酒']})
        assert result['added'] == ['000858.SZ', '000001.SZ']
        assert result['skipped'] == []
        assert 'warning' not in result
        pool_repo.update.assert_called_once()
        args = pool_repo.update.call_args[0]
        assert args[0] == 1
        assert args[1]['symbols'] == ['600519.SH', '000858.SZ', '000001.SZ']
        new_members = args[1]['members'][1:]
        assert new_members[0]['name'] == '五粮液'
        assert new_members[0]['description'] == '关注'
        assert new_members[0]['tags'] == ['白酒']
        assert new_members[1]['name'] == '平安银行'

    def test_add_members_skips_existing(self, mock_stock_repo):
        svc, pool_repo = self._make_service(mock_stock_repo, self._static_pool())
        result = svc.add_members(1, ['600519.SH', '000858.SZ'])
        assert result['added'] == ['000858.SZ']
        assert result['skipped'] == ['600519.SH']

    def test_add_members_all_existing_no_update(self, mock_stock_repo):
        svc, pool_repo = self._make_service(mock_stock_repo, self._static_pool())
        result = svc.add_members(1, ['600519.SH'])
        assert result['added'] == []
        assert result['skipped'] == ['600519.SH']
        pool_repo.update.assert_not_called()

    def test_add_members_pool_not_found(self, mock_stock_repo):
        svc, _ = self._make_service(mock_stock_repo, None)
        with pytest.raises(ValueError, match="Pool 999 not found"):
            svc.add_members(999, ['600519.SH'])

    def test_add_members_dynamic_pool_warning(self, mock_stock_repo):
        pool = self._static_pool()
        pool['pool_type'] = 'dynamic'
        svc, _ = self._make_service(mock_stock_repo, pool)
        result = svc.add_members(1, ['000858.SZ'])
        assert 'warning' in result
        assert 'refresh' in result['warning']

    def test_add_members_rebuilds_members_from_symbols(self, mock_stock_repo):
        pool = {'id': 1, 'name': '旧池', 'pool_type': 'static',
                'symbols': ['600519.SH'], 'members': []}
        svc, pool_repo = self._make_service(mock_stock_repo, pool)
        svc.add_members(1, ['000858.SZ'])
        args = pool_repo.update.call_args[0]
        assert [m['symbol'] for m in args[1]['members']] == ['600519.SH', '000858.SZ']

    def test_remove_members_removes_from_symbols_and_members(self, mock_stock_repo):
        pool = self._static_pool()
        pool['symbols'].append('000858.SZ')
        pool['members'].append({'symbol': '000858.SZ', 'name': '五粮液',
                                'description': None, 'buy_point': None,
                                'sell_point': None, 'tags': []})
        svc, pool_repo = self._make_service(mock_stock_repo, pool)
        result = svc.remove_members(1, ['000858.SZ'])
        assert result['removed'] == ['000858.SZ']
        assert result['skipped'] == []
        args = pool_repo.update.call_args[0]
        assert args[1]['symbols'] == ['600519.SH']
        assert [m['symbol'] for m in args[1]['members']] == ['600519.SH']

    def test_remove_members_skips_missing(self, mock_stock_repo):
        svc, pool_repo = self._make_service(mock_stock_repo, self._static_pool())
        result = svc.remove_members(1, ['000858.SZ'])
        assert result['removed'] == []
        assert result['skipped'] == ['000858.SZ']
        pool_repo.update.assert_not_called()

    def test_remove_members_pool_not_found(self, mock_stock_repo):
        svc, _ = self._make_service(mock_stock_repo, None)
        with pytest.raises(ValueError, match="Pool 999 not found"):
            svc.remove_members(999, ['600519.SH'])

    def test_remove_members_dynamic_pool_warning(self, mock_stock_repo):
        pool = self._static_pool()
        pool['pool_type'] = 'dynamic'
        svc, _ = self._make_service(mock_stock_repo, pool)
        result = svc.remove_members(1, ['600519.SH'])
        assert 'warning' in result
