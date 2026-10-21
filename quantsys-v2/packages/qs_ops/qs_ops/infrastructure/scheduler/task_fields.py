"""调度任务字段契约（2026-09-13 新建，REQ-c970e5 / w-a1402b8c）

为什么单独成模块：`domain`（六域）是写库字段，但**创建/更新路径此前完全不接它** ——
端口、域服务、仓储三处签名都没有该参数，创建接口也不透传 → 每个新建任务 born-NULL，
看板对账「v2 侧 domain 缺 N」于是反复变脏（2026-09-02 加列当天回填 30 个 → 0 NULL；
2026-09-12 又修 12 条；2026-09-13 新建 6 条再 NULL）。

同类根因 2026-09-02 已在 OS 侧 `public.tasks.agent_line` 上发生过一次
（NOT NULL DEFAULT 'profit_engine' + Go Create() 的 INSERT 不含该列 → 静默继承默认值，
见 docs/work-logs/2026-09/scheduler-line-tagging-20260902.md 第 74-75 行）。
故这里**刻意不设 DEFAULT**：宁可 NULL 被对账显式暴露，也不要静默继承。

取值须与 ORM 列注释一致：infrastructure/persistence/orm/models/scheduler.py
（'data/signal/trading/analysis/report/monitor'）。
"""
from typing import Optional

SCHEDULER_DOMAINS = ('data', 'signal', 'trading', 'analysis', 'report', 'monitor')


def validate_domain(value: Optional[str]) -> Optional[str]:
    """校验六域取值。

    - None / 空串 → None（表示未打标，交给看板对账与 v2_health_check 暴露，不猜）
    - 白名单内 → 规范化后的字符串
    - 其它 → ValueError（由调用方转成 400 / 写入前拒绝）
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text not in SCHEDULER_DOMAINS:
        raise ValueError(f"Invalid domain {text!r}, must be one of {list(SCHEDULER_DOMAINS)}")
    return text
