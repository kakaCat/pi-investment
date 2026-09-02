"""
测试因子报告生成功能
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import tempfile


class TestFactorReportGeneration:
    """测试因子 HTML 报告生成"""

    @pytest.fixture
    def sample_factor_df(self):
        """创建示例因子数据"""
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', '2024-03-31', freq='D')
        symbols = ['600000.SH', '600519.SH', '000001.SZ']

        data = []
        for date in dates:
            for symbol in symbols:
                data.append({
                    'date': date,
                    'symbol': symbol,
                    'factor': np.random.randn(),
                    'close': 100 + np.random.randn() * 10
                })

        return pd.DataFrame(data)

    @pytest.fixture
    def factor_service(self):
        """创建 FactorAnalysisService 实例"""
        from application.services.factor_analysis_service import FactorAnalysisService, ALPHALENS_AVAILABLE

        if not ALPHALENS_AVAILABLE:
            pytest.skip("alphalens not available")

        return FactorAnalysisService()

    def test_generate_report_html_basic(self, factor_service, sample_factor_df, tmp_path):
        """测试基础 HTML 报告生成"""
        # 准备因子数据
        factor_data = factor_service.prepare_factor_data(
            sample_factor_df,
            periods=(1, 5),
            quantiles=5,
            max_loss=0.5
        )

        # 生成报告
        output_path = str(tmp_path / "test_report.html")
        result_path = factor_service.generate_report_html(
            factor_data,
            factor_name="test_factor",
            output_path=output_path
        )

        # 验证
        assert result_path == output_path
        assert os.path.exists(result_path)

        # 读取 HTML 内容
        with open(result_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 验证关键内容
        assert 'test_factor' in html_content
        assert 'IC 时间序列' in html_content
        assert '分层收益' in html_content
        assert '累计收益' in html_content
        assert '<img src="data:image/png;base64,' in html_content
        assert 'QuantSys V2 因子分析系统' in html_content

    def test_generate_report_html_auto_path(self, factor_service, sample_factor_df):
        """测试自动生成文件路径"""
        # 准备因子数据
        factor_data = factor_service.prepare_factor_data(
            sample_factor_df,
            periods=(1,),
            quantiles=5,
            max_loss=0.5
        )

        # 生成报告（不指定路径）
        result_path = factor_service.generate_report_html(
            factor_data,
            factor_name="auto_path_test"
        )

        # 验证
        assert result_path.startswith('/tmp/factor_report_auto_path_test_')
        assert result_path.endswith('.html')
        assert os.path.exists(result_path)

        # 清理
        os.remove(result_path)

    def test_generate_report_multiple_periods(self, factor_service, sample_factor_df, tmp_path):
        """测试多周期报告生成"""
        # 准备因子数据（三个周期）
        factor_data = factor_service.prepare_factor_data(
            sample_factor_df,
            periods=(1, 5, 10),
            quantiles=5,
            max_loss=0.5
        )

        # 生成报告
        output_path = str(tmp_path / "multi_period_report.html")
        result_path = factor_service.generate_report_html(
            factor_data,
            factor_name="multi_period",
            output_path=output_path
        )

        # 读取内容验证
        with open(result_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 应该包含多个周期的结果
        assert '1D' in html_content or '5D' in html_content or '10D' in html_content

    def test_generate_report_without_alphalens(self):
        """测试 alphalens 不可用时的错误处理"""
        from application.services.factor_analysis_service import ALPHALENS_AVAILABLE

        if ALPHALENS_AVAILABLE:
            pytest.skip("alphalens is available, cannot test unavailable scenario")

        from application.services.factor_analysis_service import FactorAnalysisService
        service = FactorAnalysisService()

        # 应该在初始化时就给出警告
        # 实际调用时应该抛出 ImportError
        with pytest.raises(ImportError):
            service.generate_report_html(
                pd.DataFrame(),
                factor_name="test"
            )


class TestDataServiceReportIntegration:
    """DataService.generate_factor_report 已在 P2-3 重构中移除，
    因子报告生成请使用 FactorAnalysisService（见 TestFactorReportGeneration）。
    保留此类占位，避免后续开发者误以为该接口仍存在于 DataService 上。
    """

    def test_generate_factor_report_removed(self):
        from application.services.data_service import DataService
        assert not hasattr(DataService, 'generate_factor_report')
