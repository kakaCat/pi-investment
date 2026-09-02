"""
Tests for OpportunityScoringService
"""
import pytest
from datetime import datetime, timedelta
from application.services.opportunity_scoring_service import OpportunityScoringService
from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.repositories import StockORMRepository
from adapters.outbound.repositories.financial_repository import FinancialORMRepository
from adapters.outbound.repositories.fund_flow_repository import FundFlowORMRepository
from adapters.shared.services import get_factor_adapter


@pytest.fixture
def scoring_service(db_connection):
    """Create scoring service with repositories"""
    kline_repo = KlineORMRepository()
    kline_repo.db = db_connection
    stock_repo = StockORMRepository()
    stock_repo.db = db_connection
    financial_repo = FinancialORMRepository()
    financial_repo.db = db_connection
    fund_flow_repo = FundFlowORMRepository()
    fund_flow_repo.db = db_connection
    factor_adapter = get_factor_adapter()
    return OpportunityScoringService(
        kline_repo,
        stock_repo,
        factor_adapter,
        financial_repo=financial_repo,
        fund_flow_repo=fund_flow_repo,
    )


def test_score_stocks_basic(scoring_service, db_connection):
    """测试基本评分功能"""
    symbols = ['999991', '999992']

    # 先插入股票基础数据，避免外键约束失败
    cursor = db_connection.cursor()
    for symbol in symbols:
        cursor.execute(
            "INSERT INTO quant.stocks (symbol, name, market) VALUES (%s, %s, %s) ON CONFLICT (symbol) DO NOTHING",
            (symbol, 'Test', 'A')
        )
    db_connection.commit()
    cursor.close()

    # 插入测试K线数据
    for symbol in symbols:
        for i in range(120):
            date = (datetime.now() - timedelta(days=120-i-1)).strftime('%Y-%m-%d')
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO quant.daily_klines
                (symbol, trade_date, open, high, low, close, volume)
                VALUES (%s, %s, 100, 105, 95, 102, 1000000)
                ON CONFLICT (symbol, trade_date) DO NOTHING
            """, (symbol, date))
            db_connection.commit()
            cursor.close()

    # 执行评分
    filters = {
        'technical': ['rsi_oversold'],
        'fundamental': []
    }
    results = scoring_service.score_stocks(symbols, filters)

    # 验证结果
    assert isinstance(results, list)
    assert len(results) <= len(symbols)
    for opp in results:
        assert 'symbol' in opp
        assert 'score' in opp
        assert 'technical_score' in opp
        assert 'fundamental_score' in opp
        assert 'capital_score' in opp
        assert 0 <= opp['score'] <= 100


def test_calculate_technical_score_rsi_oversold(scoring_service):
    """测试RSI超卖技术面评分"""
    # RSI超卖场景
    factors = {'rsi': 25}
    score = scoring_service._calculate_technical_score(factors, ['rsi_oversold'])
    assert score == 25

    # RSI不超卖
    factors = {'rsi': 50}
    score = scoring_service._calculate_technical_score(factors, ['rsi_oversold'])
    assert score == 0


def test_calculate_technical_score_macd_golden_cross(scoring_service):
    """测试MACD金叉技术面评分"""
    # MACD金叉场景
    factors = {
        'macd': 0.5,
        'macd_signal': 0.3,
        'macd_prev': 0.2,
        'macd_signal_prev': 0.4
    }
    score = scoring_service._calculate_technical_score(factors, ['macd_golden_cross'])
    assert score == 25

    # 非金叉场景
    factors = {
        'macd': 0.3,
        'macd_signal': 0.5,
        'macd_prev': 0.2,
        'macd_signal_prev': 0.4
    }
    score = scoring_service._calculate_technical_score(factors, ['macd_golden_cross'])
    assert score == 0


def test_calculate_technical_score_bollinger_breakout(scoring_service):
    """测试布林带突破技术面评分"""
    # 突破上轨
    factors = {'close': 105, 'boll_upper': 100}
    score = scoring_service._calculate_technical_score(factors, ['bollinger_breakout'])
    assert score == 25

    # 未突破
    factors = {'close': 95, 'boll_upper': 100}
    score = scoring_service._calculate_technical_score(factors, ['bollinger_breakout'])
    assert score == 0


def test_calculate_technical_score_volume_surge(scoring_service):
    """测试成交量放大技术面评分"""
    # 成交量放大
    factors = {'volume_ratio_5d': 2.5}
    score = scoring_service._calculate_technical_score(factors, ['volume_surge'])
    assert score == 25

    # 成交量未放大
    factors = {'volume_ratio_5d': 1.5}
    score = scoring_service._calculate_technical_score(factors, ['volume_surge'])
    assert score == 0


def test_calculate_technical_score_no_conditions(scoring_service):
    """测试无技术条件时返回默认技术面评分"""
    factors = {'rsi': 25}
    score = scoring_service._calculate_technical_score(factors, [])
    assert score == 65.0


def test_calculate_technical_score_multiple_conditions(scoring_service):
    """测试多个技术条件同时满足"""
    factors = {
        'rsi': 25,
        'macd': 0.5,
        'macd_signal': 0.3,
        'macd_prev': 0.2,
        'macd_signal_prev': 0.4,
        'close': 105,
        'boll_upper': 100,
        'volume_ratio_5d': 2.5
    }
    score = scoring_service._calculate_technical_score(
        factors,
        ['rsi_oversold', 'macd_golden_cross', 'bollinger_breakout', 'volume_surge']
    )
    assert score == 100


def test_calculate_fundamental_score_pe_low(scoring_service):
    """测试PE低基本面评分"""
    # PE低
    fundamental = {'pe': 25}
    score = scoring_service._calculate_fundamental_score(fundamental, ['pe_low'])
    assert score == 25

    # PE高
    fundamental = {'pe': 50}
    score = scoring_service._calculate_fundamental_score(fundamental, ['pe_low'])
    assert score == 0


def test_calculate_fundamental_score_roe_high(scoring_service):
    """测试ROE高基本面评分"""
    # ROE高
    fundamental = {'roe': 20}
    score = scoring_service._calculate_fundamental_score(fundamental, ['roe_high'])
    assert score == 25

    # ROE低
    fundamental = {'roe': 10}
    score = scoring_service._calculate_fundamental_score(fundamental, ['roe_high'])
    assert score == 0


def test_calculate_fundamental_score_gross_margin_high(scoring_service):
    """测试毛利率高基本面评分"""
    # 毛利率高
    fundamental = {'gross_margin': 35}
    score = scoring_service._calculate_fundamental_score(fundamental, ['gross_margin_high'])
    assert score == 25

    # 毛利率低
    fundamental = {'gross_margin': 20}
    score = scoring_service._calculate_fundamental_score(fundamental, ['gross_margin_high'])
    assert score == 0


def test_calculate_fundamental_score_debt_ratio_low(scoring_service):
    """测试负债率低基本面评分"""
    # 负债率低
    fundamental = {'debt_ratio': 30}
    score = scoring_service._calculate_fundamental_score(fundamental, ['debt_ratio_low'])
    assert score == 25

    # 负债率高
    fundamental = {'debt_ratio': 60}
    score = scoring_service._calculate_fundamental_score(fundamental, ['debt_ratio_low'])
    assert score == 0


def test_calculate_fundamental_score_no_data(scoring_service):
    """测试无基本面数据时返回中性评分"""
    score = scoring_service._calculate_fundamental_score(None, ['pe_low'])
    assert score == 50


def test_calculate_fundamental_score_no_conditions(scoring_service):
    """测试无基本面条件时返回默认基本面评分"""
    fundamental = {'pe': 25}
    score = scoring_service._calculate_fundamental_score(fundamental, [])
    assert score == 58.0


def test_calculate_capital_score(scoring_service):
    """测试资金面评分"""
    # 所有条件满足
    factors = {
        'volume_ratio_5d': 1.6,
        'volume': 2000000,
        'volume_ma20': 1500000,
        'volume_ma5': 1800000,
        'volume_history': [1000000, 1200000, 1500000]
    }
    score = scoring_service._calculate_capital_score(factors)
    assert score == 91.0

    # 部分条件满足
    factors = {
        'volume_ratio_5d': 1.6,
        'volume': 1000000,
        'volume_ma20': 1500000,
        'volume_ma5': 1400000,
        'volume_history': [1500000, 1200000, 1000000]
    }
    score = scoring_service._calculate_capital_score(factors)
    assert score == 46.0


def test_calculate_comprehensive_score(scoring_service):
    """测试综合评分计算"""
    tech_score = 80
    fund_score = 60
    capital_score = 40

    # 综合评分 = 技术面×0.5 + 基本面×0.3 + 资金面×0.2
    expected = 80 * 0.5 + 60 * 0.3 + 40 * 0.2

    result = scoring_service._calculate_comprehensive_score(tech_score, fund_score, capital_score)
    assert result == expected


def test_calculate_risk_level(scoring_service):
    """测试风险等级计算"""
    assert scoring_service._calculate_risk_level(75) == 'low'
    assert scoring_service._calculate_risk_level(70) == 'low'
    assert scoring_service._calculate_risk_level(60) == 'medium'
    assert scoring_service._calculate_risk_level(50) == 'medium'
    assert scoring_service._calculate_risk_level(40) == 'high'
    assert scoring_service._calculate_risk_level(30) == 'high'


def test_is_macd_golden_cross(scoring_service):
    """测试MACD金叉判断"""
    # 金叉
    factors = {
        'macd': 0.5,
        'macd_signal': 0.3,
        'macd_prev': 0.2,
        'macd_signal_prev': 0.4
    }
    assert scoring_service._is_macd_golden_cross(factors) is True

    # 死叉
    factors = {
        'macd': 0.3,
        'macd_signal': 0.5,
        'macd_prev': 0.4,
        'macd_signal_prev': 0.2
    }
    assert scoring_service._is_macd_golden_cross(factors) is False


def test_is_volume_increasing(scoring_service):
    """测试成交量连续递增判断"""
    # 连续递增
    factors = {'volume_history': [1000000, 1200000, 1500000]}
    assert scoring_service._is_volume_increasing(factors, days=3) is True

    # 非连续递增
    factors = {'volume_history': [1500000, 1200000, 1000000]}
    assert scoring_service._is_volume_increasing(factors, days=3) is False

    # 数据不足
    factors = {'volume_history': [1000000, 1200000]}
    assert scoring_service._is_volume_increasing(factors, days=3) is False


def test_score_stocks_with_insufficient_klines(scoring_service, db_connection):
    """测试K线数据不足时的处理 - 被数据质量门跳过"""
    symbols = ['999990']

    # 先插入股票基础数据，避免外键约束失败
    cursor = db_connection.cursor()
    cursor.execute(
        "INSERT INTO quant.stocks (symbol, name, market) VALUES (%s, %s, %s) ON CONFLICT (symbol) DO NOTHING",
        (symbols[0], 'Test', 'A')
    )
    db_connection.commit()
    cursor.close()

    # 只插入5天数据（不足以满足质量门最低120根的要求）
    for i in range(5):
        date = (datetime.now() - timedelta(days=5-i-1)).strftime('%Y-%m-%d')
        cursor = db_connection.cursor()
        cursor.execute("""
            INSERT INTO quant.daily_klines
            (symbol, trade_date, open, high, low, close, volume)
            VALUES (%s, %s, 100, 105, 95, 102, 1000000)
            ON CONFLICT (symbol, trade_date) DO NOTHING
        """, (symbols[0], date))
        db_connection.commit()
        cursor.close()

    filters = {'technical': [], 'fundamental': []}
    results = scoring_service.score_stocks(symbols, filters)

    # 数据不足应被跳过
    assert len(results) == 0
    assert scoring_service.last_diagnostics['skipped_insufficient_klines'] == 1


def test_score_stocks_parallel_processing(scoring_service, db_connection):
    """测试并行处理多只股票"""
    symbols = [f'99{i:04d}' for i in range(10)]

    # 先插入股票基础数据，避免外键约束失败
    cursor = db_connection.cursor()
    for symbol in symbols:
        cursor.execute(
            "INSERT INTO quant.stocks (symbol, name, market) VALUES (%s, %s, %s) ON CONFLICT (symbol) DO NOTHING",
            (symbol, 'Test', 'A')
        )
    db_connection.commit()
    cursor.close()

    # 插入测试数据
    for symbol in symbols:
        for i in range(120):
            date = (datetime.now() - timedelta(days=120-i-1)).strftime('%Y-%m-%d')
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO quant.daily_klines
                (symbol, trade_date, open, high, low, close, volume)
                VALUES (%s, %s, 100, 105, 95, 102, 1000000)
                ON CONFLICT (symbol, trade_date) DO NOTHING
            """, (symbol, date))
            db_connection.commit()
            cursor.close()

    filters = {'technical': [], 'fundamental': []}
    results = scoring_service.score_stocks(symbols, filters)

    # 应该返回所有股票的评分
    assert len(results) == len(symbols)
    assert all('symbol' in r for r in results)


def test_evaluate_conditions_and_logic():
    """Test AND logic with all conditions met"""
    service = OpportunityScoringService(None, None, None)

    conditions = [
        {"field": "roe", "operator": ">=", "value": 15},
        {"field": "debt_ratio", "operator": "<=", "value": 50}
    ]
    stock_data = {"roe": 20, "debt_ratio": 40}
    factors = {}

    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is True


def test_evaluate_conditions_and_logic_fail():
    """Test AND logic with one condition not met"""
    service = OpportunityScoringService(None, None, None)

    conditions = [
        {"field": "roe", "operator": ">=", "value": 15},
        {"field": "debt_ratio", "operator": "<=", "value": 50}
    ]
    stock_data = {"roe": 10, "debt_ratio": 40}  # roe too low
    factors = {}

    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is False


def test_evaluate_conditions_or_logic():
    """Test OR logic with one condition met"""
    service = OpportunityScoringService(None, None, None)

    conditions = [
        {"field": "roe", "operator": ">=", "value": 15},
        {"field": "pe", "operator": "<=", "value": 10}
    ]
    stock_data = {"roe": 20, "pe": 50}  # only roe meets condition
    factors = {}

    result = service._evaluate_conditions(conditions, "OR", stock_data, factors)
    assert result is True


def test_evaluate_conditions_missing_field():
    """Test with missing field returns False"""
    service = OpportunityScoringService(None, None, None)

    conditions = [{"field": "roe", "operator": ">=", "value": 15}]
    stock_data = {}  # missing roe
    factors = {}

    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is False


def test_evaluate_conditions_from_factors():
    """Test reading field from factors dict"""
    service = OpportunityScoringService(None, None, None)

    conditions = [{"field": "rsi", "operator": "<=", "value": 30}]
    stock_data = {}
    factors = {"rsi": 25}

    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is True


def test_adx_factor_calculated():
    """测试 ADX 因子被正确计算（需要 TA-Lib）"""
    try:
        import talib
    except ImportError:
        pytest.skip("TA-Lib not available")
    
    from adapters.shared.services import get_factor_adapter
    
    service = OpportunityScoringService(None, None, get_factor_adapter())
    
    # 生成模拟 K 线数据
    klines = []
    for i in range(120):
        klines.append({
            'date': f'2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
            'open': 100 + i * 0.1,
            'high': 102 + i * 0.1,
            'low': 98 + i * 0.1,
            'close': 101 + i * 0.1,
            'volume': 1000000 + i * 10000
        })
    
    factors = service._calculate_factors(klines)
    
    # 验证 ADX 被计算
    assert 'adx' in factors
    assert isinstance(factors['adx'], (int, float))
    assert 0 <= factors['adx'] <= 100


def test_technical_scorer_integration():
    """测试 TechnicalScorer 集成到 OpportunityScoringService"""
    from adapters.shared.services import get_factor_adapter
    
    service = OpportunityScoringService(None, None, get_factor_adapter())
    
    # 验证 TechnicalScorer 已初始化
    assert hasattr(service, 'technical_scorer')
    assert service.technical_scorer is not None
    
    # 准备测试数据
    factors = {
        'rsi': 25,
        'macd': 0.5,
        'macd_signal': 0.3,
        'macd_prev': 0.2,
        'macd_signal_prev': 0.4,
        'adx': 30,
        'volume_ratio_5d': 1.8,
    }
    
    # 测试评分
    result = service.technical_scorer.score(factors)
    
    # 验证返回结构
    assert 'total' in result
    assert 'breakdown' in result
    assert 0 <= result['total'] <= 100
    
    # 验证包含 ADX 评分
    assert 'adx' in result['breakdown']


def test_fundamental_scorer_integration():
    """测试 FundamentalScorer 集成到 OpportunityScoringService"""
    from adapters.shared.services import get_factor_adapter
    
    service = OpportunityScoringService(None, None, get_factor_adapter())
    
    # 验证 FundamentalScorer 已初始化
    assert hasattr(service, 'fundamental_scorer')
    assert service.fundamental_scorer is not None
    
    # 准备测试数据
    fundamental = {
        'pe': 15,
        'roe': 18,
        'gross_margin': 30,
        'debt_ratio': 35,
        'revenue_growth': 20
    }
    
    # 测试评分
    result = service.fundamental_scorer.score(fundamental)
    
    # 验证返回结构
    assert 'total' in result
    assert 'breakdown' in result
    assert 0 <= result['total'] <= 100
    
    # 验证包含所有维度评分
    expected_keys = ['base', 'pe', 'roe', 'gross_margin', 'debt_ratio', 'revenue_growth', 'resonance']
    for key in expected_keys:
        assert key in result['breakdown']
