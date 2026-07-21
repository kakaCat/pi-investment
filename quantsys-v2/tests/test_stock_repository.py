"""测试StockRepository"""
import pytest
from adapters.outbound.repositories import StockORMRepository


class TestStockRepository:
    """测试股票仓储"""

    def test_get_by_symbol_validation(self):
        """测试get_by_symbol参数校验"""
        repo = StockORMRepository()

        # 无效代码应该抛出异常
        with pytest.raises(ValueError):
            repo.get_by_symbol("")

        with pytest.raises(ValueError):
            repo.get_by_symbol("1234")

    def test_get_all_with_filters(self):
        """测试get_all筛选参数"""
        repo = StockORMRepository()

        # 测试参数组合（如果没有数据库连接会抛出异常）
        try:
            # 应该接受这些参数
            result = repo.get_all(market="A", industry="科技", is_st=False, limit=10)
            # 如果有数据库连接，应该返回列表
            assert isinstance(result, list)
        except RuntimeError as e:
            # 如果没有数据库连接，会抛出异常，这是预期的
            assert "database" in str(e).lower() or "connection" in str(e).lower()

    def test_batch_get_fundamentals(self, db_connection):
        """测试批量查询股票基本面数据"""
        repo = StockORMRepository()
        repo.db = db_connection

        # 准备测试数据：3只股票，2只有数据，1只没有数据
        symbols = ['000001.SH', '600036.SH', '601318.SH']

        # 插入测试基本面数据（只插入前2只）
        cursor = db_connection.cursor()
        cursor.execute("""
            INSERT INTO quant.stock_fundamentals
            (symbol, pe_ratio, roe, gross_margin, debt_ratio, update_time)
            VALUES (%s, 45.2, 0.28, 0.85, 0.15, '2024-01-15')
            ON CONFLICT (symbol) DO UPDATE SET
            pe_ratio = EXCLUDED.pe_ratio,
            roe = EXCLUDED.roe,
            gross_margin = EXCLUDED.gross_margin,
            debt_ratio = EXCLUDED.debt_ratio,
            update_time = EXCLUDED.update_time
        """, (symbols[0],))

        cursor.execute("""
            INSERT INTO quant.stock_fundamentals
            (symbol, pe_ratio, roe, gross_margin, debt_ratio, update_time)
            VALUES (%s, 12.8, 0.15, 0.42, 0.35, '2024-01-15')
            ON CONFLICT (symbol) DO UPDATE SET
            pe_ratio = EXCLUDED.pe_ratio,
            roe = EXCLUDED.roe,
            gross_margin = EXCLUDED.gross_margin,
            debt_ratio = EXCLUDED.debt_ratio,
            update_time = EXCLUDED.update_time
        """, (symbols[1],))

        db_connection.commit()
        cursor.close()

        # 执行批量查询
        result = repo.batch_get_fundamentals(symbols)

        # 验证结果结构
        assert isinstance(result, dict)
        assert len(result) == 3  # 必须包含所有3只股票

        # 验证有数据的股票
        assert symbols[0] in result
        assert result[symbols[0]] is not None
        assert result[symbols[0]]['pe_ratio'] == 45.2
        assert result[symbols[0]]['roe'] == 0.28
        assert result[symbols[0]]['gross_margin'] == 0.85
        assert result[symbols[0]]['debt_ratio'] == 0.15
        assert 'update_time' in result[symbols[0]]

        assert symbols[1] in result
        assert result[symbols[1]] is not None
        assert result[symbols[1]]['pe_ratio'] == 12.8

        # 验证没有数据的股票返回None
        assert symbols[2] in result
        assert result[symbols[2]] is None

    def test_batch_get_fundamentals_empty_list(self, db_connection):
        """测试空列表批量查询基本面"""
        repo = StockORMRepository()
        repo.db = db_connection

        result = repo.batch_get_fundamentals([])
        assert result == {}

    def test_get_index_constituents(self, db_connection):
        """测试查询指数成分股"""
        repo = StockORMRepository()
        repo.db = db_connection

        index_codes = ['000300.SH', '399006.SZ']

        # 插入测试指数成分股数据
        cursor = db_connection.cursor()

        # 沪深300成分股
        for i in range(5):
            symbol = f'60{i:04d}.SH'
            cursor.execute("""
                INSERT INTO quant.index_constituents
                (index_code, constituent_symbol, weight, update_time)
                VALUES (%s, %s, 1.0, NOW())
                ON CONFLICT (index_code, constituent_symbol) DO NOTHING
            """, (index_codes[0], symbol))

        # 创业板指成分股（包含一些重复的）
        for i in range(3, 8):
            symbol = f'60{i:04d}.SH'
            cursor.execute("""
                INSERT INTO quant.index_constituents
                (index_code, constituent_symbol, weight, update_time)
                VALUES (%s, %s, 1.0, NOW())
                ON CONFLICT (index_code, constituent_symbol) DO NOTHING
            """, (index_codes[1], symbol))

        db_connection.commit()
        cursor.close()

        # 执行查询
        result = repo.get_index_constituents(index_codes)

        # 验证结果
        assert isinstance(result, list)
        assert len(result) == 8  # 去重后应该是8只股票（0-7）
        assert all(isinstance(s, str) for s in result)

        # 验证包含预期的股票
        assert '600000.SH' in result
        assert '600004.SH' in result
        assert '600007.SH' in result

    def test_get_index_constituents_empty_list(self, db_connection):
        """测试空列表查询指数成分股"""
        repo = StockORMRepository()
        repo.db = db_connection

        result = repo.get_index_constituents([])
        assert result == []
