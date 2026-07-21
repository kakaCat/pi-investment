# services/report_generator.py
"""
报告生成器 - 生成 Markdown 格式的诊断报告
"""
from typing import Dict
from datetime import datetime
from pathlib import Path
import structlog
import re

logger = structlog.get_logger(__name__)


class ReportGenerationError(Exception):
    """报告生成错误"""
    pass


class ReportGenerator:
    """Markdown 报告生成器"""

    def __init__(self, output_dir: str = 'docs/superpowers/reports'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, analysis: Dict, diagnosis: Dict, params: Dict) -> str:
        """
        生成诊断报告

        Args:
            analysis: 分析结果 {metrics, benchmark, ratings}
            diagnosis: 诊断结论 {conclusion, strengths, weaknesses, suggestions}
            params: 参数 {strategy_name, symbol, start_date, end_date}

        Returns:
            报告文件路径

        Raises:
            ReportGenerationError: 输入验证失败或文件写入失败
        """
        # 输入验证
        self._validate_inputs(analysis, diagnosis, params)

        # 生成文件名（包含时间戳避免覆盖）
        timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')
        strategy_name = self._sanitize_filename(params['strategy_name'])
        symbol = self._sanitize_filename(params['symbol'])
        filename = f"{timestamp}-{strategy_name}-{symbol}-diagnosis.md"
        filepath = self.output_dir / filename

        # 生成报告内容
        content = self._generate_content(analysis, diagnosis, params)

        # 写入文件
        try:
            filepath.write_text(content, encoding='utf-8')
        except (OSError, PermissionError) as e:
            raise ReportGenerationError(f"Failed to write report to {filepath}: {e}")

        logger.info(f"Report generated: {filepath}")

        return str(filepath)

    def _validate_inputs(self, analysis: Dict, diagnosis: Dict, params: Dict) -> None:
        """
        验证输入参数

        Raises:
            ReportGenerationError: 缺少必填字段
        """
        # 验证 analysis
        required_analysis_keys = ['metrics', 'benchmark', 'ratings']
        for key in required_analysis_keys:
            if key not in analysis:
                raise ReportGenerationError(f"Missing required key in analysis: {key}")

        # 验证 metrics
        required_metrics = ['annualReturn', 'sharpeRatio', 'maxDrawdown', 'winRate', 'totalTrades']
        for key in required_metrics:
            if key not in analysis['metrics']:
                raise ReportGenerationError(f"Missing required key in analysis.metrics: {key}")

        # 验证 benchmark
        required_benchmark = ['annualReturn', 'sharpeRatio', 'maxDrawdown']
        for key in required_benchmark:
            if key not in analysis['benchmark']:
                raise ReportGenerationError(f"Missing required key in analysis.benchmark: {key}")

        # 验证 ratings
        required_ratings = ['overall', 'return', 'risk', 'stability']
        for key in required_ratings:
            if key not in analysis['ratings']:
                raise ReportGenerationError(f"Missing required key in analysis.ratings: {key}")

        # 验证 diagnosis
        required_diagnosis_keys = ['conclusion', 'strengths', 'weaknesses', 'suggestions']
        for key in required_diagnosis_keys:
            if key not in diagnosis:
                raise ReportGenerationError(f"Missing required key in diagnosis: {key}")

        # 验证 params
        required_params = ['strategy_name', 'symbol', 'start_date', 'end_date']
        for key in required_params:
            if key not in params:
                raise ReportGenerationError(f"Missing required key in params: {key}")

    def _sanitize_filename(self, name: str) -> str:
        """
        清理文件名中的特殊字符

        Args:
            name: 原始文件名

        Returns:
            清理后的文件名
        """
        # 移除或替换不安全的文件名字符
        # 保留字母、数字、中文、下划线、连字符、点号
        sanitized = re.sub(r'[^\w一-鿿\-.]', '_', name)
        # 移除连续的下划线
        sanitized = re.sub(r'_+', '_', sanitized)
        # 移除首尾的下划线和点号
        sanitized = sanitized.strip('_.')
        return sanitized

    def _generate_content(self, analysis: Dict, diagnosis: Dict, params: Dict) -> str:
        """生成报告内容"""
        metrics = analysis['metrics']
        benchmark = analysis['benchmark']
        ratings = analysis['ratings']

        content = f"""# 策略诊断报告

**诊断时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**策略名称**: {params['strategy_name']}
**股票代码**: {params['symbol']}
**回测周期**: {params['start_date']} ~ {params['end_date']}
**基准指数**: {benchmark.get('name', '沪深300')}

## 一、综合评级

**评级**: {ratings['overall']}

**结论**: {diagnosis['conclusion']}

## 二、关键指标

| 指标 | 策略 | 基准 | 评级 |
|------|------|------|------|
| 年化收益 | {metrics['annualReturn']:.1%} | {benchmark['annualReturn']:.1%} | {self._translate_rating(ratings['return'])} |
| 夏普比率 | {metrics['sharpeRatio']:.2f} | {benchmark['sharpeRatio']:.2f} | {self._translate_rating(ratings['stability'])} |
| 最大回撤 | {metrics['maxDrawdown']:.1%} | {benchmark['maxDrawdown']:.1%} | {self._translate_risk_rating(ratings['risk'])} |
| 胜率 | {metrics['winRate']:.1%} | - | - |
| 交易次数 | {metrics['totalTrades']} | - | - |

## 三、诊断分析

### 优势
"""

        # 处理空列表情况
        if diagnosis['strengths']:
            for strength in diagnosis['strengths']:
                content += f"- ✓ {strength}\n"
        else:
            content += "- 暂无明显优势\n"

        content += "\n### 劣势\n"
        if diagnosis['weaknesses']:
            for weakness in diagnosis['weaknesses']:
                content += f"- ✗ {weakness}\n"
        else:
            content += "- 暂无明显劣势\n"

        content += "\n### 优化建议\n"
        if diagnosis['suggestions']:
            for i, suggestion in enumerate(diagnosis['suggestions'], 1):
                content += f"{i}. {suggestion}\n"
        else:
            content += "- 暂无优化建议\n"

        content += f"""

---

**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**系统版本**: quantsys-v2
"""

        return content

    def _translate_rating(self, rating: str) -> str:
        """翻译评级"""
        mapping = {
            'excellent': '优秀',
            'good': '良好',
            'moderate': '一般',
            'poor': '较差'
        }
        return mapping.get(rating, rating)

    def _translate_risk_rating(self, rating: str) -> str:
        """翻译风险评级"""
        mapping = {
            'low': '低风险',
            'moderate': '中等风险',
            'high': '高风险'
        }
        return mapping.get(rating, rating)
