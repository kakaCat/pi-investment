"""端到端测试：alphalens 因子分析完整流程（2026-10-23 重写）

原文件测试 `DataService.analyze_factors` / `generate_factor_report` /
`_fetch_factor_data`——这三者在 qs_market_data 包化后**全仓零实现**（功能
迁至 `FactorAnalysisService`：prepare_factor_data → calculate_* →
generate_report_html）。保留端到端意图：合成因子数据 → 真实 alphalens 计算
→ HTML 报告（图表 base64 内联）→ 文件落盘可读。
"""
import os

import numpy as np
import pandas as pd
import pytest

from application.services.factor_analysis_service import (
    ALPHALENS_AVAILABLE,
    FactorAnalysisService,
)

pytestmark = pytest.mark.e2e


def _make_factor_df(days: int = 120, symbols: int = 30, seed: int = 42) -> pd.DataFrame:
    """合成 alphalens 输入：date/symbol/factor/close"""
    rng = np.random.default_rng(seed)
    dates = pd.date_range('2024-01-01', periods=days, freq='D')
    symbols_list = [f'{600000 + i:06d}.SH' for i in range(symbols)]
    rows = []
    for d in dates:
        for s in symbols_list:
            rows.append({
                'date': d,
                'symbol': s,
                'factor': float(rng.standard_normal()),
                'close': float(100 + rng.standard_normal() * 10),
            })
    return pd.DataFrame(rows)


@pytest.fixture
def service():
    if not ALPHALENS_AVAILABLE:
        pytest.skip('alphalens not available')
    return FactorAnalysisService()


class TestFactorAnalysisE2E:
    def test_full_pipeline_without_report(self, service):
        """完整分析链路：数据准备 → IC/分层收益/换手率"""
        factor_data = service.prepare_factor_data(
            _make_factor_df(), periods=(1, 5), quantiles=5, max_loss=0.5)

        # 多周期以列形式进入（'1D' / '5D'）
        assert '1D' in factor_data.columns
        assert '5D' in factor_data.columns
        assert 'factor' in factor_data.columns

        ic = service.calculate_ic_analysis(factor_data)
        assert -1.0 <= ic['ic_mean'] <= 1.0
        assert 'ic_ir' in ic

        returns = service.calculate_returns_analysis(factor_data)
        assert returns is not None

    def test_html_report_end_to_end(self, service, tmp_path):
        """端到端：生成 HTML 报告（含 base64 内联图表）并校验内容"""
        factor_data = service.prepare_factor_data(
            _make_factor_df(), periods=(1, 5), quantiles=5, max_loss=0.5)
        out = tmp_path / 'report.html'

        path = service.generate_report_html(
            factor_data, factor_name='e2e_factor', output_path=str(out))

        assert path == str(out)
        assert os.path.exists(path)
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()

        assert 'e2e_factor' in html
        assert '因子分析报告' in html
        assert '<img src="data:image/png;base64,' in html
        assert '分析周期' in html
        assert '1D' in html or '5D' in html
        # 报告应包含核心指标区
        assert '核心指标摘要' in html
