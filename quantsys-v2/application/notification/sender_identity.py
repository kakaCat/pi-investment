"""外发消息的发送方身份（REQ-261007101318-c392 FR-3）。

**为什么需要这个模块**（取证 E7 + 用户 2026-10-07 的原话「执行可能是另外一个机器执行的」）：

- v2 与 agent-ts 的 `FEISHU_WEBHOOK` **完全相同**（两份 `.env` 的 sha1 一致）⇒ 飞书里显示
  同一个机器人，卡面与机器人名**无法区分发送方**；
- 本机 v2 在保留日志窗口内**零条** watch 类型外发（77 条全是 `system_alert`），
  而 `NotificationService(repository=None)` ⇒ **外发零持久化**，事后无处可查；
- 结论：不给卡片本身写来源，就永远无法回答"这张卡谁发的"。

**口径**：`<kind>@<hostname>#<pid>`（进程级，无配置项）。
- 跨机分辨靠 `hostname` 段——正是"另一台机器执行"这一情形；
- 跨进程分辨靠 `pid` 段——区分 API 进程 / 一次性脚本 / 其他调用方；
- 不引入配置：容器与单机都够用，且不需要运维同步任何东西。
"""
from __future__ import annotations

import os
import socket

#: 盯盘外发的来源前缀（卡面尾注与审计都用它）
WATCH_SENDER_KIND = 'v2-watch'


def current_sender_id(kind: str = WATCH_SENDER_KIND) -> str:
    """当前进程的发送方标识：`v2-watch@<host>#<pid>`。

    取主机名失败时退化为 `unknown-host`（**绝不因此抛错**——身份标注失败不该阻断通知）。
    """
    try:
        host = socket.gethostname() or 'unknown-host'
    except OSError:
        host = 'unknown-host'
    return f'{kind}@{host}#{os.getpid()}'
