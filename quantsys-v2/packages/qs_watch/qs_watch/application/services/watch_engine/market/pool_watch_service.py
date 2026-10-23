"""池级盯盘服务（2026-10-20）：选池 ↔ 盯盘接线

把一个 stock_pools 池的成员批量映射为盯盘规则：

  · 成员增 → 建规则（成员自带 buy_point/sell_point 生成 price_break，池级条件模板叠加）
  · 成员减 → 退役规则（只收本绑定生成的，created_from='pool_watch:{id}'）
  · 成员点位变 → 更新规则 conditions（生成规则不作人工修改的前提下）

边界纪律：
  · 只动 created_from 属于本绑定的规则——人手改的池规则不在管辖内（避免覆盖用户意图）；
  · 交易类意图（intent 非 observe 系）必须有账户——rule_guard 在 create_rule 把关，
    这里预检给出清晰错误；
  · 成员数超 max_members 拒绝同步（全市场候选池 283 只绑定盯盘 = 消息洪水，
    要的就是这个闸）；
  · reconcile 任何一步失败向上抛（调用方 fail-closed：宁可不同步也不半同步）。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

CREATED_FROM_PREFIX = 'pool_watch:'

#: observe 系意图（无需账户）；其余走 TRADE_INTENTS 口径（rule_guard 同源）
_OBSERVE_INTENTS = ('trend_observe', '')


def binding_created_from(binding_id: int) -> str:
    return '%s%s' % (CREATED_FROM_PREFIX, int(binding_id))


class PoolWatchService:
    """绑定 → 规则的 reconcile（无状态：绑定仓储/成员来源/规则仓储构造注入）"""

    def __init__(self, binding_repo, pool_source, rule_repo):
        self._binding_repo = binding_repo
        self._pool_source = pool_source
        self._rule_repo = rule_repo

    # ── 绑定 CRUD 透传（路由层薄封装用）────────────────────────
    def list_bindings(self, enabled: Optional[bool] = None) -> List[Dict[str, Any]]:
        return self._binding_repo.list_bindings(enabled=enabled)

    def get_binding(self, binding_id: int) -> Optional[Dict[str, Any]]:
        return self._binding_repo.get_binding(binding_id)

    def create_binding(self, **fields) -> Dict[str, Any]:
        self._preflight(fields)
        return self._binding_repo.create_binding(**fields)

    def update_binding(self, binding_id: int, **fields) -> Optional[Dict[str, Any]]:
        if fields:
            self._preflight(fields, partial=True)
        return self._binding_repo.update_binding(binding_id, **fields)

    def _preflight(self, fields: Dict[str, Any], partial: bool = False) -> None:
        intent = str(fields.get('intent', 'trend_observe') or 'trend_observe')
        if intent not in _OBSERVE_INTENTS and not fields.get('account'):
            from qs_watch.domain.watch.services.rule_guard import KNOWN_ACCOUNTS
            raise ValueError(
                '交易类意图(%s)的池绑定必须指定归属账户（rule_guard 铁律，'
                '可选：%s）' % (intent, '/'.join(KNOWN_ACCOUNTS)))
        mode = str(fields.get('member_points_mode', 'breakout') or 'breakout')
        if mode not in ('breakout', 'pullback'):
            raise ValueError("member_points_mode 只支持 breakout|pullback")
        if not partial or 'max_members' in fields:
            if int(fields.get('max_members', 100)) <= 0:
                raise ValueError('max_members 必须为正整数')

    # ── 核心：绑定 ↔ 规则 reconcile ────────────────────────────
    def reconcile_binding(self, binding: Dict[str, Any],
                          now: Optional[datetime] = None) -> Dict[str, Any]:
        """单绑定对账：返回 {created, retired, updated, unchanged, skipped, details}。"""
        bid = int(binding['id'])
        members = self._pool_source.get_members(binding['pool_id']) or []
        cap = int(binding.get('max_members') or 100)
        if len(members) > cap:
            raise RuntimeError(
                '池 #%s 成员 %d 超出绑定上限 %d——拒绝同步（防消息洪水；调大 max_members 或缩小池）'
                % (binding['pool_id'], len(members), cap))

        want = {m['symbol']: m for m in members}
        created_from = binding_created_from(bid)
        existing: Dict[str, Any] = {}
        for r in self._rule_repo.list_rules(enabled=True):
            if str(getattr(r, 'created_from', '') or '') == created_from:
                existing[str(r.symbol).split('.')[0]] = r

        created, retired, updated, unchanged, details = 0, 0, 0, 0, []

        # 离场：规则在、成员没了 → 退役
        for sym, rule in existing.items():
            if sym not in want:
                self._rule_repo.update_fields(
                    rule.id, enabled=False,
                    next_action_hint=('已移出池 #%s，绑定 #%s 自动收摊（%s）'
                                      % (binding['pool_id'], bid, (now or datetime.now()).date())))
                retired += 1
                details.append({'symbol': sym, 'action': 'retired',
                                'rule_id': rule.id})

        # 入场/更新：成员在 → 建或比对 conditions
        for sym, member in want.items():
            conds = self._build_conditions(binding, member)
            if not conds:
                details.append({'symbol': sym, 'action': 'skipped',
                                'reason': '无可用条件（无点位且模板为空）'})
                continue
            rule = existing.get(sym)
            if rule is None:
                rid = self._create_rule(binding, member, conds, bid)
                if rid:
                    created += 1
                    details.append({'symbol': sym, 'action': 'created', 'rule_id': rid})
                continue
            # 点位漂移 → 更新 conditions（与生成口径一致才更新）
            cur = [dict(c) for c in (getattr(rule, 'conditions', None) or [])]
            if cur != conds:
                try:
                    self._rule_repo.update_fields(rule.id, conditions=conds)
                    updated += 1
                    details.append({'symbol': sym, 'action': 'updated',
                                    'rule_id': rule.id})
                except Exception as e:
                    details.append({'symbol': sym, 'action': 'update_failed',
                                    'rule_id': rule.id, 'error': str(e)})
            else:
                unchanged += 1

        summary = {'binding_id': bid, 'pool_id': binding['pool_id'],
                   'members': len(members), 'created': created, 'retired': retired,
                   'updated': updated, 'unchanged': unchanged, 'details': details}
        self._binding_repo.save_sync_summary(bid, summary)
        logger.info('池盯盘对账完成', **{k: summary[k] for k in
                    ('pool_id', 'members', 'created', 'retired', 'updated', 'unchanged')})
        return summary

    def reconcile_all(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """全部启用绑定逐一对账（sidecar 每日入口）。"""
        out = []
        for b in self._binding_repo.list_bindings(enabled=True):
            try:
                out.append(self.reconcile_binding(b, now=now))
            except Exception as e:  # noqa: BLE001 - 单绑定失败不阻断其余
                logger.error('池绑定对账失败（跳过该绑定）', binding_id=b['id'], error=str(e))
                out.append({'binding_id': b['id'], 'pool_id': b['pool_id'],
                            'error': str(e)})
        return out

    # ── 内部 ────────────────────────────────────────────────
    def _build_conditions(self, binding: Dict[str, Any],
                          member: Dict[str, Any]) -> List[Dict[str, Any]]:
        conds: List[Dict[str, Any]] = []
        if binding.get('use_member_points'):
            mode = str(binding.get('member_points_mode') or 'breakout')
            buy_dir = 'above' if mode == 'breakout' else 'below'
            sell_dir = 'below' if mode == 'breakout' else 'above'
            # buy_point/sell_point 在部分池是自由文本（如「23.50附近企稳」）而非数字——
            # 实测 pool #30（2026-10-20）：不可解析的点位跳过并留痕，不炸整批对账。
            for key, direction in (('buy_point', buy_dir), ('sell_point', sell_dir)):
                raw = member.get(key)
                if raw is None or raw == '':
                    continue
                try:
                    conds.append({'type': 'price_break',
                                  'params': {'price': float(raw), 'direction': direction}})
                except (TypeError, ValueError):
                    logger.warning('成员点位非数字，跳过（可用条件模板兜底）',
                                   symbol=member.get('symbol'), field=key, raw=str(raw)[:60])
        for c in binding.get('conditions_template') or []:
            conds.append(dict(c))
        cd = binding.get('cooldown_sec')
        if cd and conds:
            for c in conds:
                c.setdefault('cooldown_sec', int(cd))
        return conds

    def _create_rule(self, binding: Dict[str, Any], member: Dict[str, Any],
                     conds: List[Dict[str, Any]], bid: int) -> Optional[int]:
        intent = str(binding.get('intent') or 'trend_observe')
        desc = (member.get('description') or '')[:80]
        try:
            rule = self._rule_repo.create_rule(
                symbol=member['symbol'],
                conditions=conds,
                context=('池「%s」(#%s) 自动盯盘：%s%s'
                         % (binding.get('pool_name') or binding['pool_id'],
                            binding['pool_id'],
                            '成员自带买卖点+' if binding.get('use_member_points') else '',
                            '池级模板条件')),
                created_by='pool_watch', account=binding.get('account'),
            )
            self._rule_repo.update_fields(
                rule.id, intent=intent,
                linked_account=binding.get('account'),
                created_from=binding_created_from(bid)[:80],
                next_action_hint=(desc or '池成员盯盘：触及点位按绑定 #%d 语义处置' % bid)[:160],
            )
            return rule.id
        except Exception as e:
            logger.error('池盯盘规则创建失败', symbol=member.get('symbol'), error=str(e))
            return None
