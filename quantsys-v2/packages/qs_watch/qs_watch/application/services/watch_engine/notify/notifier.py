"""WatchEngine 触发通知器：分层提醒 + 自动升级 + DDD 通知架构

触发层级（trigger_level）：
- L0_MESSAGE：纯信息通知，直接发飞书（不唤醒 Agent，不经 LLM）
- L1_OBSERVATION：观察提醒，直接发飞书（不唤醒 Agent，不经 LLM）
- L2_ACTION：关键操作，发给 Agent（经 LLM 分析后决策）

升级机制：
- L0/L1 触发满足 escalation_policy 条件时，自动升级为 L2
- 升级原因在飞书消息中标注

架构约束：
- 所有通知必须走 NotificationFacade（禁止直接调用飞书 SDK）
- 参考：pi-investment/CLAUDE.md 架构规范章节
"""
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests
import structlog

from qs_notification.application.notification_factory import NotificationFactory
from qs_watch.application.services.watch_engine.dto import TriggerPayload
from qs_watch.domain.watch.models import MetricKind, TriggerLevel
from qs_watch.domain.watch.services.metric_contract import metric_matches

from qs_watch.application.services.watch_engine._repo_resolver import (
    stock_repo,
)

logger = structlog.get_logger(__name__)


def _norm_symbol(symbol: str) -> str:
    """'002241.SZ' -> '002241'（stocks 表为纯 6 位代码）。"""
    return (symbol or '').split('.')[0].strip()


def _relation_of(rule, pnl_pct):
    """「与我何干」一句话（统一委托 domain relation_of，单一事实源）。"""
    try:
        from qs_watch.domain.watch.services.watch_message import relation_of
        return relation_of(rule, pnl_pct)
    except Exception:  # noqa: BLE001 - 失败不阻断通知主路径
        return None


def _same_condition(a: dict, b: dict) -> bool:
    """两条条件 JSON 是否同一条（补发去重比对用，键序不敏感）。"""
    import json
    try:
        return json.dumps(a or {}, sort_keys=True, ensure_ascii=False) == \
               json.dumps(b or {}, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return False


def _lookup_stock_name(symbol: str) -> Optional[str]:
    """兜底查股票名称（quant.stocks）。失败返回 None，不影响主流程。

    2026-09-14（w-32314d00，REQ-24e15d）：裸 SQL 收口到
    StockORMRepository.get_name（仓储返回 None / 上抛异常两种情形都由下面的
    except 兜住，**兜底语义与留痕不变**）。
    """
    try:
        return stock_repo().get_name(_norm_symbol(symbol))
    except Exception as e:
        logger.debug('股票名称兜底查询失败', symbol=symbol, error=str(e))
        return None


class WatchNotifier:
    """WatchEngine 通知器
    
    职责：
    1. 构建 TriggerPayload（含 trigger_level/action_hint）
    2. 根据 trigger_level 决定通知模式（direct/agent）
    3. 调用 NotificationFacade 发送通知（复用 DDD 通知架构）
    4. WebSocket 广播 + 触发记录落库
    
    架构约束：
    - 禁止直接调用 feishu_service.send_alert()
    - 禁止直接调用 agent_service.notify_agent_detailed()
    - 所有通知必须走 NotificationFacade
    """
    
    def __init__(
        self,
        trigger_repo=None,
        ws_url: Optional[str] = 'http://127.0.0.1:5003/broadcast/market_data',
        max_retries: int = 3,
        retry_interval: float = 1.0,
        notification_facade=None,  # 可选：注入 NotificationFacade 实例
        account_total_provider=None,  # REQ-c9f899 t12：账户总资产取数（金额门），与 factory 同口径
        name_resolver=None,  # 2026-10-19：StockNameResolver 端口（标的名解析），factory 注入
    ):
        self.trigger_repo = trigger_repo
        self.ws_url = ws_url
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        #: 账户总资产 provider（factory 注入，避免另造第二份取数口径）
        self._account_total_provider = account_total_provider
        #: 标的名解析端口（StockNameResolver）；None = 回退旧直连路径（测试/未接线兼容）
        self._name_resolver = name_resolver
        #: WS 广播线程池（懒建；shutdown 由 engine.stop 触发）
        self._ws_pool = None
        
        # 注入或懒加载 NotificationFacade
        self._notification_facade = notification_facade

    def _lookup_stock_name(self, symbol: str) -> Optional[str]:
        """标的名解析：优先走注入的 StockNameResolver 端口（单一取数口径，
        批量实现一轮一联查）；未注入时回退旧的直连仓储路径（兼容既有测试）。"""
        if self._name_resolver is not None:
            try:
                return self._name_resolver.resolve_batch([symbol]).get(_norm_symbol(symbol))
            except Exception as e:  # noqa: BLE001 - 名称是渲染增益，绝不阻断通知
                logger.debug('标的名端口解析失败', symbol=symbol, error=str(e))
                return None
        return _lookup_stock_name(symbol)

    def _account_total_yuan(self, rule):
        """账户总资产（元）：供金额门判定。provider 缺失/抛错/取不到 → None（门关闭，不抛错）。

        REQ-c9f899 t12（§6 待接线项 2）：金额门在 facade 侧已修好，但 notifier 调用处
        从未传 account_total_yuan → 生产链路上门仍关闭。此处复用 factory 的
        account_total_provider（同一取数口径，勿另造）；缺数据时保持门关闭（原行为），
        绝不因取数失败中断通知（路由/告警不该被数据问题阻断）。
        """
        provider = self._account_total_provider
        if provider is None:
            return None
        try:
            value = provider(rule)
        except Exception as e:  # noqa: BLE001 - 取数失败不许打挂通知
            logger.warning('账户总资产取数失败，金额门关闭（None）', error=str(e))
            return None
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    
    @property
    def notification_facade(self):
        """获取 NotificationFacade 实例（懒加载）"""
        if self._notification_facade is None:
            self._notification_facade = NotificationFactory.get_instance()
        return self._notification_facade

    def notify(self, rule, condition: dict, quote, result, escalation_reason: str = None,
               disposition: str = None, disposition_reason: str = None,
               dup_of: int = None, action_amount_yuan: float = None, level: str = None,
               merged_from_rule: int = None, exec_directive=None):
        """触发通知
        
        Args:
            rule: 触发规则（含 action_hint, escalation_policy）
            condition: 触发的条件
            quote: 实时行情
            result: 条件评估结果
            escalation_reason: 升级原因（如果是 L1→L2 自动升级）
            exec_directive: P0 执行指令（`exec_directive.ExecDirective`；由
                `DeliverStage` **唯一构造**，与待办读同一个对象）——非空时覆盖
                通知的「下一步」/结构化动作块，并把三态处置并入预案段。
                缺省 None = 行为与改造前完全一致（不许改坏旧渲染）。
        
        Returns:
            bool: 是否成功送达
        """
        # 0. 去重短路（REQ-f08def）：同标的同向在去重窗内已有触发 → 只落库不通知。
        # 实测噪声来源：同规则同向多阈值（0.46 秒内两条）、601600 六条规则语义重合（一次跌穿 4+ 条）。
        # 仍落库是为了保留审计（notified=False + disposition='deduped' + dup_of 溯源）。
        if disposition == 'deduped':
            logger.info('触发去重合并（不通知）', rule_id=getattr(rule, 'id', None),
                        symbol=getattr(rule, 'symbol', None), dup_of=dup_of)
            return self._record(rule, condition, quote, result, notified=False,
                                disposition=disposition, disposition_reason=disposition_reason,
                                dup_of=dup_of)

        # 2026-09-11 用户否决：观察类也必须推送。
        # 我曾按 RFC 015 草案把 auto_observed 从即时通道摘掉（理由"只是一眼看不值得打扰"），
        # 但用户的定位是「通知是给用户看的事实」——**不该由机器替用户过滤掉一类信息**。
        # 降噪的正确路径是「让 agent 把规则设好」（规则重叠/阈值失真 → 治理），
        # 而不是在通知层悄悄吞掉。故此处保持推送（disposition 照旧记录以便追溯）。

        # 1. 构建 TriggerPayload
        payload = self._build_payload(rule, condition, quote, result, escalation_reason,
                                      action_amount_yuan=action_amount_yuan, level=level,
                                      merged_from_rule=merged_from_rule)

        # 1.5 补发短路（REQ-261016155500-4f2a wt:engine:2）：同条件存在未送达记录
        # （上轮发送失败、引擎未闩锁重试到这里）→ 只补发那一条（同一 trigger 行回写），
        # 不新建记录、不重复发送。
        prev = self._find_unsent(rule, condition)
        if prev is not None:
            payload0 = self._build_payload(rule, condition, quote, result, escalation_reason,
                                           action_amount_yuan=action_amount_yuan, level=level,
                                           merged_from_rule=merged_from_rule)
            ok = self._deliver_payload(rule, payload0, exec_directive=exec_directive)
            try:
                self.trigger_repo.mark_notified(prev.id, ok)
                prev.notified = ok
            except Exception as e:  # noqa: BLE001
                logger.error('notified 回写失败（补发）', trigger_id=prev.id, error=str(e))
            return prev

        # 2. 先落库（notified=False）→ 发送 → 回写：发送失败时 trigger 行已存在且
        #    notified=False，下 tick 经上方补发短路重发同一条（不新建不双发）。
        trigger = self._record(rule, condition, quote, result, notified=False,
                               disposition=disposition, disposition_reason=disposition_reason)
        trigger_id = getattr(trigger, 'id', None)

        # 3. 调用 NotificationFacade 发送通知
        logger.info(
            '发送盯盘触发通知',
            rule_id=rule.id,
            symbol=rule.symbol,
            trigger_level=payload.trigger_level,
            notify_mode='direct',  # trigger_level 退役（2026-10-22）：统一直发用户，agent 由 escalation 负责
            escalation_reason=escalation_reason,
            merged_from_rule=merged_from_rule,
        )
        notified = self._deliver_payload(rule, payload, exec_directive=exec_directive)

        # 4. 回写实际发送结果（notified = 真实送达与否，观测口径的事实源）
        if trigger is not None:
            try:
                self.trigger_repo.mark_notified(trigger_id, notified)
                trigger.notified = notified
            except Exception as e:  # noqa: BLE001 - 回写失败不得中断通知
                logger.error('notified 回写失败', trigger_id=trigger_id, error=str(e))

        # 5. WebSocket 广播
        self._broadcast_ws(payload)

        return trigger

    def record_only(self, rule, condition: dict, quote, result,
                    disposition: str = None, disposition_reason: str = None):
        """只落触发记录不发送（REQ-261016155500-4f2a wt:validate:1 观察聚合缓冲用）。

        无判据 observe 触发进 15 分钟聚合卡：逐条触发照常落库（审计不丢，
        notified=False + reason 标「已进聚合缓冲」），聚合卡本身由 aggregator 发送。
        """
        return self._record(rule, condition, quote, result, notified=False,
                            disposition=disposition, disposition_reason=disposition_reason)

    def _find_unsent(self, rule, condition: dict):
        """该规则最近一条 notified=False 且条件相同的触发；无则 None。"""
        repo = self.trigger_repo
        if repo is None:
            return None
        try:
            prev = repo.latest_unsent(getattr(rule, 'id', None))
        except Exception as e:  # noqa: BLE001
            logger.debug('未送达记录查询失败', error=str(e))
            return None
        if prev is None or not _same_condition(getattr(prev, 'condition', None), condition):
            return None
        # 聚合缓冲条目 notified=False 是设计值（合屏发送），不是"未送达"——不得补发，
        # 否则同一事件既进聚合卡又被即时补发（双通道重复）。
        if '聚合缓冲' in str(getattr(prev, 'disposition_reason', '') or ''):
            return None
        return prev

    def _deliver_payload(self, rule, payload, exec_directive=None) -> bool:
        """经 NotificationFacade 发送，返回是否送达；任何异常都不抛出（如实 False）。

        P0 执行指令（RFC 017 §2.1.2，卡 `exec-directive-card`）：`exec_directive`
        非空时把指令**并入通知正文的三个既有落点**，不改 facade 契约、不改模板：
          · `next_action_hint` → 级别模板 P0 卡的「下一步」（`_action_text` 最高优先）；
          · `action_params`    → MSG_V2 四段式的「建议动作」块（结构化买卖/数量/参考价）；
          · `context`          → 「预案」段追加三态处置（执行/不执行/超时）的收敛口径。
        指令与待办是**同一个对象**（构造点在 DeliverStage），故这里只渲染、不再构造。
        """
        try:
            next_action_hint = payload.next_action_hint
            action_params = payload.action_params
            context = payload.context
            if exec_directive is not None:
                next_action_hint = exec_directive.card_action_text()
                # 不可执行时不拿残缺指令顶替规则自己的结构化指引
                action_params = exec_directive.action_params() or action_params
                context = exec_directive.card_context(payload.context)
            # 构建 NotificationFacade 参数
            facade_result = self.notification_facade.send_watch_triggered(
                symbol=payload.symbol,
                name=payload.name or payload.symbol,
                price=payload.price,
                condition=payload.condition,
                message=payload.message,
                context=context,
                notify_mode='direct',  # trigger_level 退役（2026-10-22）：统一直发用户，agent 由 escalation 负责
                change_pct=payload.change_pct,
                pnl_pct=payload.pnl_pct,
                trigger_level=payload.trigger_level,
                action_hint=payload.to_notification_variables().get('action_hint'),
                escalation_reason=payload.escalation_reason,
                decision_audit_id=payload.decision_audit_id,
                intent=payload.intent,
                lifecycle_stage=payload.lifecycle_stage,
                next_action_hint=next_action_hint,
                account=payload.account,
                scope=payload.scope,
                action_amount_yuan=payload.action_amount_yuan,
                # REQ-c9f899 t12 §6-项2：金额门取数（缺失=None=门关闭，不抛错）
                account_total_yuan=self._account_total_yuan(rule),
                # REQ-c9f899 t12 §6-项1：级别随通知下发（无值走旧渲染，兼容非分级路径）
                level=payload.level,
                # REQ-ad0a FR-10：规则号随通知下发（模板显示真实号；缺失=None=手工）
                rule_id=getattr(rule, 'id', None),
                # REQ-261016155500-4f2a：结构化操作指引随通知下发（建议动作块数据源）；
                # P0 执行指令存在时以指令（数量/参考价来自持仓真值）为准
                action_params=action_params,
                # REQ-261016155500-4f2a wt:engine:2：dedup 合并展示标注
                merged_from_rule=payload.merged_from_rule,
            )
            return facade_result.success if hasattr(facade_result, 'success') else bool(facade_result)
        except Exception as e:
            logger.error('通知发送失败', symbol=payload.symbol, error=str(e))
            return False

    def _build_payload(self, rule, condition, quote, result, escalation_reason: str = None,
                       action_amount_yuan: float = None, level: str = None,
                       merged_from_rule: int = None) -> TriggerPayload:
        """构建 TriggerPayload"""
        price = float(quote.price)
        
        # 计算涨跌幅
        change_pct = None
        if getattr(quote, 'prev_close', None):
            change_pct = round((price - float(quote.prev_close)) / float(quote.prev_close) * 100, 2)
        elif getattr(quote, 'change_pct', None) is not None:
            change_pct = float(quote.change_pct)
        
        # 计算盈亏比例
        pnl_pct = None
        cost = getattr(rule, 'cost_price', None)
        if cost:
            pnl_pct = round((price - float(cost)) / float(cost) * 100, 2)
        
        # 名称兜底
        name = getattr(quote, 'name', None) or self._lookup_stock_name(rule.symbol)
        
        # 获取 trigger_level（从 action_hint 或 rule 属性）
        trigger_level = 'L1'  # 默认 L1
        action_hint = None
        
        # 尝试从 rule.action_hint 读取
        if hasattr(rule, 'action_hint') and rule.action_hint:
            import json
            try:
                if isinstance(rule.action_hint, str):
                    ah = json.loads(rule.action_hint)
                else:
                    ah = rule.action_hint
                trigger_level = ah.get('trigger_level', 'L1')
                from qs_watch.domain.watch.models import ActionHint, TriggerLevel
                action_hint = ActionHint(
                    trigger_level=TriggerLevel(trigger_level),
                    action_on_trigger=ah.get('action_on_trigger', 'observe'),
                    requires_agent=ah.get('requires_agent', False),
                    position_ref=ah.get('position_ref'),
                    confidence=ah.get('confidence'),
                    max_position_pct=ah.get('max_position_pct'),
                    stop_loss=ah.get('stop_loss'),
                    target_price=ah.get('target_price'),
                )
            except Exception as e:
                logger.warning('解析 action_hint 失败', rule_id=rule.id, error=str(e))
        
        # 如果是 L1→L2 升级，强制改为 L2
        if escalation_reason:
            trigger_level = 'L2'
        
        return TriggerPayload(
            rule_id=rule.id,
            symbol=rule.symbol,
            name=name,
            price=price,
            condition=condition,
            message=result.message,
            context=getattr(rule, 'context', None),
            trigger_level=trigger_level,
            action_hint=action_hint,
            escalation_reason=escalation_reason,
            change_pct=change_pct,
            pnl_pct=pnl_pct,
            # 2026-09-18（REQ-c9f899 t2）：只有真正产出 volume_ratio 的判据才能填量比字段；
            # 此前无条件把 result.value 当量比（price_break 的现价会被渲染成 388.5x 量比）。
            volume_ratio=(result.value if metric_matches(result, {MetricKind.VOLUME_RATIO}) else None),
            intent=getattr(rule, 'intent', None),
            lifecycle_stage=getattr(rule, 'lifecycle_stage', None),
            next_action_hint=getattr(rule, 'next_action_hint', None),
            account=getattr(rule, 'account', None),
            scope=getattr(rule, 'scope', None),
            action_amount_yuan=action_amount_yuan,
            level=level,
            # REQ-261016155500-4f2a：结构化操作指引（消息「建议动作」块权威数据源）
            action_params=getattr(rule, 'action_params', None),
            # REQ-261016155500-4f2a wt:engine:2：dedup 合并展示标注
            merged_from_rule=merged_from_rule,
            # 2026-10-19：「与我何干」（统一由 domain relation_of 产出）
            relation=_relation_of(rule, pnl_pct),
        )

    def record_governance(self, rule, reason: str, detail: dict = None):
        '''记录一条规则治理项（P8：去重从通知层的橡皮擦升级为规则层的体检项）。

        2026-09-11 用户指出：去重合并是业务上的偷懒——同标的同向被多条规则重复表达时，
        静默合并只是让症状闭嘴，根因（规则重叠）仍在。故跨规则重叠时：
          1. 仍然合并通知（避免同一次跌穿响多次）
          2. 另外落一条 meta_review 治理项 → 进未处置清单 → agent 决定合并/调参/退役
        '''
        if self.trigger_repo is None:
            return None
        try:
            return self.trigger_repo.record(
                rule_id=getattr(rule, 'id', None),
                symbol=getattr(rule, 'symbol', None),
                condition={'type': 'rule_overlap', 'params': detail or {}},
                trigger_price=None,
                detail={'message': reason, **(detail or {})},
                notified=False,
                disposition='meta_review',
                disposition_reason=reason,
                disposition_by='system',
            )
        except Exception as e:
            logger.error('治理项落库失败', error=str(e))
            return None

    def _broadcast_ws(self, payload: TriggerPayload):
        """WebSocket 广播（fire-and-forget，不阻塞 tick）。

        2026-10-19 异步化：此前同步 requests.post(timeout=3) 在通知主路径上——
        WS 服务卡住时每条触发最多拖慢 tick 3 秒。现提交到单工线程池：
        广播是给看板的实时增益，丢了不重试（下一条触发会带新状态），
        绝不反压到判定循环。
        """
        if not self.ws_url:
            return
        if self._ws_pool is None:
            self._ws_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='watch-ws')
        self._ws_pool.submit(self._post_ws, payload)

    def _post_ws(self, payload: TriggerPayload):
        try:
            requests.post(
                self.ws_url,
                json={'type': 'watch_triggered', 'data': payload.to_notification_variables()},
                timeout=3
            )
        except Exception as e:
            logger.debug('WS 广播失败（忽略）', error=str(e))

    def shutdown(self):
        """回收 WS 广播线程池（engine.stop 时调用；幂等）。"""
        if self._ws_pool is not None:
            self._ws_pool.shutdown(wait=False, cancel_futures=True)
            self._ws_pool = None

    def _record(self, rule, condition, quote, result, notified,
                disposition: str = None, disposition_reason: str = None, dup_of: int = None):
        """触发记录落库（含处置初态，返回落库后的触发对象供去重溯源）"""
        if self.trigger_repo is None:
            return None
        try:
            return self.trigger_repo.record(
                rule_id=rule.id,
                symbol=rule.symbol,
                condition=condition,
                trigger_price=float(quote.price),
                detail={'value': result.value, 'message': result.message},
                notified=notified,
                disposition=disposition or 'pending',
                disposition_reason=disposition_reason,
                dup_of=dup_of,
            )
        except Exception as e:
            logger.error('触发记录落库失败', error=str(e))
            return None
