#!/usr/bin/env python3
"""
每周绩效分析脚本

功能：
1. 收集本周交易信号和回测数据
2. 分析信号质量和策略表现
3. 统计因子有效性
4. 生成绩效报告（Markdown + JSON）
5. 对比历史趋势
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict, Counter
import argparse

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class WeeklyPerformanceAnalyzer:
    """每周绩效分析器"""

    def __init__(self, quant_dir: str):
        self.quant_dir = quant_dir
        self.pi_invest_dir = os.path.join(quant_dir, '.pi-invest')
        self.reports_dir = os.path.join(self.pi_invest_dir, 'performance_reports')
        os.makedirs(self.reports_dir, exist_ok=True)

    def get_week_number(self, date: datetime) -> Tuple[int, int]:
        """获取年份和周数"""
        return date.isocalendar()[0], date.isocalendar()[1]

    def get_week_range(self, year: int, week: int) -> Tuple[datetime, datetime]:
        """获取指定周的日期范围"""
        # ISO周从周一开始
        jan_4 = datetime(year, 1, 4)
        week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
        target_monday = week_1_monday + timedelta(weeks=week - 1)
        target_sunday = target_monday + timedelta(days=6)
        return target_monday, target_sunday

    def collect_signals_data(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """收集指定日期范围内的信号数据"""
        all_signals = []

        # 读取当前 signals.json（最新的）
        signals_file = os.path.join(self.pi_invest_dir, 'signals.json')
        if os.path.exists(signals_file):
            try:
                with open(signals_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    signals = data.get('signals', [])

                    # 过滤本周的信号
                    for signal in signals:
                        signal_date = datetime.fromisoformat(signal['date'])
                        if start_date <= signal_date <= end_date:
                            all_signals.append(signal)

                logger.info(f"从 signals.json 读取到 {len(signals)} 条信号，本周有 {len(all_signals)} 条")
            except Exception as e:
                logger.warning(f"读取 signals.json 失败: {e}")

        # TODO: 如果有历史信号文件（按日期存储），也可以在这里读取
        # 例如: signals_2026-05-18.json

        return all_signals

    def collect_backtest_reports(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """收集回测报告"""
        reports = []

        # 查找回测报告文件
        if os.path.exists(self.pi_invest_dir):
            for filename in os.listdir(self.pi_invest_dir):
                if filename.startswith('backtest_report_') and filename.endswith('.json'):
                    filepath = os.path.join(self.pi_invest_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            report = json.load(f)
                            # 检查日期范围
                            report_date_str = filename.replace('backtest_report_', '').replace('.json', '')
                            report_date = datetime.strptime(report_date_str, '%Y-%m-%d')
                            if start_date <= report_date <= end_date:
                                reports.append(report)
                    except Exception as e:
                        logger.warning(f"读取回测报告 {filename} 失败: {e}")

        logger.info(f"找到 {len(reports)} 份本周回测报告")
        return reports

    def analyze_signal_quality(self, signals: List[Dict]) -> Dict:
        """分析信号质量"""
        if not signals:
            return {
                'total': 0,
                'buy_count': 0,
                'sell_count': 0,
                'avg_confidence': 0,
                'confidence_distribution': {},
                'strategy_distribution': {},
                'symbol_distribution': {}
            }

        buy_signals = [s for s in signals if s['signal'] == 'BUY']
        sell_signals = [s for s in signals if s['signal'] == 'SELL']

        # 信心度分布
        confidence_ranges = {
            '0.0-0.2': 0,
            '0.2-0.4': 0,
            '0.4-0.6': 0,
            '0.6-0.8': 0,
            '0.8-1.0': 0
        }

        for signal in signals:
            conf = signal['confidence']
            if conf < 0.2:
                confidence_ranges['0.0-0.2'] += 1
            elif conf < 0.4:
                confidence_ranges['0.2-0.4'] += 1
            elif conf < 0.6:
                confidence_ranges['0.4-0.6'] += 1
            elif conf < 0.8:
                confidence_ranges['0.6-0.8'] += 1
            else:
                confidence_ranges['0.8-1.0'] += 1

        # 策略分布
        strategy_counter = Counter([s['strategy'] for s in signals])

        # 股票分布
        symbol_counter = Counter([s['symbol'] for s in signals])

        return {
            'total': len(signals),
            'buy_count': len(buy_signals),
            'sell_count': len(sell_signals),
            'avg_confidence': sum(s['confidence'] for s in signals) / len(signals),
            'confidence_distribution': confidence_ranges,
            'strategy_distribution': dict(strategy_counter),
            'symbol_distribution': dict(symbol_counter.most_common(10))
        }

    def analyze_strategy_performance(self, signals: List[Dict]) -> Dict:
        """分析各策略表现"""
        strategy_stats = defaultdict(lambda: {
            'total': 0,
            'buy': 0,
            'sell': 0,
            'confidences': [],
            'avg_confidence': 0
        })

        for signal in signals:
            strategy = signal['strategy']
            strategy_stats[strategy]['total'] += 1
            strategy_stats[strategy]['confidences'].append(signal['confidence'])

            if signal['signal'] == 'BUY':
                strategy_stats[strategy]['buy'] += 1
            else:
                strategy_stats[strategy]['sell'] += 1

        # 计算平均信心度
        for strategy, stats in strategy_stats.items():
            if stats['confidences']:
                stats['avg_confidence'] = sum(stats['confidences']) / len(stats['confidences'])
            del stats['confidences']  # 删除原始数据

        return dict(strategy_stats)

    def analyze_factor_usage(self, signals: List[Dict]) -> Dict:
        """分析因子使用情况"""
        # 从信号的 reason 中提取因子名称
        factor_mentions = defaultdict(int)

        # 常见因子列表
        common_factors = [
            'RSI', 'MA5', 'MA10', 'MA20', 'MA60',
            'MACD', 'DIF', 'DEA', 'KDJ', 'K', 'D', 'J',
            'BOLL', 'ATR', 'OBV', 'CCI', 'WR'
        ]

        for signal in signals:
            reason = signal.get('reason', '')
            strategy = signal.get('strategy', '')

            # 根据策略推断使用的因子
            if 'RSI' in strategy:
                factor_mentions['RSI12'] += 1
            elif '均线' in strategy or 'MA' in strategy:
                factor_mentions['MA5'] += 1
                factor_mentions['MA20'] += 1
            elif 'MACD' in strategy:
                factor_mentions['MACD_DIF'] += 1
                factor_mentions['MACD_DEA'] += 1
            elif '布林' in strategy or 'BOLL' in strategy:
                factor_mentions['BOLL_UPPER'] += 1
                factor_mentions['BOLL_LOWER'] += 1
            elif 'KDJ' in strategy:
                factor_mentions['KDJ_K'] += 1
                factor_mentions['KDJ_D'] += 1

            # 从 reason 中提取
            for factor in common_factors:
                if factor in reason:
                    factor_mentions[factor] += 1

        # 排序
        sorted_factors = sorted(factor_mentions.items(), key=lambda x: x[1], reverse=True)

        return {
            'total_factors': len(sorted_factors),
            'most_used': dict(sorted_factors[:10]),
            'usage_summary': dict(sorted_factors)
        }

    def load_previous_report(self, year: int, week: int) -> Optional[Dict]:
        """加载上周报告"""
        # 计算上周
        prev_week = week - 1
        prev_year = year
        if prev_week < 1:
            prev_year -= 1
            prev_week = 52  # 简化处理

        filename = f"performance_report_{prev_year}-W{prev_week:02d}.json"
        filepath = os.path.join(self.reports_dir, filename)

        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"读取上周报告失败: {e}")

        return None

    def compare_with_previous(self, current: Dict, previous: Optional[Dict]) -> Dict:
        """对比上周数据"""
        if not previous:
            return {
                'available': False,
                'message': '无上周数据'
            }

        current_quality = current['signal_quality']
        prev_quality = previous['signal_quality']

        def calc_change(curr, prev):
            if prev == 0:
                return 0
            return ((curr - prev) / prev) * 100

        return {
            'available': True,
            'signal_count_change': calc_change(current_quality['total'], prev_quality['total']),
            'avg_confidence_change': calc_change(current_quality['avg_confidence'], prev_quality['avg_confidence']),
            'buy_count_change': calc_change(current_quality['buy_count'], prev_quality['buy_count']),
            'sell_count_change': calc_change(current_quality['sell_count'], prev_quality['sell_count']),
        }

    def generate_recommendations(self, analysis: Dict) -> List[str]:
        """生成优化建议"""
        recommendations = []

        signal_quality = analysis['signal_quality']
        strategy_perf = analysis['strategy_performance']

        # 1. 信号数量建议
        if signal_quality['total'] < 10:
            recommendations.append("信号数量较少，建议检查数据更新是否正常，或考虑放宽策略条件")
        elif signal_quality['total'] > 100:
            recommendations.append("信号数量较多，建议提高信号过滤标准，聚焦高质量机会")

        # 2. 信心度建议
        avg_conf = signal_quality['avg_confidence']
        if avg_conf < 0.5:
            recommendations.append(f"平均信心度较低 ({avg_conf:.2f})，建议优化策略参数或增加过滤条件")
        elif avg_conf > 0.8:
            recommendations.append(f"平均信心度很高 ({avg_conf:.2f})，策略表现优秀，可考虑增加仓位")

        # 3. 策略表现建议
        if strategy_perf:
            # 找出信号最多的策略
            top_strategy = max(strategy_perf.items(), key=lambda x: x[1]['total'])
            recommendations.append(f"'{top_strategy[0]}' 策略最活跃 ({top_strategy[1]['total']}个信号)，建议重点关注")

            # 找出信心度最高的策略
            high_conf_strategy = max(strategy_perf.items(), key=lambda x: x[1]['avg_confidence'])
            if high_conf_strategy[1]['avg_confidence'] > 0.7:
                recommendations.append(f"'{high_conf_strategy[0]}' 策略信心度最高 ({high_conf_strategy[1]['avg_confidence']:.2f})，建议增加权重")

        # 4. 买卖平衡建议
        buy_ratio = signal_quality['buy_count'] / signal_quality['total'] if signal_quality['total'] > 0 else 0
        if buy_ratio > 0.8:
            recommendations.append("买入信号占比过高，注意市场可能过热")
        elif buy_ratio < 0.2:
            recommendations.append("卖出信号占比过高，注意市场可能过冷")

        # 5. 对比建议
        comparison = analysis.get('comparison', {})
        if comparison.get('available'):
            if comparison['signal_count_change'] < -30:
                recommendations.append(f"信号数量较上周下降 {abs(comparison['signal_count_change']):.1f}%，建议检查市场环境变化")
            elif comparison['signal_count_change'] > 50:
                recommendations.append(f"信号数量较上周增长 {comparison['signal_count_change']:.1f}%，注意风险控制")

        if not recommendations:
            recommendations.append("整体表现正常，继续保持当前策略")

        return recommendations

    def generate_markdown_report(self, analysis: Dict, year: int, week: int) -> str:
        """生成 Markdown 报告"""
        start_date, end_date = self.get_week_range(year, week)

        md = f"# 每周绩效分析报告 - {year}年第{week}周\n\n"
        md += f"**分析周期**: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}\n\n"
        md += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += "---\n\n"

        # 1. 本周概况
        quality = analysis['signal_quality']
        md += "## 本周概况\n\n"

        if quality['total'] == 0:
            md += "本周暂无交易信号数据。\n\n"
            return md

        md += f"- **交易日**: {analysis['trading_days']}天\n"
        md += f"- **生成信号**: {quality['total']}个 (买入: {quality['buy_count']}, 卖出: {quality['sell_count']})\n"
        md += f"- **平均信心度**: {quality['avg_confidence']:.2f}\n"
        md += f"- **买入占比**: {quality['buy_count']/quality['total']*100:.1f}%\n\n"

        # 2. 信心度分布
        md += "### 信心度分布\n\n"
        md += "| 信心度区间 | 信号数量 | 占比 |\n"
        md += "|-----------|---------|------|\n"
        for range_name, count in quality['confidence_distribution'].items():
            pct = count / quality['total'] * 100 if quality['total'] > 0 else 0
            md += f"| {range_name} | {count} | {pct:.1f}% |\n"
        md += "\n"

        # 3. 策略表现
        md += "## 策略表现\n\n"
        strategy_perf = analysis['strategy_performance']

        if strategy_perf:
            md += "| 策略 | 信号数 | 买入 | 卖出 | 平均信心度 | 评价 |\n"
            md += "|------|--------|------|------|------------|------|\n"

            # 按信号数排序
            sorted_strategies = sorted(strategy_perf.items(), key=lambda x: x[1]['total'], reverse=True)

            for strategy, stats in sorted_strategies:
                avg_conf = stats['avg_confidence']

                # 评价
                if avg_conf >= 0.8:
                    rating = "优秀"
                elif avg_conf >= 0.6:
                    rating = "良好"
                elif avg_conf >= 0.4:
                    rating = "一般"
                else:
                    rating = "需优化"

                md += f"| {strategy} | {stats['total']} | {stats['buy']} | {stats['sell']} | {avg_conf:.2f} | {rating} |\n"
            md += "\n"
        else:
            md += "暂无策略数据。\n\n"

        # 4. 因子分析
        md += "## 因子分析\n\n"
        factor_usage = analysis['factor_usage']

        if factor_usage['most_used']:
            md += "### 最常用因子 (Top 10)\n\n"
            md += "| 因子 | 使用次数 |\n"
            md += "|------|----------|\n"
            for factor, count in factor_usage['most_used'].items():
                md += f"| {factor} | {count} |\n"
            md += "\n"
        else:
            md += "暂无因子使用数据。\n\n"

        # 5. 热门股票
        md += "## 热门股票 (Top 10)\n\n"
        if quality['symbol_distribution']:
            md += "| 股票代码 | 信号数量 |\n"
            md += "|----------|----------|\n"
            for symbol, count in quality['symbol_distribution'].items():
                md += f"| {symbol} | {count} |\n"
            md += "\n"
        else:
            md += "暂无数据。\n\n"

        # 6. 对比上周
        comparison = analysis.get('comparison', {})
        if comparison.get('available'):
            md += "## 对比上周\n\n"
            md += f"- 信号数量: {comparison['signal_count_change']:+.1f}%\n"
            md += f"- 平均信心度: {comparison['avg_confidence_change']:+.1f}%\n"
            md += f"- 买入信号: {comparison['buy_count_change']:+.1f}%\n"
            md += f"- 卖出信号: {comparison['sell_count_change']:+.1f}%\n\n"

        # 7. 优化建议
        md += "## 优化建议\n\n"
        recommendations = analysis['recommendations']
        for i, rec in enumerate(recommendations, 1):
            md += f"{i}. {rec}\n"
        md += "\n"

        # 8. 备注
        md += "---\n\n"
        md += "**备注**:\n"
        md += "- 本报告基于历史信号数据生成，不构成投资建议\n"
        md += "- 策略表现需结合实际交易结果验证\n"
        md += "- 建议定期回顾和优化策略参数\n"

        return md

    def analyze(self, year: Optional[int] = None, week: Optional[int] = None) -> Dict:
        """执行完整分析"""
        # 默认分析本周
        if year is None or week is None:
            now = datetime.now()
            year, week = self.get_week_number(now)

        logger.info(f"开始分析 {year}年第{week}周 的绩效")

        # 获取日期范围
        start_date, end_date = self.get_week_range(year, week)
        logger.info(f"日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")

        # 收集数据
        signals = self.collect_signals_data(start_date, end_date)
        backtest_reports = self.collect_backtest_reports(start_date, end_date)

        # 计算交易日（简化：周一到周五）
        trading_days = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # 0-4 是周一到周五
                trading_days += 1
            current += timedelta(days=1)

        # 分析
        signal_quality = self.analyze_signal_quality(signals)
        strategy_performance = self.analyze_strategy_performance(signals)
        factor_usage = self.analyze_factor_usage(signals)

        # 加载上周报告
        previous_report = self.load_previous_report(year, week)

        # 组装分析结果
        analysis = {
            'year': year,
            'week': week,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'trading_days': trading_days,
            'signal_quality': signal_quality,
            'strategy_performance': strategy_performance,
            'factor_usage': factor_usage,
            'backtest_count': len(backtest_reports),
            'generated_at': datetime.now().isoformat()
        }

        # 对比分析
        comparison = self.compare_with_previous(analysis, previous_report)
        analysis['comparison'] = comparison

        # 生成建议
        recommendations = self.generate_recommendations(analysis)
        analysis['recommendations'] = recommendations

        return analysis

    def save_report(self, analysis: Dict, year: int, week: int):
        """保存报告"""
        # 保存 JSON
        json_filename = f"performance_report_{year}-W{week:02d}.json"
        json_path = os.path.join(self.reports_dir, json_filename)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON 报告已保存: {json_path}")

        # 保存 Markdown
        md_content = self.generate_markdown_report(analysis, year, week)
        md_filename = f"performance_report_{year}-W{week:02d}.md"
        md_path = os.path.join(self.reports_dir, md_filename)

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(f"Markdown 报告已保存: {md_path}")

        return json_path, md_path


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='每周绩效分析')
    parser.add_argument('--year', type=int, help='年份（默认：本年）')
    parser.add_argument('--week', type=int, help='周数（默认：本周）')
    parser.add_argument('--quant-dir', type=str,
                       default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       help='Quant 项目目录')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("每周绩效分析任务开始")
    logger.info(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 创建分析器
    analyzer = WeeklyPerformanceAnalyzer(args.quant_dir)

    # 执行分析
    try:
        analysis = analyzer.analyze(args.year, args.week)

        year = analysis['year']
        week = analysis['week']

        # 保存报告
        json_path, md_path = analyzer.save_report(analysis, year, week)

        # 输出摘要
        logger.info("")
        logger.info("=" * 60)
        logger.info("分析完成")
        logger.info(f"分析周期: {year}年第{week}周")
        logger.info(f"信号总数: {analysis['signal_quality']['total']}")
        logger.info(f"平均信心度: {analysis['signal_quality']['avg_confidence']:.2f}")
        logger.info(f"活跃策略: {len(analysis['strategy_performance'])}")
        logger.info("=" * 60)

        # 显示优化建议
        logger.info("\n优化建议:")
        for i, rec in enumerate(analysis['recommendations'], 1):
            logger.info(f"  {i}. {rec}")

        logger.info(f"\n报告已保存:")
        logger.info(f"  - JSON: {json_path}")
        logger.info(f"  - Markdown: {md_path}")

    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
