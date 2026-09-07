"""
改进的股票评分服务 - 配置驱动版本

使用外部配置文件，支持灵活调整评分权重和规则
"""
import structlog
from typing import Dict
from datetime import datetime

logger = structlog.get_logger(__name__)

# 导入配置
try:
    from infrastructure.config.scoring_config import (
        SCORING_WEIGHTS,
        TECHNICAL_SCORING,
        FUNDAMENTAL_SCORING,
        MOMENTUM_SCORING,
        QUALITY_SCORING,
        GRADE_THRESHOLDS,
        SIGNAL_RULES,
    )
except ImportError:
    logger.warning("无法导入评分配置，使用默认配置")
    # 如果导入失败，使用默认配置
    SCORING_WEIGHTS = {'technical': 0.40, 'fundamental': 0.30, 'momentum': 0.20, 'quality': 0.10}
    TECHNICAL_SCORING = {}
    FUNDAMENTAL_SCORING = {}
    MOMENTUM_SCORING = {}
    QUALITY_SCORING = {}
    GRADE_THRESHOLDS = [(90, 'A+'), (80, 'A'), (70, 'B+'), (60, 'B'), (50, 'C'), (0, 'D')]
    SIGNAL_RULES = {}


class ConfigurableScoringService:
    """配置驱动的股票评分服务"""

    def __init__(self, stock_repo=None, factor_repo=None):
        """
        初始化评分服务

        Args:
            stock_repo: 股票数据仓库（可选，默认通过 ServiceFactory 获取）
            factor_repo: 因子数据仓库（可选，默认通过 ServiceFactory 获取）
        """
        if stock_repo is None or factor_repo is None:
            from infrastructure.services.service_factory import ServiceFactory
            stock_repo = stock_repo or ServiceFactory.get_stock_repository()
            factor_repo = factor_repo or ServiceFactory.get_factor_repository()
        self.stock_repo = stock_repo
        self.factor_repo = factor_repo
        self.weights = SCORING_WEIGHTS
        logger.info(f"评分权重: {self.weights}")

    def calculate_comprehensive_score(self, symbol: str) -> Dict:
        """
        计算股票综合评分（配置驱动版本）

        使用外部配置文件中的权重和规则
        """
        try:
            # 1. 获取股票基本信息
            stock_info = self.stock_repo.get_by_symbol(symbol)
            if not stock_info:
                return {'error': f'股票 {symbol} 不存在'}

            # 2. 获取最新因子数据
            factors = self.factor_repo.get_latest_factors(symbol)
            if not factors:
                return {'error': f'股票 {symbol} 暂无因子数据'}

            # 3. 计算各维度得分（使用配置）
            technical_score = self._calculate_technical_score_v2(factors)
            fundamental_score = self._calculate_fundamental_score_v2(factors)
            momentum_score = self._calculate_momentum_score_v2(factors)
            quality_score = self._calculate_quality_score_v2(factors)

            # 4. 加权计算总分（使用配置的权重）
            total_score = (
                technical_score * self.weights['technical'] +
                fundamental_score * self.weights['fundamental'] +
                momentum_score * self.weights['momentum'] +
                quality_score * self.weights['quality']
            )

            # 5. 生成信号和建议（使用配置）
            signals = self._generate_signals_v2(factors, total_score)
            grade = self._score_to_grade_v2(total_score)

            return {
                'symbol': symbol,
                'name': stock_info.get('name', ''),
                'market': stock_info.get('market', ''),
                'total_score': round(total_score, 2),
                'technical_score': round(technical_score, 2),
                'fundamental_score': round(fundamental_score, 2),
                'momentum_score': round(momentum_score, 2),
                'quality_score': round(quality_score, 2),
                'grade': grade,
                'signals': signals,
                'config_version': 'v2_configurable',
                'weights': self.weights,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"计算 {symbol} 评分失败: {e}", exc_info=True)
            return {'error': str(e)}

    def _calculate_technical_score_v2(self, factors: Dict) -> float:
        """技术面评分 - 配置驱动版本"""
        if not TECHNICAL_SCORING:
            # 如果没有配置，使用原始方法
            from application.services.stock_scoring_service import StockScoringService
            legacy = StockScoringService(stock_repo=self.stock_repo, factor_repo=self.factor_repo)
            return legacy._calculate_technical_score(factors)

        score = 0.0

        # RSI
        rsi = factors.get('rsi')
        if rsi is not None and 'rsi' in TECHNICAL_SCORING:
            config = TECHNICAL_SCORING['rsi']
            for rule in config['rules']:
                range_tuple = rule['range']
                if range_tuple[0] <= rsi < range_tuple[1]:
                    score += rule['score']
                    break

        # MACD
        macd = factors.get('macd')
        macd_signal = factors.get('macd_signal')
        macd_hist = factors.get('macd_hist')

        if macd is not None and macd_signal is not None and 'macd' in TECHNICAL_SCORING:
            config = TECHNICAL_SCORING['macd']
            rules = config['rules']

            if macd > macd_signal and macd_hist and macd_hist > 0:
                score += rules['golden_cross_rising']
            elif macd > macd_signal:
                score += rules['golden_cross']
            elif macd < macd_signal and macd_hist and macd_hist < 0:
                score += rules['death_cross_falling']
            else:
                score += rules['neutral']

        # 均线
        close = factors.get('close')
        ma5 = factors.get('ma5')
        ma20 = factors.get('ma20')
        ma60 = factors.get('ma60')

        if all([close, ma5, ma20, ma60]) and 'ma' in TECHNICAL_SCORING:
            config = TECHNICAL_SCORING['ma']
            rules = config['rules']

            if close > ma5 > ma20 > ma60:
                score += rules['full_bullish']
            elif close > ma20 > ma60:
                score += rules['partial_bullish']
            elif close > ma60:
                score += rules['above_ma60']
            else:
                score += rules['other']

        # 布林带
        bb_position = factors.get('bb_position')
        if bb_position is not None and 'bollinger' in TECHNICAL_SCORING:
            config = TECHNICAL_SCORING['bollinger']
            for rule in config['rules']:
                range_tuple = rule['range']
                if range_tuple[0] <= bb_position < range_tuple[1]:
                    score += rule['score']
                    break

        return min(100, max(0, score))

    def _calculate_fundamental_score_v2(self, factors: Dict) -> float:
        """基本面评分 - 配置驱动版本"""
        if not FUNDAMENTAL_SCORING:
            from application.services.stock_scoring_service import StockScoringService
            legacy = StockScoringService(stock_repo=self.stock_repo, factor_repo=self.factor_repo)
            return legacy._calculate_fundamental_score(factors)

        score = 0.0

        # PE
        pe = factors.get('pe')
        if pe is not None and pe > 0 and 'pe' in FUNDAMENTAL_SCORING:
            config = FUNDAMENTAL_SCORING['pe']
            for rule in config['rules']:
                range_tuple = rule['range']
                if range_tuple[0] <= pe < range_tuple[1]:
                    score += rule['score']
                    break

        # ROE
        roe = factors.get('roe')
        if roe is not None and 'roe' in FUNDAMENTAL_SCORING:
            config = FUNDAMENTAL_SCORING['roe']
            for rule in config['rules']:
                range_tuple = rule['range']
                if range_tuple[0] <= roe < range_tuple[1]:
                    score += rule['score']
                    break

        # 负债率
        debt_ratio = factors.get('debt_ratio') or factors.get('debt_to_asset_ratio')
        if debt_ratio is not None and 'debt_ratio' in FUNDAMENTAL_SCORING:
            config = FUNDAMENTAL_SCORING['debt_ratio']
            for rule in config['rules']:
                range_tuple = rule['range']
                if range_tuple[0] <= debt_ratio < range_tuple[1]:
                    score += rule['score']
                    break

        # PB
        pb = factors.get('pb')
        if pb is not None and pb > 0 and 'pb' in FUNDAMENTAL_SCORING:
            config = FUNDAMENTAL_SCORING['pb']
            for rule in config['rules']:
                range_tuple = rule['range']
                if range_tuple[0] <= pb < range_tuple[1]:
                    score += rule['score']
                    break

        return min(100, max(0, score))

    def _calculate_momentum_score_v2(self, factors: Dict) -> float:
        """动量评分 - 配置驱动版本"""
        if not MOMENTUM_SCORING:
            from application.services.stock_scoring_service import StockScoringService
            legacy = StockScoringService(stock_repo=self.stock_repo, factor_repo=self.factor_repo)
            return legacy._calculate_momentum_score(factors)

        score = MOMENTUM_SCORING.get('base_score', 50)

        # 价格涨跌幅处理函数
        def apply_threshold_rules(value, config):
            if value is None:
                return 0
            for rule in config['rules']:
                if value >= rule['threshold']:
                    return rule['score']
            return 0

        # 5日涨跌幅
        if 'change_5d' in MOMENTUM_SCORING:
            change_5d = factors.get('change_pct_5d')
            score += apply_threshold_rules(change_5d, MOMENTUM_SCORING['change_5d'])

        # 20日涨跌幅
        if 'change_20d' in MOMENTUM_SCORING:
            change_20d = factors.get('change_pct_20d')
            score += apply_threshold_rules(change_20d, MOMENTUM_SCORING['change_20d'])

        # 成交量比率
        if 'volume_ratio' in MOMENTUM_SCORING:
            volume_ratio = factors.get('volume_ratio')
            score += apply_threshold_rules(volume_ratio, MOMENTUM_SCORING['volume_ratio'])

        # 连续上涨天数
        if 'consecutive_up' in MOMENTUM_SCORING:
            consecutive_up = factors.get('consecutive_up_days', 0)
            score += apply_threshold_rules(consecutive_up, MOMENTUM_SCORING['consecutive_up'])

        return min(100, max(0, score))

    def _calculate_quality_score_v2(self, factors: Dict) -> float:
        """质量评分 - 配置驱动版本"""
        if not QUALITY_SCORING:
            from application.services.stock_scoring_service import StockScoringService
            legacy = StockScoringService(stock_repo=self.stock_repo, factor_repo=self.factor_repo)
            return legacy._calculate_quality_score(factors)

        score = QUALITY_SCORING.get('base_score', 50)

        def apply_threshold_rules(value, config):
            if value is None:
                return 0
            for rule in config['rules']:
                if value >= rule['threshold']:
                    return rule['score']
            return 0

        # 毛利率
        if 'gross_margin' in QUALITY_SCORING:
            gross_margin = factors.get('gross_margin')
            score += apply_threshold_rules(gross_margin, QUALITY_SCORING['gross_margin'])

        # 净利率
        if 'net_margin' in QUALITY_SCORING:
            net_margin = factors.get('net_margin')
            score += apply_threshold_rules(net_margin, QUALITY_SCORING['net_margin'])

        # 经营现金流比率
        if 'ocf_ratio' in QUALITY_SCORING:
            ocf_ratio = factors.get('operating_cashflow_ratio')
            score += apply_threshold_rules(ocf_ratio, QUALITY_SCORING['ocf_ratio'])

        return min(100, max(0, score))

    def _generate_signals_v2(self, factors: Dict, total_score: float) -> list:
        """生成交易信号 - 配置驱动版本"""
        if not SIGNAL_RULES:
            from application.services.stock_scoring_service import StockScoringService
            legacy = StockScoringService(stock_repo=self.stock_repo, factor_repo=self.factor_repo)
            return legacy._generate_signals(factors, total_score)

        signals = []

        for signal_type, rule in SIGNAL_RULES.items():
            if rule['condition'](total_score):
                signals.append({
                    'type': signal_type,
                    'message': rule['message'],
                    'priority': rule['priority']
                })

        # RSI 超买超卖信号
        rsi = factors.get('rsi')
        if rsi and rsi < 30:
            signals.append({
                'type': 'oversold',
                'message': f'RSI={rsi:.1f}，超卖区域，可能反弹',
                'priority': 'medium'
            })
        elif rsi and rsi > 70:
            signals.append({
                'type': 'overbought',
                'message': f'RSI={rsi:.1f}，超买区域，注意回调风险',
                'priority': 'medium'
            })

        return signals

    def _score_to_grade_v2(self, score: float) -> str:
        """评分转等级 - 配置驱动版本"""
        for threshold, grade in GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return 'D'
