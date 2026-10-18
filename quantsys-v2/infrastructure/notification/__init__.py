"""已迁移占位 shim：notification 基础设施层（渠道/格式化器）已抽离为独立二方包 `qs-notification`（packages/qs_notification）。

保留本兼容层用于吸收未跟踪代码/实验脚本中的旧路径 import。
新代码一律使用 `from qs_notification.infrastructure import FeishuChannel`；本 shim 计划在 30 天观察期后删除。
"""
import warnings as _warnings

try:
    import qs_notification.infrastructure as _pkg
    from qs_notification.infrastructure import *  # noqa: F401,F403
    __path__ = _pkg.__path__
except ImportError as _e:  # pragma: no cover
    _warnings.warn(f"旧路径 infrastructure.notification 已迁移为 qs_notification.infrastructure，但包不可导入: {_e}")
