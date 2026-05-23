#!/usr/bin/env python3
"""
每日报告生成脚本（HTTP 客户端版）

通过 Flask API 获取数据，生成本地 Markdown + JSON 报告。
前置条件: Flask API 服务运行在 127.0.0.1:5002（可通过 QUANT_API_URL 环境变量覆盖）
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import requests

API_BASE = os.getenv("QUANT_API_URL", "http://127.0.0.1:5002")

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
        self.report_date = datetime.now().strftime("%Y-%m-%d")

    def _api_get(self, path: str, **kwargs) -> dict:
        try:
            resp = requests.get(f"{API_BASE}{path}", timeout=kwargs.pop('timeout', 30), **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"API 请求失败 {path}: {e}")
            return {}

    def _api_post(self, path: str, json_data: dict = None, **kwargs) -> dict:
        try:
            resp = requests.post(f"{API_BASE}{path}", json=json_data or {},
                               timeout=kwargs.pop('timeout', 30), **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"API 请求失败 {path}: {e}")
            return {}

    def load_signals(self) -> Optional[Dict]:
        """从 API 加载交易信号"""
        data = self._api_get('/api/signals')
        signals = data.get('signals', [])
        if signals:
            logger.info(f"加载信号: {len(signals)} 个")
        return data

    def load_risk(self) -> Optional[Dict]:
        """从 API 加载风险检查结果"""
        data = self._api_post('/api/risk/check')
        if data.get('checks'):
            logger.info(f"加载风险检查: {len(data['checks'])} 个持仓")
        return data

    def load_market_overview(self) -> Dict:
        """从 API 获取市场概况"""
        data = self._api_get('/api/stocks/data-status')
        return {
            "total_stocks": data.get('total_stocks', 0),
            "stocks_with_klines": data.get('complete_stocks', 0),
            "latest_date": data.get('stocks', [{}])[0].get('latest_date', '未知') if data.get('stocks') else '未知',
            "factor_coverage": data.get('complete_stocks', 0),
            "coverage_rate": (data.get('complete_stocks', 0) / max(data.get('total_stocks', 1), 1)) * 100
        }

    def generate_markdown(self, market: Dict, signals_data: Dict,
                          risk_data: Dict, ml_data: Dict = None) -> str:
        lines = [
            f"# 量化系统每日报告 - {self.report_date}",
            "",
            "## 📊 市场概况",
            f"- 股票总数: {market.get('total_stocks', 0)}只",
            f"- K线覆盖: {market.get('stocks_with_klines', 0)}只",
            f"- 最新数据: {market.get('latest_date', '未知')}",
            f"- 因子覆盖: {market.get('factor_coverage', 0)}只 ({market.get('coverage_rate', 0):.1f}%)",
            ""
        ]

        # 信号
        signals = signals_data.get('signals', [])
        buy_signals = [s for s in signals if s.get('signal') == 'BUY']
        sell_signals = [s for s in signals if s.get('signal') == 'SELL']

        lines.extend([
            "## 🎯 交易信号",
            f"- 总信号: {len(signals)}个 | 买入: {len(buy_signals)} | 卖出: {len(sell_signals)}",
            ""
        ])

        if buy_signals:
            buy_signals.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            lines.append("### Top 5 买入信号")
            for i, s in enumerate(buy_signals[:5], 1):
                lines.append(f"{i}. **{s.get('symbol', '?')}** - {s.get('strategy', '')} "
                           f"(信心度: {s.get('confidence', 0):.2f})")
                lines.append(f"   价格: ¥{s.get('price', 0):.2f} | {s.get('reason', '')}")
            lines.append("")

        # 风险
        checks = risk_data.get('checks', [])
        risk_level = risk_data.get('risk_level', 'unknown')
        risk_score = risk_data.get('risk_score', 100)
        lines.extend([
            "## ⚠️ 风险预警",
            f"- 持仓: {len(checks)}只 | 评分: {risk_score}/100 | 等级: {risk_level}",
            ""
        ])
        for c in checks:
            for w in c.get('checks', []):
                lines.append(f"- **{c['symbol']}**: {w.get('message', '')}")
        lines.append("")

        # 页脚
        lines.extend([
            "---",
            f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])
        return "\n".join(lines)

    def generate(self):
        logger.info("=" * 60)
        logger.info("开始生成每日报告 (API 模式)")
        logger.info("=" * 60)

        # 检查 API
        try:
            requests.get(f"{API_BASE}/api/health", timeout=5)
        except requests.ConnectionError:
            logger.error(f"❌ 无法连接到 API ({API_BASE})")
            return False

        # 加载数据
        logger.info("1. 加载数据...")
        signals_data = self.load_signals()
        risk_data = self.load_risk()
        market = self.load_market_overview()

        # 生成报告
        logger.info("2. 生成报告...")
        md = self.generate_markdown(market, signals_data, risk_data)

        # 保存
        logger.info("3. 保存报告...")
        md_path = self.output_dir / f"daily_report_{self.report_date}.md"
        json_path = self.output_dir / "daily_report.json"

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md)
        logger.info(f"✅ Markdown → {md_path}")

        json_data = {
            "generated_at": datetime.now().isoformat(),
            "report_date": self.report_date,
            "market_overview": market,
            "signals": signals_data.get('summary', {}),
            "risk": risk_data
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ JSON → {json_path}")

        print("\n" + md)
        return True


def main():
    parser = argparse.ArgumentParser(description='生成每日报告')
    parser.add_argument('--output-dir', default='.pi-invest', help='输出目录')
    args = parser.parse_args()

    generator = DailyReportGenerator(output_dir=args.output_dir)
    success = generator.generate()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    import argparse
    main()
