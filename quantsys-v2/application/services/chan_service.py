"""缠论分析服务"""
import structlog
logger = structlog.get_logger(__name__)
from domain.ports import IAgentKnowledgeRepository, IKlineRepository
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd

from domain.chan.chan_analyzer import ChanAnalyzer
from domain.chan.types import Bi, Segment, ZhongShu, BuyPoint


class ChanService:
    """缠论分析服务

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(self, kline_repo: Optional[IKlineRepository] = None):
        """初始化服务

        Args:
            kline_repo: K线仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.analyzer = ChanAnalyzer()
        self.kline_repo = kline_repo  # 如果为 None，使用时会报错，调用方需要确保传入

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

        # 执行缠论分析（buypoint_types 缺省必须回落默认列表——
        # 直接传 None 会让 analyzer 的 `bp.type in None` 炸 TypeError）
        result = self.analyzer.analyze(
            symbol, klines_df,
            buypoint_types or ['1买', '2买', '3买', '1卖', '2卖', '3卖'])

        # 附加历史胜率知识（chan_knowledge_distill 蒸馏产物；失败不阻塞分析）
        knowledge_map = self._load_knowledge_map()
        buypoints = [self._format_buypoint(bp) for bp in result.buypoints]
        for bp in buypoints:
            bp['knowledge'] = knowledge_map.get(f"chan_{bp['type']}")

        # 转换为前端格式
        return {
            "symbol": symbol,
            "trend_type": result.trend_type,
            "bis": [self._format_bi(bi) for bi in result.bis],
            "segments": [self._format_segment(seg) for seg in result.segments],
            "zhongshus": [self._format_zhongshu(zs) for zs in result.zhongshus],
            "buypoints": buypoints,
            "klines": self._format_klines(result.klines)
        }

    def _load_knowledge_map(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """加载 chan_theory 蒸馏知识 → {strategy: {win_rate, samples, suggested_confidence}}
        任何异常返回空 map（知识是增强项，不阻塞分析）"""
        try:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            repo = EnhancedServiceFactory.resolve(IAgentKnowledgeRepository)
            rows = repo.get_by_domain('chan_theory', 'signal_effectiveness')
            out = {}
            for r in rows:
                c = r.get('content') or {}
                strategy = c.get('strategy')
                if not strategy:
                    continue
                samples = c.get('samples', 0)
                win_rate = c.get('win_rate', 0)
                if samples < 10:
                    suggested = '低（样本不足）'
                elif win_rate >= 0.6:
                    suggested = '中高'
                elif win_rate >= 0.45:
                    suggested = '中'
                else:
                    suggested = '低'
                out[strategy] = {
                    'win_rate': win_rate,
                    'samples': samples,
                    'suggested_confidence': suggested,
                }
            return out
        except Exception as e:
            logger.info(f'加载缠论知识失败（不阻塞分析）: {e}')
            return {}

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

            # 归一化日期类型：生产 K 线 date 列可能是字符串，
            # 下游 _format_klines/_format_buypoint 调 .strftime 需要 datetime
            df['date'] = pd.to_datetime(df['date'])

            return df[required_cols]

        except Exception as e:
            logger.info(f'获取K线数据失败: {e}')
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

    def _format_zhongshu(self, zhongshu) -> Dict[str, Any]:
        """格式化笔中枢（BiZhongShu）"""
        return {
            "high": float(zhongshu.zg),
            "low": float(zhongshu.zd),
            "start_index": zhongshu.start_index,
            "end_index": zhongshu.end_index,
            "type": zhongshu.type,
            "bi_count": zhongshu.bi_count
        }

    def _format_buypoint(self, buypoint: BuyPoint) -> Dict[str, Any]:
        """格式化买卖点数据（价格 2 位小数——复权数据原始值带长尾）"""
        return {
            "type": buypoint.type,
            "price": round(float(buypoint.price), 2),
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
