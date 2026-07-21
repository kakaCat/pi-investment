"""
公司质量评分服务

专注于基本面质量指标：ROE、负债率、毛利率、净利率及其趋势
"""
import structlog
from typing import Dict, Optional, List
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class QualityScoringService:
    """公司质量评分服务"""

    def __init__(self, data_service):
        """
        初始化质量评分服务

        Args:
            data_service: 数据服务实例
        """
        self.ds = data_service

    def calculate_quality_score(self, symbol: str, framework: str = 'auto') -> Dict:
        """
        计算公司质量评分

        Args:
            symbol: 股票代码
            framework: 评分框架 ('auto', 'roe_focused', 'balance_sheet', 'profitability')

        Returns:
            {
                'symbol': str,
                'name': str,
                'quality_score': float,       # 总质量评分 (0-100)
                'grade': str,                 # 质量等级 (A+/A/B+/B/C/D)
                'dimensions': {
                    'profitability': {        # 盈利能力 (40%)
                        'score': float,
                        'roe': float,
                        'net_margin': float,
                        'gross_margin': float,
                        'indicators': list
                    },
                    'financial_health': {     # 财务健康 (30%)
                        'score': float,
                        'debt_ratio': float,
                        'current_ratio': float,
                        'indicators': list
                    },
                    'efficiency': {           # 运营效率 (20%)
                        'score': float,
                        'asset_turnover': float,
                        'inventory_turnover': float,
                        'indicators': list
                    },
                    'cashflow': {             # 现金流 (10%)
                        'score': float,
                        'ocf_ratio': float,
                        'indicators': list
                    }
                },
                'trends': {                   # 趋势分析
                    'roe_trend': str,         # 'improving'/'stable'/'declining'
                    'margin_trend': str,
                    'debt_trend': str,
                    'description': str
                },
                'warnings': list,             # 风险警示
                'strengths': list,            # 优势亮点
                'timestamp': str
            }
        """
        try:
            # 1. 获取股票基本信息
            stock_info = self.ds.stock.get_by_symbol(symbol)
            if not stock_info:
                return {'error': f'股票 {symbol} 不存在'}

            # 2. 获取最新因子数据
            factors = self.ds.factor.get_latest_factors(symbol)
            if not factors:
                return {'error': f'股票 {symbol} 暂无因子数据'}

            # 3. 获取历史数据用于趋势分析
            trends = self._analyze_trends(symbol)

            # 4. 计算各维度得分
            profitability = self._score_profitability(factors)
            financial_health = self._score_financial_health(factors)
            efficiency = self._score_efficiency(factors)
            cashflow = self._score_cashflow(factors)

            # 5. 加权计算质量总分
            weights = self._get_framework_weights(framework)
            quality_score = (
                profitability['score'] * weights['profitability'] +
                financial_health['score'] * weights['financial_health'] +
                efficiency['score'] * weights['efficiency'] +
                cashflow['score'] * weights['cashflow']
            )

            # 6. 生成质量等级
            grade = self._score_to_grade(quality_score)

            # 7. 生成警示和亮点
            warnings = self._generate_warnings(factors, profitability, financial_health, trends)
            strengths = self._generate_strengths(factors, profitability, financial_health, trends)

            return {
                'symbol': symbol,
                'name': stock_info.get('name', ''),
                'market': stock_info.get('market', ''),
                'quality_score': round(quality_score, 2),
                'grade': grade,
                'framework': framework,
                'dimensions': {
                    'profitability': profitability,
                    'financial_health': financial_health,
                    'efficiency': efficiency,
                    'cashflow': cashflow
                },
                'trends': trends,
                'warnings': warnings,
                'strengths': strengths,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"计算 {symbol} 质量评分失败: {e}", exc_info=True)
            return {'error': str(e)}

    def _score_profitability(self, factors: Dict) -> Dict:
        """
        盈利能力评分 (0-100)

        指标：
        - ROE (40%): 净资产收益率
        - 净利率 (35%): 净利润/营收
        - 毛利率 (25%): 毛利/营收
        """
        score = 0.0
        indicators = []

        # ROE 评分 (40分)
        roe = factors.get('roe')
        if roe is not None:
            roe_score = 0
            if roe >= 0.20:  # 20%+
                roe_score = 40
                indicators.append(f"ROE优秀({roe*100:.1f}%)")
            elif roe >= 0.15:
                roe_score = 35
                indicators.append(f"ROE良好({roe*100:.1f}%)")
            elif roe >= 0.10:
                roe_score = 25
                indicators.append(f"ROE中等({roe*100:.1f}%)")
            elif roe >= 0.05:
                roe_score = 10
                indicators.append(f"ROE偏低({roe*100:.1f}%)")
            else:
                roe_score = 0
                indicators.append(f"ROE较差({roe*100:.1f}%)")
            score += roe_score

        # 净利率评分 (35分)
        net_margin = factors.get('net_margin')
        if net_margin is not None:
            margin_score = 0
            if net_margin >= 0.20:  # 20%+
                margin_score = 35
                indicators.append(f"净利率优秀({net_margin*100:.1f}%)")
            elif net_margin >= 0.10:
                margin_score = 28
                indicators.append(f"净利率良好({net_margin*100:.1f}%)")
            elif net_margin >= 0.05:
                margin_score = 18
                indicators.append(f"净利率中等({net_margin*100:.1f}%)")
            else:
                margin_score = 5
                indicators.append(f"净利率偏低({net_margin*100:.1f}%)")
            score += margin_score

        # 毛利率评分 (25分)
        gross_margin = factors.get('gross_margin')
        if gross_margin is not None:
            gross_score = 0
            if gross_margin >= 0.50:  # 50%+
                gross_score = 25
                indicators.append(f"毛利率优秀({gross_margin*100:.1f}%)")
            elif gross_margin >= 0.30:
                gross_score = 20
                indicators.append(f"毛利率良好({gross_margin*100:.1f}%)")
            elif gross_margin >= 0.20:
                gross_score = 12
                indicators.append(f"毛利率中等({gross_margin*100:.1f}%)")
            else:
                gross_score = 5
                indicators.append(f"毛利率偏低({gross_margin*100:.1f}%)")
            score += gross_score

        return {
            'score': round(min(100, max(0, score)), 2),
            'roe': round(roe * 100, 2) if roe else None,
            'net_margin': round(net_margin * 100, 2) if net_margin else None,
            'gross_margin': round(gross_margin * 100, 2) if gross_margin else None,
            'indicators': indicators
        }

    def _score_financial_health(self, factors: Dict) -> Dict:
        """
        财务健康评分 (0-100)

        指标：
        - 负债率 (60%): 总负债/总资产
        - 流动比率 (40%): 流动资产/流动负债
        """
        score = 0.0
        indicators = []

        # 负债率评分 (60分)
        debt_ratio = factors.get('debt_ratio') or factors.get('debt_to_asset_ratio')
        if debt_ratio is not None:
            debt_score = 0
            if debt_ratio < 0.30:  # 低负债
                debt_score = 60
                indicators.append(f"负债率健康({debt_ratio*100:.1f}%)")
            elif debt_ratio < 0.50:
                debt_score = 45
                indicators.append(f"负债率适中({debt_ratio*100:.1f}%)")
            elif debt_ratio < 0.70:
                debt_score = 25
                indicators.append(f"负债率偏高({debt_ratio*100:.1f}%)")
            else:
                debt_score = 5
                indicators.append(f"负债率过高({debt_ratio*100:.1f}%)")
            score += debt_score

        # 流动比率评分 (40分) - 如果有的话
        current_ratio = factors.get('current_ratio')
        if current_ratio is not None:
            cr_score = 0
            if current_ratio >= 2.0:  # 流动比率 >= 2
                cr_score = 40
                indicators.append(f"流动性充足(流动比率{current_ratio:.2f})")
            elif current_ratio >= 1.5:
                cr_score = 32
                indicators.append(f"流动性良好(流动比率{current_ratio:.2f})")
            elif current_ratio >= 1.0:
                cr_score = 20
                indicators.append(f"流动性尚可(流动比率{current_ratio:.2f})")
            else:
                cr_score = 5
                indicators.append(f"流动性不足(流动比率{current_ratio:.2f})")
            score += cr_score
        else:
            # 如果没有流动比率，按负债率调整给分
            score += 30 if debt_ratio and debt_ratio < 0.5 else 15

        return {
            'score': round(min(100, max(0, score)), 2),
            'debt_ratio': round(debt_ratio * 100, 2) if debt_ratio else None,
            'current_ratio': round(current_ratio, 2) if current_ratio else None,
            'indicators': indicators
        }

    def _score_efficiency(self, factors: Dict) -> Dict:
        """
        运营效率评分 (0-100)

        指标：
        - 资产周转率 (60%)
        - 存货周转率 (40%)
        """
        score = 50.0  # 基准分（因为这些指标不一定都有）
        indicators = []

        # 资产周转率（简化估算）
        asset_turnover = factors.get('asset_turnover')
        if asset_turnover is not None:
            if asset_turnover >= 1.0:
                score += 30
                indicators.append(f"资产周转率良好({asset_turnover:.2f})")
            elif asset_turnover >= 0.5:
                score += 20
                indicators.append(f"资产周转率中等({asset_turnover:.2f})")
            else:
                score += 10
                indicators.append(f"资产周转率偏低({asset_turnover:.2f})")

        # 存货周转率
        inventory_turnover = factors.get('inventory_turnover')
        if inventory_turnover is not None:
            if inventory_turnover >= 10:
                score += 20
                indicators.append(f"存货周转率优秀({inventory_turnover:.1f})")
            elif inventory_turnover >= 5:
                score += 15
                indicators.append(f"存货周转率良好({inventory_turnover:.1f})")
            else:
                score += 8
                indicators.append(f"存货周转率中等({inventory_turnover:.1f})")

        if not indicators:
            indicators.append("运营效率数据不足")

        return {
            'score': round(min(100, max(0, score)), 2),
            'asset_turnover': round(asset_turnover, 2) if asset_turnover else None,
            'inventory_turnover': round(inventory_turnover, 2) if inventory_turnover else None,
            'indicators': indicators
        }

    def _score_cashflow(self, factors: Dict) -> Dict:
        """
        现金流评分 (0-100)

        指标：
        - 经营现金流/净利润比率
        """
        score = 50.0  # 基准分
        indicators = []

        ocf_ratio = factors.get('operating_cashflow_ratio')
        if ocf_ratio is not None:
            if ocf_ratio >= 1.2:  # 现金流 > 净利润 20%
                score = 100
                indicators.append(f"现金流优秀(OCF/NI={ocf_ratio:.2f})")
            elif ocf_ratio >= 1.0:
                score = 80
                indicators.append(f"现金流良好(OCF/NI={ocf_ratio:.2f})")
            elif ocf_ratio >= 0.8:
                score = 60
                indicators.append(f"现金流尚可(OCF/NI={ocf_ratio:.2f})")
            else:
                score = 30
                indicators.append(f"现金流偏弱(OCF/NI={ocf_ratio:.2f})")
        else:
            indicators.append("现金流数据不足")

        return {
            'score': round(min(100, max(0, score)), 2),
            'ocf_ratio': round(ocf_ratio, 2) if ocf_ratio else None,
            'indicators': indicators
        }

    def _analyze_trends(self, symbol: str) -> Dict:
        """分析关键指标趋势"""
        # 简化版：暂时返回"数据不足"
        # 完整版需要查询历史财务数据并计算趋势
        return {
            'roe_trend': 'stable',
            'margin_trend': 'stable',
            'debt_trend': 'stable',
            'description': '趋势分析需要更多历史数据'
        }

    def _generate_warnings(
        self,
        factors: Dict,
        profitability: Dict,
        financial_health: Dict,
        trends: Dict
    ) -> List[str]:
        """生成风险警示"""
        warnings = []

        # ROE 过低
        roe = factors.get('roe', 0)
        if roe and roe < 0.05:
            warnings.append(f"ROE过低({roe*100:.1f}%)，盈利能力弱")

        # 负债率过高
        debt_ratio = factors.get('debt_ratio') or factors.get('debt_to_asset_ratio', 0)
        if debt_ratio and debt_ratio > 0.70:
            warnings.append(f"负债率过高({debt_ratio*100:.1f}%)，财务风险较大")

        # 净利率过低
        net_margin = factors.get('net_margin', 0)
        if net_margin and net_margin < 0.03:
            warnings.append(f"净利率过低({net_margin*100:.1f}%)，盈利质量差")

        # 现金流异常
        ocf_ratio = factors.get('operating_cashflow_ratio')
        if ocf_ratio and ocf_ratio < 0.6:
            warnings.append(f"经营现金流偏弱(OCF/NI={ocf_ratio:.2f})，利润含金量低")

        if not warnings:
            warnings.append("暂无重大风险警示")

        return warnings

    def _generate_strengths(
        self,
        factors: Dict,
        profitability: Dict,
        financial_health: Dict,
        trends: Dict
    ) -> List[str]:
        """生成优势亮点"""
        strengths = []

        # 高ROE
        roe = factors.get('roe', 0)
        if roe and roe >= 0.15:
            strengths.append(f"ROE优秀({roe*100:.1f}%)，盈利能力强")

        # 低负债
        debt_ratio = factors.get('debt_ratio') or factors.get('debt_to_asset_ratio', 0)
        if debt_ratio and debt_ratio < 0.30:
            strengths.append(f"负债率低({debt_ratio*100:.1f}%)，财务稳健")

        # 高毛利率
        gross_margin = factors.get('gross_margin', 0)
        if gross_margin and gross_margin >= 0.40:
            strengths.append(f"毛利率高({gross_margin*100:.1f}%)，产品竞争力强")

        # 好现金流
        ocf_ratio = factors.get('operating_cashflow_ratio')
        if ocf_ratio and ocf_ratio >= 1.2:
            strengths.append(f"现金流充沛(OCF/NI={ocf_ratio:.2f})，利润含金量高")

        if not strengths:
            strengths.append("暂无突出优势")

        return strengths

    def _get_framework_weights(self, framework: str) -> Dict[str, float]:
        """获取评分框架权重"""
        frameworks = {
            'auto': {
                'profitability': 0.40,
                'financial_health': 0.30,
                'efficiency': 0.20,
                'cashflow': 0.10
            },
            'roe_focused': {
                'profitability': 0.50,
                'financial_health': 0.25,
                'efficiency': 0.15,
                'cashflow': 0.10
            },
            'balance_sheet': {
                'profitability': 0.25,
                'financial_health': 0.50,
                'efficiency': 0.15,
                'cashflow': 0.10
            },
            'profitability': {
                'profitability': 0.60,
                'financial_health': 0.20,
                'efficiency': 0.10,
                'cashflow': 0.10
            }
        }
        return frameworks.get(framework, frameworks['auto'])

    def _score_to_grade(self, score: float) -> str:
        """评分转等级"""
        if score >= 90:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 70:
            return 'B+'
        elif score >= 60:
            return 'B'
        elif score >= 50:
            return 'C'
        else:
            return 'D'
