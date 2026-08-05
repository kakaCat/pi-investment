"""
机会雷达集成测试

测试完整的扫描流程：API端点 → 服务层 → 数据库
"""
import pytest
import time
from datetime import datetime, timedelta
from adapters.inbound.api.server import app
from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.repositories import StockORMRepository
from application.services.stock_pool_service import StockPoolService
from application.services.opportunity_scoring_service import OpportunityScoringService


class TestOpportunityRadarIntegration:
    """机会雷达集成测试"""

    @pytest.fixture
    def client(self, db_connection):
        """Flask测试客户端"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def kline_repo(self):
        """K线数据仓库"""
        return KlineORMRepository()

    @pytest.fixture
    def stock_repo(self):
        """股票数据仓库"""
        return StockORMRepository()

    @pytest.fixture
    def test_stocks(self):
        """测试用股票代码"""
        return ['600000.SH', '000001.SZ', '600036.SH']  # 归一后不撞键（000001.SH/SZ 归一均为 000001）

    @pytest.fixture
    def setup_test_data(self, db_connection, test_stocks):
        """设置测试数据"""
        cursor = db_connection.cursor()

        # 清理旧数据
        bare = [s.split('.')[0] for s in test_stocks]  # 数据库统一无后缀
        cursor.execute("DELETE FROM quant.daily_klines WHERE symbol = ANY(%s)", (bare,))
        cursor.execute("DELETE FROM quant.stock_fundamentals WHERE symbol = ANY(%s)", (bare,))
        cursor.execute("DELETE FROM quant.index_constituents WHERE constituent_symbol = ANY(%s)", (bare,))
        db_connection.commit()

        # 插入120天K线数据
        end_date = datetime.now()
        for symbol in bare:
            for i in range(120):
                trade_date = end_date - timedelta(days=i)
                # 生成模拟价格数据（带趋势）
                base_price = 100.0
                trend = (120 - i) * 0.1  # 上升趋势
                close = base_price + trend + (i % 10) * 0.5
                open_price = close - 0.5
                high = close + 1.0
                low = close - 1.0
                volume = 1000000 + (i % 20) * 50000

                cursor.execute("""
                    INSERT INTO quant.daily_klines
                    (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, trade_date) DO NOTHING
                """, (
                    symbol, trade_date.strftime('%Y-%m-%d'),
                    open_price, high, low, close,
                    volume, volume * close, 1.5
                ))

        # 插入基本面数据
        for symbol in bare:
            cursor.execute("""
                INSERT INTO quant.stock_fundamentals
                (symbol, pe_ratio, roe, gross_margin, debt_ratio, update_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    pe_ratio = EXCLUDED.pe_ratio,
                    roe = EXCLUDED.roe,
                    gross_margin = EXCLUDED.gross_margin,
                    debt_ratio = EXCLUDED.debt_ratio,
                    update_time = EXCLUDED.update_time
            """, (
                symbol, 15.5, 18.2, 45.3, 35.0,
                datetime.now().strftime('%Y-%m-%d')
            ))

        # 插入指数成分股数据（模拟热门股票池）
        for symbol in bare:
            cursor.execute("""
                INSERT INTO quant.index_constituents
                (index_code, constituent_symbol, weight, update_time)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (index_code, constituent_symbol) DO NOTHING
            """, ('000300.SH', symbol, 1.0, datetime.now()))

        db_connection.commit()

        yield

        # 清理测试数据
        bare = [s.split('.')[0] for s in test_stocks]  # 数据库统一无后缀
        cursor.execute("DELETE FROM quant.daily_klines WHERE symbol = ANY(%s)", (bare,))
        cursor.execute("DELETE FROM quant.stock_fundamentals WHERE symbol = ANY(%s)", (bare,))
        cursor.execute("DELETE FROM quant.index_constituents WHERE constituent_symbol = ANY(%s)", (bare,))
        db_connection.commit()
        cursor.close()

    def test_end_to_end_scan(self, client, setup_test_data, test_stocks):
        """测试完整扫描流程"""
        # 调用扫描端点
        response = client.post('/api/signals/scan', json={
            'stocks': test_stocks,
            'minScore': 0,
            'maxRiskLevel': 'high',
            'technical': [],
            'fundamental': []
        })

        # 验证响应状态
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # 验证响应结构
        data = response.get_json()
        assert data is not None, "Response data is None"
        assert 'success' in data, "Missing 'success' field"
        assert data['success'] is True, f"Scan failed: {data.get('error', 'Unknown error')}"
        assert 'opportunities' in data, "Missing 'opportunities' field"
        assert 'total' in data, "Missing 'total' field"
        assert 'scanned' in data, "Missing 'scanned' field"

        # 验证扫描了正确数量的股票
        assert data['scanned'] == len(test_stocks), \
            f"Expected to scan {len(test_stocks)} stocks, got {data['scanned']}"

        # 验证返回了机会
        opportunities = data['opportunities']
        assert len(opportunities) > 0, "No opportunities returned"

        # 验证每个机会的结构
        for opp in opportunities:
            assert 'symbol' in opp, "Missing 'symbol' field"
            assert 'name' in opp, "Missing 'name' field"
            assert 'score' in opp, "Missing 'score' field"
            assert 'technical_score' in opp, "Missing 'technical_score' field"
            assert 'fundamental_score' in opp, "Missing 'fundamental_score' field"
            assert 'capital_score' in opp, "Missing 'capital_score' field"
            assert 'confidence' in opp, "Missing 'confidence' field"
            assert 'risk_level' in opp, "Missing 'risk_level' field"
            assert 'signal_type' in opp, "Missing 'signal_type' field"
            assert 'timestamp' in opp, "Missing 'timestamp' field"

            # 验证评分范围
            assert 0 <= opp['score'] <= 100, f"Score out of range: {opp['score']}"
            assert 0 <= opp['technical_score'] <= 100, \
                f"Technical score out of range: {opp['technical_score']}"
            assert 0 <= opp['fundamental_score'] <= 100, \
                f"Fundamental score out of range: {opp['fundamental_score']}"
            assert 0 <= opp['capital_score'] <= 100, \
                f"Capital score out of range: {opp['capital_score']}"
            assert 0 <= opp['confidence'] <= 1, \
                f"Confidence out of range: {opp['confidence']}"
            assert opp['risk_level'] in ['low', 'medium', 'high'], \
                f"Invalid risk level: {opp['risk_level']}"

    def test_real_data_scoring(self, client, setup_test_data, test_stocks):
        """测试真实数据评分计算"""
        # 调用扫描端点
        response = client.post('/api/signals/scan', json={
            'stocks': test_stocks,
            'minScore': 0,
            'maxRiskLevel': 'high',
            'technical': ['rsi_oversold'],  # RSI超卖
            'fundamental': ['low_pe']  # 低市盈率
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        opportunities = data['opportunities']
        assert len(opportunities) > 0, "No opportunities returned with filters"

        # 验证评分逻辑
        for opp in opportunities:
            # 综合评分应该是技术面、基本面、资金面的加权平均
            # 权重：技术面50%、基本面30%、资金面20%
            expected_score = (
                opp['technical_score'] * 0.5 +
                opp['fundamental_score'] * 0.3 +
                opp['capital_score'] * 0.2
            )
            # 允许1分的误差（四舍五入）
            assert abs(opp['score'] - expected_score) <= 1, \
                f"Score calculation mismatch for {opp['symbol']}: " \
                f"expected ~{expected_score:.1f}, got {opp['score']}"

    def test_performance_400_stocks(self, client, db_connection):
        """测试400只股票扫描性能"""
        # 生成400只测试股票
        test_symbols = []
        for i in range(400):
            if i < 200:
                symbol = f"{600000 + i}.SH"
            else:
                symbol = f"{i - 200:06d}.SZ"
            test_symbols.append(symbol)

        cursor = db_connection.cursor()

        try:
            # 插入测试数据（130 天，满足 DataQualityGate.MIN_KLINES=120）
            end_date = datetime.now()
            for symbol in [s_.split('.')[0] for s_ in test_symbols]:  # 数据库统一无后缀
                for i in range(130):
                    trade_date = end_date - timedelta(days=i)
                    cursor.execute("""
                        INSERT INTO quant.daily_klines
                        (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, trade_date) DO NOTHING
                    """, (
                        symbol, trade_date.strftime('%Y-%m-%d'),
                        100.0, 101.0, 99.0, 100.5,
                        1000000, 100500000, 1.5
                    ))

            db_connection.commit()

            # 测量扫描时间
            start_time = time.time()
            response = client.post('/api/signals/scan', json={
                'stocks': test_symbols,
                'minScore': 0,
                'maxRiskLevel': 'high',
                'technical': [],
                'fundamental': []
            })
            elapsed = time.time() - start_time

            # 验证响应
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True

            # 验证性能
            print(f"\n性能测试结果: 扫描{len(test_symbols)}只股票耗时 {elapsed:.2f}秒")
            assert elapsed < 10.0, \
                f"Performance test failed: {elapsed:.2f}s > 10s target"

            # 验证返回了结果
            assert data['scanned'] == len(test_symbols)
            assert len(data['opportunities']) > 0

        finally:
            # 清理测试数据
            cursor.execute("DELETE FROM quant.daily_klines WHERE symbol = ANY(%s)", ([s_.split('.')[0] for s_ in test_symbols],))
            db_connection.commit()
            cursor.close()

    def test_filter_combinations(self, client, setup_test_data, test_stocks):
        """测试过滤器组合"""
        # 测试1: 最小评分过滤
        response = client.post('/api/signals/scan', json={
            'stocks': test_stocks,
            'minScore': 60,
            'maxRiskLevel': 'high'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        for opp in data['opportunities']:
            assert opp['score'] >= 60, f"Score {opp['score']} < 60"

        # 测试2: 风险等级过滤
        response = client.post('/api/signals/scan', json={
            'stocks': test_stocks,
            'minScore': 0,
            'maxRiskLevel': 'low'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        for opp in data['opportunities']:
            assert opp['risk_level'] == 'low', \
                f"Risk level {opp['risk_level']} > low"

        # 测试3: 技术面过滤
        response = client.post('/api/signals/scan', json={
            'stocks': test_stocks,
            'minScore': 0,
            'maxRiskLevel': 'high',
            'technical': ['rsi_oversold', 'macd_golden_cross']
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        # 技术面过滤可能会减少结果数量
        assert data['scanned'] == len(test_stocks)

        # 测试4: 基本面过滤
        response = client.post('/api/signals/scan', json={
            'stocks': test_stocks,
            'minScore': 0,
            'maxRiskLevel': 'high',
            'fundamental': ['low_pe', 'high_roe']
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 测试5: 组合过滤
        response = client.post('/api/signals/scan', json={
            'stocks': test_stocks,
            'minScore': 50,
            'maxRiskLevel': 'medium',
            'technical': ['rsi_oversold'],
            'fundamental': ['low_pe']
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        for opp in data['opportunities']:
            assert opp['score'] >= 50
            assert opp['risk_level'] in ['low', 'medium']

    def test_batch_query_efficiency(self, kline_repo, stock_repo, test_stocks, setup_test_data):
        """测试批量查询效率"""
        # 测试批量K线查询
        start_time = time.time()
        klines_map = kline_repo.batch_get_recent_klines(test_stocks, days=120)
        kline_elapsed = time.time() - start_time

        assert len(klines_map) == len(test_stocks), \
            f"Expected {len(test_stocks)} stocks, got {len(klines_map)}"
        for symbol in test_stocks:
            assert symbol in klines_map, f"Missing klines for {symbol}"
            assert len(klines_map[symbol]) > 0, f"Empty klines for {symbol}"

        print(f"\n批量K线查询: {len(test_stocks)}只股票耗时 {kline_elapsed:.3f}秒")

        # 测试批量基本面查询
        start_time = time.time()
        fundamentals_map = stock_repo.batch_get_fundamentals(test_stocks)
        fund_elapsed = time.time() - start_time

        assert len(fundamentals_map) == len(test_stocks), \
            f"Expected {len(test_stocks)} stocks, got {len(fundamentals_map)}"
        for symbol in test_stocks:
            assert symbol in fundamentals_map, f"Missing fundamentals for {symbol}"

        print(f"批量基本面查询: {len(test_stocks)}只股票耗时 {fund_elapsed:.3f}秒")

        # 批量查询应该比单个查询快得多
        # 对于3只股票，批量查询应该在0.1秒内完成
        assert kline_elapsed < 0.5, f"Batch kline query too slow: {kline_elapsed:.3f}s"
        assert fund_elapsed < 0.5, f"Batch fundamental query too slow: {fund_elapsed:.3f}s"

    def test_empty_stock_list(self, client):
        """测试空股票列表"""
        response = client.post('/api/signals/scan', json={
            'stocks': [],
            'minScore': 0,
            'maxRiskLevel': 'high'
        })

        # 应该返回成功，但没有机会
        assert response.status_code == 200
        data = response.get_json()
        # 空列表会触发自选股+热门股票池逻辑，所以可能有结果
        assert data['success'] is True

    def test_invalid_stock_codes(self, client):
        """测试无效股票代码（容错契约：无效代码被跳过而不是整单 500）"""
        response = client.post('/api/signals/scan', json={
            'stocks': ['INVALID.XX', '999999.SH'],
            'minScore': 0,
            'maxRiskLevel': 'high'
        })

        # 现行契约：扫描服务对无数据/无效代码按 skip 处理，返回 200 且机会为空
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['opportunities'] == []

    def test_error_handling(self, client):
        """测试错误处理"""
        # 测试无效的JSON
        response = client.post('/api/signals/scan',
                                data='invalid json',
                                content_type='application/json')
        # Flask会返回400或500
        assert response.status_code in [400, 500]

        # 测试无效的参数类型 - 会抛出ValueError
        # 这个测试验证API没有做参数类型验证，会直接抛出异常
        # 在生产环境中应该添加参数验证
        try:
            response = client.post('/api/signals/scan', json={
                'minScore': 'invalid',  # 应该是数字
                'maxRiskLevel': 'high'
            })
            # 如果没有抛出异常，应该返回错误
            assert response.status_code in [400, 500]
        except ValueError:
            # 预期会抛出ValueError，这是当前的行为
            pass
