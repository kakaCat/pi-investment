"""
AkshareSectorProvider - 板块列表备选数据源（eastmoney 单一源的 failover 备选）

2026-09-01 (investor w-8366e526)：sector_providers 原只有 EastmoneySectorProvider
单一源，外部源故障/超时（实测 12.8-20s 抖动卡 20s 阈值）时板块列表断链。
本 provider 作为 failover 备选，走与东财完全独立的通道：

- 行业板块：新浪行业（ak.stock_sector_spot，sina 通道，49 个大类行业，~0.1s）
- 概念板块：同花顺概念（ak.stock_board_concept_name_ths，ths 通道，375 个概念，~5s）

字段差异（与东财对齐，缺失字段填默认值）：
- 新浪行业：有 板块/涨跌幅/涨跌额，无总市值（market_cap=0）
- 同花顺概念：仅 名称/代码（change_pct/change_amount/market_cap 均为 0）

get_sector_stocks 返回 None：板块成分查询仍由 eastmoney 提供（本 provider 不
实现成分能力，failover 时 _try_providers 会跳过/失败并继续下一个）。
"""
import logging
from datetime import datetime
from typing import Optional

from adapters.outbound.datasources.base import MarketProvider
from adapters.outbound.datasources.models import MarketData

logger = logging.getLogger(__name__)


class AkshareSectorProvider(MarketProvider):
    """A股板块列表备选数据源（新浪行业 + 同花顺概念）"""

    @property
    def name(self) -> str:
        return "akshare"

    # ── 板块列表（行业板块 + 概念板块）────────────────────────────

    def get_sector_list(self) -> Optional[MarketData]:
        """获取行业板块和概念板块列表（备选通道）。

        Returns:
            MarketData(data_type='sector_list')，data 含 industries[] 和 concepts[]。
            网络全部失败时抛异常（交给 manager 故障转移）。
        """
        industries = self._fetch_sina_industries()
        concepts = self._fetch_ths_concepts()

        if not industries and not concepts:
            raise RuntimeError("akshare sector: no data available")

        return MarketData(
            data_type='sector_list',
            data={
                'industries': industries,
                'concepts': concepts,
                'total': len(industries) + len(concepts),
                'industry_count': len(industries),
                'concept_count': len(concepts),
            },
            source=self.name,
            timestamp=datetime.now().isoformat(),
        )

    # ── 新浪行业板块 ─────────────────────────────────────────────

    def _fetch_sina_industries(self) -> list:
        """新浪行业板块（sina 通道，独立于东财）。

        列：label/板块/公司家数/平均价格/涨跌额/涨跌幅/总成交量/总成交额/...
        """
        try:
            import akshare as ak

            df = ak.stock_sector_spot(indicator="新浪行业")
            if df is None or df.empty:
                return []
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    'code': str(row.get('label', '')),
                    'name': str(row.get('板块', '')),
                    'change_pct': self._safe_float(row.get('涨跌幅')),
                    'change_amount': self._safe_float(row.get('涨跌额')),
                    'market_cap': 0.0,  # 新浪行业接口无总市值
                })
            logger.info('akshare 新浪行业: %d 个板块', len(rows))
            return rows
        except Exception as e:  # noqa: BLE001
            logger.warning('akshare 新浪行业获取失败: %s', e)
            return []

    # ── 同花顺概念板块 ───────────────────────────────────────────

    def _fetch_ths_concepts(self) -> list:
        """同花顺概念板块（ths 通道，独立于东财）。

        仅返回 名称/代码 两列（akshare 1.18 版接口），涨跌幅等字段缺失填 0。
        """
        try:
            import akshare as ak

            df = ak.stock_board_concept_name_ths()
            if df is None or df.empty:
                return []
            rows = []
            for _, row in df.iterrows():
                rows.append({
                    'code': str(row.get('code', '')),
                    'name': str(row.get('name', '')),
                    'change_pct': 0.0,
                    'change_amount': 0.0,
                    'market_cap': 0.0,
                })
            logger.info('akshare 同花顺概念: %d 个板块', len(rows))
            return rows
        except Exception as e:  # noqa: BLE001
            logger.warning('akshare 同花顺概念获取失败: %s', e)
            return []

    # ── 板块成分（本 provider 不实现，返回 None 交给 failover） ──

    def get_sector_stocks(self, sector: str) -> Optional[MarketData]:
        return None

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        try:
            if value is None or value == '' or value == '-':
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    # ── MarketProvider 抽象方法（本 provider 未实现，返回 None） ──

    def get_market_overview(self) -> Optional[MarketData]:
        return None

    def get_lhb_stock(self, symbol: str, date: str) -> Optional[MarketData]:
        return None

    def get_lhb_daily(self, date: str) -> Optional[MarketData]:
        return None
