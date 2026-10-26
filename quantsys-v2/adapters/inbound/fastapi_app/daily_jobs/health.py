"""规则健康检查与事件日历（拆分自 daily_jobs_bootstrap.py）

2026-10-01（REQ-261001145152-3982 t-686185）：由 daily_jobs_bootstrap.py 机械拆分而来
（原文件 1147 行）。函数体与签名**逐字未改**；原模块保留为转发壳，既有导入路径不受影响。
"""
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from typing import Any, Callable, Dict, List, Optional

import structlog

# 失败判定口径唯一来源（含嵌套下钻）：与 APScheduler 路径共用，避免两套标准
from infrastructure.scheduler.job_executor import find_result_failure
from adapters.inbound.fastapi_app.daily_jobs.alerting import _send_feishu  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.defs import logger  # noqa: F401

_EVENT_TYPE_LABELS = {
    'cpi_ppi': '📊 CPI/PPI', 'pmi': '🏭 PMI', 'nbs': '📈 国民经济数据',
    'lpr': '🏦 LPR', 'fomc': '🇺🇸 FOMC 议息', 'us_cpi': '🇺🇸 CPI',
    'nfp': '🇺🇸 非农', 'earnings': '📋 财报披露', 'futures_delivery': '⚙️ 期货交割',
    'policy': '📜 政策事件', 'other': '📌 其他',
}

#: 预案日期的**标签前缀**——只有带这些标签的日期才被当作预案日期。
#:
#: 2026-10-21 修复（误伤事故）：原实现用宽松正则从 context 散文里抓任意
#: 「M/D」或「YYYY-MM-DD」当作预案日期。R-022 分批止盈文案「卖出 1/3 锁定利润」
#: 被读成「1月3日」（已过去 291 天）⇒ 规则判 OUTDATED ⇒ 当天 16:30:15 自动禁用。
#: **全库 80 条规则带同款雷**（35 account=null / 35 agent_brain / 5 agent_virtual /
#: 5 user_main_simulation）；已实测 #269（600000 止盈）、#295（601600 止盈）被误禁用。
#:
#: 修复口径：**只认显式标注的日期**，不再从自由文本推断。散文里的裸数字
#: （"1/3"、"10/20 跌破8.40" 等）一律不解释为日期。
_PREPLAN_DATE_LABEL_PATTERN = re.compile(
    r'(?:预案日期|有效期至|有效期|截止日期|到期日|失效日期)\s*[:：]\s*'
    r'(\d{4})-(\d{1,2})-(\d{1,2})'
)


def find_labelled_preplan_date(context: Optional[str]) -> Optional[datetime]:
    """从 context 中找出**带标签**的预案日期；没有则返回 None。

    纯函数（不碰 DB、不看当前时间），便于单测与复用。

    Args:
        context: 规则 context 自由文本。

    Returns:
        第一个带标签的日期（datetime），无标签日期时返回 None。
    """
    if not context:
        return None
    for match in _PREPLAN_DATE_LABEL_PATTERN.findall(context):
        try:
            year, month, day = int(match[0]), int(match[1]), int(match[2])
            return datetime(year, month, day)
        except (ValueError, IndexError):
            continue
    return None

def _job_watch_rule_health() -> Dict[str, Any]:
    """规则健康检查：每天收盘后评估所有启用规则的健康度（2026-10-22 对齐三分支）。

    标失效（进 agent 裁决闭环，agent 可续期回 active / 退役归 archived）：
    - EXPIRED: 已过有效期
    - OUTDATED: 预案日期已过期

    停用直接禁用：
    - STALE（价格偏差）：已由「盘中实时失效判定」按 agent 设定的
      invalidation_threshold_pct 覆盖——此处不再用写死 20% 直接 enabled=false，
      避免和 agent 阈值打架。

    标记审查（不动）：
    - INACTIVE: 30天未触发

    飞书通知：健康度报告
    """
    import json

    # 取数收口到仓储（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：
    # 原先整段跑在一个 with engine.begin() as conn 里，用裸 SQL 读 watch_rules、
    # 逐条查 daily_klines 最新收盘、查 watch_triggers 最近触发，并就地 UPDATE 禁用。
    # 现读走三个仓储，写走 WatchRuleRepository.update_fields。
    #
    # 事务语义差异（已确认对结果无影响）：原实现循环结束后统一提交（中途抛异常则全部回滚），
    # 现在每条禁用即时提交（update_fields 内部 commit）。循环内除禁用外没有任何其它写操作；
    # 对"每天收盘后跑一次"的巡检而言，半途失败不该丢掉已经判定的结论，故按新语义保留。
    from adapters.outbound.repositories.watch_rule_repository import (
        WatchRuleRepository, WatchTriggerRepository,
    )
    from adapters.outbound.repositories.kline_repository import KlineORMRepository

    rule_repo = WatchRuleRepository()
    trigger_repo = WatchTriggerRepository()
    kline_repo = KlineORMRepository()

    reports = []
    # 2026-10-22 对齐三分支失效闭环：
    #  · EXPIRED/OUTDATED → auto_invalidated（标 invalid 进 agent 裁决闭环，不再裸 enabled=false）
    #  · STALE（价格偏离）→ stale_deferred（停用——盘中实时失效判定已按 agent 设定的
    #    invalidation_threshold_pct 覆盖，此处不再用写死 20% 直接禁用，避免两套失效标准打架）
    auto_invalidated = []
    stale_deferred = []
    marked_inactive = []

    # 与原来的 FROM quant.watch_rules WHERE enabled = true 等价。
    # 注意：**不能用 list_enabled()** —— 那个方法会把已过期规则过滤掉，
    # 而本函数的 EXPIRED 分支正是要吃这些行并把它们禁用。
    for rule in rule_repo.list_rules(enabled=True):
        rule_id, symbol = rule.id, rule.symbol
        context, conditions = rule.context, rule.conditions
        expires_at, created_at = rule.expires_at, rule.created_at
        status = 'HEALTHY'
        reason = '正常'
            
        # 1. 检查有效期
        if expires_at and expires_at < datetime.now():
            status = 'EXPIRED'
            reason = f'已过有效期（{expires_at.strftime("%Y-%m-%d")}）'
        else:
            # 2. 检查价格偏差
            try:
                # 获取当前价格（仓储口径：无 K 线返回 None，与原 fetchone() 空行为等价）
                current_close = kline_repo.get_latest_close(symbol)
                    
                if current_close is not None and conditions:
                    current_price = float(current_close)
                    conds = json.loads(conditions) if isinstance(conditions, str) else conditions
                        
                    # 提取触发价格
                    trigger_price = None
                    for cond in conds:
                        if isinstance(cond, dict):
                            params = cond.get('params', {})
                            if 'price' in params:
                                trigger_price = float(params['price'])
                                break
                        
                    if trigger_price and trigger_price > 0:
                        deviation = abs(current_price - trigger_price) / trigger_price * 100
                        if deviation > 20:
                            status = 'STALE'
                            reason = f'价格偏差{deviation:.1f}%（当前{current_price} vs 设定{trigger_price}）'
                    
                # 3. 检查预案日期（如果还没被标记为 STALE）
                #
                # 2026-10-21 修复（误伤事故）：原实现用宽松正则从 context **散文**里
                # 抓任意「M/D」或「YYYY-MM-DD」当作预案日期。R-022 分批止盈的文案
                # 「卖出 1/3 锁定利润」被读成「1月3日」（已过去 291 天）⇒ 规则判
                # OUTDATED ⇒ 当天 16:30:15 自动禁用。**全库 80 条规则带同款雷**
                # （35 account=null / 35 agent_brain / 5 agent_virtual /
                #   5 user_main_simulation），已实测 #269（600000 止盈）、
                #   #295（601600 止盈）因此被误禁用。
                #
                # 修复口径（见 find_labelled_preplan_date 的 docstring）：**只认显式
                # 标注的日期**，不再从自由文本推断——① 结构化 expires_at（第 1 步已判
                # EXPIRED）② context 中带「预案日期：」等标签前缀的日期。
                if status == 'HEALTHY' and context:
                    date_obj = find_labelled_preplan_date(context)
                    if date_obj is not None:
                        days_diff = (datetime.now() - date_obj).days
                        if days_diff > 7:
                            status = 'OUTDATED'
                            reason = f'预案日期已过期（{date_obj.strftime("%Y-%m-%d")}，已过去{days_diff}天）'
                    
                # 4. 检查触发活跃度（如果还没被标记）
                if status == 'HEALTHY':
                    # 无触发行与 MAX 为 NULL 都返回 None，与原 trigger_row[0] if trigger_row else None 一致
                    last_trigger = trigger_repo.get_last_triggered_at(rule_id)
                        
                    if last_trigger:
                        days_since = (datetime.now() - last_trigger).days
                        if days_since > 30:
                            status = 'INACTIVE'
                            reason = f'{days_since}天未触发（上次：{last_trigger.strftime("%Y-%m-%d")}）'
                    elif created_at:
                        days_since = (datetime.now() - created_at).days
                        if days_since > 30:
                            status = 'INACTIVE'
                            reason = f'创建后{days_since}天从未触发'
                
            except Exception as e:
                logger.warning('规则健康检查异常', rule_id=rule_id, error=str(e))
            
        reports.append({
            'rule_id': rule_id,
            'symbol': symbol,
            'status': status,
            'reason': reason,
        })
            
        # 自动处理（2026-10-22 对齐三分支失效闭环）
        if status == 'STALE':
            # 价格偏离失效已由「盘中实时失效判定」负责（按 agent 设定的
            # invalidation_threshold_pct 标 invalid + 投递裁决）——此处不再用写死 20%
            # 直接禁用，避免和 agent 阈值打架（agent 设 30% 时偏离 25% 不该被禁用）。
            stale_deferred.append({'rule_id': rule_id, 'symbol': symbol, 'reason': reason})
        elif status in ('EXPIRED', 'OUTDATED'):
            # 时间维度失效：对齐三分支——标 invalid（agent 可裁决续期回 active /
            # 退役归 archived），不再裸 enabled=false（那会让规则静默消失、绕过裁决闭环）。
            rule_repo.update_fields(rule_id, rule_state='invalid',
                                    invalid_reason=reason, invalid_at=datetime.now())
            auto_invalidated.append({'rule_id': rule_id, 'symbol': symbol, 'reason': reason})
        elif status == 'INACTIVE':
            marked_inactive.append({'rule_id': rule_id, 'symbol': symbol, 'reason': reason})
    
    # 生成飞书通知
    if auto_invalidated or stale_deferred or marked_inactive:
        lines = [f'🧹 【规则健康检查】{datetime.now().strftime("%Y-%m-%d")}', '']

        if auto_invalidated:
            lines.append('已标失效（待 agent 裁决续期 / 退役）：')
            for d in auto_invalidated:
                lines.append(f"- 规则#{d['rule_id']} {d['symbol']}：{d['reason']}")
            lines.append('')

        if stale_deferred:
            lines.append(f'价格偏离 {len(stale_deferred)} 条：已由盘中实时失效判定'
                         f'（按 agent 设定的阈值）覆盖，本巡检不再直接禁用。')
            lines.append('')

        if marked_inactive:
            lines.append('待人工审查：')
            for d in marked_inactive:
                lines.append(f"- 规则#{d['rule_id']} {d['symbol']}：{d['reason']}")
            lines.append('')

        # 统计
        healthy_count = len([r for r in reports if r['status'] == 'HEALTHY'])
        lines.append(f'统计：总数 {len(reports)} 条 | 健康 {healthy_count} 条 | '
                     f'标失效 {len(auto_invalidated)} 条 | 偏离移交实时判定 {len(stale_deferred)} 条 | '
                     f'待审查 {len(marked_inactive)} 条')

        _send_feishu('\n'.join(lines))

    return {
        'status': 'success',
        'total': len(reports),
        'healthy': len([r for r in reports if r['status'] == 'HEALTHY']),
        'auto_invalidated': len(auto_invalidated),
        'stale_deferred': len(stale_deferred),
        'marked_inactive': len(marked_inactive),
        'details': reports,
    }


def _event_md(e) -> str:
    """单条事件的卡片 Markdown"""
    d = e.event_date
    dd = f'{d.month:02d}-{d.day:02d}' if d else '??-??'
    label = _EVENT_TYPE_LABELS.get(e.event_type or 'other', '📌 其他')
    flag = '🚨' if (e.importance or 1) >= 3 else '🔸'
    line = f'{flag} **{dd}** {label}：{e.title}'
    if e.event_time:
        line += f'（{e.event_time.strftime("%H:%M")}）'
    desc = (e.description or '').strip()
    if desc:
        line += f'\n　{desc[:60]}{"…" if len(desc) > 60 else ""}'
    return line


def _job_event_calendar_check() -> Dict[str, Any]:
    """事件日历检查：未来2日 pending 且重要性>=2 的事件 → 飞书提醒 → 标记 notified。

    幂等：只处理 status=='pending'；发送成功即 mark notified（meta 记 notified_by），
    框架失败重试只会补发未成功的——已 notified 的不再命中，事件提醒至多一次。
    无目标事件时返回 no_event（不打扰）。
    """
    from adapters.outbound.repositories.event_calendar_repository import (
        get_event_calendar_repo,
    )
    # 2026-09-11（w-23c70356）：改走 NotificationFacade（原直接 new 旧版
    # FeishuNotificationService，绕过 DDD 通知域）
    from qs_notification.application import get_notification_facade

    events = get_event_calendar_repo().list_upcoming(days_ahead=2)
    target = [e for e in events if e.status == 'pending' and (e.importance or 1) >= 2]
    if not target:
        return {'status': 'no_event', 'pending_in_window': len(events), 'notified': 0}

    high = [e for e in target if e.importance >= 3]
    mid = [e for e in target if e.importance < 3]
    svc = get_notification_facade()
    sent_ids: List[int] = []
    fail: Optional[Exception] = None

    def _send_batch(title: str, urgency: str, items: List[Any]) -> None:
        nonlocal fail
        try:
            ok = svc.send_card(title=title, content='\n'.join(_event_md(e) for e in items),
                               urgency=urgency)
        except Exception as ex:  # noqa: BLE001
            fail = ex
            return
        if not ok:
            fail = RuntimeError('feishu send_card returned False')
            return
        sent_ids.extend(e.id for e in items)

    if high:
        _send_batch('🚨 未来2日高优事件预警', 'high', high)
    if mid and fail is None:
        _send_batch('📌 未来2日事件提醒', 'normal', mid)

    repo = get_event_calendar_repo()
    for eid in sent_ids:
        repo.mark_status(eid, 'notified', meta_patch={
            'notified_at': datetime.now().isoformat(timespec='seconds'),
            'notified_by': 'event_calendar_check',
        })

    if fail is not None:
        raise RuntimeError(f'feishu send failed（重试将只补未 notified 的）: {fail}')
    return {'status': 'notified', 'notified': len(sent_ids),
            'high': len(high), 'mid': len(mid)}


def _job_invalid_escalation() -> Dict[str, Any]:
    """失效规则滞留升级（2026-10-22 用户裁定）。

    三分支里 invalid = "agent 待裁决（改/删）"。agent 该处理却超龄（默认 24h）未处理
    → 这些规则标记出来、发盯盘群给用户，请用户推进（改阈值回 active / 退役归 archived）。
    提醒后写 invalid_escalated_at（每个规则只提醒一次，不天天刷同一条）。

    走 send_watch_alert（用户盯盘群）而非 _send_feishu（运维群）——这是**用户要推进的
    行动项**，不是系统运维消息（2026-10-14 分群裁定的边界）。
    """
    from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
    from qs_watch.application.services.watch_engine.watch_channels import send_watch_alert

    repo = WatchRuleRepository()
    stale = repo.list_stale_invalid(older_than_hours=24)
    if not stale:
        return {'stale': 0, 'escalated': 0, 'sent': False}

    now = datetime.now()
    lines = [
        f'⏰ 【失效规则待你推进】{now.strftime("%Y-%m-%d")}',
        f'{len(stale)} 条规则已失效超 24h，agent 未裁决。请推进（改阈值回盯盘 / 退役清理）：',
        '',
    ]
    for r in stale:
        age = now - (r.invalid_at or now)
        age_str = f'{age.days}天{age.seconds // 3600}时' if age.days else f'{age.seconds // 3600}时'
        lines.append(f"- 规则#{r.id} {r.symbol}：{str(r.invalid_reason or '')[:60]}（滞留 {age_str}）")
    lines.append('')
    lines.append('处置：PATCH /api/watch/rules/{id}，rule_state=active（调阈值续用）/ archived（退役）')

    sent = False
    try:
        sent = bool(send_watch_alert('\n'.join(lines)))
    except Exception as e:  # noqa: BLE001 - 发送失败不阻断标记（下轮不重复刷）
        logger.error('失效规则滞留提醒发送失败', error=str(e))

    # 标记已提醒（发送成败都标记，避免同一规则每天重复刷；只记日志不抛）
    marked = 0
    for r in stale:
        try:
            repo.update_fields(r.id, invalid_escalated_at=now)
            marked += 1
        except Exception as e:  # noqa: BLE001
            logger.error('滞留标记失败', rule_id=getattr(r, 'id', None), error=str(e))
    return {'stale': len(stale), 'escalated': marked, 'sent': sent}
