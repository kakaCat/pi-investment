"""
测试风控检查服务
"""

import pytest
from unittest.mock import Mock, MagicMock
from application.services.risk_check_service import RiskCheckService
from application.services.data_service import DataService


@pytest.fixture
def mock_data_service():
    """创建模拟的DataService"""
    ds = Mock(spec=DataService)

    # Mock kline repository
    ds.kline = Mock()
    ds.kline.get_latest_daily_kline = Mock(return_value={
        'symbol': '000001.SH',
        'close': 1500.0,
        'date': '2026-05-28'
    })

    # Mock risk repository - 充足的资金
    ds.risk = Mock()
    ds.risk.get_latest_balance = Mock(return_value={
        'cash': 500000.0,  # 50万现金
        'total_assets': 1000000.0,  # 100万总资产
        'market_value': 500000.0
    })

    # Mock portfolio repository
    ds.portfolio = Mock()
    ds.portfolio.get_holding = Mock(return_value=None)
    ds.portfolio.get_all_holdings = Mock(return_value=[])
    ds.portfolio.db = Mock()

    # Mock cursor for trade limit check
    mock_cursor = Mock()
    mock_cursor.fetchall = Mock(return_value=[])
    ds.portfolio.db.cursor = Mock(return_value=mock_cursor)

    # Mock stock repository
    ds.stock = Mock()
    ds.stock.get_by_symbol = Mock(return_value={
        'symbol': '000001.SH',
        'name': '浦发银行',
        'industry': '白酒'
    })

    return ds


def test_check_signal_buy_pass(mock_data_service):
    """测试买入信号通过风控"""
    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        'quantity': 100,
        'risk_management': {
            'stop_loss': {'percent': 5.0}
        }
    }

    result = service.check_signal(signal)

    assert result['passed'] is True
    assert result['quantity'] == 100
    assert 'checks' in result
    assert 'funds_check' in result['checks']
    assert result['checks']['funds_check']['passed'] is True


def test_check_signal_insufficient_funds(mock_data_service):
    """测试资金不足被拒绝"""
    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        'quantity': 100000,  # 超大数量，需要1.5亿
        'risk_management': {
            'stop_loss': {'percent': 5.0}
        }
    }

    result = service.check_signal(signal)

    assert result['passed'] is False
    assert '资金不足' in result['reason']


def test_check_signal_sell_with_holding(mock_data_service):
    """测试有持仓时卖出通过"""
    # Mock有持仓
    mock_data_service.portfolio.get_holding = Mock(return_value={
        'symbol': '000001.SH',
        'quantity': 500
    })

    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'sell',
        'quantity': 100
    }

    result = service.check_signal(signal)

    assert result['passed'] is True
    assert result['quantity'] == 100
    assert 'holding_check' in result['checks']


def test_check_signal_no_holding(mock_data_service):
    """测试卖出无持仓被拒绝"""
    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '999999.SH',
        'action': 'sell',
        'quantity': 100
    }

    result = service.check_signal(signal)

    assert result['passed'] is False
    assert '无持仓' in result['reason']


def test_check_signal_insufficient_holding(mock_data_service):
    """测试持仓不足被拒绝"""
    # Mock持仓不足
    mock_data_service.portfolio.get_holding = Mock(return_value={
        'symbol': '000001.SH',
        'quantity': 50
    })

    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'sell',
        'quantity': 100
    }

    result = service.check_signal(signal)

    assert result['passed'] is False
    assert '持仓不足' in result['reason']


def test_check_signal_missing_stop_loss(mock_data_service):
    """测试缺少止损设置被拒绝"""
    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        'quantity': 100
        # 缺少 risk_management.stop_loss
    }

    result = service.check_signal(signal)

    assert result['passed'] is False
    assert '止损' in result['reason']


def test_check_signal_stop_loss_too_small(mock_data_service):
    """测试止损幅度过小被拒绝"""
    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        'quantity': 100,
        'risk_management': {
            'stop_loss': {'percent': 1.0}  # 小于最小值3%
        }
    }

    result = service.check_signal(signal)

    assert result['passed'] is False
    assert '止损幅度过小' in result['reason']


def test_check_signal_stop_loss_too_large(mock_data_service):
    """测试止损幅度过大被拒绝"""
    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        'quantity': 100,
        'risk_management': {
            'stop_loss': {'percent': 20.0}  # 大于最大值15%
        }
    }

    result = service.check_signal(signal)

    assert result['passed'] is False
    assert '止损幅度过大' in result['reason']


def test_check_single_order_limit(mock_data_service):
    """测试单笔订单限制"""
    service = RiskCheckService(mock_data_service)

    # 订单金额超过总资产的20%
    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        'quantity': 200,  # 200 * 1500 = 300000 > 1000000 * 20% = 200000
        'risk_management': {
            'stop_loss': {'percent': 5.0}
        }
    }

    result = service.check_signal(signal)

    assert result['passed'] is False
    assert '单笔订单超限' in result['reason']


def test_check_position_concentration(mock_data_service):
    """测试仓位集中度检查"""
    # Mock已有持仓
    mock_data_service.portfolio.get_holding = Mock(return_value={
        'symbol': '000001.SH',
        'quantity': 180  # 180 * 1500 = 270000 = 27%
    })

    service = RiskCheckService(mock_data_service)

    # 新增20股，总仓位 = (180+20)*1500 = 300000 = 30% of 1000000
    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        'quantity': 20,
        'risk_management': {
            'stop_loss': {'percent': 5.0}
        }
    }

    result = service.check_signal(signal)

    # 应该通过，但有警告（正好30%上限，超过80%阈值）
    assert result['passed'] is True
    assert len(result['warnings']) > 0


def test_check_sector_concentration(mock_data_service):
    """测试行业集中度检查"""
    # Mock同行业持仓
    mock_data_service.portfolio.get_all_holdings = Mock(return_value=[
        {'symbol': '000858.SZ', 'quantity': 200}  # 五粮液，白酒行业
    ])

    # Mock五粮液信息
    def get_stock_by_symbol(symbol):
        if symbol == '000001.SH':
            return {'symbol': '000001.SH', 'name': '浦发银行', 'industry': '白酒'}
        elif symbol == '000858.SZ':
            return {'symbol': '000858.SZ', 'name': '五粮液', 'industry': '白酒'}
        return None

    mock_data_service.stock.get_by_symbol = Mock(side_effect=get_stock_by_symbol)

    # Mock五粮液K线
    def get_kline(symbol):
        if symbol == '000001.SH':
            return {'symbol': '000001.SH', 'close': 1500.0}
        elif symbol == '000858.SZ':
            return {'symbol': '000858.SZ', 'close': 1000.0}
        return None

    mock_data_service.kline.get_latest_daily_kline = Mock(side_effect=get_kline)

    service = RiskCheckService(mock_data_service)

    # 现有白酒仓位 = 200 * 1000 = 200000 = 20%
    # 新增后 = 200000 + 50*1500 = 275000 = 27.5%，未超过40%
    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        'quantity': 50,
        'risk_management': {
            'stop_loss': {'percent': 5.0}
        }
    }

    result = service.check_signal(signal)

    assert result['passed'] is True
    assert 'sector_concentration' in result['checks']


def test_check_daily_trade_limit(mock_data_service):
    """测试日内交易次数限制"""
    # Mock今日已有5笔交易
    mock_cursor = Mock()
    mock_cursor.fetchall = Mock(return_value=[1, 2, 3, 4, 5])
    mock_data_service.portfolio.db.cursor = Mock(return_value=mock_cursor)

    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        'quantity': 100,
        'risk_management': {
            'stop_loss': {'percent': 5.0}
        }
    }

    result = service.check_signal(signal)

    assert result['passed'] is False
    assert '日内交易次数超限' in result['reason']


def test_calculate_quantity_with_position_sizing(mock_data_service):
    """测试根据仓位管理计算数量"""
    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'buy',
        # 不指定quantity，使用position_sizing
        'risk_management': {
            'position_sizing': {'percent': 10.0},  # 10% of 1000000 = 100000
            'stop_loss': {'percent': 5.0}
        }
    }

    result = service.check_signal(signal)

    assert result['passed'] is True
    # 100000 / 1500 = 66.67, 向下取整到100的倍数 = 0, max(100, 0) = 100
    assert result['quantity'] == 100
    assert result['quantity'] % 100 == 0


def test_calculate_sell_quantity_all(mock_data_service):
    """测试卖出全部持仓"""
    # Mock持仓
    mock_data_service.portfolio.get_holding = Mock(return_value={
        'symbol': '000001.SH',
        'quantity': 500
    })

    service = RiskCheckService(mock_data_service)

    signal = {
        'symbol': '000001.SH',
        'action': 'sell'
        # 不指定quantity，卖出全部
    }

    result = service.check_signal(signal)

    assert result['passed'] is True
    assert result['quantity'] == 500
