# tests/test_diagnosis_service.py
import pytest
from application.services.diagnosis_service import DiagnosisService
from unittest.mock import Mock, patch

def test_run_diagnosis():
    """测试运行完整诊断"""
    service = DiagnosisService()

    params = {
        'symbol': '000001.SZ',
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'strategy_name': 'ma_cross',
        'benchmark': '000300.SH'
    }

    # Mock 回测数据
    backtest_data = {
        'annualReturn': 0.15,
        'sharpeRatio': 1.2,
        'maxDrawdown': -0.18,
        'winRate': 0.55,
        'totalTrades': 24
    }

    with patch.object(service, '_get_backtest_data', return_value=backtest_data):
        with patch.object(service, '_get_benchmark_data', return_value={
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        }):
            result = service.run_diagnosis(params)

    assert 'diagnosisId' in result
    assert 'timestamp' in result
    assert 'metrics' in result
    assert 'benchmark' in result
    assert 'ratings' in result
    assert 'diagnosis' in result
    assert 'reportPath' in result

    assert result['ratings']['overall'] in ['A', 'B', 'C', 'D']
    assert result['metrics']['sharpeRatio'] == 1.2


def test_run_diagnosis_missing_required_params():
    """测试缺少必填参数"""
    service = DiagnosisService()

    # 缺少 symbol
    with pytest.raises(ValueError, match="缺少必填参数: symbol"):
        service.run_diagnosis({
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'strategy_name': 'ma_cross'
        })

    # 缺少 start_date
    with pytest.raises(ValueError, match="缺少必填参数: start_date"):
        service.run_diagnosis({
            'symbol': '000001.SZ',
            'end_date': '2024-12-31',
            'strategy_name': 'ma_cross'
        })

    # 缺少 end_date
    with pytest.raises(ValueError, match="缺少必填参数: end_date"):
        service.run_diagnosis({
            'symbol': '000001.SZ',
            'start_date': '2024-01-01',
            'strategy_name': 'ma_cross'
        })

    # 缺少 strategy_name
    with pytest.raises(ValueError, match="缺少必填参数: strategy_name"):
        service.run_diagnosis({
            'symbol': '000001.SZ',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })


def test_run_diagnosis_invalid_date_format():
    """测试无效的日期格式"""
    service = DiagnosisService()

    params = {
        'symbol': '000001.SZ',
        'start_date': 'invalid-date',
        'end_date': '2024-12-31',
        'strategy_name': 'ma_cross'
    }

    with pytest.raises(ValueError, match="日期格式无效"):
        service.run_diagnosis(params)


def test_run_diagnosis_end_date_before_start_date():
    """测试结束日期早于开始日期"""
    service = DiagnosisService()

    params = {
        'symbol': '000001.SZ',
        'start_date': '2024-12-31',
        'end_date': '2024-01-01',
        'strategy_name': 'ma_cross'
    }

    with pytest.raises(ValueError, match="结束日期必须晚于开始日期"):
        service.run_diagnosis(params)


def test_run_diagnosis_empty_symbol():
    """测试空股票代码"""
    service = DiagnosisService()

    params = {
        'symbol': '',
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'strategy_name': 'ma_cross'
    }

    with pytest.raises(ValueError, match="股票代码不能为空"):
        service.run_diagnosis(params)


def test_run_diagnosis_empty_strategy_name():
    """测试空策略名称"""
    service = DiagnosisService()

    params = {
        'symbol': '000001.SZ',
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'strategy_name': ''
    }

    with pytest.raises(ValueError, match="策略名称不能为空"):
        service.run_diagnosis(params)


def test_get_backtest_data_missing_id():
    """测试缺少回测ID"""
    service = DiagnosisService()

    params = {
        'symbol': '000001.SZ',
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'strategy_name': 'ma_cross'
    }

    with pytest.raises(ValueError, match="backtestId is required"):
        service._get_backtest_data(params)


def test_get_backtest_data_not_found():
    """测试回测结果不存在"""
    service = DiagnosisService()

    params = {'backtestId': 99999}

    with patch.object(service.backtest_repo, 'get_backtest', return_value=None):
        with pytest.raises(ValueError, match="Backtest not found: 99999"):
            service._get_backtest_data(params)


def test_calculate_returns_normal():
    """测试正常收益率计算"""
    service = DiagnosisService()

    klines = [
        {'close': 100.0},
        {'close': 110.0},
        {'close': 120.0}
    ]

    returns = service._calculate_returns(klines)
    # 3天数据，总收益20%，年化 = (1.2)^(252/3) - 1
    assert returns > 0


def test_calculate_returns_empty_klines():
    """测试空K线数据"""
    service = DiagnosisService()

    assert service._calculate_returns([]) == 0.0
    assert service._calculate_returns(None) == 0.0


def test_calculate_returns_single_kline():
    """测试单条K线数据"""
    service = DiagnosisService()

    klines = [{'close': 100.0}]
    assert service._calculate_returns(klines) == 0.0


def test_calculate_returns_zero_start_price():
    """测试起始价格为0"""
    service = DiagnosisService()

    klines = [
        {'close': 0.0},
        {'close': 100.0}
    ]

    assert service._calculate_returns(klines) == 0.0


def test_calculate_returns_negative_total_return():
    """测试负收益率（亏损超过100%）"""
    service = DiagnosisService()

    klines = [
        {'close': 100.0},
        {'close': 0.01}  # 亏损99.99%
    ]

    returns = service._calculate_returns(klines)
    assert returns < 0


def test_calculate_sharpe_ratio_positive_returns():
    """测试正收益的夏普比率"""
    service = DiagnosisService()

    sharpe = service._calculate_sharpe_ratio(0.15)
    assert sharpe > 0


def test_calculate_sharpe_ratio_negative_returns():
    """测试负收益的夏普比率"""
    service = DiagnosisService()

    sharpe = service._calculate_sharpe_ratio(-0.10)
    assert sharpe < 0


def test_calculate_sharpe_ratio_zero_returns():
    """测试零收益的夏普比率"""
    service = DiagnosisService()

    sharpe = service._calculate_sharpe_ratio(0.0)
    assert sharpe < 0  # (0 - 0.03) / 0.1 = -0.3


def test_calculate_max_drawdown_normal():
    """测试正常最大回撤计算"""
    service = DiagnosisService()

    klines = [
        {'close': 100.0},
        {'close': 120.0},  # 新高
        {'close': 90.0},   # 回撤 (90-120)/120 = -25%
        {'close': 110.0}
    ]

    max_dd = service._calculate_max_drawdown(klines)
    assert max_dd == pytest.approx(-0.25, rel=1e-5)


def test_calculate_max_drawdown_no_drawdown():
    """测试无回撤（持续上涨）"""
    service = DiagnosisService()

    klines = [
        {'close': 100.0},
        {'close': 110.0},
        {'close': 120.0}
    ]

    max_dd = service._calculate_max_drawdown(klines)
    assert max_dd == 0.0


def test_calculate_max_drawdown_empty_klines():
    """测试空K线数据"""
    service = DiagnosisService()

    assert service._calculate_max_drawdown([]) == 0.0
    assert service._calculate_max_drawdown(None) == 0.0


def test_get_benchmark_data_fallback():
    """测试基准数据获取失败时的降级"""
    service = DiagnosisService()

    with patch.object(service.kline_repo, 'get_daily_klines', return_value=[]):
        result = service._get_benchmark_data('000300.SH', '2024-01-01', '2024-12-31')

    assert result['symbol'] == '000300.SH'
    assert result['name'] == '沪深300'
    assert result['annualReturn'] == 0.08
    assert result['sharpeRatio'] == 0.6
    assert result['maxDrawdown'] == -0.25


def test_get_benchmark_data_exception():
    """测试基准数据获取异常"""
    service = DiagnosisService()

    with patch.object(service.kline_repo, 'get_daily_klines', side_effect=Exception("DB error")):
        result = service._get_benchmark_data('000300.SH', '2024-01-01', '2024-12-31')

    # 应该返回默认值
    assert result['symbol'] == '000300.SH'
    assert result['annualReturn'] == 0.08


def test_get_index_name():
    """测试指数名称映射"""
    service = DiagnosisService()

    assert service._get_index_name('000300.SH') == '沪深300'
    assert service._get_index_name('000001.SH') == '上证指数'
    assert service._get_index_name('399001.SZ') == '深证成指'
    assert service._get_index_name('399006.SZ') == '创业板指'
    assert service._get_index_name('unknown') == 'unknown'


def test_generate_id_format():
    """测试诊断ID格式"""
    service = DiagnosisService()

    diagnosis_id = service._generate_id()

    # 格式: diag_YYYYMMDD_xxxxxxxx
    assert diagnosis_id.startswith('diag_')
    parts = diagnosis_id.split('_')
    assert len(parts) == 3
    assert len(parts[1]) == 8  # YYYYMMDD
    assert len(parts[2]) == 8  # UUID前8位
    assert parts[1].isdigit()


def test_get_default_benchmark():
    """测试默认基准数据"""
    service = DiagnosisService()

    result = service._get_default_benchmark()

    assert result['symbol'] == '000300.SH'
    assert result['name'] == '沪深300'
    assert result['annualReturn'] == 0.08
    assert result['sharpeRatio'] == 0.6
    assert result['maxDrawdown'] == -0.25
