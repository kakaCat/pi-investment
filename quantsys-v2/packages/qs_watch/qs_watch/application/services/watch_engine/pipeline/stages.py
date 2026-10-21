"""`_process_condition` 的 15 个「评估后」阶段（2026-10-21 从 engine 抽出）。

每个阶段与改造前引擎里的一步一一对应，阶段内代码按原顺序逐句搬运，
只把散装局部变量换成 `TriggerContext` 字段。阶段必须无状态：注册表在模块级
只构造一次，同一实例服务全部触发。

阶段顺序（注册表 `registry.DEFAULT_STAGES` 是唯一权威）：
  1 latch          闩锁/冷却/迟滞（TriggerJudge.should_emit）
  2 stale_residency 陈旧驻留（昨收已在触发侧 → 规则失真治理）
  3 env_gate       全局环境闸（个股总闸 + 止损/保护线豁免）
  4 confirm_verify 确认核验（仅 staged_break 确认：利空/流动性/共振）
  5 daily_cap      每日通知上限（宪法级豁免）
  6 noise_suppress 抑噪期短路（每日留一条样本）
  7 escalation     升级检查（L0/L1 → L2）
  8 disposition    处置决策五门（金额/增量/经济/预算/…）
  9 market_gate    per-rule 市场环境复合门（加严项）
 10 dedup          去重合并 / 跨规则重叠转治理
 11 deliver        通知或观察聚合缓冲（出口唯一处）
 12 daily_emit     日通知计数（送达成功才计数）
 13 todo           落待办（闭环载体）
 14 settle         送达后结算：去重标记 / 介入记账 / 止损使命退役
 15 finalize       闩锁回退 + 事件记录（含环境闸豁免溯源）
"""
from __future__ import annotations

from typing import Optional

import structlog

from qs_watch.application.services.watch_engine.conditions import freshness_of
from qs_watch.domain.watch.services import noise_policy
from qs_watch.domain.watch.services.disposition import (
    DISPOSITION_AUTO_OBSERVED, normalize_symbol,
)

from .constants import DAILY_CAP_REASON, SUPPRESSED_TRIGGER_REASON
from .context import TriggerContext
from .stage import StageResult

logger = structlog.get_logger(__name__)


class LatchStage:
    """#1 闩锁/冷却/迟滞：三段判定委托 TriggerJudge（未触发→重新武装等）。"""

    name = 'latch'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        # value=result.value：price_break 的迟滞带按现价判定（combined/velocity
        # 等非价格条件 value 语义不同或为空 → within_hysteresis_band 直接放行）。
        if not ctx.engine.judge.should_emit(
                ctx.rule.id, ctx.idx, ctx.result.triggered, ctx.cond, ctx.now,
                value=ctx.result.value):
            return StageResult.stop('latch')
        return None


class StaleResidencyStage:
    """#2 陈旧驻留：昨收已在触发侧 = 非今日新穿越（规则失真，非市场事件）。"""

    name = 'stale_residency'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        if freshness_of(ctx.cond, getattr(ctx.quote, 'prev_close', None)) is False:
            ctx.engine._handle_stale_residency(
                ctx.rule, ctx.idx, ctx.cond, ctx.quote, ctx.result, ctx.now)
            return StageResult.stop('stale_residency')
        return None


class EnvironmentGateStage:
    """#3 全局环境闸：环境不达标 → 个股信号全部只归档不动作。

    止损/保护线豁免只跳过**这一道**全局闸，后面的抑噪/升级/处置/per-rule
    market_gate/去重全部照旧（叠加语义不变）。
    """

    name = 'env_gate'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        env_gate = ctx.env_gate
        if not (env_gate and env_gate[0]):
            return None
        engine = ctx.engine
        rule = ctx.rule
        exempt, exempt_reason = engine._env_gate_exemption(rule, ctx.cond)
        if exempt:
            ctx.env_exempt_reason = exempt_reason
            logger.info('环境闸豁免（照常通知）', rule_id=rule.id,
                        symbol=rule.symbol, reason=exempt_reason)
            return StageResult.done('env_gate_exempt')
        ctx.env_exempt_reason = ''
        env_reason = env_gate[1]
        archived = engine._archive_environment_trigger(
            rule, ctx.cond, ctx.quote, ctx.result, env_reason)
        if archived is None:
            # 归档失败：不闩锁，下 tick 重试（at-least-once，同市场门口径）
            logger.error('环境闸归档失败（不闩锁，下 tick 重试）',
                         rule_id=rule.id, symbol=rule.symbol, reason=env_reason)
            return StageResult.stop('env_gate_archive_failed')
        engine.judge.mark_emitted(rule.id, ctx.idx, ctx.now, rule.symbol)
        ctx.events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                           'condition': ctx.cond, 'price': float(ctx.quote.price),
                           'message': ctx.result.message,
                           'disposition': DISPOSITION_AUTO_OBSERVED,
                           'disposition_reason': env_reason,
                           'dup_of': None, 'merged_from_rule': None,
                           'trigger_id': getattr(archived, 'id', None),
                           'trigger_level': engine._get_trigger_level(rule),
                           'suppressed': True,
                           'notified': False})
        logger.info('环境闸拦截（只记录不动作）', rule_id=rule.id,
                    symbol=rule.symbol, reason=env_reason,
                    trigger_id=getattr(archived, 'id', None))
        return StageResult.stop('env_gate_blocked')


class ConfirmVerifyStage:
    """#4 确认核验：仅 staged_break 确认成立时跑三道核验，失败只归档假信号。"""

    name = 'confirm_verify'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        if ctx.verify_confirm and not ctx.engine._confirm_verify(
                ctx.rule, ctx.cond, ctx.quote, ctx.result, ctx.now, ctx.events):
            return StageResult.stop('confirm_verify_failed')
        return None


class DailyCapStage:
    """#5 每日通知上限：超限只落 suppressed 归档（宪法级意图豁免）。"""

    name = 'daily_cap'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        engine = ctx.engine
        rule = ctx.rule
        if not (engine.judge.daily_emit_exceeded(rule.id, ctx.idx, ctx.now)
                and not engine._is_constitutional(rule)):
            return None
        capped = engine._record_suppressed_trigger(
            rule, ctx.cond, ctx.quote, ctx.result, reason=DAILY_CAP_REASON)
        engine.judge.mark_emitted(rule.id, ctx.idx, ctx.now, rule.symbol)
        ctx.events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                           'condition': ctx.cond, 'price': float(ctx.quote.price),
                           'message': ctx.result.message,
                           'disposition': DISPOSITION_AUTO_OBSERVED,
                           'disposition_reason': DAILY_CAP_REASON,
                           'dup_of': None,
                           'trigger_id': getattr(capped, 'id', None),
                           'trigger_level': engine._get_trigger_level(rule),
                           'suppressed': True,
                           'notified': False})
        logger.info('日上限触发已归档（不推送/不进队列）', rule_id=rule.id,
                    symbol=rule.symbol, trigger_id=getattr(capped, 'id', None))
        return StageResult.stop('daily_cap')


class NoiseSuppressStage:
    """#6 抑噪期短路：不升级、不进摘要队列、不建待办，每日只留一条样本。"""

    name = 'noise_suppress'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        rule = ctx.rule
        if not noise_policy.is_suppressed(
                getattr(rule, 'noise_state', None),
                getattr(rule, 'suppress_until', None), ctx.now):
            return None
        engine = ctx.engine
        # 归档节流（P1-6，2026-10-19）：抑噪期每日每规则只留一条 suppressed
        # 样本（账不丢、可复盘），后续触发只闩锁/冷却不再落库。
        if rule.id in engine.state.suppressed_reported:
            suppressed_trigger = None
        else:
            engine.state.suppressed_reported.add(rule.id)
            suppressed_trigger = engine._record_suppressed_trigger(
                rule, ctx.cond, ctx.quote, ctx.result)
        engine.judge.mark_emitted(rule.id, ctx.idx, ctx.now, rule.symbol)
        ctx.events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                           'condition': ctx.cond, 'price': float(ctx.quote.price),
                           'message': ctx.result.message,
                           'disposition': DISPOSITION_AUTO_OBSERVED,
                           'disposition_reason': SUPPRESSED_TRIGGER_REASON,
                           'dup_of': None,
                           'trigger_id': getattr(suppressed_trigger, 'id', None),
                           'trigger_level': engine._get_trigger_level(rule),
                           'suppressed': True,
                           'notified': False})
        logger.info('抑噪期触发已归档（不推送/不进队列）', rule_id=rule.id,
                    symbol=rule.symbol,
                    trigger_id=getattr(suppressed_trigger, 'id', None))
        return StageResult.stop('noise_suppressed')


class EscalationStage:
    """#7 升级检查：L0/L1 触发满足条件时自动升级为 L2。"""

    name = 'escalation'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        reason = ctx.engine.escalation.check(
            ctx.rule, ctx.cond, ctx.quote, ctx.result, ctx.now)
        ctx.escalation_reason = reason
        ctx.trigger_level = ctx.engine._get_trigger_level(ctx.rule)
        return StageResult.done(str(reason)) if reason else None


class DispositionStage:
    """#8 处置决策：机械优先（去重合并 / observe 归档当场收敛），零 LLM。"""

    name = 'disposition'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        disposition, reason = ctx.engine.disposition.decide(
            ctx.rule, ctx.cond, ctx.quote,
            escalated=bool(ctx.escalation_reason),
            escalation_reason=ctx.escalation_reason)
        ctx.disposition = disposition
        ctx.disposition_reason = reason
        return StageResult.done(str(disposition))


class MarketGateStage:
    """#9 per-rule 市场环境复合门（加严项）：环境异常日不接飞刀。

    全局环境闸已在 tick 前置拦截并 return；本门只在「环境闸放行/缺数据
    fail-open」时按规则自己的阈值加严。
    """

    name = 'market_gate'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        rule = ctx.rule
        ap = getattr(rule, 'action_params', None)
        gate = ap.get('market_gate') if isinstance(ap, dict) else None
        if not (gate and ctx.disposition in ('pending', 'escalated')):
            return None
        engine = ctx.engine
        blocked, gate_why = engine._check_market_gate(gate, ctx.now)
        if not blocked:
            return StageResult.done('market_gate_passed')
        try:
            gated_trigger = engine.notifier.record_only(
                rule, ctx.cond, ctx.quote, ctx.result,
                disposition=DISPOSITION_AUTO_OBSERVED,
                disposition_reason=gate_why)
        except Exception as e:  # noqa: BLE001 - 归档失败由调用方决定重试
            logger.error('市场门归档失败（不闩锁，下 tick 重试）',
                         rule_id=rule.id, error=str(e))
            return StageResult.stop('market_gate_archive_failed')
        engine.judge.bump_daily_emit(rule.id, ctx.idx, ctx.now)
        engine.judge.mark_emitted(rule.id, ctx.idx, ctx.now, rule.symbol)
        engine.dedup.mark_notified(rule, ctx.cond, ctx.now,
                                   getattr(gated_trigger, 'id', 0) or 0)
        ctx.events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                           'condition': ctx.cond, 'price': float(ctx.quote.price),
                           'message': ctx.result.message,
                           'disposition': DISPOSITION_AUTO_OBSERVED,
                           'disposition_reason': gate_why,
                           'dup_of': None, 'merged_from_rule': None,
                           'trigger_id': getattr(gated_trigger, 'id', None),
                           'trigger_level': engine._get_trigger_level(rule),
                           'notified': False})
        # 豁免溯源（2026-10-20）：全局闸已豁免、但规则自己的 market_gate
        # 更严 → 仍只归档。事件如实记录「为什么能走到二次校验」。
        if ctx.env_exempt_reason:
            ctx.events[-1]['env_gate_exempt'] = True
            ctx.events[-1]['env_gate_exempt_reason'] = ctx.env_exempt_reason
        logger.info('市场门拦截（只记录不动作）', rule_id=rule.id,
                    symbol=rule.symbol, reason=gate_why)
        return StageResult.stop('market_gate_blocked')


class DedupStage:
    """#10 去重：同标的同向窗内合并；跨规则重叠另转治理（每对每天一次）。"""

    name = 'dedup'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        engine = ctx.engine
        rule = ctx.rule
        outcome = engine.dedup.check(rule, ctx.cond, ctx.now)
        if not outcome.is_duplicate:
            return None
        if ctx.disposition in ('pending', 'auto_observed', 'ignored', 'expired'):
            ctx.disposition = 'deduped'
            ctx.disposition_reason = engine.dedup.reason_text(outcome)
            ctx.dup_of = outcome.dup_of
        else:
            # 守卫（REQ-261016155500-4f2a wt:engine:2）：dedup 命中不再无条件改判
            # deduped——escalated/exit_stop 是宪法级消息，只合并展示照发不误。
            ctx.merged_from_rule = outcome.prev_rule_id
            ctx.disposition_reason = (
                (ctx.disposition_reason + '；') if ctx.disposition_reason else ''
            ) + '与规则#%s 同事件（%ds 窗内），已合并展示但不吞消息' % (
                outcome.prev_rule_id, engine.dedup_window_sec)
        if outcome.overlap_pair:
            reason = engine.dedup.overlap_reason(outcome.overlap_pair, outcome.key)
            try:
                engine.notifier.record_governance(
                    rule, reason,
                    {'overlap_with_rule': outcome.overlap_pair[0],
                     'key': list(outcome.key)})
                logger.info('规则重叠已转治理',
                            rules=list(outcome.overlap_pair),
                            key=list(outcome.key))
            except Exception as e:  # noqa: BLE001 - 治理项失败不阻断携带
                logger.error('规则重叠治理项记录失败', error=str(e))
        return StageResult.done(str(ctx.disposition))


class DeliverStage:
    """#11 通知或观察聚合缓冲：唯一出口（发送失败不闩锁，下 tick 补发）。"""

    name = 'deliver'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        engine = ctx.engine
        rule = ctx.rule
        try:
            # 金额门取数复用一次（与级别判定的"是否持仓"输入同源，避免重复查库）
            ctx.action_amount = engine._position_value(rule)
            # 按级别渲染（t12 §6-项1）：仅闭环开启（todo_service 注入）时给级别；
            # 否则 None → 通知保持旧渲染（默认行为与改造前一致）。
            ctx.notify_level = engine._notify_level(
                rule, ctx.disposition, has_position=bool(ctx.action_amount))
            notify_kwargs = dict(
                escalation_reason=ctx.escalation_reason,
                disposition=ctx.disposition,
                disposition_reason=ctx.disposition_reason,
                dup_of=ctx.dup_of,
                action_amount_yuan=ctx.action_amount,
                merged_from_rule=ctx.merged_from_rule,
            )
            if ctx.notify_level:
                notify_kwargs['level'] = ctx.notify_level
            # 观察聚合路由（REQ-261016155500-4f2a wt:validate:1）：无判据 observe
            # 触发不进即时通道，落库后入 15 分钟聚合缓冲；有判据 observe 与
            # escalated/pending 等需动作类照旧即时单发。
            ctx.buffered = (engine.observe_agg is not None
                            and engine.observe_agg.should_buffer(rule, ctx.disposition))
            if ctx.buffered:
                buffer_reason = ((ctx.disposition_reason or '')
                                 + '；已进 15 分钟聚合缓冲（合屏发送）')
                trigger = engine.notifier.record_only(
                    rule, ctx.cond, ctx.quote, ctx.result,
                    disposition=ctx.disposition,
                    disposition_reason=buffer_reason)
                ctx.disposition_reason = buffer_reason
                from qs_watch.domain.watch.services.watch_message import (
                    relation_of, resolve_action,
                )
                engine.observe_agg.add(
                    getattr(rule, 'linked_account', None) or getattr(rule, 'account', None),
                    rule.symbol,
                    {'rule_id': rule.id,
                     'trigger_id': getattr(trigger, 'id', None),
                     'message': ctx.result.message,
                     'price': float(ctx.quote.price),
                     'name': getattr(ctx.quote, 'name', None),
                     'at': ctx.now.isoformat()},
                    ctx.now, float(ctx.quote.price),
                    action_text=resolve_action(
                        action_params=getattr(rule, 'action_params', None),
                        next_action_hint=getattr(rule, 'next_action_hint', None),
                        intent=getattr(rule, 'intent', None),
                        rule_id=rule.id).text,
                    relation_text=relation_of(
                        rule,
                        engine._pnl_of(rule, ctx.quote)))
            else:
                trigger = engine.notifier.notify(
                    rule, ctx.cond, ctx.quote, ctx.result, **notify_kwargs)
        except Exception as e:  # noqa: BLE001 - 不闩锁、下个 tick 重试（at-least-once）
            logger.error('通知发送失败', rule_id=rule.id, cond=ctx.cond, error=str(e))
            return StageResult.stop('notify_failed')
        ctx.trigger = trigger
        if ctx.buffered:
            return StageResult.done('buffered')
        return StageResult.done(
            'notified' if getattr(trigger, 'notified', False) else 'not_notified')


class DailyEmitCountStage:
    """#12 日通知计数：送达成功才计一次（notifier 内部吞异常并回填 notified）。"""

    name = 'daily_emit'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        # 聚合缓冲也计入日上限（2026-10-19）：缓冲路径 trigger.notified 恒 False
        # （设计上不单发），此前 observe 聚合通道完全不受日上限约束——恰是噪音
        # 最大的通道。入缓冲即计一次（用户会在聚合卡里看到它）。
        if (ctx.buffered or ctx.trigger is None
                or getattr(ctx.trigger, 'notified', False)):
            ctx.engine.judge.bump_daily_emit(ctx.rule.id, ctx.idx, ctx.now)
        return None


class TodoStage:
    """#13 落待办：闭环唯一载体（触发 → L1→L2→L3 晋升 + 到期巡检 + 回执）。"""

    name = 'todo'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        if ctx.buffered:
            # 聚合缓冲的触发不建待办（2026-10-19）：无判据 observe 属「记录不打扰」，
            # 且聚合卡最长 15 分钟后才到用户——待办 SLA 时钟不应早于用户可见。
            return StageResult.done('skipped_buffered')
        try:
            ctx.engine._create_watch_todo(
                ctx.rule, ctx.now, ctx.disposition, ctx.trigger, ctx.notify_level)
        except Exception as e:  # noqa: BLE001 - 双保险：helper 已自吞异常，tick 不许被打挂
            logger.error('建待办异常（tick 继续）', rule_id=ctx.rule.id, error=str(e))
        return None


class SettleStage:
    """#14 送达后结算：去重标记 / 介入记账 / 止损使命退役。"""

    name = 'settle'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        engine = ctx.engine
        rule = ctx.rule
        if ctx.disposition != 'deduped':
            engine.dedup.mark_notified(
                rule, ctx.cond, ctx.now, getattr(ctx.trigger, 'id', 0) or 0)
        if ctx.disposition == 'escalated':
            # 增量门 + 预算记账：escalated = 进 agent 摘要队列 = 一次潜在介入
            norm = normalize_symbol(rule.symbol)
            intent = str(getattr(rule, 'intent', '') or '') or str(
                (rule.action_hint or {}).get('action_on_trigger', '')
                if isinstance(getattr(rule, 'action_hint', None), dict) else '')
            engine.state.last_intervention[(norm, intent or 'unknown')] = ctx.now
            engine.state.interventions_today += 1
            if engine.ledger is not None:
                engine.ledger.record(
                    symbol=rule.symbol, intent=(intent or None), rule_id=rule.id,
                    trigger_kind='price', outcome='escalated',
                    trigger_ids=[getattr(ctx.trigger, 'id', None)],
                )
        # 止损使命完成自动退役（2026-10-19 用户裁定）：exit_stop 触发即消费，
        # 原阈值已失效；未平仓的新风控线由 agent 起草、用户确认后重建。
        engine._maybe_retire_executed_stop(rule, ctx.disposition, ctx.now)
        return None


class FinalizeStage:
    """#15 闩锁回退 + 事件记录（含环境闸豁免溯源）。"""

    name = 'finalize'

    def run(self, ctx: TriggerContext) -> Optional[StageResult]:
        engine = ctx.engine
        rule = ctx.rule
        engine.judge.mark_emitted(rule.id, ctx.idx, ctx.now, rule.symbol)
        # 未送达不闩锁（REQ-261016155500-4f2a wt:engine:2）：notifier 先落库后
        # 发送，失败时 trigger.notified=False——回退闩锁/冷却，下个 tick 重判再走
        # notify 的补发短路（同一 trigger 行重发，不新建不双发）。
        # ⚠️ 聚合缓冲路径（buffered=True）的 trigger.notified 恒为 False（设计上
        # 就不单发），绝不可走这里——否则闩锁/冷却每发即毁，规则每 60s 复读。
        if (not ctx.buffered and ctx.trigger is not None
                and not getattr(ctx.trigger, 'notified', False)):
            engine.state.latched.discard((rule.id, ctx.idx))
            engine.state.last_triggered.pop((rule.id, ctx.idx), None)
        ctx.events.append({'rule_id': rule.id, 'symbol': rule.symbol,
                           'condition': ctx.cond, 'price': float(ctx.quote.price),
                           'message': ctx.result.message,
                           'disposition': ctx.disposition,
                           'disposition_reason': ctx.disposition_reason,
                           'dup_of': ctx.dup_of,
                           'merged_from_rule': ctx.merged_from_rule,
                           'trigger_id': getattr(ctx.trigger, 'id', None),
                           'trigger_level': ctx.trigger_level,
                           'notified': bool(getattr(ctx.trigger, 'notified', False))})
        # 豁免溯源（2026-10-20）：止损/保护线信号是在环境闸拦截日被放行的——
        # 事件必须带得出「为什么它没被拦」，否则复盘无法区分正常日与豁免日。
        if ctx.env_exempt_reason:
            ctx.events[-1]['env_gate_exempt'] = True
            ctx.events[-1]['env_gate_exempt_reason'] = ctx.env_exempt_reason
        return None

