"""WatchEngine 盯盘规则/触发记录 ORM Repository"""
from datetime import datetime
from typing import List, Optional

import structlog
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Numeric, Text, ForeignKey, or_, func,
    bindparam, case, update as sa_update, insert as sa_insert,
    update as sa_table_update, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import load_only
from sqlalchemy.orm.attributes import set_committed_value

from qs_kernel.infrastructure.persistence.orm import BaseORMRepository
from qs_kernel.infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)

# ── RFC 017（2026-10-21）：持仓状态显式化 / 规则级盯盘频率 ────────────────────
# position_state: 'none' = 无持仓（entry 族可求值）/ 'holding' = 有持仓（exit 族可求值）。
# NULL 与"列不存在"都表示**状态未知** —— 引擎必须按旧行为 fail-open（照常评估），
# 绝不因为状态缺失而静默不评估（止损永远优先于状态机正确性，RFC 017 §2.2）。
POSITION_STATE_NONE = 'none'
POSITION_STATE_HOLDING = 'holding'
POSITION_STATES = (POSITION_STATE_NONE, POSITION_STATE_HOLDING)

#: 迁移 20261021_watch_rules_position_interval.py 新增的两列。
NEW_RULE_COLUMNS = ('position_state', 'interval_sec')

#: 列预检的缓存（key = engine url）。列一旦落库不会消失，缓存 True 安全；
#: 迁移在运行中落地时调 reset_watch_rules_column_cache() 或重启进程即可。
_COLUMNS_PRESENT_CACHE: dict = {}

_COLUMNS_SQL = text(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema = 'quant' AND table_name = 'watch_rules'"
)


def reset_watch_rules_column_cache() -> None:
    """清空列预检缓存（测试/迁移后热生效用）。"""
    _COLUMNS_PRESENT_CACHE.clear()


def normalize_position_state(value) -> str:
    """写入口径：None/空 → 'none'；只接受 none/holding（大小写不敏感）。

    非法值抛 ValueError —— 静默落库一个引擎读不懂的状态，等于让规则的分支行为
    变成抽奖；让调用方（API → 400）当场知道。
    """
    if value is None:
        return POSITION_STATE_NONE
    text_value = str(value).strip().lower()
    if text_value in ('', 'none', 'null'):
        return POSITION_STATE_NONE
    if text_value == POSITION_STATE_HOLDING:
        return POSITION_STATE_HOLDING
    raise ValueError("position_state 只接受 none/holding（收到的：%r）" % (value,))


def normalize_interval_sec(value) -> Optional[int]:
    """写入口径：None/空 → None（跟随全局 base/fast 档）；否则为正整数秒。

    RFC 017 §2.3 的 5s 下限属**引擎调度保护**（同一个 interval_sec 在引擎侧被
    clamp），仓储只拒绝无法解释的值（0/负数/非整数）。
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, bool):
        raise ValueError('interval_sec 必须是整数秒或 None（收到布尔值）')
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        raise ValueError('interval_sec 必须是整数秒或 None（收到的：%r）' % (value,))
    if seconds < 1:
        raise ValueError('interval_sec 必须 >= 1 秒，或给 None 表示跟随全局档')
    return seconds


def rule_position_state(rule) -> Optional[str]:
    """读口径（fail-open）：'none'/'holding'；NULL、缺列、未知值 → None。

    **None 不等于 'none'**：'none' 是"确认无持仓"，None 是"状态不可知"。
    调用方拿到 None 必须退回旧行为（不按状态分支、照常评估），而不是当成无持仓。
    """
    try:
        raw = getattr(rule, 'position_state', None)
    except Exception:  # noqa: BLE001 - 分离态/过期对象/缺列懒加载失败都按未知处理
        raw = None
    if raw is None:
        return None
    try:
        return normalize_position_state(raw)
    except ValueError:
        logger.debug('未知 position_state，按状态不可知 fail-open',
                     rule_id=getattr(rule, 'id', None), value=raw)
        return None


def rule_interval_sec(rule) -> Optional[int]:
    """读口径（fail-open）：正整数秒；NULL、缺列、非法值 → None（跟随全局档）。"""
    try:
        raw = getattr(rule, 'interval_sec', None)
    except Exception:  # noqa: BLE001
        return None
    if raw is None:
        return None
    try:
        return normalize_interval_sec(raw)
    except ValueError:
        logger.debug('非法 interval_sec，按未设置处理',
                     rule_id=getattr(rule, 'id', None), value=raw)
        return None


class WatchRule(Base):
    __tablename__ = 'watch_rules'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    enabled = Column(Boolean, default=True)
    conditions = Column(JSONB, nullable=False)
    context = Column(Text)
    cost_price = Column(Numeric(12, 4))
    active_window = Column(JSONB)
    expires_at = Column(DateTime)
    created_by = Column(String(50), default='agent')
    # account：规则归属账户（account_name 全名）。None=通用观察（无主/跨账户候选，
    # 2026-09-04 看板按账户分组展示用）。历史规则由迁移脚本按 context/持仓回填。
    account = Column(String(50))
    # notify_mode：direct=v2 直发飞书（纯提醒）；agent=唤醒 LLM 分析后再发
    # （2026-09-02 修复：模型此前漏此列，致 getattr 拿不到、agent 模式静默降级为 direct）
    notify_mode = Column(String(20), default='direct')
    # RFC 011：分层提醒与自动升级
    action_hint = Column(JSONB, default={})
    escalation_policy = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    # ── 价值生命周期（REQ-f08def P1/P4/P7，RFC 014 v3 §7.1）──────────────
    # 2026-09-11 实测教训（两次踩）：①migration 加了 DB 列但 ORM 未声明 →
    # intent/lifecycle_stage/scope/价值账本对 ORM 完全不可见，update_fields 的改动
    # 也不落库（#120 改成 entry 看似成功、库里仍是旧值）；②锚点 agent_response 在
    # WatchTrigger 里也有，第一次补列插错了类。补 ORM 列时必须做唯一性断言。
    intent = Column(String(30))
    lifecycle_stage = Column(String(30), default='tracking')
    scope = Column(String(20), default='symbol')
    target = Column(String(60))
    linked_account = Column(String(60))
    created_from = Column(String(80))
    next_action_hint = Column(String(160))
    last_reviewed_at = Column(DateTime)
    review_interval_days = Column(Integer)
    review_due_at = Column(DateTime)
    burst_count_window = Column(Integer, default=0)
    last_burst_alert_at = Column(DateTime)
    valuable_actions = Column(Integer, default=0)
    valuable_reviews = Column(Integer, default=0)
    interventions = Column(Integer, default=0)
    noise_triggers = Column(Integer, default=0)
    tokens_cost = Column(Numeric(12, 4), default=0)
    last_value_at = Column(DateTime)

    # ── 规则自愈抑噪态（REQ-c9f899 R6 / t8，2026-09-18）─────────────────
    # t1 迁移 20260918 为 watch_rules 加了四个列（noise_state / suppress_until /
    # self_heal_count / last_repair_at）。引擎判定"是否处于抑噪期"需要前两个：
    # 不映射则 getattr(rule, 'noise_state') 恒为 None → 抑噪形同虚设（与 2026-09-11
    # intent/lifecycle_stage 漏映射同一坑）。此处**只读声明**，不改列语义；
    # self_heal_count / last_repair_at 的读写仍由 watch_rule_noise_repository（本任务）
    # 用裸 SQL 承担，避免同一张表两处 ORM 映射打架。
    noise_state = Column(String(16))
    suppress_until = Column(DateTime)

    # ── 决策化改造（REQ-261016155500-4f2a，2026-10-16）─────────────────────
    # action_params：结构化操作指引——消息"建议动作"块的唯一权威数据源
    # （schema: action ∈ buy/sell/hold/reduce/observe、reference_price、
    #  position_pct|quantity、invalidation（重估条件）、observation_criterion）。
    # ops_notes：机器注记数组 [{at, by, text}]——健康检查巡检/事实校正等机器写入
    # 的注记从 context 剥离到这里，不进用户视野（消息只引用剥离后的真预案）。
    # 列由迁移 20261016_watch_rules_upgrade.py 添加。
    action_params = Column(JSONB)
    ops_notes = Column(JSONB)

    # ── 持仓状态 / 规则级频率（RFC 017 §2.2/§2.3，2026-10-21）────────────────
    # 列由迁移 20261021_watch_rules_position_interval.py 添加：
    #   position_state varchar(16) NOT NULL DEFAULT 'none'（none/holding）
    #   interval_sec   integer NULL（NULL = 跟随全局 base 60s / fast 10s 档）
    # ⚠️ 刻意**不给 Python 侧默认值**：有 Python 默认值（哪怕是个常量）SQLAlchemy
    # 就会把它写进 INSERT，迁移未落库的库上 INSERT 直接 UndefinedColumn。
    # 现在"不传就不进 INSERT"，由 DB 默认 'none' 兜住 —— 这是缺列兼容的一半；
    # 另一半是读路径的 _rule_query() 预检（见 WatchRuleRepository）。
    # ⚠️ 两个 server_default 不是为了 DDL（列由迁移建），而是给 SQLAlchemy 的信号：
    # "本列未显式给值时不要进 INSERT"。没有它时 ORM 会把 NULL 写进 INSERT，
    # 既违反 position_state 的 NOT NULL，又会在缺列库上 UndefinedColumn ——
    # 实测第一版（无 server_default）就是这么把 6 个既有仓储测试打红的。
    position_state = Column(String(16), server_default=text("'none'"))
    interval_sec = Column(Integer, server_default=text('NULL'))


class WatchTrigger(Base):
    __tablename__ = 'watch_triggers'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('quant.watch_rules.id', ondelete='SET NULL'))
    symbol = Column(String(20), nullable=False)
    condition = Column(JSONB, nullable=False)
    trigger_price = Column(Numeric(12, 4))
    detail = Column(JSONB)
    agent_response = Column(JSONB)
    notified = Column(Boolean, default=False)
    triggered_at = Column(DateTime, default=datetime.now)
    # ── 处置状态机（REQ-f08def，2026-09-11）─────────────────────────────
    # 为什么要落库：实测近 200 条触发 agent_response 全为 null，触发无终态 = 无闭环。
    # disposition 让每条触发有明确归属：机械归档 / 去重合并 / 升级给 agent / 待处置 / 已处置。
    disposition = Column(String(20), default='pending')
    disposition_reason = Column(Text)
    # 2026-10-19 加宽 50→120：生产实测 15 条顶格值全为 agent 会话 ID（investor-session-*,恰 50 字符被调用方先裁）——处置人是审计归因字段，须容下完整会话 ID（迁移：20261019_watch_triggers_disposition_by_widen）
    disposition_by = Column(String(120))
    disposition_at = Column(DateTime)
    dup_of = Column(Integer)
    # 抑噪标记（REQ-c9f899 R6 / t8）：规则处于抑噪期时触发的触发记录标 true，
    # 仅供 P3 聚合与复盘，不推送、不进摘要队列。列由 t1 迁移 20260918 添加
    # （watch_triggers.suppressed BOOLEAN DEFAULT FALSE）。
    suppressed = Column(Boolean, default=False)
    # 触发 → 待办的溯源回填（REQ-c9f899 t12）：列由 t1 迁移 20260918 添加
    # （watch_triggers.todo_id INTEGER），t12 接线后由 WatchTriggerRepository.set_todo_id 写入。
    todo_id = Column(Integer)


def rule_to_dict(rule: WatchRule) -> dict:
    """序列化为 API 响应 dict（snake_case，与现有契约风格一致）"""
    return {
        'id': rule.id,
        'symbol': rule.symbol,
        'enabled': rule.enabled,
        'conditions': rule.conditions,
        'context': rule.context,
        'cost_price': float(rule.cost_price) if rule.cost_price is not None else None,
        'active_window': rule.active_window,
        'expires_at': rule.expires_at.isoformat() if rule.expires_at else None,
        'created_by': rule.created_by,
        'account': rule.account,
        'notify_mode': rule.notify_mode,
        'action_hint': rule.action_hint,
        'escalation_policy': rule.escalation_policy,
        'created_at': rule.created_at.isoformat() if rule.created_at else None,
        'updated_at': rule.updated_at.isoformat() if rule.updated_at else None,
        # ── 价值生命周期字段（REQ-f08def P1，RFC 014 v3 §7.1）──
        # 没有 intent/lifecycle_stage，agent 拿到触发不知道该回答什么问题。
        'intent': getattr(rule, 'intent', None),
        'lifecycle_stage': getattr(rule, 'lifecycle_stage', None),
        'scope': getattr(rule, 'scope', None),
        'target': getattr(rule, 'target', None),
        'linked_account': getattr(rule, 'linked_account', None),
        'created_from': getattr(rule, 'created_from', None),
        'next_action_hint': getattr(rule, 'next_action_hint', None),
        # 决策化改造（REQ-261016155500-4f2a）：结构化操作指引 + 机器注记
        'action_params': getattr(rule, 'action_params', None),
        'ops_notes': getattr(rule, 'ops_notes', None),
        # RFC 017（2026-10-21）：持仓状态 / 规则级盯盘频率。
        # position_state=None 表示**状态不可知**（NULL/缺列），消费方须 fail-open
        # 旧行为，不要把它当成 'none'（那会误判"确认无持仓"）。
        'position_state': rule_position_state(rule),
        'interval_sec': rule_interval_sec(rule),
        'last_reviewed_at': rule.last_reviewed_at.isoformat() if getattr(rule, 'last_reviewed_at', None) else None,
        'review_interval_days': getattr(rule, 'review_interval_days', None),
        'review_due_at': rule.review_due_at.isoformat() if getattr(rule, 'review_due_at', None) else None,
        'value_ledger': {
            'valuable_actions': getattr(rule, 'valuable_actions', 0) or 0,
            'valuable_reviews': getattr(rule, 'valuable_reviews', 0) or 0,
            'interventions': getattr(rule, 'interventions', 0) or 0,
            'noise_triggers': getattr(rule, 'noise_triggers', 0) or 0,
            'tokens_cost': getattr(rule, 'tokens_cost', 0.0) or 0.0,
            'last_value_at': rule.last_value_at.isoformat() if getattr(rule, 'last_value_at', None) else None,
        },
    }


def trigger_to_dict(t: WatchTrigger) -> dict:
    return {
        'id': t.id,
        'rule_id': t.rule_id,
        'symbol': t.symbol,
        'condition': t.condition,
        'trigger_price': float(t.trigger_price) if t.trigger_price is not None else None,
        'detail': t.detail,
        'agent_response': t.agent_response,
        'notified': t.notified,
        'triggered_at': t.triggered_at.isoformat() if t.triggered_at else None,
        # 处置状态机字段（REQ-f08def）
        'disposition': getattr(t, 'disposition', None),
        'disposition_reason': getattr(t, 'disposition_reason', None),
        'disposition_by': getattr(t, 'disposition_by', None),
        'disposition_at': t.disposition_at.isoformat() if getattr(t, 'disposition_at', None) else None,
        'dup_of': getattr(t, 'dup_of', None),
        # 抑噪标记（R6/t8）：true = 该触发产生于规则抑噪期，只进聚合不推送
        'suppressed': getattr(t, 'suppressed', None),
    }


class WatchRuleRepository(BaseORMRepository[WatchRule]):
    model = WatchRule

    #: 缺列兼容时只加载的"安全列"（= migration 之前的全部 ORM 列）。
    #: 类体里算一次，_rule_query 每次只做一次列表拼装。
    _SAFE_RULE_COLUMNS = tuple(
        c.name for c in WatchRule.__table__.columns if c.name not in NEW_RULE_COLUMNS
    )

    # ── 缺列兼容（RFC 017 §3：迁移未落库 / 已回滚时按旧行为 fail-open）────────
    #
    # 为什么需要：ORM 一旦声明了列，SQLAlchemy 的每一次 SELECT / INSERT / refresh
    # 都会带上它。若代码先于迁移上线（灰度、或回滚了 DDL），整表查询会直接
    # UndefinedColumn —— 不是"新功能不可用"，而是**盯盘整体停摆**。
    # 故这里做两件事，且只影响本仓储：
    #   读：预检缺列时用 load_only 排除新列（SQL 不带它），并用
    #       set_committed_value 注入"状态未知/频率未设置"（None）——
    #       值已提交，不会触发懒加载，也不会标脏；
    #   写：缺列时丢弃新字段（warn），创建走不 refresh 的提交路径。
    # 预检失败（无库/无权限/连接异常）按"列在位"处理：宁可走正常路径报真错，
    # 也不要把一个探活失败静默降级成"所有规则无状态"。
    def _new_columns_available(self) -> bool:
        try:
            bind = self.session.get_bind()
        except Exception:  # noqa: BLE001
            return True
        key = str(getattr(bind, 'url', bind))
        cached = _COLUMNS_PRESENT_CACHE.get(key)
        if cached is not None:
            return cached
        available = True
        missing = []
        try:
            # no_autoflush：预检是纯读，不该顺手把调用方未完成的写操作 flush 出去
            with self.session.no_autoflush:
                present = {row[0] for row in self.session.execute(_COLUMNS_SQL)}
            missing = [name for name in NEW_RULE_COLUMNS if name not in present]
            available = not missing
        except Exception as e:  # noqa: BLE001
            logger.warning('watch_rules 列预检失败，按新列在位处理', error=str(e))
            self._safe_rollback()
        if not available:
            logger.warning(
                'watch_rules 缺 position_state/interval_sec 列（迁移未落库），新字段按旧行为 fail-open',
                missing=missing,
            )
        _COLUMNS_PRESENT_CACHE[key] = available
        return available

    def _rule_query(self):
        """规则查询入口：缺列时排除新列（否则整表 UndefinedColumn）。"""
        q = self.session.query(WatchRule)
        if self._new_columns_available():
            return q
        return q.options(load_only(*[getattr(WatchRule, n) for n in self._SAFE_RULE_COLUMNS]))

    def _apply_legacy_defaults(self, rule):
        """缺列模式下给新属性注入"状态未知 / 频率未设置"（不标脏、不触发懒加载）。"""
        if rule is None or self._new_columns_available():
            return rule
        try:
            set_committed_value(rule, 'position_state', None)
            set_committed_value(rule, 'interval_sec', None)
        except Exception:  # noqa: BLE001 - 注入失败也不该让读路径崩
            logger.debug('legacy 默认值注入失败', rule_id=getattr(rule, 'id', None))
        return rule

    def _reload_rule(self, rule_id):
        if rule_id is None:
            return None
        try:
            rule = (self._rule_query()
                    .populate_existing()
                    .filter(WatchRule.id == rule_id)
                    .first())
        except SQLAlchemyError as e:
            logger.error('规则重载失败', rule_id=rule_id, error=str(e))
            self._safe_rollback()
            return None
        return self._apply_legacy_defaults(rule)

    def get_by_id(self, id_value):
        """覆盖基类：走 _rule_query（缺列兼容）+ 注入 legacy 默认值。"""
        try:
            if self._new_columns_available():
                rule = self.session.get(WatchRule, id_value)
            else:
                rule = (self._rule_query()
                        .filter(WatchRule.id == id_value)
                        .first())
        except SQLAlchemyError as e:
            logger.error('读取规则失败', rule_id=id_value, error=str(e))
            self._safe_rollback()
            return None
        return self._apply_legacy_defaults(rule)

    def _create_rule_row(self, rule: WatchRule):
        """落库新规则。缺列模式下走 Core INSERT（只列安全列）。

        为什么不能只用 ORM：ORM 的 INSERT 会为 `server_default` 列追加
        `RETURNING position_state, interval_sec`（SQLAlchemy 2.0 用 RETURNING 取
        服务端默认值），缺列库上照样 UndefinedColumn —— 实测踩过，故 legacy 分支
        直接对 `WatchRule.__table__` 发 Core INSERT（只带显式赋过值的安全列，
        其余列由 Column 默认值在 Core 阶段补齐），再按安全列重载回 ORM 对象。
        """
        if self._new_columns_available():
            return self.create(rule)
        table = WatchRule.__table__
        safe_columns = set(self._SAFE_RULE_COLUMNS) - {'id'}
        values = {k: v for k, v in vars(rule).items() if k in safe_columns}
        try:
            rule_id = self.session.execute(
                sa_insert(table).values(**values).returning(table.c.id)
            ).scalar()
            self.session.commit()
        except SQLAlchemyError as e:
            logger.error('创建规则失败（legacy schema：缺新列）', error=str(e))
            self._safe_rollback()
            return None
        return self._reload_rule(rule_id)

    def _save_rule_fields(self, rule_id: int, values: dict):
        """缺列模式下按"字段 → 值"发 Core UPDATE（只碰安全列，不 refresh 全列）。"""
        table = WatchRule.__table__
        values = dict(values)
        # 与正常路径一致：任何一次 update_fields 都推进 updated_at
        values['updated_at'] = datetime.now()
        try:
            with self.session.no_autoflush:
                self.session.execute(
                    sa_table_update(table).where(table.c.id == rule_id).values(**values)
                )
            self.session.commit()
        except SQLAlchemyError as e:
            logger.error('更新规则失败（legacy schema：缺新列）', rule_id=rule_id, error=str(e))
            self._safe_rollback()
            return None
        return self._reload_rule(rule_id)

    def create_rule(self, symbol, conditions, context=None, cost_price=None,
                    active_window=None, expires_at=None, created_by='agent',
                    account=None, linked_account=None,
                    intent=None, action_hint=None, action_params=None,
                    position_state=None, interval_sec=None) -> WatchRule:
        # 铁律下沉（2026-09-11，w-aebfddcd）：没有账户的规则不能进入买卖——在**仓储层**拦，
        # 这样任何创建路径（API / 内部服务 / 定时任务）都绕不过去。观察类规则放行。
        from qs_watch.domain.watch.services.rule_guard import guard_new_rule
        guard_new_rule(intent=intent, action_hint=action_hint, conditions=conditions,
                       account=(linked_account or account), symbol=symbol)
        available = self._new_columns_available()
        new_fields = {}
        if available:
            # 只在显式给值时写：不写 → INSERT 不带该列 → DB 默认 'none' 兜住存量语义
            if position_state is not None:
                new_fields['position_state'] = normalize_position_state(position_state)
            if interval_sec is not None:
                new_fields['interval_sec'] = normalize_interval_sec(interval_sec)
        elif position_state is not None or interval_sec is not None:
            logger.warning('watch_rules 缺新列，创建时忽略 position_state/interval_sec（fail-open 旧行为）',
                           symbol=symbol)
        # 账户归一：account 与 linked_account 是同一语义的两个字段，
        # 只传其一时另一个必须跟随——否则新建的规则在投送侧（读 linked_account）看起来"无账户"，
        # 触发时会被当成数据缺陷，而创建方以为自己给了账户。
        rule = WatchRule(
            symbol=symbol, conditions=conditions, context=context,
            cost_price=cost_price, active_window=active_window,
            expires_at=expires_at, created_by=created_by, enabled=True,
            account=account or linked_account,
            linked_account=linked_account or account,
            # 2026-09-11（w-aebfddcd）：这两个参数此前被**静默丢弃**（签名收了却不写库），
            # 导致"创建时声明 intent=exit_stop"的规则实际落库 intent=NULL，
            # 仓储层守卫与运行时都把它当观察类 —— 典型的参数收下不生效陷阱。
            intent=intent,
            action_hint=action_hint,
            action_params=action_params,
            **new_fields,
        )
        return self._create_rule_row(rule)

    def list_enabled(self) -> List[WatchRule]:
        """启用的规则（排除已过期）"""
        rows = (
            self._rule_query()
            .filter(WatchRule.enabled.is_(True))
            .filter((WatchRule.expires_at.is_(None)) | (WatchRule.expires_at > datetime.now()))
            .all()
        )
        return [self._apply_legacy_defaults(r) for r in rows]

    def list_rules(self, symbol: Optional[str] = None,
                   enabled: Optional[bool] = None,
                   account: Optional[str] = None) -> List[WatchRule]:
        """account=某账户时返回「该账户归属 + 通用观察(account IS NULL)」——
        看板按账户展示盯盘需要两组都可见；不传则返回全部。"""
        q = self._rule_query()
        if symbol:
            q = q.filter(WatchRule.symbol == symbol)
        if enabled is not None:
            q = q.filter(WatchRule.enabled.is_(enabled))
        if account:
            q = q.filter(or_(WatchRule.account == account, WatchRule.account.is_(None)))
        return [self._apply_legacy_defaults(r) for r in q.order_by(WatchRule.id.desc()).all()]

    def set_position_state(self, rule_id: int, state) -> Optional[WatchRule]:
        """写持仓状态（RFC 017 §2.2 双通道同步用：fill 事件 / 日频对账）。

        值经 normalize（None → 'none'），缺列时由 update_fields 按旧行为丢弃并 warn。
        """
        return self.update_fields(rule_id, position_state=normalize_position_state(state))

    def set_interval_sec(self, rule_id: int, interval_sec) -> Optional[WatchRule]:
        """写规则级频率（RFC 017 §2.3）。None = 恢复跟随全局档。"""
        return self.update_fields(rule_id, interval_sec=normalize_interval_sec(interval_sec))

    def update_fields(self, rule_id: int, **fields) -> Optional[WatchRule]:
        rule = self.get_by_id(rule_id)
        if rule is None:
            return None
        # 级联判定用：改动前的启用态（停用级联只在「启用 → 停用」跳变时触发一次）
        was_enabled = bool(rule.enabled)
        # 铁律下沉：按"改后状态"判——不许把观察规则改成买卖规则却不给账户，
        # 也不许把已有买卖规则的账户清空（任何调用方都绕不过）
        from qs_watch.domain.watch.services.rule_guard import (
            guard_disable_rule, guard_rule_change,
        )
        guard_rule_change(rule, {k: v for k, v in fields.items()
                                 if k in ('intent', 'action_hint', 'conditions',
                                          'account', 'linked_account')} or None)
        # 停用守卫（2026-10-20 用户裁定）：宪法级止损规则的停用必须随附理由
        # （ops_notes/context），裸 enabled=false 拒绝——300677 #103 静默停用事故的收口。
        # 卡口设在仓储层：API/批量/生命周期/引擎/自愈全部停用路径都经 update_fields，漏不掉。
        guard_disable_rule(rule, fields)

        available = self._new_columns_available()
        if not available:
            dropped = [k for k in fields if k in NEW_RULE_COLUMNS]
            if dropped:
                logger.warning('watch_rules 缺新列，更新忽略新字段（fail-open 旧行为）',
                               rule_id=rule_id, dropped=dropped)
                fields = {k: v for k, v in fields.items() if k not in NEW_RULE_COLUMNS}
        # RFC 017 写入归一：position_state 永远落 none/holding（NULL→none）；
        # interval_sec 落正整数秒或 NULL（NULL=跟随全局档，显式清空既有值也用 None）。
        if 'position_state' in fields:
            fields['position_state'] = normalize_position_state(fields['position_state'])
        if 'interval_sec' in fields:
            fields['interval_sec'] = normalize_interval_sec(fields['interval_sec'])

        allowed = {'symbol', 'enabled', 'conditions', 'context',
                   'cost_price', 'active_window', 'expires_at', 'account',
                   'notify_mode',  # 2026-09-05 补：notify_mode 曾被白名单静默丢弃
                   # 2026-09-11（w-c8cae280 / REQ-f08def Phase 3）：规则演化（改分级/改动作/改升级策略）
                   # 需要这两个字段可写，否则 agent 无法按 RFC 014 §4 的反馈边调整规则。
                   'action_hint', 'escalation_policy',
                   # REQ-f08def P2：规则重配置所需字段（价值账本计数由系统维护，不在此列）
                   'intent', 'lifecycle_stage', 'scope', 'target',
                   'linked_account', 'created_from', 'next_action_hint',
                   'review_interval_days', 'review_due_at',
                   # REQ-261016155500-4f2a：结构化操作指引与机器注记可写
                   'action_params', 'ops_notes',
                   # RFC 017（2026-10-21）：持仓状态与规则级频率经既有规则 CRUD 调整
                   'position_state', 'interval_sec'}
        if available:
            for key, value in fields.items():
                if key in allowed:
                    setattr(rule, key, value)
            rule.updated_at = datetime.now()
            updated = self.update(rule)
        else:
            # 缺列：一律走 Core UPDATE（不 setattr、不 refresh 全列）。
            # 若在此处 setattr 再 commit，ORM flush 仍会把新增列塞进语句/RETURNING。
            updated = self._save_rule_fields(
                rule_id, {k: v for k, v in fields.items() if k in allowed})
        # 级联归档（2026-10-19）：规则「启用 → 停用」时，它名下未收敛待办的触发链
        # 已断、工单永久无法执行——不埋掉的话 SLA 巡检会继续晋升/超时打扰用户
        # （生产实测：死工单挂 3 天晋升 3 次发 3 张超时卡，最后还要人工大扫除）。
        # 在此收口而非逐调用点改：全部停用路径（API 单改/批量、持仓生命周期、
        # 引擎、健康作业、合并工具）都走 update_fields，漏不掉。
        # 静默归档不发回执——"系统扔垃圾"不值得一张卡。
        if updated is not None and was_enabled and fields.get('enabled') is False:
            from adapters.outbound.repositories.watch_todo_repository import (
                WatchTodoRepository,
            )
            WatchTodoRepository().close_open_by_rule(rule_id)
        return updated

    def apply_intervention_ledger(self, rule_id: int, cost_delta: float,
                                  valuable: bool, commit: bool = False) -> None:
        """把一次介入的成本/价值记到规则的价值账本（quant.watch_rules）。

        迁移背景（2026-09-14，w-8b43d3b8，REQ-24e15d B4-c5）：原实现是
        adapters/outbound/repositories/watch_state_repository.py 里
        WatchInterventionRepository.record() 内联在介入 INSERT 之后的
        UPDATE quant.watch_rules（裸 SQL）。它写的是 **watch_rules** 而不是介入表，
        语义上属本仓储，故收口到这里；调用方与那次介入行共享同一事务。

        本仓此前**没有**任何方法承担这条账本自增（唯一写点就是那段裸 SQL），
        因此这里是新增方法而非复用既有方法。

        口径逐值对齐旧 SQL：
            interventions = COALESCE(interventions, 0) + 1
            tokens_cost   = COALESCE(tokens_cost, 0) + :cost
            last_value_at = CASE WHEN :valuable THEN NOW() ELSE last_value_at END

        Args:
            rule_id: 规则 id（调用方保证非 None）
            cost_delta: 本次介入成本（元），累加到 tokens_cost
            valuable: 本次介入是否"有价值"（outcome in handled/reviewed），
                      为真时把 last_value_at 推到数据库当前时间
            commit: 是否立即提交。**默认 False** —— 调用方（介入记账）必须与介入行
                    同事务提交，否则会出现"介入行回滚了、账本却已自增"。
        """
        stmt = (
            sa_update(WatchRule)
            .where(WatchRule.id == rule_id)
            .values(
                interventions=func.coalesce(WatchRule.interventions, 0) + 1,
                # 不显式给类型：NullType 直通，psycopg2 按 float8 发送，
                # 与旧 SQL 的裸 :cost 参数同形（避免被 Numeric 强转）。
                tokens_cost=func.coalesce(WatchRule.tokens_cost, 0)
                + bindparam('cost_delta', cost_delta),
                last_value_at=case(
                    (bindparam('valuable', valuable, type_=Boolean), func.now()),
                    else_=WatchRule.last_value_at,
                ),
            )
        )
        self.session.execute(stmt)
        if commit:
            self.session.commit()


class WatchTriggerRepository(BaseORMRepository[WatchTrigger]):
    model = WatchTrigger

    def record(self, rule_id, symbol, condition, trigger_price,
               detail=None, notified=False, disposition='pending',
               disposition_reason=None, disposition_by='system',
               dup_of=None, suppressed=False) -> WatchTrigger:
        """落一条触发 + 其处置初态（REQ-f08def）。

        disposition 由 domain/watch/services/disposition.decide() 决定：
        机械可判的（observe/message 类、去重合并）当场收敛，不唤醒 agent。

        suppressed（REQ-c9f899 R6 / t8）：规则处于抑噪期时置 true，表示该触发只进
        P3 聚合与复盘、不推送不进摘要队列。默认 False —— 既有调用方语义不变
        （新增 keyword 参数，位置参数顺序未动）。
        """
        trigger = WatchTrigger(
            rule_id=rule_id, symbol=symbol, condition=condition,
            trigger_price=trigger_price, detail=detail, notified=notified,
            disposition=disposition,
            disposition_reason=disposition_reason,
            disposition_by=disposition_by,
            disposition_at=datetime.now() if disposition not in ('pending', 'escalated') else None,
            dup_of=dup_of,
            suppressed=bool(suppressed),
        )
        return self.create(trigger)

    def set_todo_id(self, trigger_id: int, todo_id) -> None:
        """回填触发的 todo_id（触发→待办溯源，REQ-c9f899 t12）。

        同一个 trigger_id 只会有一条待办（引擎侧幂等），回填是溯源增益不是闭环前提；
        触发已被清理（get_by_id 返回 None）时静默返回，不抛。
        """
        if todo_id is None:
            return
        trigger = self.get_by_id(trigger_id)
        if trigger is None:
            return
        trigger.todo_id = int(todo_id)
        self.session.commit()

    def mark_notified(self, trigger_id: int, notified: bool) -> None:
        """回写触发的实际送达结果（REQ-261016155500-4f2a wt:engine:2）。

        先落库后发送架构下，落库时 notified=False，发送后经此方法回写——
        notified 字段从此等于真实送达与否（观测口径的事实源）。
        触发不存在时静默返回（与 set_todo_id 同口径）。
        """
        trigger = self.get_by_id(trigger_id)
        if trigger is None:
            return
        trigger.notified = bool(notified)
        self.session.commit()

    def latest_unsent(self, rule_id: int) -> Optional[WatchTrigger]:
        """该规则最近一条 notified=false 的触发（补发去重用，REQ-261016155500-4f2a）。

        只回一条（最新）；条件是否相同由调用方（notifier.retry_unsent）比对——
        不同条件的未送达记录不属于本次补发范围。
        """
        return (
            self.session.query(WatchTrigger)
            .filter(WatchTrigger.rule_id == rule_id,
                    WatchTrigger.notified.is_(False))
            .order_by(WatchTrigger.id.desc())
            .first()
        )

    def update_disposition(self, trigger_id: int, disposition: str,
                           reason: str = None, by: str = 'agent') -> Optional[WatchTrigger]:
        """处置一条触发（handled / ignored / expired）。ignored 必须带 reason。"""
        from qs_watch.domain.watch.services.disposition import DISPOSITION_IGNORED
        if disposition == DISPOSITION_IGNORED and not (reason or '').strip():
            raise ValueError('ignored 状态必须填写 reason（为什么知悉但不动作）')
        trigger = self.get_by_id(trigger_id)
        if trigger is None:
            return None
        trigger.disposition = disposition
        trigger.disposition_reason = reason
        trigger.disposition_by = by
        trigger.disposition_at = datetime.now()
        self.session.commit()
        return trigger


    def get_rule_trigger_stats(self) -> dict:
        """批量触发统计（元触发复核用，避免 N+1）：{rule_id: {today, last_at}}

        对应 domain/watch/ports.ITriggerHistoryRepository 的批量口径扩展。

        迁移背景（2026-09-14，w-8b43d3b8，REQ-24e15d B4-c5）：原实现用
        get_engine().connect() 自己开一条连接跑裸聚合——
            SELECT rule_id,
                   count(*) FILTER (WHERE triggered_at >= CURRENT_DATE) AS today_cnt,
                   max(triggered_at) AS last_at
              FROM quant.watch_triggers GROUP BY rule_id
        现改走 self.session + ORM 聚合：func.count().filter(...) 编出同形状的
        count(*) FILTER (WHERE ...)，CURRENT_DATE 仍由数据库求值
        （func.current_date()，不用应用时钟，避免时区/时钟差改变"今日"口径）。
        ⚠️ 刻意保留逐行 int(r[0]) 的取值方式及其边界：rule_id 为 NULL 的分组会让
        int(None) 抛 TypeError，被下面的 except 捕获后返回**已累计的部分结果**——
        这是旧实现的行为，本轮不修（另在报告中登记为既有缺陷）。
        """
        out = {}
        try:
            rows = (
                self.session.query(
                    WatchTrigger.rule_id,
                    func.count()
                    .filter(WatchTrigger.triggered_at >= func.current_date())
                    .label('today_cnt'),
                    func.max(WatchTrigger.triggered_at).label('last_at'),
                )
                .group_by(WatchTrigger.rule_id)
                .all()
            )
            for r in rows:
                out[int(r[0])] = {"today": int(r[1] or 0), "last_at": r[2]}
        except Exception as e:
            self._safe_rollback()
            import structlog
            structlog.get_logger(__name__).warning("批量触发统计读取失败", error=str(e))
        return out

    def get_last_triggered_at(self, rule_id: int):
        """某规则最近一次触发时间（无触发返回 None）。

        迁移背景（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：原实现是
        daily_jobs_bootstrap._watch_rule_health 里的
        SELECT MAX(triggered_at) FROM quant.watch_triggers WHERE rule_id = :rid，
        属 inbound 层裸 SQL，收口到这里。

        「无触发」有两种原因：该规则从未触发（无行）→ None；有行但 triggered_at 全为
        NULL → 也是 None。调用方据此区分"从未触发"与"30 天未触发"，与原来
        trigger_row[0] if trigger_row else None 的取值完全一致。
        """
        try:
            return (
                self.session.query(func.max(WatchTrigger.triggered_at))
                .filter(WatchTrigger.rule_id == rule_id)
                .scalar()
            )
        except Exception as e:  # noqa: BLE001
            self._safe_rollback()
            import structlog
            structlog.get_logger(__name__).warning("读取规则最近触发时间失败", rule_id=rule_id, error=str(e))
            raise

    def list_triggers(self, symbol: Optional[str] = None,
                      disposition: Optional[str] = None,
                      dispositions: Optional[tuple] = None,
                      limit: int = 200) -> List[WatchTrigger]:
        """按状态查触发（盘后未处置清单的数据源）"""
        q = self.session.query(WatchTrigger)
        if symbol:
            q = q.filter(WatchTrigger.symbol == symbol)
        if disposition:
            q = q.filter(WatchTrigger.disposition == disposition)
        if dispositions:
            q = q.filter(WatchTrigger.disposition.in_(list(dispositions)))
        return q.order_by(WatchTrigger.triggered_at.desc()).limit(limit).all()

    def count_older_unresolved(self, since: datetime,
                               dispositions: tuple) -> dict:
        """早于 since 的未处置触发统计（digest 积压可见，REQ-261016155500-4f2a wt:engine:4）。

        返回 {'count': N, 'oldest_at': 最早 triggered_at | None}——build_digest 的
        since 增量段只拉最近窗口，更早的未处置触发此前完全不可见（积压隐形）。
        """
        q = self.session.query(
            func.count(WatchTrigger.id),
            func.min(WatchTrigger.triggered_at),
        ).filter(
            WatchTrigger.disposition.in_(list(dispositions)),
            WatchTrigger.triggered_at < since,
        )
        count, oldest = q.one()
        return {'count': int(count or 0), 'oldest_at': oldest}

    def list_by_symbol(self, symbol: Optional[str] = None, limit: int = 50) -> List[WatchTrigger]:
        q = self.session.query(WatchTrigger)
        if symbol:
            q = q.filter(WatchTrigger.symbol == symbol)
        return q.order_by(WatchTrigger.triggered_at.desc()).limit(limit).all()
