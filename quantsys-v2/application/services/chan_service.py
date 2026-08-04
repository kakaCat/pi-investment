"""缠论分析服务"""
from datetime import datetime, timedelta
from typing import Dict, List, Any
import pandas as pd

from domain.chan.chan_analyzer import ChanAnalyzer
from domain.chan.types import Bi, Segment, ZhongShu, BuyPoint
from adapters.outbound.repositories import KlineORMRepository


class ChanService:
    """缠论分析服务"""

    def __init__(self):
        self.analyzer = ChanAnalyzer()
        self.kline_repo = KlineORMRepository()

    def analyze(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        buypoint_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        执行缠论分析

        Args:
            symbol: 股票代码（如 600519.SH）
            start_date: 开始日期（默认最近1年）
            end_date: 结束日期（默认今天）
            buypoint_types: 买卖点类型过滤（如 ['1买', '2买']）

        Returns:
            缠论分析结果
        """
        # 默认日期范围
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        # 获取K线数据
        klines_df = self._fetch_kline_data(symbol, start_date, end_date)

        if klines_df.empty:
            return {
                "symbol": symbol,
                "trend_type": "无数据",
                "bis": [],
                "segments": [],
                "zhongshus": [],
                "buypoints": [],
                "klines": []
            }

        # 执行缠论分析
        result = self.analyzer.analyze(symbol, klines_df, buypoint_types)

        # 转换为前端格式
        return {
            "symbol": symbol,
            "trend_type": result.trend_type,
            "bis": [self._format_bi(bi) for bi in result.bis],
            "segments": [self._format_segment(seg) for seg in result.segments],
            "zhongshus": [self._format_zhongshu(zs) for zs in result.zhongshus],
            "buypoints": [self._format_buypoint(bp) for bp in result.buypoints],
            "klines": self._format_klines(result.klines)
        }

    def _fetch_kline_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取K线数据"""
        try:
            # 使用 KlineRepository 获取数据（返回 polars DataFrame）
            pl_df = self.kline_repo.get_daily_klines(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            if pl_df.is_empty():
                return pd.DataFrame()

            # 转换为 pandas DataFrame
            df = pl_df.to_pandas()

            # 确保有所需的列
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']

            # 检查并转换列名（如果需要）
            if 'trade_date' in df.columns and 'date' not in df.columns:
                df = df.rename(columns={'trade_date': 'date'})

            for col in required_cols:
                if col not in df.columns:
                    if col == 'volume':
                        df[col] = 0
                    else:
                        raise ValueError(f"缺少必需列: {col}")

            return df[required_cols]

        except Exception as e:
            print(f"获取K线数据失败: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def _format_bi(self, bi: Bi) -> Dict[str, Any]:
        """格式化笔数据（契约对齐 domain.chan.types.Bi：
        start_fenxing/end_fenxing/price_change）"""
        return {
            "direction": bi.direction,
            "start_index": bi.start_fenxing.index,
            "end_index": bi.end_fenxing.index,
            "start_price": float(bi.start_fenxing.price),
            "end_price": float(bi.end_fenxing.price),
            "high": float(bi.high),
            "low": float(bi.low),
            "length": bi.length,
            "price_change": float(bi.price_change)
        }

    def _format_segment(self, segment: Segment) -> Dict[str, Any]:
        """格式化线段数据"""
        return {
            "direction": segment.direction,
            "start_index": segment.start_index,
            "end_index": segment.end_index,
            "high": float(segment.high),
            "low": float(segment.low),
            "bi_count": len(segment.bis)
        }

    def _format_zhongshu(self, zhongshu: ZhongShu) -> Dict[str, Any]:
        """格式化中枢数据"""
        return {
            "high": float(zhongshu.high),
            "low": float(zhongshu.low),
            "start_index": zhongshu.start_index,
            "end_index": zhongshu.end_index,
            "type": zhongshu.type,
            "segment_count": len(zhongshu.segments)
        }

    def _format_buypoint(self, buypoint: BuyPoint) -> Dict[str, Any]:
        """格式化买卖点数据"""
        return {
            "type": buypoint.type,
            "price": float(buypoint.price),
            "index": buypoint.index,
            "date": buypoint.date.strftime('%Y-%m-%d') if buypoint.date else None,
            "confidence": float(buypoint.confidence),
            "position_ratio": float(buypoint.position_ratio),
            "reason": buypoint.reason
        }

    def _format_klines(self, klines: List) -> List[Dict[str, Any]]:
        """格式化K线数据"""
        result = []
        for kline in klines:
            result.append({
                "date": kline.date.strftime('%Y-%m-%d') if kline.date else None,
                "open": float(kline.open),
                "high": float(kline.high),
                "low": float(kline.low),
                "close": float(kline.close),
                "volume": float(kline.volume)
            })
        return result
