"""
博弈预警服务 - GameAlertService

实时监控市场博弈态势，发现风险和机会时主动预警
"""
import hashlib
import json
import structlog
from typing import Callable, Dict, Any, List, MutableMapping, Optional
from datetime import datetime, timedelta
from qs_kernel.domain.ports import IFundFlowRepository
from qs_intel.application.services.opponent_behavior_service import OpponentBehaviorService
from qs_intel.application.services.manipulation_detector import ManipulationDetector

logger = structlog.get_logger(__name__)


def _net_flow_yi(participant: Dict[str, Any]) -> Optional[float]:
    """参与者净流入（亿元）；数据不可用时返回 None。

    口径：OpponentBehaviorService 返回的 net_flow 单位是「元」，降级时为 None
    （见 opponent_behavior_service._analyze_retail_behavior / _analyze_institution_behavior）。

    2026-09-11 修复（w-f4aa1f6a）：原实现读 participant['flow_amount']，该键不存在，
    抛 KeyError 后被下面 except 吞掉 → 对手资金预警长期失效，
    /api/alerts/check 恒返回空（实证：日志 “检查对手行为预警失败: 'flow_amount'”，
    而同一时刻对手服务已识别出 panic_selling + accumulating 的抄底机会）。
    """
    flow = participant.get('net_flow')
    if flow is None:
        return None
    return flow / 100_000_000.0


def _fmt_yi(value: Optional[float]) -> str:
    """净流入格式化（亿元）；None → 数据不可用，避免预警文案里出现 'None亿'。"""
    return f"{value:.1f}亿" if value is not None else "数据不可用"


class GameAlertService:
    """博弈预警服务 - 实时监控和预警

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        fund_flow_repo: Optional[IFundFlowRepository] = None,
        opponent_service: Optional[OpponentBehaviorService] = None,
        manipulation_detector: Optional[ManipulationDetector] = None,
        alert_state: Optional[MutableMapping[str, Dict[str, Any]]] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        """初始化服务

        Args:
            fund_flow_repo: 资金流仓库（可选）
            opponent_service: 对手行为服务（可选）
            manipulation_detector: 操纵检测器（可选）
            alert_state: 可注入的告警状态映射；支持原子 observe 的持久适配器。
                缺省为进程内存；生产由 ServiceFactory 显式注入文件状态适配器。
            now_fn: 当前时间提供者（可选，测试可注入固定时间）
        """
        self.fund_flow_repo = fund_flow_repo
        self.opponent_service = opponent_service or OpponentBehaviorService()
        self.manipulation_detector = manipulation_detector or ManipulationDetector()
        self._alert_state = alert_state if alert_state is not None else {}
        self._alert_state_persistence = (
            'injected_store' if alert_state is not None else 'process_memory')
        self._now_fn = now_fn or datetime.now

        # 操纵检测总超时（秒）：外部数据源（涨停池/龙虎榜）可能无响应，
        # 必须给 check_alerts 设硬上限，否则 /api/alerts/check 无限挂起。
        self.manipulation_timeout_seconds = 20

        # 预警阈值配置
        self.thresholds = {
            'retail_panic_threshold': -30,  # 散户恐慌：净流出30亿
            'retail_fomo_threshold': 30,    # 散户追涨：净流入30亿
            'institution_flow_threshold': 20,  # 机构资金流：20亿
            'manipulation_confidence': 0.8,  # 操纵检测置信度
        }

    @staticmethod
    def _notification_key(alert: Dict[str, Any]) -> str:
        symbols = ','.join(sorted(str(item) for item in (alert.get('symbols') or [])))
        return f"{alert.get('type', 'unknown')}:{alert.get('title', 'unknown')}:{symbols}"

    @staticmethod
    def _fingerprint_payload(alert: Dict[str, Any]) -> Dict[str, Any]:
        # 轮询时间、通知状态和上一轮ID不参与内容指纹。
        excluded = {
            'alert_id', 'created_at', 'last_seen_at', 'content_fingerprint',
            'notify_worthy', 'notification_reason', 'notification_key',
            'dedup_persistence', 'dedup_restart_safe', 'dedup_status', 'dedup_error',
        }
        return {key: value for key, value in alert.items() if key not in excluded}

    def _finalize_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """生成确定性ID，并把重复内容降级为非 notify-worthy。

        返回重复告警而不是返回空列表，避免调用方把“已提醒过”误读为“风险消失”。
        持久适配器通过 observe 在同一临界区内完成读取、判重和写入。
        """
        finalized = dict(alert)
        payload = self._fingerprint_payload(finalized)
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
        fingerprint = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        key = self._notification_key(finalized)
        observed_at = self._now_fn().isoformat(timespec='seconds')
        previous = None
        state_error = None
        unchanged = False
        observer = getattr(self._alert_state, 'observe', None)
        try:
            if callable(observer):
                previous, unchanged = observer(key, fingerprint, observed_at)
            else:
                previous = self._alert_state.get(key)
                unchanged = bool(previous and previous.get('fingerprint') == fingerprint)
        except Exception as exc:
            state_error = str(exc)
            logger.error(f"读取/更新告警去重状态失败: {exc}")

        first_seen_at = (
            str(previous.get('first_seen_at'))
            if unchanged and previous and previous.get('first_seen_at') else observed_at
        )
        finalized.update({
            'alert_id': self._generate_alert_id(fingerprint),
            'content_fingerprint': fingerprint,
            'notification_key': key,
            'notify_worthy': False if state_error else not unchanged,
            'notification_reason': (
                'dedup_error' if state_error else 'unchanged' if unchanged else 'new_or_changed'),
            'created_at': first_seen_at,
            'last_seen_at': observed_at,
            'dedup_persistence': getattr(
                self._alert_state, 'persistence', self._alert_state_persistence),
            'dedup_restart_safe': getattr(
                self._alert_state, 'restart_safe',
                False if self._alert_state_persistence == 'process_memory' else None),
            'dedup_status': 'error' if state_error else 'ok',
            'dedup_error': state_error,
        })
        if not callable(observer):
            try:
                self._alert_state[key] = {
                    'fingerprint': fingerprint,
                    'first_seen_at': first_seen_at,
                    'last_seen_at': observed_at,
                }
            except Exception as exc:
                finalized['dedup_status'] = 'error'
                finalized['dedup_error'] = str(exc)
                finalized['notify_worthy'] = False
                finalized['notification_reason'] = 'dedup_error'
                logger.error(f"写入告警去重状态失败: {exc}")
        return finalized

    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        检查所有预警条件

        Returns:
            预警列表 [
                {
                    'alert_id': 'alert_<content-hash>',
                    'type': 'opportunity',  # opportunity/risk
                    'level': 'high',        # low/medium/high/critical
                    'title': '资金承接观察',
                    'message': '5日累计窗口……',
                    'action': '等待价格结构确认',
                    'symbols': [],
                    'window': 'trailing_5d_cumulative',
                    'start': '2026-11-13',
                    'end': '2026-11-18',
                    'as_of': '2026-11-17',
                    'source_rows': 3,
                    'content_fingerprint': '<sha256>',
                    'notify_worthy': True,
                    'created_at': '2026-11-18T09:30:00'
                }
            ]
        """
        logger.info("🔍 开始检查博弈预警")

        alerts = []

        try:
            # 1. 检查对手行为预警
            opponent_alerts = self._check_opponent_alerts()
            alerts.extend(opponent_alerts)

            # 2. 检查操纵预警
            manipulation_alerts = self._check_manipulation_alerts()
            alerts.extend(manipulation_alerts)

            # 3. 检查持仓风险预警（如果有持仓）
            # position_alerts = self._check_position_alerts()
            # alerts.extend(position_alerts)

            # 所有通道统一在出口生成稳定ID并标记通知资格
            alerts = [self._finalize_alert(alert) for alert in alerts]

            logger.info(f"✅ 预警检查完成: 发现{len(alerts)}个预警")
            return alerts

        except Exception as e:
            logger.error(f"❌ 预警检查失败: {e}", exc_info=True)
            return []

    @staticmethod
    def _flow_window_fields(behavior: Dict[str, Any]) -> Dict[str, Any]:
        source = behavior
        if not source.get('window'):
            source = behavior.get('institution') or behavior.get('retail') or {}
        keys = (
            'window', 'window_unit', 'lookback_days', 'start', 'end', 'as_of',
            'source', 'source_row_kind', 'source_rows', 'current_day',
            'current_day_source_rows', 'has_current_day_data',
        )
        return {key: source.get(key) for key in keys}

    @staticmethod
    def _window_label(fields: Dict[str, Any]) -> str:
        days = fields.get('lookback_days') or 5
        return (
            f"{days}日累计窗口 {fields.get('start') or '未知'}~{fields.get('end') or '未知'}，"
            f"数据截至{fields.get('as_of') or '无可用数据'}，"
            f"日聚合行{fields.get('source_rows') or 0}条"
        )

    def _check_opponent_alerts(self) -> List[Dict[str, Any]]:
        """检查对手行为预警；历史累计与真实单日风险严格分开。"""
        alerts = []

        try:
            opponent_behavior = self.opponent_service.analyze_current_behavior()
            retail = opponent_behavior.get('retail') or {}
            institution = opponent_behavior.get('institution') or {}
            retail_yi = _net_flow_yi(retail)
            institution_yi = _net_flow_yi(institution)
            window_fields = self._flow_window_fields(opponent_behavior)
            window_label = self._window_label(window_fields)
            market_details = {
                'market_phase': opponent_behavior.get('market_phase', 'unknown'),
                'market_phase_basis': opponent_behavior.get(
                    'market_phase_basis', 'fund_flow_combination_only'),
                'market_phase_requires_price_confirmation': True,
                'flow_window': dict(window_fields),
            }

            if (retail.get('behavior') == 'panic_selling' and
                    institution.get('behavior') == 'accumulating'):
                alerts.append({
                    'type': 'opportunity',
                    'level': 'high',
                    'title': '资金承接观察',
                    'message': (
                        f"{window_label}：散户累计{_fmt_yi(retail_yi)}，"
                        f"主力累计{_fmt_yi(institution_yi)}；资金背离不代表价格底部"
                    ),
                    'action': '加入观察清单，等待价格结构和基本面确认',
                    'symbols': [],
                    'details': {
                        **market_details,
                        'retail_emotion': retail.get('emotion_index'),
                    },
                    **window_fields,
                })

            if (retail.get('behavior') == 'fomo_buying' and
                    institution.get('behavior') == 'distributing'):
                alerts.append({
                    'type': 'risk',
                    'level': 'high',
                    'title': '资金流向分歧',
                    'message': (
                        f"{window_label}：散户累计{_fmt_yi(retail_yi)}，"
                        f"主力累计{_fmt_yi(institution_yi)}；该组合不构成价格位置判断"
                    ),
                    'action': '结合价格位置与最新单日数据复核，不直接触发交易动作',
                    'symbols': [],
                    'details': market_details,
                    **window_fields,
                })

            current_day_raw = institution.get('current_day_net_flow')
            current_day_yi = (
                current_day_raw / 100_000_000.0 if current_day_raw is not None else None)
            has_current_day = bool(
                window_fields.get('has_current_day_data')
                and current_day_yi is not None
                and (window_fields.get('current_day_source_rows') or 0) > 0
            )

            if has_current_day and current_day_yi < -50:
                current_day = window_fields.get('current_day')
                single_day_fields = dict(window_fields)
                single_day_fields.update({
                    'window': 'single_day',
                    'window_unit': 'calendar_day',
                    'lookback_days': 1,
                    'start': current_day,
                    'end': current_day,
                    'as_of': current_day,
                    'source_rows': window_fields.get('current_day_source_rows') or 0,
                })
                alerts.append({
                    'type': 'risk',
                    'level': 'critical',
                    'title': '机构资金当日大额净流出',
                    'message': (
                        f"{current_day}单日主力净流出{abs(current_day_yi):.1f}亿"
                        f"（单日数据）；需结合价格结构复核"
                    ),
                    'action': '复核持仓风险与价格结构，按既有风控规则处理',
                    'symbols': [],
                    'details': {
                        'institution_flow': current_day_yi,
                        'flow_scope': 'single_day',
                        'flow_window': single_day_fields,
                    },
                    **single_day_fields,
                })
            elif institution_yi is not None and institution_yi < -50:
                # 累计阈值只产生区间复核线索；无当日行绝不能升级为当日critical。
                alerts.append({
                    'type': 'risk',
                    'level': 'high',
                    'title': '机构资金区间累计净流出',
                    'message': (
                        f"{window_label}：主力累计净流出{abs(institution_yi):.1f}亿；"
                        f"该数值不是当日流量"
                    ),
                    'action': '仅作区间风险线索，结合最新单日数据和价格位置复核',
                    'symbols': [],
                    'details': {
                        'institution_flow': institution_yi,
                        'flow_scope': 'window_cumulative',
                        'flow_window': dict(window_fields),
                        'current_day_data_missing': not has_current_day,
                    },
                    **window_fields,
                })

        except Exception as e:
            logger.warning(f"检查对手行为预警失败: {e}")

        return alerts

    def _check_manipulation_alerts(self) -> List[Dict[str, Any]]:
        """检查操纵预警"""
        alerts = []

        try:
            # 执行操纵检测（受控超时，避免外部数据源拖垮预警接口）
            manipulation_result = self._run_with_timeout(
                self.manipulation_detector.detect_market_manipulation,
                self.manipulation_timeout_seconds,
            )
            if not manipulation_result:
                logger.warning("操纵检测超时，跳过操纵预警（降级）")
                return alerts

            # 活跃的操纵事件 → 风险预警
            active_manipulations = manipulation_result.get('active_manipulations', [])

            for manip in active_manipulations:
                # 只预警高置信度和高风险的
                if (manip.get('confidence', 0) >= self.thresholds['manipulation_confidence'] and
                    manip.get('risk_level') in ['high', 'extreme']):

                    alerts.append({
                        'type': 'risk',
                        'level': 'critical' if manip['risk_level'] == 'extreme' else 'high',
                        'title': '操纵风险预警',
                        'message': (
                            f"{manip['symbol']} {manip.get('name', '')} "
                            f"检测到{manip['manipulation_type']}操纵行为（置信度{manip['confidence']*100:.0f}%）"
                        ),
                        'action': '远离该股，避免高位接盘',
                        'symbols': [manip['symbol']],
                        'details': {
                            'manipulation_type': manip['manipulation_type'],
                            'stage': manip['stage'],
                            'signals': manip.get('signals', []),
                            'current_price': manip.get('current_price'),
                            'fair_value': manip.get('fair_value')
                        },
                        'created_at': self._now_fn().isoformat()
                    })

            # 崩盘后机会 → 机会预警
            opportunities = manipulation_result.get('post_manipulation_opportunities', [])

            for opp in opportunities:
                if opp.get('confidence', 0) >= 0.7:
                    alerts.append({
                        'type': 'opportunity',
                        'level': 'medium',
                        'title': '崩盘抄底机会',
                        'message': (
                            f"{opp['symbol']} 已崩盘完成，"
                            f"当前价格{opp.get('current_price', 0):.2f}接近公允价值{opp.get('fair_value', 0):.2f}"
                        ),
                        'action': opp.get('entry_trigger', '止跌企稳后介入'),
                        'symbols': [opp['symbol']],
                        'details': {
                            'upside': opp.get('upside', 'N/A'),
                            'confidence': opp.get('confidence', 0)
                        },
                        'created_at': self._now_fn().isoformat()
                    })

        except Exception as e:
            logger.warning(f"检查操纵预警失败: {e}")

        return alerts

    def _check_position_alerts(self) -> List[Dict[str, Any]]:
        """检查持仓风险预警"""
        alerts = []

        # TODO: 实现持仓风险检查
        # 需要获取当前持仓，检查每个持仓的风险状态

        return alerts

    def _generate_alert_id(self, fingerprint: str) -> str:
        """由内容指纹生成确定性ID，相同业务内容跨轮询保持一致。"""
        return f"alert_{fingerprint[:24]}"

    def _run_with_timeout(self, fn, timeout_seconds: float, *args):
        """在受控线程中执行 fn，超时返回 None 并遗弃线程。

        与 adapters/outbound/datasources/manager.py 的 _try_providers 同模式：
        Python 线程无法强杀，超时后仅放弃等待，后台线程自行结束。
        用于把外部数据源不响应的操纵检测限制在硬上限内。
        """
        import concurrent.futures
        guard = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        def _guarded():
            try:
                return fn(*args)
            finally:
                try:
                    from qs_kernel.infrastructure.persistence.orm import close_session
                    close_session()
                except Exception:
                    pass

        try:
            fut = guard.submit(_guarded)
            return fut.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            logger.warning(f"操作超时（>{timeout_seconds}s），放弃等待")
            return None
        finally:
            guard.shutdown(wait=False)

    def get_alert_statistics(self) -> Dict[str, Any]:
        """
        获取预警统计

        Returns:
            {
                'total_alerts': 10,
                'by_type': {
                    'opportunity': 4,
                    'risk': 6
                },
                'by_level': {
                    'critical': 2,
                    'high': 3,
                    'medium': 4,
                    'low': 1
                },
                'recent_alerts': [...]
            }
        """
        # 简化实现：实时生成统计
        alerts = self.check_alerts()

        by_type = {}
        by_level = {}

        for alert in alerts:
            alert_type = alert.get('type', 'unknown')
            by_type[alert_type] = by_type.get(alert_type, 0) + 1

            level = alert.get('level', 'unknown')
            by_level[level] = by_level.get(level, 0) + 1

        return {
            'total_alerts': len(alerts),
            'by_type': by_type,
            'by_level': by_level,
            'recent_alerts': alerts[:10]
        }

    def subscribe_alerts(self, user_id: str, preferences: Dict) -> Dict[str, Any]:
        """
        订阅预警

        Args:
            user_id: 用户ID
            preferences: 订阅偏好 {
                'alert_types': ['opportunity', 'risk'],
                'min_level': 'medium',
                'symbols': ['600519.SH']  # 可选，指定关注股票
            }

        Returns:
            订阅信息
        """
        # TODO: 实现订阅逻辑（存储到数据库）
        logger.info(f"用户{user_id}订阅预警: {preferences}")

        return {
            'user_id': user_id,
            'subscribed': True,
            'preferences': preferences
        }
