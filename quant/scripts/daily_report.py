#!/usr/bin/env python3
"""
每日报告生成脚本

功能：
1. 汇总当日数据（交易信号、风险报告、ML预测）
2. 从数据库读取因子统计
3. 生成 Markdown 和 JSON 格式报告
4. 保存到 .pi-invest/daily_report_YYYY-MM-DD.md
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class DailyReportGenerator:
    """每日报告生成器"""

    def __init__(self, output_dir: str = ".pi-invest"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database()
        self.report_date = datetime.now().strftime("%Y-%m-%d")

    def load_signals(self) -> Optional[Dict]:
        """加载交易信号"""
        signals_file = self.output_dir / "signals.json"
        try:
            if signals_file.exists():
                with open(signals_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"加载信号文件: {len(data.get('signals', []))} 个信号")
                    return data
            else:
                logger.warning(f"信号文件不存在: {signals_file}")
                return None
        except Exception as e:
            logger.error(f"加载信号文件失败: {e}")
            return None

    def load_risk_report(self) -> Optional[Dict]:
        """加载风险报告"""
        risk_file = self.output_dir / "risk_report.json"
        try:
            if risk_file.exists():
                with open(risk_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"加载风险报告: {len(data.get('positions', []))} 个持仓")
                    return data
            else:
                logger.info("风险报告文件不存在（可能没有持仓）")
                return None
        except Exception as e:
            logger.error(f"加载风险报告失败: {e}")
            return None

    def load_ml_predictions(self) -> Optional[Dict]:
        """加载ML预测"""
        ml_file = self.output_dir / "ml_predictions.json"
        try:
            if ml_file.exists():
                with open(ml_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"加载ML预测: {len(data.get('predictions', []))} 个预测")
                    return data
            else:
                logger.info("ML预测文件不存在（待实现）")
                return None
        except Exception as e:
            logger.error(f"加载ML预测失败: {e}")
            return None

    def get_market_overview(self) -> Dict[str, Any]:
        """获取市场概况"""
        try:
            conn = self.db._get_connection()

            # 获取股票总数
            total_stocks = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]

            # 获取最新K线日期
            latest_date_row = conn.execute("SELECT MAX(date) FROM daily_klines").fetchone()
            latest_date = latest_date_row[0] if latest_date_row and latest_date_row[0] else "未知"

            # 获取有K线数据的股票数
            stocks_with_klines = conn.execute(
                "SELECT COUNT(DISTINCT symbol) FROM daily_klines"
            ).fetchone()[0]

            # 获取因子覆盖情况（如果factor_values表存在）
            try:
                factor_coverage = conn.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM factor_values WHERE date = ?",
                    (latest_date,)
                ).fetchone()[0]
            except Exception:
                factor_coverage = 0

            # 计算因子覆盖率
            coverage_rate = (factor_coverage / stocks_with_klines * 100) if stocks_with_klines > 0 else 0

            return {
                "total_stocks": total_stocks,
                "stocks_with_klines": stocks_with_klines,
                "latest_date": latest_date,
                "factor_coverage": factor_coverage,
                "coverage_rate": coverage_rate
            }
        except Exception as e:
            logger.error(f"获取市场概况失败: {e}")
            return {
                "total_stocks": 0,
                "stocks_with_klines": 0,
                "latest_date": "未知",
                "factor_coverage": 0,
                "coverage_rate": 0
            }

    def get_factor_stats(self) -> Dict[str, Any]:
        """获取因子统计"""
        try:
            conn = self.db._get_connection()

            # 获取最新日期
            latest_date_row = conn.execute("SELECT MAX(date) FROM daily_klines").fetchone()
            latest_date = latest_date_row[0] if latest_date_row and latest_date_row[0] else None

            if not latest_date:
                return {"factor_count": 0, "factors": []}

            # 获取因子统计
            try:
                factor_stats = conn.execute("""
                    SELECT factor_name, COUNT(*) as count
                    FROM factor_values
                    WHERE date = ?
                    GROUP BY factor_name
                    ORDER BY factor_name
                """, (latest_date,)).fetchall()

                factors = [
                    {"name": row[0], "count": row[1]}
                    for row in factor_stats
                ]

                return {
                    "factor_count": len(factors),
                    "factors": factors
                }
            except Exception:
                return {"factor_count": 0, "factors": []}

        except Exception as e:
            logger.error(f"获取因子统计失败: {e}")
            return {"factor_count": 0, "factors": []}

    def generate_markdown_report(
        self,
        market_overview: Dict,
        signals_data: Optional[Dict],
        risk_data: Optional[Dict],
        ml_data: Optional[Dict],
        factor_stats: Dict
    ) -> str:
        """生成Markdown格式报告"""

        lines = [
            f"# 量化系统每日报告 - {self.report_date}",
            "",
            "## 📊 市场概况",
            f"- 股票总数: {market_overview['total_stocks']}只",
            f"- K线数据覆盖: {market_overview['stocks_with_klines']}只",
            f"- 最新日期: {market_overview['latest_date']}",
            f"- 因子覆盖: {market_overview['factor_coverage']}只 ({market_overview['coverage_rate']:.1f}%)",
            ""
        ]

        # 交易信号部分
        if signals_data:
            summary = signals_data.get('summary', {})
            signals = signals_data.get('signals', [])

            lines.extend([
                "## 🎯 交易信号",
                f"- 总信号数: {summary.get('total', 0)}个",
                f"- 买入信号: {summary.get('buy', 0)}个",
                f"- 卖出信号: {summary.get('sell', 0)}个",
                ""
            ])

            # Top 5 买入信号
            buy_signals = [s for s in signals if s.get('signal') == 'BUY']
            buy_signals.sort(key=lambda x: x.get('confidence', 0), reverse=True)

            if buy_signals:
                lines.append("### Top 5 买入信号")
                for i, signal in enumerate(buy_signals[:5], 1):
                    lines.append(
                        f"{i}. **{signal['symbol']}** - {signal['strategy']} "
                        f"(信心度: {signal['confidence']:.2f})"
                    )
                    lines.append(f"   - {signal['reason']}")
                    lines.append(f"   - 价格: ¥{signal['price']:.2f}")
                lines.append("")

            # Top 5 卖出信号
            sell_signals = [s for s in signals if s.get('signal') == 'SELL']
            sell_signals.sort(key=lambda x: x.get('confidence', 0), reverse=True)

            if sell_signals:
                lines.append("### Top 5 卖出信号")
                for i, signal in enumerate(sell_signals[:5], 1):
                    lines.append(
                        f"{i}. **{signal['symbol']}** - {signal['strategy']} "
                        f"(信心度: {signal['confidence']:.2f})"
                    )
                    lines.append(f"   - {signal['reason']}")
                    lines.append(f"   - 价格: ¥{signal['price']:.2f}")
                lines.append("")
        else:
            lines.extend([
                "## 🎯 交易信号",
                "- 暂无信号数据",
                ""
            ])

        # 因子分布部分
        if factor_stats['factor_count'] > 0:
            lines.extend([
                "## 📈 因子分布",
                f"- 因子种类: {factor_stats['factor_count']}个",
                ""
            ])
            for factor in factor_stats['factors']:
                lines.append(f"- {factor['name']}: {factor['count']}只股票")
            lines.append("")
        else:
            lines.extend([
                "## 📈 因子分布",
                "- 暂无因子数据",
                ""
            ])

        # 风险预警部分
        if risk_data:
            positions = risk_data.get('positions', [])
            warnings = risk_data.get('warnings', [])

            lines.extend([
                "## ⚠️ 风险预警",
                f"- 持仓数量: {len(positions)}只",
                f"- 预警数量: {len(warnings)}个",
                ""
            ])

            if warnings:
                lines.append("### 风险预警详情")
                for warning in warnings[:10]:  # 最多显示10个
                    lines.append(f"- **{warning.get('symbol', 'N/A')}**: {warning.get('message', 'N/A')}")
                lines.append("")
        else:
            lines.extend([
                "## ⚠️ 风险预警",
                "- 暂无持仓，无风险预警",
                ""
            ])

        # ML预测部分
        if ml_data:
            predictions = ml_data.get('predictions', [])
            bullish = len([p for p in predictions if p.get('direction') == 'UP'])
            bearish = len([p for p in predictions if p.get('direction') == 'DOWN'])

            lines.extend([
                "## 🤖 ML预测",
                f"- 预测数量: {len(predictions)}只",
                f"- 看涨: {bullish}只",
                f"- 看跌: {bearish}只",
                ""
            ])

            # Top 5 看涨预测
            bullish_predictions = [p for p in predictions if p.get('direction') == 'UP']
            bullish_predictions.sort(key=lambda x: x.get('confidence', 0), reverse=True)

            if bullish_predictions:
                lines.append("### Top 5 看涨预测")
                for i, pred in enumerate(bullish_predictions[:5], 1):
                    lines.append(
                        f"{i}. **{pred['symbol']}** - 信心度: {pred['confidence']:.2f}"
                    )
                lines.append("")
        else:
            lines.extend([
                "## 🤖 ML预测",
                "- ML预测功能待实现",
                ""
            ])

        # 报告生成时间
        lines.extend([
            "---",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])

        return "\n".join(lines)

    def generate_json_report(
        self,
        market_overview: Dict,
        signals_data: Optional[Dict],
        risk_data: Optional[Dict],
        ml_data: Optional[Dict],
        factor_stats: Dict
    ) -> Dict:
        """生成JSON格式报告"""
        return {
            "generated_at": datetime.now().isoformat(),
            "report_date": self.report_date,
            "market_overview": market_overview,
            "signals": signals_data.get('summary', {}) if signals_data else {},
            "risk": {
                "positions_count": len(risk_data.get('positions', [])) if risk_data else 0,
                "warnings_count": len(risk_data.get('warnings', [])) if risk_data else 0
            },
            "ml_predictions": {
                "total": len(ml_data.get('predictions', [])) if ml_data else 0,
                "bullish": len([p for p in ml_data.get('predictions', []) if p.get('direction') == 'UP']) if ml_data else 0,
                "bearish": len([p for p in ml_data.get('predictions', []) if p.get('direction') == 'DOWN']) if ml_data else 0
            },
            "factor_stats": factor_stats
        }

    def save_reports(self, markdown_content: str, json_data: Dict):
        """保存报告文件"""
        # 保存Markdown报告
        md_filename = f"daily_report_{self.report_date}.md"
        md_path = self.output_dir / md_filename
        try:
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            logger.info(f"Markdown报告已保存: {md_path}")
        except Exception as e:
            logger.error(f"保存Markdown报告失败: {e}")

        # 保存JSON报告
        json_path = self.output_dir / "daily_report.json"
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON报告已保存: {json_path}")
        except Exception as e:
            logger.error(f"保存JSON报告失败: {e}")

    def generate(self):
        """生成每日报告"""
        logger.info("=" * 60)
        logger.info("开始生成每日报告")
        logger.info("=" * 60)

        try:
            # 加载数据
            logger.info("1. 加载数据...")
            signals_data = self.load_signals()
            risk_data = self.load_risk_report()
            ml_data = self.load_ml_predictions()

            # 获取统计信息
            logger.info("2. 获取统计信息...")
            market_overview = self.get_market_overview()
            factor_stats = self.get_factor_stats()

            # 生成报告
            logger.info("3. 生成报告...")
            markdown_content = self.generate_markdown_report(
                market_overview, signals_data, risk_data, ml_data, factor_stats
            )
            json_data = self.generate_json_report(
                market_overview, signals_data, risk_data, ml_data, factor_stats
            )

            # 保存报告
            logger.info("4. 保存报告...")
            self.save_reports(markdown_content, json_data)

            # 打印报告摘要
            logger.info("=" * 60)
            logger.info("报告生成完成")
            logger.info("=" * 60)
            print("\n" + markdown_content)

            return True

        except Exception as e:
            logger.error(f"生成报告失败: {e}", exc_info=True)
            return False
        finally:
            self.db.close()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='生成量化系统每日报告')
    parser.add_argument(
        '--output-dir',
        default='.pi-invest',
        help='输出目录 (默认: .pi-invest)'
    )

    args = parser.parse_args()

    generator = DailyReportGenerator(output_dir=args.output_dir)
    success = generator.generate()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
