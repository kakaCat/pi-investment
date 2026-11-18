"""
对手行为分析服务
分析市场参与者行为，识别博弈机会

按照 quantsys-v2 项目规范实现
"""
from qs_kernel.domain.ports import IAgentIntelligenceRepository, IFundFlowRepository
import structlog
from typing import Callable, Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class OpponentBehaviorService:
    """对手行为分析服务

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        opponent_repo: Optional[IAgentIntelligenceRepository] = None,
        fund_flow_repo: Optional[IFundFlowRepository] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        """初始化服务

        Args:
            opponent_repo: 智能仓库（可选）
            fund_flow_repo: 资金流仓库（可选）
            now_fn: 当前时间提供者（可选，测试可注入固定时间）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.opponent_repo = opponent_repo
        self._now_fn = now_fn or datetime.now
        
        # 自动创建 fund_flow_repo（如果未提供）
        if fund_flow_repo is None:
            from infrastructure.services.service_factory import ServiceFactory
            from qs_kernel.domain.ports import IFundFlowRepository
            fund_flow_repo = ServiceFactory.resolve(IFundFlowRepository)
        
        self.fund_flow_repo = fund_flow_repo

    def _load_flow_data(self) -> Dict[str, Any]:
        """一次读取并描述资金窗口，避免散户/机构各自取数造成口径漂移。

        ``source_rows`` 是仓储返回的“每日市场聚合行”数量，不是底层个股行数；
        ``as_of`` 取实际数据中的最新交易日，不能用轮询时间冒充数据时点。
        """
        now = self._now_fn()
        end = now.strftime('%Y-%m-%d')
        # start/end 均为闭区间：5 个日历日 = 今天及此前 4 天，而非此前 5 天共 6 天。
        start = (now - timedelta(days=4)).strftime('%Y-%m-%d')
        rows: List[Dict[str, Any]] = []
        read_error = None
        try:
            raw_rows = self.fund_flow_repo.get_market_aggregate_flow(start, end) or []
            for row in raw_rows:
                normalized = dict(row)
                normalized['trade_date'] = str(row.get('trade_date') or '')[:10]
                rows.append(normalized)
            rows.sort(key=lambda item: item['trade_date'])
        except Exception as exc:  # 数据不可用时显式降级，不用0伪装中性
            read_error = str(exc)
            logger.warning(f"读取市场资金流窗口失败: {exc}")

        today_rows = [row for row in rows if row['trade_date'] == end]
        has_current_day = bool(today_rows)

        def current_day_flow(keys: List[str], main_fallback: bool = False) -> Optional[float]:
            if not has_current_day:
                return None
            total = 0.0
            for row in today_rows:
                if main_fallback:
                    amount_wan = ((row.get('total_main_flow') or 0)
                                  or (row.get('total_large_flow') or 0)
                                  + (row.get('total_big_flow') or 0))
                else:
                    amount_wan = sum(float(row.get(key) or 0) for key in keys)
                total += float(amount_wan) * 10000
            return total

        return {
            'rows': rows,
            'window': 'trailing_5d_cumulative',
            'window_unit': 'calendar_days',
            'lookback_days': 5,
            'start': start,
            'end': end,
            'as_of': max((row['trade_date'] for row in rows), default=None),
            'source': 'fund_flow_repository.get_market_aggregate_flow',
            'source_row_kind': 'daily_market_aggregate',
            'source_rows': len(rows),
            'current_day': end,
            'current_day_source_rows': len(today_rows),
            'has_current_day_data': has_current_day,
            'current_day_retail_flow': current_day_flow(
                ['total_small_flow', 'total_medium_flow']),
            'current_day_institution_flow': current_day_flow(
                ['total_main_flow'], main_fallback=True),
            'read_error': read_error,
        }

    @staticmethod
    def _participant_flow_fields(flow_data: Dict[str, Any], participant: str) -> Dict[str, Any]:
        """附加到参与者对象的窗口契约；net_flow 始终表示窗口累计值。"""
        fields = {
            key: flow_data[key] for key in (
                'window', 'window_unit', 'lookback_days', 'start', 'end', 'as_of',
                'source', 'source_row_kind', 'source_rows', 'current_day',
                'current_day_source_rows', 'has_current_day_data', 'read_error'
            )
        }
        fields['net_flow_scope'] = 'window_cumulative'
        fields['current_day_net_flow'] = flow_data[
            f'current_day_{participant}_flow']
        return fields

    def analyze_current_behavior(self) -> Dict[str, Any]:
        """
        分析当前市场参与者行为

        Returns:
            {
                'retail': {...},           # 散户行为
                'institution': {...},      # 机构行为
                'hot_money': {...},        # 游资行为
                'market_phase': '...',     # 市场阶段
                'risk_appetite': '...',    # 风险偏好
                'opportunity_map': {...},  # 博弈机会
                'timestamp': '...'
            }
        """
        logger.info("🔍 开始分析对手行为")

        try:
            # 1. 一次读取同一资金窗口，散户和机构共享完全相同的数据版本
            flow_data = self._load_flow_data()

            # 2. 分析散户行为
            retail = self._analyze_retail_behavior(flow_data)
            logger.info(f"散户行为: {retail['behavior']}, 情绪指数: {retail['emotion_index']}")

            # 3. 分析机构行为
            institution = self._analyze_institution_behavior(flow_data)
            inst_flow = institution['net_flow']
            logger.info(f"机构行为: {institution['behavior']}, 净流入: "
                        f"{inst_flow/100000000:.1f}亿" if inst_flow is not None
                        else f"机构行为: {institution['behavior']}, 净流入: 数据不可用")

            # 3. 分析游资行为
            hot_money = self._analyze_hot_money_behavior()
            logger.info(f"游资行为: {hot_money['behavior']}")

            # 4. 判断市场阶段
            market_phase = self._determine_market_phase(retail, institution)
            logger.info(f"市场阶段: {market_phase}")

            # 5. 评估风险偏好
            risk_appetite = self._assess_risk_appetite(retail, institution)

            # 6. 生成机会地图
            opportunity_map = self._generate_opportunity_map(retail, institution, hot_money)
            logger.info(f"识别到 {len(opportunity_map)} 个博弈机会")

            # 7. 保存快照
            snapshot = {
                'retail_behavior': retail['behavior'],
                'retail_net_flow': retail['net_flow'],
                'retail_emotion_index': retail['emotion_index'],
                'institution_behavior': institution['behavior'],
                'institution_net_flow': institution['net_flow'],
                'institution_target_sectors': institution.get('target_sectors', []),
                'hot_money_behavior': hot_money['behavior'],
                'hot_money_target_stocks': hot_money.get('target_stocks', []),
                'hot_money_stage': hot_money.get('stage'),
                'market_phase': market_phase,
                'market_phase_basis': 'fund_flow_combination_only',
                'market_phase_requires_price_confirmation': True,
                'window': flow_data['window'],
                'window_unit': flow_data['window_unit'],
                'lookback_days': flow_data['lookback_days'],
                'start': flow_data['start'],
                'end': flow_data['end'],
                'as_of': flow_data['as_of'],
                'source': flow_data['source'],
                'source_row_kind': flow_data['source_row_kind'],
                'source_rows': flow_data['source_rows'],
                'current_day': flow_data['current_day'],
                'current_day_source_rows': flow_data['current_day_source_rows'],
                'has_current_day_data': flow_data['has_current_day_data'],
                'risk_appetite': risk_appetite,
                'opportunities': opportunity_map
            }
            # W2: opponent_repo 可能为 None，跳过保存
            if self.opponent_repo is not None:
                self.opponent_repo.save_snapshot(snapshot)
            else:
                logger.debug("opponent_repo 不可用，跳过保存快照")

            # 8. 构建返回结果
            result = {
                'retail': retail,
                'institution': institution,
                'hot_money': hot_money,
                'market_phase': market_phase,
                'market_phase_basis': 'fund_flow_combination_only',
                'market_phase_requires_price_confirmation': True,
                'window': flow_data['window'],
                'window_unit': flow_data['window_unit'],
                'lookback_days': flow_data['lookback_days'],
                'start': flow_data['start'],
                'end': flow_data['end'],
                'as_of': flow_data['as_of'],
                'source': flow_data['source'],
                'source_row_kind': flow_data['source_row_kind'],
                'source_rows': flow_data['source_rows'],
                'current_day': flow_data['current_day'],
                'current_day_source_rows': flow_data['current_day_source_rows'],
                'has_current_day_data': flow_data['has_current_day_data'],
                'risk_appetite': risk_appetite,
                'opportunity_map': opportunity_map,
                'degraded': bool(retail.get('degraded') or institution.get('degraded')),
                'timestamp': self._now_fn().isoformat()
            }

            logger.info("✅ 对手行为分析完成")
            return result

        except Exception as e:
            logger.error(f"❌ 对手行为分析失败: {e}", exc_info=True)
            raise

    def _analyze_retail_behavior(self, flow_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """分析散户行为；net_flow 是窗口累计，不代表当日流量。"""
        try:
            flow_data = flow_data or self._load_flow_data()
            window_fields = self._participant_flow_fields(flow_data, 'retail')
            retail_flow = self._calculate_retail_flow(flows=flow_data['rows'])

            if retail_flow is None:
                return {
                    'behavior': 'unknown',
                    'net_flow': None,
                    'emotion_index': None,
                    'common_mistakes': [],
                    'degraded': True,
                    'reason': 'stock_fund_flow 无数据（等待每日采集任务 fund_flow_update）',
                    'description': '资金流数据不可用，无法判断散户行为',
                    **window_fields,
                }

            # 判断行为模式
            if retail_flow < -30_0000_0000:  # -30亿
                behavior = 'panic_selling'
                emotion_index = 20.0  # 极度恐慌
                mistakes = ['割肉在低位', '恐慌中卖出优质股']
            elif retail_flow > 30_0000_0000:  # +30亿
                behavior = 'fomo_buying'
                emotion_index = 80.0  # 极度贪婪
                mistakes = ['追涨在高位', '不看基本面盲目追热点']
            else:
                behavior = 'neutral'
                emotion_index = 50.0  # 中性
                mistakes = []

            return {
                'behavior': behavior,
                'net_flow': int(retail_flow),
                'emotion_index': emotion_index,
                'common_mistakes': mistakes,
                'degraded': False,
                'description': self._get_behavior_description(behavior, 'retail'),
                **window_fields,
            }

        except Exception as e:
            logger.warning(f"分析散户行为失败: {e}")
            return {
                'behavior': 'unknown',
                'net_flow': None,
                'emotion_index': None,
                'common_mistakes': [],
                'degraded': True,
                'reason': str(e),
                'description': '数据不足，无法判断'
            }

    def _analyze_institution_behavior(self, flow_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """分析机构行为；net_flow 是窗口累计，不代表当日流量。"""
        try:
            flow_data = flow_data or self._load_flow_data()
            window_fields = self._participant_flow_fields(flow_data, 'institution')
            institution_flow = self._calculate_institution_flow(flows=flow_data['rows'])

            if institution_flow is None:
                return {
                    'behavior': 'unknown',
                    'net_flow': None,
                    'target_sectors': [],
                    'position_change': 'unknown',
                    'degraded': True,
                    'reason': 'stock_fund_flow 无数据（等待每日采集任务 fund_flow_update）',
                    'description': '资金流数据不可用，无法判断机构行为',
                    **window_fields,
                }

            # 判断行为模式
            if institution_flow > 20_0000_0000:  # +20亿
                behavior = 'accumulating'
                position_change = 'increasing'
            elif institution_flow < -20_0000_0000:  # -20亿
                behavior = 'distributing'
                position_change = 'decreasing'
            else:
                behavior = 'neutral'
                position_change = 'stable'

            # TODO: 分析目标板块（需要按行业聚合资金流向）
            target_sectors = self._identify_target_sectors(institution_flow > 0)

            return {
                'behavior': behavior,
                'net_flow': int(institution_flow),
                'target_sectors': target_sectors,
                'position_change': position_change,
                'degraded': False,
                'description': self._get_behavior_description(behavior, 'institution'),
                **window_fields,
            }

        except Exception as e:
            logger.warning(f"分析机构行为失败: {e}")
            return {
                'behavior': 'unknown',
                'net_flow': None,
                'target_sectors': [],
                'position_change': 'unknown',
                'degraded': True,
                'reason': str(e),
                'description': '数据不足，无法判断'
            }

    def _analyze_hot_money_behavior(self) -> Dict[str, Any]:
        """
        分析游资行为

        基于龙虎榜、涨停板数据分析游资的炒作行为

        Returns:
            {
                'behavior': 'pump_and_dump' | 'inactive',
                'target_stocks': [str],  # 目标股票
                'stage': str,            # accumulation/markup/distribution
                'activity_level': str    # high/medium/low
            }
        """
        try:
            # 游资行为暂无真实数据源（龙虎榜席位数据未接入），
            # 显式标注 estimated，避免被当作真实分析结果
            return {
                'behavior': 'inactive',
                'target_stocks': [],
                'stage': 'unknown',
                'activity_level': 'low',
                'estimated': True,
                'description': '游资活跃度较低，市场以价值投资为主（估算值，龙虎榜数据未接入）'
            }

        except Exception as e:
            logger.warning(f"分析游资行为失败: {e}")
            return {
                'behavior': 'inactive',
                'target_stocks': [],
                'stage': 'unknown',
                'activity_level': 'low',
                'description': '数据不足，无法判断'
            }

    def _determine_market_phase(self, retail: Dict, institution: Dict) -> str:
        """
        判断市场阶段

        根据散户和机构的历史行为组合返回兼容枚举。

        注意：这些枚举只描述资金组合，不是已经确认的价格位置；调用方不得
        仅凭该字段输出价格顶部/底部结论或直接交易动作。

        Args:
            retail: 散户行为数据
            institution: 机构行为数据

        Returns:
            市场阶段
        """
        retail_behavior = retail['behavior']
        institution_behavior = institution['behavior']

        # 数据不可用时显式返回 unknown，不伪装成 consolidation
        if retail_behavior == 'unknown' or institution_behavior == 'unknown':
            return 'unknown'

        # 吸筹阶段：机构建仓，散户恐慌抛售
        if institution_behavior == 'accumulating' and retail_behavior == 'panic_selling':
            return 'accumulation'

        # 派发阶段：机构出货，散户FOMO追涨
        elif institution_behavior == 'distributing' and retail_behavior == 'fomo_buying':
            return 'distribution'

        # 上涨阶段：机构建仓，散户追涨
        elif institution_behavior == 'accumulating' and retail_behavior == 'fomo_buying':
            return 'markup'

        # 下跌阶段：机构出货，散户恐慌
        elif institution_behavior == 'distributing' and retail_behavior == 'panic_selling':
            return 'markdown'

        # 震荡整理
        else:
            return 'consolidation'

    def _assess_risk_appetite(self, retail: Dict, institution: Dict) -> str:
        """
        评估市场风险偏好

        Args:
            retail: 散户行为数据
            institution: 机构行为数据

        Returns:
            'high' | 'medium' | 'low'
        """
        emotion_index = retail['emotion_index']

        if emotion_index is None:
            return 'unknown'

        if emotion_index > 70:
            return 'high'
        elif emotion_index < 30:
            return 'low'
        else:
            return 'medium'

    def _generate_opportunity_map(self, retail: Dict, institution: Dict,
                                  hot_money: Dict) -> Dict[str, Any]:
        """
        生成博弈机会地图

        根据对手行为识别可以利用的机会

        Args:
            retail: 散户行为
            institution: 机构行为
            hot_money: 游资行为

        Returns:
            机会地图
        """
        opportunities = {}

        # 机会1: 收割散户恐慌
        if retail['behavior'] == 'panic_selling' and institution['behavior'] == 'accumulating':
            opportunities['take_from_retail'] = [{
                'strategy': 'bottom_fishing',
                'confidence': 0.85,
                'expected_return': '+5% ~ +10%',
                'time_horizon': '3-5 days',
                'reason': '窗口内散户累计流出、主力累计流入；价格位置与标的基本面仍需确认',
                'action': '创建资金背离观察清单，等待价格结构和基本面确认'
            }]

        # 资金分歧只形成复核线索，不能脱离价格位置直接推导交易动作
        if institution['behavior'] == 'distributing' and retail['behavior'] == 'fomo_buying':
            opportunities['avoid_institution'] = [{
                'risk': 'high',
                'reason': '窗口内主力累计净流出、散户累计净流入，存在资金分歧；价格位置尚待确认',
                'action': '结合价格位置与最新单日流向复核，不直接触发交易动作',
                'urgency': 'normal'
            }]

        # 机会3: 跟随机构建仓
        if institution['behavior'] == 'accumulating' and retail['behavior'] == 'neutral':
            opportunities['follow_institution'] = [{
                'strategy': 'value_investing',
                'confidence': 0.75,
                'expected_return': '+10% ~ +20%',
                'time_horizon': '1-3 months',
                'reason': '机构悄悄建仓，散户尚未察觉',
                'action': f"关注机构建仓板块: {', '.join(institution['target_sectors'])}"
            }]

        # 机会4: 游资炒作后抄底
        if hot_money['behavior'] == 'pump_and_dump' and hot_money['stage'] == 'collapse':
            opportunities['post_manipulation'] = [{
                'strategy': 'value_recovery',
                'confidence': 0.65,
                'expected_return': '+15% ~ +30%',
                'time_horizon': '1-2 weeks',
                'reason': '游资出货完毕，恐慌盘杀跌结束',
                'action': '在游资炒作股暴跌后，筛选基本面尚可的股票抄底'
            }]

        return opportunities

    # ==================== 辅助方法 ====================

    def _calculate_retail_flow(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        flows: Optional[List[Dict[str, Any]]] = None,
    ) -> float | None:
        """计算窗口内散户累计净流入；无数据返回 None。"""
        try:
            if flows is None:
                end_date = end_date or self._now_fn()
                start_date = start_date or (end_date - timedelta(days=5))
                flows = self.fund_flow_repo.get_market_aggregate_flow(
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )

            if not flows:
                logger.warning("stock_fund_flow 无市场聚合资金流数据")
                return None

            # repo 返回单位万元，×1e4 转元
            total_retail_flow = sum([
                (row.get('total_small_flow') or 0) + (row.get('total_medium_flow') or 0)
                for row in flows
            ]) * 10000

            logger.debug(f"散户资金流向: {total_retail_flow/100000000:.2f}亿元")
            return float(total_retail_flow)

        except Exception as e:
            logger.error(f"计算散户资金流失败: {e}")
            return None

    def _calculate_institution_flow(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        flows: Optional[List[Dict[str, Any]]] = None,
    ) -> float | None:
        """计算窗口内机构累计净流入；无数据返回 None。"""
        try:
            if flows is None:
                end_date = end_date or self._now_fn()
                start_date = start_date or (end_date - timedelta(days=5))
                flows = self.fund_flow_repo.get_market_aggregate_flow(
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )

            if not flows:
                logger.warning("stock_fund_flow 无市场聚合资金流数据")
                return None

            # repo 返回单位万元，×1e4 转元。
            # 优先 main（主力）口径：东财/新浪两个源都有该字段；
            # large+big 四档口径仅东财源有，缺失时为 0 不代表无流入。
            total_institution_flow = sum([
                (row.get('total_main_flow') or 0)
                or (row.get('total_large_flow') or 0) + (row.get('total_big_flow') or 0)
                for row in flows
            ]) * 10000

            logger.debug(f"机构资金流向: {total_institution_flow/100000000:.2f}亿元")
            return float(total_institution_flow)

        except Exception as e:
            logger.error(f"计算机构资金流失败: {e}")
            return None

    def _identify_target_sectors(self, is_buying: bool) -> List[str]:
        """
        识别机构目标板块

        基于最新交易日各行业主力净流入排序：买入取流入最多，卖出取流出最多。
        无数据时返回空列表（调用方已在 degraded 分支处理，这里不再返回硬编码板块）。
        """
        try:
            latest = self.fund_flow_repo.get_latest_trade_date()
            if not latest:
                return []

            industry_flows = self.fund_flow_repo.get_industry_aggregate_flow(latest)
            if not industry_flows:
                return []

            if is_buying:
                top = industry_flows[:5]
            else:
                top = sorted(industry_flows, key=lambda x: x['main_net_inflow'])[:5]

            # industry 形如「制造业-医药制造业」，取末级细分行业
            return [item['industry'].split('-')[-1] for item in top]

        except Exception as e:
            logger.error(f"识别目标板块失败: {e}")
            return []

    def _get_behavior_description(self, behavior: str, participant: str) -> str:
        """获取行为描述"""
        descriptions = {
            ('panic_selling', 'retail'): '窗口内散户资金累计净流出并达到流出阈值，不代表当日恐慌',
            ('fomo_buying', 'retail'): '窗口内散户资金累计净流入并达到流入阈值，不代表当日追涨',
            ('neutral', 'retail'): '窗口内散户资金累计流向未达到行为阈值',
            ('accumulating', 'institution'): '窗口内主力资金累计净流入并达到流入阈值，需结合价格位置确认',
            ('distributing', 'institution'): '窗口内主力资金累计净流出并达到流出阈值，需结合价格位置确认',
            ('neutral', 'institution'): '窗口内主力资金累计流向未达到行为阈值',
        }
        return descriptions.get((behavior, participant), '行为模式不明确')
