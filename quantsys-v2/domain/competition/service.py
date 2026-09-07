"""竞争分析服务 - 行业竞争格局、对手对比、优劣势识别

核心逻辑：
1. 识别同行业竞争对手（按市值排序）
2. 计算市场规模和占有率
3. 对比财务指标（ROE、毛利率、增长率）
4. 提取竞争优劣势
5. 生成结构化分析报告

博弈智能视角：
- 市占率 = 战场控制力
- ROE/毛利率 = 盈利能力（护城河指标）
- 增长率 = 扩张速度（进攻性）
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


def normalize_symbol(symbol: str) -> str:
    """归一化股票代码为 bare 格式（6 位数字）"""
    s = symbol.strip().upper()
    if "." in s:
        s = s.split(".")[0]
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s


class CompetitionAnalysisService:
    def __init__(self, repo):
        self.repo = repo

    def analyze(self, symbol: str, include_financial: bool = True) -> Dict[str, Any]:
        """竞争分析主入口

        Args:
            symbol: 股票代码
            include_financial: 是否包含财务对比（默认 True）

        Returns:
            完整的竞争分析报告（字典格式）
        """
        symbol = normalize_symbol(symbol)

        # 1. 获取目标公司信息
        stock_info = self.repo.get_stock_info(symbol)
        if not stock_info:
            return {"symbol": symbol, "error": "股票不存在或已退市"}

        if not stock_info.get("industry"):
            return {
                "symbol": symbol,
                "company_name": stock_info.get("name", ""),
                "error": "该股票缺少行业分类，无法进行竞争分析"
            }

        industry = stock_info["industry"]

        # 2. 获取同行业竞争对手（前 10 名）
        competitors = self.repo.get_competitors(industry, limit=10)
        if not competitors:
            return {
                "symbol": symbol,
                "company_name": stock_info["name"],
                "error": f"未找到 {industry} 行业的其他公司"
            }

        # 3. 计算行业汇总指标
        industry_totals = self.repo.get_industry_totals(industry)
        total_market_cap = industry_totals.get("total_market_cap", 0)

        # 4. 找到目标公司在竞争对手列表中的位置
        target_rank = None
        target_market_cap = stock_info.get("market_cap", 0)
        for idx, comp in enumerate(competitors, start=1):
            if comp["symbol"] == symbol:
                target_rank = idx
                break

        if target_rank is None:
            # 目标公司不在前 10，说明是小公司
            target_rank = len(competitors) + 1

        # 5. 构建竞争对手列表（排除自己）
        competitors_list = []
        for comp in competitors:
            if comp["symbol"] == symbol:
                continue

            comp_market_cap = comp.get("market_cap") or 0
            market_share = (comp_market_cap / total_market_cap * 100) if total_market_cap > 0 else 0

            # 竞争地位分级
            position = self._classify_position(market_share, competitors.index(comp) + 1)

            competitors_list.append({
                "symbol": comp["symbol"],
                "name": comp["name"],
                "market_cap": round(comp_market_cap, 2),
                "market_share": round(market_share, 2),
                "competitive_position": position
            })

        # 6. 计算目标公司市占率
        target_market_share = (target_market_cap / total_market_cap * 100) if total_market_cap > 0 else 0

        # 7. 财务对比（可选）
        financial_comparison = None
        if include_financial:
            financial_comparison = self._build_financial_comparison(
                symbol, stock_info, competitors
            )

        # 8. 提取竞争优劣势
        advantages, disadvantages = self._extract_competitive_edges(
            stock_info, industry_totals
        )

        # 9. 生成摘要
        summary = self._generate_summary(
            stock_info, industry, target_rank, target_market_share,
            competitors_list[:3], industry_totals
        )

        # 10. 解析行业分类
        industry_parts = industry.split("-")
        industry_dict = {
            "level1": industry_parts[0] if len(industry_parts) > 0 else industry,
            "level2": industry
        }

        return {
            "symbol": symbol,
            "company_name": stock_info["name"],
            "industry": industry_dict,
            "market_size": {
                "total_market_cap": round(total_market_cap, 2),
                "industry_rank": target_rank,
                "market_share": round(target_market_share, 2)
            },
            "competitors": competitors_list,
            "financial_comparison": financial_comparison,
            "competitive_advantages": advantages,
            "competitive_disadvantages": disadvantages,
            "summary": summary
        }

    def _classify_position(self, market_share: float, rank: int) -> str:
        """竞争地位分级

        - leader: 市占率 > 30% 或排名第 1
        - second_tier: 排名 2-5 或市占率 5%-30%
        - follower: 排名 6+ 或市占率 < 5%
        """
        if market_share > 30 or rank == 1:
            return "leader"
        elif 2 <= rank <= 5 or 5 <= market_share <= 30:
            return "second_tier"
        else:
            return "follower"

    def _build_financial_comparison(
        self, target_symbol: str, target_info: dict, competitors: List[dict]
    ) -> Dict[str, Any]:
        """构建财务对比表"""
        metrics = ["roe", "gross_margin", "net_profit_growth", "revenue_growth"]
        data = []

        # 添加目标公司
        target_row = {
            "symbol": target_symbol,
            "name": target_info["name"],
            "roe": target_info.get("roe"),
            "gross_margin": target_info.get("gross_margin"),
            "net_profit_growth": target_info.get("net_profit_growth"),
            "revenue_growth": target_info.get("revenue_growth")
        }
        data.append(target_row)

        # 添加竞争对手
        for comp in competitors:
            if comp["symbol"] == target_symbol:
                continue
            comp_row = {
                "symbol": comp["symbol"],
                "name": comp["name"],
                "roe": comp.get("roe"),
                "gross_margin": comp.get("gross_margin"),
                "net_profit_growth": comp.get("net_profit_growth"),
                "revenue_growth": comp.get("revenue_growth")
            }
            data.append(comp_row)

        return {
            "metrics": metrics,
            "data": data
        }

    def _extract_competitive_edges(
        self, stock_info: dict, industry_totals: dict
    ) -> tuple[List[str], List[str]]:
        """提取竞争优劣势

        优势：指标高于行业均值 20% 以上
        劣势：指标低于行业均值 20% 以上或为负值
        """
        advantages = []
        disadvantages = []

        # ROE 对比
        roe = stock_info.get("roe")
        avg_roe = industry_totals.get("avg_roe")
        if roe is not None and avg_roe is not None and avg_roe > 0:
            if roe > avg_roe * 1.2:
                advantages.append(
                    f"ROE {roe:.2f}% 领先行业平均（{avg_roe:.2f}%）"
                )
            elif roe < avg_roe * 0.8 or roe < 0:
                disadvantages.append(
                    f"ROE {roe:.2f}% 低于行业平均（{avg_roe:.2f}%）"
                )

        # 毛利率对比
        gm = stock_info.get("gross_margin")
        avg_gm = industry_totals.get("avg_gross_margin")
        if gm is not None and avg_gm is not None and avg_gm > 0:
            if gm > avg_gm * 1.2:
                advantages.append(
                    f"毛利率 {gm:.2f}% 显著高于行业（{avg_gm:.2f}%）"
                )
            elif gm < avg_gm * 0.8:
                disadvantages.append(
                    f"毛利率 {gm:.2f}% 低于行业平均（{avg_gm:.2f}%）"
                )

        # 净利润增长率对比
        npg = stock_info.get("net_profit_growth")
        avg_npg = industry_totals.get("avg_net_profit_growth")
        if npg is not None and avg_npg is not None:
            if npg > avg_npg * 1.2 and npg > 0:
                advantages.append(
                    f"净利润增长率 {npg:.2f}% 高于行业（{avg_npg:.2f}%）"
                )
            elif npg < avg_npg * 0.8 or npg < 0:
                disadvantages.append(
                    f"净利润增长 {npg:.2f}% 低于行业平均（{avg_npg:.2f}%）"
                )

        # 营收增长率对比
        rg = stock_info.get("revenue_growth")
        avg_rg = industry_totals.get("avg_revenue_growth")
        if rg is not None and avg_rg is not None:
            if rg > avg_rg * 1.2 and rg > 0:
                advantages.append(
                    f"营收增长率 {rg:.2f}% 高于行业（{avg_rg:.2f}%）"
                )
            elif rg < avg_rg * 0.8 or rg < 0:
                disadvantages.append(
                    f"营收增长 {rg:.2f}% 低于行业平均（{avg_rg:.2f}%）"
                )

        # 市占率优势
        market_cap = stock_info.get("market_cap", 0)
        total_cap = industry_totals.get("total_market_cap", 0)
        if total_cap > 0:
            market_share = market_cap / total_cap * 100
            if market_share > 30:
                advantages.append(
                    f"市值占比 {market_share:.1f}%，行业龙头地位稳固"
                )
            elif market_share < 5:
                disadvantages.append(
                    f"市值占比仅 {market_share:.1f}%，市场份额较小"
                )

        return advantages, disadvantages

    def _generate_summary(
        self, stock_info: dict, industry: str, rank: int, market_share: float,
        top_competitors: List[dict], industry_totals: dict
    ) -> str:
        """生成竞争分析摘要"""
        name = stock_info["name"]
        industry_name = industry.split("-")[-1]  # 取细分行业名

        # 地位描述
        if rank == 1 and market_share > 30:
            position_desc = "绝对龙头地位"
        elif rank == 1:
            position_desc = "龙头地位"
        elif rank <= 3:
            position_desc = "头部企业"
        elif rank <= 5:
            position_desc = "二线阵营"
        else:
            position_desc = "跟随者位置"

        # 盈利能力描述
        roe = stock_info.get("roe")
        avg_roe = industry_totals.get("avg_roe")
        if roe is not None and avg_roe is not None and avg_roe > 0:
            if roe > avg_roe * 1.2:
                profit_desc = f"盈利能力显著强于竞争对手（ROE {roe:.2f}% vs 行业均值 {avg_roe:.2f}%）"
            elif roe < avg_roe * 0.8:
                profit_desc = f"盈利能力低于行业平均水平（ROE {roe:.2f}% vs {avg_roe:.2f}%）"
            else:
                profit_desc = f"盈利能力与行业平均接近（ROE {roe:.2f}%）"
        else:
            profit_desc = "盈利能力数据不足"

        # 主要竞争对手
        if top_competitors:
            competitors_names = "、".join([
                f"{c['name']}（市占率{c['market_share']:.1f}%）"
                for c in top_competitors[:3]
            ])
            competitors_desc = f"主要竞争对手为{competitors_names}。"
        else:
            competitors_desc = "暂无显著竞争对手。"

        summary = (
            f"{name}在{industry_name}行业处于{position_desc}，"
            f"市值占比{market_share:.1f}%。{profit_desc}。{competitors_desc}"
        )

        return summary
