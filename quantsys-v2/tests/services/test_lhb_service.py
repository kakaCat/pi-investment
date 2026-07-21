"""
LhbService 单元测试
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch
from application.services.lhb_service import LhbService


class TestLhbService:
    """LhbService 测试类"""

    def test_get_stock_lhb_success(self):
        """测试个股查询成功"""
        # Mock 数据源
        mock_data_source = Mock()
        mock_df = pd.DataFrame({
            '上榜日': ['2026-05-31', '2026-05-30'],
            '股票简称': ['中粮糖业', '中粮糖业'],
            '解读': ['日涨幅偏离值达7%', '日振幅值达15%'],
            '收盘价': [10.50, 10.20],
            '涨跌幅': [8.5, 5.2],
            '龙虎榜净买额': [5000.0, 3000.0],
            '龙虎榜买入额': [8000.0, 5000.0],
            '龙虎榜卖出额': [3000.0, 2000.0],
            '龙虎榜成交额': [11000.0, 7000.0]
        })
        mock_data_source.fetch_stock_lhb.return_value = mock_df

        # 创建服务
        service = LhbService(data_source=mock_data_source)

        # 调用方法
        result = service.get_stock_lhb('600737', days=30)

        # 验证结果
        assert result['success'] is True
        assert result['symbol'] == '600737'
        assert result['name'] == '中粮糖业'
        assert result['total_records'] == 2
        assert len(result['records']) == 2
        assert result['records'][0]['date'] == '2026-05-31'
        assert result['records'][0]['close_price'] == 10.50

    def test_get_stock_lhb_no_data(self):
        """测试个股无数据"""
        # Mock 数据源返回空 DataFrame
        mock_data_source = Mock()
        mock_data_source.fetch_stock_lhb.return_value = pd.DataFrame()

        service = LhbService(data_source=mock_data_source)
        result = service.get_stock_lhb('600737', days=30)

        assert result['success'] is False
        assert '无龙虎榜记录' in result['error']

    def test_get_stock_lhb_exception(self):
        """测试个股查询异常"""
        # Mock 数据源抛出异常
        mock_data_source = Mock()
        mock_data_source.fetch_stock_lhb.side_effect = Exception('网络错误')

        service = LhbService(data_source=mock_data_source)
        result = service.get_stock_lhb('600737', days=30)

        assert result['success'] is False
        assert '网络错误' in result['error']

    def test_get_daily_lhb_success(self):
        """测试日期汇总成功"""
        # Mock 数据源
        mock_data_source = Mock()
        mock_df = pd.DataFrame({
            '代码': ['600737', '600519'],
            '名称': ['中粮糖业', '贵州茅台'],
            '解读': ['日涨幅偏离值达7%', '日振幅值达15%'],
            '收盘价': [10.50, 1800.0],
            '涨跌幅': [8.5, 3.2],
            '龙虎榜净买额': [5000.0, 20000.0],
            '龙虎榜买入额': [8000.0, 30000.0],
            '龙虎榜卖出额': [3000.0, 10000.0],
            '龙虎榜成交额': [11000.0, 40000.0]
        })
        mock_data_source.fetch_daily_lhb.return_value = mock_df

        service = LhbService(data_source=mock_data_source)
        result = service.get_daily_lhb('20260531')

        assert result['success'] is True
        assert result['date'] == '2026-05-31'
        assert result['total_stocks'] == 2
        assert len(result['stocks']) == 2
        assert result['stocks'][0]['symbol'] == '600737'

    def test_get_daily_lhb_no_data(self):
        """测试日期无数据"""
        mock_data_source = Mock()
        mock_data_source.fetch_daily_lhb.return_value = pd.DataFrame()

        service = LhbService(data_source=mock_data_source)
        result = service.get_daily_lhb('20260531')

        assert result['success'] is False
        assert '无龙虎榜数据' in result['error']

    def test_format_date(self):
        """测试日期格式化"""
        service = LhbService()
        assert service._format_date('20260531') == '2026-05-31'
        assert service._format_date('20261225') == '2026-12-25'
