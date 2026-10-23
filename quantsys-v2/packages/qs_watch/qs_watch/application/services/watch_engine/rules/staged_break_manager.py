"""staged_break 两段式伏击状态机（2026-10-19 P1，用户裁定：盯盘是「守伏击点」）

为什么要有它：裸 price_break 触及即发卡，阈值附近反复横跳时一天能刷几十次
（2026-10-19 实测规则 #248 单日 61 次触发、当日全库 471 次）。两段式把
「触及」与「信号」分开：触及只进观察态（静默），确认成立才进正常触发流水线。

状态机（每 规则×条件 一条）：

    WATCHING ──触及──▶ OBSERVING(touch_at, deadline) ──确认──▶ 产出 confirmed 结果 → 回 WATCHING
       ▲                     │
       └──窗口到期未确认──────┘  产出 expired（引擎归档 suppressed 样本，不通知）

持久化：快照挂在运行态 store 的专用方法（load_staged_states/save_staged_states，
适配器缺失时全部 no-op，纯内存行为与改造前等价——与 StateManager 同一纪律）。
observing 状态含截止时间，重启恢复后窗口语义不丢。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import structlog

from qs_watch.application.services.watch_engine.conditions import (
    DEFAULT_STAGED_WINDOW_MIN,
    EvalContext,
    EvalResult,
    eval_staged_confirm,
    eval_staged_touch,
)
from qs_watch.domain.watch.models import MetricKind

logger = structlog.get_logger(__name__)

#: process() 的产出类别
OUTCOME_WATCHING = 'watching'      # 未触及，待命
OUTCOME_ENTERED = 'entered'        # 本 tick 触及，进入观察态（静默）
OUTCOME_OBSERVING = 'observing'    # 观察中，确认未成立（静默）
OUTCOME_CONFIRMED = 'confirmed'    # 确认成立：result 可进正常触发流水线
OUTCOME_EXPIRED = 'expired'        # 窗口到期未确认：引擎归档样本，回到待命


class StagedBreakManager:
    """两段式状态机（内存为实，store 为持久化外壳；store=None 时全 no-op）"""

    def __init__(self, store=None):
        # key=(rule_id, cond_idx) → {'touch_at': dt, 'deadline': dt, 'touch_price': float}
        self._states: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self._store = store
        self._dirty = False

    # ── 主入口 ──────────────────────────────────────────────

    def process(self, rule_id: int, cond_idx: int, cond: dict, quote,
                ctx: EvalContext, now: datetime) -> Tuple[str, Optional[EvalResult]]:
        """推进一拍。返回 (outcome, eval_result)。

        eval_result 的用途：
          · confirmed → 交给引擎 _process_condition 走完整触发流水线；
          · expired   → 交给引擎归档 suppressed 样本（消息说明触及与窗口）；
          · 其余      → 仅供 fast-mode 距离判定（触及线越近 tick 越密），不产出事件。
        """
        params = cond.get('params') or {}
        key = (rule_id, cond_idx)
        st = self._states.get(key)
        touch = eval_staged_touch(cond, quote)

        if st is None:
            if not touch.triggered:
                return OUTCOME_WATCHING, touch
            window_min = float(params.get('window_min', DEFAULT_STAGED_WINDOW_MIN))
            self._states[key] = {
                'touch_at': now,
                'deadline': now + timedelta(minutes=window_min),
                'touch_price': float(quote.price),
            }
            self._dirty = True
            logger.info('伏击触及，进入观察态（静默）', rule_id=rule_id, cond_idx=cond_idx,
                        symbol=getattr(quote, 'symbol', None),
                        price=float(quote.price), window_min=window_min)
            return OUTCOME_ENTERED, touch

        # OBSERVING
        if now >= st['deadline']:
            del self._states[key]
            self._dirty = True
            result = EvalResult(
                triggered=False, value=float(quote.price), distance_ratio=None,
                message=(f'伏击观察窗到期未确认：{st["touch_at"].strftime("%H:%M")} 触及 '
                         f'{st["touch_price"]}，{(params.get("window_min", DEFAULT_STAGED_WINDOW_MIN)):.0f}min '
                         f'内确认条件未成立，回到待命'),
                metric=MetricKind.PRICE, unit='元')
            logger.info('伏击观察窗到期未确认，归档样本并回到待命',
                        rule_id=rule_id, cond_idx=cond_idx,
                        symbol=getattr(quote, 'symbol', None))
            return OUTCOME_EXPIRED, result

        confirm = eval_staged_confirm(cond, quote, ctx, now, st['touch_at'])
        if confirm.degraded:
            # 数据缺失（如放量确认无均量）：不判死也不确认，等到期归档
            return OUTCOME_OBSERVING, touch
        if not confirm.triggered:
            return OUTCOME_OBSERVING, touch

        del self._states[key]
        self._dirty = True
        result = EvalResult(
            triggered=True, value=confirm.value, distance_ratio=0.0,
            message=(f'伏击确认：{st["touch_at"].strftime("%H:%M")} 触及 {st["touch_price"]} → '
                     f'{confirm.message}'),
            degraded=False, metric=confirm.metric, unit=confirm.unit)
        logger.info('伏击确认成立，进入触发流水线', rule_id=rule_id, cond_idx=cond_idx,
                    symbol=getattr(quote, 'symbol', None), message=result.message)
        return OUTCOME_CONFIRMED, result

    # ── 生命周期 ────────────────────────────────────────────

    def reset_daily(self) -> None:
        """跨天清空：观察窗不隔夜（隔夜后的「企稳」语义已变，重新等触及）。"""
        if self._states:
            self._states.clear()
            self._dirty = True

    def pending(self) -> int:
        """当前观察中的条目数（观测用）"""
        return len(self._states)

    # ── 持久化（store 缺失/不支持时全 no-op）────────────────

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """可 JSON 序列化的快照：{'<rule_id>:<cond_idx>': {...isoformat...}}"""
        return {
            f'{rid}:{cidx}': {
                'touch_at': st['touch_at'].isoformat(),
                'deadline': st['deadline'].isoformat(),
                'touch_price': st['touch_price'],
            }
            for (rid, cidx), st in self._states.items()
        }

    def restore(self, rows: Dict[str, Dict[str, Any]]) -> int:
        """从快照恢复；坏行跳过不抛错（恢复失败不该打挂引擎启动）。"""
        restored = 0
        for key, st in (rows or {}).items():
            try:
                rid, cidx = (int(x) for x in key.split(':'))
                self._states[(rid, cidx)] = {
                    'touch_at': datetime.fromisoformat(st['touch_at']),
                    'deadline': datetime.fromisoformat(st['deadline']),
                    'touch_price': float(st['touch_price']),
                }
                restored += 1
            except Exception:  # noqa: BLE001 - 坏行跳过
                logger.warning('staged 运行态行格式非法，已跳过', key=key)
        return restored

    def restore_from_store(self) -> int:
        loader = getattr(self._store, 'load_staged_states', None)
        if not callable(loader):
            return 0
        try:
            return self.restore(loader() or {})
        except Exception as e:  # noqa: BLE001 - 响亮但不致命（列未迁移时降级纯内存）
            logger.error('staged 运行态恢复失败（本进程从待命开始，观察窗丢失）',
                         error=str(e))
            return 0

    def flush(self) -> bool:
        """脏才写；写入失败不抛错（tick 绝不被落库打挂）。返回是否写了库。"""
        saver = getattr(self._store, 'save_staged_states', None)
        if not callable(saver) or not self._dirty:
            return False
        try:
            saver(self.snapshot())
            self._dirty = False
            return True
        except Exception as e:  # noqa: BLE001
            logger.error('staged 运行态落库失败（内存态保留，下拍重试）', error=str(e))
            return False
