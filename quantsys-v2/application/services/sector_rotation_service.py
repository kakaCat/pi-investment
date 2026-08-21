"""
行业轮动服务

职责：
1. 计算行业评分和排名
2. 筛选强势行业
3. 提供行业成分股查询
"""
from domain.ports import IKlineRepository, IStockRepository
from typing import List, Dict, Optional
from application.services.strategy_engine.sector_rotation import SectorRotation
import structlog

logger = structlog.get_logger(__name__)


class SectorRotationService:
    """行业轮动服务"""

    def __init__(
        self,
        stock_repo,  # 移除类型注解
        kline_repo   # 移除类型注解
    ):
        self.stock_repo = stock_repo
        self.kline_repo = kline_repo

    def get_sector_ranking(
        self,
        market: str = "A",
        limit: int = 10,
        min_score: float = 0.0
    ) -> List[Dict]:
        """获取行业排名

        Args:
            market: 市场类型 ("A" 或 "HK")
            limit: 返回前N个行业
            min_score: 最低评分过滤

        Returns:
            行业排名列表，每个元素包含:
            {
                "name": "食品饮料",
                "code": "BK0438",
                "composite_score": 0.85,
                "momentum": 0.82,
                "flow": 0.88,
                "relative_strength": 0.86,
                "rank": 1
            }
        """
        try:
            # 获取所有行业列表
            industries = self._get_all_industries()
            logger.info(f"获取到行业列表: {len(industries)} 个")
            if not industries:
                logger.warning("未找到行业数据")
                return []

            # 计算各行业指标
            logger.info(f"开始计算 {len(industries)} 个行业的指标...")
            momentum_data = self._calculate_momentum(industries)
            logger.info(f"momentum 计算完成: {len(momentum_data)} 个行业, 非零数据: {sum(1 for v in momentum_data.values() if v != 0)}")

            flow_data = self._calculate_flow(industries)
            logger.info(f"flow 计算完成: {len(flow_data)} 个行业, 非零数据: {sum(1 for v in flow_data.values() if v != 0)}")

            strength_data = self._calculate_relative_strength(industries)
            logger.info(f"strength 计算完成: {len(strength_data)} 个行业, 非零数据: {sum(1 for v in strength_data.values() if v != 0)}")

            # 使用 SectorRotation 引擎计算综合评分
            rotation = SectorRotation(market=market)
            sector_scores = rotation.score(
                momentum=momentum_data,
                sector_flow=flow_data,
                relative_strength=strength_data
            )

            # 转换为字典格式
            results = []
            for idx, score_obj in enumerate(sector_scores):
                composite = score_obj.composite_score
                if composite < min_score:
                    continue

                results.append({
                    "name": score_obj.sector_name,
                    "code": "",  # TODO: 从行业映射表获取
                    "composite_score": round(composite, 4),
                    "momentum": round(score_obj.detail.get("momentum", 0), 4),
                    "flow": round(score_obj.detail.get("flow", 0), 4),
                    "relative_strength": round(score_obj.detail.get("strength", 0), 4),
                    "rank": idx + 1
                })

                if len(results) >= limit:
                    break

            return results

        except Exception as e:
            logger.error(f"计算行业排名失败: {e}", exc_info=True)
            return []

    def filter_top_sectors(
        self,
        top_n: int = 3,
        min_score: float = 0.0,
        exclude_sectors: Optional[List[str]] = None,
        market: str = "A"
    ) -> List[str]:
        """筛选强势行业

        Args:
            top_n: 选择前N个行业
            min_score: 最低评分
            exclude_sectors: 排除的行业列表
            market: 市场类型

        Returns:
            行业名称列表
        """
        ranking = self.get_sector_ranking(market=market, limit=100, min_score=0.0)

        # 过滤排除的行业
        if exclude_sectors:
            ranking = [s for s in ranking if s['name'] not in exclude_sectors]

        # 过滤最低评分
        ranking = [s for s in ranking if s['composite_score'] >= min_score]

        # 取前N个
        top_sectors = ranking[:top_n]

        return [s['name'] for s in top_sectors], ranking[:top_n]

    def _get_all_industries(self) -> List[str]:
        """获取所有行业列表"""
        try:
            return self.stock_repo.get_all_industries()
        except Exception as e:
            logger.error(f"获取行业列表失败: {e}")
            return []

    def _calculate_momentum(self, industries: List[str]) -> Dict[str, float]:
        """计算行业动量（简化版：使用近期涨幅）"""
        momentum = {}
        logger.info(f"[momentum] 开始计算 {len(industries)} 个行业的动量...")

        for idx, industry in enumerate(industries):
            try:
                # 获取该行业的股票
                stocks = self.stock_repo.get_stocks_by_industries([industry])

                if idx < 3:  # 只记录前3个行业的详细日志
                    logger.info(f"[momentum] 行业 {industry} 股票数: {len(stocks)}")

                if not stocks:
                    momentum[industry] = 0.0
                    continue

                # 限制采样数量
                sample_stocks = stocks[:50]

                # 批量查询K线数据
                klines_map = self.kline_repo.batch_get_recent_klines(sample_stocks, days=20)

                if idx < 3:
                    logger.info(f"[momentum] 行业 {industry} K线数据: {len(klines_map)} 只股票返回数据")

                # 计算行业平均涨幅（最近20日）
                total_return = 0.0
                count = 0
                for symbol in sample_stocks:
                    klines = klines_map.get(symbol, [])
                    if len(klines) >= 20:
                        start_price = klines[0].get('close', 0)
                        end_price = klines[-1].get('close', 0)
                        if start_price > 0:
                            total_return += (end_price - start_price) / start_price
                            count += 1

                momentum[industry] = total_return / count if count > 0 else 0.0

                if idx < 3:
                    logger.info(f"[momentum] 行业 {industry} 结果: {momentum[industry]:.4f} (有效股票: {count}/{len(sample_stocks)})")

            except Exception as e:
                logger.warning(f"计算行业 {industry} 动量失败: {e}")
                momentum[industry] = 0.0

        return momentum

    def _calculate_flow(self, industries: List[str]) -> Dict[str, float]:
        """计算行业资金流（简化版：使用成交量变化）"""
        flow = {}
        for industry in industries:
            try:
                stocks = self.stock_repo.get_stocks_by_industries([industry])
                if not stocks:
                    flow[industry] = 0.0
                    continue

                sample_stocks = stocks[:50]
                klines_map = self.kline_repo.batch_get_recent_klines(sample_stocks, days=10)

                # 计算行业平均成交量变化
                total_volume_ratio = 0.0
                count = 0
                for symbol in sample_stocks:
                    klines = klines_map.get(symbol, [])
                    if len(klines) >= 10:
                        recent_vol = sum(k.get('volume', 0) for k in klines[-5:]) / 5
                        prev_vol = sum(k.get('volume', 0) for k in klines[-10:-5]) / 5
                        if prev_vol > 0:
                            total_volume_ratio += (recent_vol - prev_vol) / prev_vol
                            count += 1

                flow[industry] = total_volume_ratio / count if count > 0 else 0.0

            except Exception as e:
                logger.warning(f"计算行业 {industry} 资金流失败: {e}")
                flow[industry] = 0.0

        return flow

    def _calculate_relative_strength(self, industries: List[str]) -> Dict[str, float]:
        """计算行业相对强度（简化版：相对大盘的超额收益）"""
        strength = {}

        # 获取大盘指数收益（使用上证指数 000001，因为沪深300数据可能缺失）
        try:
            index_klines = self.kline_repo.get_latest('000001', limit=20)
            if len(index_klines) >= 20:
                index_start = index_klines[0].get('close', 0)
                index_end = index_klines[-1].get('close', 0)
                index_return = (index_end - index_start) / index_start if index_start > 0 else 0.0
                logger.info(f"大盘指数收益率: {index_return:.4f}")
            else:
                logger.warning(f"上证指数数据不足: 仅 {len(index_klines)} 条")
                index_return = 0.0
        except Exception as e:
            logger.error(f"获取上证指数数据失败: {e}")
            index_return = 0.0

        for industry in industries:
            try:
                stocks = self.stock_repo.get_stocks_by_industries([industry])
                if not stocks:
                    strength[industry] = 0.0
                    continue

                sample_stocks = stocks[:50]
                klines_map = self.kline_repo.batch_get_recent_klines(sample_stocks, days=20)

                # 计算行业平均收益
                total_return = 0.0
                count = 0
                for symbol in sample_stocks:
                    klines = klines_map.get(symbol, [])
                    if len(klines) >= 20:
                        start_price = klines[0].get('close', 0)
                        end_price = klines[-1].get('close', 0)
                        if start_price > 0:
                            total_return += (end_price - start_price) / start_price
                            count += 1

                industry_return = total_return / count if count > 0 else 0.0
                # 相对强度 = 行业收益 - 大盘收益
                strength[industry] = industry_return - index_return

            except Exception as e:
                logger.warning(f"计算行业 {industry} 相对强度失败: {e}")
                strength[industry] = 0.0

        return strength
