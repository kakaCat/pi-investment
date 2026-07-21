"""
端到端测试：alphalens 因子分析完整流程
"""
import pytest
import os
import time
import psutil
from application.services.data_service import DataService
from application.services.factor_analysis_service import ALPHALENS_AVAILABLE


@pytest.mark.e2e
class TestFactorAnalysisE2E:
    """端到端测试：完整因子分析流程"""

    @pytest.fixture
    def data_service(self):
        return DataService()

    def test_basic_factor_analysis_without_report(self, data_service, monkeypatch):
        """场景1: 基础因子分析（不生成报告）"""
        import pandas as pd
        import numpy as np

        if not ALPHALENS_AVAILABLE:
            pytest.skip("alphalens not available")

        # Mock _fetch_factor_data
        def mock_fetch_factor_data(factor_name, universe, start_date, end_date):
            np.random.seed(42)
            dates = pd.date_range(start_date, end_date, freq='D')[:90]
            data = []
            for date in dates:
                for symbol in universe:
                    data.append({
                        'symbol': symbol,
                        'date': date,
                        'factor': np.random.randn(),
                        'close': 100 + np.random.randn() * 10
                    })
            return pd.DataFrame(data)

        monkeypatch.setattr(data_service, '_fetch_factor_data', mock_fetch_factor_data)

        result = data_service.analyze_factors(
            factors=['rsi', 'macd', 'momentum_6m'],
            start_date='2024-01-01',
            end_date='2024-03-31',
            universe=['600000.SH', '600519.SH', '000001.SZ'],
            use_alphalens=True
        )

        assert result['success'] is True
        assert result['method'] == 'alphalens'
        assert len(result['factors']) == 3

        for factor in result['factors']:
            assert 'ic_analysis' in factor
            ic_mean = factor['ic_analysis']['ic_mean']
            assert -1 <= ic_mean <= 1, f"IC mean {ic_mean} out of range"
            assert 'returns_analysis' in factor
            assert 'turnover_analysis' in factor

    def test_generate_html_reports(self, data_service, tmp_path, monkeypatch):
        """场景2: 生成 HTML 报告"""
        import pandas as pd
        import numpy as np

        if not ALPHALENS_AVAILABLE:
            pytest.skip("alphalens not available")

        # Mock _fetch_factor_data
        def mock_fetch_factor_data(factor_name, universe, start_date, end_date):
            np.random.seed(42)
            dates = pd.date_range(start_date, end_date, freq='D')[:180]

            # 生成50只不同的股票代码
            unique_symbols = [f"{600000+i:06d}.SH" for i in range(50)]

            data = []
            for date in dates:
                for symbol in unique_symbols:
                    data.append({
                        'symbol': symbol,
                        'date': date,
                        'factor': np.random.randn(),
                        'close': 100 + np.random.randn() * 10
                    })
            return pd.DataFrame(data)

        monkeypatch.setattr(data_service, '_fetch_factor_data', mock_fetch_factor_data)

        start = time.time()

        result = data_service.generate_factor_report(
            factors=['rsi', 'macd'],
            start_date='2024-01-01',
            end_date='2024-06-30',
            universe=['600000.SH'],  # universe 参数不重要，mock会生成自己的数据
            output_dir=str(tmp_path)
        )

        elapsed = time.time() - start

        assert result['success'] is True
        assert result['success_count'] == 2
        assert elapsed < 30, f"耗时 {elapsed:.2f}秒，超过30秒限制"

        for report in result['reports']:
            if report['success']:
                assert os.path.exists(report['report_path'])
                file_size = os.path.getsize(report['report_path'])
                assert 100_000 < file_size < 500_000, \
                    f"文件大小 {file_size} 不在 100KB-500KB 范围内"

                # 验证 HTML 内容
                with open(report['report_path'], 'r', encoding='utf-8') as f:
                    html_content = f.read()
                assert '因子分析报告' in html_content
                assert '<img src="data:image/png;base64,' in html_content

    def test_batch_analysis_performance(self, data_service, tmp_path, monkeypatch):
        """场景3: 批量因子分析性能"""
        import pandas as pd
        import numpy as np

        if not ALPHALENS_AVAILABLE:
            pytest.skip("alphalens not available")

        # Mock _fetch_factor_data
        def mock_fetch_factor_data(factor_name, universe, start_date, end_date):
            np.random.seed(42)
            dates = pd.date_range(start_date, end_date, freq='D')[:250]

            # 生成100只不同的股票代码
            unique_symbols = [f"{600000+i:06d}.SH" for i in range(100)]

            data = []
            for date in dates:
                for symbol in unique_symbols:
                    data.append({
                        'symbol': symbol,
                        'date': date,
                        'factor': np.random.randn(),
                        'close': 100 + np.random.randn() * 10
                    })
            return pd.DataFrame(data)

        monkeypatch.setattr(data_service, '_fetch_factor_data', mock_fetch_factor_data)

        process = psutil.Process()
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        start = time.time()

        result = data_service.generate_factor_report(
            factors=['rsi', 'macd', 'momentum_6m', 'volatility_20', 'volume_ratio'],
            start_date='2024-01-01',
            end_date='2024-12-31',
            universe=['600000.SH'],  # universe 参数不重要
            output_dir=str(tmp_path)
        )

        elapsed = time.time() - start
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_used = mem_after - mem_before

        assert result['success'] is True
        assert elapsed < 60, f"耗时 {elapsed:.2f}秒，超过60秒限制"
        assert mem_used < 500, f"内存使用 {mem_used:.2f}MB，超过500MB限制"

        print(f"\n批量分析性能:")
        print(f"  耗时: {elapsed:.2f}秒")
        print(f"  内存: {mem_used:.2f}MB")
        print(f"  成功率: {result['success_count']}/{result['total']}")

    def test_partial_failure_handling(self, data_service, tmp_path, monkeypatch):
        """场景4.1: 部分因子无数据"""
        import pandas as pd
        import numpy as np

        if not ALPHALENS_AVAILABLE:
            pytest.skip("alphalens not available")

        def mock_fetch_factor_data(factor_name, universe, start_date, end_date):
            if factor_name == 'bad_factor':
                return pd.DataFrame()  # 空数据

            # 正常数据
            np.random.seed(42)
            dates = pd.date_range(start_date, end_date, freq='D')[:30]
            data = []
            for date in dates:
                for symbol in universe[:3]:
                    data.append({
                        'symbol': symbol,
                        'date': date,
                        'factor': np.random.randn(),
                        'close': 100 + np.random.randn() * 10
                    })
            return pd.DataFrame(data)

        monkeypatch.setattr(data_service, '_fetch_factor_data', mock_fetch_factor_data)

        result = data_service.generate_factor_report(
            factors=['good_factor_1', 'bad_factor', 'good_factor_2'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            universe=['600000.SH'],
            output_dir=str(tmp_path)
        )

        assert result['success'] is True
        assert result['success_count'] == 2
        assert result['failed_count'] == 1

        bad_report = next(r for r in result['reports'] if r['factor'] == 'bad_factor')
        assert bad_report['success'] is False
        assert 'error' in bad_report

    def test_alphalens_unavailable_fallback(self, data_service):
        """场景4.2: alphalens 不可用时的降级"""
        if ALPHALENS_AVAILABLE:
            pytest.skip("alphalens is available, cannot test unavailable scenario")

        result = data_service.analyze_factors(
            factors=['rsi', 'macd'],
            start_date='2024-01-01',
            end_date='2024-03-31',
            universe=['600000.SH'],
            use_alphalens=True
        )

        # 应该自动降级到 fallback 模式
        assert result['success'] is True
        assert result['method'] == 'fallback'
        assert 'note' in result or 'warning' in result
