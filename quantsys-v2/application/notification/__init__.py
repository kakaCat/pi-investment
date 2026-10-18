"""已迁移占位 shim：notification 应用层已抽离为独立二方包 `qs-notification`（packages/qs_notification）。

保留本兼容层用于吸收未跟踪代码/实验脚本中的旧路径 import。
新代码一律使用 `from qs_notification.application import NotificationFacade`；本 shim 计划在 30 天观察期后删除。
"""
import warnings as _warnings

try:
    import qs_notification.application as _pkg
    from qs_notification.application import *  # noqa: F401,F403
    __path__ = _pkg.__path__
except ImportError as _e:  # pragma: no cover
    _warnings.warn(f"旧路径 application.notification 已迁移为 qs_notification.application，但包不可导入: {_e}")
