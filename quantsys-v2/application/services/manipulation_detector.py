"""
操纵检测服务 - ManipulationDetector

检测市场操纵行为（拉高出货等），识别风险和机会
"""
from domain.ports import IAgentIntelligenceRepository, IFundFlowRepository, IKlineRepository, IFinancialRepository
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class ManipulationDetector:
    """操纵检测器 - 识别拉高出货等操纵行为

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        manipulation_repo: Optional[IAgentIntelligenceRepository] = None,
        fund_flow_repo: Optional[IFundFlowRepository] = None,
        kline_repo: Optional[IKlineRepository] = None,
        financial_repo: Optional[IFinancialRepository] = None,
    ):
        """初始化服务

        Args:
            manipulation_repo: 智能仓库（可选）
            fund_flow_repo: 资金流仓库（可选）
            kline_repo: K线仓库（可选）
            financial_repo: 财务仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.manipulation_repo = manipulation_repo
        self.fund_flow_repo = fund_flow_repo
        self.kline_repo = kline_repo
        self.financial_repo = financial_repo

        # M7-3 兜底注入：manipulation_repo 未注入时自建（操纵事件落库/读取需要）
        if self.manipulation_repo is None:
            try:
                from adapters.outbound.repositories.agent_intelligence_repository import (
                    AgentIntelligenceORMRepository,
                )
                self.manipulation_repo = AgentIntelligenceORMRepository()
                logger.info("manipulation_repo 兜底注入 AgentIntelligenceORMRepository（ManipulationDetector）")
            except Exception as e:
                logger.warning(f"manipulation_repo 兜底注入失败: {e}")

        # M7-3 兜底注入：fund_flow_repo 未注入时自建，保证操纵检测的
        # 成交量信号（_check_volume_surge / _check_high_volume_stagnation）可用
        if self.fund_flow_repo is None:
            try:
                from adapters.outbound.repositories.fund_flow_repository import FundFlowORMRepository
                self.fund_flow_repo = FundFlowORMRepository()
                logger.info("fund_flow_repo 兜底注入 FundFlowORMRepository（ManipulationDetector）")
            except Exception as e:
                logger.warning(f"fund_flow_repo 兜底注入失败: {e}")

        # M7-3 兜底注入：kline_repo / financial_repo（信号5/6 需要真实 K 线与财务数据）
        if self.kline_repo is None:
            try:
                from adapters.outbound.repositories.kline_repository import KlineORMRepository
                self.kline_repo = KlineORMRepository()
                logger.info("kline_repo 兜底注入 KlineORMRepository（ManipulationDetector）")
            except Exception as e:
                logger.warning(f"kline_repo 兜底注入失败: {e}")

        if self.financial_repo is None:
            try:
                from adapters.outbound.repositories.financial_repository import FinancialORMRepository
                self.financial_repo = FinancialORMRepository()
                logger.info("financial_repo 兜底注入 FinancialORMRepository（ManipulationDetector）")
            except Exception as e:
                logger.warning(f"financial_repo 兜底注入失败: {e}")

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
            # 通过统一数据访问层获取今日涨停池（Phase 2 数据提供者接口）
            from infrastructure.services.service_factory import ServiceFactory

            provider_manager = ServiceFactory.get_data_provider_manager()
            result = provider_manager.get_zt_pool(datetime.now().strftime('%Y%m%d'))
            if not result.get('success') or not result.get('data'):
                return []

            records = result['data'].data.get('records', [])
            if not records:
                return []

            # 转换为字典列表
            stocks = []
            for row in records:
                # 涨停统计字段：akshare 返回 "N/M" 字符串（连续N天/总共M天）或 dict（兼容旧格式）
                zt_stat = row.get('涨停统计')
                zt_count = 0
                if isinstance(zt_stat, dict):
                    zt_count = zt_stat.get('连续涨停', 0) or 0
                elif isinstance(zt_stat, str):
                    try:
                        zt_count = int(zt_stat.split('/')[0])
                    except (ValueError, IndexError):
                        zt_count = 0
                # 兜底：直接用连板数字段（akshare 新版列名）
                if zt_count == 0:
                    zt_count = int(row.get('连板数') or 0)

                stocks.append({
                    'symbol': str(row.get('代码', '')),
                    'name': row.get('名称', ''),
                    'current_price': row.get('最新价', 0),
                    'change_pct': row.get('涨跌幅', 0),
                    'turnover_rate': row.get('换手率', 0),
                    'zt_count': zt_count
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

        # 信号3: 龙虎榜游资席位（仅连板≥2 才查——游资拉板必上榜；0/1连板查询纯属浪费
        #         实时网络调用，8/28 实测全池 50 只逐股查需 162s，优化后仅对连板股查）
        if zt_count >= 2 and self._check_lhb_hot_money(symbol):
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

        优先：stock_lhb_stock_detail_em 席位明细（买卖营业部名称）
        - akshare 该接口返回不稳定（同参数多次调用结果集不同），
          M7-3 实测：同一天调用有时缺席位 → 每日期重试 3 次取并集
        - TypeError 表示该日无上榜数据（akshare 内部 NoneType 订阅 bug），静默跳过
        回退：get_lhb_detail 汇总记录（净买额占总成交比 > 20% 视为游资/主力主导代理）

        Args:
            symbol: 股票代码

        Returns:
            是否检测到游资
        """
        try:
            # 路径1：席位明细（东财 stock_lhb_stock_detail_em，买入/卖出营业部）
            import akshare as ak

            bare = symbol.split('.')[0]
            hot_money_keywords = [
                '东方财富证券拉萨',
                '国泰君安成都',
                '华泰证券深圳',
                '银河证券绍兴',
                '中信证券杭州',
                '财通证券杭州',
                '申万宏源证券上海徐汇',
                '平安证券杭州',
                '国盛证券宁波',
                '中国中投证券深圳',
                '华鑫证券上海',
                '招商证券深圳',
                '中信建投证券杭州',
                '国金证券上海',
            ]

            # 近5个交易日逐日查席位（明细接口按单日查询；每日期重试2次取并集，
            # 规避 akshare stock_lhb_stock_detail_em 偶发空结果）
            for i in range(0, 6):
                date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                seen_names = set()
                for _attempt in range(2):
                    try:
                        df = ak.stock_lhb_stock_detail_em(symbol=bare, date=date, flag='买入')
                    except Exception:
                        continue
                    if df is None or len(df) == 0:
                        continue
                    for _, row in df.iterrows():
                        name = str(row.get('交易营业部名称', ''))
                        if name in seen_names:
                            continue
                        seen_names.add(name)
                        # 东财返回营业部全称（如"中国银河证券股份有限公司绍兴鲁迅中路证券营业部"），
                        # 关键词用"券商名+城市"精简模式（如"银河证券绍兴"）→ 剥离中间"股份有限公司"等干扰词
                        compact = (name
                                   .replace('股份有限公司', '')
                                   .replace('有限责任公司', '')
                                   .replace('证券营业部', '')
                                   .replace('分公司', ''))
                        for keyword in hot_money_keywords:
                            if keyword in compact:
                                logger.debug(f"龙虎榜游资信号: {symbol} {date} {name}")
                                return True

            # 路径2：回退到汇总记录（净买额占比 > 20% = 游资/主力主导）
            from infrastructure.services.service_factory import ServiceFactory
            provider_manager = ServiceFactory.get_data_provider_manager()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)
            result = provider_manager.get_lhb_detail(
                symbol=symbol,
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d')
            )
            if result.get('success') and result.get('data'):
                records = result['data'].data.get('records', [])
                for row in records:
                    ratio = row.get('净买额占总成交比', 0) or 0
                    if ratio > 20:
                        logger.debug(f"龙虎榜游资信号(代理): {symbol} 净买额占比{ratio:.1f}%")
                        return True

            return False

        except Exception as e:
            logger.debug(f"检查龙虎榜失败: {symbol} - {e}")
            return False

    def _check_volume_surge(self, symbol: str) -> bool:
        """
        检查成交量是否异常放大

        基于最近K线真实成交量：近3日均量 vs 前7日均量 > 3 倍
        （原实现误用 main_net_inflow 当成交量，且数据不足时静默 False）

        Args:
            symbol: 股票代码

        Returns:
            是否成交量异常
        """
        try:
            if self.kline_repo is None:
                return False

            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            df = self.kline_repo.get_range(symbol, start_date, end_date)
            if df is None or len(df) < 10:
                return False

            volumes = df['volume'].to_list()
            if not volumes or len(volumes) < 10:
                return False

            # 近3天平均成交量 vs 前7天平均
            recent_vol = sum(float(v) for v in volumes[-3:]) / 3
            previous_vol = sum(float(v) for v in volumes[-10:-3]) / 7

            if previous_vol <= 0:
                return False

            # 成交量放大3倍以上
            ratio = recent_vol / previous_vol
            if ratio >= 3:
                logger.debug(f"成交量异常放大信号: {symbol} 近3日均量/前7日均量={ratio:.1f}x")
                return True

            return False

        except Exception as e:
            logger.debug(f"检查成交量失败: {symbol} - {e}")
            return False

    def _check_fundamental_deviation(self, symbol: str, stock_info: Dict) -> bool:
        """
        检查价格是否严重偏离基本面

        基于最新年度 EPS 与当前价格计算 PE-TTM 近似值：
        - 亏损（EPS<=0）：连板拉升无基本面支撑 → 偏离
        - PE > 200：严重高估 → 偏离
        - 无财务数据：不判定（避免误伤）

        Args:
            symbol: 股票代码
            stock_info: 股票信息

        Returns:
            是否严重偏离基本面
        """
        try:
            if self.financial_repo is None:
                return False

            financial = self.financial_repo.get_financial_data(symbol)
            if not financial or not financial.get('income'):
                return False

            income = financial['income']
            eps = income.get('eps') or income.get('eps_diluted')
            if eps is None or eps == 0:
                return False

            current_price = stock_info.get('current_price', 0)
            if current_price <= 0:
                return False

            pe = current_price / abs(eps)
            # 亏损：EPS 为负 → 连板拉升完全无基本面支撑
            if eps < 0:
                logger.debug(f"基本面偏离信号: {symbol} EPS为负({eps:.2f}) 亏损连板")
                return True
            # PE 极高（>200）视为严重偏离
            if pe > 200:
                logger.debug(f"基本面偏离信号: {symbol} PE={pe:.0f} 严重高估")
                return True

            return False

        except Exception as e:
            logger.debug(f"检查基本面偏离失败: {symbol} - {e}")
            return False

    def _check_high_volume_stagnation(self, symbol: str) -> bool:
        """
        检查是否高位放量滞涨

        基于最近K线数据（近20个交易日）：
        - 价格处于近期高位（最新收盘 > 20日区间 80% 分位）
        - 近期（3日）成交量较前期（前7日）放大 1.5 倍以上
        - 近期涨幅收窄（3日累计涨幅 < 5%，滞涨）

        三者同时满足 = 高位放量滞涨（出货嫌疑）

        Args:
            symbol: 股票代码

        Returns:
            是否高位滞涨
        """
        try:
            if self.kline_repo is None:
                return False

            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')

            df = self.kline_repo.get_range(symbol, start_date, end_date)
            if df is None or len(df) < 20:
                return False

            closes = df['close'].to_list()
            volumes = df['volume'].to_list()
            if not closes or not volumes:
                return False

            recent_close = float(closes[-1])
            if recent_close <= 0:
                return False

            # 1. 高位判断：最新价 > 20日最高价的 90%（接近高点）
            period_high = max(float(c) for c in closes[-20:])
            if recent_close < period_high * 0.9:
                return False

            # 2. 放量判断：近3日均量 vs 前7日均量 > 1.5 倍
            recent_vol = sum(float(v) for v in volumes[-3:]) / 3
            prev_vol = sum(float(v) for v in volumes[-10:-3]) / 7 if len(volumes) >= 10 else 0
            if prev_vol <= 0 or recent_vol <= prev_vol * 1.5:
                return False

            # 3. 滞涨判断：近3日累计涨幅 < 5%（放量但涨不动）
            gain_3d = (recent_close / float(closes[-4]) - 1) * 100 if len(closes) >= 4 else 99
            if gain_3d >= 5:
                return False

            logger.debug(f"高位放量滞涨信号: {symbol} 高位({recent_close:.2f}) 放量({recent_vol/prev_vol:.1f}x) 滞涨({gain_3d:.1f}%)")
            return True

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

        优先：最新日K收盘价；失败返回 0

        Args:
            symbol: 股票代码

        Returns:
            当前价格
        """
        try:
            if self.kline_repo is None:
                return 0.0

            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
            df = self.kline_repo.get_range(symbol, start_date, end_date)
            if df is None or len(df) == 0:
                return 0.0
            return float(df['close'].to_list()[-1])

        except Exception as e:
            logger.debug(f"获取当前价格失败: {symbol} - {e}")
            return 0.0
