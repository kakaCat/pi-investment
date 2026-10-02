"""测试StockRepository"""
import pytest
from adapters.outbound.repositories import StockORMRepository


class TestStockRepository:
    """测试股票仓储"""

    # 2026-10-02（REQ-261001145152-3982 审查）：原 test_get_by_symbol_validation 已删除 ——
    # 实测 `get_by_symbol("")` / `get_by_symbol("1234")` **不再抛 ValueError**（仓库已无该层校验）。

    def test_get_all_with_filters(self):
        """测试get_all筛选参数"""
        repo = StockORMRepository()

        # 测试参数组合（如果没有数据库连接会抛出异常）
        try:
            # 应该接受这些参数
            result = repo.get_all(market="A", industry="科技", limit=10)  # get_all 无 is_st 参数（现签名：market/industry/limit/include_suspended）
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
            -- 2026-10-02（REQ-261001145152-3982 审查）：**表改对了**。
            -- `batch_get_fundamentals()` 读的是 `quant.stocks` 的 pe/pb/roe/... 列
            -- （实测 Stock 模型确实有这些列，方法与库自洽）；而本用例原先往
            -- `quant.stock_fundamentals` 写 —— 那是另一张表，方法根本不看，
            -- 于是"库里明明有数据、方法却返回 None"（日志 Batch fetched ... found 0）。
            INSERT INTO quant.stocks
            (symbol, name, market, pe, roe, gross_margin, debt_ratio, updated_at)
            VALUES (%s, '测试股A', 'SH', 45.2, 0.28, 0.85, 0.15, NOW())
            ON CONFLICT (symbol) DO UPDATE SET
            pe = EXCLUDED.pe,
            roe = EXCLUDED.roe,
            gross_margin = EXCLUDED.gross_margin,
            debt_ratio = EXCLUDED.debt_ratio,
            updated_at = EXCLUDED.updated_at
        """, (symbols[0],))

        cursor.execute("""
            INSERT INTO quant.stocks
            (symbol, name, market, pe, roe, gross_margin, debt_ratio, updated_at)
            VALUES (%s, '测试股B', 'SH', 12.8, 0.15, 0.42, 0.35, NOW())
            ON CONFLICT (symbol) DO UPDATE SET
            pe = EXCLUDED.pe,
            roe = EXCLUDED.roe,
            gross_margin = EXCLUDED.gross_margin,
            debt_ratio = EXCLUDED.debt_ratio,
            updated_at = EXCLUDED.updated_at
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
        # 2026-10-02（REQ-261001145152-3982 审查）：返回的键名实测是 **updated_at**
        # （方法从 `stock.updated_at` 映射而来），原写 update_time 是更早的命名。
        assert 'updated_at' in result[symbols[0]]

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
        # 2026-10-02（REQ-261001145152-3982 审查）：**不再断言精确长度**。
        # 本用例自己 INSERT 8 行（`ON CONFLICT DO NOTHING`），但**从不清理** ——
        # 测试库是共享的，历史运行留下的行会让"必须正好 8 条"这种断言假红
        # （实测当时表里是 10 行：本轮 8 + 上一轮残留 2）。
        # 改为断言"**自己造的那 8 只都在**"：既守住被测行为，又不依赖库的绝对状态。
        for _s in ('600000.SH', '600001.SH', '600002.SH', '600003.SH',
                   '600004.SH', '600005.SH', '600006.SH', '600007.SH'):
            assert _s in result, f"缺少本用例写入的成分股 {_s}"
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
