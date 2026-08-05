"""
市场风格检测端到端测试

验证完整流程：数据库 → 服务 → API → Agent
"""
import pytest
import time
from datetime import date, datetime, timedelta
from adapters.inbound.api.server import app
from application.services.market_style_detector import MarketStyleDetector
from application.services.strategy_weight_adjuster import StrategyWeightAdjuster
from adapters.outbound.repositories import MarketStyleORMRepository


class TestMarketStyleE2E:
    """市场风格检测端到端测试"""

    @pytest.fixture(scope="function")
    def test_db_connection(self):
        """为 E2E 测试提供独立的数据库连接"""
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from infrastructure.persistence.database.base_repository import _resolve_db_dsn

        dsn = _resolve_db_dsn()
        conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        yield conn
        conn.close()

    @pytest.fixture
    def client(self):
        """Flask测试客户端"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def test_kline_data(self, test_db_connection):
        """准备测试用 K 线数据"""
        cursor = test_db_connection.cursor()

        # 清理旧数据
        cursor.execute("DELETE FROM quant.daily_klines WHERE symbol IN ('000001.SH', '000300.SH', '399001.SZ')")
        test_db_connection.commit()

        # 插入测试数据（最近 60 天）
        test_symbols = ['000001.SH', '000300.SH', '399001.SZ']
        base_date = date.today() - timedelta(days=60)

        for symbol in test_symbols:
            for i in range(60):
                trade_date = base_date + timedelta(days=i)
                # 跳过周末
                if trade_date.weekday() >= 5:
                    continue

                cursor.execute("""
                    INSERT INTO quant.daily_klines
                    (symbol, trade_date, open, high, low, close, volume, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, trade_date) DO NOTHING
                """, (
                    symbol,
                    trade_date,
                    100.0 + i * 0.5,  # open
                    102.0 + i * 0.5,  # high
                    99.0 + i * 0.5,   # low
                    101.0 + i * 0.5,  # close
                    1000000 + i * 10000,  # volume
                    100000000 + i * 1000000  # amount
                ))

        test_db_connection.commit()
        yield

        # 清理
        cursor.execute("DELETE FROM quant.daily_klines WHERE symbol IN ('000001.SH', '000300.SH', '399001.SZ')")
        test_db_connection.commit()

    def test_market_style_detection_e2e(self, test_db_connection, test_kline_data):
        """测试市场风格检测完整流程"""
        # 1. 执行检测（当前契约：detect_market_style，风格为 value/growth/cycle）
        detector = MarketStyleDetector()
        result = detector.detect_market_style()

        assert result['style'] in ['value', 'growth', 'cycle']
        assert 0 <= result['confidence'] <= 1
        assert 'indicators' in result
        assert 'scores' in result

        # 2. 保存到数据库（当前契约：由 MarketStyleORMRepository 持久化）
        repo = MarketStyleORMRepository()
        saved_ok = repo.save_market_style(
            trade_date=date.today(),
            style=result['style'],
            confidence=result['confidence'],
            metrics=result.get('indicators')
        )
        assert saved_ok is True

        # 3. 从数据库读取
        saved = repo.get_market_style(date.today())
        assert saved is not None
        assert saved['style'] == result['style']
        assert float(saved['confidence']) == result['confidence']

        # 4. 查询策略权重
        adjuster = StrategyWeightAdjuster()
        weight_result = adjuster.get_weight(
            strategy_name='test_strategy',
            strategy_type='trend_following',
            market_style=result['style']
        )

        assert 'weight_adjustment' in weight_result
        assert weight_result['mode'] in ['static', 'dynamic']
        assert weight_result['weight_adjustment'] > 0

    def test_api_integration(self, client, test_db_connection, test_kline_data):
        """测试 API 集成"""
        # 获取市场风格（当前契约：indicators 字段，风格为 value/growth/cycle）
        response = client.get('/api/market/style')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True

        style_data = data['data']
        assert 'style' in style_data
        assert 'confidence' in style_data
        assert 'indicators' in style_data

        market_style = style_data['style']
        assert market_style in ['value', 'growth', 'cycle']

        # 注：GET /api/strategies/<name>/weight 端点已从代码库移除
        # （Flask/FastAPI 路由均无），权重调整能力经 StrategyWeightAdjuster
        # 服务覆盖（见 test_market_style_detection_e2e 第 4 步）

    def test_performance_requirements(self, test_db_connection, test_kline_data):
        """测试性能要求"""
        detector = MarketStyleDetector()
        repo = MarketStyleORMRepository()

        # 检测时间应 < 5 秒
        start = time.time()
        result = detector.detect_market_style()
        elapsed = time.time() - start

        assert elapsed < 5.0, f"检测时间 {elapsed:.2f}s 超过 5 秒限制"

        # API 响应时间应 < 200ms（缓存命中）
        repo.save_market_style(
            trade_date=date.today(),
            style=result['style'],
            confidence=result['confidence'],
            metrics=result.get('indicators')
        )

        start = time.time()
        cached = repo.get_market_style(date.today())
        elapsed = time.time() - start

        assert elapsed < 0.2, f"API 响应时间 {elapsed:.3f}s 超过 200ms 限制"

        # 验证缓存有效性
        assert cached is not None
        assert cached['style'] == result['style']
