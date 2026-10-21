"""流水线阶段共享的归档理由文案。

为什么下沉到这里：这两条 reason 原先定义在 `engine.py`，被 `_process_condition`
的抽取段（日上限 / 抑噪短路）直接引用。阶段模块若反向 import engine 会形成
import cycle（engine → pipeline → engine），故落在本模块；`engine.py` 继续
re-export 它们，`from ...engine import DAILY_CAP_REASON` 的既有调用方零改动。
"""
from qs_watch.application.services.watch_engine.conditions import DEFAULT_DAILY_EMIT_CAP

#: 抑噪期触发的归档理由（REQ-c9f899 R6 / t8）：与 NoiseSelfHealService 已经建出的
#: 「修规则」待办呼应——告诉读者这条触发为什么不推送、去哪里看它的处置。
SUPPRESSED_TRIGGER_REASON = '规则处于抑噪期（反复触发），已改造为修规则待办'

#: 每日通知上限归档文案（REQ-261016155500-4f2a wt:engine:1）：每规则每条件每日
#: ≤ DEFAULT_DAILY_EMIT_CAP 次通知，超限只归档不打扰（与抑噪同通道，reason 区分）。
#: 直接内插常量（曾用 %d 占位忘记格式化，数字会原样落库——2026-10-16 审核修正）。
DAILY_CAP_REASON = ('当日通知次数已达上限（每规则每条件每日 '
                    f'{DEFAULT_DAILY_EMIT_CAP} 次），仅归档不推送')
