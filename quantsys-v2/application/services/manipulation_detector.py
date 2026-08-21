"""
操纵检测服务 - ManipulationDetector

检测市场操纵行为（拉高出货等），识别风险和机会
"""
from domain.ports import IAgentIntelligenceRepository, IFundFlowRepository
import structlog
from typing import Dict, Any, List
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class ManipulationDetector:
    """操纵检测器 - 识别拉高出货等操纵行为"""

    def __init__(self):
        """初始化服务"""
        self.manipulation_repo = IAgentIntelligenceRepository()
        self.fund_flow_repo = IFundFlowRepository()

    def detect_market_manipulation(self) -> Dict[str, Any]:
        """
        检测市场操纵行为

        Returns:
            {
                'active_manipulations': [
                    {
                        'symbol': '000XXX.SZ',
                        'manipulation_type': 'pump_and_dump',
                        'stage': 'distribution',
                        'confidence': 0.92,
                        'signals': [...],
                        'fair_value': 8.5,
                        'current_price': 12.3,
                        'deviation': '+45%',
                        'action': 'avoid',
                        'risk_level': 'extreme'
                    }
                ],
                'post_manipulation_opportunities': [
                    {
                        'symbol': '000YYY.SZ',
                        'stage': 'collapse_complete',
                        'collapsed_from': 15.2,
                        'current_price': 8.1,
                        'fair_value': 10.5,
                        'upside': '+30%',
                        'confidence': 0.78,
                        'action': 'bottom_fishing'
                    }
                ]
            }
        """
        logger.info("🔍 开始检测市场操纵行为")

        try:
            # 1. 扫描涨停板股票（可能被操纵）
            active_manipulations = self._scan_potential_manipulations()

            # 2. 扫描已崩盘股票（寻找抄底机会）
            post_manipulation_opportunities = self._scan_post_manipulation_opportunities()

            result = {
                'active_manipulations': active_manipulations,
                'post_manipulation_opportunities': post_manipulation_opportunities,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(
                f"✅ 操纵检测完成: 发现{len(active_manipulations)}个活跃操纵, "
                f"{len(post_manipulation_opportunities)}个抄底机会"
            )

            return result

        except Exception as e:
            logger.error(f"❌ 操纵检测失败: {e}", exc_info=True)
            raise

    def _scan_potential_manipulations(self) -> List[Dict]:
        """
        扫描潜在的操纵行为

        Returns:
            活跃的操纵事件列表
        """
        manipulations = []

        try:
            # 获取最近的涨停板数据
            zt_pool = self._get_recent_zt_stocks()

            for stock in zt_pool:
                symbol = stock['symbol']

                # 检测操纵信号
                signals = self._detect_manipulation_signals(symbol, stock)

                if len(signals) >= 3:  # 至少3个信号才判定为操纵
                    # 计算置信度
                    confidence = min(0.95, 0.5 + len(signals) * 0.15)

                    # 判断操纵阶段
                    stage = self._determine_manipulation_stage(symbol, signals)

                    # 估算公允价值
                    fair_value = self._estimate_fair_value(symbol, stock)
                    current_price = stock.get('current_price', 0)

                    if current_price > 0 and fair_value > 0:
                        deviation = ((current_price - fair_value) / fair_value) * 100

                        manipulation = {
                            'symbol': symbol,
                            'name': stock.get('name', ''),
                            'manipulation_type': 'pump_and_dump',
                            'stage': stage,
                            'confidence': confidence,
                            'signals': signals,
                            'fair_value': fair_value,
                            'current_price': current_price,
                            'deviation': f"{deviation:+.1f}%",
                            'action': 'avoid' if stage in ['markup', 'distribution'] else 'monitor',
                            'risk_level': self._assess_risk_level(stage, deviation)
                        }

                        manipulations.append(manipulation)

                        # 保存到数据库
                        self._save_manipulation_event(manipulation)

        except Exception as e:
            logger.warning(f"扫描潜在操纵失败: {e}")

        return manipulations

    def _get_recent_zt_stocks(self) -> List[Dict]:
        """
        获取最近涨停的股票

        Returns:
            涨停股列表
        """
        try:
            # 通过统一数据访问层获取今日涨停池（Phase 3 数据访问治理）
            from adapters.outbound.datasources.manager import get_data_provider_manager

            result = get_data_provider_manager().get_zt_pool(datetime.now().strftime('%Y%m%d'))
            if not result.get('success') or not result.get('data'):
                return []

            records = result['data'].data.get('records', [])
            if not records:
                return []

            # 转换为字典列表
            stocks = []
            for row in records:
                stocks.append({
                    'symbol': row.get('代码', ''),
                    'name': row.get('名称', ''),
                    'current_price': row.get('最新价', 0),
                    'change_pct': row.get('涨跌幅', 0),
                    'turnover_rate': row.get('换手率', 0),
                    'zt_count': row.get('涨停统计', {}).get('连续涨停', 0) if isinstance(row.get('涨停统计'), dict) else 0
                })

            return stocks[:50]  # 限制扫描数量

        except Exception as e:
            logger.warning(f"获取涨停池失败: {e}")
            return []

    def _detect_manipulation_signals(self, symbol: str, stock_info: Dict) -> List[str]:
        """
        检测操纵信号

        Args:
            symbol: 股票代码
            stock_info: 股票信息

        Returns:
            检测到的信号列表
        """
        signals = []

        # 信号1: 连续涨停
        zt_count = stock_info.get('zt_count', 0)
        if zt_count >= 3:
            signals.append(f'连续{zt_count}天涨停')

        # 信号2: 换手率异常
        turnover_rate = stock_info.get('turnover_rate', 0)
        if turnover_rate > 30:
            signals.append(f'换手率异常高({turnover_rate:.1f}%)')

        # 信号3: 龙虎榜游资席位
        if self._check_lhb_hot_money(symbol):
            signals.append('龙虎榜显示游资活跃')

        # 信号4: 成交量放大
        if self._check_volume_surge(symbol):
            signals.append('成交量异常放大')

        # 信号5: 价格偏离基本面
        if self._check_fundamental_deviation(symbol, stock_info):
            signals.append('价格严重偏离基本面')

        # 信号6: 高位放量滞涨
        if self._check_high_volume_stagnation(symbol):
            signals.append('高位放量滞涨')

        return signals

    def _check_lhb_hot_money(self, symbol: str) -> bool:
        """
        检查龙虎榜是否有游资席位

        Args:
            symbol: 股票代码

        Returns:
            是否检测到游资
        """
        try:
            # 通过统一数据访问层获取最近5天的龙虎榜数据（Phase 3 数据访问治理；
            # 顺带修复：原 ak.stock_lhb_detail_em(symbol=...) 传了不存在的参数，必 TypeError）
            from adapters.outbound.datasources.manager import get_data_provider_manager

            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)

            result = get_data_provider_manager().get_lhb_detail(
                symbol=symbol,
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d')
            )
            if not result.get('success') or not result.get('data'):
                return False

            records = result['data'].data.get('records', [])
            if not records:
                return False

            # 检查是否有知名游资席位
            hot_money_keywords = [
                '东方财富证券拉萨',
                '国泰君安成都',
                '华泰证券深圳',
                '银河证券绍兴',
                '中信证券杭州'
            ]

            for row in records:
                buyer = str(row.get('买方营业部', ''))
                for keyword in hot_money_keywords:
                    if keyword in buyer:
                        return True

            return False

        except Exception as e:
            logger.debug(f"检查龙虎榜失败: {symbol} - {e}")
            return False

    def _check_volume_surge(self, symbol: str) -> bool:
        """
        检查成交量是否异常放大

        Args:
            symbol: 股票代码

        Returns:
            是否成交量异常
        """
        try:
            # 获取最近的资金流向数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=10)

            flows = self.fund_flow_repo.get_fund_flow(
                symbol,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )

            if len(flows) < 5:
                return False

            # 计算最近3天平均成交量 vs 前7天平均
            recent_volumes = [row.get('main_net_inflow', 0) for row in flows[:3]]
            previous_volumes = [row.get('main_net_inflow', 0) for row in flows[3:]]

            if not previous_volumes:
                return False

            recent_avg = sum(abs(v) for v in recent_volumes) / len(recent_volumes)
            previous_avg = sum(abs(v) for v in previous_volumes) / len(previous_volumes)

            # 成交量放大3倍以上
            return recent_avg > previous_avg * 3

        except Exception as e:
            logger.debug(f"检查成交量失败: {symbol} - {e}")
            return False

    def _check_fundamental_deviation(self, symbol: str, stock_info: Dict) -> bool:
        """
        检查价格是否严重偏离基本面

        简化版：仅基于PE判断
        """
        try:
            # TODO: 获取股票基本面数据（PE、PB等）
            # 这里简化处理，实际应该调用财务数据API
            return False

        except Exception as e:
            logger.debug(f"检查基本面偏离失败: {symbol} - {e}")
            return False

    def _check_high_volume_stagnation(self, symbol: str) -> bool:
        """
        检查是否高位放量滞涨

        Args:
            symbol: 股票代码

        Returns:
            是否高位滞涨
        """
        try:
            # 获取最近K线数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=10)

            # TODO: 获取K线数据，判断是否高位+放量+涨幅收窄
            # 这里简化处理
            return False

        except Exception as e:
            logger.debug(f"检查高位滞涨失败: {symbol} - {e}")
            return False

    def _determine_manipulation_stage(self, symbol: str, signals: List[str]) -> str:
        """
        判断操纵所处阶段

        Stages:
        - accumulation: 吸筹阶段
        - markup: 拉高阶段
        - distribution: 出货阶段
        - collapse: 崩盘阶段

        Args:
            symbol: 股票代码
            signals: 检测到的信号

        Returns:
            操纵阶段
        """
        # 简化判断逻辑
        if '连续' in ''.join(signals) and '涨停' in ''.join(signals):
            if '高位' in ''.join(signals):
                return 'distribution'  # 高位涨停 = 出货
            else:
                return 'markup'  # 拉高阶段

        if '放量' in ''.join(signals) and '滞涨' in ''.join(signals):
            return 'distribution'  # 放量滞涨 = 出货

        return 'markup'  # 默认拉高阶段

    def _estimate_fair_value(self, symbol: str, stock_info: Dict) -> float:
        """
        估算公允价值

        简化版：基于涨幅回撤估算

        Args:
            symbol: 股票代码
            stock_info: 股票信息

        Returns:
            估算的公允价值
        """
        current_price = stock_info.get('current_price', 0)
        zt_count = stock_info.get('zt_count', 0)

        if current_price <= 0:
            return 0

        # 简化估算：假设每个涨停板10%，回撤50%是合理价值
        if zt_count > 0:
            total_gain = (1.1 ** zt_count) - 1
            fair_value = current_price / (1 + total_gain * 0.5)
            return round(fair_value, 2)

        return current_price

    def _assess_risk_level(self, stage: str, deviation: float) -> str:
        """
        评估风险级别

        Args:
            stage: 操纵阶段
            deviation: 价格偏离度

        Returns:
            风险级别
        """
        if stage == 'distribution' or deviation > 50:
            return 'extreme'
        elif stage == 'markup' or deviation > 30:
            return 'high'
        else:
            return 'medium'

    def _save_manipulation_event(self, manipulation: Dict):
        """
        保存操纵事件到数据库

        Args:
            manipulation: 操纵事件数据
        """
        try:
            event = {
                'symbol': manipulation['symbol'],
                'manipulation_type': manipulation['manipulation_type'],
                'stage': manipulation['stage'],
                'confidence': manipulation['confidence'],
                'signals': manipulation['signals'],
                'current_price': manipulation['current_price'],
                'fair_value': manipulation['fair_value'],
                'risk_level': manipulation['risk_level']
            }

            self.manipulation_repo.create_event(event)

        except Exception as e:
            logger.warning(f"保存操纵事件失败: {e}")

    def _scan_post_manipulation_opportunities(self) -> List[Dict]:
        """
        扫描已崩盘的股票，寻找抄底机会

        Returns:
            抄底机会列表
        """
        opportunities = []

        try:
            # 获取最近记录的操纵事件
            active_events = self.manipulation_repo.get_active_events()

            for event in active_events:
                symbol = event['symbol']

                # 检查是否已经崩盘完成
                if self._check_collapse_complete(symbol, event):
                    opportunity = {
                        'symbol': symbol,
                        'stage': 'collapse_complete',
                        'collapsed_from': event.get('current_price', 0),
                        'current_price': self._get_current_price(symbol),
                        'fair_value': event.get('fair_value', 0),
                        'confidence': 0.75,
                        'action': 'bottom_fishing',
                        'entry_trigger': '止跌企稳后介入'
                    }

                    # 计算潜在收益
                    if opportunity['current_price'] > 0 and opportunity['fair_value'] > 0:
                        upside = ((opportunity['fair_value'] - opportunity['current_price']) /
                                 opportunity['current_price']) * 100
                        opportunity['upside'] = f"+{upside:.1f}%"

                    opportunities.append(opportunity)

                    # 更新事件状态
                    self.manipulation_repo.resolve_event(event['id'])

        except Exception as e:
            logger.warning(f"扫描抄底机会失败: {e}")

        return opportunities

    def _check_collapse_complete(self, symbol: str, event: Dict) -> bool:
        """
        检查是否崩盘完成

        判断标准：
        - 距离检测时间超过7天
        - 当前价格接近公允价值

        Args:
            symbol: 股票代码
            event: 操纵事件

        Returns:
            是否崩盘完成
        """
        try:
            # 时间判断
            detected_time = event.get('detected_at')
            if not detected_time:
                return False

            if isinstance(detected_time, str):
                detected_time = datetime.fromisoformat(detected_time)

            days_passed = (datetime.now() - detected_time).days
            if days_passed < 7:
                return False

            # 价格判断
            current_price = self._get_current_price(symbol)
            fair_value = event.get('fair_value', 0)

            if current_price <= 0 or fair_value <= 0:
                return False

            # 当前价格在公允价值±20%范围内
            deviation = abs(current_price - fair_value) / fair_value
            return deviation < 0.2

        except Exception as e:
            logger.debug(f"检查崩盘完成失败: {symbol} - {e}")
            return False

    def _get_current_price(self, symbol: str) -> float:
        """
        获取当前价格

        Args:
            symbol: 股票代码

        Returns:
            当前价格
        """
        try:
            # TODO: 获取实时价格
            # 这里简化处理
            return 0.0

        except Exception as e:
            logger.debug(f"获取当前价格失败: {symbol} - {e}")
            return 0.0
