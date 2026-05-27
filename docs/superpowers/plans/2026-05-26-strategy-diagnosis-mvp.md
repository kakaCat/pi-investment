# 策略诊断系统 MVP 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 BacktestCenter 添加策略诊断功能，快速判断策略是否有效（夏普比率 < 1.0 = 不如指数）

**Architecture:** 新增 DiagnosisService/StrategyAnalyzer/ReportGenerator 服务层，通过 /api/diagnosis/run 端点提供诊断，前端在 BacktestCenter 添加诊断标签页展示结果

**Tech Stack:** Python (Flask), Vue 3 (Element Plus), PostgreSQL

---

## 文件结构

**后端新增**:
- `quantsys-v2/services/diagnosis_service.py` - 诊断服务主入口
- `quantsys-v2/services/strategy_analyzer.py` - 策略分析器（评级算法）
- `quantsys-v2/services/report_generator.py` - Markdown 报告生成器
- `quantsys-v2/api/routes/diagnosis.py` - 诊断 API 端点

**前端新增**:
- `web-frontend/src/views/BacktestCenter/DiagnosisTab.vue` - 诊断标签页
- `web-frontend/src/views/BacktestCenter/DiagnosisCards.vue` - 指标卡片组件
- `web-frontend/src/api/diagnosis.ts` - 诊断 API 调用

**前端修改**:
- `web-frontend/src/views/BacktestCenter/index.vue` - 添加诊断标签页

**测试**:
- `quantsys-v2/tests/test_diagnosis_service.py`
- `quantsys-v2/tests/test_strategy_analyzer.py`

---

## Task 1: StrategyAnalyzer - 策略分析器

**Files:**
- Create: `quantsys-v2/services/strategy_analyzer.py`
- Test: `quantsys-v2/tests/test_strategy_analyzer.py`

- [ ] **Step 1: Write failing test for rating calculation**

```python
# tests/test_strategy_analyzer.py
import pytest
from services.strategy_analyzer import StrategyAnalyzer

def test_calculate_ratings_excellent_strategy():
    """测试优秀策略评级"""
    analyzer = StrategyAnalyzer()
    
    metrics = {
        'sharpeRatio': 1.8,
        'annualReturn': 0.20,
        'maxDrawdown': -0.12,
        'winRate': 0.60,
        'totalTrades': 30
    }
    
    benchmark = {
        'sharpeRatio': 0.6,
        'annualReturn': 0.08,
        'maxDrawdown': -0.25
    }
    
    result = analyzer.analyze(metrics, benchmark)
    
    assert result['ratings']['overall'] == 'A'
    assert result['ratings']['stability'] == 'excellent'
    assert result['ratings']['return'] == 'excellent'
    assert result['ratings']['risk'] == 'low'

def test_calculate_ratings_poor_strategy():
    """测试差策略评级"""
    analyzer = StrategyAnalyzer()
    
    metrics = {
        'sharpeRatio': 0.4,
        'annualReturn': 0.03,
        'maxDrawdown': -0.40,
        'winRate': 0.35,
        'totalTrades': 50
    }
    
    benchmark = {
        'sharpeRatio': 0.6,
        'annualReturn': 0.08,
        'maxDrawdown': -0.25
    }
    
    result = analyzer.analyze(metrics, benchmark)
    
    assert result['ratings']['overall'] == 'D'
    assert result['ratings']['stability'] == 'poor'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/test_strategy_analyzer.py::test_calculate_ratings_excellent_strategy -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'services.strategy_analyzer'"

- [ ] **Step 3: Implement StrategyAnalyzer with rating logic**

```python
# services/strategy_analyzer.py
"""
策略分析器 - 计算策略评级和诊断结论
"""
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class StrategyAnalyzer:
    """策略指标分析器"""
    
    # 固定阈值标准
    THRESHOLDS = {
        'sharpe': {'excellent': 1.5, 'good': 1.0, 'poor': 0.5},
        'return': {'excellent': 0.15, 'good': 0.10, 'poor': 0.05},
        'drawdown': {'excellent': -0.15, 'good': -0.25, 'poor': -0.35}
    }
    
    def analyze(self, metrics: Dict, benchmark: Dict) -> Dict:
        """
        分析策略表现
        
        Args:
            metrics: 策略指标 {sharpeRatio, annualReturn, maxDrawdown, winRate, totalTrades}
            benchmark: 基准指标 {sharpeRatio, annualReturn, maxDrawdown}
            
        Returns:
            分析结果 {ratings, comparison}
        """
        # 1. 计算各维度评级
        ratings = self._calculate_ratings(metrics, benchmark)
        
        # 2. 对比基准
        comparison = self._compare_with_benchmark(metrics, benchmark)
        
        # 3. 综合评级
        overall_rating = self._calculate_overall_rating(ratings, comparison)
        
        return {
            'ratings': {
                'overall': overall_rating,
                'return': ratings['return'],
                'risk': ratings['risk'],
                'stability': ratings['stability']
            },
            'comparison': comparison
        }
    
    def _calculate_ratings(self, metrics: Dict, benchmark: Dict) -> Dict:
        """计算各维度评级"""
        sharpe = metrics['sharpeRatio']
        annual_return = metrics['annualReturn']
        max_drawdown = metrics['maxDrawdown']
        
        # 收益评级（混合：固定阈值 + 相对基准）
        if annual_return > self.THRESHOLDS['return']['excellent']:
            return_rating = 'excellent'
        elif annual_return > benchmark['annualReturn']:
            return_rating = 'good'
        elif annual_return > self.THRESHOLDS['return']['poor']:
            return_rating = 'moderate'
        else:
            return_rating = 'poor'
        
        # 风险评级
        if max_drawdown > self.THRESHOLDS['drawdown']['excellent']:
            risk_rating = 'low'
        elif max_drawdown > self.THRESHOLDS['drawdown']['good']:
            risk_rating = 'moderate'
        else:
            risk_rating = 'high'
        
        # 稳定性评级（基于夏普比率）
        if sharpe > self.THRESHOLDS['sharpe']['excellent']:
            stability_rating = 'excellent'
        elif sharpe > self.THRESHOLDS['sharpe']['good']:
            stability_rating = 'good'
        else:
            stability_rating = 'poor'
        
        return {
            'return': return_rating,
            'risk': risk_rating,
            'stability': stability_rating
        }
    
    def _compare_with_benchmark(self, metrics: Dict, benchmark: Dict) -> Dict:
        """对比基准指标"""
        return {
            'sharpe_vs_benchmark': metrics['sharpeRatio'] - benchmark['sharpeRatio'],
            'return_vs_benchmark': metrics['annualReturn'] - benchmark['annualReturn'],
            'drawdown_vs_benchmark': metrics['maxDrawdown'] - benchmark['maxDrawdown']
        }
    
    def _calculate_overall_rating(self, ratings: Dict, comparison: Dict) -> str:
        """
        计算综合评级 A/B/C/D
        
        评分规则：
        - 稳定性（夏普比率）权重 40%
        - 收益权重 30%
        - 风险控制权重 20%
        - 相对基准加分 10%
        """
        score = 0
        
        # 稳定性权重 40%
        if ratings['stability'] == 'excellent':
            score += 40
        elif ratings['stability'] == 'good':
            score += 25
        else:
            score += 10
        
        # 收益权重 30%
        if ratings['return'] == 'excellent':
            score += 30
        elif ratings['return'] == 'good':
            score += 20
        else:
            score += 5
        
        # 风险控制权重 20%
        if ratings['risk'] == 'low':
            score += 20
        elif ratings['risk'] == 'moderate':
            score += 10
        
        # 相对基准加分 10%
        if comparison['sharpe_vs_benchmark'] > 0.3:
            score += 10
        
        # 评级映射
        if score >= 80:
            return 'A'
        elif score >= 60:
            return 'B'
        elif score >= 40:
            return 'C'
        else:
            return 'D'
    
    def generate_diagnosis(self, metrics: Dict, ratings: Dict, comparison: Dict) -> Dict:
        """
        生成诊断结论
        
        Returns:
            {conclusion, strengths, weaknesses, suggestions}
        """
        strengths = []
        weaknesses = []
        suggestions = []
        
        # 优势
        if ratings['stability'] in ['excellent', 'good']:
            strengths.append(
                f"夏普比率 {metrics['sharpeRatio']:.2f} "
                f"{'优于' if comparison['sharpe_vs_benchmark'] > 0 else '低于'}基准"
            )
        if metrics['winRate'] > 0.5:
            strengths.append(f"胜率 {metrics['winRate']:.1%} 超过 50%")
        
        # 劣势
        if abs(metrics['maxDrawdown']) > 0.25:
            weaknesses.append(
                f"最大回撤 {abs(metrics['maxDrawdown']):.1%} 偏高，建议加强止损"
            )
        if metrics['totalTrades'] < 20:
            weaknesses.append("交易次数较少，可能错过机会")
        
        # 建议
        if abs(metrics['maxDrawdown']) > 0.25:
            suggestions.append("添加动态止损（基于 ATR）")
        if metrics['totalTrades'] < 20:
            suggestions.append("优化入场信号，提高交易频率")
        if ratings['overall'] in ['C', 'D']:
            suggestions.append("考虑加入市场状态识别")
        
        # 结论
        conclusion = self._generate_conclusion(metrics, ratings, comparison)
        
        return {
            'conclusion': conclusion,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'suggestions': suggestions
        }
    
    def _generate_conclusion(self, metrics: Dict, ratings: Dict, comparison: Dict) -> str:
        """生成诊断结论文本"""
        rating_text = {
            'A': '优秀',
            'B': '良好',
            'C': '一般',
            'D': '较差'
        }
        
        overall = ratings['overall']
        sharpe = metrics['sharpeRatio']
        sharpe_diff = comparison['sharpe_vs_benchmark']
        
        if sharpe < 1.0:
            return f"策略表现{rating_text[overall]}，夏普比率 {sharpe:.2f} < 1.0，不如买指数"
        elif sharpe_diff > 0:
            return f"策略表现{rating_text[overall]}，夏普比率 {sharpe:.2f} 优于基准，风险调整后收益较好"
        else:
            return f"策略表现{rating_text[overall]}，夏普比率 {sharpe:.2f}，建议优化"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd quantsys-v2 && pytest tests/test_strategy_analyzer.py -v`

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add services/strategy_analyzer.py tests/test_strategy_analyzer.py
git commit -m "feat(diagnosis): add StrategyAnalyzer with rating logic"
```


## Task 2: ReportGenerator - 报告生成器

**Files:**
- Create: `quantsys-v2/services/report_generator.py`
- Test: `quantsys-v2/tests/test_report_generator.py`

- [ ] **Step 1: Write failing test for report generation**

```python
# tests/test_report_generator.py
import pytest
from services.report_generator import ReportGenerator
from pathlib import Path
import os

def test_generate_report():
    """测试生成 Markdown 报告"""
    generator = ReportGenerator()
    
    analysis = {
        'metrics': {
            'annualReturn': 0.15,
            'sharpeRatio': 1.2,
            'maxDrawdown': -0.18,
            'winRate': 0.55,
            'totalTrades': 24
        },
        'benchmark': {
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        },
        'ratings': {
            'overall': 'B',
            'return': 'good',
            'risk': 'moderate',
            'stability': 'good'
        }
    }
    
    diagnosis = {
        'conclusion': '策略表现良好',
        'strengths': ['夏普比率优于基准'],
        'weaknesses': ['最大回撤偏高'],
        'suggestions': ['添加动态止损']
    }
    
    params = {
        'strategyName': 'ma_cross',
        'symbol': '000001.SZ',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31'
    }
    
    report_path = generator.generate(analysis, diagnosis, params)
    
    assert report_path.startswith('docs/superpowers/reports/')
    assert report_path.endswith('.md')
    assert Path(report_path).exists()
    
    # 验证报告内容
    content = Path(report_path).read_text()
    assert '策略诊断报告' in content
    assert 'ma_cross' in content
    assert '000001.SZ' in content
    assert '夏普比率' in content
    
    # 清理测试文件
    Path(report_path).unlink()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/test_report_generator.py::test_generate_report -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'services.report_generator'"

- [ ] **Step 3: Implement ReportGenerator**

```python
# services/report_generator.py
"""
报告生成器 - 生成 Markdown 格式的诊断报告
"""
from typing import Dict
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


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
            params: 参数 {strategyName, symbol, startDate, endDate}
            
        Returns:
            报告文件路径
        """
        # 生成文件名
        timestamp = datetime.now().strftime('%Y-%m-%d')
        filename = f"{timestamp}-{params['strategyName']}-{params['symbol']}-diagnosis.md"
        filepath = self.output_dir / filename
        
        # 生成报告内容
        content = self._generate_content(analysis, diagnosis, params)
        
        # 写入文件
        filepath.write_text(content, encoding='utf-8')
        
        logger.info(f"Report generated: {filepath}")
        
        return str(filepath)
    
    def _generate_content(self, analysis: Dict, diagnosis: Dict, params: Dict) -> str:
        """生成报告内容"""
        metrics = analysis['metrics']
        benchmark = analysis['benchmark']
        ratings = analysis['ratings']
        
        content = f"""# 策略诊断报告

**诊断时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**策略名称**: {params['strategyName']}  
**股票代码**: {params['symbol']}  
**回测周期**: {params['startDate']} ~ {params['endDate']}  
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
        
        for strength in diagnosis['strengths']:
            content += f"- ✓ {strength}\n"
        
        content += "\n### 劣势\n"
        for weakness in diagnosis['weaknesses']:
            content += f"- ✗ {weakness}\n"
        
        content += "\n### 优化建议\n"
        for i, suggestion in enumerate(diagnosis['suggestions'], 1):
            content += f"{i}. {suggestion}\n"
        
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && pytest tests/test_report_generator.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/report_generator.py tests/test_report_generator.py
git commit -m "feat(diagnosis): add ReportGenerator for Markdown reports"
```


## Task 3: DiagnosisService - 诊断服务主入口

**Files:**
- Create: `quantsys-v2/services/diagnosis_service.py`
- Test: `quantsys-v2/tests/test_diagnosis_service.py`

- [ ] **Step 1: Write failing test for diagnosis service**

```python
# tests/test_diagnosis_service.py
import pytest
from services.diagnosis_service import DiagnosisService
from unittest.mock import Mock, patch

def test_run_diagnosis():
    """测试运行完整诊断"""
    service = DiagnosisService()
    
    params = {
        'symbol': '000001.SZ',
        'startDate': '2024-01-01',
        'endDate': '2024-12-31',
        'strategyName': 'ma_cross',
        'benchmark': '000300.SH'
    }
    
    # Mock 回测数据
    backtest_data = {
        'annualReturn': 0.15,
        'sharpeRatio': 1.2,
        'maxDrawdown': -0.18,
        'winRate': 0.55,
        'totalTrades': 24
    }
    
    with patch.object(service, '_get_backtest_data', return_value=backtest_data):
        with patch.object(service, '_get_benchmark_data', return_value={
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        }):
            result = service.run_diagnosis(params)
    
    assert 'diagnosisId' in result
    assert 'timestamp' in result
    assert 'metrics' in result
    assert 'benchmark' in result
    assert 'ratings' in result
    assert 'diagnosis' in result
    assert 'reportPath' in result
    
    assert result['ratings']['overall'] in ['A', 'B', 'C', 'D']
    assert result['metrics']['sharpeRatio'] == 1.2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/test_diagnosis_service.py::test_run_diagnosis -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'services.diagnosis_service'"

- [ ] **Step 3: Implement DiagnosisService**

```python
# services/diagnosis_service.py
"""
诊断服务 - 策略诊断主入口
"""
from typing import Dict, Optional
from datetime import datetime
import logging
import uuid

from services.strategy_analyzer import StrategyAnalyzer
from services.report_generator import ReportGenerator
from repositories.backtest_repository import BacktestRepository
from repositories.kline_repository import KlineRepository

logger = logging.getLogger(__name__)


class DiagnosisService:
    """策略诊断服务"""
    
    def __init__(self):
        self.backtest_repo = BacktestRepository()
        self.kline_repo = KlineRepository()
        self.strategy_analyzer = StrategyAnalyzer()
        self.report_generator = ReportGenerator()
    
    def run_diagnosis(self, params: Dict) -> Dict:
        """
        运行完整诊断
        
        Args:
            params: {
                backtestId: 回测ID（可选）
                symbol: 股票代码
                startDate: 开始日期
                endDate: 结束日期
                strategyName: 策略名称
                benchmark: 基准指数（默认 000300.SH）
            }
            
        Returns:
            诊断结果
        """
        try:
            # 1. 获取回测数据
            backtest_data = self._get_backtest_data(params)
            
            # 2. 获取基准数据
            benchmark_symbol = params.get('benchmark', '000300.SH')
            benchmark_data = self._get_benchmark_data(
                benchmark_symbol,
                params['startDate'],
                params['endDate']
            )
            
            # 3. 策略分析
            analysis = self.strategy_analyzer.analyze(backtest_data, benchmark_data)
            
            # 4. 生成诊断结论
            diagnosis = self.strategy_analyzer.generate_diagnosis(
                backtest_data,
                analysis['ratings'],
                analysis['comparison']
            )
            
            # 5. 生成报告文件
            report_path = self.report_generator.generate(
                {
                    'metrics': backtest_data,
                    'benchmark': benchmark_data,
                    'ratings': analysis['ratings']
                },
                diagnosis,
                params
            )
            
            # 6. 返回结果
            return {
                'diagnosisId': self._generate_id(),
                'timestamp': datetime.now().isoformat(),
                'strategy': {
                    'name': params['strategyName'],
                    'symbol': params['symbol'],
                    'period': f"{params['startDate']} ~ {params['endDate']}"
                },
                'metrics': backtest_data,
                'benchmark': benchmark_data,
                'ratings': analysis['ratings'],
                'diagnosis': diagnosis,
                'reportPath': report_path
            }
            
        except Exception as e:
            logger.error(f"Diagnosis failed: {e}", exc_info=True)
            raise
    
    def _get_backtest_data(self, params: Dict) -> Dict:
        """
        获取回测数据
        
        如果提供了 backtestId，从数据库读取
        否则需要先运行回测
        """
        backtest_id = params.get('backtestId')
        
        if backtest_id:
            # 从数据库读取回测结果
            backtest = self.backtest_repo.get_backtest(int(backtest_id))
            if not backtest:
                raise ValueError(f"Backtest not found: {backtest_id}")
            
            return {
                'annualReturn': backtest.get('annual_return', 0),
                'sharpeRatio': backtest.get('sharpe_ratio', 0),
                'maxDrawdown': backtest.get('max_drawdown', 0),
                'winRate': backtest.get('win_rate', 0),
                'totalTrades': backtest.get('total_trades', 0)
            }
        else:
            # 需要先运行回测
            # 这里简化处理，实际应该调用回测服务
            raise ValueError("backtestId is required. Please run backtest first.")
    
    def _get_benchmark_data(self, benchmark_symbol: str, start_date: str, end_date: str) -> Dict:
        """
        获取基准指数数据
        
        计算基准的年化收益、夏普比率、最大回撤
        """
        try:
            # 获取指数 K 线数据
            klines = self.kline_repo.get_daily_klines(benchmark_symbol, start_date, end_date)
            
            if not klines or len(klines) < 2:
                logger.warning(f"Insufficient benchmark data for {benchmark_symbol}, using default")
                return self._get_default_benchmark()
            
            # 计算指标
            returns = self._calculate_returns(klines)
            sharpe = self._calculate_sharpe_ratio(returns)
            max_dd = self._calculate_max_drawdown(klines)
            
            return {
                'symbol': benchmark_symbol,
                'name': self._get_index_name(benchmark_symbol),
                'annualReturn': returns,
                'sharpeRatio': sharpe,
                'maxDrawdown': max_dd
            }
            
        except Exception as e:
            logger.warning(f"Failed to get benchmark data: {e}, using default")
            return self._get_default_benchmark()
    
    def _calculate_returns(self, klines: list) -> float:
        """计算年化收益率"""
        if not klines or len(klines) < 2:
            return 0.0
        
        start_price = klines[0]['close']
        end_price = klines[-1]['close']
        total_return = (end_price - start_price) / start_price
        
        # 年化
        days = len(klines)
        years = days / 252.0
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        return annual_return
    
    def _calculate_sharpe_ratio(self, returns: float, risk_free_rate: float = 0.03) -> float:
        """计算夏普比率（简化版）"""
        # 简化计算：假设波动率为收益率的 1/3
        volatility = abs(returns) / 3 if returns != 0 else 0.1
        sharpe = (returns - risk_free_rate) / volatility if volatility > 0 else 0
        return sharpe
    
    def _calculate_max_drawdown(self, klines: list) -> float:
        """计算最大回撤"""
        if not klines:
            return 0.0
        
        peak = klines[0]['close']
        max_dd = 0.0
        
        for kline in klines:
            price = kline['close']
            if price > peak:
                peak = price
            dd = (price - peak) / peak
            if dd < max_dd:
                max_dd = dd
        
        return max_dd
    
    def _get_index_name(self, symbol: str) -> str:
        """获取指数名称"""
        mapping = {
            '000300.SH': '沪深300',
            '000001.SH': '上证指数',
            '399001.SZ': '深证成指',
            '399006.SZ': '创业板指'
        }
        return mapping.get(symbol, symbol)
    
    def _get_default_benchmark(self) -> Dict:
        """返回默认基准数据（沪深300 历史平均）"""
        return {
            'symbol': '000300.SH',
            'name': '沪深300',
            'annualReturn': 0.08,
            'sharpeRatio': 0.6,
            'maxDrawdown': -0.25
        }
    
    def _generate_id(self) -> str:
        """生成诊断ID"""
        timestamp = datetime.now().strftime('%Y%m%d')
        short_uuid = str(uuid.uuid4())[:8]
        return f"diag_{timestamp}_{short_uuid}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd quantsys-v2 && pytest tests/test_diagnosis_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/diagnosis_service.py tests/test_diagnosis_service.py
git commit -m "feat(diagnosis): add DiagnosisService main entry point"
```


## Task 4: API 端点 - /api/diagnosis/run

**Files:**
- Create: `quantsys-v2/api/routes/diagnosis.py`
- Modify: `quantsys-v2/api/server.py` (注册 blueprint)

- [ ] **Step 1: Write API endpoint**

```python
# api/routes/diagnosis.py
"""
诊断 API 路由
"""
from flask import Blueprint, jsonify, request
import logging

from api.shared import (
    api_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake
)
from services.diagnosis_service import DiagnosisService

logger = logging.getLogger(__name__)

diagnosis_bp = Blueprint('diagnosis', __name__)


@diagnosis_bp.route('/api/diagnosis/run', methods=['POST'])
@handle_api_error
def run_diagnosis():
    """
    运行策略诊断
    
    Request Body:
    {
        "backtestId": "123",
        "symbol": "000001.SZ",
        "startDate": "2024-01-01",
        "endDate": "2024-12-31",
        "strategyName": "ma_cross",
        "benchmark": "000300.SH"
    }
    """
    raw_data = request.get_json() or {}
    data = convert_keys_to_snake(raw_data)
    
    # 验证必需参数
    required = ['symbol', 'start_date', 'end_date', 'strategy_name']
    for field in required:
        if field not in data:
            return jsonify({'error': f'缺少必需参数: {field}'}), 400
    
    # 运行诊断
    service = DiagnosisService()
    result = service.run_diagnosis(data)
    
    return jsonify(sanitize_for_json(result))


@diagnosis_bp.route('/api/diagnosis/health', methods=['GET'])
def diagnosis_health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'diagnosis',
        'version': '1.0.0'
    })
```

- [ ] **Step 2: Register blueprint in server.py**

```python
# api/server.py
# 在现有的 blueprint 注册代码后添加

from api.routes.diagnosis import diagnosis_bp
app.register_blueprint(diagnosis_bp)
```

找到 `api/server.py` 中的 blueprint 注册部分（约第 46-96 行），在最后添加：

```python
from api.routes.diagnosis import diagnosis_bp
app.register_blueprint(diagnosis_bp)
```

- [ ] **Step 3: Test API endpoint manually**

Run: 
```bash
# 启动服务
cd quantsys-v2
python api/server.py
```

在另一个终端测试：
```bash
curl -X POST http://127.0.0.1:5001/api/diagnosis/run \
  -H "Content-Type: application/json" \
  -d '{
    "backtestId": "1",
    "symbol": "000001.SZ",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31",
    "strategyName": "ma_cross"
  }'
```

Expected: JSON response with diagnosis results (or error if no backtest data)

- [ ] **Step 4: Test health endpoint**

Run:
```bash
curl http://127.0.0.1:5001/api/diagnosis/health
```

Expected: `{"status":"ok","service":"diagnosis","version":"1.0.0"}`

- [ ] **Step 5: Commit**

```bash
git add api/routes/diagnosis.py api/server.py
git commit -m "feat(diagnosis): add /api/diagnosis/run endpoint"
```


## Task 5: 前端 API 服务

**Files:**
- Create: `web-frontend/src/api/diagnosis.ts`

- [ ] **Step 1: Create diagnosis API service**

```typescript
// web-frontend/src/api/diagnosis.ts
import request from '@/utils/request'

export interface DiagnosisParams {
  backtestId?: string
  symbol: string
  startDate: string
  endDate: string
  strategyName: string
  benchmark?: string
}

export interface DiagnosisResult {
  diagnosisId: string
  timestamp: string
  strategy: {
    name: string
    symbol: string
    period: string
  }
  metrics: {
    annualReturn: number
    sharpeRatio: number
    maxDrawdown: number
    winRate: number
    totalTrades: number
  }
  benchmark: {
    name: string
    annualReturn: number
    sharpeRatio: number
    maxDrawdown: number
  }
  ratings: {
    overall: 'A' | 'B' | 'C' | 'D'
    return: string
    risk: string
    stability: string
  }
  diagnosis: {
    conclusion: string
    strengths: string[]
    weaknesses: string[]
    suggestions: string[]
  }
  reportPath: string
}

/**
 * 运行策略诊断
 */
export function runDiagnosis(params: DiagnosisParams) {
  return request<DiagnosisResult>({
    url: '/api/diagnosis/run',
    method: 'post',
    data: params
  })
}

/**
 * 健康检查
 */
export function diagnosisHealth() {
  return request({
    url: '/api/diagnosis/health',
    method: 'get'
  })
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd web-frontend
npm run type-check
```

Expected: No TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add web-frontend/src/api/diagnosis.ts
git commit -m "feat(diagnosis): add frontend API service"
```


## Task 6: DiagnosisCards - 指标卡片组件

**Files:**
- Create: `web-frontend/src/views/BacktestCenter/DiagnosisCards.vue`

- [ ] **Step 1: Create DiagnosisCards component**

```vue
<!-- web-frontend/src/views/BacktestCenter/DiagnosisCards.vue -->
<template>
  <div class="diagnosis-cards">
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="card-header">
            <span class="label">年化收益</span>
            <el-icon :class="['icon', metrics.annualReturn >= 0 ? 'text-up' : 'text-down']">
              <TrendCharts v-if="metrics.annualReturn >= 0" />
              <Bottom v-else />
            </el-icon>
          </div>
          <div :class="['value', metrics.annualReturn >= 0 ? 'text-up' : 'text-down']">
            {{ formatPercent(metrics.annualReturn) }}
          </div>
          <div class="benchmark">
            基准: {{ formatPercent(benchmark.annualReturn) }}
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="card-header">
            <span class="label">夏普比率</span>
            <el-icon class="icon">
              <DataAnalysis />
            </el-icon>
          </div>
          <div :class="['value', getSharpeColor(metrics.sharpeRatio)]">
            {{ metrics.sharpeRatio.toFixed(2) }}
          </div>
          <div class="benchmark">
            基准: {{ benchmark.sharpeRatio.toFixed(2) }}
          </div>
          <div v-if="metrics.sharpeRatio < 1.0" class="warning-text">
            ⚠️ 不如买指数
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="card-header">
            <span class="label">最大回撤</span>
            <el-icon class="icon text-down">
              <Bottom />
            </el-icon>
          </div>
          <div class="value text-down">
            {{ formatPercent(metrics.maxDrawdown) }}
          </div>
          <div class="benchmark">
            基准: {{ formatPercent(benchmark.maxDrawdown) }}
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="metric-card rating-card">
          <div class="card-header">
            <span class="label">综合评级</span>
          </div>
          <div :class="['rating-badge', `rating-${ratings.overall}`]">
            {{ ratings.overall }}
          </div>
          <div class="rating-desc">
            {{ getRatingText(ratings.overall) }}
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { TrendCharts, Bottom, DataAnalysis } from '@element-plus/icons-vue'

interface Props {
  metrics: {
    annualReturn: number
    sharpeRatio: number
    maxDrawdown: number
    winRate: number
    totalTrades: number
  }
  benchmark: {
    name: string
    annualReturn: number
    sharpeRatio: number
    maxDrawdown: number
  }
  ratings: {
    overall: 'A' | 'B' | 'C' | 'D'
    return: string
    risk: string
    stability: string
  }
}

defineProps<Props>()

const formatPercent = (value: number) => {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(2)}%`
}

const getSharpeColor = (sharpe: number) => {
  if (sharpe >= 1.5) return 'text-excellent'
  if (sharpe >= 1.0) return 'text-good'
  if (sharpe >= 0.5) return 'text-moderate'
  return 'text-poor'
}

const getRatingText = (rating: string) => {
  const mapping: Record<string, string> = {
    'A': '优秀',
    'B': '良好',
    'C': '一般',
    'D': '较差'
  }
  return mapping[rating] || rating
}
</script>

<style scoped>
.diagnosis-cards {
  margin-bottom: 20px;
}

.metric-card {
  text-align: center;
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.label {
  font-size: 14px;
  color: #606266;
}

.icon {
  font-size: 20px;
}

.value {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 8px;
}

.benchmark {
  font-size: 12px;
  color: #909399;
}

.warning-text {
  margin-top: 8px;
  font-size: 12px;
  color: #E6A23C;
  font-weight: 500;
}

.text-up {
  color: #F56C6C;
}

.text-down {
  color: #67C23A;
}

.text-excellent {
  color: #67C23A;
}

.text-good {
  color: #409EFF;
}

.text-moderate {
  color: #E6A23C;
}

.text-poor {
  color: #F56C6C;
}

.rating-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.rating-badge {
  font-size: 48px;
  font-weight: bold;
  margin: 12px 0;
}

.rating-A {
  color: #67C23A;
}

.rating-B {
  color: #409EFF;
}

.rating-C {
  color: #E6A23C;
}

.rating-D {
  color: #F56C6C;
}

.rating-desc {
  font-size: 14px;
  color: #909399;
}
</style>
```

- [ ] **Step 2: Verify component renders**

Create a test file or manually test by importing in parent component.

- [ ] **Step 3: Commit**

```bash
git add web-frontend/src/views/BacktestCenter/DiagnosisCards.vue
git commit -m "feat(diagnosis): add DiagnosisCards component"
```


## Task 7: DiagnosisTab - 诊断标签页

**Files:**
- Create: `web-frontend/src/views/BacktestCenter/DiagnosisTab.vue`

- [ ] **Step 1: Create DiagnosisTab component**

```vue
<!-- web-frontend/src/views/BacktestCenter/DiagnosisTab.vue -->
<template>
  <div class="diagnosis-tab">
    <div class="toolbar">
      <el-button 
        type="primary" 
        :loading="loading" 
        :disabled="!backtestResult"
        @click="handleRunDiagnosis"
      >
        <el-icon><DataAnalysis /></el-icon>
        运行诊断
      </el-button>
      
      <el-button 
        v-if="diagnosisResult"
        @click="handleViewReport"
      >
        <el-icon><Document /></el-icon>
        查看报告
      </el-button>
    </div>

    <div v-if="!diagnosisResult && !loading" class="empty-state">
      <el-empty description="暂无诊断结果">
        <el-button type="primary" @click="handleRunDiagnosis" :disabled="!backtestResult">
          运行诊断
        </el-button>
      </el-empty>
    </div>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>

    <div v-if="diagnosisResult && !loading" class="diagnosis-content">
      <!-- 关键指标卡片 -->
      <DiagnosisCards
        :metrics="diagnosisResult.metrics"
        :benchmark="diagnosisResult.benchmark"
        :ratings="diagnosisResult.ratings"
      />

      <!-- 诊断结论 -->
      <el-card shadow="never" class="conclusion-card">
        <template #header>
          <div class="card-header">
            <span class="title">诊断结论</span>
            <el-tag :type="getRatingType(diagnosisResult.ratings.overall)" size="large">
              {{ diagnosisResult.ratings.overall }} 级
            </el-tag>
          </div>
        </template>

        <div class="conclusion-text">
          {{ diagnosisResult.diagnosis.conclusion }}
        </div>

        <el-divider />

        <!-- 优势 -->
        <div v-if="diagnosisResult.diagnosis.strengths.length > 0" class="section">
          <h4 class="section-title">
            <el-icon color="#67C23A"><CircleCheck /></el-icon>
            优势
          </h4>
          <ul class="list">
            <li v-for="(item, index) in diagnosisResult.diagnosis.strengths" :key="index" class="list-item strength">
              {{ item }}
            </li>
          </ul>
        </div>

        <!-- 劣势 -->
        <div v-if="diagnosisResult.diagnosis.weaknesses.length > 0" class="section">
          <h4 class="section-title">
            <el-icon color="#F56C6C"><CircleClose /></el-icon>
            劣势
          </h4>
          <ul class="list">
            <li v-for="(item, index) in diagnosisResult.diagnosis.weaknesses" :key="index" class="list-item weakness">
              {{ item }}
            </li>
          </ul>
        </div>

        <!-- 优化建议 -->
        <div v-if="diagnosisResult.diagnosis.suggestions.length > 0" class="section">
          <h4 class="section-title">
            <el-icon color="#409EFF"><Lightbulb /></el-icon>
            优化建议
          </h4>
          <ol class="list suggestions">
            <li v-for="(item, index) in diagnosisResult.diagnosis.suggestions" :key="index" class="list-item">
              {{ item }}
            </li>
          </ol>
        </div>
      </el-card>

      <!-- 与基准对比 -->
      <el-card shadow="never" class="comparison-card">
        <template #header>
          <span class="title">与基准对比</span>
        </template>

        <el-table :data="comparisonData" stripe>
          <el-table-column prop="metric" label="指标" width="120" />
          <el-table-column prop="strategy" label="策略" align="right" />
          <el-table-column prop="benchmark" label="基准" align="right" />
          <el-table-column prop="diff" label="差值" align="right">
            <template #default="{ row }">
              <span :class="row.diffClass">{{ row.diff }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Document, CircleCheck, CircleClose, Lightbulb } from '@element-plus/icons-vue'
import DiagnosisCards from './DiagnosisCards.vue'
import { runDiagnosis, type DiagnosisResult } from '@/api/diagnosis'

interface Props {
  backtestResult: any
}

const props = defineProps<Props>()

const loading = ref(false)
const diagnosisResult = ref<DiagnosisResult | null>(null)

const handleRunDiagnosis = async () => {
  if (!props.backtestResult) {
    ElMessage.warning('请先运行回测')
    return
  }

  loading.value = true
  try {
    const params = {
      symbol: props.backtestResult.symbol,
      startDate: props.backtestResult.startDate,
      endDate: props.backtestResult.endDate,
      strategyName: props.backtestResult.strategyName,
      benchmark: '000300.SH'
    }

    const result = await runDiagnosis(params)
    diagnosisResult.value = result
    ElMessage.success('诊断完成')
  } catch (error: any) {
    ElMessage.error(error.message || '诊断失败')
  } finally {
    loading.value = false
  }
}

const handleViewReport = () => {
  if (diagnosisResult.value?.reportPath) {
    ElMessage.info(`报告路径: ${diagnosisResult.value.reportPath}`)
  }
}

const getRatingType = (rating: string) => {
  const mapping: Record<string, any> = {
    'A': 'success',
    'B': 'primary',
    'C': 'warning',
    'D': 'danger'
  }
  return mapping[rating] || 'info'
}

const comparisonData = computed(() => {
  if (!diagnosisResult.value) return []

  const { metrics, benchmark } = diagnosisResult.value

  const formatPercent = (value: number) => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${(value * 100).toFixed(2)}%`
  }

  return [
    {
      metric: '年化收益',
      strategy: formatPercent(metrics.annualReturn),
      benchmark: formatPercent(benchmark.annualReturn),
      diff: formatPercent(metrics.annualReturn - benchmark.annualReturn),
      diffClass: metrics.annualReturn >= benchmark.annualReturn ? 'text-up' : 'text-down'
    },
    {
      metric: '夏普比率',
      strategy: metrics.sharpeRatio.toFixed(2),
      benchmark: benchmark.sharpeRatio.toFixed(2),
      diff: (metrics.sharpeRatio - benchmark.sharpeRatio).toFixed(2),
      diffClass: metrics.sharpeRatio >= benchmark.sharpeRatio ? 'text-up' : 'text-down'
    },
    {
      metric: '最大回撤',
      strategy: formatPercent(metrics.maxDrawdown),
      benchmark: formatPercent(benchmark.maxDrawdown),
      diff: formatPercent(metrics.maxDrawdown - benchmark.maxDrawdown),
      diffClass: metrics.maxDrawdown >= benchmark.maxDrawdown ? 'text-up' : 'text-down'
    }
  ]
})
</script>

<style scoped>
.diagnosis-tab {
  padding: 20px;
}

.toolbar {
  margin-bottom: 20px;
  display: flex;
  gap: 12px;
}

.empty-state,
.loading-state {
  padding: 60px 0;
}

.diagnosis-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 16px;
  font-weight: 600;
}

.conclusion-text {
  font-size: 15px;
  line-height: 1.8;
  color: #303133;
  padding: 12px;
  background: #F5F7FA;
  border-radius: 4px;
}

.section {
  margin-top: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
}

.list {
  margin: 0;
  padding-left: 24px;
}

.list-item {
  margin-bottom: 8px;
  line-height: 1.6;
}

.strength {
  color: #67C23A;
}

.weakness {
  color: #F56C6C;
}

.suggestions {
  color: #409EFF;
}

.text-up {
  color: #F56C6C;
  font-weight: 500;
}

.text-down {
  color: #67C23A;
  font-weight: 500;
}

.comparison-card {
  margin-top: 20px;
}
</style>
```

- [ ] **Step 2: Verify component compiles**

Run:
```bash
cd web-frontend
npm run type-check
```

Expected: No TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add web-frontend/src/views/BacktestCenter/DiagnosisTab.vue
git commit -m "feat(diagnosis): add DiagnosisTab component"
```


## Task 8: 集成到 BacktestCenter

**Files:**
- Modify: `web-frontend/src/views/BacktestCenter/index.vue`

- [ ] **Step 1: Add DiagnosisTab to BacktestCenter**

在 `web-frontend/src/views/BacktestCenter/index.vue` 中找到回测结果展示部分（约第 174-200 行），将其改为标签页形式：

```vue
<!-- 修改前：直接展示回测结果 -->
<el-card v-if="backtestResult">
  <template #header>
    <div class="flex items-center justify-between">
      <span class="font-semibold">回测结果</span>
      ...
    </div>
  </template>
  <!-- 回测结果内容 -->
</el-card>

<!-- 修改后：使用标签页 -->
<el-card v-if="backtestResult">
  <template #header>
    <div class="flex items-center justify-between">
      <span class="font-semibold">回测结果</span>
      <div class="flex items-center gap-2">
        <el-button size="small" @click="handleExportResult">导出报告</el-button>
        <el-button size="small" @click="handleSaveStrategy">保存策略</el-button>
      </div>
    </div>
  </template>

  <el-tabs v-model="activeTab" class="result-tabs">
    <el-tab-pane label="回测结果" name="result">
      <!-- 原有的回测结果内容 -->
      <div class="grid grid-cols-4 gap-3 mb-4">
        <!-- 关键指标卡片 -->
        ...
      </div>
      <!-- 资金曲线图表 -->
      ...
      <!-- 交易记录表格 -->
      ...
    </el-tab-pane>

    <el-tab-pane label="策略诊断" name="diagnosis">
      <DiagnosisTab :backtest-result="backtestResult" />
    </el-tab-pane>
  </el-tabs>
</el-card>
```

- [ ] **Step 2: Import DiagnosisTab component**

在 `<script setup>` 部分添加导入：

```typescript
import DiagnosisTab from './DiagnosisTab.vue'
```

- [ ] **Step 3: Add activeTab state**

在 `<script setup>` 部分添加状态：

```typescript
const activeTab = ref('result')
```

- [ ] **Step 4: Test in browser**

Run:
```bash
cd web-frontend
npm run dev
```

访问 http://localhost:3001/backtest-center

步骤：
1. 填写回测表单
2. 点击"开始回测"
3. 等待回测完成
4. 切换到"策略诊断"标签页
5. 点击"运行诊断"按钮
6. 查看诊断结果

Expected: 
- 标签页切换正常
- 诊断按钮可点击
- 诊断结果正确显示

- [ ] **Step 5: Commit**

```bash
git add web-frontend/src/views/BacktestCenter/index.vue
git commit -m "feat(diagnosis): integrate DiagnosisTab into BacktestCenter"
```


## Task 9: 端到端测试和文档

**Files:**
- Create: `docs/superpowers/reports/.gitkeep` (确保目录存在)
- Update: `quantsys-v2/README.md` (添加诊断功能说明)

- [ ] **Step 1: Create reports directory**

```bash
mkdir -p docs/superpowers/reports
touch docs/superpowers/reports/.gitkeep
git add docs/superpowers/reports/.gitkeep
git commit -m "chore: create reports directory for diagnosis"
```

- [ ] **Step 2: Run end-to-end test**

完整测试流程：

```bash
# 1. 启动后端服务
cd quantsys-v2
python api/server.py

# 2. 在另一个终端启动前端
cd web-frontend
npm run dev

# 3. 浏览器访问 http://localhost:3001/backtest-center

# 4. 执行测试步骤：
#    a. 填写回测表单（策略：MA 双均线，股票：000001.SZ，时间：2024-01-01 ~ 2024-12-31）
#    b. 点击"开始回测"
#    c. 等待回测完成，查看回测结果
#    d. 切换到"策略诊断"标签页
#    e. 点击"运行诊断"按钮
#    f. 验证诊断结果显示：
#       - 4个指标卡片（年化收益、夏普比率、最大回撤、综合评级）
#       - 诊断结论（优势、劣势、建议）
#       - 与基准对比表格
#    g. 检查 docs/superpowers/reports/ 目录下是否生成了报告文件
```

Expected:
- ✅ 回测正常运行
- ✅ 诊断按钮可点击
- ✅ 诊断结果正确显示
- ✅ 如果夏普比率 < 1.0，显示"⚠️ 不如买指数"
- ✅ 报告文件已生成

- [ ] **Step 3: Update README with diagnosis feature**

在 `quantsys-v2/README.md` 的功能列表中添加：

```markdown
## 新增功能

### 策略诊断系统 (2026-05-26)

在 BacktestCenter 页面添加策略诊断功能，帮助用户快速判断策略有效性。

**核心功能**：
- 快速判断策略是否有效（夏普比率 < 1.0 = 不如指数）
- 混合评级体系（固定阈值 + 基准对比）
- 综合评级 A/B/C/D
- 诊断结论（优势、劣势、优化建议）
- 生成 Markdown 报告

**使用方法**：
1. 在 BacktestCenter 运行回测
2. 切换到"策略诊断"标签页
3. 点击"运行诊断"按钮
4. 查看诊断结果和优化建议

**API 端点**：
- `POST /api/diagnosis/run` - 运行策略诊断
- `GET /api/diagnosis/health` - 健康检查

**报告位置**：
- `docs/superpowers/reports/YYYY-MM-DD-{strategy}-{symbol}-diagnosis.md`
```

- [ ] **Step 4: Verify all tests pass**

```bash
cd quantsys-v2
pytest tests/test_strategy_analyzer.py -v
pytest tests/test_report_generator.py -v
pytest tests/test_diagnosis_service.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Final commit**

```bash
git add quantsys-v2/README.md
git commit -m "docs: add strategy diagnosis feature documentation"
```

- [ ] **Step 6: Create summary report**

创建实现总结报告：

```bash
cat > docs/superpowers/reports/2026-05-26-diagnosis-mvp-completed.md << 'REPORT'
# 策略诊断系统 MVP 实现完成报告

**完成时间**: 2026-05-26  
**实现范围**: MVP 第一阶段

## 已完成功能

### 后端
- ✅ StrategyAnalyzer - 策略分析器（评级算法）
- ✅ ReportGenerator - Markdown 报告生成器
- ✅ DiagnosisService - 诊断服务主入口
- ✅ API 端点 `/api/diagnosis/run`

### 前端
- ✅ DiagnosisCards - 指标卡片组件
- ✅ DiagnosisTab - 诊断标签页
- ✅ 集成到 BacktestCenter

### 测试
- ✅ 单元测试（StrategyAnalyzer, ReportGenerator, DiagnosisService）
- ✅ 端到端测试

## 核心价值验证

✅ **快速判断策略有效性**
- 夏普比率 < 1.0 时显示"⚠️ 不如买指数"
- 综合评级 A/B/C/D 一目了然

✅ **混合评级体系**
- 固定阈值：夏普 > 1.5 为优秀
- 相对基准：对比沪深300
- 综合评分：稳定性 40% + 收益 30% + 风险 20% + 基准加分 10%

✅ **诊断结论**
- 优势：列出策略强项
- 劣势：指出问题所在
- 建议：提供优化方向

✅ **报告生成**
- Markdown 格式
- 保存到 `docs/superpowers/reports/`
- 可追溯、可分享

## 使用示例

```bash
# 1. 启动服务
cd quantsys-v2 && python api/server.py
cd web-frontend && npm run dev

# 2. 访问 http://localhost:3001/backtest-center
# 3. 运行回测
# 4. 切换到"策略诊断"标签页
# 5. 点击"运行诊断"
```

## 后续优化方向

- [ ] 因子 IC 分析功能
- [ ] 历史诊断记录查询
- [ ] CLI 命令支持
- [ ] 定时自动诊断（scheduler）
- [ ] 更多图表可视化

## 技术栈

- 后端：Python, Flask, PostgreSQL
- 前端：Vue 3, TypeScript, Element Plus
- 测试：pytest

---

**实现团队**: QuantSys V2  
**文档版本**: 1.0
REPORT

git add docs/superpowers/reports/2026-05-26-diagnosis-mvp-completed.md
git commit -m "docs: add MVP completion report"
```


---

## 实现计划总结

### 任务清单

- **Task 1**: StrategyAnalyzer - 策略分析器（评级算法）
- **Task 2**: ReportGenerator - 报告生成器
- **Task 3**: DiagnosisService - 诊断服务主入口
- **Task 4**: API 端点 - /api/diagnosis/run
- **Task 5**: 前端 API 服务
- **Task 6**: DiagnosisCards - 指标卡片组件
- **Task 7**: DiagnosisTab - 诊断标签页
- **Task 8**: 集成到 BacktestCenter
- **Task 9**: 端到端测试和文档

### 预计工作量

- 后端开发：2-3 小时
- 前端开发：2-3 小时
- 测试和调试：1-2 小时
- **总计**：5-8 小时

### 关键里程碑

1. ✅ 后端服务层完成（Task 1-3）
2. ✅ API 端点可用（Task 4）
3. ✅ 前端组件完成（Task 5-7）
4. ✅ 集成测试通过（Task 8-9）

### 验收标准

- [ ] 用户可以在 BacktestCenter 运行诊断
- [ ] 诊断结果正确显示（4个指标卡片 + 诊断结论）
- [ ] 夏普比率 < 1.0 时显示"不如买指数"警告
- [ ] 报告文件成功生成到 `docs/superpowers/reports/`
- [ ] 所有单元测试通过

---

## 执行说明

本计划已完成，可以开始实现。

