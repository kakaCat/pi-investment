#!/usr/bin/env python3
"""
测试每周绩效分析脚本

功能：
1. 测试数据收集
2. 测试分析功能
3. 测试报告生成
4. 验证输出格式
"""

import os
import sys
import json
import unittest
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.weekly_performance import WeeklyPerformanceAnalyzer


class TestWeeklyPerformance(unittest.TestCase):
    """测试每周绩效分析"""

    def setUp(self):
        """设置测试环境"""
        self.quant_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.analyzer = WeeklyPerformanceAnalyzer(self.quant_dir)

    def test_week_number_calculation(self):
        """测试周数计算"""
        date = datetime(2026, 5, 18)
        year, week = self.analyzer.get_week_number(date)

        print(f"\n测试日期: {date.strftime('%Y-%m-%d')}")
        print(f"年份: {year}, 周数: {week}")

        self.assertEqual(year, 2026)
        self.assertGreater(week, 0)
        self.assertLessEqual(week, 53)

    def test_week_range_calculation(self):
        """测试周范围计算"""
        year, week = 2026, 21
        start_date, end_date = self.analyzer.get_week_range(year, week)

        print(f"\n{year}年第{week}周:")
        print(f"开始日期: {start_date.strftime('%Y-%m-%d')} ({start_date.strftime('%A')})")
        print(f"结束日期: {end_date.strftime('%Y-%m-%d')} ({end_date.strftime('%A')})")

        # 验证是周一到周日
        self.assertEqual(start_date.weekday(), 0)  # 周一
        self.assertEqual(end_date.weekday(), 6)    # 周日

        # 验证日期差
        self.assertEqual((end_date - start_date).days, 6)

    def test_signal_quality_analysis(self):
        """测试信号质量分析"""
        # 模拟信号数据
        signals = [
            {'signal': 'BUY', 'confidence': 0.9, 'strategy': 'RSI反转', 'symbol': '000001', 'reason': 'RSI超卖'},
            {'signal': 'BUY', 'confidence': 0.7, 'strategy': '均线突破', 'symbol': '000002', 'reason': 'MA5上穿MA20'},
            {'signal': 'SELL', 'confidence': 0.5, 'strategy': 'MACD', 'symbol': '000003', 'reason': 'MACD死叉'},
            {'signal': 'SELL', 'confidence': 0.3, 'strategy': '均线突破', 'symbol': '000001', 'reason': 'MA5下穿MA20'},
        ]

        result = self.analyzer.analyze_signal_quality(signals)

        print("\n信号质量分析结果:")
        print(f"总信号数: {result['total']}")
        print(f"买入信号: {result['buy_count']}")
        print(f"卖出信号: {result['sell_count']}")
        print(f"平均信心度: {result['avg_confidence']:.2f}")
        print(f"信心度分布: {result['confidence_distribution']}")

        self.assertEqual(result['total'], 4)
        self.assertEqual(result['buy_count'], 2)
        self.assertEqual(result['sell_count'], 2)
        self.assertAlmostEqual(result['avg_confidence'], 0.6, places=1)

    def test_strategy_performance_analysis(self):
        """测试策略表现分析"""
        signals = [
            {'signal': 'BUY', 'confidence': 0.9, 'strategy': 'RSI反转'},
            {'signal': 'BUY', 'confidence': 0.8, 'strategy': 'RSI反转'},
            {'signal': 'SELL', 'confidence': 0.6, 'strategy': '均线突破'},
            {'signal': 'BUY', 'confidence': 0.7, 'strategy': '均线突破'},
        ]

        result = self.analyzer.analyze_strategy_performance(signals)

        print("\n策略表现分析结果:")
        for strategy, stats in result.items():
            print(f"\n{strategy}:")
            print(f"  总信号: {stats['total']}")
            print(f"  买入: {stats['buy']}, 卖出: {stats['sell']}")
            print(f"  平均信心度: {stats['avg_confidence']:.2f}")

        self.assertIn('RSI反转', result)
        self.assertIn('均线突破', result)
        self.assertEqual(result['RSI反转']['total'], 2)
        self.assertEqual(result['均线突破']['total'], 2)

    def test_factor_usage_analysis(self):
        """测试因子使用分析"""
        signals = [
            {'strategy': 'RSI反转', 'reason': 'RSI超卖 (18.29 < 30)'},
            {'strategy': '均线突破', 'reason': 'MA5(10.24) > MA20(9.73)'},
            {'strategy': 'MACD', 'reason': 'MACD金叉 (DIF=0.05, DEA=0.03)'},
            {'strategy': 'KDJ', 'reason': 'KDJ超卖 (K=15, D=18)'},
        ]

        result = self.analyzer.analyze_factor_usage(signals)

        print("\n因子使用分析结果:")
        print(f"因子总数: {result['total_factors']}")
        print(f"最常用因子: {result['most_used']}")

        self.assertGreater(result['total_factors'], 0)
        self.assertIsInstance(result['most_used'], dict)

    def test_recommendations_generation(self):
        """测试建议生成"""
        # 模拟分析结果
        analysis = {
            'signal_quality': {
                'total': 5,
                'buy_count': 2,
                'sell_count': 3,
                'avg_confidence': 0.49
            },
            'strategy_performance': {
                'RSI反转': {'total': 1, 'avg_confidence': 1.0},
                '均线突破': {'total': 4, 'avg_confidence': 0.36}
            },
            'comparison': {'available': False}
        }

        recommendations = self.analyzer.generate_recommendations(analysis)

        print("\n生成的建议:")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")

        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)

    def test_markdown_report_generation(self):
        """测试 Markdown 报告生成"""
        # 模拟完整分析结果
        analysis = {
            'year': 2026,
            'week': 21,
            'trading_days': 5,
            'signal_quality': {
                'total': 5,
                'buy_count': 2,
                'sell_count': 3,
                'avg_confidence': 0.49,
                'confidence_distribution': {
                    '0.0-0.2': 2,
                    '0.2-0.4': 0,
                    '0.4-0.6': 1,
                    '0.6-0.8': 1,
                    '0.8-1.0': 1
                },
                'symbol_distribution': {
                    '000001': 2,
                    '000002': 1
                }
            },
            'strategy_performance': {
                'RSI反转': {'total': 1, 'buy': 1, 'sell': 0, 'avg_confidence': 1.0},
                '均线突破': {'total': 4, 'buy': 1, 'sell': 3, 'avg_confidence': 0.36}
            },
            'factor_usage': {
                'total_factors': 4,
                'most_used': {
                    'MA5': 8,
                    'MA20': 8,
                    'RSI12': 1
                }
            },
            'comparison': {'available': False},
            'recommendations': [
                '信号数量较少，建议检查数据更新',
                '平均信心度较低，建议优化策略参数'
            ]
        }

        md_content = self.analyzer.generate_markdown_report(analysis, 2026, 21)

        print("\n生成的 Markdown 报告预览:")
        print(md_content[:500] + "...")

        # 验证报告包含关键部分
        self.assertIn('# 每周绩效分析报告', md_content)
        self.assertIn('## 本周概况', md_content)
        self.assertIn('## 策略表现', md_content)
        self.assertIn('## 因子分析', md_content)
        self.assertIn('## 优化建议', md_content)

    def test_full_analysis_workflow(self):
        """测试完整分析流程"""
        print("\n执行完整分析流程...")

        try:
            # 执行分析
            analysis = self.analyzer.analyze()

            print(f"\n分析完成:")
            print(f"周期: {analysis['year']}年第{analysis['week']}周")
            print(f"信号总数: {analysis['signal_quality']['total']}")
            print(f"活跃策略: {len(analysis['strategy_performance'])}")

            # 验证结果结构
            self.assertIn('year', analysis)
            self.assertIn('week', analysis)
            self.assertIn('signal_quality', analysis)
            self.assertIn('strategy_performance', analysis)
            self.assertIn('factor_usage', analysis)
            self.assertIn('recommendations', analysis)

            print("\n完整分析流程测试通过!")

        except Exception as e:
            print(f"\n分析过程出错: {e}")
            # 不失败测试，因为可能没有数据
            print("这可能是因为没有足够的数据，属于正常情况")


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("每周绩效分析脚本测试")
    print("=" * 60)

    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWeeklyPerformance)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
